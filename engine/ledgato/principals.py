"""Authenticated principals and separation of duties.

Before this module, Ledgato trusted identity fields supplied in the request
body: ``agent``, ``requested_by``, ``granted_by``, ``revoked_by``, ``decided_by``.
A single shared API key was therefore enough for a governed agent to approve its
own pending request, or to act as any other agent.

A principal is now derived from the presented credential, and the credential's
role decides what it may call. Body-supplied identities are still accepted, but
only as *claims* that must match the authenticated principal.

Scope note: this is deliberately the smallest thing that proves separation of
duties for the lab. It is not SSO, not user management, and not key rotation.
Credentials are compared in constant time; they are still bearer secrets.
"""
from __future__ import annotations

import hmac
import os
from dataclasses import dataclass
from typing import Iterable, Optional

#: An autonomous agent under governance. May request execution as itself only.
ROLE_AGENT = "agent"
#: A human who may decide pending approvals. May not act as an agent.
ROLE_APPROVER = "approver"
#: Authority administrator. May issue and revoke grants.
ROLE_ADMIN = "admin"

ROLES: frozenset[str] = frozenset({ROLE_AGENT, ROLE_APPROVER, ROLE_ADMIN})


@dataclass(frozen=True)
class Principal:
    """An authenticated caller."""

    id: str
    role: str

    def is_agent(self) -> bool:
        return self.role == ROLE_AGENT

    def may_decide_approvals(self) -> bool:
        return self.role == ROLE_APPROVER

    def may_administer_authority(self) -> bool:
        return self.role == ROLE_ADMIN

    def to_dict(self) -> dict[str, str]:
        return {"id": self.id, "role": self.role}


class PrincipalRegistry:
    """Maps bearer credentials to principals.

    Construct from explicit principals, or from the ``LEDGATO_PRINCIPALS``
    environment variable using ``id:role:secret`` triples separated by commas:

        LEDGATO_PRINCIPALS="lab-agent:agent:s1,tk:approver:s2,ops:admin:s3"
    """

    def __init__(self, entries: Iterable[tuple[str, str, str]] = ()):
        self._by_secret: dict[str, Principal] = {}
        for principal_id, role, secret in entries:
            self.add(principal_id, role, secret)

    def add(self, principal_id: str, role: str, secret: str) -> Principal:
        if role not in ROLES:
            raise ValueError(f"unknown role '{role}' (expected one of {sorted(ROLES)})")
        if not secret:
            raise ValueError(f"principal '{principal_id}' must have a non-empty secret")
        if not principal_id:
            raise ValueError("principal id must be non-empty")
        principal = Principal(id=principal_id, role=role)
        self._by_secret[secret] = principal
        return principal

    @classmethod
    def from_env(cls, var: str = "LEDGATO_PRINCIPALS") -> "PrincipalRegistry":
        raw = os.getenv(var, "").strip()
        entries: list[tuple[str, str, str]] = []
        if raw:
            for chunk in raw.split(","):
                chunk = chunk.strip()
                if not chunk:
                    continue
                parts = chunk.split(":")
                if len(parts) != 3:
                    raise ValueError(
                        f"malformed {var} entry '{chunk}' (expected id:role:secret)"
                    )
                entries.append((parts[0], parts[1], parts[2]))
        return cls(entries)

    def __len__(self) -> int:
        return len(self._by_secret)

    def configured(self) -> bool:
        return bool(self._by_secret)

    def resolve(self, token: str | None) -> Optional[Principal]:
        """Return the principal for a bearer token, or None.

        Compared in constant time against every registered secret so that a
        wrong token cannot be narrowed down by timing.
        """
        if not token:
            return None
        found: Optional[Principal] = None
        for secret, principal in self._by_secret.items():
            if hmac.compare_digest(secret, token):
                found = principal
        return found


class IdentityClaimError(Exception):
    """A body-supplied identity did not match the authenticated principal."""


def enforce_claim(principal: Principal, claimed: str | None, *, field: str) -> str:
    """Bind a body-supplied identity claim to the authenticated principal.

    Returns the identity to record. A claim that disagrees with the presented
    credential is rejected rather than silently overwritten, so that spoofing
    attempts appear as errors instead of quietly-corrected requests.
    """
    if claimed is not None and claimed != principal.id:
        raise IdentityClaimError(
            f"{field} '{claimed}' does not match authenticated principal '{principal.id}'"
        )
    return principal.id
