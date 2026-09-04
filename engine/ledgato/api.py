"""Ledgato HTTP API.

The API exposes the legacy policy/release-assurance endpoints plus the real
execution gateway: discovery, delegated/JIT grants, approval pause/resume, and
post-action verification through registered native adapters.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from . import attestation as attest_ops
from .adapters.base import EnforcementAdapter
from .adapters.github import GitHubAdapter
from .approvals import ApprovalStore
from .authority import AuthorityStore
from .crypto import Signer
from .distributed import Node
from .engine import DENY, Decision, evaluate_action
from .gate import attest_release
from .gateway import EnforcementGateway
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


class AttestVerifyIn(BaseModel):
    agent: str
    release: str


class DiscoveryRequest(BaseModel):
    agent: str
    adapter: str


class GatewayRequest(BaseModel):
    agent: str
    adapter: str
    action: ActionIn
    task_id: Optional[str] = None
    grant_id: Optional[str] = None
    requested_by: Optional[str] = None


class GrantIssueRequest(BaseModel):
    agent: str
    granted_by: str
    purpose: str
    tools: list[str] = Field(default_factory=list)
    data_domains: list[str] = Field(default_factory=list)
    impact_max: str = "readonly"
    task_id: Optional[str] = None
    credential_ref: Optional[str] = None
    parent_grant_id: Optional[str] = None
    ttl_seconds: Optional[int] = None


class GrantRevokeRequest(BaseModel):
    revoked_by: str
    reason: str


class ApprovalDecisionRequest(BaseModel):
    decided_by: str
    reason: Optional[str] = None
    jit_ttl_seconds: Optional[int] = 300


class ApprovalDenyRequest(BaseModel):
    decided_by: str
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
    api_key: str | None = None,
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

    authority = AuthorityStore(authority_path)
    approvals = ApprovalStore(approvals_path)
    registered_adapters = adapters if adapters is not None else _default_adapters_from_env()
    gateway = EnforcementGateway(
        policies=policies,
        adapters=registered_adapters,
        ledger=ledger,
        authority=authority,
        approvals=approvals,
    )

    app = FastAPI(title="Ledgato", version="0.3.0")
    app.state.gateway = gateway
    app.state.authority = authority
    app.state.approvals = approvals
    app.state.adapters = registered_adapters

    configured_key = api_key or os.getenv("LEDGATO_API_KEY")

    def _auth(authorization: str | None = Header(default=None)) -> None:
        if not configured_key:
            return
        expected = f"Bearer {configured_key}"
        if authorization != expected:
            raise HTTPException(401, "invalid or missing Ledgato API key")

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

    @app.post("/v1/discovery", dependencies=[Depends(_auth)])
    def discovery(req: DiscoveryRequest):
        try:
            return gateway.discover(agent=req.agent, adapter=req.adapter)
        except KeyError as exc:
            raise HTTPException(404, str(exc)) from exc
        except Exception as exc:
            raise HTTPException(502, f"live discovery failed: {exc}") from exc

    @app.post("/v1/gateway/execute", dependencies=[Depends(_auth)])
    def gateway_execute(req: GatewayRequest):
        try:
            return gateway.execute(
                agent=req.agent,
                adapter=req.adapter,
                action=_action(req.action),
                task_id=req.task_id,
                grant_id=req.grant_id,
                requested_by=req.requested_by,
            )
        except KeyError as exc:
            raise HTTPException(404, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        except Exception as exc:
            raise HTTPException(502, f"protected execution failed: {exc}") from exc

    @app.post("/v1/authority/grants", dependencies=[Depends(_auth)])
    def issue_grant(req: GrantIssueRequest):
        try:
            grant = authority.issue(**_model_dict(req))
        except (KeyError, ValueError) as exc:
            raise HTTPException(409, str(exc)) from exc
        ledger.append(req.agent, "GRANTED", {"authority": grant.to_dict()}, action="authority.grant")
        return grant.to_dict()

    @app.get("/v1/authority/grants", dependencies=[Depends(_auth)])
    def list_grants(agent: str | None = None, active_only: bool = False):
        return {"grants": [g.to_dict() for g in authority.list(agent=agent, active_only=active_only)]}

    @app.post("/v1/authority/grants/{grant_id}/revoke", dependencies=[Depends(_auth)])
    def revoke_grant(grant_id: str, req: GrantRevokeRequest):
        try:
            grant = authority.revoke(grant_id, revoked_by=req.revoked_by, reason=req.reason)
        except KeyError as exc:
            raise HTTPException(404, f"unknown grant '{grant_id}'") from exc
        ledger.append(grant.agent, "REVOKED", {"authority": grant.to_dict()}, action="authority.revoke")
        return grant.to_dict()

    @app.get("/v1/approvals", dependencies=[Depends(_auth)])
    def list_approvals(status: str | None = None):
        return {"approvals": [a.to_dict() for a in approvals.list(status=status)]}

    @app.post("/v1/approvals/{approval_id}/approve", dependencies=[Depends(_auth)])
    def approve(approval_id: str, req: ApprovalDecisionRequest):
        try:
            return gateway.approve(
                approval_id,
                decided_by=req.decided_by,
                reason=req.reason,
                jit_ttl_seconds=req.jit_ttl_seconds,
            )
        except KeyError as exc:
            raise HTTPException(404, f"unknown approval '{approval_id}'") from exc
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post("/v1/approvals/{approval_id}/deny", dependencies=[Depends(_auth)])
    def deny_approval(approval_id: str, req: ApprovalDenyRequest):
        try:
            return gateway.deny_approval(approval_id, decided_by=req.decided_by, reason=req.reason)
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


app = create_app()
