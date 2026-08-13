"""Core data models for Ledgato.

An agent's *scope* is declared as a :class:`Policy` (per agent), expressed as
"attack surface as code" (fence.yaml). Every runtime action is a
:class:`Action` that the engine checks against its agent's policy.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional

# Ordered severity levels. Higher = more dangerous.
IMPACTS: dict[str, int] = {"readonly": 1, "write": 2, "exec": 3, "destructive": 4}


@dataclass
class Action:
    """A single agent action (a tool call) to be verified."""

    tool: str
    params: dict[str, Any] = field(default_factory=dict)
    domain: Optional[str] = None  # e.g. "sandbox::*", "prod::billing", "db.read"
    impact: str = "readonly"  # readonly | write | exec | destructive
    intent: Optional[str] = None  # natural-language context, used for injection checks

    def severity(self) -> int:
        return IMPACTS.get(self.impact, 1)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Policy:
    """Declared scope for one agent (one `agent:` block in fence.yaml)."""

    agent: str
    allow_tools: set[str] = field(default_factory=set)
    deny_tools: set[str] = field(default_factory=set)
    impact_max: str = "readonly"
    data_domains: list[str] = field(default_factory=list)
    on_deny: list[str] = field(default_factory=lambda: ["alert"])

    def impact_max_severity(self) -> int:
        return IMPACTS.get(self.impact_max, 3)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent": self.agent,
            "allow_tools": sorted(self.allow_tools),
            "deny_tools": sorted(self.deny_tools),
            "impact_max": self.impact_max,
            "data_domains": list(self.data_domains),
            "on_deny": list(self.on_deny),
        }


def parse_policy(data: dict[str, Any]) -> Policy:
    """Parse a single `policy:` block from fence.yaml into a :class:`Policy`."""
    return Policy(
        agent=data.get("agent", "agent"),
        allow_tools=_as_set(data.get("allow_tool")),
        deny_tools=_as_set(data.get("deny_tool")),
        impact_max=data.get("impact_max", "readonly"),
        data_domains=_as_list(data.get("data_domains")),
        on_deny=_as_list(data.get("on_deny", ["alert"])),
    )


def load_policies(yaml_doc: dict[str, Any]) -> dict[str, Policy]:
    """Load all `policies:` blocks from a parsed fence.yaml into {agent: Policy}."""
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