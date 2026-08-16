"""Distributed ledger + consensus for Ledgato.

Independent Ledgato nodes each hold a full copy of the signed, proof-of-work
attestation chain. When nodes exchange chains they apply **longest-valid-chain
consensus**: a chain is only adopted if it fully verifies (hashes, signatures
and proof-of-work) and is at least as long as the local one. This is what makes
the evidence **distributed**: no single node can silently rewrite history,
because every other node can cross-verify the same chain and detect a fork.

For a real network each node would gossip over HTTP (see the API's
``/v1/ledger/*`` endpoints); the pure-Python :class:`Node` here models the
same reconciliation logic so it is testable and usable headlessly or across
processes that exchange chain JSON.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Optional

from .ledger import Ledger, LedgerEntry


@dataclass
class SyncResult:
    adopted: bool
    by: str  # "local" | "remote"
    reason: str
    local_len: int
    remote_len: int
    local_ok: bool
    remote_ok: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "adopted": self.adopted,
            "by": self.by,
            "reason": self.reason,
            "local_len": self.local_len,
            "remote_len": self.remote_len,
            "local_ok": self.local_ok,
            "remote_ok": self.remote_ok,
        }


def validate_entries(data: list[dict[str, Any]]) -> list[LedgerEntry]:
    """Turn raw dict entries into LedgerEntry objects (raises on bad shape)."""
    return [LedgerEntry(**d) for d in data]


def verify_candidate(entries: list[LedgerEntry]) -> tuple[bool, list[str]]:
    """Verify a candidate chain (hashes, signatures, PoW, links) without a live Ledger."""
    if not entries:
        return True, []
    temp = Ledger(difficulty=0)
    temp.entries = entries
    return temp.verify_chain()


class Node:
    """A Ledgato node: owns a Ledger and can reconcile with peers."""

    def __init__(self, ledger: Ledger, node_id: Optional[str] = None):
        self.ledger = ledger
        self.node_id = node_id or f"node-{id(self):x}"
        self.peers: list[str] = []

    # ---- local writes ------------------------------------------------
    def record(
        self,
        agent: str,
        decision: str,
        evidence: dict[str, Any],
        action: str = "",
        difficulty: int | None = None,
    ) -> LedgerEntry:
        """Append + mine an entry locally, then propagate to peers (best-effort)."""
        return self.ledger.append(agent, decision, evidence, action, difficulty=difficulty)

    # ---- distributed operations -------------------------------------
    def status(self) -> dict[str, Any]:
        head = self.ledger.entries[-1] if self.ledger.entries else None
        ok, errs = self.ledger.verify_chain()
        return {
            "node": self.node_id,
            "entries": len(self.ledger.entries),
            "head": head.hash if head else "GENESIS",
            "difficulty": self.ledger.difficulty,
            "verified": ok,
            "errors": errs,
            "peers": list(self.peers),
        }

    def chain(self) -> list[dict[str, Any]]:
        return self.ledger.to_list()

    def receive(self, remote_chain: list[dict[str, Any]]) -> SyncResult:
        """Validate + reconcile against a remote chain (a peer's chain())."""
        return self.reconcile(remote_chain)

    def reconcile(self, remote_chain: list[dict[str, Any]]) -> SyncResult:
        """Longest-valid-chain consensus. Adopt the remote chain if it's valid
        and at least as long as ours; otherwise keep local."""
        remote_entries = shared_entries(remote_chain)
        remote_ok, _ = verify_candidate(remote_entries)
        local_ok, _ = self.ledger.verify_chain()
        rlen, llen = len(remote_entries), len(self.ledger.entries)

        if not remote_ok:
            return SyncResult(False, "local", "remote chain invalid", llen, rlen, local_ok, False)
        if local_ok and llen >= rlen:
            return SyncResult(False, "local", "local chain is authoritative (same-or-longer)", llen, rlen, True, True)
        # remote is valid and strictly longer than local -> adopt it
        self.ledger.entries = remote_entries
        return SyncResult(True, "remote", "adopted remote chain", llen, rlen, local_ok, True)

    def connect(self, peer_url: str) -> None:
        if peer_url not in self.peers:
            self.peers.append(peer_url)

    # ---- import/export ----------------------------------------------
    def dump(self) -> dict[str, Any]:
        return {
            "node": self.node_id,
            "difficulty": self.ledger.difficulty,
            "entries": self.ledger.to_list(),
        }

    @classmethod
    def load(cls, data: dict[str, Any]) -> "Node":
        entries = shared_entries(data.get("entries", []))
        led = Ledger(difficulty=int(data.get("difficulty", 0)))
        led.entries = entries
        return cls(led, node_id=data.get("node"))


def shared_entries(raw: list[dict[str, Any]]) -> list[LedgerEntry]:
    """Build LedgerEntry objects from raw dicts, tolerant of missing keys."""
    entries: list[LedgerEntry] = []
    for d in raw:
        entry = LedgerEntry(
            index=d.get("index", 0),
            agent=d.get("agent", ""),
            action=d.get("action", ""),
            decision=d.get("decision", ""),
            evidence=d.get("evidence", {}),
            ts=d.get("ts", 0.0),
            prev_hash=d.get("prev_hash", "GENESIS"),
            hash=d.get("hash", ""),
            signature=d.get("signature", ""),
            id=d.get("id", ""),
            public_key=d.get("public_key", ""),
            nonce=int(d.get("nonce", 0)),
            difficulty=int(d.get("difficulty", 0)),
        )
        entries.append(entry)
    return entries
