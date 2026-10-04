"""Owner session grants: one approval that covers a bounded working session.

TK decided on 2026-10-04 (agent-os docs/decisions/OWNER_INITIATED_AUTHORITY.md)
that one Telegram tap at the start of a working session should cover the
merges and runtime installs of that session, instead of one tap per action.

The session is itself a protected action, ``ledgato.session.grant``. Policy
holds it for owner approval like any other consequential crossing; when the
owner selects Allow once, this adapter issues an AuthorityGrant marked
``satisfies_approval``. Later requests that carry that grant id are treated as
already owner-approved, but only for the tools, domains and impact the grant
names and only until it expires.

Hard limits, enforced here regardless of what the request asks for:

- only reachable through an owner approval (never as a direct ALLOW);
- tools must be listed explicitly and come from ``grantable_tools``;
  a grant can never include ``ledgato.session.grant`` itself;
- data domains must be listed explicitly;
- impact at most ``write``; lifetime at most ``max_ttl_seconds`` (4 hours).
"""
from __future__ import annotations

from typing import Any

from .base import ExecutionReceipt
from ..models import Action

SESSION_GRANT_TOOL = "ledgato.session.grant"
DEFAULT_GRANTABLE_TOOLS = frozenset({"host.agentos.runtime.activate", "github.pull.merge"})
MAX_TTL_SECONDS = 4 * 3600
_IMPACT_ORDER = {"readonly": 0, "write": 1}


class SessionGrantError(ValueError):
    """The session request asked for more than a session grant may carry."""


class SessionGrantAdapter:
    name = "session"
    is_live_provider = False
    boundary_resource = None

    def __init__(self, authority, *, grantable_tools=DEFAULT_GRANTABLE_TOOLS,
                 max_ttl_seconds: int = MAX_TTL_SECONDS):
        self.authority = authority
        self.grantable_tools = frozenset(grantable_tools) - {SESSION_GRANT_TOOL}
        self.max_ttl_seconds = int(max_ttl_seconds)

    def discover(self, agent: str) -> set[str]:
        return {SESSION_GRANT_TOOL}

    def execute(self, action: Action) -> ExecutionReceipt:
        # A session grant must name the owner who approved it. The plain
        # execute path carries no approval, so it never issues anything.
        raise SessionGrantError("a session grant can only be issued from an owner approval")

    def execute_with_context(self, action: Action, *, agent: str,
                             approved_by: str | None, approval_id: str | None) -> ExecutionReceipt:
        if action.tool != SESSION_GRANT_TOOL:
            raise SessionGrantError(f"unsupported session action '{action.tool}'")
        if not approved_by or not approval_id:
            raise SessionGrantError("a session grant can only be issued from an owner approval")
        params = action.params or {}
        tools = params.get("tools")
        if not isinstance(tools, list) or not tools:
            raise SessionGrantError("a session grant must list its tools explicitly")
        tools = {str(tool) for tool in tools}
        outside = sorted(tools - self.grantable_tools)
        if outside:
            raise SessionGrantError(f"tools not grantable to a session: {', '.join(outside)}")
        domains = params.get("data_domains")
        if not isinstance(domains, list) or not domains or not all(isinstance(d, str) and d for d in domains):
            raise SessionGrantError("a session grant must list its data domains explicitly")
        impact = str(params.get("impact_max") or "write")
        if impact not in _IMPACT_ORDER:
            raise SessionGrantError("a session grant may carry at most write impact")
        try:
            ttl = int(params.get("ttl_seconds") or self.max_ttl_seconds)
        except (TypeError, ValueError):
            raise SessionGrantError("ttl_seconds must be a whole number of seconds") from None
        if not 60 <= ttl <= self.max_ttl_seconds:
            raise SessionGrantError(f"a session grant lasts between 60 s and {self.max_ttl_seconds} s")
        purpose = str(params.get("purpose") or "owner session").strip()[:200]

        grant = self.authority.issue(
            agent=agent,
            granted_by=f"owner-session:{approved_by}",
            purpose=f"session:{approval_id}: {purpose}",
            tools=tools,
            data_domains=list(domains),
            impact_max=impact,
            ttl_seconds=ttl,
            satisfies_approval=True,
        )
        return ExecutionReceipt(
            adapter=self.name,
            action=action.tool,
            executed=True,
            status="granted",
            external_id=grant.id,
            result={"grant_id": grant.id, "expires_at": grant.expires_at,
                    "tools": sorted(grant.tools), "data_domains": grant.data_domains},
        )

    def verify(self, action: Action, receipt: ExecutionReceipt) -> dict[str, Any]:
        grant = self.authority.get(receipt.external_id) if receipt.external_id else None
        return {
            "verified": bool(grant and grant.active() and grant.satisfies_approval),
            "method": "authority_store_readback",
            "grant_id": receipt.external_id,
        }

    def verify_denied(self, action: Action) -> dict[str, Any]:
        return {"verified": True, "method": "gateway_non_execution_receipt", "grant_issued": False}
