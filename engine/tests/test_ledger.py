import pytest

from ledgato.crypto import Signer
from ledgato.ledger import Ledger


def test_chain_verifies():
    ledger = Ledger()
    ledger.append("ops-agent", "ALLOW", {"tool": "read.docs"})
    ledger.append("ops-agent", "SIGNED", {"probes": 6})
    ledger.append("ops-agent", "GATED", {"release": "v1.0"})
    ok, errs = ledger.verify_chain()
    assert ok, errs
    assert len(ledger.entries) == 3


def test_tamper_detected():
    ledger = Ledger()
    ledger.append("ops-agent", "ALLOW", {"tool": "read.docs"})
    ledger.append("ops-agent", "GATED", {"release": "v1.0"})
    # tamper with the second entry's evidence
    ledger.entries[1].evidence["release"] = "v9.9"
    ok, errs = ledger.verify_chain()
    assert ok is False
    assert any("hash mismatch" in e for e in errs)


def test_signature_invalid_detected():
    ledger = Ledger()
    ledger.append("ops-agent", "ALLOW", {"tool": "read.docs"})
    ledger.entries[0].signature = "AAAA"  # corrupt signature
    ok, errs = ledger.verify_chain()
    assert ok is False
    assert any("signature" in e for e in errs)


def test_prev_hash_chain():
    ledger = Ledger()
    a = ledger.append("ops-agent", "ALLOW", {})
    b = ledger.append("ops-agent", "SIGNED", {})
    assert b.prev_hash == a.hash
    assert ledger.entries[0].prev_hash == "GENESIS"


def test_roundtrip_persist(tmp_path):
    path = tmp_path / "ledger.jsonl"
    ledger = Ledger(path=path)
    ledger.append("ops-agent", "ALLOW", {"tool": "x"})
    loaded = Ledger.load(path)
    assert len(loaded.entries) == 1
    ok, errs = loaded.verify_chain()
    assert ok, errs


def test_signer_sign_and_verify():
    s = Signer()
    msg = b"ledgato attestation"
    sig = s.sign(msg)
    assert Signer.verify(s.public_key_b64(), msg, sig) is True
    assert Signer.verify(s.public_key_b64(), b"other", sig) is False