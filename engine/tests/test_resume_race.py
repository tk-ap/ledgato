"""Regression: one human approval must yield exactly one protected action.

This reproduces a bypass found by the Stage 7 harness. `ApprovalStore.consume`
checked `status` against the process's in-memory copy of file-backed state, so
several uvicorn workers could each observe APPROVED and each execute. Racing
resume across OS processes reliably produced 2-3 real merges from a single
approval; the equivalent threaded test passed, because the GIL hid the window.

Threads alone are therefore not sufficient coverage for this class of bug.
"""
import multiprocessing as mp
import pathlib

from ledgato.adapters.base import ExecutionReceipt
from ledgato.approvals import ApprovalStore
from ledgato.authority import AuthorityStore
from ledgato.crypto import Signer
from ledgato.gateway import EnforcementGateway
from ledgato.ledger import Ledger
from ledgato.models import Action, Policy

PROCESSES = 12


class SinkAdapter:
    name = "github"

    def __init__(self, sink):
        self.sink = sink

    def discover(self, agent):
        return {"github.pull.merge"}

    def execute(self, action):
        self.sink.append(action.params.get("pull_number"))
        return ExecutionReceipt(
            adapter="github", action=action.tool, executed=True,
            status="ok", external_id="m", result={},
        )

    def verify(self, action, receipt):
        return {"verified": True}

    def verify_denied(self, action):
        return {"verified": True, "executed": False}


def _gateway(tmp, sink):
    tmp = pathlib.Path(tmp)
    return EnforcementGateway(
        policies={
            "lab-agent": Policy(
                agent="lab-agent", allow_tools={"github.pull.merge"},
                impact_max="destructive", approval_tools={"github.pull.merge"},
            )
        },
        adapters={"github": SinkAdapter(sink)},
        ledger=Ledger(signer=Signer(), path=tmp / "ledger.jsonl"),
        authority=AuthorityStore(tmp / "authority.json"),
        approvals=ApprovalStore(tmp / "approvals.json"),
    )


def _worker(tmp, approval_id, token, sink, barrier):
    barrier.wait()
    try:
        _gateway(tmp, sink).resume(approval_id, resume_token=token)
    except Exception:
        pass          # losing the race is the correct outcome


def test_concurrent_resume_across_processes_merges_exactly_once(tmp_path):
    with mp.Manager() as mgr:
        sink = mgr.list()
        gw = _gateway(tmp_path, sink)
        pending = gw.execute(
            agent="lab-agent", adapter="github",
            action=Action(tool="github.pull.merge", impact="destructive",
                          params={"pull_number": 1}),
            task_id="task-race",
        )
        approved = gw.approve(pending["approval"]["id"], decided_by="tk", jit_ttl_seconds=300)
        approval_id = pending["approval"]["id"]
        token = approved["approval"]["resume_token"]

        barrier = mgr.Barrier(PROCESSES)
        procs = [
            mp.Process(target=_worker, args=(str(tmp_path), approval_id, token, sink, barrier))
            for _ in range(PROCESSES)
        ]
        for p in procs:
            p.start()
        for p in procs:
            p.join(timeout=30)

        merges = list(sink)

    assert merges == [1], (
        f"one approval produced {len(merges)} protected actions: {merges} "
        "— approval replay bypass has regressed"
    )
