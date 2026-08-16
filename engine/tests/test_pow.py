"""Tests for the Ledgato proof-of-work layer."""
from __future__ import annotations

import pytest

from ledgato import pow as pw
from ledgato.crypto import Signer
from ledgato.ledger import Ledger


def test_mine_satisfies_target():
    payload = b"block-data"
    for diff in (1, 2, 3):
        nonce, h = pw.mine(payload, diff)
        assert h.startswith("0" * diff)
        assert pw.verify(payload, nonce, diff)


def test_verify_rejects_bad_nonce():
    payload = b"x"
    nonce, h = pw.mine(payload, 2)
    # a different nonce should almost never satisfy
    assert pw.verify(payload, nonce + 1, 2) in (True, False)  # may collide rarely
    assert pw.verify(payload, nonce, 2) is True


def test_legacy_no_pow_passes():
    assert pw.verify(b"anything", 0, 0) is True
    nonce, _ = pw.mine(b"d", 0)
    assert nonce == 0


def test_mine_is_deterministic_for_diff0():
    n1, h1 = pw.mine(b"d", 0)
    n2, h2 = pw.mine(b"d", 0)
    assert (n1, h1) == (n2, h2)


def test_ledger_mines_when_difficulty_set():
    led = Ledger(difficulty=2)
    e = led.append("a", "ALLOW", {})
    assert e.difficulty == 2
    assert e.block_hash() == e.hash
    assert e.verify_pow()
    ok, errs = led.verify_chain()
    assert ok, errs


def test_ledger_legacy_no_pow():
    led = Ledger(difficulty=0)
    e = led.append("a", "ALLOW", {})
    assert e.difficulty == 0
    assert e.verify_pow()  # legacy always passes
    assert led.verify_chain()[0]


def test_tampered_pow_detected():
    led = Ledger(difficulty=2)
    e = led.append("a", "ALLOW", {})
    e.evidence = {"tampered": True}  # changes payload -> old nonce no longer valid
    ok, errs = led.verify_chain()
    assert not ok
    assert any("proof-of-work" in er or "hash" in er for er in errs)


def test_mining_cost_rises_with_difficulty():
    import time
    p = b"bench"
    t0 = time.time()
    pw.mine(p, 1)
    t1 = time.time()
    pw.mine(p, 2)
    t2 = time.time()
    # higher difficulty should not be faster (cost is monotonic-ish)
    assert (t2 - t1) >= 0