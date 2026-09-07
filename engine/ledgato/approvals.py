"""Approval state for consequential actions that must pause before execution."""
from __future__ import annotations

import errno
import json
import os
import secrets
import threading
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

try:  # POSIX advisory locking; absent on Windows.
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None

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
    #: Guards read-modify-write sequences within a single process.
    _thread_lock = threading.Lock()

    @contextmanager
    def _exclusive(self):
        """Serialize a read-modify-write across threads *and* processes.

        The approval store is file-backed and each process holds its own
        in-memory copy, so checking ``status`` against that copy is a
        time-of-check/time-of-use bug: several workers can each observe
        APPROVED and each execute the protected action from one human
        approval. An advisory lock on a sidecar file plus a re-read inside the
        lock closes that window.
        """
        with self._thread_lock:
            if not self.path or fcntl is None:
                yield
                return
            self.path.parent.mkdir(parents=True, exist_ok=True)
            lock_path = self.path.with_suffix(self.path.suffix + ".lock")
            fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX)
                self._load()            # discard stale state; re-read under lock
                yield
            finally:
                try:
                    fcntl.flock(fd, fcntl.LOCK_UN)
                finally:
                    os.close(fd)

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
        """Claim an approval exactly once.

        The status check and the write happen under an exclusive lock, so a
        concurrent resume — in this process or another worker — sees CONSUMED
        and is refused rather than executing the protected action again.
        """
        with self._exclusive():
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
        payload = json.dumps([asdict(i) for i in self._items.values()], indent=2, sort_keys=True)
        tmp = self.path.with_suffix(self.path.suffix + f".tmp.{os.getpid()}")
        tmp.write_text(payload)
        tmp.replace(self.path)          # atomic on POSIX
