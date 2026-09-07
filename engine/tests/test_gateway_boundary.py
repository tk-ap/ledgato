"""Gateway -> BoundaryStore wiring.

Closes the Stage 2 gap: Ledgato recorded decisions in the ledger but never
against the boundary they concern. The load-bearing property is that this
wiring can only *weaken* a boundary claim, never strengthen it on its own.
"""
import pytest

from ledgato.adapters.base import ExecutionReceipt
from ledgato.approvals import ApprovalStore
from ledgato.authority import AuthorityStore
from ledgato.boundary import BoundaryStore
from ledgato.crypto import Signer
from ledgato.gateway import EnforcementGateway
from ledgato.ledger import Ledger
from ledgato.models import Action, Policy

REPO = "tk-ap/ledgato-enforcement-lab"


class FakeGitHub:
    """In-process double. Deliberately NOT a live provider."""

    name = "github"
    is_live_provider = False

    def __init__(self):
        self.boundary_resource = REPO
        self.merged: list[int] = []

    def discover(self, agent):
        return {"github.pull.merge"}

    def execute(self, action):
        pr = action.params.get("pull_number")
        self.merged.append(pr)
        return ExecutionReceipt(adapter="github", action=action.tool, executed=True,
                                status="ok", external_id=f"m{pr}", result={})

    def verify(self, action, receipt):
        return {"verified": True, "method": "fake"}

    def verify_denied(self, action):
        return {"verified": True, "executed": False, "method": "fake"}


class LiveishGitHub(FakeGitHub):
    """Stands in for a real adapter purely to exercise the liveness branch."""

    is_live_provider = True


def build(tmp_path, adapter, *, approval_gated=False, register=True):
    boundaries = BoundaryStore(tmp_path / "boundaries.json")
    if register:
        boundaries.register(id="github_lab_merge", provider="github",
                            resource=REPO, action="github.pull.merge")
    gw = EnforcementGateway(
        policies={"lab-agent": Policy(
            agent="lab-agent", allow_tools={"github.pull.merge"},
            impact_max="destructive",
            approval_tools={"github.pull.merge"} if approval_gated else set(),
        )},
        adapters={"github": adapter},
        ledger=Ledger(signer=Signer(), path=tmp_path / "ledger.jsonl"),
        authority=AuthorityStore(tmp_path / "authority.json"),
        approvals=ApprovalStore(tmp_path / "approvals.json"),
        boundaries=boundaries,
    )
    return gw, boundaries


def merge(gw, pr=1, tool="github.pull.merge"):
    return gw.execute(agent="lab-agent", adapter="github",
                      action=Action(tool=tool, impact="destructive",
                                    params={"pull_number": pr}),
                      task_id="t")


def kinds(boundaries):
    return [e.kind for e in boundaries.get("github_lab_merge").verification_evidence]


# --- decisions are filed ---------------------------------------------------

def test_allow_is_filed_as_boundary_evidence(tmp_path):
    gw, boundaries = build(tmp_path, FakeGitHub())
    result = merge(gw)
    assert result["status"] == "ALLOW"
    evidence = boundaries.get("github_lab_merge").verification_evidence
    assert [e.outcome for e in evidence if e.kind == "decision"] == ["ALLOW"]
    assert evidence[0].ledger_entry_id == result["attestation_id"]


def test_deny_is_filed_as_boundary_evidence(tmp_path):
    gw, boundaries = build(tmp_path, FakeGitHub())
    # Deny the merge tool itself, so the denied action still matches the
    # registered boundary. (Emptying allow_tools would not deny at all — an
    # empty allowlist disables the check; see engine.py:85.)
    gw.policies["lab-agent"].deny_tools = {"github.pull.merge"}
    result = merge(gw)
    assert result["status"] == "DENY"
    decisions = [e for e in boundaries.get("github_lab_merge").verification_evidence
                 if e.kind == "decision"]
    assert [d.outcome for d in decisions] == ["DENY"]
    assert decisions[0].protected_action_occurred is False


def test_approval_pause_is_filed(tmp_path):
    gw, boundaries = build(tmp_path, FakeGitHub(), approval_gated=True)
    assert merge(gw)["status"] == "APPROVE"
    assert "APPROVE" in [e.outcome for e in
                         boundaries.get("github_lab_merge").verification_evidence]


# --- the load-bearing property --------------------------------------------

def test_decisions_never_advance_bypass_status(tmp_path):
    """Any number of decisions leaves the boundary UNVERIFIED."""
    gw, boundaries = build(tmp_path, FakeGitHub())
    for pr in range(15):
        merge(gw, pr)
    gw.policies["lab-agent"].deny_tools = {"github.pull.merge"}
    for pr in range(15):
        merge(gw, pr)
    assert boundaries.get("github_lab_merge").bypass_status == "UNVERIFIED"


def test_fake_adapter_cannot_produce_provider_readback(tmp_path):
    """Otherwise an in-process double satisfies the VERIFIED gate."""
    gw, boundaries = build(tmp_path, FakeGitHub())
    merge(gw)
    assert "provider_readback" not in kinds(boundaries)


def test_live_adapter_does_produce_provider_readback(tmp_path):
    gw, boundaries = build(tmp_path, LiveishGitHub())
    merge(gw)
    assert "provider_readback" in kinds(boundaries)


def test_gateway_decisions_alone_still_cannot_verify(tmp_path):
    """End to end: run real traffic, then try to claim VERIFIED."""
    gw, boundaries = build(tmp_path, LiveishGitHub())
    merge(gw)
    gw.policies["lab-agent"].deny_tools = {"github.pull.merge"}
    merge(gw, 2)
    with pytest.raises(ValueError, match="no bypass/leakage/escalation attempts"):
        boundaries.set_status("github_lab_merge", "VERIFIED",
                              attested_by="c", justification="traffic looks fine")


# --- no auto-inventory -----------------------------------------------------

def test_unregistered_boundary_is_not_created(tmp_path):
    gw, boundaries = build(tmp_path, FakeGitHub(), register=False)
    assert merge(gw)["status"] == "ALLOW"
    assert boundaries.list() == []


def test_action_without_matching_boundary_is_ignored(tmp_path):
    gw, boundaries = build(tmp_path, FakeGitHub())
    gw.policies["lab-agent"].allow_tools.add("github.issue.comment")
    gw.execute(agent="lab-agent", adapter="github",
               action=Action(tool="github.issue.comment", impact="write"), task_id="t")
    assert kinds(boundaries) == []


def test_gateway_without_boundary_store_still_works(tmp_path):
    adapter = FakeGitHub()
    gw = EnforcementGateway(
        policies={"lab-agent": Policy(agent="lab-agent",
                                      allow_tools={"github.pull.merge"},
                                      impact_max="destructive")},
        adapters={"github": adapter},
        ledger=Ledger(signer=Signer(), path=tmp_path / "l.jsonl"),
        authority=AuthorityStore(tmp_path / "a.json"),
        approvals=ApprovalStore(tmp_path / "ap.json"),
    )
    assert merge(gw)["status"] == "ALLOW"
    assert adapter.merged == [1]
