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

#: A read-only independent verifier. May observe; never mutates, executes,
#: issues authority, or decides approvals.
ROLE_VERIFIER = "verifier"

ROLES: frozenset[str] = frozenset(
    {ROLE_AGENT, ROLE_APPROVER, ROLE_ADMIN, ROLE_VERIFIER}
)

#: Trust domains are orthogonal to roles. ``role`` says what an identity may do;
#: ``trust_domain`` says which security domain it belongs to. Existing
#: principals default to ``operational`` so nothing changes for them.
TRUST_OPERATIONAL = "operational"
TRUST_ADVERSARIAL = "adversarial"
TRUST_VERIFIER = "verifier"

TRUST_DOMAINS: frozenset[str] = frozenset(
    {TRUST_OPERATIONAL, TRUST_ADVERSARIAL, TRUST_VERIFIER}
)


@dataclass(frozen=True)
class Principal:
    """An authenticated caller.

    ``role`` is the separation-of-duties role (agent/approver/admin/verifier).
    ``trust_domain`` is the orthogonal security domain the identity belongs to.
    """

    id: str
    role: str
    trust_domain: str = TRUST_OPERATIONAL

    def is_agent(self) -> bool:
        return self.role == ROLE_AGENT

    def may_decide_approvals(self) -> bool:
        return self.role == ROLE_APPROVER

    def may_administer_authority(self) -> bool:
        return self.role == ROLE_ADMIN

    def is_operational(self) -> bool:
        return self.trust_domain == TRUST_OPERATIONAL

    def is_adversarial(self) -> bool:
        return self.trust_domain == TRUST_ADVERSARIAL

    def is_verifier(self) -> bool:
        return self.trust_domain == TRUST_VERIFIER or self.role == ROLE_VERIFIER

    def to_dict(self) -> dict[str, str]:
        return {"id": self.id, "role": self.role, "trust_domain": self.trust_domain}


class PrincipalRegistry:
    """Maps bearer credentials to principals.

    Construct from explicit principals, or from the ``LEDGATO_PRINCIPALS``
    environment variable using ``id:role:secret`` triples separated by commas:

        LEDGATO_PRINCIPALS="lab-agent:agent:s1,tk:approver:s2,ops:admin:s3"
    """

    def __init__(self, entries: Iterable[tuple] = ()):
        self._by_secret: dict[str, Principal] = {}
        for entry in entries:
            if len(entry) == 3:
                principal_id, role, secret = entry
                self.add(principal_id, role, secret)
            elif len(entry) == 4:
                principal_id, role, trust_domain, secret = entry
                self.add(principal_id, role, secret, trust_domain)
            else:
                raise ValueError(
                    "principal entry must be (id, role, secret) or "
                    "(id, role, trust_domain, secret)"
                )

    def add(
        self,
        principal_id: str,
        role: str,
        secret: str,
        trust_domain: str = TRUST_OPERATIONAL,
    ) -> Principal:
        if role not in ROLES:
            raise ValueError(f"unknown role '{role}' (expected one of {sorted(ROLES)})")
        if trust_domain not in TRUST_DOMAINS:
            # Fail closed: an unknown trust domain is never silently accepted.
            raise ValueError(
                f"unknown trust_domain '{trust_domain}' "
                f"(expected one of {sorted(TRUST_DOMAINS)})"
            )
        if not secret:
            raise ValueError(f"principal '{principal_id}' must have a non-empty secret")
        if not principal_id:
            raise ValueError("principal id must be non-empty")
        principal = Principal(id=principal_id, role=role, trust_domain=trust_domain)
        self._by_secret[secret] = principal
        return principal

    @classmethod
    def from_env(cls, var: str = "LEDGATO_PRINCIPALS") -> "PrincipalRegistry":
        raw = os.getenv(var, "").strip()
        entries: list[tuple] = []
        if raw:
            for chunk in raw.split(","):
                chunk = chunk.strip()
                if not chunk:
                    continue
                parts = chunk.split(":")
                # Backward compatible: three parts is the original
                # id:role:secret (operational). Four parts pins a trust domain
                # explicitly as id:role:trust_domain:secret.
                if len(parts) == 3:
                    entries.append((parts[0], parts[1], parts[2]))
                elif len(parts) == 4:
                    entries.append((parts[0], parts[1], parts[2], parts[3]))
                else:
                    raise ValueError(
                        f"malformed {var} entry '{chunk}' (expected "
                        "id:role:secret or id:role:trust_domain:secret)"
                    )
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
