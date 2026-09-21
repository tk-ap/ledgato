"""Campaign authority: the persisted, digest-pinned authorization for an
adversarial validation campaign.

This is an orthogonal layer on top of the existing enforcement engine. It does
not replace authority grants, principals, or the gateway. It answers one
question the base engine cannot: is this adversarial caller acting inside a
currently valid campaign envelope, and is the requested attack surface within
that envelope's declared scope.

Only public authorization material is stored (the AgentOS PR #143 envelope
shape). Attacker prompts, tactics, reasoning, mutation strategy, and future
plans are never received or persisted here. The whole validated envelope is
canonicalized into a deterministic SHA-256 digest; that digest is the identity
of the authorized campaign state, and every execution transition revalidates
against it.

An adversarial principal can never register, widen, replace, or revoke its own
campaign authority: those are administrative operations, gated at the API to
the admin role. This store does not itself grant execution; it only records and
serves the pinned authority.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

try:  # POSIX advisory locking; absent on Windows.
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None

from .models import utcnow


class CampaignError(ValueError):
    """The campaign envelope is malformed, or the store operation is invalid."""


def canonical_digest(envelope: dict[str, Any]) -> str:
    """Deterministic SHA-256 over the whole validated public envelope."""
    return hashlib.sha256(
        json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _parse_time(value: str, field_name: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, AttributeError) as exc:
        raise CampaignError(f"{field_name} is not a valid date-time") from exc
    if parsed.tzinfo is None:
        raise CampaignError(f"{field_name} must include a timezone")
    return parsed.astimezone(timezone.utc)


@dataclass
class CampaignAuthority:
    """Pinned, public authorization state for one adversarial campaign."""

    campaign_id: str
    principal_id: str
    authority_ref: str
    campaign_digest: str
    issued_at: str
    expires_at: str
    target: dict[str, Any]
    permitted_attack_surface: list[str]
    prohibited_surfaces: list[str]
    budget: dict[str, Any]
    revoked_at: str | None = None
    revoked_by: str | None = None
    revocation_reason: str | None = None

    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    def is_expired(self, now: datetime | None = None) -> bool:
        current = (now or utcnow()).astimezone(timezone.utc)
        return current >= _parse_time(self.expires_at, "expires_at")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_authority(envelope: dict[str, Any], *, expected_principal_id: str) -> CampaignAuthority:
    """Validate a public campaign envelope and pin it to an adversarial principal.

    Only the public authorization fields are read. The digest covers the whole
    envelope, so any later change to it is detectable on revalidation.
    """
    if not isinstance(envelope, dict):
        raise CampaignError("campaign envelope must be an object")
    try:
        authorization = envelope["authorization"]
        campaign_id = envelope["campaign_id"]
        authority_ref = authorization["authority_ref"]
        issued_at = authorization["issued_at"]
        expires_at = authorization["expires_at"]
        target = envelope["target"]
        permitted = envelope["permitted_attack_surface"]
        prohibited = envelope["prohibited_surfaces"]
        budget = envelope["budget"]
    except (KeyError, TypeError) as exc:
        raise CampaignError(f"campaign envelope missing field: {exc}") from exc

    if authorization.get("target_owned_or_authorized") is not True:
        raise CampaignError("authorization.target_owned_or_authorized must be true")
    if not isinstance(permitted, list) or not permitted:
        raise CampaignError("permitted_attack_surface must be a non-empty array")
    if not isinstance(prohibited, list) or not prohibited:
        raise CampaignError("prohibited_surfaces must be a non-empty array")
    overlap = sorted(set(permitted) & set(prohibited))
    if overlap:
        raise CampaignError("surface is both permitted and prohibited: " + ", ".join(overlap))
    issued = _parse_time(issued_at, "authorization.issued_at")
    expires = _parse_time(expires_at, "authorization.expires_at")
    if expires <= issued:
        raise CampaignError("authorization.expires_at must be after issued_at")
    if not str(expected_principal_id or "").strip():
        raise CampaignError("a campaign must be pinned to an adversarial principal id")

    return CampaignAuthority(
        campaign_id=campaign_id,
        principal_id=expected_principal_id,
        authority_ref=authority_ref,
        campaign_digest=canonical_digest(envelope),
        issued_at=issued_at,
        expires_at=expires_at,
        target=dict(target),
        permitted_attack_surface=list(permitted),
        prohibited_surfaces=list(prohibited),
        budget=dict(budget),
    )


@dataclass
class CampaignDecision:
    allow: bool
    reason: str
    campaign_id: str | None = None
    campaign_digest: str | None = None


class CampaignAuthorityStore:
    """File-backed pinned campaign authority, with the same cross-process
    locking contract as AuthorityStore/ApprovalStore.
    """

    def __init__(self, path: str | Path | None = None):
        self._thread_lock = threading.RLock()
        self.path = Path(path) if path else None
        self._campaigns: dict[str, CampaignAuthority] = {}
        self._load()

    @contextmanager
    def _exclusive(self):
        with self._thread_lock:
            if not self.path or fcntl is None:
                yield
                return
            self.path.parent.mkdir(parents=True, exist_ok=True)
            lock_path = self.path.with_suffix(self.path.suffix + ".lock")
            fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX)
                self._load()
                yield
            finally:
                try:
                    fcntl.flock(fd, fcntl.LOCK_UN)
                finally:
                    os.close(fd)

    def register(self, authority: CampaignAuthority) -> CampaignAuthority:
        """Pin a campaign once. Re-registering with a different digest is refused.

        Registration is an administrative act; the API restricts it to the
        admin role. An adversarial principal never reaches this method.
        """
        with self._exclusive():
            existing = self._campaigns.get(authority.campaign_id)
            if existing is not None:
                if existing.campaign_digest != authority.campaign_digest:
                    raise CampaignError(
                        f"campaign '{authority.campaign_id}' is already pinned to a "
                        "different authority digest; refusing to widen or replace it"
                    )
                return existing
            self._campaigns[authority.campaign_id] = authority
            self._save()
            return authority

    def get(self, campaign_id: str) -> CampaignAuthority | None:
        return self._campaigns.get(campaign_id)

    def revoke(self, campaign_id: str, *, revoked_by: str, reason: str) -> CampaignAuthority:
        with self._exclusive():
            authority = self._campaigns.get(campaign_id)
            if authority is None:
                raise KeyError(campaign_id)
            if not authority.is_revoked():
                authority.revoked_at = utcnow().isoformat()
                authority.revoked_by = revoked_by
                authority.revocation_reason = reason
                self._save()
            return authority

    def list(self) -> list[CampaignAuthority]:
        return list(self._campaigns.values())

    def _load(self) -> None:
        if not self.path or not self.path.exists():
            return
        raw = json.loads(self.path.read_text() or "[]")
        self._campaigns = {r["campaign_id"]: CampaignAuthority(**r) for r in raw}

    def _save(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps([a.to_dict() for a in self._campaigns.values()],
                             indent=2, sort_keys=True)
        tmp = self.path.with_suffix(self.path.suffix + f".tmp.{os.getpid()}")
        tmp.write_text(payload)
        tmp.replace(self.path)


def authorize_campaign_action(
    store: CampaignAuthorityStore,
    *,
    principal_id: str,
    campaign_id: str | None,
    authority_ref: str | None,
    campaign_digest: str | None,
    attack_surface: Iterable[str] | str | None,
    now: datetime | None = None,
) -> CampaignDecision:
    """Fail-closed campaign check, reloaded from the persisted store every call.

    The persisted authority — never the request, a checkpoint, a provider
    session, or a previous success — is the source of scope. Called before the
    initial attempt, on resume, and on every retry/restart/rotation/replay.
    Over-scope is DENY, never APPROVE.
    """
    def deny(reason: str) -> CampaignDecision:
        return CampaignDecision(allow=False, reason=reason, campaign_id=campaign_id)

    if not campaign_id:
        return deny("adversarial request carries no campaign_id")
    authority = store.get(campaign_id)
    if authority is None:
        return deny(f"unknown campaign '{campaign_id}'")
    if authority.is_revoked():
        return deny("campaign authority has been revoked")
    if authority.is_expired(now):
        return deny("campaign authority has expired")
    if authority.principal_id != principal_id:
        return deny("principal does not match the pinned campaign authority")
    if authority.authority_ref != authority_ref:
        return deny("authority_ref does not match the pinned campaign authority")
    if authority.campaign_digest != campaign_digest:
        return deny("campaign digest does not match the pinned authority")

    if attack_surface is None:
        return deny("adversarial request declared no attack surface")
    requested = {attack_surface} if isinstance(attack_surface, str) else set(attack_surface)
    if not requested:
        return deny("adversarial request declared no attack surface")
    permitted = set(authority.permitted_attack_surface)
    prohibited = set(authority.prohibited_surfaces)
    over = sorted(requested - permitted)
    if over:
        return deny("attack surface outside permitted scope: " + ", ".join(over))
    touched = sorted(requested & prohibited)
    if touched:
        return deny("attack surface touches a prohibited surface: " + ", ".join(touched))

    return CampaignDecision(
        allow=True, reason="within pinned campaign scope",
        campaign_id=campaign_id, campaign_digest=authority.campaign_digest,
    )
