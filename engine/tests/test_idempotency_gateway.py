import pytest

from ledgato.adapters.base import ExecutionReceipt
from ledgato.approvals import ApprovalStore
from ledgato.authority import AuthorityStore
from ledgato.crypto import Signer
from ledgato.gateway import EnforcementGateway
from ledgato.idempotency import IdempotencyConflict, IdempotencyPending, IdempotencyStore
from ledgato.ledger import Ledger
from ledgato.models import Action, Policy


class CountingAdapter:
    name = "fake"

    def __init__(self):
        self.executions = 0

    def discover(self, agent: str) -> set[str]:
        return {"fake.safe"}

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
        return {"verified": True, "receipt": receipt.external_id}

    def verify_denied(self, action: Action):
        return {"verified": True, "executed": False}


def make_gateway(tmp_path, adapter, *, store=None):
    return EnforcementGateway(
        policies={"agent": Policy(agent="agent", allow_tools={"fake.safe"}, impact_max="write")},
        adapters={"fake": adapter},
        ledger=Ledger(signer=Signer(), path=tmp_path / "ledger.jsonl"),
        authority=AuthorityStore(tmp_path / "authority.json"),
        approvals=ApprovalStore(tmp_path / "approvals.json"),
        idempotency=store or IdempotencyStore(tmp_path / "idempotency.json"),
    )


def test_same_key_replays_result_without_second_execution(tmp_path):
    adapter = CountingAdapter()
    gateway = make_gateway(tmp_path, adapter)
    action = Action(tool="fake.safe", impact="write")

    first = gateway.execute(
        agent="agent",
        adapter="fake",
        action=action,
        task_id="task-1",
        idempotency_key="operation-1",
    )
    second = gateway.execute(
        agent="agent",
        adapter="fake",
        action=action,
        task_id="task-1",
        idempotency_key="operation-1",
    )

    assert first["executed"] is True
    assert first["idempotent_replay"] is False
    assert second["executed"] is True
    assert second["idempotent_replay"] is True
    assert second["attestation_id"] == first["attestation_id"]
    assert adapter.executions == 1


def test_completed_key_survives_restart_and_does_not_reexecute(tmp_path):
    first_adapter = CountingAdapter()
    first_gateway = make_gateway(tmp_path, first_adapter)
    action = Action(tool="fake.safe", impact="write")

    first = first_gateway.execute(
        agent="agent",
        adapter="fake",
        action=action,
        task_id="task-restart",
        idempotency_key="operation-restart",
    )
    assert first_adapter.executions == 1

    second_adapter = CountingAdapter()
    reloaded = IdempotencyStore(tmp_path / "idempotency.json")
    second_gateway = make_gateway(tmp_path, second_adapter, store=reloaded)
    replay = second_gateway.execute(
        agent="agent",
        adapter="fake",
        action=action,
        task_id="task-restart",
        idempotency_key="operation-restart",
    )

    assert replay["idempotent_replay"] is True
    assert replay["attestation_id"] == first["attestation_id"]
    assert second_adapter.executions == 0


def test_reusing_key_for_different_request_is_rejected(tmp_path):
    adapter = CountingAdapter()
    gateway = make_gateway(tmp_path, adapter)

    gateway.execute(
        agent="agent",
        adapter="fake",
        action=Action(tool="fake.safe", impact="write", params={"target": "one"}),
        task_id="task-1",
        idempotency_key="operation-conflict",
    )

    with pytest.raises(IdempotencyConflict):
        gateway.execute(
            agent="agent",
            adapter="fake",
            action=Action(tool="fake.safe", impact="write", params={"target": "two"}),
            task_id="task-1",
            idempotency_key="operation-conflict",
        )
    assert adapter.executions == 1


def test_unresolved_pending_record_fails_closed_after_restart(tmp_path):
    store_path = tmp_path / "idempotency.json"
    store = IdempotencyStore(store_path)
    request = {
        "agent": "agent",
        "adapter": "fake",
        "action": Action(tool="fake.safe", impact="write").to_dict(),
        "task_id": "task-uncertain",
        "grant_id": None,
        "requested_by": None,
    }
    assert store.begin("operation-uncertain", request) is None

    reloaded = IdempotencyStore(store_path)
    with pytest.raises(IdempotencyPending):
        reloaded.begin("operation-uncertain", request)
