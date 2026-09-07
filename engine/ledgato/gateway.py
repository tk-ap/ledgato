"""Execution gateway: the boundary where Ledgato decisions become real.

The gateway owns protected adapter credentials and only invokes the downstream
system after ALLOW or a consumed approval. A DENY never calls ``execute``.
"""
from __future__ import annotations

from typing import Any

from .adapters.base import EnforcementAdapter, ExecutionReceipt
from .approvals import APPROVED, ApprovalStore
from .boundary import BoundaryStore
from .authority import AuthorityStore
from .engine import ALLOW, APPROVE, DENY, Decision, detect_drift, evaluate_action
from .idempotency import IdempotencyStore
from .ledger import Ledger
from .models import Action, AuthorityGrant, Policy


class EnforcementGateway:
    def __init__(
        self,
        *,
        policies: dict[str, Policy],
        adapters: dict[str, EnforcementAdapter],
        ledger: Ledger,
        authority: AuthorityStore | None = None,
        approvals: ApprovalStore | None = None,
        idempotency: IdempotencyStore | None = None,
        boundaries: BoundaryStore | None = None,
    ):
        self.policies = policies
        self.adapters = adapters
        self.ledger = ledger
        self.authority = authority or AuthorityStore()
        self.approvals = approvals or ApprovalStore()
        self.idempotency = idempotency or IdempotencyStore()
        #: Optional. When present, decisions are filed as boundary evidence.
        #: Boundaries are never auto-created — an unregistered target is simply
        #: not tracked, so this cannot drift into an asset inventory.
        self.boundaries = boundaries

    def discover(self, *, agent: str, adapter: str) -> dict[str, Any]:
        pol = self._policy(agent)
        target = self._adapter(adapter)
        observed = set(target.discover(agent))
        declared = _declared_for_adapter(pol, adapter, observed)
        drift = detect_drift(declared, observed, agent)
        evidence = {
            "adapter": adapter,
            "declared": sorted(declared),
            "observed": sorted(observed),
            "drift": drift,
        }
        self.ledger.append(agent, "DISCOVERED", evidence, action=f"discover:{adapter}")
        return evidence

    def execute(
        self,
        *,
        agent: str,
        adapter: str,
        action: Action,
        task_id: str | None = None,
        grant_id: str | None = None,
        requested_by: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        # Validate all deterministic local prerequisites before reserving the
        # operation key. Configuration mistakes must not poison a key as an
        # "uncertain execution" when no downstream action could have happened.
        pol = self._policy(agent)
        target = self._adapter(adapter)
        grant, decision = self._decide(
            policy=pol,
            action=action,
            task_id=task_id,
            grant_id=grant_id,
        )

        request_record = {
            "agent": agent,
            "adapter": adapter,
            "action": action.to_dict(),
            "task_id": task_id,
            "grant_id": grant_id,
            "requested_by": requested_by,
        }
        if idempotency_key:
            cached = self.idempotency.begin(idempotency_key, request_record)
            if cached is not None:
                return {**cached, "idempotent_replay": True}

        base_evidence = {
            "task_id": task_id,
            "adapter": adapter,
            "action": action.to_dict(),
            "decision": decision.to_dict(),
            "authority": grant.to_dict() if grant else None,
            "requested_by": requested_by,
            "idempotency_key": idempotency_key,
        }

        if decision.outcome == DENY:
            result = self._record_denial(
                agent=agent,
                target=target,
                action=action,
                decision=decision,
                evidence=base_evidence,
            )
            return self._complete_idempotent(idempotency_key, result)

        if decision.outcome == APPROVE:
            pending = self.approvals.request(
                agent=agent,
                task_id=task_id,
                adapter=adapter,
                action=action.to_dict(),
                grant_id=grant_id,
                requested_by=requested_by,
            )
            evidence = {
                **base_evidence,
                "approval_id": pending.id,
                "downstream_execute_called": False,
                "boundary_crossed": False,
            }
            entry = self.ledger.append(agent, APPROVE, evidence, action=action.tool)
            self._file_boundary_evidence(
                target=target, action=action, status=APPROVE, executed=False,
                ledger_entry_id=entry.id,
            )
            result = {
                "status": APPROVE,
                "executed": False,
                "paused": True,
                "approval": pending.to_dict(),
                "decision": decision.to_dict(),
                "attestation_id": entry.id,
            }
            return self._complete_idempotent(idempotency_key, result)

        result = self._execute_allowed(
            agent=agent,
            target=target,
            adapter=adapter,
            action=action,
            decision=decision,
            task_id=task_id,
            grant=grant,
            requested_by=requested_by,
            approval_id=None,
        )
        return self._complete_idempotent(idempotency_key, result)

    def approve(
        self,
        approval_id: str,
        *,
        decided_by: str,
        reason: str | None = None,
        jit_ttl_seconds: int | None = 300,
    ) -> dict[str, Any]:
        item = self.approvals.decide(
            approval_id, approved=True, decided_by=decided_by, reason=reason
        )
        jit = None
        if jit_ttl_seconds:
            action = Action(**item.action)
            jit = self.authority.issue(
                agent=item.agent,
                granted_by=decided_by,
                purpose=f"approval:{item.id}",
                tools={action.tool},
                data_domains=[action.domain] if action.domain else [],
                impact_max=action.impact,
                task_id=item.task_id,
                parent_grant_id=item.grant_id,
                ttl_seconds=jit_ttl_seconds,
            )
            self.approvals.attach_jit_grant(item.id, jit.id)
            item = self.approvals.get(item.id) or item
        evidence = {
            "approval": item.to_dict(),
            "jit_grant": jit.to_dict() if jit else None,
        }
        self.ledger.append(item.agent, "APPROVED", evidence, action=item.action.get("tool", "approval"))
        return {
            "approval": item.to_dict(include_resume_token=True),
            "jit_grant": jit.to_dict() if jit else None,
        }

    def deny_approval(self, approval_id: str, *, decided_by: str, reason: str | None = None) -> dict[str, Any]:
        item = self.approvals.decide(
            approval_id, approved=False, decided_by=decided_by, reason=reason
        )
        evidence = {"approval": item.to_dict(), "boundary_crossed": False}
        self.ledger.append(item.agent, DENY, evidence, action=item.action.get("tool", "approval"))
        return item.to_dict()

    def resume(self, approval_id: str, *, resume_token: str) -> dict[str, Any]:
        item = self.approvals.get(approval_id)
        if not item:
            raise KeyError(approval_id)
        if item.status != APPROVED:
            raise ValueError(f"approval is {item.status}, not APPROVED")

        consumed = self.approvals.consume(approval_id, resume_token)
        action = Action(**consumed.action)
        pol = self._policy(consumed.agent)
        target = self._adapter(consumed.adapter)
        effective_grant_id = consumed.jit_grant_id or consumed.grant_id
        grant, decision = self._decide(
            policy=pol,
            action=action,
            task_id=consumed.task_id,
            grant_id=effective_grant_id,
            approval_satisfied=True,
        )
        if decision.outcome != ALLOW:
            return self._record_denial(
                agent=consumed.agent,
                target=target,
                action=action,
                decision=decision,
                evidence={"approval_id": consumed.id, "authority": grant.to_dict() if grant else None},
            )
        return self._execute_allowed(
            agent=consumed.agent,
            target=target,
            adapter=consumed.adapter,
            action=action,
            decision=decision,
            task_id=consumed.task_id,
            grant=grant,
            requested_by=consumed.requested_by,
            approval_id=consumed.id,
        )

    def _decide(
        self,
        *,
        policy: Policy,
        action: Action,
        task_id: str | None,
        grant_id: str | None,
        approval_satisfied: bool = False,
    ) -> tuple[AuthorityGrant | None, Decision]:
        grant = None
        if grant_id:
            grant = self.authority.get(grant_id)
            if not grant:
                raise KeyError(f"unknown authority grant '{grant_id}'")
            valid, reason = self.authority.validate(grant_id)
            if not valid:
                denial_reason = reason or "authority grant is not effective"
                return grant, Decision(
                    allow=False,
                    outcome=DENY,
                    reason=f"DENY: {denial_reason}",
                    reasons=[denial_reason],
                    policy=policy.agent,
                    on_deny=list(policy.on_deny),
                    grant_id=grant.id,
                )
        decision = evaluate_action(
            policy,
            action,
            grant=grant,
            task_id=task_id,
            approval_satisfied=approval_satisfied,
        )
        return grant, decision

    def _file_boundary_evidence(
        self,
        *,
        target: EnforcementAdapter,
        action: Action,
        status: str,
        executed: bool,
        ledger_entry_id: str | None,
        verification: dict[str, Any] | None = None,
    ) -> None:
        """Record a decision against a registered EnforcementBoundary.

        Deliberately does nothing unless a boundary was explicitly registered
        for this provider/resource/action. ``record_decision`` cannot change
        ``bypass_status``: answering DENY shows the gateway evaluated policy,
        not that no other route to the action exists.

        A provider readback is filed separately, and only for adapters that
        declare ``is_live_provider``. Without that guard an in-process test
        double would emit the very evidence the VERIFIED gate demands.
        """
        if self.boundaries is None:
            return
        resource = getattr(target, "boundary_resource", None)
        if not resource:
            return
        boundary = self.boundaries.find(
            provider=target.name, resource=resource, action=action.tool
        )
        if boundary is None:
            return

        self.boundaries.record_decision(
            boundary.id,
            status=status,
            executed=executed,
            ledger_entry_id=ledger_entry_id,
            detail={"action": action.to_dict()},
        )

        if verification is not None and getattr(target, "is_live_provider", False):
            self.boundaries.record_evidence(
                boundary.id,
                kind="provider_readback",
                summary=f"provider readback after {status}",
                outcome="verified" if verification.get("verified") else "unverified",
                protected_action_occurred=executed,
                ledger_entry_id=ledger_entry_id,
                detail=verification,
            )

    def _record_denial(
        self,
        *,
        agent: str,
        target: EnforcementAdapter,
        action: Action,
        decision: Decision,
        evidence: dict[str, Any],
    ) -> dict[str, Any]:
        denial_verification = target.verify_denied(action)
        final_evidence = {
            **evidence,
            "decision": decision.to_dict(),
            "downstream_execute_called": False,
            "boundary_crossed": False,
            "verification": denial_verification,
        }
        entry = self.ledger.append(agent, DENY, final_evidence, action=action.tool)
        self._file_boundary_evidence(
            target=target, action=action, status=DENY, executed=False,
            ledger_entry_id=entry.id, verification=denial_verification,
        )
        return {
            "status": DENY,
            "executed": False,
            "boundary_crossed": False,
            "decision": decision.to_dict(),
            "verification": denial_verification,
            "attestation_id": entry.id,
        }

    def _execute_allowed(
        self,
        *,
        agent: str,
        target: EnforcementAdapter,
        adapter: str,
        action: Action,
        decision: Decision,
        task_id: str | None,
        grant: AuthorityGrant | None,
        requested_by: str | None,
        approval_id: str | None,
    ) -> dict[str, Any]:
        receipt: ExecutionReceipt = target.execute(action)
        verification = target.verify(action, receipt)
        receipt.verification = verification
        evidence = {
            "task_id": task_id,
            "adapter": adapter,
            "action": action.to_dict(),
            "decision": decision.to_dict(),
            "authority": grant.to_dict() if grant else None,
            "requested_by": requested_by,
            "approval_id": approval_id,
            "downstream_execute_called": True,
            "boundary_crossed": bool(receipt.executed),
            "receipt": receipt.to_dict(),
            "verification": verification,
        }
        entry = self.ledger.append(agent, ALLOW, evidence, action=action.tool)
        self._file_boundary_evidence(
            target=target, action=action, status=ALLOW, executed=bool(receipt.executed),
            ledger_entry_id=entry.id, verification=verification,
        )
        return {
            "status": ALLOW,
            "executed": receipt.executed,
            "boundary_crossed": bool(receipt.executed),
            "decision": decision.to_dict(),
            "receipt": receipt.to_dict(),
            "verification": verification,
            "attestation_id": entry.id,
        }

    def _complete_idempotent(
        self, idempotency_key: str | None, result: dict[str, Any]
    ) -> dict[str, Any]:
        if not idempotency_key:
            return result
        normalized = {
            **result,
            "idempotency_key": idempotency_key,
            "idempotent_replay": False,
        }
        return self.idempotency.complete(idempotency_key, normalized)

    def _policy(self, agent: str) -> Policy:
        pol = self.policies.get(agent)
        if not pol:
            raise KeyError(f"no policy for agent '{agent}'")
        return pol

    def _adapter(self, name: str) -> EnforcementAdapter:
        adapter = self.adapters.get(name)
        if not adapter:
            raise KeyError(f"no adapter named '{name}'")
        return adapter


def _declared_for_adapter(policy: Policy, adapter: str, observed: set[str]) -> set[str]:
    prefixed = {t for t in policy.allow_tools if t.startswith(adapter + ".")}
    if prefixed:
        return prefixed
    return set(policy.allow_tools) & observed
