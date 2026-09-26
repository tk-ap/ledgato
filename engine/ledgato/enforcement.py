"""Mandatory consequential-action checkpoint: contract → decision → permit.

The gateway in ``gateway.py`` enforces only when every caller routes through it.
This module closes the remaining gap for one narrow boundary: the protected
resource will not act unless it is shown a Ledgato permit, and only Ledgato can
mint one.

    AgentOS (executes)  ──contract──▶  Ledgato (decides, signs, records)
          │                                   │
          │◀──── decision (+ permit on ALLOW) ┘
          ▼
    ProtectedResource (holds the capability; verifies the permit)

* A permit is issued **only** on ALLOW. DENY and APPROVAL_REQUIRED never carry
  one, so there is nothing a caller could present to the resource.
* A permit is Ed25519-signed by the Ledgato identity and bound to the digest of
  the exact contract, the ledger entry that recorded the decision, and a short
  expiry. The resource pins Ledgato's public key; AgentOS never holds the
  private key, so it cannot forge, widen, or re-target a permit.
* Decisions and outcomes are persisted (``DecisionStore``) and written to the
  signed hash-chained ledger, so the evidence survives a process restart.

IAM identifies the caller, AgentOS executes, Ledgato is the checkpoint. This
module grants nothing on its own: the policy for the authenticated agent still
decides, via ``engine.evaluate_action``.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Optional

from .crypto import Signer
from .engine import ALLOW, APPROVE, DENY, evaluate_action
from .ledger import Ledger
from .models import IMPACTS, Action, Policy

CONTRACT_VERSION = "ledgato.action-contract/v1"
PERMIT_VERSION = "ledgato.permit/v1"

#: Outcomes as they appear on the contract boundary. APPROVE from the policy
#: engine is surfaced as APPROVAL_REQUIRED: it is a stop, not a soft allow.
OUTCOME_ALLOW = "ALLOW"
OUTCOME_DENY = "DENY"
OUTCOME_APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
OUTCOMES = frozenset({OUTCOME_ALLOW, OUTCOME_DENY, OUTCOME_APPROVAL_REQUIRED})

_ENGINE_TO_CONTRACT = {
    ALLOW: OUTCOME_ALLOW,
    DENY: OUTCOME_DENY,
    APPROVE: OUTCOME_APPROVAL_REQUIRED,
}

DEFAULT_PERMIT_TTL_SECONDS = 120


class ContractError(ValueError):
    """The action contract is malformed. No decision can be made from it."""


def canonical(data: Any) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":")).encode()


def digest(data: Any) -> str:
    return hashlib.sha256(canonical(data)).hexdigest()


def policy_digest(policy: Policy) -> str:
    return digest(policy.to_dict())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _require_str(data: Mapping[str, Any], key: str, where: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{where}.{key} must be a non-empty string")
    return value


def _reject_unknown(data: Mapping[str, Any], allowed: set[str], where: str) -> None:
    extra = sorted(set(data) - allowed)
    if extra:
        raise ContractError(f"{where} has unknown fields: {extra}")


# ---------------------------------------------------------------------------
# Action contract
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ActionContract:
    """One consequential action AgentOS asks to perform.

    Everything that determines whether and what may execute is in here, and the
    permit is bound to ``digest()`` of all of it — changing any field after the
    decision invalidates the permit.
    """

    work_id: str
    agent_id: str
    agent_identity: str
    action: str
    impact: str
    resource: str
    policy_id: str
    params: dict[str, Any] = field(default_factory=dict)
    policy_digest: Optional[str] = None
    evidence: tuple[dict[str, Any], ...] = ()

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ActionContract":
        if not isinstance(data, Mapping):
            raise ContractError("contract must be an object")
        _reject_unknown(
            data,
            {"version", "work_id", "agent", "requested_action", "resource", "policy", "evidence"},
            "contract",
        )
        if data.get("version") != CONTRACT_VERSION:
            raise ContractError(f"contract.version must be '{CONTRACT_VERSION}'")

        agent = data.get("agent")
        requested = data.get("requested_action")
        policy = data.get("policy")
        for name, value in (("agent", agent), ("requested_action", requested), ("policy", policy)):
            if not isinstance(value, Mapping):
                raise ContractError(f"contract.{name} must be an object")
        _reject_unknown(agent, {"id", "identity"}, "contract.agent")
        _reject_unknown(requested, {"name", "impact", "params"}, "contract.requested_action")
        _reject_unknown(policy, {"id", "digest"}, "contract.policy")

        impact = _require_str(requested, "impact", "contract.requested_action")
        if impact not in IMPACTS:
            raise ContractError(
                f"contract.requested_action.impact must be one of {sorted(IMPACTS)}"
            )
        params = requested.get("params", {})
        if not isinstance(params, Mapping):
            raise ContractError("contract.requested_action.params must be an object")
        pdigest = policy.get("digest")
        if pdigest is not None and not isinstance(pdigest, str):
            raise ContractError("contract.policy.digest must be a string")

        evidence = data.get("evidence", [])
        if not isinstance(evidence, list):
            raise ContractError("contract.evidence must be a list")
        for i, item in enumerate(evidence):
            if not isinstance(item, Mapping):
                raise ContractError(f"contract.evidence[{i}] must be an object")
            _require_str(item, "kind", f"contract.evidence[{i}]")
            _require_str(item, "ref", f"contract.evidence[{i}]")

        return cls(
            work_id=_require_str(data, "work_id", "contract"),
            agent_id=_require_str(agent, "id", "contract.agent"),
            agent_identity=_require_str(agent, "identity", "contract.agent"),
            action=_require_str(requested, "name", "contract.requested_action"),
            impact=impact,
            resource=_require_str(data, "resource", "contract"),
            policy_id=_require_str(policy, "id", "contract.policy"),
            params=dict(params),
            policy_digest=pdigest,
            evidence=tuple(dict(item) for item in evidence),
        )

    def to_dict(self) -> dict[str, Any]:
        policy: dict[str, Any] = {"id": self.policy_id}
        if self.policy_digest is not None:
            policy["digest"] = self.policy_digest
        return {
            "version": CONTRACT_VERSION,
            "work_id": self.work_id,
            "agent": {"id": self.agent_id, "identity": self.agent_identity},
            "requested_action": {
                "name": self.action,
                "impact": self.impact,
                "params": dict(self.params),
            },
            "resource": self.resource,
            "policy": policy,
            "evidence": [dict(item) for item in self.evidence],
        }

    def digest(self) -> str:
        return digest(self.to_dict())

    def to_action(self) -> Action:
        return Action(
            tool=self.action,
            params=dict(self.params),
            domain=self.resource,
            impact=self.impact,
            intent=f"work:{self.work_id}",
        )


# ---------------------------------------------------------------------------
# Permits
# ---------------------------------------------------------------------------
_PERMIT_FIELDS = (
    "version",
    "permit_id",
    "decision_id",
    "contract_digest",
    "work_id",
    "agent_id",
    "action",
    "resource",
    "ledger_entry_id",
    "ledger_entry_hash",
    "issued_at",
    "expires_at",
    "issuer_public_key",
)


def sign_permit(signer: Signer, body: dict[str, Any]) -> dict[str, Any]:
    unsigned = {k: body[k] for k in _PERMIT_FIELDS}
    return {**unsigned, "signature": signer.sign(canonical(unsigned))}


def verify_permit(
    permit: Any,
    *,
    contract: ActionContract,
    trusted_keys: set[str],
    resource: str,
    now: datetime | None = None,
) -> Optional[str]:
    """Return None if ``permit`` authorizes exactly ``contract`` here, else why not.

    Fails closed on anything unexpected: a missing field is a rejection, not a
    default.
    """
    if not isinstance(permit, Mapping):
        return "no Ledgato permit presented"
    missing = [k for k in (*_PERMIT_FIELDS, "signature") if not isinstance(permit.get(k), str)]
    if missing:
        return f"permit is missing fields: {missing}"
    if set(permit) - {*_PERMIT_FIELDS, "signature"}:
        return "permit has unknown fields"
    if permit["version"] != PERMIT_VERSION:
        return "unsupported permit version"
    key = permit["issuer_public_key"]
    if key not in trusted_keys:
        return "permit issuer is not a trusted Ledgato key"
    unsigned = {k: permit[k] for k in _PERMIT_FIELDS}
    if not Signer.verify(key, canonical(unsigned), permit["signature"]):
        return "permit signature is invalid"
    if permit["contract_digest"] != contract.digest():
        return "permit was issued for a different contract"
    if (permit["work_id"], permit["agent_id"], permit["action"]) != (
        contract.work_id, contract.agent_id, contract.action
    ):
        return "permit fields do not match the contract"
    if permit["resource"] != resource or contract.resource != resource:
        return f"permit is not valid for resource '{resource}'"
    try:
        expires = datetime.fromisoformat(permit["expires_at"])
    except ValueError:
        return "permit expiry is unreadable"
    if (now or _utcnow()) >= expires:
        return "permit has expired"
    return None


# ---------------------------------------------------------------------------
# Durable state
# ---------------------------------------------------------------------------
def atomic_write_json(path: Path, data: Any) -> None:
    """Write JSON so a crash leaves either the old or the new file, never half."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, sort_keys=True)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


