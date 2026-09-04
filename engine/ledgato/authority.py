"""Persistent delegated/JIT authority grants."""
from __future__ import annotations

import json
import secrets
from datetime import timedelta
from pathlib import Path
from typing import Iterable

from .models import AuthorityGrant, utcnow


class AuthorityStore:
    """Small file-backed authority-grant registry.

    The store is deliberately provider-neutral: IAM systems can issue the actual
    credential while Ledgato records the bounded grant that is valid for a task.
    """

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else None
        self._grants: dict[str, AuthorityGrant] = {}
        self._load()

    def issue(
        self,
        *,
        agent: str,
        granted_by: str,
        purpose: str,
        tools: Iterable[str] = (),
        data_domains: Iterable[str] = (),
        impact_max: str = "readonly",
        task_id: str | None = None,
        credential_ref: str | None = None,
        parent_grant_id: str | None = None,
        ttl_seconds: int | None = None,
    ) -> AuthorityGrant:
        now = utcnow()
        expires = (now + timedelta(seconds=ttl_seconds)).isoformat() if ttl_seconds else None
        grant = AuthorityGrant(
            id=f"grant_{secrets.token_urlsafe(12)}",
            agent=agent,
            granted_by=granted_by,
            purpose=purpose,
            tools=set(tools),
            data_domains=list(data_domains),
            impact_max=impact_max,
            task_id=task_id,
            credential_ref=credential_ref,
            parent_grant_id=parent_grant_id,
            issued_at=now.isoformat(),
            expires_at=expires,
        )
        self._grants[grant.id] = grant
        self._save()
        return grant

    def get(self, grant_id: str | None) -> AuthorityGrant | None:
        if not grant_id:
            return None
        return self._grants.get(grant_id)

    def revoke(self, grant_id: str, *, revoked_by: str, reason: str) -> AuthorityGrant:
        grant = self._require(grant_id)
        if not grant.revoked_at:
            grant.revoked_at = utcnow().isoformat()
            grant.revoked_by = revoked_by
            grant.revocation_reason = reason
            self._save()
        return grant

    def list(self, *, agent: str | None = None, active_only: bool = False) -> list[AuthorityGrant]:
        grants = list(self._grants.values())
        if agent:
            grants = [g for g in grants if g.agent == agent]
        if active_only:
            grants = [g for g in grants if g.active()]
        return grants

    def _require(self, grant_id: str) -> AuthorityGrant:
        grant = self.get(grant_id)
        if not grant:
            raise KeyError(grant_id)
        return grant

    def _load(self) -> None:
        if not self.path or not self.path.exists():
            return
        raw = json.loads(self.path.read_text() or "[]")
        self._grants = {item["id"]: AuthorityGrant.from_dict(item) for item in raw}

    def _save(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps([g.to_dict() for g in self._grants.values()], indent=2, sort_keys=True))
