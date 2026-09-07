import pytest

from ledgato.boundary import BoundaryStore


@pytest.fixture()
def store(tmp_path):
    return BoundaryStore(tmp_path / "boundaries.json")


@pytest.fixture()
def lab(store):
    store.register(
        id="github_lab_merge",
        provider="github",
        resource="tk-ap/ledgato-enforcement-lab",
        action="github.pull.merge",
    )
    return store


def test_new_boundary_starts_unverified(lab):
    boundary = lab.get("github_lab_merge")
    assert boundary.bypass_status == "UNVERIFIED"
    assert boundary.failure_mode == "CLOSED"
    assert boundary.gateway_credential_owner == "ledgato"
    assert boundary.verification_evidence == []


def test_duplicate_registration_rejected(lab):
    with pytest.raises(ValueError, match="already registered"):
        lab.register(
            id="github_lab_merge",
            provider="github",
            resource="other",
            action="github.pull.merge",
        )


# --- the core Stage 2 rule -------------------------------------------------

def test_deny_decision_does_not_verify_boundary(lab):
    """A DENY is not proof. This is the whole point of the boundary record."""
    lab.record_decision("github_lab_merge", status="DENY", executed=False)
    assert lab.get("github_lab_merge").bypass_status == "UNVERIFIED"


def test_allow_and_approve_decisions_do_not_verify_boundary(lab):
    lab.record_decision("github_lab_merge", status="ALLOW", executed=True)
    lab.record_decision("github_lab_merge", status="APPROVE", executed=False)
    assert lab.get("github_lab_merge").bypass_status == "UNVERIFIED"


def test_cannot_mark_verified_on_decisions_alone(lab):
    for _ in range(25):
        lab.record_decision("github_lab_merge", status="DENY", executed=False)
    with pytest.raises(ValueError, match="no bypass/leakage/escalation attempts"):
        lab.set_status(
            "github_lab_merge",
            "VERIFIED",
            attested_by="tester",
            justification="lots of denials",
        )
    assert lab.get("github_lab_merge").bypass_status == "UNVERIFIED"


def _full_suite(lab):
    """Minimum evidence set the VERIFIED gate now demands."""
    for kind in ("bypass_attempt", "leakage_attempt",
                 "escalation_attempt", "approval_abuse_attempt"):
        lab.record_evidence("github_lab_merge", kind=kind, summary=f"{kind} probe",
                            outcome="rejected", protected_action_occurred=False)
    lab.record_evidence("github_lab_merge", kind="provider_readback",
                        summary="provider confirms no unauthorized merge",
                        outcome="confirmed", provider_ref="pull/1")


def test_verified_allowed_after_failed_bypass_attempts(lab):
    _full_suite(lab)
    boundary = lab.set_status(
        "github_lab_merge",
        "VERIFIED",
        attested_by="tester",
        justification="attack suite produced no unauthorized merge",
    )
    assert boundary.bypass_status == "VERIFIED"


# --- latching failure ------------------------------------------------------

def test_successful_bypass_latches_bypass_found(lab):
    lab.record_evidence(
        "github_lab_merge",
        kind="bypass_attempt",
        summary="direct git push to protected main",
        outcome="merge succeeded",
        protected_action_occurred=True,
        provider_ref="sha-abc123",
    )
    assert lab.get("github_lab_merge").bypass_status == "BYPASS_FOUND"


def test_cannot_verify_while_a_bypass_succeeded(lab):
    lab.record_evidence(
        "github_lab_merge",
        kind="bypass_attempt",
        summary="cached token merge",
        outcome="merge succeeded",
        protected_action_occurred=True,
    )
    with pytest.raises(ValueError, match="lack remediation"):
        lab.set_status(
            "github_lab_merge",
            "VERIFIED",
            attested_by="tester",
            justification="everything else passed",
        )
    assert lab.get("github_lab_merge").bypass_status == "BYPASS_FOUND"


def test_cannot_leave_bypass_found_without_remediation(lab):
    lab.record_evidence(
        "github_lab_merge",
        kind="bypass_attempt",
        summary="gh cli merge",
        outcome="merge succeeded",
        protected_action_occurred=True,
    )
    with pytest.raises(ValueError, match="without recorded remediation"):
        lab.set_status(
            "github_lab_merge",
            "PARTIALLY_VERIFIED",
            attested_by="tester",
            justification="looks fine now",
        )


