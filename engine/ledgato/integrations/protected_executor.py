"""AgentOS-side protected executor: ask Ledgato, then act only on ALLOW.

AgentOS executes; Ledgato decides. This adapter is the only path AgentOS uses
to reach a protected resource, and it is deliberately unable to act on its own
say-so: the resource demands a Ledgato-signed permit, which only an ALLOW
decision carries.

Outcomes:

* ``EXECUTED``          — ALLOW, permit accepted, resource acted once.
* ``DENIED``            — DENY; resource never called.
* ``APPROVAL_REQUIRED`` — paused for a human; resource never called.
* ``FAILED_CLOSED``     — no valid decision (Ledgato unreachable, malformed or
  mismatched response, ALLOW without a usable permit) or the resource refused
  the permit. Nothing was executed on our side.

The executor reports every outcome back to Ledgato so the ledger holds both the
decision and what actually happened.
"""
from __future__ import annotations

from typing import Any, Mapping, Protocol

from ..enforcement import (
    OUTCOME_ALLOW,
    OUTCOME_APPROVAL_REQUIRED,
    OUTCOME_DENY,
    OUTCOMES,
    ActionContract,
)
from ..protected_resource import PermitRejected

EXECUTED = "EXECUTED"
DENIED = "DENIED"
APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
FAILED_CLOSED = "FAILED_CLOSED"


class DecisionClient(Protocol):
    def decide(self, contract: dict[str, Any]) -> dict[str, Any]: ...
    def record_outcome(self, decision_id: str, report: dict[str, Any]) -> dict[str, Any]: ...


class Resource(Protocol):
    def perform(self, contract: Any, permit: Any) -> dict[str, Any]: ...


class ProtectedExecutor:
    def __init__(self, ledgato: DecisionClient, resource: Resource):
        self.ledgato = ledgato
        self.resource = resource

    def run(self, contract: ActionContract) -> dict[str, Any]:
        expected_digest = contract.digest()
        try:
            decision = self.ledgato.decide(contract.to_dict())
        except Exception as exc:  # unreachable, auth failure, 4xx/5xx, bad JSON
            return _result(FAILED_CLOSED, f"no Ledgato decision: {exc}")

        problem = _invalid_decision(decision, expected_digest)
        if problem:
            return _result(FAILED_CLOSED, problem, decision=decision)

        decision_id = decision["decision_id"]
        outcome = decision["outcome"]

        if outcome == OUTCOME_DENY:
            return self._finish(DENIED, "Ledgato denied the action", decision)
        if outcome == OUTCOME_APPROVAL_REQUIRED:
            return self._finish(APPROVAL_REQUIRED, "Ledgato requires approval", decision)

        permit = decision.get("permit")
        if not isinstance(permit, Mapping) or permit.get("decision_id") != decision_id \
                or permit.get("contract_digest") != expected_digest:
            return self._finish(FAILED_CLOSED, "ALLOW without a matching permit", decision)

        try:
            receipt = self.resource.perform(contract, dict(permit))
        except PermitRejected as exc:
            return self._finish(FAILED_CLOSED, f"resource refused the permit: {exc.reason}", decision)
        except Exception as exc:
            # The resource burns the permit before acting, so this is at most
            # one attempt. Its outcome is unknown and is reported as such.
            return self._finish(
                FAILED_CLOSED, f"resource error: {exc}", decision, executed=None
            )
        return self._finish(
            EXECUTED, "executed on Ledgato ALLOW", decision, receipt=receipt, executed=True
        )

    def _finish(
        self,
        status: str,
        reason: str,
        decision: dict[str, Any],
        *,
        receipt: dict[str, Any] | None = None,
        executed: bool | None = False,
    ) -> dict[str, Any]:
        # executed: True = acted, False = did not act, None = outcome unknown.
        report = {"status": status, "executed": executed is True, "receipt": receipt}
        if executed is None:
            report["receipt"] = {"unknown": True, "reason": reason}
        recorded: dict[str, Any] | None = None
        record_error = None
        try:
            recorded = self.ledgato.record_outcome(decision["decision_id"], report)
        except Exception as exc:
            record_error = str(exc)
        out = _result(status, reason, decision=decision, receipt=receipt, executed=executed)
        out["outcome_recorded"] = recorded is not None
        if record_error:
            out["outcome_record_error"] = record_error
        return out


def _invalid_decision(decision: Any, expected_digest: str) -> str | None:
    if not isinstance(decision, Mapping):
        return "Ledgato response is not a decision"
    if not isinstance(decision.get("decision_id"), str) or not decision["decision_id"]:
        return "Ledgato decision has no decision_id"
    if decision.get("outcome") not in OUTCOMES:
        return f"unrecognised Ledgato outcome {decision.get('outcome')!r}"
    if decision.get("contract_digest") != expected_digest:
        return "Ledgato decided a different contract than the one submitted"
    if decision["outcome"] != OUTCOME_ALLOW and decision.get("permit"):
        return "Ledgato returned a permit on a non-ALLOW decision"
    return None


def _result(
    status: str,
    reason: str,
    *,
    decision: Any = None,
    receipt: dict[str, Any] | None = None,
    executed: bool | None = False,
) -> dict[str, Any]:
    decision = decision if isinstance(decision, Mapping) else {}
    return {
        "status": status,
        "executed": executed,
        "reason": reason,
        "decision_id": decision.get("decision_id"),
        "decision": decision.get("outcome"),
        "ledger_entry_hash": decision.get("ledger_entry_hash"),
        "receipt": receipt,
    }
