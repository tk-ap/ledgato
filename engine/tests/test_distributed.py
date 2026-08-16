"""Tests for the distributed ledger + longest-valid-chain consensus."""
from __future__ import annotations

from ledgato.distributed import Node
from ledgato.ledger import Ledger


def _node(difficulty=2, entries=3):
    led = Ledger(difficulty=difficulty)
    for i in range(entries):
        led.append("agent", "ALLOW", {"i": i}, action=f"act{i}")
    return Node(led)


def test_reconcile_keeps_longer_local():
    local = _node(entries=5)
    remote = _node(entries=3)
    res = local.reconcile(remote.chain())
    assert res.adopted is False
    assert len(local.ledger.entries) == 5


def test_reconcile_adopts_longer_remote():
    local = _node(entries=2)
    remote = _node(entries=6)
    res = local.reconcile(remote.chain())
    assert res.adopted is True
    assert res.by == "remote"
    assert len(local.ledger.entries) == 6


def test_reconcile_rejects_invalid_remote():
    local = _node(entries=3)
    remote = _node(entries=6)
    # tamper: break a mid chain entry so the whole remote chain is invalid
    remote.ledger.entries[2].evidence = {"tampered": True}
    res = local.reconcile(remote.chain())
    assert res.adopted is False
    assert res.remote_ok is False
    assert len(local.ledger.entries) == 3


def test_equal_length_keeps_local():
    local = _node(entries=4)
    remote = _node(entries=4)
    res = local.reconcile(remote.chain())
    # remote valid but not longer -> local wins
    assert res.adopted is False


def test_node_roundtrip():
    n = _node(entries=3)
    data = n.dump()
    n2 = Node.load(data)
    assert len(n2.ledger.entries) == 3
    assert n2.ledger.verify_chain()[0]


def test_node_status():
    n = _node(entries=2)
    s = n.status()
    assert s["entries"] == 2
    assert s["verified"] is True
    assert s["head"] == n.ledger.entries[-1].hash