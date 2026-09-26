import pytest

from ledgato.adapters.x402 import X402Adapter
from ledgato.approvals import ApprovalStore
from ledgato.authority import AuthorityStore
from ledgato.crypto import Signer
from ledgato.gateway import EnforcementGateway
from ledgato.ledger import Ledger
from ledgato.models import Action, Policy


class FakePaymentClient:
    def __init__(self):
        self.calls = []

    def request(self, *, method, url, params, json_body, headers):
        self.calls.append(
            {
                "method": method,
                "url": url,
                "params": params,
                "json": json_body,
                "headers": dict(headers),
            }
        )
        return {
            "status_code": 200,
            "url": url,
            "content_type": "application/json",
            "body": {"ok": True},
            "settlement": {
                "success": True,
                "transaction": "0xabc123",
                "network": "eip155:84532",
            },
            "payment_response_header_sha256": "a" * 64,
        }


@pytest.fixture()
def payment_adapter():
    client = FakePaymentClient()
    adapter = X402Adapter(
        client=client,
        allowed_hosts=["paid.example"],
        live_provider=False,
    )
    return adapter, client


def _gateway(tmp_path, adapter, policy):
    return EnforcementGateway(
        policies={policy.agent: policy},
        adapters={"x402": adapter},
        ledger=Ledger(signer=Signer(), path=tmp_path / "ledger.jsonl"),
        authority=AuthorityStore(tmp_path / "authority.json"),
        approvals=ApprovalStore(tmp_path / "approvals.json"),
    )


def _payment_action(**params):
    body = {
        "url": "https://paid.example/resource",
        "method": "GET",
    }
    body.update(params)
    return Action(
        tool="x402.pay",
        params=body,
        domain="paid.example",
        impact="write",
        intent="purchase a paid API response",
    )


def test_x402_adapter_returns_settlement_receipt(payment_adapter):
    adapter, client = payment_adapter

    receipt = adapter.execute(_payment_action(params={"city": "Los Angeles"}))
    verification = adapter.verify(_payment_action(), receipt)

    assert len(client.calls) == 1
    assert receipt.executed is True
    assert receipt.status == "settled"
    assert receipt.external_id == "0xabc123"
    assert receipt.result["body"] == {"ok": True}
    assert verification["verified"] is True
    assert verification["network"] == "eip155:84532"
    assert verification["onchain_finality_verified"] is False


def test_x402_adapter_rejects_unallowlisted_host_before_transport(payment_adapter):
    adapter, client = payment_adapter

    with pytest.raises(ValueError, match="not allowlisted"):
        adapter.execute(
            _payment_action(url="https://evil.example/resource")
        )

    assert client.calls == []


@pytest.mark.parametrize(
    "headers",
    [
        {"PAYMENT-SIGNATURE": "agent-supplied"},
        {"Authorization": "Bearer secret"},
        {"Cookie": "session=secret"},
    ],
)
def test_x402_adapter_rejects_protected_headers(payment_adapter, headers):
    adapter, client = payment_adapter

    with pytest.raises(ValueError, match="protected header"):
        adapter.execute(_payment_action(headers=headers))

    assert client.calls == []


def test_gateway_deny_never_invokes_x402_client(tmp_path, payment_adapter):
    adapter, client = payment_adapter
    gateway = _gateway(
        tmp_path,
        adapter,
        Policy(agent="agent", allow_tools={"other.tool"}, impact_max="write"),
    )

    result = gateway.execute(
        agent="agent",
        adapter="x402",
        action=_payment_action(),
        task_id="task-denied-payment",
    )

    assert result["status"] == "DENY"
    assert result["executed"] is False
    assert client.calls == []


def test_gateway_approval_pauses_before_x402_then_resumes_once(tmp_path, payment_adapter):
    adapter, client = payment_adapter
    gateway = _gateway(
        tmp_path,
        adapter,
        Policy(
            agent="agent",
            allow_tools={"x402.pay"},
            approval_tools={"x402.pay"},
            impact_max="write",
        ),
    )

    pending = gateway.execute(
        agent="agent",
        adapter="x402",
        action=_payment_action(),
        task_id="task-approved-payment",
        requested_by="agent-os",
    )

    assert pending["status"] == "APPROVE"
    assert pending["paused"] is True
    assert client.calls == []

    approved = gateway.approve(
        pending["approval"]["id"],
        decided_by="owner",
        jit_ttl_seconds=60,
    )
    result = gateway.resume(
        pending["approval"]["id"],
        resume_token=approved["approval"]["resume_token"],
    )

    assert result["status"] == "ALLOW"
    assert result["executed"] is True
    assert result["verification"]["verified"] is True
    assert len(client.calls) == 1

    with pytest.raises(ValueError):
        gateway.resume(
            pending["approval"]["id"],
            resume_token=approved["approval"]["resume_token"],
        )
    assert len(client.calls) == 1


def test_gateway_allow_invokes_x402_once_and_records_settlement(tmp_path, payment_adapter):
    adapter, client = payment_adapter
    gateway = _gateway(
        tmp_path,
        adapter,
        Policy(
            agent="agent",
            allow_tools={"x402.pay"},
            impact_max="write",
        ),
    )

    result = gateway.execute(
        agent="agent",
        adapter="x402",
        action=_payment_action(),
        task_id="task-direct-payment",
        idempotency_key="payment-1",
    )
    replay = gateway.execute(
        agent="agent",
        adapter="x402",
        action=_payment_action(),
        task_id="task-direct-payment",
        idempotency_key="payment-1",
    )

    assert result["status"] == "ALLOW"
    assert result["receipt"]["external_id"] == "0xabc123"
    assert result["verification"]["verified"] is True
    assert replay["idempotent_replay"] is True
    assert len(client.calls) == 1
