"""Approval state for consequential actions that must pause before execution."""
from __future__ import annotations

import json
import secrets
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .models import utcnow

PENDING = "PENDING"
APPROVED = "APPROVED"
DENIED = "DENIED"
CONSUMED = "CONSUMED"


@dataclass
class Approval:
    id: str
    agent: str
    task_id: str | None
    adapter: str
    action: dict[str, Any]
    grant_id: str | None
    requested_at: str
    requested_by: str | None = None
    status: str = PENDING
    decided_at: str | None = None
    decided_by: str | None = None
    decision_reason: str | None = None
    resume_token: str = field(default_factory=lambda: secrets.token_urlsafe(24))
    jit_grant_id: str | None = None
    consumed_at: str | None = None

    def to_dict(self, *, include_resume_token: bool = False) -> dict[str, Any]:
        data = asdict(self)
        if not include_resume_token:
            data.pop("resume_token", None)
        return data


class ApprovalStore:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else None
        self._items: dict[str, Approval] = {}
        self._load()

    def request(
        self,
        *,
        agent: str,
        task_id: str | None,
        adapter: str,
        action: dict[str, Any],
        grant_id: str | None,
        requested_by: str | None = None,
    ) -> Approval:
        approval = Approval(
            id=f"approval_{secrets.token_urlsafe(12)}",
            agent=agent,
            task_id=task_id,
            adapter=adapter,
            action=action,
            grant_id=grant_id,
            requested_at=utcnow().isoformat(),
            requested_by=requested_by,
        )
        self._items[approval.id] = approval
        self._save()
        return approval

    def get(self, approval_id: str) -> Approval | None:
        return self._items.get(approval_id)

    def decide(self, approval_id: str, *, approved: bool, decided_by: str, reason: str | None = None) -> Approval:
        item = self._require(approval_id)
        if item.status != PENDING:
            raise ValueError(f"approval is already {item.status}")
        item.status = APPROVED if approved else DENIED
        item.decided_at = utcnow().isoformat()
        item.decided_by = decided_by
        item.decision_reason = reason
        self._save()
        return item

    def attach_jit_grant(self, approval_id: str, grant_id: str) -> Approval:
        item = self._require(approval_id)
        item.jit_grant_id = grant_id
        self._save()
        return item

    def consume(self, approval_id: str, resume_token: str) -> Approval:
        item = self._require(approval_id)
        if item.status != APPROVED:
            raise ValueError(f"approval is {item.status}, not APPROVED")
        if not secrets.compare_digest(item.resume_token, resume_token):
            raise PermissionError("invalid resume token")
        item.status = CONSUMED
        item.consumed_at = utcnow().isoformat()
        self._save()
        return item

    def list(self, *, status: str | None = None) -> list[Approval]:
        items = list(self._items.values())
        return [i for i in items if i.status == status] if status else items

    def _require(self, approval_id: str) -> Approval:
        item = self.get(approval_id)
        if not item:
            raise KeyError(approval_id)
        return item

    def _load(self) -> None:
        if not self.path or not self.path.exists():
            return
        raw = json.loads(self.path.read_text() or "[]")
        self._items = {item["id"]: Approval(**item) for item in raw}

    def _save(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps([asdict(i) for i in self._items.values()], indent=2, sort_keys=True))
