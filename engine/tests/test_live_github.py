"""Stage 6 — real GitHub boundary, against the disposable lab only.

SKIPPED BY DEFAULT. Requires LEDGATO_LIVE_TESTS=1 plus LEDGATO_GITHUB_TOKEN and
LEDGATO_GITHUB_REPOSITORY, and the repository name must identify it as a lab
(see conftest.live_repository).

These are the tests that actually move `github_lab_merge` off UNVERIFIED, because
they are the only ones whose evidence is provider-backed. Everything else in the
suite runs against in-process doubles and proves control flow, not enforcement.

The credential used here must be held by the gateway and must NOT be reachable
from the agent sandbox — that separation is what lab/sandbox.sh enforces and
what this file assumes rather than establishes.
"""
import os

import pytest

from ledgato.adapters.github import GitHubAdapter
from ledgato.approvals import ApprovalStore
from ledgato.authority import AuthorityStore
from ledgato.boundary import BoundaryStore
from ledgato.crypto import Signer
from ledgato.gateway import EnforcementGateway
from ledgato.ledger import Ledger
from ledgato.models import Action, Policy

pytestmark = pytest.mark.live

MERGE = "github.pull.merge"


@pytest.fixture()
def adapter(live_repository):
    return GitHubAdapter(
        repository=live_repository,
        token=os.environ["LEDGATO_GITHUB_TOKEN"],
        api_url=os.getenv("LEDGATO_GITHUB_API_URL"),
    )


@pytest.fixture()
def lab(tmp_path, adapter, live_repository):
    boundaries = BoundaryStore(tmp_path / "boundaries.json")
    boundaries.register(id="github_lab_merge", provider="github",
                        resource=live_repository, action=MERGE)
    gw = EnforcementGateway(
        policies={"lab-agent": Policy(agent="lab-agent",
                                      allow_tools={"github.issue.comment"},
                                      deny_tools={MERGE},
                                      impact_max="write")},
        adapters={"github": adapter},
        ledger=Ledger(signer=Signer(), path=tmp_path / "ledger.jsonl"),
        authority=AuthorityStore(tmp_path / "authority.json"),
        approvals=ApprovalStore(tmp_path / "approvals.json"),
        boundaries=boundaries,
    )
    return gw, boundaries, adapter


def _pr_number() -> int:
    pr = os.getenv("LEDGATO_LAB_PR_NUMBER")
    if not pr:
        pytest.skip("set LEDGATO_LAB_PR_NUMBER to an open PR in the lab repo")
    return int(pr)


def test_live_discovery_reports_actual_credential_permissions(lab):
    """What can the gateway credential really do? Recorded, not assumed."""
    gw, _, _ = lab
    result = gw.discover(agent="lab-agent", adapter="github")
    assert "github.repo.read" in result["observed"]
    # Recorded for the report: an over-broad credential is itself a finding.
    print("observed capabilities:", sorted(result["observed"]))


def test_denied_merge_never_reaches_github(lab):
    """The core Stage 6 case: DENY, and GitHub confirms the PR is still open."""
    gw, boundaries, adapter = lab
    pr = _pr_number()

    result = gw.execute(
        agent="lab-agent", adapter="github",
        action=Action(tool=MERGE, impact="destructive", params={"pull_number": pr}),
        task_id="live-deny",
    )

    assert result["status"] == "DENY"
    assert result["executed"] is False
    assert result["boundary_crossed"] is False

    # Provider-side truth, not the gateway's own report.
    state = adapter._call("GET", f"/repos/{adapter.repository}/pulls/{pr}")
    assert state["merged"] is False, "DENIED PR was merged — boundary failure"

    boundary = boundaries.get("github_lab_merge")
    assert boundary.bypass_status == "UNVERIFIED", (
        "a single DENY must not verify the boundary"
    )
    assert any(e.kind == "provider_readback" for e in boundary.verification_evidence)


def test_denied_merge_is_recorded_as_provider_backed_evidence(lab):
    gw, boundaries, _ = lab
    pr = _pr_number()
    gw.execute(agent="lab-agent", adapter="github",
               action=Action(tool=MERGE, impact="destructive",
                             params={"pull_number": pr}),
               task_id="live-evidence")
    readbacks = [e for e in boundaries.get("github_lab_merge").verification_evidence
                 if e.kind == "provider_readback"]
    assert readbacks, "live adapter must file provider_readback evidence"
    assert readbacks[0].protected_action_occurred is False


@pytest.mark.skip(reason="Stage 6 approval+merge: enable once the lab PR is disposable per-run")
def test_approved_merge_executes_once_and_is_verified(lab):
    """Placeholder for the destructive half of Stage 6.

    Left explicitly skipped rather than written speculatively: it merges a real
    PR, so it needs a per-run throwaway branch/PR fixture that does not exist
    yet. Writing it against a hand-made PR would make the suite non-repeatable
    and would quietly consume the lab.
    """
