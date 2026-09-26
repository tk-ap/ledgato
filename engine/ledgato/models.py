"""Core data models for Ledgato.

Policies describe the authority an agent is intended to have. AuthorityGrant
models a concrete delegated/JIT grant carried into an execution request.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

IMPACTS: dict[str, int] = {"readonly": 1, "write": 2, "exec": 3, "destructive": 4}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


@dataclass
class Action:
    """A single agent action (tool call) presented to the assurance boundary."""

    tool: str
    params: dict[str, Any] = field(default_factory=dict)
    domain: Optional[str] = None
    impact: str = "readonly"
    intent: Optional[str] = None

    def severity(self) -> int:
        return IMPACTS.get(self.impact, 1)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AuthorityGrant:
    """Delegated authority carried by an agent for a bounded purpose.

    Grants can be permanent, task-bound, or just-in-time. Revocation and expiry
    are checked at decision time rather than trusted from caller state.
    """

    id: str
    agent: str
    granted_by: str
    purpose: str
    tools: set[str] = field(default_factory=set)
    data_domains: list[str] = field(default_factory=list)
    impact_max: str = "readonly"
    task_id: Optional[str] = None
    credential_ref: Optional[str] = None
    parent_grant_id: Optional[str] = None
    issued_at: str = field(default_factory=lambda: utcnow().isoformat())
    expires_at: Optional[str] = None
    revoked_at: Optional[str] = None
    revoked_by: Optional[str] = None
    revocation_reason: Optional[str] = None

    def active(self, now: datetime | None = None) -> bool:
        now = now or utcnow()
        if self.revoked_at:
            return False
        expiry = parse_time(self.expires_at)
        return not expiry or now < expiry

    def impact_max_severity(self) -> int:
        return IMPACTS.get(self.impact_max, 1)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["tools"] = sorted(self.tools)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AuthorityGrant":
        copy = dict(data)
        copy["tools"] = _as_set(copy.get("tools"))
        copy["data_domains"] = _as_list(copy.get("data_domains"))
        return cls(**copy)


@dataclass
class Policy:
    """Declared scope for one agent (one ``agent:`` block in fence.yaml)."""

    agent: str
    allow_tools: set[str] = field(default_factory=set)
    deny_tools: set[str] = field(default_factory=set)
    impact_max: str = "readonly"
    data_domains: list[str] = field(default_factory=list)
    on_deny: list[str] = field(default_factory=lambda: ["alert"])
    approval_tools: set[str] = field(default_factory=set)
    approval_impact_min: Optional[str] = None
    require_grant: bool = False

    def impact_max_severity(self) -> int:
        return IMPACTS.get(self.impact_max, 3)

    def approval_min_severity(self) -> int | None:
        if not self.approval_impact_min:
            return None
        return IMPACTS.get(self.approval_impact_min)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent": self.agent,
            "allow_tools": sorted(self.allow_tools),
            "deny_tools": sorted(self.deny_tools),
            "impact_max": self.impact_max,
            "data_domains": list(self.data_domains),
            "on_deny": list(self.on_deny),
            "approval_tools": sorted(self.approval_tools),
            "approval_impact_min": self.approval_impact_min,
            "require_grant": self.require_grant,
        }


_POLICY_KEYS = {
    "agent",
    "allow_tool",
    "allow_tools",
    "deny_tool",
    "deny_tools",
    "approve_tool",
    "approve_tools",
    "impact_max",
    "data_domains",
    "on_deny",
    "approval_impact_min",
    "require_grant",
}


def _validate_policy_keys(data: dict[str, Any]) -> None:
    unknown = sorted(set(data) - _POLICY_KEYS)
    if unknown:
        raise ValueError(
            "unknown policy key(s): " + ", ".join(unknown)
            + "; policy parsing fails closed rather than ignoring configuration"
        )


def _aliased_tool_set(
    data: dict[str, Any], singular_key: str, plural_key: str, *, mode: str
) -> set[str]:
    """Read singular/plural aliases without allowing ambiguity to widen authority.

    For allowlists, both declarations means intersection (narrower authority).
    For deny/approval gates, both declarations means union (more actions gated).
    Explicit empty declarations still participate, so ``allow_tool: []`` plus a
    non-empty plural alias resolves to deny-all instead of silently widening.
    """
    singular_present = singular_key in data
    plural_present = plural_key in data
    singular = _as_set(data.get(singular_key))
    plural = _as_set(data.get(plural_key))

    if singular_present and plural_present:
        if mode == "intersection":
            return singular & plural
        if mode == "union":
            return singular | plural
        raise ValueError(f"unsupported alias merge mode: {mode}")
    if singular_present:
        return singular
    if plural_present:
        return plural
    return set()


def parse_policy(data: dict[str, Any]) -> Policy:
    _validate_policy_keys(data)
    return Policy(
        agent=data.get("agent", "agent"),
        allow_tools=_aliased_tool_set(
            data, "allow_tool", "allow_tools", mode="intersection"
        ),
        deny_tools=_aliased_tool_set(
            data, "deny_tool", "deny_tools", mode="union"
        ),
        impact_max=data.get("impact_max", "readonly"),
        data_domains=_as_list(data.get("data_domains")),
        on_deny=_as_list(data.get("on_deny", ["alert"])),
        approval_tools=_aliased_tool_set(
            data, "approve_tool", "approve_tools", mode="union"
        ),
        approval_impact_min=data.get("approval_impact_min"),
        require_grant=bool(data.get("require_grant", False)),
    )


def load_policies(yaml_doc: dict[str, Any]) -> dict[str, Policy]:
    policies: dict[str, Policy] = {}
    for block in yaml_doc.get("policies", []) or []:
        pol = parse_policy(block)
        policies[pol.agent] = pol
    return policies


def _as_set(value: Any) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, str):
        return {value}
    return {str(v) for v in value}


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [str(v) for v in value]
