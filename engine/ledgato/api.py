"""Ledgato HTTP API (FastAPI).

A small backend that exposes the engine over HTTP: check an action, run the
probe battery, gate a release with signed attestations, and query/verify the
ledger. State is held per-process; persistence is via the CLI's JSONL ledger.
"""
from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Literal, Optional
import uuid

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .crypto import Signer
from .engine import detect_drift, evaluate_action
from .gate import attest_release
from .ledger import Ledger
from .models import Action, Policy, load_policies
from .probes import run_probes, summarize
from . import attestation as attest_ops
from .distributed import Node


class ActionIn(BaseModel):
    tool: str
    params: dict[str, Any] = Field(default_factory=dict)
    domain: Optional[str] = None
    impact: str = "readonly"
    intent: Optional[str] = None


class CheckRequest(BaseModel):
    agent: str
    action: ActionIn


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


def _action(a: ActionIn) -> Action:
    return Action(tool=a.tool, params=a.params, domain=a.domain, impact=a.impact, intent=a.intent)


def create_app(
    config_path: str | Path = "fence.yaml",
    ledger_path: str | Path = "ledger.jsonl",
    key_dir: str | Path = "keys",
    difficulty: int = 0,
) -> FastAPI:
    config_path = Path(config_path)
    key_dir = Path(key_dir)
    signer = Signer()
    if (key_dir / "ledgato_private.pem").exists() and (key_dir / "ledgato_public.pem").exists():
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
    authority_statuses: dict[str, AuthorityStatus] = {}

    app = FastAPI(title="Ledgato", version="0.2.0")

    def _policy(agent: str) -> Policy:
        pol = policies.get(agent)
        if not pol:
            raise HTTPException(404, f"no policy for agent '{agent}'")
        return pol

    @app.get("/health")
    def health():
        return {"status": "ok", "version": "0.2.0", "difficulty": ledger.difficulty, "policies": sorted(policies), "ledger_entries": len(ledger.entries)}

    @app.post("/v1/actions/check")
    def check(req: CheckRequest):
        decision = evaluate_action(_policy(req.agent), _action(req.action))
        ledger.append(req.agent, decision.reason.split(":")[0], decision.to_dict(), action=req.action.tool)
        return {"agent": req.agent, **decision.to_dict()}

    @app.post("/v1/authority/resolve", response_model=AuthorityDecision)
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

    @app.get("/v1/authority/status/{work_id}", response_model=AuthorityStatus)
    def authority_status(work_id: str):
        status = authority_statuses.get(work_id)
        if not status:
            raise HTTPException(404, f"no authority decision for work '{work_id}'")
        return status

    @app.post("/v1/probes/run")
    def probes(req: ProbeRequest):
        pol = _policy(req.agent)
        summary = summarize(run_probes(pol))
        ledger.append(req.agent, "PROBED", {"passed": summary["passed"], "total": summary["total"]}, action="probe_battery")
        return {"agent": req.agent, **summary}

    @app.post("/v1/releases/attest")
    def attest(req: AttestRequest):
        pol = _policy(req.agent)
        actions = [_action(a) for a in req.actions]
        if not actions:
            actions = [Action(tool=t, impact="readonly") for t in sorted(pol.allow_tools)]
        observed = set(req.observed_scope or (set(pol.allow_tools) | {"db.write"} if req.drift else set()))
        result = attest_release(ledger, pol, req.release, actions, observed_scope=observed or None)
        return result.to_dict()

    @app.get("/v1/ledger")
    def get_ledger(limit: int = 50, verify: bool = False):
        data = ledger.to_list()[-limit:]
        out = {"count": len(data), "entries": data}
        if verify:
            ok, errs = ledger.verify_chain()
            out["verified"] = ok
            out["errors"] = errs
        return out

    @app.post("/v1/ledger/verify")
    def verify_ledger():
        ok, errs = ledger.verify_chain()
        return {"verified": ok, "errors": errs, "entries": len(ledger.entries)}

    # ---- distributed ledger endpoints ---------------------------------
    @app.get("/v1/ledger/status")
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

    @app.get("/v1/ledger/chain")
    def ledger_chain():
        return {"entries": ledger.to_list(), "difficulty": ledger.difficulty}

    @app.post("/v1/ledger/reconcile")
    def ledger_reconcile(body: dict):
        """Longest-valid-chain consensus against a peer's chain."""
        from .distributed import Node

        node = Node(ledger)
        remote = body.get("chain", [])
        result = node.reconcile(remote)
        return {"sync": result.to_dict(), "entries": len(ledger.entries)}

    # ---- attestation verification & ops --------------------------------
    @app.post("/v1/attestations/verify")
    def attest_verify(req: AttestVerifyIn):
        return attest_ops.verify_release(ledger, req.agent, req.release)

    @app.post("/v1/attestations/report")
    def attest_report(req: AttestVerifyIn):
        return attest_ops.export_report(ledger, req.agent, req.release)

    @app.post("/v1/attestations/report/verify")
    def attest_report_verify(body: dict):
        return attest_ops.verify_report(body)

    return app


app = create_app()
