"""Ledgato HTTP API (FastAPI).

A small backend that exposes the engine over HTTP: check an action, run the
probe battery, gate a release with signed attestations, and query/verify the
ledger. State is held per-process; persistence is via the CLI's JSONL ledger.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

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


class DemoRunRequest(BaseModel):
    """One atomic, inspectable product slice for previews and evaluations."""

    agent: str = "ops-agent"
    release: str = "preview-1"
    attempt: ActionIn = Field(
        default_factory=lambda: ActionIn(
            tool="db.write", domain="prod::billing", impact="write"
        )
    )


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

    @app.post("/v1/demo/run")
    def demo_run(req: DemoRunRequest):
        """Execute the MVP story in one request so serverless state is not implied.

        The result is produced by the real policy evaluator, adversarial probe
        battery, release gate, and signature verifier. The demo does not execute
        the requested external tool; Ledgato is the authorization boundary.
        """
        pol = _policy(req.agent)
        attempt = _action(req.attempt)
        decision = evaluate_action(pol, attempt)
        decision_entry = ledger.append(
            req.agent,
            decision.reason.split(":")[0],
            {"release": req.release, "decision": decision.to_dict()},
            action=attempt.tool,
        )
        probe_summary = summarize(run_probes(pol))
        gate = attest_release(
            ledger,
            pol,
            req.release,
            [attempt],
            observed_scope=set(pol.allow_tools),
        )
        verified, errors = ledger.verify_chain()
        return {
            "mode": "preview_ephemeral",
            "executed_external_action": False,
            "policy": pol.to_dict(),
            "attempt": attempt.to_dict(),
            "decision": decision.to_dict(),
            "decision_evidence": {
                "id": decision_entry.id,
                "hash": decision_entry.hash,
                "signature": decision_entry.signature,
                "public_key": decision_entry.public_key,
            },
            "probes": probe_summary,
            "gate": gate.to_dict(),
            "ledger": {
                "verified": verified,
                "errors": errors,
                "entries": len(ledger.entries),
                "head": ledger.entries[-1].hash if ledger.entries else "GENESIS",
            },
        }

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


_default_state = Path(tempfile.gettempdir()) / "ledgato-default"
app = create_app(
    ledger_path=_default_state / "ledger.jsonl",
    key_dir=_default_state / "keys",
)
