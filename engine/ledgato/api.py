"""Ledgato HTTP API.

The API exposes the legacy policy/release-assurance endpoints plus the real
execution gateway: discovery, delegated/JIT grants, approval pause/resume, and
post-action verification through registered native adapters.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Optional
import uuid

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from . import attestation as attest_ops
from .adapters.base import EnforcementAdapter
from .adapters.github import GitHubAdapter
from .approvals import ApprovalStore
from .principals import (
    IdentityClaimError,
    Principal,
    PrincipalRegistry,
    enforce_claim,
)
from .authority import AuthorityStore
from .campaign import (
    CampaignAuthorityStore,
    CampaignError,
    authorize_campaign_action,
    build_authority,
)
from .crypto import Signer
from .distributed import Node
from .engine import DENY, Decision, evaluate_action
from .gate import attest_release
from .gateway import EnforcementGateway
from .idempotency import IdempotencyStore
from .ledger import Ledger
from .models import Action, Policy, load_policies
from .probes import run_probes, summarize


class ActionIn(BaseModel):
    tool: str
    params: dict[str, Any] = Field(default_factory=dict)
    domain: Optional[str] = None
    impact: str = "readonly"
    intent: Optional[str] = None


class CheckRequest(BaseModel):
    agent: str
    action: ActionIn
    task_id: Optional[str] = None
    grant_id: Optional[str] = None


class ProbeRequest(BaseModel):
    agent: str


class AttestRequest(BaseModel):
    agent: str
    release: str
    actions: list[ActionIn] = Field(default_factory=list)
    observed_scope: Optional[list[str]] = None
    drift: bool = False


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AuthorityRequester(ContractModel):
    agent: str
    identity: str


class AuthorityRequest(ContractModel):
    request_id: str
    work_id: str
    requester: AuthorityRequester
    actions: list[str] = Field(min_length=1)
    resources: list[str] = Field(min_length=1)
    data_classes: list[str] = Field(default_factory=list)
    network_destinations: list[str] = Field(default_factory=list)
    constraints: dict[str, Any]
    requested_at: datetime


class CapabilityManifest(ContractModel):
    manifest_id: str
    work_id: str
    agents: list[str] = Field(min_length=1)
    skills: list[str]
    tools: list[str]
    resources: list[str] = Field(default_factory=list)
    harness_candidates: list[str] = Field(min_length=1)
    estimated_cost: dict[str, Any] = Field(default_factory=dict)
    generated_at: datetime


class AuthorityResolveRequest(ContractModel):
    authority_request: AuthorityRequest
    capability_manifest: CapabilityManifest


class AuthorityEvidence(BaseModel):
    ledger_entry_id: str
    ledger_hash: str
    signature: str
    public_key: str


class AuthorityDecision(BaseModel):
    decision_id: str
    request_id: str
    work_id: str
    outcome: Literal["allow", "deny", "approval_required"]
    reasons: list[str]
    policy: str
    evaluated_actions: int
    decided_at: datetime
    evidence: AuthorityEvidence


class AuthorityStatus(BaseModel):
    work_id: str
    state: Literal["authorized", "blocked", "awaiting_approval"]
    decision_id: str
    updated_at: datetime
    evidence_hash: str


class AttestVerifyIn(BaseModel):
    agent: str
    release: str


class DiscoveryRequest(BaseModel):
    agent: str
    adapter: str


class GatewayRequest(BaseModel):
    agent: Optional[str] = None
    adapter: str
    action: ActionIn
    task_id: Optional[str] = None
    grant_id: Optional[str] = None
    requested_by: Optional[str] = None
    idempotency_key: Optional[str] = None
    # Adversarial campaign context. Required when the caller's trust domain is
    # adversarial; ignored for operational callers.
    campaign_id: Optional[str] = None
    authority_ref: Optional[str] = None
    campaign_digest: Optional[str] = None
    attack_surface: Optional[list[str]] = None
    # Execution metadata only; grants nothing.
    executor_provider: Optional[str] = None


class CampaignRegisterRequest(BaseModel):
    principal_id: str
    envelope: dict[str, Any]


class CampaignRevokeRequest(BaseModel):
    reason: str
    revoked_by: Optional[str] = None


class GrantIssueRequest(BaseModel):
    agent: str
    granted_by: Optional[str] = None
    purpose: str
    tools: list[str] = Field(default_factory=list)
    data_domains: list[str] = Field(default_factory=list)
    impact_max: str = "readonly"
    task_id: Optional[str] = None
    credential_ref: Optional[str] = None
    parent_grant_id: Optional[str] = None
    ttl_seconds: Optional[int] = None


class GrantRevokeRequest(BaseModel):
    # Optional claim: if present it must match the authenticated principal.
    revoked_by: Optional[str] = None
    reason: str


class ApprovalDecisionRequest(BaseModel):
    decided_by: Optional[str] = None
    reason: Optional[str] = None
    jit_ttl_seconds: Optional[int] = 300


class ApprovalDenyRequest(BaseModel):
    decided_by: Optional[str] = None
    reason: Optional[str] = None


class ResumeRequest(BaseModel):
    resume_token: str


def _action(a: ActionIn) -> Action:
    return Action(tool=a.tool, params=a.params, domain=a.domain, impact=a.impact, intent=a.intent)


def _model_dict(model: BaseModel) -> dict[str, Any]:
    """Support both Pydantic v1 and v2 for client deployments."""
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def create_app(
    config_path: str | Path = "fence.yaml",
    ledger_path: str | Path = "ledger.jsonl",
    key_dir: str | Path = "keys",
    difficulty: int = 0,
    *,
    adapters: dict[str, EnforcementAdapter] | None = None,
    authority_path: str | Path | None = "authority.json",
    approvals_path: str | Path | None = "approvals.json",
    idempotency_path: str | Path | None = "idempotency.json",
    campaigns_path: str | Path | None = "campaigns.json",
    api_key: str | None = None,
    principals: PrincipalRegistry | None = None,
    require_auth: bool = True,
) -> FastAPI:
    config_path = Path(config_path)
    key_dir = Path(key_dir)
    signer = Signer()
    if key_dir.exists():
        signer = Signer.load(key_dir)
    else:
        signer.save(key_dir)

    policies: dict[str, Policy] = {}
    if config_path.exists():
        import yaml
        policies = load_policies(yaml.safe_load(config_path.read_text()) or {})

    ledger = Ledger(signer=signer, path=Path(ledger_path), difficulty=int(difficulty))
    if Path(ledger_path).exists():
        ledger = Ledger.load(ledger_path, signer=signer)
        ledger.difficulty = int(difficulty)
    authority_statuses: dict[str, AuthorityStatus] = {}

    authority = AuthorityStore(authority_path)
    approvals = ApprovalStore(approvals_path)
    idempotency = IdempotencyStore(idempotency_path)
    campaigns = CampaignAuthorityStore(campaigns_path)
    registered_adapters = adapters if adapters is not None else _default_adapters_from_env()
    gateway = EnforcementGateway(
        policies=policies,
        adapters=registered_adapters,
        ledger=ledger,
        authority=authority,
        approvals=approvals,
        idempotency=idempotency,
        campaigns=campaigns,
    )

    app = FastAPI(title="Ledgato", version="0.3.0")
    app.state.gateway = gateway
    app.state.authority = authority
    app.state.approvals = approvals
    app.state.idempotency = idempotency
    app.state.campaigns = campaigns
    app.state.adapters = registered_adapters

    configured_key = api_key or os.getenv("LEDGATO_API_KEY")
    registry = principals if principals is not None else PrincipalRegistry.from_env()

    # A shared key stays supported for single-tenant use, but it is mapped onto
    # an explicit admin principal rather than bypassing identity entirely.
    if configured_key and not registry.configured():
        registry.add("shared-key", "admin", configured_key)

    if require_auth and not registry.configured():
        raise RuntimeError(
            "Ledgato refuses to start unauthenticated: set LEDGATO_API_KEY or "
            "LEDGATO_PRINCIPALS, or pass require_auth=False for an explicitly "
            "unauthenticated local development instance."
        )

    app_requires_auth = registry.configured()

    def _principal(authorization: str | None = Header(default=None)) -> Principal:
        """Resolve the caller from its bearer credential. Fails closed."""
        if not app_requires_auth:
            return Principal(id="anonymous", role="admin")
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(401, "missing Ledgato credential")
        found = registry.resolve(authorization[len("Bearer ") :])
        if found is None:
            raise HTTPException(401, "invalid Ledgato credential")
        return found

    def _auth(authorization: str | None = Header(default=None)) -> None:
        _principal(authorization)

    def _require_role(principal: Principal, *, allowed: set[str], action: str) -> None:
        if principal.role not in allowed:
            raise HTTPException(
                403,
                f"principal '{principal.id}' with role '{principal.role}' may not {action}",
            )

    def _claim(principal: Principal, claimed: str | None, *, field: str) -> str:
        try:
            return enforce_claim(principal, claimed, field=field)
        except IdentityClaimError as exc:
            raise HTTPException(403, str(exc)) from exc

    def _policy(agent: str) -> Policy:
        pol = policies.get(agent)
        if not pol:
            raise HTTPException(404, f"no policy for agent '{agent}'")
        return pol

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "version": "0.3.0",
            "difficulty": ledger.difficulty,
            "policies": sorted(policies),
            "adapters": sorted(registered_adapters),
            "ledger_entries": len(ledger.entries),
            "idempotency_records": len(idempotency.list()),
        }

    @app.post("/v1/actions/check", dependencies=[Depends(_auth)])
    def check(req: CheckRequest):
        policy = _policy(req.agent)
        grant = None
        if req.grant_id:
            grant = authority.get(req.grant_id)
            if not grant:
                raise HTTPException(404, f"unknown authority grant '{req.grant_id}'")
            valid, reason = authority.validate(req.grant_id)
            if not valid:
                decision = Decision(
                    allow=False,
                    outcome=DENY,
                    reason=f"DENY: {reason or 'authority grant is not effective'}",
                    reasons=[reason or "authority grant is not effective"],
                    policy=policy.agent,
                    on_deny=list(policy.on_deny),
                    grant_id=grant.id,
                )
            else:
                decision = evaluate_action(policy, _action(req.action), grant=grant, task_id=req.task_id)
        else:
            decision = evaluate_action(policy, _action(req.action), task_id=req.task_id)
        ledger.append(
            req.agent,
            decision.outcome,
            {"decision": decision.to_dict(), "task_id": req.task_id, "authority": grant.to_dict() if grant else None},
            action=req.action.tool,
        )
        return {"agent": req.agent, **decision.to_dict()}

    @app.post("/v1/authority/resolve", response_model=AuthorityDecision, dependencies=[Depends(_auth)])
    def resolve_authority(req: AuthorityResolveRequest):
        """Resolve an Agent OS authority request before a harness executes work."""
        request = req.authority_request
        manifest = req.capability_manifest
        policy = _policy(request.requester.agent)
        reasons: list[str] = []

        if request.work_id != manifest.work_id:
            reasons.append("authority request and capability manifest refer to different work")
        if request.requester.agent not in manifest.agents:
            reasons.append("requesting agent is not present in the capability manifest")

        missing_actions = sorted(set(request.actions) - set(manifest.tools))
        if missing_actions:
            reasons.append(f"requested actions are absent from the capability manifest: {missing_actions}")
        missing_resources = sorted(set(request.resources) - set(manifest.resources))
        if missing_resources:
            reasons.append(f"requested resources are absent from the capability manifest: {missing_resources}")

        impact = str(request.constraints.get("impact", "readonly"))
        intent = request.constraints.get("intent")
        action_decisions = []
        if not reasons:
            for tool in request.actions:
                for resource in request.resources:
                    decision = evaluate_action(
                        policy,
                        Action(tool=tool, domain=resource, impact=impact, intent=intent),
                    )
                    action_decisions.append(decision)
                    reasons.extend(decision.reasons)

        denied = bool(reasons and not action_decisions) or any(not item.allow for item in action_decisions)
        approval_on_deny = bool({"approve", "approval", "require_approval"} & set(policy.on_deny))
        outcome = "approval_required" if denied and approval_on_deny else "deny" if denied else "allow"
        evidence_body = {
            "request_id": request.request_id,
            "work_id": request.work_id,
            "manifest_id": manifest.manifest_id,
            "identity": request.requester.identity,
            "outcome": outcome,
            "reasons": reasons,
            "actions": request.actions,
            "resources": request.resources,
        }
        entry = ledger.append(
            request.requester.agent,
            outcome.upper(),
            evidence_body,
            action="authority.resolve",
        )
        resolved = AuthorityDecision(
            decision_id=uuid.uuid4().hex,
            request_id=request.request_id,
            work_id=request.work_id,
            outcome=outcome,
            reasons=reasons,
            policy=policy.agent,
            evaluated_actions=len(action_decisions),
            decided_at=datetime.now(timezone.utc),
            evidence=AuthorityEvidence(
                ledger_entry_id=entry.id,
                ledger_hash=entry.hash,
                signature=entry.signature,
                public_key=entry.public_key,
            ),
        )
        authority_statuses[request.work_id] = AuthorityStatus(
            work_id=request.work_id,
            state={
                "allow": "authorized",
                "deny": "blocked",
                "approval_required": "awaiting_approval",
            }[outcome],
            decision_id=resolved.decision_id,
            updated_at=resolved.decided_at,
            evidence_hash=entry.hash,
        )
        return resolved

    @app.get("/v1/authority/status/{work_id}", response_model=AuthorityStatus, dependencies=[Depends(_auth)])
    def authority_status(work_id: str):
        status = authority_statuses.get(work_id)
        if not status:
            raise HTTPException(404, f"no authority decision for work '{work_id}'")
        return status

    @app.post("/v1/discovery", dependencies=[Depends(_auth)])
    def discovery(req: DiscoveryRequest):
        try:
            return gateway.discover(agent=req.agent, adapter=req.adapter)
        except KeyError as exc:
            raise HTTPException(404, str(exc)) from exc
        except Exception as exc:
            raise HTTPException(502, f"live discovery failed: {exc}") from exc

    @app.post("/v1/gateway/execute")
    def gateway_execute(req: GatewayRequest, principal: Principal = Depends(_principal)):
        # A verifier is observation-only and must never reach execution,
        # regardless of role. Fail closed before anything else.
        if principal.is_verifier():
            raise HTTPException(
                403, f"verifier principal '{principal.id}' may not execute actions"
            )
        # An agent principal may only ever act as itself. Approver/admin
        # principals are not permitted to drive agent execution at all, so a
        # human credential cannot be used to launder an agent action.
        _require_role(principal, allowed={"agent"}, action="execute governed actions")
        agent_id = _claim(principal, req.agent, field="agent")

        campaign_context = None
        if principal.is_adversarial():
            # Bind adversarial execution to a currently valid campaign, checked
            # against the persisted authority before the adapter can run. Over-
            # scope is DENY, never APPROVE, and never reaches idempotency.
            verdict = authorize_campaign_action(
                campaigns,
                principal_id=principal.id,
                campaign_id=req.campaign_id,
                authority_ref=req.authority_ref,
                campaign_digest=req.campaign_digest,
                attack_surface=req.attack_surface,
            )
            campaign_context = {
                "principal_id": principal.id,
                "principal_role": principal.role,
                "trust_domain": principal.trust_domain,
                "campaign_id": req.campaign_id,
                "authority_ref": req.authority_ref,
                "campaign_digest": req.campaign_digest,
                "attack_surface": req.attack_surface,
                "executor_provider": req.executor_provider,
            }
            if not verdict.allow:
                try:
                    return gateway.deny_campaign(
                        agent=agent_id, adapter=req.adapter,
                        action=_action(req.action), reason=verdict.reason,
                        campaign_context=campaign_context,
                    )
                except KeyError as exc:
                    raise HTTPException(404, str(exc)) from exc
        try:
            return gateway.execute(
                agent=agent_id,
                adapter=req.adapter,
                action=_action(req.action),
                task_id=req.task_id,
                grant_id=req.grant_id,
                requested_by=principal.id,
                idempotency_key=req.idempotency_key,
                campaign_context=campaign_context,
            )
        except KeyError as exc:
            raise HTTPException(404, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        except Exception as exc:
            raise HTTPException(502, f"protected execution failed: {exc}") from exc

    @app.post("/v1/campaigns")
    def register_campaign(
        req: CampaignRegisterRequest, principal: Principal = Depends(_principal)
    ):
        # Registering campaign authority is a control-plane act. An adversarial
        # principal can never create, widen, or replace its own authorization.
        _require_role(principal, allowed={"admin"}, action="register campaign authority")
        try:
            authority = build_authority(req.envelope, expected_principal_id=req.principal_id)
            pinned = campaigns.register(authority)
        except CampaignError as exc:
            raise HTTPException(400, str(exc)) from exc
        ledger.append(
            req.principal_id, "CAMPAIGN_REGISTERED",
            {"campaign_id": pinned.campaign_id, "campaign_digest": pinned.campaign_digest,
             "authority_ref": pinned.authority_ref, "registered_by": principal.id},
            action="campaign.register",
        )
        return pinned.to_dict()

    @app.post("/v1/campaigns/{campaign_id}/revoke")
    def revoke_campaign(
        campaign_id: str, req: CampaignRevokeRequest,
        principal: Principal = Depends(_principal),
    ):
        _require_role(principal, allowed={"admin"}, action="revoke campaign authority")
        revoked_by = _claim(principal, req.revoked_by, field="revoked_by")
        try:
            authority = campaigns.revoke(campaign_id, revoked_by=revoked_by, reason=req.reason)
        except KeyError as exc:
            raise HTTPException(404, f"unknown campaign '{campaign_id}'") from exc
        ledger.append(
            authority.principal_id, "CAMPAIGN_REVOKED",
            {"campaign_id": campaign_id, "revoked_by": revoked_by, "reason": req.reason},
            action="campaign.revoke",
        )
        return authority.to_dict()

    @app.get("/v1/campaigns", dependencies=[Depends(_auth)])
    def list_campaigns():
        return {"campaigns": [c.to_dict() for c in campaigns.list()]}

    @app.post("/v1/authority/grants")
    def issue_grant(req: GrantIssueRequest, principal: Principal = Depends(_principal)):
        _require_role(principal, allowed={"admin"}, action="issue authority grants")
        payload = _model_dict(req)
        payload["granted_by"] = _claim(principal, payload.get("granted_by"), field="granted_by")
        try:
            grant = authority.issue(**payload)
        except (KeyError, ValueError) as exc:
            raise HTTPException(409, str(exc)) from exc
        ledger.append(req.agent, "GRANTED", {"authority": grant.to_dict()}, action="authority.grant")
        return grant.to_dict()

    @app.get("/v1/authority/grants", dependencies=[Depends(_auth)])
    def list_grants(agent: str | None = None, active_only: bool = False):
        return {"grants": [g.to_dict() for g in authority.list(agent=agent, active_only=active_only)]}

    @app.post("/v1/authority/grants/{grant_id}/revoke")
    def revoke_grant(
        grant_id: str, req: GrantRevokeRequest, principal: Principal = Depends(_principal)
    ):
        _require_role(principal, allowed={"admin"}, action="revoke authority grants")
        revoked_by = _claim(principal, req.revoked_by, field="revoked_by")
        try:
            grant = authority.revoke(grant_id, revoked_by=revoked_by, reason=req.reason)
        except KeyError as exc:
            raise HTTPException(404, f"unknown grant '{grant_id}'") from exc
        ledger.append(grant.agent, "REVOKED", {"authority": grant.to_dict()}, action="authority.revoke")
        return grant.to_dict()

    @app.get("/v1/approvals", dependencies=[Depends(_auth)])
    def list_approvals(status: str | None = None):
        return {"approvals": [a.to_dict() for a in approvals.list(status=status)]}

    @app.post("/v1/approvals/{approval_id}/approve")
    def approve(
        approval_id: str,
        req: ApprovalDecisionRequest,
        principal: Principal = Depends(_principal),
    ):
        # Separation of duties: the agent that requested the action can never
        # be the principal that approves it.
        _require_role(principal, allowed={"approver"}, action="decide approvals")
        decided_by = _claim(principal, req.decided_by, field="decided_by")
        try:
            return gateway.approve(
                approval_id,
                decided_by=decided_by,
                reason=req.reason,
                jit_ttl_seconds=req.jit_ttl_seconds,
            )
        except KeyError as exc:
            raise HTTPException(404, f"unknown approval '{approval_id}'") from exc
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post("/v1/approvals/{approval_id}/deny")
    def deny_approval(
        approval_id: str, req: ApprovalDenyRequest, principal: Principal = Depends(_principal)
    ):
        _require_role(principal, allowed={"approver"}, action="decide approvals")
        decided_by = _claim(principal, req.decided_by, field="decided_by")
        try:
            return gateway.deny_approval(approval_id, decided_by=decided_by, reason=req.reason)
        except KeyError as exc:
            raise HTTPException(404, f"unknown approval '{approval_id}'") from exc
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post("/v1/approvals/{approval_id}/resume", dependencies=[Depends(_auth)])
    def resume(approval_id: str, req: ResumeRequest):
        try:
            return gateway.resume(approval_id, resume_token=req.resume_token)
        except KeyError as exc:
            raise HTTPException(404, f"unknown approval '{approval_id}'") from exc
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        except Exception as exc:
            raise HTTPException(502, f"resumed execution failed: {exc}") from exc

    @app.post("/v1/probes/run", dependencies=[Depends(_auth)])
    def probes(req: ProbeRequest):
        pol = _policy(req.agent)
        summary = summarize(run_probes(pol))
        ledger.append(req.agent, "PROBED", {"passed": summary["passed"], "total": summary["total"]}, action="probe_battery")
        return {"agent": req.agent, **summary}

    @app.post("/v1/releases/attest", dependencies=[Depends(_auth)])
    def attest(req: AttestRequest):
        pol = _policy(req.agent)
        actions = [_action(a) for a in req.actions]
        if not actions:
            actions = [Action(tool=t, impact="readonly") for t in sorted(pol.allow_tools)]
        observed = set(req.observed_scope or (set(pol.allow_tools) | {"db.write"} if req.drift else set()))
        result = attest_release(ledger, pol, req.release, actions, observed_scope=observed or None)
        return result.to_dict()

    @app.get("/v1/ledger", dependencies=[Depends(_auth)])
    def get_ledger(limit: int = 50, verify: bool = False):
        data = ledger.to_list()[-limit:]
        out = {"count": len(data), "entries": data}
        if verify:
            ok, errs = ledger.verify_chain()
            out["verified"] = ok
            out["errors"] = errs
        return out

    @app.post("/v1/ledger/verify", dependencies=[Depends(_auth)])
    def verify_ledger():
        ok, errs = ledger.verify_chain()
        return {"verified": ok, "errors": errs, "entries": len(ledger.entries)}

    @app.get("/v1/ledger/status", dependencies=[Depends(_auth)])
    def ledger_status():
        head = ledger.entries[-1] if ledger.entries else None
        ok, errs = ledger.verify_chain()
        return {
            "entries": len(ledger.entries),
            "head": head.hash if head else "GENESIS",
            "difficulty": ledger.difficulty,
            "verified": ok,
            "errors": errs,
        }

    @app.get("/v1/ledger/chain", dependencies=[Depends(_auth)])
    def ledger_chain():
        return {"entries": ledger.to_list(), "difficulty": ledger.difficulty}

    @app.post("/v1/ledger/reconcile", dependencies=[Depends(_auth)])
    def ledger_reconcile(body: dict):
        node = Node(ledger)
        remote = body.get("chain", [])
        result = node.reconcile(remote)
        return {"sync": result.to_dict(), "entries": len(ledger.entries)}

    @app.post("/v1/attestations/verify", dependencies=[Depends(_auth)])
    def attest_verify(req: AttestVerifyIn):
        return attest_ops.verify_release(ledger, req.agent, req.release)

    @app.post("/v1/attestations/report", dependencies=[Depends(_auth)])
    def attest_report(req: AttestVerifyIn):
        return attest_ops.export_report(ledger, req.agent, req.release)

    @app.post("/v1/attestations/report/verify", dependencies=[Depends(_auth)])
    def attest_report_verify(body: dict):
        return attest_ops.verify_report(body)

    return app


def _default_adapters_from_env() -> dict[str, EnforcementAdapter]:
    adapters: dict[str, EnforcementAdapter] = {}
    repository = os.getenv("LEDGATO_GITHUB_REPOSITORY")
    token = os.getenv("LEDGATO_GITHUB_TOKEN") or os.getenv("GITHUB_TOKEN")
    if repository and token:
        adapters["github"] = GitHubAdapter(
            repository=repository,
            token=token,
            api_url=os.getenv("LEDGATO_GITHUB_API_URL"),
        )
    return adapters


def __getattr__(name: str):
    """Build the default ASGI app lazily.

    ``uvicorn ledgato.api:app`` still resolves, and a server started without a
    credential still refuses to boot. Building it eagerly at import time would
    mean the fail-closed check fires on *any* import of this module, including
    by tooling that never serves traffic.
    """
    if name == "app":
        return create_app()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
