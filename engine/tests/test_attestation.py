"""Tests for attestation verification & ops (export / offline verify)."""
from __future__ import annotations

import json

from ledgato import attestation as at
from ledgato.crypto import Signer
from ledgato.gate import attest_release
from ledgato.ledger import Ledger
from ledgato.models import Policy


def _signed_release(difficulty=2, drift=False):
    led = Ledger(difficulty=difficulty)
    pol = Policy(
        agent="ops-agent",
        allow_tools={"read.docs", "search"},
        deny_tools={"db.write"},
        impact_max="readonly",
        data_domains=["sandbox::*"],
    )
    from ledgato.models import Action

    actions = [Action(tool=t, impact="readonly", domain="sandbox::x") for t in sorted(pol.allow_tools)]
    observed = set(pol.allow_tools) | ({"db.write"} if drift else set())
    result = attest_release(led, pol, "v2.4", actions, observed_scope=observed or None)
    return led, result


def test_verify_release_approved():
    led, result = _signed_release()
    assert result.verdict == "APPROVED"
    v = at.verify_release(led, "ops-agent", "v2.4")
    assert v["verified"] is True
    assert v["verdict"] == "APPROVED"
    assert v["signatures_valid"] is True
    assert v["proof_of_work_valid"] is True
    assert v["chain_integrity"] is True


def test_verify_release_gated():
    led, result = _signed_release(drift=True)
    assert result.verdict == "GATED"
    v = at.verify_release(led, "ops-agent", "v2.4")
    assert v["verdict"] == "GATED"
    assert v["verified"] is False  # evidence intact but release was not approved


def test_export_and_offline_verify_roundtrip():
    led, _ = _signed_release()
    bundle = at.export_report(led, "ops-agent", "v2.4", publisher="publisher-key")
    assert bundle["release"] == "v2.4"
    assert bundle["entries"]
    # serialize like a real file transfer
    shipped = json.loads(json.dumps(bundle))
    v = at.verify_report(shipped)
    assert v["verified"] is True
    assert v["verdict"] == "APPROVED"


def test_offline_verify_detects_tamper():
    led, _ = _signed_release()
    bundle = at.export_report(led, "ops-agent", "v2.4")
    # mutate one entry's evidence then re-serialize
    bundle["entries"][0]["evidence"]["action"]["impact"] = "destructive"
    v = at.verify_report(json.loads(json.dumps(bundle)))
    assert v["verified"] is False
    assert v["errors"]


def test_offline_verify_detects_signature_forge():
    led, _ = _signed_release()
    bundle = at.export_report(led, "ops-agent", "v2.4")
    bundle["entries"][1]["signature"] = "AAAA"  # corrupt signature
    v = at.verify_report(json.loads(json.dumps(bundle)))
    assert v["verified"] is False


def test_export_missing_release_is_empty_but_verifies():
    led = Ledger(difficulty=0)
    led.append("a", "ALLOW", {"release": "other"})
    bundle = at.export_report(led, "a", "v9")
    v = at.verify_report(bundle)
    # empty bundle verifies trivially
    assert v["verified"] is True
    assert v["entries"] == 0