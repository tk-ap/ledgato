"""Thin agent-os integration hook.

agent-os remains the execution control plane. This hook asks Ledgato before a
consequential tool call and translates the result into continue / stop / pause.
"""
from __future__ import annotations

from typing import Any

from ..sdk import LedgatoClient


class AgentOSBoundaryHook:
    def __init__(self, client: LedgatoClient, *, adapter: str):
        self.client = client
        self.adapter = adapter

    def before_tool_call(
        self,
        *,
        agent: str,
        task_id: str,
        tool: str,
        params: dict[str, Any] | None = None,
        domain: str | None = None,
        impact: str = "readonly",
        intent: str | None = None,
        grant_id: str | None = None,
    ) -> dict[str, Any]:
        result = self.client.execute(
            agent=agent,
            adapter=self.adapter,
            task_id=task_id,
            grant_id=grant_id,
            requested_by="agent-os",
            action={
                "tool": tool,
                "params": params or {},
                "domain": domain,
                "impact": impact,
                "intent": intent,
            },
        )
        status = result.get("status")
        approval = result.get("approval") or {}
        return {
            "proceed": status == "ALLOW",
            "pause": status == "APPROVE",
            "stop": status == "DENY",
            "approval_id": approval.get("id"),
            "attestation_id": result.get("attestation_id"),
            "ledgato": result,
        }