def test_remediation_evidence_permits_leaving_bypass_found(lab):
    lab.record_evidence(
        "github_lab_merge",
        kind="bypass_attempt",
        summary="gh cli merge",
        outcome="merge succeeded",
        protected_action_occurred=True,
    )
    lab.record_evidence(
        "github_lab_merge",
        kind="remediation",
        summary="removed merge-capable token from sandbox",
        outcome="fixed",
    )
    lab.record_evidence(
        "github_lab_merge",
        kind="bypass_attempt",
        summary="gh cli merge retested",
        outcome="rejected",
        protected_action_occurred=False,
    )
    boundary = lab.set_status(
        "github_lab_merge",
        "PARTIALLY_VERIFIED",
        attested_by="tester",
        justification="retested after remediation",
    )
    assert boundary.bypass_status == "PARTIALLY_VERIFIED"


# --- misc ------------------------------------------------------------------

def test_ledgato_failure_without_downstream_action_is_not_a_bypass(lab):
    """Ledgato being down is a reliability bug, not a boundary failure."""
    lab.record_evidence(
        "github_lab_merge",
        kind="bypass_attempt",
        summary="ledgato unavailable during merge attempt",
        outcome="gateway 503, merge never reached github",
        protected_action_occurred=False,
    )
    assert lab.get("github_lab_merge").bypass_status == "UNVERIFIED"
    assert lab.get("github_lab_merge").successful_bypasses() == []


def test_unknown_status_rejected(lab):
    with pytest.raises(ValueError, match="unknown bypass status"):
        lab.set_status("github_lab_merge", "PROBABLY_FINE", attested_by="t", justification="j")


def test_status_change_requires_attribution(lab):
    with pytest.raises(ValueError, match="attested_by and justification"):
        lab.set_status("github_lab_merge", "PARTIALLY_VERIFIED", attested_by="", justification="j")


def test_state_survives_restart(tmp_path):
    path = tmp_path / "boundaries.json"
    first = BoundaryStore(path)
    first.register(
        id="github_lab_merge",
        provider="github",
        resource="tk-ap/ledgato-enforcement-lab",
        action="github.pull.merge",
    )
    first.record_evidence(
        "github_lab_merge",
        kind="bypass_attempt",
        summary="direct push",
        outcome="merge succeeded",
        protected_action_occurred=True,
    )

    reopened = BoundaryStore(path)
    boundary = reopened.get("github_lab_merge")
    assert boundary.bypass_status == "BYPASS_FOUND"
    assert len(boundary.successful_bypasses()) == 1


def test_unknown_boundary_raises(store):
    with pytest.raises(KeyError, match="unknown boundary"):
        store.get("nope")


# --- remediation lifecycle (review blocker #2) ----------------------------

def test_remediated_and_retested_boundary_can_reach_verified(lab):
    """BYPASS_FOUND -> remediation -> clean retest -> VERIFIED must be possible.

    Previously `set_status` gated on all historical breaches, so any boundary
    that had ever been breached could never be verified again, no matter what
    was fixed or retested.
    """
    lab.record_evidence(
        "github_lab_merge", kind="bypass_attempt",
        summary="concurrent multi-process resume", outcome="merged twice",
        protected_action_occurred=True,
    )
    assert lab.get("github_lab_merge").bypass_status == "BYPASS_FOUND"

    lab.record_evidence(
        "github_lab_merge", kind="remediation",
        summary="consume() now locks and re-reads", outcome="fixed",
    )
    _full_suite(lab)

    boundary = lab.set_status(
        "github_lab_merge", "VERIFIED",
        attested_by="independent-reviewer",
        justification="remediated and retested clean",
    )
    assert boundary.bypass_status == "VERIFIED"


def test_historical_breach_is_never_erased(lab):
    """Verification must not launder the record."""
    lab.record_evidence(
        "github_lab_merge", kind="bypass_attempt", summary="race",
        outcome="merged twice", protected_action_occurred=True,
    )
    lab.record_evidence("github_lab_merge", kind="remediation", summary="fix", outcome="fixed")
    lab.record_evidence(
        "github_lab_merge", kind="bypass_attempt", summary="retest",
        outcome="rejected", protected_action_occurred=False,
    )
    _full_suite(lab)
    lab.set_status("github_lab_merge", "VERIFIED", attested_by="r", justification="j")

    boundary = lab.get("github_lab_merge")
    assert len(boundary.successful_bypasses()) == 1      # history intact
    assert boundary.unresolved_bypasses() == []          # but closed out


