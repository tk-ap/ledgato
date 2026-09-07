"""Fail-closed idempotency records for protected gateway executions.

The store intentionally favors duplicate prevention over automatic recovery. Once an
operation key is marked PENDING, a retry cannot execute the protected action until
that record is completed or an operator deliberately resolves the uncertain state.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .models import utcnow

PENDING = "PENDING"
COMPLETED = "COMPLETED"


class IdempotencyConflict(ValueError):
    """The same operation key was reused for a different request."""


class IdempotencyPending(ValueError):
    """A prior attempt may have crossed the boundary but did not complete its receipt."""


@dataclass
class IdempotencyRecord:
    key: str
    fingerprint: str
    status: str
    created_at: str
    completed_at: str | None = None
    result: dict[str, Any] | None = None


class IdempotencyStore:
    """Small file-backed operation registry for a single-process pilot.

    This is not a distributed lock. It provides durable retry semantics for the
    constrained first-client deployment and deliberately fails closed when a
    previous attempt is left PENDING.
    """

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else None
        self._records: dict[str, IdempotencyRecord] = {}
        self._load()

    @staticmethod
    def fingerprint(request: dict[str, Any]) -> str:
        payload = json.dumps(request, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def begin(self, key: str, request: dict[str, Any]) -> dict[str, Any] | None:
        if not key or not key.strip():
            raise ValueError("idempotency key must not be empty")
        fp = self.fingerprint(request)
        existing = self._records.get(key)
        if existing:
            if existing.fingerprint != fp:
                raise IdempotencyConflict(
                    f"idempotency key '{key}' was already used for a different protected request"
                )
            if existing.status == COMPLETED and existing.result is not None:
                return dict(existing.result)
            raise IdempotencyPending(
                f"idempotency key '{key}' has an unresolved prior attempt; verify downstream state before retrying"
            )

        self._records[key] = IdempotencyRecord(
            key=key,
            fingerprint=fp,
            status=PENDING,
            created_at=utcnow().isoformat(),
        )
        self._save()
        return None

    def complete(self, key: str, result: dict[str, Any]) -> dict[str, Any]:
        record = self._records.get(key)
        if not record:
            raise KeyError(key)
        if record.status == COMPLETED:
            return dict(record.result or {})
        record.status = COMPLETED
        record.completed_at = utcnow().isoformat()
        record.result = dict(result)
        self._save()
        return dict(record.result)

    def get(self, key: str) -> IdempotencyRecord | None:
        return self._records.get(key)

    def list(self) -> list[IdempotencyRecord]:
        return list(self._records.values())

    def _load(self) -> None:
        if not self.path or not self.path.exists():
            return
        raw = json.loads(self.path.read_text() or "[]")
        self._records = {item["key"]: IdempotencyRecord(**item) for item in raw}

    def _save(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(self.path.suffix + ".tmp")
        temp.write_text(
            json.dumps([asdict(r) for r in self._records.values()], indent=2, sort_keys=True)
        )
        temp.replace(self.path)
