"""Ledgato decision engine.

The engine answers ALLOW / DENY / APPROVE for one consequential action. It
checks both the declared policy and, when present or required, the concrete
delegated authority grant carried by the caller.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .models import Action, AuthorityGrant, Policy

ALLOW = "ALLOW"
DENY = "DENY"
APPROVE = "APPROVE"


@dataclass
class Decision:
    allow: bool
    reason: str
    reasons: list[str]
    policy: str
    on_deny: list[str]
    outcome: str = ALLOW
    grant_id: str | None = None

    @property
    def requires_approval(self) -> bool:
        return self.outcome == APPROVE

    def to_dict(self) -> dict[str, Any]:
        return {
            "allow": self.allow,
            "outcome": self.outcome,
            "requires_approval": self.requires_approval,
            "reason": self.reason,
            "reasons": self.reasons,
            "policy": self.policy,
            "on_deny": self.on_deny,
            "grant_id": self.grant_id,
        }


def _decision(
    outcome: str,
    reason: str,
    reasons: list[str],
    policy: Policy,
    grant: AuthorityGrant | None = None,
) -> Decision:
    return Decision(
        allow=outcome == ALLOW,
        outcome=outcome,
        reason=reason,
        reasons=reasons,
        policy=policy.agent,
        on_deny=list(policy.on_deny),
        grant_id=grant.id if grant else None,
    )


def evaluate_action(
    policy: Policy,
    action: Action,
    *,
    grant: AuthorityGrant | None = None,
    task_id: str | None = None,
    now: datetime | None = None,
    approval_satisfied: bool = False,
) -> Decision:
    """Evaluate one action against policy + concrete delegated authority.

    ``approval_satisfied`` is only set by the gateway when resuming a previously
    approved request. Direct callers cannot turn an out-of-policy DENY into ALLOW.
    """
    reasons: list[str] = []

    if action.tool in policy.deny_tools:
        reasons.append(f"tool '{action.tool}' is on deny list")
        return _decision(DENY, "DENY: tool explicitly denied", reasons, policy, grant)

    if policy.allow_tools and action.tool not in policy.allow_tools:
        reasons.append(f"tool '{action.tool}' not in allow_tools {sorted(policy.allow_tools)}")
        return _decision(DENY, "DENY: tool out of scope", reasons, policy, grant)

    if action.severity() > policy.impact_max_severity():
        reasons.append(f"impact '{action.impact}' exceeds impact_max '{policy.impact_max}'")
        return _decision(DENY, "DENY: impact exceeds declared max", reasons, policy, grant)

    if policy.data_domains and action.domain and not _domain_allowed(action.domain, policy.data_domains):
        reasons.append(f"domain '{action.domain}' not in data_domains {policy.data_domains}")
        return _decision(DENY, "DENY: data domain out of scope", reasons, policy, grant)

    if policy.require_grant and grant is None:
        reasons.append("policy requires a delegated authority grant")
        return _decision(DENY, "DENY: delegated authority required", reasons, policy)

    if grant is not None:
        grant_failure = _check_grant(grant, policy, action, task_id, now)
        if grant_failure:
            reasons.append(grant_failure)
            return _decision(DENY, f"DENY: {grant_failure}", reasons, policy, grant)
        reasons.append(f"grant '{grant.id}' active and in scope")

    approval_min = policy.approval_min_severity()
    approval_needed = (
        action.tool in policy.approval_tools
        or (approval_min is not None and action.severity() >= approval_min)
    )
    if approval_needed and not approval_satisfied:
        reasons.append("policy requires approval for this consequential crossing")
        return _decision(APPROVE, "APPROVE: human or higher-order approval required", reasons, policy, grant)

    reasons.append("in scope: tool allowed, impact ok, domain ok")
    return _decision(ALLOW, "ALLOW: action verified in scope", reasons, policy, grant)


def _check_grant(
    grant: AuthorityGrant,
    policy: Policy,
    action: Action,
    task_id: str | None,
    now: datetime | None,
) -> str | None:
    if grant.agent != policy.agent:
        return f"grant belongs to agent '{grant.agent}', not '{policy.agent}'"
    if not grant.active(now):
        return "authority grant is expired or revoked"
    if grant.task_id and grant.task_id != task_id:
        return f"grant is bound to task '{grant.task_id}'"
    if grant.tools and action.tool not in grant.tools:
        return f"tool '{action.tool}' is outside delegated grant"
    if action.severity() > grant.impact_max_severity():
        return f"impact '{action.impact}' exceeds delegated grant max '{grant.impact_max}'"
    if grant.data_domains and action.domain and not _domain_allowed(action.domain, grant.data_domains):
        return f"domain '{action.domain}' is outside delegated grant"
    return None


def _domain_allowed(domain: str, allowed: list[str]) -> bool:
    if domain in allowed:
        return True
    for pat in allowed:
        if pat.endswith("*") and domain.startswith(pat[:-1]):
            return True
    return False


def detect_drift(declared: set[str], observed: set[str], agent: str) -> dict[str, Any]:
    """Compare declared capability with capability observed by a live adapter."""
    undeclared = sorted(observed - declared)
    missing = sorted(declared - observed)
    return {
        "agent": agent,
        "drift": bool(undeclared or missing),
        "undeclared_gains": undeclared,
        "missing": missing,
    }
