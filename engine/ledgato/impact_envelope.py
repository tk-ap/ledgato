"""Conservative expected-impact context for one exact pending approval.

Impact informs the human decision but never grants authority. Deterministic
provider/runtime facts should be supplied through impact_context; absent that,
this module emits a deliberately partial envelope from the exact stored action.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .approvals import Approval

VERSION = "ledgato.impact-envelope/v1"
CONFIDENCE = {"KNOWN", "INFERRED", "UNKNOWN"}
EXTENT = {"LOW", "MEDIUM", "HIGH", "UNKNOWN"}
CHANGE_KINDS = {
    "CREATE", "MODIFY", "REPLACE", "DELETE", "MOVE", "GRANT", "REVOKE",
    "RESTART", "MIGRATE", "EXECUTE", "OTHER",
}
CATEGORIES = {
    "DEPENDENCY", "WORKSTREAM", "AUTHORITY", "RUNTIME", "DATA", "USER",
    "SECURITY", "OTHER",
}
REVERSIBILITY = {
    "REVERSIBLE", "PARTIALLY_REVERSIBLE", "IRREVERSIBLE", "UNKNOWN",
}
NOVELTY = {"KNOWN_REPEATED", "KNOWN_CHANGED", "NEW", "UNKNOWN"}
RESOLUTION = {"COMPLETE", "PARTIAL", "UNAVAILABLE"}


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(envelope: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(envelope).encode("utf-8")).hexdigest()


def _text(value: Any, *, limit: int = 280) -> str:
    value = str(value or "").strip()
    return value if len(value) <= limit else value[: limit - 3] + "..."


def _enum(value: Any, allowed: set[str], default: str) -> str:
    candidate = str(value or "").upper()
    return candidate if candidate in allowed else default


def _evidence_refs(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_text(item, limit=220) for item in value[:12] if _text(item, limit=220)]


def _direct_change(item: Any, *, trusted: bool = False) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    subject = _text(item.get("subject"))
    summary = _text(item.get("summary"))
    if not subject or not summary:
        return None
    return {
        "kind": _enum(item.get("kind"), CHANGE_KINDS, "OTHER"),
        "subject": subject,
        "summary": summary,
        "confidence": (\n            _enum(item.get("confidence"), CONFIDENCE, "UNKNOWN")\n            if trusted else "INFERRED"\n        ),
        "evidence_refs": _evidence_refs(item.get("evidence_refs")),
    }


def _related_impact(item: Any, *, trusted: bool = False) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    subject = _text(item.get("subject"))
    effect = _text(item.get("effect"))
    if not subject or not effect:
        return None
    return {
        "category": _enum(item.get("category"), CATEGORIES, "OTHER"),
        "subject": subject,
        "effect": effect,
        "extent": _enum(item.get("extent"), EXTENT, "UNKNOWN"),
        "confidence": (
            _enum(item.get("confidence"), CONFIDENCE, "UNKNOWN")
            if trusted else "INFERRED"
        ),
        "evidence_refs": _evidence_refs(item.get("evidence_refs")),
    }


def _fallback_direct(approval: "Approval") -> list[dict[str, Any]]:
    action = dict(approval.action or {})
    impact = str(action.get("impact") or "unknown").lower()
    tool = _text(action.get("tool") or "unknown")
    resource = _text(action.get("domain") or "unspecified")
    kind = {
        "readonly": "OTHER",
        "write": "MODIFY",
        "exec": "EXECUTE",
        "destructive": "OTHER",
    }.get(impact, "OTHER")
    if impact == "readonly":
        summary = f"The stored action declares read-only access to {resource}."
    else:
        summary = (
            f"The stored action {tool} targets {resource} with declared "
            f"impact class {impact}."
        )
    return [{
        "kind": kind,
        "subject": resource,
        "summary": summary,
        "confidence": "KNOWN",
        "evidence_refs": [],
    }]


def build(approval: "Approval", *, action_contract_digest: str) -> dict[str, Any]:
    context = approval.decision_context if isinstance(approval.decision_context, dict) else {}
    # impact_context currently arrives on the governed agent request. Treat it\n    # as advisory hints only: the actor asking for authority cannot self-certify\n    # its own blast-radius claims as KNOWN.\n    supplied = context.get("impact_context")
    supplied = supplied if isinstance(supplied, dict) else {}

    direct = [
        parsed for parsed in (_direct_change(item, trusted=False) for item in supplied.get("direct_changes", []))
        if parsed is not None
    ][:16]
    if not direct:
        direct = _fallback_direct(approval)

    related = [
        parsed for parsed in (_related_impact(item, trusted=False) for item in supplied.get("related_impacts", []))
        if parsed is not None
    ][:16]
    if approval.task_id and not any(
        item["category"] == "WORKSTREAM" and item["subject"] == approval.task_id
        for item in related
    ):
        related.append({
            "category": "WORKSTREAM",
            "subject": approval.task_id,
            "effect": "This protected action is linked to this AgentOS task.",
            "extent": "UNKNOWN",
            "confidence": "KNOWN",
            "evidence_refs": [],
        })

    raw_rev = supplied.get("reversibility")
    raw_rev = raw_rev if isinstance(raw_rev, dict) else {}
    reversibility = {
        "class": _enum(raw_rev.get("class"), REVERSIBILITY, "UNKNOWN"),
        "summary": _text(
            raw_rev.get("summary")
            or "Reversibility has not yet been established for this exact action."
        ),
        "confidence": "INFERRED" if raw_rev else "UNKNOWN",
        "evidence_refs": _evidence_refs(raw_rev.get("evidence_refs")),
    }

    raw_novelty = supplied.get("novelty")
    raw_novelty = raw_novelty if isinstance(raw_novelty, dict) else {}
    novelty = {
        "class": _enum(raw_novelty.get("class"), NOVELTY, "UNKNOWN"),
        "summary": _text(
            raw_novelty.get("summary")
            or "No sufficiently similar proven action has been established in this envelope."
        ),
        "confidence": "INFERRED" if raw_novelty else "UNKNOWN",
        "evidence_refs": _evidence_refs(raw_novelty.get("evidence_refs")),
    }

    unknowns = []
    if isinstance(supplied.get("unknowns"), list):
        unknowns = [_text(item) for item in supplied["unknowns"][:12] if _text(item)]
    if not supplied:
        unknowns.extend([
            "Exact downstream create/replace/delete delta was not supplied.",
            "Indirect dependency and workstream blast radius has not been resolved.",
        ])

    resolution = _enum(
        supplied.get("resolution_state"),
        RESOLUTION,
        "PARTIAL" if direct or related else "UNAVAILABLE",
    )

    return {
        "version": VERSION,
        "action_contract_digest": action_contract_digest,
        # Stable across repeated GETs for the same pending approval.
        "generated_at": approval.requested_at,
        "resolution_state": resolution,
        "direct_changes": direct,
        "related_impacts": related,
        "reversibility": reversibility,
        "novelty": novelty,
        "unknowns": unknowns,
        "source_refs": _evidence_refs(supplied.get("source_refs")),
    }
