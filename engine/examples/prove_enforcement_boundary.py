"""Prove one non-bypassable boundary: AgentOS → Ledgato → protected action.

Runs Ledgato and a protected resource as two separate OS processes, drives them
through the AgentOS-side ProtectedExecutor, attempts to bypass the checkpoint,
restarts both processes, and re-verifies the evidence from disk.

    python engine/examples/prove_enforcement_boundary.py [--workdir DIR]

Exits 0 only when every check passes. Needs no external credential: the
protected "action" is a recorded state change inside the resource process,
which stands in for the downstream credential-holding system.
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable
from urllib import error, request

ENGINE = Path(__file__).resolve().parents[1]
if str(ENGINE) not in sys.path:
    sys.path.insert(0, str(ENGINE))

from ledgato.crypto import Signer  # noqa: E402
from ledgato.enforcement import CONTRACT_VERSION, ActionContract, sign_permit  # noqa: E402
from ledgato.integrations.protected_executor import (  # noqa: E402
    APPROVAL_REQUIRED,
    DENIED,
    EXECUTED,
    FAILED_CLOSED,
    ProtectedExecutor,
)
from ledgato.protected_resource import PermitRejected, RemoteProtectedResource  # noqa: E402
from ledgato.sdk import LedgatoClient, LedgatoError  # noqa: E402

FENCE = ENGINE / "examples" / "agent-os-protected-executor-fence.yaml"
AGENT = "agent-os-deployer"
RESOURCE = "service::billing-api"

_LEDGATO_LAUNCHER = """
import sys, uvicorn
from ledgato.api import create_app
d, port = sys.argv[1], int(sys.argv[2])
app = create_app(
    config_path=f"{d}/fence.yaml", ledger_path=f"{d}/ledger.jsonl", key_dir=f"{d}/keys",
    authority_path=f"{d}/authority.json", approvals_path=f"{d}/approvals.json",
    idempotency_path=f"{d}/idempotency.json", campaigns_path=f"{d}/campaigns.json",
    decisions_path=f"{d}/decisions.json", adapters={},
)
uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
"""


def contract(work_id: str, action: str, impact: str = "write", **params: Any) -> ActionContract:
    return ActionContract.from_dict({
        "version": CONTRACT_VERSION,
        "work_id": work_id,
        "agent": {"id": AGENT, "identity": f"iam:svc/{AGENT}"},
        "requested_action": {"name": action, "impact": impact, "params": params},
        "resource": RESOURCE,
        "policy": {"id": AGENT},
        "evidence": [{"kind": "work-item", "ref": f"agent-os:{work_id}"}],
    })


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait(url: str, timeout: float = 20.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with request.urlopen(url, timeout=1):
                return
        except (error.URLError, ConnectionError, OSError):
            time.sleep(0.1)
    raise RuntimeError(f"{url} did not come up")


class KeepsPermits:
    """Wraps the resource client and keeps a copy of every permit AgentOS sent.

    This is what a compromised or buggy AgentOS would hold: the exact permit it
    was issued. Replaying it must not produce a second action.
    """

    def __init__(self, inner: RemoteProtectedResource, kept: dict[str, dict[str, Any]]):
        self.inner = inner
        self.kept = kept

    def perform(self, contract: Any, permit: Any) -> dict[str, Any]:
        if isinstance(permit, dict):
            self.kept[permit["decision_id"]] = dict(permit)
        return self.inner.perform(contract, permit)


class Stack:
    """Ledgato + protected resource, each in its own process, state on disk."""

    def __init__(self, workdir: Path):
        self.dir = workdir
        self.dir.mkdir(parents=True, exist_ok=True)
        shutil.copy(FENCE, self.dir / "fence.yaml")
        keys = self.dir / "keys"
        if not keys.exists():
            Signer().save(keys)
        # The operator pins Ledgato's public key into the resource out of band.
        self.ledgato_key = Signer.load(keys).public_key_b64()
        self.agent_secret = secrets.token_urlsafe(24)
        self.approver_secret = secrets.token_urlsafe(24)
        self.verifier_secret = secrets.token_urlsafe(24)
        self.ledgato_port = _free_port()
        self.resource_port = _free_port()
        self.procs: dict[str, subprocess.Popen] = {}
        self.kept_permits: dict[str, dict[str, Any]] = {}

    @property
    def ledgato_url(self) -> str:
        return f"http://127.0.0.1:{self.ledgato_port}"

    @property
    def resource_url(self) -> str:
        return f"http://127.0.0.1:{self.resource_port}"

    def _env(self) -> dict[str, str]:
        env = {k: v for k, v in os.environ.items() if not k.startswith("LEDGATO_")}
        env["PYTHONPATH"] = str(ENGINE) + os.pathsep + env.get("PYTHONPATH", "")
        env["LEDGATO_PRINCIPALS"] = ",".join([
            f"{AGENT}:agent:{self.agent_secret}",
            f"tk-approver:approver:{self.approver_secret}",
            f"auditor:verifier:verifier:{self.verifier_secret}",
        ])
        return env

    def start_ledgato(self) -> None:
        self.procs["ledgato"] = subprocess.Popen(
            [sys.executable, "-c", _LEDGATO_LAUNCHER, str(self.dir), str(self.ledgato_port)],
            env=self._env(), stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        )
        _wait(self.ledgato_url + "/health")

    def start_resource(self) -> None:
        # The resource never receives Ledgato's API credentials: it trusts only
        # the pinned public key.
        env = {k: v for k, v in self._env().items() if k != "LEDGATO_PRINCIPALS"}
        self.procs["resource"] = subprocess.Popen(
            [sys.executable, "-m", "ledgato.protected_resource",
             "--resource", RESOURCE, "--state", str(self.dir / "resource.json"),
             "--trusted-key", self.ledgato_key, "--port", str(self.resource_port)],
            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        )
        _wait(self.resource_url + "/effects")

    def start(self) -> None:
        self.start_ledgato()
        self.start_resource()

    def stop(self, name: str | None = None) -> None:
        for key in [name] if name else list(self.procs):
            proc = self.procs.pop(key, None)
            if proc and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()

    def client(self, secret: str | None = None) -> LedgatoClient:
        return LedgatoClient(self.ledgato_url, api_key=secret or self.agent_secret, timeout=5)

    def verifier(self) -> LedgatoClient:
        return self.client(self.verifier_secret)

    def resource(self) -> RemoteProtectedResource:
        return RemoteProtectedResource(self.resource_url, timeout=5)

    def executor(self) -> ProtectedExecutor:
        return ProtectedExecutor(self.client(), KeepsPermits(self.resource(), self.kept_permits))

    def effects(self) -> list[dict[str, Any]]:
        with request.urlopen(self.resource_url + "/effects", timeout=5) as resp:
            return json.loads(resp.read())["effects"]


def run_proof(workdir: Path, log: Callable[[str], None] = lambda _m: None) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def check(name: str, ok: bool, detail: Any = None) -> bool:
        checks.append({"check": name, "passed": bool(ok), "detail": detail})
        log(f"  [{'PASS' if ok else 'FAIL'}] {name}")
        return ok

    stack = Stack(workdir)
    try:
        log("1. start Ledgato and the protected resource as separate processes")
        stack.start()
        executor = stack.executor()

        log("2. AgentOS runs three contracts through the protected executor")
        allowed_c = contract("work-allow", "release.deploy", version="2026.09.25")
        denied_c = contract("work-deny", "release.delete", impact="exec")
        approval_c = contract("work-approval", "release.rollback", to="2026.09.24")
        allowed = executor.run(allowed_c)
        denied = executor.run(denied_c)
        approval = executor.run(approval_c)
        check("allowed contract executed", allowed["status"] == EXECUTED and allowed["executed"] is True, allowed["reason"])
        check("denied contract stopped", denied["status"] == DENIED and denied["executed"] is False, denied["reason"])
        check("approval-required contract stopped",
              approval["status"] == APPROVAL_REQUIRED and approval["executed"] is False, approval["reason"])
        effects = stack.effects()
        check("exactly one side effect, for the allowed contract",
              len(effects) == 1 and effects[0]["work_id"] == "work-allow", [e["work_id"] for e in effects])

        log("3. bypass attempts")
        resource = stack.resource()
        allow_permit = stack.client().decide(contract("work-probe", "release.deploy", version="probe").to_dict())["permit"]

        def rejected(label: str, fn: Callable[[], Any]) -> None:
            try:
                fn()
            except PermitRejected as exc:
                check(f"bypass rejected: {label}", True, exc.reason)
            else:
                check(f"bypass rejected: {label}", False, "resource acted")

        rejected("direct call with no permit", lambda: resource.perform(allowed_c, None))
        rejected("replay of an already-used permit",
                 lambda: resource.perform(allowed_c, stack.kept_permits[allowed["decision_id"]]))
        rejected("valid permit re-targeted to a different contract",
                 lambda: resource.perform(contract("work-probe", "release.deploy", version="evil"), allow_permit))
        rejected("valid permit presented for a denied contract", lambda: resource.perform(denied_c, allow_permit))
        forged = sign_permit(Signer(), {**allow_permit, "issuer_public_key": Signer().public_key_b64()})
        rejected("permit signed by a non-Ledgato key",
                 lambda: resource.perform(contract("work-probe", "release.deploy", version="probe"), forged))
        tampered = {**allow_permit, "action": "release.delete"}
        rejected("permit with a tampered field",
                 lambda: resource.perform(contract("work-probe", "release.deploy", version="probe"), tampered))

        for label, secret, c in (
            ("human approver credential cannot obtain a permit", stack.approver_secret, allowed_c),
            ("verifier credential cannot obtain a permit", stack.verifier_secret, allowed_c),
        ):
            try:
                stack.client(secret).decide(c.to_dict())
                check(label, False, "decision returned")
            except LedgatoError as exc:
                check(label, exc.status_code == 403, exc.status_code)
        impostor = ActionContract.from_dict({**allowed_c.to_dict(), "agent": {"id": "other-agent", "identity": "iam:svc/other"}})
        try:
            stack.client().decide(impostor.to_dict())
            check("agent cannot request a permit as another agent", False, "decision returned")
        except LedgatoError as exc:
            check("agent cannot request a permit as another agent", exc.status_code == 403, exc.status_code)

        effects = stack.effects()
        check("still exactly one side effect after every bypass attempt", len(effects) == 1, len(effects))

        log("4. restart both processes; state is reloaded from disk")
        stack.stop()
        stack.start()
        verifier = stack.verifier()
        for label, result, executed in (
            ("allowed", allowed, True), ("denied", denied, False), ("approval-required", approval, False),
        ):
            ev = verifier.evidence(result["decision_id"])
            check(f"{label}: evidence verified after restart",
                  ev["verified"] and ev["chain_valid"] and ev["executed"] is executed and ev["consistent"],
                  ev["problems"])
        effects = stack.effects()
        allow_ev = verifier.evidence(allowed["decision_id"])
        check("resource effect is bound to the ledger decision entry",
              len(effects) == 1 and effects[0]["ledger_entry_hash"] == allow_ev["decision_entry"]["hash"]
              and effects[0]["decision_id"] == allowed["decision_id"],
              effects[0]["ledger_entry_hash"] if effects else None)
        rejected("permit replay after restart", lambda: stack.resource().perform(allowed_c, stack.kept_permits[allowed["decision_id"]]))

        log("5. Ledgato unavailable: the executor fails closed")
        stack.stop("ledgato")
        down = stack.executor().run(contract("work-outage", "release.deploy", version="outage"))
        check("no Ledgato decision -> FAILED_CLOSED, nothing executed",
              down["status"] == FAILED_CLOSED and down["executed"] is False, down["reason"])
        check("side effects unchanged after outage", len(stack.effects()) == 1, len(stack.effects()))
    finally:
        stack.stop()

    passed = all(c["passed"] for c in checks)
    return {"passed": passed, "checks": checks, "workdir": str(workdir)}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--workdir", help="state directory (default: a new temp dir)")
    args = p.parse_args(argv)
    workdir = Path(args.workdir) if args.workdir else Path(tempfile.mkdtemp(prefix="ledgato-proof-"))
    print(f"Ledgato enforcement boundary proof — state in {workdir}")
    result = run_proof(workdir, log=print)
    print(json.dumps({"passed": result["passed"],
                      "failed": [c["check"] for c in result["checks"] if not c["passed"]]}, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
