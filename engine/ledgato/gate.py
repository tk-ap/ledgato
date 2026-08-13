"""The release gate.

This is the product's core promise: *an unverified agent doesn't ship.*
``attest_release`` runs every agent's actions and probes through the engine,
writes each result as a signed, hash-chained attestation to the ledger, and
returns the release verdict. If any required check is out of scope, drifted, or
unverified, the release is GATED (blocked) with evidence — not approved on trust.
"""
from __future__ import annotations

from typing import Any

from .engine import detect_drift, evaluate_action
from .ledger import Ledger
from .models import Action, Policy
from .probes import run_probes, summarize


class GateResult:
    def __init__(
        self,
        release: str,
        agent: str,
        verdict: str,  # APPROVED | GATED
        attestations: list[dict[str, Any]],
        gap: list[str],
        drift: dict[str, Any] | None,
    ):
        self.release = release
        self.agent = agent
        self.verdict = verdict
        self.attestations = attestations
        self.gap = gap
        self.drift = drift

    def to_dict(self) -> dict[str, Any]:
        return {
            "release": self.release,
            "agent": self.agent,
            "verdict": self.verdict,
            "gap": self.gap,
            "drift": self.drift,
            "attestations": self.attestations,
        }


def attest_release(
    ledger: Ledger,
    policy: Policy,
    release: str,
    actions: list[Action],
    observed_scope: set[str] | None = None,
) -> GateResult:
    """Attest a single agent against the given release. Returns a verdict."""
    attestations: list[dict[str, Any]] = []
    gap: list[str] = []

    # 1. sign every declared action against scope
    for action in actions:
        decision = evaluate_action(policy, action)
        evidence = {
            "release": release,
            "action": action.to_dict(),
            "decision": decision.to_dict(),
        }
        entry = ledger.append(policy.agent, decision.reason.split(":")[0], evidence, action=action.tool)
        attestations.append(
            {"id": entry.id, "action": action.tool, "decision": decision.allow,
             "reason": decision.reason, "attestation": entry.hash[:12], "evidence": evidence}
        )
        if not decision.allow:
            gap.append(action.tool)

    # 2. adversarial probes — any gap means the boundary can't be trusted
    probe_summary = summarize(run_probes(policy))
    for pr in probe_summary["results"]:
        if not pr["passed"]:
            gap.append(f"probe:{pr['name']}")
    ledger.append(
        policy.agent,
        "SIGNED",
        {"release": release, "probes": probe_summary["passed"], "total": probe_summary["total"]},
        action="probe_battery",
    )

    # 3. drift check: the verified surface is the allow-list (permitted capability).
    #    Anything observed beyond it — a gained capability like db.write — is drift.
    drift = None
    if observed_scope is not None:
        declared = policy.allow_tools
        drift = detect_drift(declared, observed_scope, policy.agent)
        if drift["drift"]:
            gap.append("scope_drift")

    verdict = "APPROVED" if not gap else "GATED"
    ledger.append(
        policy.agent,
        verdict,
        {"release": release, "gap": gap},
        action="release_gate",
    )
    return GateResult(release, policy.agent, verdict, attestations, gap, drift)