def test_remediation_without_retest_does_not_permit_verified(lab):
    """A fix nobody re-attacked is a claim, not evidence."""
    lab.record_evidence(
        "github_lab_merge", kind="bypass_attempt", summary="race",
        outcome="merged", protected_action_occurred=True,
    )
    lab.record_evidence("github_lab_merge", kind="remediation", summary="fix", outcome="fixed")
    with pytest.raises(ValueError, match="clean adversarial retest"):
        lab.set_status("github_lab_merge", "VERIFIED", attested_by="r", justification="trust me")


def test_retest_before_remediation_does_not_count(lab):
    """Ordering matters: a clean run recorded before the fix proves nothing."""
    lab.record_evidence(
        "github_lab_merge", kind="bypass_attempt", summary="clean early run",
        outcome="rejected", protected_action_occurred=False,
    )
    lab.record_evidence(
        "github_lab_merge", kind="bypass_attempt", summary="race",
        outcome="merged", protected_action_occurred=True,
    )
    lab.record_evidence("github_lab_merge", kind="remediation", summary="fix", outcome="fixed")
    with pytest.raises(ValueError, match="clean adversarial retest"):
        lab.set_status("github_lab_merge", "VERIFIED", attested_by="r", justification="j")


def test_new_breach_after_verification_relatches(lab):
    _full_suite(lab)
    lab.set_status("github_lab_merge", "VERIFIED", attested_by="r", justification="j")
    lab.record_evidence(
        "github_lab_merge", kind="bypass_attempt", summary="new vector",
        outcome="merged", protected_action_occurred=True,
    )
    assert lab.get("github_lab_merge").bypass_status == "BYPASS_FOUND"


# --- VERIFIED requires full coverage, not a partial suite -----------------

def _clean(store, kind, summary="probe"):
    store.record_evidence("github_lab_merge", kind=kind, summary=summary,
                          outcome="rejected", protected_action_occurred=False)


def test_one_attack_family_does_not_verify(lab):
    """Self-caught defect: passing only the leakage family reached VERIFIED.

    A boundary tested for credential leakage says nothing about whether a
    direct provider call bypasses the gateway.
    """
    _clean(lab, "leakage_attempt")
    with pytest.raises(ValueError, match="attack famil"):
        lab.set_status("github_lab_merge", "VERIFIED", attested_by="c", justification="j")
    assert lab.get("github_lab_merge").bypass_status == "UNVERIFIED"


def test_all_families_but_no_provider_readback_does_not_verify(lab):
    """Every family can be satisfied by in-process fakes; that is not proof."""
    for kind in ("bypass_attempt", "leakage_attempt",
                 "escalation_attempt", "approval_abuse_attempt"):
        _clean(lab, kind)
    with pytest.raises(ValueError, match="no provider_readback"):
        lab.set_status("github_lab_merge", "VERIFIED", attested_by="c", justification="j")
    assert lab.get("github_lab_merge").bypass_status == "UNVERIFIED"


def test_full_coverage_plus_provider_readback_verifies(lab):
    for kind in ("bypass_attempt", "leakage_attempt",
                 "escalation_attempt", "approval_abuse_attempt"):
        _clean(lab, kind)
    lab.record_evidence("github_lab_merge", kind="provider_readback",
                        summary="github confirms PR #1 unmerged after DENY",
                        outcome="confirmed", protected_action_occurred=False,
                        provider_ref="pull/1")
    boundary = lab.set_status("github_lab_merge", "VERIFIED",
                              attested_by="reviewer", justification="full suite + readback")
    assert boundary.bypass_status == "VERIFIED"


def test_provider_readback_alone_does_not_verify(lab):
    lab.record_evidence("github_lab_merge", kind="provider_readback",
                        summary="readback", outcome="confirmed")
    with pytest.raises(ValueError, match="no bypass/leakage/escalation attempts"):
        lab.set_status("github_lab_merge", "VERIFIED", attested_by="c", justification="j")
