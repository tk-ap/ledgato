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
from . import pow as pow_mod


@dataclass
class LedgerEntry:
    index: int
    agent: str
    action: str
    decision: str  # ALLOW | DENY | SIGNED | GATED | APPROVED
    evidence: dict[str, Any]
    ts: float
    prev_hash: str
    hash: str
    signature: str = ""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    public_key: str = ""
    nonce: int = 0       # proof-of-work nonce (0 = legacy / not mined)
    difficulty: int = 0  # proof-of-work difficulty (0 = no PoW)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def payload(self) -> bytes:
        """Canonical bytes hashed/signed: everything except hash & signature.
        Includes the mined nonce & difficulty, so the signature commits to them."""
        d = self.to_dict()
        d.pop("hash", None)
        d.pop("signature", None)
        return json.dumps(d, sort_keys=True, separators=(",", ":")).encode()

    def pow_input(self) -> bytes:
        """Proof-of-work pre-image: canonical bytes minus hash, signature and
        nonce. The nonce is excluded because it is discovered *while* mining,
        so it cannot be part of its own pre-image. Difficulty stays (constant)."""
        d = self.to_dict()
        d.pop("hash", None)
        d.pop("signature", None)
        d.pop("nonce", None)
        return json.dumps(d, sort_keys=True, separators=(",", ":")).encode()

    def block_hash(self) -> str:
        """The proof-of-work block hash: sha256(pow_input + nonce)."""
        return pow_mod.hash_block(self.pow_input(), self.nonce)

    def verify_pow(self) -> bool:
        """True if this entry's proof-of-work is valid (or legacy, no PoW)."""
        return pow_mod.verify(self.pow_input(), self.nonce, self.difficulty)


class Ledger:
    def __init__(
        self,
        signer: Optional[Signer] = None,
        path: Optional[str | Path] = None,
        difficulty: int = 0,
    ):
        self.signer = signer or Signer()
        self.path = Path(path) if path else None
        self.difficulty = int(difficulty)
        self.entries: list[LedgerEntry] = []

    # ---- appending -----------------------------------------------------
    def append(
        self,
        agent: str,
        decision: str,
        evidence: dict[str, Any],
        action: str = "",
        difficulty: int | None = None,
    ) -> LedgerEntry:
        index = len(self.entries)
        prev_hash = self.entries[-1].hash if self.entries else "GENESIS"
        now = time.time()
        diff = self.difficulty if difficulty is None else int(difficulty)
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
            difficulty=diff,
        )
        entry.hash = sha256(entry.payload())
        # mine proof-of-work (skipped when difficulty <= 0)
        if diff > 0:
            entry.nonce, _ = pow_mod.mine(entry.pow_input(), diff)
            entry.hash = entry.block_hash()
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
            if entry.difficulty:
                # mined entries: stored hash must equal the proof-of-work block hash
                if entry.block_hash() != entry.hash:
                    errors.append(f"entry {entry.index}: proof-of-work block hash mismatch (tampered)")
                if not entry.verify_pow():
                    errors.append(f"entry {entry.index}: proof-of-work invalid")
            else:
                # legacy entries: stored hash is the plain payload hash
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