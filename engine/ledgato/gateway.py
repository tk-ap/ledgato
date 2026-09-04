"""Execution gateway: the boundary where Ledgato decisions become real.

The gateway is intentionally separate from the decision engine. It owns the
protected adapter credential and only invokes the downstream system after an
ALLOW decision or a consumed approval. A DENY never calls ``execute``.
"""
from __future__ import annotations

from typing import Any

from .adapters.base import EnforcementAdapter, ExecutionReceipt
from .approvals import APPROVED, ApprovalStore
from .authority import AuthorityStore
from .engine import ALLOW, APPROVE, DENY, Decision, detect_drift, evaluate_action
from .ledger import Ledger
from .models import Action, Policy


class EnforcementGateway:
    def __init__(
        self,
        *,
        policies: dict[str, Policy],
        adapters: dict[str, EnforcementAdapter],
        ledger: Ledger,
        authority: AuthorityStore | None = None,
        approvals: ApprovalStore | None = None,
    ):
        self.policies = policies
        self.adapters = adapters
        self.ledger = ledger
        self.authority = authority or AuthorityStore()
        self.approvals = approvals or ApprovalStore()

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
    ) -> dict[str, Any]:
        pol = self._policy(agent)
        target = self._adapter(adapter)
        grant = self.authority.get(grant_id)
        decision = evaluate_action(pol, action, grant=grant, task_id=task_id)

        base_evidence = {
            "task_id": task_id,
            "adapter": adapter,
            "action": action.to_dict(),
            "decision": decision.to_dict(),
            "authority": grant.to_dict() if grant else None,
            "requested_by": requested_by,
        }

        if decision.outcome == DENY:
            denial_verification = target.verify_denied(action)
            evidence = {
                **base_evidence,
                "downstream_execute_called": False,
                "boundary_crossed": False,
                "verification": denial_verification,
            }
            entry = self.ledger.append(agent, DENY, evidence, action=action.tool)
            return {
                "status": DENY,
                "executed": False,
                "boundary_crossed": False,
                "decision": decision.to_dict(),
                "verification": denial_verification,
                "attestation_id": entry.id,
            }

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
            return {
                "status": APPROVE,
                "executed": False,
                "paused": True,
                "approval": pending.to_dict(),
                "decision": decision.to_dict(),
                "attestation_id": entry.id,
            }

        return self._execute_allowed(
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
        grant = self.authority.get(consumed.jit_grant_id or consumed.grant_id)
        decision = evaluate_action(
            pol,
            action,
            grant=grant,
            task_id=consumed.task_id,
            approval_satisfied=True,
        )
        if decision.outcome != ALLOW:
            verification = target.verify_denied(action)
            evidence = {
                "approval_id": consumed.id,
                "decision": decision.to_dict(),
                "downstream_execute_called": False,
                "boundary_crossed": False,
                "verification": verification,
            }
            entry = self.ledger.append(consumed.agent, DENY, evidence, action=action.tool)
            return {
                "status": DENY,
                "executed": False,
                "decision": decision.to_dict(),
                "verification": verification,
                "attestation_id": entry.id,
            }
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

    def _execute_allowed(
        self,
        *,
        agent: str,
        target: EnforcementAdapter,
        adapter: str,
        action: Action,
        decision: Decision,
        task_id: str | None,
        grant: Any,
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
        return {
            "status": ALLOW,
            "executed": receipt.executed,
            "boundary_crossed": bool(receipt.executed),
            "decision": decision.to_dict(),
            "receipt": receipt.to_dict(),
            "verification": verification,
            "attestation_id": entry.id,
        }

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
    # For generic adapters without a namespace, only compare capabilities that
    # the adapter itself can expose; this avoids false drift from other surfaces.
    return set(policy.allow_tools) & observed
