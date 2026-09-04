"""Persistent delegated/JIT authority grants."""
from __future__ import annotations

import json
import secrets
from datetime import timedelta
from pathlib import Path
from typing import Iterable

from .models import AuthorityGrant, IMPACTS, parse_time, utcnow


class AuthorityStore:
    """Small file-backed authority-grant registry.

    The store is provider-neutral: IAM systems can issue the actual credential
    while Ledgato records the bounded grant valid for a task. Child grants can
    only narrow parent authority, and parent expiry/revocation invalidates the
    entire delegation chain.
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
        tool_set = set(tools)
        domains = list(data_domains)
        expires_at = (now + timedelta(seconds=ttl_seconds)).isoformat() if ttl_seconds else None

        if parent_grant_id:
            parent = self._require(parent_grant_id)
            valid, reason = self.validate(parent_grant_id)
            if not valid:
                raise ValueError(f"parent grant is not effective: {reason}")
            if parent.agent != agent:
                raise ValueError("child grant agent must match parent grant agent")
            if parent.tools and not tool_set.issubset(parent.tools):
                raise ValueError("child grant cannot add tools outside parent authority")
            if IMPACTS.get(impact_max, 1) > parent.impact_max_severity():
                raise ValueError("child grant cannot exceed parent impact authority")
            if parent.task_id and task_id != parent.task_id:
                raise ValueError("child grant must remain bound to the parent task")
            if parent.data_domains:
                outside = [d for d in domains if not _domain_allowed(d, parent.data_domains)]
                if outside:
                    raise ValueError(f"child grant domains exceed parent authority: {outside}")
            parent_expiry = parse_time(parent.expires_at)
            child_expiry = parse_time(expires_at)
            if parent_expiry and (not child_expiry or child_expiry > parent_expiry):
                expires_at = parent_expiry.isoformat()

        grant = AuthorityGrant(
            id=f"grant_{secrets.token_urlsafe(12)}",
            agent=agent,
            granted_by=granted_by,
            purpose=purpose,
            tools=tool_set,
            data_domains=domains,
            impact_max=impact_max,
            task_id=task_id,
            credential_ref=credential_ref,
            parent_grant_id=parent_grant_id,
            issued_at=now.isoformat(),
            expires_at=expires_at,
        )
        self._grants[grant.id] = grant
        self._save()
        return grant

    def get(self, grant_id: str | None) -> AuthorityGrant | None:
        if not grant_id:
            return None
        return self._grants.get(grant_id)

    def validate(self, grant_id: str) -> tuple[bool, str | None]:
        """Validate the whole delegation chain, including ancestor revocation."""
        seen: set[str] = set()
        current = self.get(grant_id)
        if not current:
            return False, "unknown grant"
        leaf_agent = current.agent
        while current:
            if current.id in seen:
                return False, "delegation cycle detected"
            seen.add(current.id)
            if current.agent != leaf_agent:
                return False, "delegation chain changes agent identity"
            if not current.active():
                return False, f"grant '{current.id}' is expired or revoked"
            if not current.parent_grant_id:
                return True, None
            parent = self.get(current.parent_grant_id)
            if not parent:
                return False, f"missing parent grant '{current.parent_grant_id}'"
            current = parent
        return True, None

    def effective(self, grant_id: str | None) -> AuthorityGrant | None:
        if not grant_id:
            return None
        grant = self.get(grant_id)
        valid, _ = self.validate(grant_id)
        return grant if grant and valid else None

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
            grants = [g for g in grants if self.validate(g.id)[0]]
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


def _domain_allowed(domain: str, allowed: list[str]) -> bool:
    if domain in allowed:
        return True
    return any(pat.endswith("*") and domain.startswith(pat[:-1]) for pat in allowed)
