import pytest

from ledgato.adapters.base import ExecutionReceipt
from ledgato.approvals import ApprovalStore
from ledgato.authority import AuthorityStore
from ledgato.crypto import Signer
from ledgato.gateway import EnforcementGateway
from ledgato.ledger import Ledger
from ledgato.models import Action, Policy


class FakeAdapter:
    name = "fake"

    def __init__(self):
        self.executions = 0
        self.verifications = 0
        self.denial_verifications = 0
        self.capabilities = {"fake.safe", "fake.risky", "fake.evil"}

    def discover(self, agent: str) -> set[str]:
        return set(self.capabilities)

    def execute(self, action: Action) -> ExecutionReceipt:
        self.executions += 1
        return ExecutionReceipt(
            adapter=self.name,
            action=action.tool,
            executed=True,
            status="ok",
            external_id=f"receipt-{self.executions}",
            result={"tool": action.tool},
        )

    def verify(self, action: Action, receipt: ExecutionReceipt):
        self.verifications += 1
        return {"verified": True, "method": "fake_readback", "receipt": receipt.external_id}

    def verify_denied(self, action: Action):
        self.denial_verifications += 1
        return {"verified": True, "method": "fake_denial_readback", "executed": False}


@pytest.fixture()
def pieces(tmp_path):
    adapter = FakeAdapter()
    authority = AuthorityStore(tmp_path / "authority.json")
    approvals = ApprovalStore(tmp_path / "approvals.json")
    ledger = Ledger(signer=Signer(), path=tmp_path / "ledger.jsonl")
    return adapter, authority, approvals, ledger


def build_gateway(pieces, policy):
    adapter, authority, approvals, ledger = pieces
    return EnforcementGateway(
        policies={policy.agent: policy},
        adapters={"fake": adapter},
        ledger=ledger,
        authority=authority,
        approvals=approvals,
    )


def test_deny_never_calls_downstream_execute(pieces):
    adapter, _, _, _ = pieces
    gateway = build_gateway(
        pieces,
        Policy(agent="agent", allow_tools={"fake.safe"}, impact_max="write"),
    )

    result = gateway.execute(
        agent="agent",
        adapter="fake",
        action=Action(tool="fake.evil", impact="write"),
        task_id="task-1",
    )

    assert result["status"] == "DENY"
    assert result["executed"] is False
    assert result["boundary_crossed"] is False
    assert adapter.executions == 0
    assert adapter.denial_verifications == 1
    assert result["verification"]["verified"] is True


def test_allow_executes_and_verifies_afterward(pieces):
    adapter, _, _, _ = pieces
    gateway = build_gateway(
        pieces,
        Policy(agent="agent", allow_tools={"fake.safe"}, impact_max="write"),
    )

    result = gateway.execute(
        agent="agent",
        adapter="fake",
        action=Action(tool="fake.safe", impact="write"),
        task_id="task-1",
    )

    assert result["status"] == "ALLOW"
    assert result["executed"] is True
    assert adapter.executions == 1
    assert adapter.verifications == 1
    assert result["verification"]["verified"] is True


def test_approval_pauses_then_resumes_exactly_once(pieces):
    adapter, _, _, _ = pieces
    gateway = build_gateway(
        pieces,
        Policy(
            agent="agent",
            allow_tools={"fake.risky"},
            impact_max="destructive",
            approval_tools={"fake.risky"},
        ),
    )

    pending = gateway.execute(
        agent="agent",
        adapter="fake",
        action=Action(tool="fake.risky", impact="destructive"),
        task_id="task-approve",
        requested_by="agent-os",
    )
    assert pending["status"] == "APPROVE"
    assert pending["paused"] is True
    assert adapter.executions == 0

    approval_id = pending["approval"]["id"]
    approved = gateway.approve(approval_id, decided_by="human@example.com", jit_ttl_seconds=60)
    assert approved["jit_grant"]["task_id"] == "task-approve"
    token = approved["approval"]["resume_token"]

    resumed = gateway.resume(approval_id, resume_token=token)
    assert resumed["status"] == "ALLOW"
    assert resumed["executed"] is True
    assert adapter.executions == 1

    with pytest.raises(ValueError):
        gateway.resume(approval_id, resume_token=token)
    assert adapter.executions == 1


def test_revoked_grant_blocks_future_execution(pieces):
    adapter, authority, _, _ = pieces
    gateway = build_gateway(
        pieces,
        Policy(
            agent="agent",
            allow_tools={"fake.safe"},
            impact_max="write",
            require_grant=True,
        ),
    )
    grant = authority.issue(
        agent="agent",
        granted_by="owner",
        purpose="task",
        tools={"fake.safe"},
        impact_max="write",
        task_id="task-1",
        ttl_seconds=300,
    )

    first = gateway.execute(
        agent="agent",
        adapter="fake",
        action=Action(tool="fake.safe", impact="write"),
        task_id="task-1",
        grant_id=grant.id,
    )
    assert first["status"] == "ALLOW"
    assert adapter.executions == 1

    authority.revoke(grant.id, revoked_by="owner", reason="task complete")
    second = gateway.execute(
        agent="agent",
        adapter="fake",
        action=Action(tool="fake.safe", impact="write"),
        task_id="task-1",
        grant_id=grant.id,
    )
    assert second["status"] == "DENY"
    assert "expired or revoked" in second["decision"]["reason"]
    assert adapter.executions == 1


def test_live_discovery_reports_permission_drift(pieces):
    gateway = build_gateway(
        pieces,
        Policy(agent="agent", allow_tools={"fake.safe", "fake.risky"}, impact_max="write"),
    )

    result = gateway.discover(agent="agent", adapter="fake")
    assert result["drift"]["drift"] is True
    assert result["drift"]["undeclared_gains"] == ["fake.evil"]
