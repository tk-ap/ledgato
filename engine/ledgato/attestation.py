"""Attestation verification & operations.

This is the "proof, not trust" half of Ledgato: given a release, verify that
every supporting attestation is genuinely in the signed, proof-of-work chain —
and produce a **self-contained verifiable report** that an auditor, compliance
or an external verifier can check offline without trusting our server.

A report bundle contains everything needed to verify: the entries, each
entry's public key, recomputed hashes and signatures, and the proof-of-work.
:func:`verify_report` recomputes all of it and returns a verdict.
"""
from __future__ import annotations

import json
import time
import uuid
from typing import Any

from . import pow as pow_mod
from .crypto import Signer, sha256
from .ledger import Ledger, LedgerEntry
from .distributed import shared_entries


def _release_entries(ledger: Ledger, agent: str, release: str) -> list[LedgerEntry]:
    return [
        e
        for e in ledger.entries
        if e.agent == agent and e.evidence.get("release") == release
    ]


def verify_release(
    ledger: Ledger,
    agent: str,
    release: str,
) -> dict[str, Any]:
    """Verify a release's attestations within the live ledger."""
    chain_ok, chain_errors = ledger.verify_chain()
    rel = _release_entries(ledger, agent, release)

    gate = next((e for e in rel if e.action == "release_gate"), None)
    verdict = gate.decision if gate else None

    attestations = [
        e for e in rel if e.action not in ("release_gate", "probe_battery")
    ]
    probes = [
        e for e in rel if e.action == "probe_battery"
    ]

    signed = all(e.public_key and Signer.verify(e.public_key, e.payload(), e.signature) for e in rel)
    pow_ok = all(e.verify_pow() for e in rel)

    return {
        "release": release,
        "agent": agent,
        "verdict": verdict,
        "attestations": len(attestations),
        "probes": len(probes),
        "chain_integrity": chain_ok,
        "chain_errors": chain_errors,
        "signatures_valid": signed,
        "proof_of_work_valid": pow_ok,
        "verified": bool(chain_ok and signed and pow_ok and verdict == "APPROVED"),
    }


def export_report(
    ledger: Ledger,
    agent: str,
    release: str,
    publisher: str = "",
) -> dict[str, Any]:
    """Export a self-contained, offline-verifiable attestation report."""
    rel = _release_entries(ledger, agent, release)
    return {
        "report": "ledgato-attestation-report",
        "version": 1,
        "generated_at": time.time(),
        "report_id": uuid.uuid4().hex[:12],
        "agent": agent,
        "release": release,
        "publisher": publisher or ledger.signer.public_key_b64(),
        "entries": [e.to_dict() for e in rel],
    }


def verify_report(bundle: dict[str, Any]) -> dict[str, Any]:
    """Verify a :func:`export_report` bundle fully offline."""
    errors: list[str] = []
    entries = shared_entries(bundle.get("entries", []))
    prev = "GENESIS"
    for e in entries:
        if e.prev_hash != prev:
            errors.append(f"entry {e.index}: prev_hash mismatch")
        # chain hash / PoW block hash
        if e.difficulty and e.block_hash() != e.hash:
            errors.append(f"entry {e.index}: proof-of-work block hash mismatch")
        elif not e.difficulty and sha256(e.payload()) != e.hash:
            errors.append(f"entry {e.index}: hash mismatch (tampered)")
        if not e.verify_pow():
            errors.append(f"entry {e.index}: proof-of-work invalid")
        if e.public_key and not Signer.verify(e.public_key, e.payload(), e.signature):
            errors.append(f"entry {e.index}: signature invalid")
        prev = e.hash

    gate = next((e for e in entries if e.action == "release_gate"), None)
    verdict = gate.decision if gate else None

    return {
        "report_id": bundle.get("report_id"),
        "agent": bundle.get("agent"),
        "release": bundle.get("release"),
        "verified": not errors,
        "verdict": verdict,
        "entries": len(entries),
        "errors": errors,
    }


def verify_chain_offline(data: list[dict[str, Any]]) -> dict[str, Any]:
    """Verify an exported chain of dict entries (no ledger object required)."""
    entries = shared_entries(data)
    ok, errs = _verify_chain_of(entries)
    return {"verified": ok, "errors": errs, "entries": len(entries)}


def _verify_chain_of(entries: list[LedgerEntry]) -> tuple[bool, list[str]]:
    temp = Ledger(difficulty=0)
    temp.entries = entries
    return temp.verify_chain()