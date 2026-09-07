"""First-class enforcement-boundary records.

A policy decision and a proven boundary are different facts. Ledgato could
previously only say "the gateway returned DENY"; it had no way to say "this
boundary has actually been tested for bypass resistance".

``EnforcementBoundary`` separates the two:

* a *decision* (ALLOW/DENY/APPROVE) is evidence that the gateway evaluated
  policy, and is recorded as such;
* ``bypass_status`` describes whether the boundary survived an attack suite.

Decisions never promote ``bypass_status``. Only an explicit verification claim
carrying evidence can, and ``BYPASS_FOUND`` latches until remediation evidence
is supplied.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional

from .models import utcnow

#: Ordered from weakest to strongest claim. ``BYPASS_FOUND`` is not on this
#: ladder — it is a latched failure state.
BYPASS_STATUSES: tuple[str, ...] = (
    "UNVERIFIED",
    "PARTIALLY_VERIFIED",
    "VERIFIED",
    "BYPASS_FOUND",
)

#: Evidence kinds that describe an adversarial attempt against the boundary.
#: Only these can support a move toward VERIFIED.
BYPASS_EVIDENCE_KINDS: frozenset[str] = frozenset(
    {"bypass_attempt", "leakage_attempt", "escalation_attempt", "approval_abuse_attempt"}
)

#: Evidence kinds produced by ordinary gateway operation. Recorded for audit,
#: but never sufficient to claim bypass resistance.
DECISION_EVIDENCE_KINDS: frozenset[str] = frozenset({"decision", "provider_readback"})


@dataclass
class BoundaryEvidence:
    """One recorded observation about a boundary."""

    kind: str
    summary: str
    outcome: str
    recorded_at: str = field(default_factory=lambda: utcnow().isoformat())
    protected_action_occurred: Optional[bool] = None
    ledger_entry_id: Optional[str] = None
    provider_ref: Optional[str] = None
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BoundaryEvidence":
        return cls(**data)


@dataclass
class EnforcementBoundary:
    """A protected provider action Ledgato claims to stand in front of."""

    id: str
    provider: str
    resource: str
    action: str
    gateway_credential_owner: str = "ledgato"
    failure_mode: str = "CLOSED"
    bypass_status: str = "UNVERIFIED"
    verification_evidence: list[BoundaryEvidence] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: utcnow().isoformat())
    notes: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["verification_evidence"] = [e.to_dict() for e in self.verification_evidence]
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EnforcementBoundary":
        copy = dict(data)
        copy["verification_evidence"] = [
            BoundaryEvidence.from_dict(e) for e in copy.get("verification_evidence", [])
        ]
        return cls(**copy)

    def bypass_attempts(self) -> list[BoundaryEvidence]:
        return [e for e in self.verification_evidence if e.kind in BYPASS_EVIDENCE_KINDS]

    def successful_bypasses(self) -> list[BoundaryEvidence]:
        """Attempts where the protected downstream action actually happened.

        This is the only signal that constitutes a security-boundary failure.
        A Ledgato-side error that left the action impossible is a reliability
        bug, not a bypass.
        """
        return [e for e in self.bypass_attempts() if e.protected_action_occurred is True]


class BoundaryStore:
    """File-backed registry of enforcement boundaries.

    File-backed state is MVP state (handoff gap #5): it is adequate for a single
    isolated lab, and is written atomically so a crash mid-write cannot truncate
    the registry. It is not safe for multi-writer production use.
    """

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else None
        self._boundaries: dict[str, EnforcementBoundary] = {}
        self._load()

    # -- persistence ---------------------------------------------------

    def _load(self) -> None:
        if not self.path or not self.path.exists():
            return
        raw = json.loads(self.path.read_text() or "{}")
        for bid, data in raw.items():
            self._boundaries[bid] = EnforcementBoundary.from_dict(data)

    def _save(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {bid: b.to_dict() for bid, b in self._boundaries.items()}
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True))
        tmp.replace(self.path)

    # -- registry ------------------------------------------------------

    def register(
        self,
        *,
        id: str,
        provider: str,
        resource: str,
        action: str,
        gateway_credential_owner: str = "ledgato",
        failure_mode: str = "CLOSED",
        notes: str | None = None,
    ) -> EnforcementBoundary:
        if id in self._boundaries:
            raise ValueError(f"boundary '{id}' already registered")
        boundary = EnforcementBoundary(
            id=id,
            provider=provider,
            resource=resource,
            action=action,
            gateway_credential_owner=gateway_credential_owner,
            failure_mode=failure_mode,
            notes=notes,
        )
        self._boundaries[id] = boundary
        self._save()
        return boundary

    def get(self, boundary_id: str) -> EnforcementBoundary:
        if boundary_id not in self._boundaries:
            raise KeyError(f"unknown boundary '{boundary_id}'")
        return self._boundaries[boundary_id]

    def list(self) -> list[EnforcementBoundary]:
        return list(self._boundaries.values())

    def find(self, *, provider: str, resource: str, action: str) -> EnforcementBoundary | None:
        for b in self._boundaries.values():
            if b.provider == provider and b.resource == resource and b.action == action:
                return b
        return None

    # -- evidence ------------------------------------------------------

    def record_evidence(
        self,
        boundary_id: str,
        *,
        kind: str,
        summary: str,
        outcome: str,
        protected_action_occurred: bool | None = None,
        ledger_entry_id: str | None = None,
        provider_ref: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> EnforcementBoundary:
        """Attach an observation to a boundary.

        Recording evidence never raises a boundary's status. A bypass attempt
        that reached the protected action latches ``BYPASS_FOUND`` immediately —
        that direction is automatic, because a demonstrated bypass is a fact,
        whereas absence of one is only ever an argument.
        """
        boundary = self.get(boundary_id)
        evidence = BoundaryEvidence(
            kind=kind,
            summary=summary,
            outcome=outcome,
            protected_action_occurred=protected_action_occurred,
            ledger_entry_id=ledger_entry_id,
            provider_ref=provider_ref,
            detail=detail or {},
        )
        boundary.verification_evidence.append(evidence)
        boundary.updated_at = utcnow().isoformat()

        if protected_action_occurred is True and kind in BYPASS_EVIDENCE_KINDS:
            boundary.bypass_status = "BYPASS_FOUND"

        self._save()
        return boundary

    def record_decision(
        self,
        boundary_id: str,
        *,
        status: str,
        executed: bool,
        ledger_entry_id: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> EnforcementBoundary:
        """Record an ALLOW/DENY/APPROVE decision as audit evidence only.

        This deliberately cannot change ``bypass_status``. A gateway that
        answered DENY has demonstrated that it evaluated policy, not that no
        other route to the action exists.
        """
        return self.record_evidence(
            boundary_id,
            kind="decision",
            summary=f"gateway decision {status}",
            outcome=status,
            protected_action_occurred=executed,
            ledger_entry_id=ledger_entry_id,
            detail=detail or {},
        )

    # -- status --------------------------------------------------------

    def set_status(
        self,
        boundary_id: str,
        status: str,
        *,
        attested_by: str,
        justification: str,
    ) -> EnforcementBoundary:
        """Explicitly claim a boundary status.

        Guardrails:

        * ``VERIFIED`` requires at least one recorded adversarial attempt, and
          is refused while any recorded attempt actually reached the protected
          action.
        * Leaving ``BYPASS_FOUND`` requires remediation evidence, so a latched
          failure cannot be cleared by re-asserting success.
        """
        if status not in BYPASS_STATUSES:
            raise ValueError(f"unknown bypass status '{status}' (expected one of {BYPASS_STATUSES})")
        if not attested_by or not justification:
            raise ValueError("status changes require attested_by and justification")

        boundary = self.get(boundary_id)

        if status == "VERIFIED":
            attempts = boundary.bypass_attempts()
            if not attempts:
                raise ValueError(
                    "cannot mark VERIFIED: no bypass/leakage/escalation attempts recorded. "
                    "Policy decisions alone are not bypass-resistance evidence."
                )
            breached = boundary.successful_bypasses()
            if breached:
                raise ValueError(
                    f"cannot mark VERIFIED: {len(breached)} recorded attempt(s) reached the "
                    "protected action; remediate and retest first"
                )

        if boundary.bypass_status == "BYPASS_FOUND" and status != "BYPASS_FOUND":
            remediated = [
                e for e in boundary.verification_evidence if e.kind == "remediation"
            ]
            if not remediated:
                raise ValueError(
                    "cannot leave BYPASS_FOUND without recorded remediation evidence"
                )

        boundary.bypass_status = status
        boundary.updated_at = utcnow().isoformat()
        boundary.verification_evidence.append(
            BoundaryEvidence(
                kind="status_change",
                summary=f"status set to {status} by {attested_by}",
                outcome=status,
                detail={"justification": justification},
            )
        )
        self._save()
        return boundary
