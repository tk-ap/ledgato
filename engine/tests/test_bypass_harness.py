"""Stage 7 — deterministic bypass harness.

Every vector here runs against a fake provider adapter and needs no GitHub
credential. These cover the approval-abuse, authority-escalation and
failure-behavior families of the directive's attack suite.

Direct-provider vectors (real merge API, git push, gh CLI, cached tokens,
credential helpers) are NOT here: they require the disposable lab and a scoped
Ledgato-held credential, and are tracked as outstanding.

For each vector the decisive question is the directive's #3: *did the protected
downstream action occur?* `adapter.merged` is the ground truth — a Ledgato-side
error that left `merged` empty is a reliability bug, not a bypass.
"""
import threading

import pytest

from ledgato.adapters.base import ExecutionReceipt
from ledgato.approvals import ApprovalStore
from ledgato.authority import AuthorityStore
from ledgato.crypto import Signer
from ledgato.gateway import EnforcementGateway
from ledgato.ledger import Ledger
from ledgato.models import Action, Policy


class FakeGitHub:
    """Records every merge that actually reached the provider."""

    name = "github"

    def __init__(self, fail_execute=False, fail_verify=False):
        self.merged: list[int] = []
        self.fail_execute = fail_execute
        self.fail_verify = fail_verify

    def discover(self, agent):
        return {"github.pull.merge"}

    def execute(self, action):
        if self.fail_execute:
            raise RuntimeError("provider timeout")
        pr = action.params.get("pull_number")
        self.merged.append(pr)
        return ExecutionReceipt(
            adapter=self.name, action=action.tool, executed=True,
            status="ok", external_id=f"merge-{pr}", result={"pr": pr},
        )

    def verify(self, action, receipt):
        if self.fail_verify:
            return {"verified": False, "reason": "readback mismatch"}
        return {"verified": True}

    def verify_denied(self, action):
        return {"verified": True, "executed": False}


def build(tmp_path, adapter, *, approval_gated=True, require_grant=False):
    policy = Policy(
        agent="lab-agent",
        allow_tools={"github.pull.merge"},
        impact_max="destructive",
        approval_tools={"github.pull.merge"} if approval_gated else set(),
        require_grant=require_grant,
    )
    return EnforcementGateway(
        policies={"lab-agent": policy},
        adapters={"github": adapter},
        ledger=Ledger(signer=Signer(), path=tmp_path / "ledger.jsonl"),
        authority=AuthorityStore(tmp_path / "authority.json"),
        approvals=ApprovalStore(tmp_path / "approvals.json"),
    )


def merge_action(pr: int) -> Action:
    return Action(tool="github.pull.merge", impact="destructive", params={"pull_number": pr})


def request_merge(gw, pr, task_id="task-1", grant_id=None):
    return gw.execute(
        agent="lab-agent", adapter="github", action=merge_action(pr),
        task_id=task_id, grant_id=grant_id,
    )


@pytest.fixture()
def lab(tmp_path):
    adapter = FakeGitHub()
    return build(tmp_path, adapter), adapter


# =====================================================================
# Approval abuse
# =====================================================================

def test_resume_replay_does_not_merge_twice(lab):
    gw, adapter = lab
    pending = request_merge(gw, 1)
    approved = gw.approve(pending["approval"]["id"], decided_by="tk", jit_ttl_seconds=300)
    token = approved["approval"]["resume_token"]
    gw.resume(pending["approval"]["id"], resume_token=token)
    assert adapter.merged == [1]

    with pytest.raises(ValueError):
        gw.resume(pending["approval"]["id"], resume_token=token)
    assert adapter.merged == [1]          # decisive: no second merge


def test_forged_resume_token_rejected(lab):
    gw, adapter = lab
    pending = request_merge(gw, 1)
    gw.approve(pending["approval"]["id"], decided_by="tk", jit_ttl_seconds=300)
    with pytest.raises((PermissionError, ValueError)):
        gw.resume(pending["approval"]["id"], resume_token="forged-token")
    assert adapter.merged == []