class DecisionStore:
    """Decision records keyed by decision_id, persisted to one JSON file."""

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else None
        self._lock = threading.Lock()
        self._records: dict[str, dict[str, Any]] = {}
        if self.path and self.path.exists():
            self._records = json.loads(self.path.read_text(encoding="utf-8"))

    def put(self, record: dict[str, Any]) -> None:
        with self._lock:
            self._records[record["decision_id"]] = record
            self._flush()

    def get(self, decision_id: str) -> Optional[dict[str, Any]]:
        with self._lock:
            record = self._records.get(decision_id)
            return json.loads(json.dumps(record)) if record else None

    def attach_outcome(self, decision_id: str, outcome: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            record = self._records.get(decision_id)
            if record is None:
                raise KeyError(decision_id)
            if record.get("outcome_report") is not None:
                raise ValueError(f"outcome already recorded for decision '{decision_id}'")
            record["outcome_report"] = outcome
            self._flush()
            return json.loads(json.dumps(record))

    def for_work(self, work_id: str) -> list[dict[str, Any]]:
        with self._lock:
            return [
                json.loads(json.dumps(r))
                for r in self._records.values()
                if r.get("work_id") == work_id
            ]

    def _flush(self) -> None:
        if self.path:
            atomic_write_json(self.path, self._records)


# ---------------------------------------------------------------------------
# The checkpoint
# ---------------------------------------------------------------------------
class EnforcementPoint:
    """Ledgato's side of the boundary: decide, sign, record, prove."""

    def __init__(
        self,
        *,
        policies: dict[str, Policy],
        ledger: Ledger,
        signer: Signer,
        store: DecisionStore,
        permit_ttl_seconds: int = DEFAULT_PERMIT_TTL_SECONDS,
    ):
        self.policies = policies
        self.ledger = ledger
        self.signer = signer
        self.store = store
        self.permit_ttl_seconds = int(permit_ttl_seconds)
        self._lock = threading.Lock()

    def public_key(self) -> str:
        return self.signer.public_key_b64()

    def decide(self, contract: ActionContract, *, principal_id: str) -> dict[str, Any]:
        """Decide one contract. Only an ALLOW carries a permit."""
        policy = self.policies.get(contract.agent_id)
        reasons: list[str] = []
        applied_digest = policy_digest(policy) if policy else None

        if policy is None:
            outcome = OUTCOME_DENY
            reasons.append(f"no policy for agent '{contract.agent_id}' (fail closed)")
        elif contract.policy_id != policy.agent:
            outcome = OUTCOME_DENY
            reasons.append(
                f"contract names policy '{contract.policy_id}' but agent "
                f"'{contract.agent_id}' is governed by '{policy.agent}'"
            )
        elif contract.policy_digest is not None and contract.policy_digest != applied_digest:
            outcome = OUTCOME_DENY
            reasons.append("contract was prepared against a different policy version")
        else:
            decision = evaluate_action(policy, contract.to_action(), task_id=contract.work_id)
            outcome = _ENGINE_TO_CONTRACT[decision.outcome]
            reasons.extend(decision.reasons)

        decision_id = uuid.uuid4().hex
        contract_digest = contract.digest()
        issued = _utcnow()
        permit_id = uuid.uuid4().hex if outcome == OUTCOME_ALLOW else None
        expires = issued + timedelta(seconds=self.permit_ttl_seconds) if permit_id else None

        evidence = {
            "kind": "enforcement.decision",
            "decision_id": decision_id,
            "work_id": contract.work_id,
            "principal": principal_id,
            "contract": contract.to_dict(),
            "contract_digest": contract_digest,
            "policy_applied": policy.agent if policy else None,
            "policy_digest": applied_digest,
            "outcome": outcome,
            "reasons": reasons,
            "permit_id": permit_id,
            "permit_expires_at": expires.isoformat() if expires else None,
            "boundary_crossed": False,
        }
        # Ledger append and store write are serialized so a decision can never
        # be visible in one and absent from the other within this process.
        with self._lock:
            entry = self.ledger.append(contract.agent_id, outcome, evidence, action=contract.action)
            permit = None
            if permit_id:
                permit = sign_permit(
                    self.signer,
                    {
                        "version": PERMIT_VERSION,
                        "permit_id": permit_id,
                        "decision_id": decision_id,
                        "contract_digest": contract_digest,
                        "work_id": contract.work_id,
                        "agent_id": contract.agent_id,
                        "action": contract.action,
                        "resource": contract.resource,
                        "ledger_entry_id": entry.id,
                        "ledger_entry_hash": entry.hash,
                        "issued_at": issued.isoformat(),
                        "expires_at": expires.isoformat(),
                        "issuer_public_key": self.public_key(),
                    },
                )
            record = {
                "decision_id": decision_id,
                "work_id": contract.work_id,
                "agent_id": contract.agent_id,
                "outcome": outcome,
                "reasons": reasons,
                "contract_digest": contract_digest,
                "permit_id": permit_id,
                "decided_at": issued.isoformat(),
                "decision_entry": {"id": entry.id, "index": entry.index, "hash": entry.hash},
                "outcome_report": None,
            }
            self.store.put(record)

        return {
            "decision_id": decision_id,
            "work_id": contract.work_id,
            "outcome": outcome,
            "reasons": reasons,
            "contract_digest": contract_digest,
            "ledger_entry_id": entry.id,
            "ledger_entry_hash": entry.hash,
            "permit": permit,
        }

    def record_outcome(
        self, decision_id: str, report: Mapping[str, Any], *, principal_id: str
    ) -> dict[str, Any]:
        """Append what actually happened after the decision.

        ``consistent`` is False when the report claims execution without an
        ALLOW — that is recorded, not hidden, so the ledger shows the anomaly.
        """
        record = self.store.get(decision_id)
        if record is None:
            raise KeyError(f"unknown decision '{decision_id}'")
        if record["agent_id"] != principal_id:
            raise PermissionError(
                f"principal '{principal_id}' may not report the outcome of "
                f"'{record['agent_id']}'s decision"
            )
        if record.get("outcome_report") is not None:
            raise ValueError(f"outcome already recorded for decision '{decision_id}'")

        executed = bool(report.get("executed"))
        consistent = (not executed) or record["outcome"] == OUTCOME_ALLOW
        evidence = {
            "kind": "enforcement.outcome",
            "decision_id": decision_id,
            "work_id": record["work_id"],
            "decision_entry_hash": record["decision_entry"]["hash"],
            "decision_outcome": record["outcome"],
            "reported_by": principal_id,
            "executed": executed,
            "boundary_crossed": executed,
            "consistent": consistent,
            "status": report.get("status"),
            "receipt": report.get("receipt"),
        }
        with self._lock:
            entry = self.ledger.append(
                record["agent_id"], "OUTCOME", evidence,
                action=f"outcome:{record['decision_id']}",
            )
            outcome = {
                "executed": executed,
                "consistent": consistent,
                "status": report.get("status"),
                "receipt": report.get("receipt"),
                "entry": {"id": entry.id, "index": entry.index, "hash": entry.hash},
            }
            return self.store.attach_outcome(decision_id, outcome)

    def evidence(self, decision_id: str) -> dict[str, Any]:
        """Everything needed to prove what was decided and what happened.

        Recomputed from the persisted ledger and decision store, so it holds
        across restarts and does not trust any in-memory state.
        """
        record = self.store.get(decision_id)
        if record is None:
            raise KeyError(f"unknown decision '{decision_id}'")
        by_hash = {e.hash: e for e in self.ledger.entries}
        decision_entry = by_hash.get(record["decision_entry"]["hash"])
        report = record.get("outcome_report")
        outcome_entry = by_hash.get(report["entry"]["hash"]) if report else None

        chain_ok, chain_errors = self.ledger.verify_chain()
        problems: list[str] = list(chain_errors)
        if decision_entry is None:
            problems.append("decision entry is missing from the ledger")
        else:
            ev = decision_entry.evidence
            if ev.get("decision_id") != decision_id or ev.get("outcome") != record["outcome"]:
                problems.append("decision entry does not match the decision record")
            if digest(ev.get("contract")) != record["contract_digest"]:
                problems.append("recorded contract does not match its digest")
        if report is not None:
            if outcome_entry is None:
                problems.append("outcome entry is missing from the ledger")
            elif outcome_entry.evidence.get("decision_entry_hash") != record["decision_entry"]["hash"]:
                problems.append("outcome entry does not reference the decision entry")

        return {
            "decision_id": decision_id,
            "work_id": record["work_id"],
            "outcome": record["outcome"],
            "executed": bool(report and report["executed"]),
            "consistent": bool(report["consistent"]) if report else None,
            "record": record,
            "decision_entry": decision_entry.to_dict() if decision_entry else None,
            "outcome_entry": outcome_entry.to_dict() if outcome_entry else None,
            "chain_valid": chain_ok,
            "verified": not problems,
            "problems": problems,
        }
