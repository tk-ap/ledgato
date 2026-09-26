"""Channel-neutral owner decision prompts for paused consequential actions."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any

from .approvals import Approval

VERSION = "ledgato.decision-prompt/v1"
SENSITIVE_KEY_PARTS = (
    "authorization", "bearer", "cookie", "credential", "key", "password",
    "secret", "session", "token",
)

def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()

def _safe_facts(params: dict[str, Any], limit: int = 6) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    for raw_key in sorted(params):
        if len(facts) >= limit:
            break
        key = str(raw_key)
        value = params[raw_key]
        if any(part in key.lower() for part in SENSITIVE_KEY_PARTS):
            facts.append({"key": key, "value": "[redacted]", "redacted": True})
            continue
        if isinstance(value, bool):
            shown = "true" if value else "false"
        elif value is None:
            shown = "null"
        elif isinstance(value, (int, float)):
            shown = str(value)
        elif isinstance(value, str):
            shown = value if len(value) <= 120 else value[:117] + "..."
        else:
            shown = "[structured value omitted]"
        facts.append({"key": key, "value": shown, "redacted": False})
    return facts

def _consequence(impact: str) -> str:
    return {
        "readonly": "This action reads protected state but does not change it.",
        "write": "This action can change external state.",
        "exec": "This action can execute work in a protected system.",
        "destructive": "This action can make a destructive or difficult-to-reverse change.",
    }.get(str(impact or "").lower(), "This action can affect a protected system.")

@dataclass(frozen=True)
class DecisionPrompt:
    version: str
    decision_id: str
    contract_digest: str
    agent: str
    task_id: str | None
    requested_at: str
    boundary: dict[str, Any]
    requested_action: dict[str, Any]
    why_held: str
    consequence: str
    state: str
    choices: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

def from_approval(approval: Approval) -> DecisionPrompt:
    action = dict(approval.action or {})
    params = action.get("params") if isinstance(action.get("params"), dict) else {}
    binding = {
        "approval_id": approval.id,
        "agent": approval.agent,
        "task_id": approval.task_id,
        "adapter": approval.adapter,
        "action": action,
        "grant_id": approval.grant_id,
        "requested_at": approval.requested_at,
    }
    context = approval.decision_context or {}
    reason = str(context.get("reason") or "This action requires explicit approval before execution.")
    impact = str(action.get("impact") or "unknown")
    return DecisionPrompt(
        version=VERSION,
        decision_id=approval.id,
        contract_digest=_sha(binding),
        agent=approval.agent,
        task_id=approval.task_id,
        requested_at=approval.requested_at,
        boundary={
            "adapter": approval.adapter,
            "resource": action.get("domain") or "unspecified",
            "protected_action": action.get("tool") or "unknown",
        },
        requested_action={
            "tool": action.get("tool") or "unknown",
            "resource": action.get("domain") or "unspecified",
            "impact": impact,
            "intent": action.get("intent"),
            "facts": _safe_facts(params),
            "parameters_digest": _sha(params),
        },
        why_held=reason,
        consequence=_consequence(impact),
        state=approval.status,
        choices=[
            {"id":"allow_once","label":"Allow once","kind":"decision","effect":"Resume this exact pending action once. This does not create standing authority."},
            {"id":"deny","label":"Deny","kind":"decision","effect":"Keep this protected action from executing and record the denial."},
            {"id":"inspect","label":"Why was this held?","kind":"information","effect":"Show the boundary, reason, scope, and non-secret action facts without granting authority."},
        ],
    )

def render_text(prompt: DecisionPrompt | dict[str, Any]) -> str:
    data = prompt.to_dict() if isinstance(prompt, DecisionPrompt) else prompt
    action = data["requested_action"]
    boundary = data["boundary"]
    lines = [
        "LEDGATo paused this action",
        "",
        f"{data['agent']} wants to perform {action['tool']}.",
        f"Resource: {boundary['resource']}",
        f"Impact: {action['impact']}",
        f"Why held: {data['why_held']}",
        f"Consequence: {data['consequence']}",
    ]
    if data.get("task_id"):
        lines.append(f"Task: {data['task_id']}")
    for fact in action.get("facts") or []:
        lines.append(f"{fact['key']}: {fact['value']}")
    lines += ["", "Nothing downstream has happened yet.", f"Scope: this exact pending action · {data['contract_digest'][:12]}"]
    return "\n".join(lines)