def test_resume_before_approval_rejected(lab):
    gw, adapter = lab
    pending = request_merge(gw, 1)
    with pytest.raises(ValueError, match="not APPROVED"):
        gw.resume(pending["approval"]["id"], resume_token="anything")
    assert adapter.merged == []


def test_resume_after_denial_rejected(lab):
    gw, adapter = lab
    pending = request_merge(gw, 1)
    gw.deny_approval(pending["approval"]["id"], decided_by="tk", reason="no")
    with pytest.raises(ValueError):
        gw.resume(pending["approval"]["id"], resume_token="anything")
    assert adapter.merged == []


def test_resume_executes_stored_action_not_a_caller_supplied_one(lab):
    """Mutation-after-approval is structurally impossible via resume.

    resume() takes only an approval id and token; the action is read back from
    the stored approval record, so there is no parameter through which a
    different PR could be substituted.
    """
    gw, adapter = lab
    pending = request_merge(gw, 1)
    approved = gw.approve(pending["approval"]["id"], decided_by="tk", jit_ttl_seconds=300)
    gw.resume(pending["approval"]["id"], resume_token=approved["approval"]["resume_token"])
    assert adapter.merged == [1]          # the approved PR, and only it


def test_jit_grant_cannot_launder_approval_onto_a_different_pr(lab):
    """The central approval-laundering vector.

    A human approves merging PR #1, which mints a JIT grant. The agent then
    tries to spend that grant on PR #99. The approval gate re-triggers, so the
    unapproved merge does not occur.
    """
    gw, adapter = lab
    pending = request_merge(gw, 1)
    approved = gw.approve(pending["approval"]["id"], decided_by="tk", jit_ttl_seconds=300)
    jit = approved["jit_grant"]

    attack = request_merge(gw, 99, grant_id=jit["id"])

    assert attack["status"] == "APPROVE"          # re-gated, not allowed
    assert attack.get("executed") is not True
    assert 99 not in adapter.merged


def test_jit_grant_cannot_be_spent_on_a_different_tool(tmp_path):
    adapter = FakeGitHub()
    gw = build(tmp_path, adapter)
    gw.policies["lab-agent"].allow_tools.add("github.repo.delete")
    pending = request_merge(gw, 1)
    approved = gw.approve(pending["approval"]["id"], decided_by="tk", jit_ttl_seconds=300)

    result = gw.execute(
        agent="lab-agent", adapter="github",
        action=Action(tool="github.repo.delete", impact="destructive"),
        task_id="task-1", grant_id=approved["jit_grant"]["id"],
    )
    assert result["status"] != "ALLOW"
    assert adapter.merged == []


def test_expired_jit_grant_blocks_execution(tmp_path):
    adapter = FakeGitHub()
    gw = build(tmp_path, adapter, approval_gated=False, require_grant=True)
    grant = gw.authority.issue(
        agent="lab-agent", granted_by="tk", purpose="merge",
        tools={"github.pull.merge"}, impact_max="destructive",
        task_id="task-1", ttl_seconds=-1,          # already expired
    )
    result = request_merge(gw, 1, grant_id=grant.id)
    assert result["status"] == "DENY"
    assert adapter.merged == []


def test_revoked_grant_blocks_subsequent_merge(tmp_path):
    adapter = FakeGitHub()
    gw = build(tmp_path, adapter, approval_gated=False, require_grant=True)
    grant = gw.authority.issue(
        agent="lab-agent", granted_by="tk", purpose="merge",
        tools={"github.pull.merge"}, impact_max="destructive",
        task_id="task-1", ttl_seconds=300,
    )
    assert request_merge(gw, 1, grant_id=grant.id)["status"] == "ALLOW"
    gw.authority.revoke(grant.id, revoked_by="tk", reason="done")

    after = request_merge(gw, 2, grant_id=grant.id)
    assert after["status"] == "DENY"
    assert adapter.merged == [1]          # PR 2 never merged


