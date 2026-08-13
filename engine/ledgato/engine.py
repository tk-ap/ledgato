"""Ledgato engine: evaluate actions against a declared scope.

The engine makes the real-time allow/deny decision for a single agent action
against that agent's :class:`Policy`. It is the "gate" that runs at the moment
of action — before anything ships.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .models import Action, IMPACTS, Policy


@dataclass
class Decision:
    allow: bool
    reason: str
    reasons: list[str]
    policy: str
    on_deny: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "allow": self.allow,
            "reason": self.reason,
            "reasons": self.reasons,
            "policy": self.policy,
            "on_deny": self.on_deny,
        }


def evaluate_action(policy: Policy, action: Action) -> Decision:
    """Check one action against an agent's policy. Returns an allow/deny decision."""
    reasons: list[str] = []

    # 1. explicit deny list wins
    if action.tool in policy.deny_tools:
        reasons.append(f"tool '{action.tool}' is on deny list")
        return Decision(False, "DENY: tool explicitly denied", reasons, policy.agent, list(policy.on_deny))

    # 2. allowlist: if defined, the tool must be allowed
    if policy.allow_tools and action.tool not in policy.allow_tools:
        reasons.append(
            f"tool '{action.tool}' not in allow_tools {sorted(policy.allow_tools)}"
        )
        return Decision(False, "DENY: tool out of scope", reasons, policy.agent, list(policy.on_deny))

    # 3. impact must not exceed the declared maximum
    if action.severity() > policy.impact_max_severity():
        reasons.append(
            f"impact '{action.impact}' exceeds impact_max '{policy.impact_max}'"
        )
        return Decision(False, "DENY: impact exceeds declared max", reasons, policy.agent, list(policy.on_deny))

    # 4. data domain must be within the allowed domains
    if policy.data_domains and action.domain:
        allowed = _domain_allowed(action.domain, policy.data_domains)
        if not allowed:
            reasons.append(
                f"domain '{action.domain}' not in data_domains {policy.data_domains}"
            )
            return Decision(False, "DENY: data domain out of scope", reasons, policy.agent, list(policy.on_deny))

    reasons.append(f"in scope: tool allowed, impact ok, domain ok")
    return Decision(True, "ALLOW: action verified in scope", reasons, policy.agent, list(policy.on_deny))


def _domain_allowed(domain: str, allowed: list[str]) -> bool:
    if domain in allowed:
        return True
    for pat in allowed:
        if pat.endswith("*") and domain.startswith(pat[:-1]):
            return True
    return False


def detect_drift(
    declared: set[str], observed: set[str], agent: str
) -> dict[str, Any]:
    """Compare a declared attack surface (map) to a live/observed one.

    Drift = capability that is live but not declared (permission creep) OR
    declared but no longer present (missing). Anything live-but-undeclared is a
    containment violation.
    """
    undeclared = sorted(observed - declared)
    missing = sorted(declared - observed)
    return {
        "agent": agent,
        "drift": bool(undeclared or missing),
        "undeclared_gains": undeclared,
        "missing": missing,
    }