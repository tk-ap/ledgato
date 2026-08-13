"""Append-only, hash-chained, signed attestation ledger.

Every attestation (one verification decision) is recorded as an entry whose
`hash` is sha256(prev_hash + index + canonical payload). The entry is signed
by the Ledgato identity. Verifying the chain recomputes every hash and checks
each signature, so any alteration or reordering is immediately detectable.
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

from .crypto import Signer, sha256


@dataclass
class LedgerEntry:
    index: int
    agent: str
    action: str
    decision: str  # ALLOW | DENY | SIGNED | GATED
    evidence: dict[str, Any]
    ts: float
    prev_hash: str
    hash: str
    signature: str = ""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    public_key: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def payload(self) -> bytes:
        """Canonical bytes hashed/signed: everything except hash & signature."""
        d = self.to_dict()
        d.pop("hash", None)
        d.pop("signature", None)
        return json.dumps(d, sort_keys=True, separators=(",", ":")).encode()


class Ledger:
    def __init__(self, signer: Optional[Signer] = None, path: Optional[str | Path] = None):
        self.signer = signer or Signer()
        self.path = Path(path) if path else None
        self.entries: list[LedgerEntry] = []

    # ---- appending -----------------------------------------------------
    def append(
        self,
        agent: str,
        decision: str,
        evidence: dict[str, Any],
        action: str = "",
    ) -> LedgerEntry:
        index = len(self.entries)
        prev_hash = self.entries[-1].hash if self.entries else "GENESIS"
        now = time.time()
        entry = LedgerEntry(
            index=index,
            agent=agent,
            action=action,
            decision=decision,
            evidence=evidence,
            ts=now,
            prev_hash=prev_hash,
            hash="",  # filled below
            public_key=self.signer.public_key_b64(),
        )
        entry.hash = sha256(entry.payload())
        entry.signature = self.signer.sign(entry.payload())
        self.entries.append(entry)
        if self.path:
            self._append_line(entry)
        return entry

    def _append_line(self, entry: LedgerEntry) -> None:
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry.to_dict()) + "\n")

    def verify_chain(self) -> tuple[bool, list[str]]:
        errors: list[str] = []
        prev = "GENESIS"
        for entry in self.entries:
            if entry.prev_hash != prev:
                errors.append(f"entry {entry.index}: prev_hash mismatch")
            if sha256(entry.payload()) != entry.hash:
                errors.append(f"entry {entry.index}: hash mismatch (tampered)")
            if entry.public_key and not Signer.verify(
                entry.public_key, entry.payload(), entry.signature
            ):
                errors.append(f"entry {entry.index}: signature invalid")
            prev = entry.hash
        return (not errors, errors)

    def to_list(self) -> list[dict[str, Any]]:
        return [e.to_dict() for e in self.entries]

    @classmethod
    def load(cls, path: str | Path, signer: Optional[Signer] = None) -> "Ledger":
        led = cls(signer=signer, path=path)
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                led.entries.append(LedgerEntry(**data))
        return led