def test_concurrent_duplicate_resume_merges_once(lab):
    """Race the resume endpoint; exactly one merge must reach the provider."""
    gw, adapter = lab
    pending = request_merge(gw, 1)
    approved = gw.approve(pending["approval"]["id"], decided_by="tk", jit_ttl_seconds=300)
    token = approved["approval"]["resume_token"]
    approval_id = pending["approval"]["id"]

    results, errors = [], []
    barrier = threading.Barrier(8)

    def attempt():
        barrier.wait()
        try:
            results.append(gw.resume(approval_id, resume_token=token))
        except Exception as exc:      # noqa: BLE001 - recording, not handling
            errors.append(exc)

    threads = [threading.Thread(target=attempt) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert adapter.merged == [1], f"expected exactly one merge, got {adapter.merged}"
    assert len(results) == 1
    assert len(errors) == 7


def test_restart_between_approval_and_resume_still_merges_once(tmp_path):
    """State is file-backed; a restart must not reopen the approval."""
    adapter = FakeGitHub()
    gw = build(tmp_path, adapter)
    pending = request_merge(gw, 1)
    approved = gw.approve(pending["approval"]["id"], decided_by="tk", jit_ttl_seconds=300)
    token = approved["approval"]["resume_token"]
    approval_id = pending["approval"]["id"]

    # Simulate a process restart: fresh gateway over the same state files.
    gw2 = build(tmp_path, adapter)
    gw2.resume(approval_id, resume_token=token)
    assert adapter.merged == [1]

    gw3 = build(tmp_path, adapter)
    with pytest.raises(ValueError):
        gw3.resume(approval_id, resume_token=token)
    assert adapter.merged == [1]


# =====================================================================
# Authority escalation
# =====================================================================

def test_agent_cannot_merge_without_any_grant_when_grant_required(tmp_path):
    adapter = FakeGitHub()
    gw = build(tmp_path, adapter, approval_gated=False, require_grant=True)
    result = request_merge(gw, 1)
    assert result["status"] == "DENY"
    assert adapter.merged == []


def test_unknown_agent_cannot_execute(lab):
    gw, adapter = lab
    with pytest.raises(KeyError):
        gw.execute(agent="ghost-agent", adapter="github",
                   action=merge_action(1), task_id="t")
    assert adapter.merged == []


def test_tool_outside_policy_is_denied(lab):
    gw, adapter = lab
    result = gw.execute(
        agent="lab-agent", adapter="github",
        action=Action(tool="github.repo.delete", impact="destructive"), task_id="t",
    )
    assert result["status"] == "DENY"
    assert adapter.merged == []


# =====================================================================
# Failure behavior — Ledgato failing must not open a merge path
# =====================================================================

def test_provider_error_reports_failure_and_merges_nothing(tmp_path):
    adapter = FakeGitHub(fail_execute=True)
    gw = build(tmp_path, adapter)
    pending = request_merge(gw, 1)
    approved = gw.approve(pending["approval"]["id"], decided_by="tk", jit_ttl_seconds=300)
    with pytest.raises(RuntimeError):
        gw.resume(pending["approval"]["id"], resume_token=approved["approval"]["resume_token"])
    assert adapter.merged == []


def test_failed_verification_is_surfaced_not_swallowed(tmp_path):
    adapter = FakeGitHub(fail_verify=True)
    gw = build(tmp_path, adapter)
    pending = request_merge(gw, 1)
    approved = gw.approve(pending["approval"]["id"], decided_by="tk", jit_ttl_seconds=300)
    result = gw.resume(pending["approval"]["id"], resume_token=approved["approval"]["resume_token"])
    assert result["verification"]["verified"] is False


def test_corrupt_approval_store_fails_closed(tmp_path):
    adapter = FakeGitHub()
    gw = build(tmp_path, adapter)
    pending = request_merge(gw, 1)
    gw.approve(pending["approval"]["id"], decided_by="tk", jit_ttl_seconds=300)

    (tmp_path / "approvals.json").write_text("{ this is not valid json")
    with pytest.raises(Exception):
        build(tmp_path, adapter)
    assert adapter.merged == []
