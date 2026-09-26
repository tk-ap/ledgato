"""A protected resource that acts only on a valid Ledgato permit.

This is the non-bypassable half of the boundary. The resource owns the
capability (in production: the credential that can cross into the downstream
system). It pins Ledgato's public key and refuses to act unless the caller
presents a permit that Ledgato signed for *exactly* this contract, on *this*
resource, that has not expired and has never been used.

The permit is burned with a durable atomic write *before* the effect runs, so
a permit can produce at most one side effect even across a restart. A crash
between the burn and the downstream call loses the action rather than
repeating it: for consequential actions, at-most-once is the safe failure.

Run it as its own process so the executor cannot reach its state directly:

    python -m ledgato.protected_resource --resource service::billing-api \\
        --state resource.json --trusted-key <ledgato-public-key-b64> --port 8801
"""
from __future__ import annotations

import argparse
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .enforcement import ActionContract, ContractError, atomic_write_json, verify_permit

Effect = Callable[[ActionContract], dict[str, Any]]


class PermitRejected(PermissionError):
    """The resource refused to act. Nothing downstream happened."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def _record_effect(contract: ActionContract) -> dict[str, Any]:
    return {"applied": contract.action, "params": dict(contract.params)}


class ProtectedResource:
    def __init__(
        self,
        *,
        resource: str,
        state_path: str | Path,
        trusted_keys: set[str] | list[str],
        effect: Effect | None = None,
        clock: Callable[[], datetime] | None = None,
    ):
        if not trusted_keys:
            raise ValueError("a protected resource must pin at least one Ledgato key")
        self.resource = resource
        self.state_path = Path(state_path)
        self.trusted_keys = set(trusted_keys)
        self._effect = effect or _record_effect
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._lock = threading.Lock()
        self._state = {"consumed_permits": {}, "effects": [], "rejections": []}
        if self.state_path.exists():
            self._state = json.loads(self.state_path.read_text(encoding="utf-8"))

    def perform(self, contract: Any, permit: Any) -> dict[str, Any]:
        """Act once for a valid permit; otherwise raise PermitRejected."""
        with self._lock:
            try:
                parsed = (
                    contract
                    if isinstance(contract, ActionContract)
                    else ActionContract.from_dict(contract)
                )
            except ContractError as exc:
                self._reject(None, permit, f"malformed contract: {exc}")
            reason = verify_permit(
                permit,
                contract=parsed,
                trusted_keys=self.trusted_keys,
                resource=self.resource,
                now=self._clock(),
            )
            if reason is None and permit["permit_id"] in self._state["consumed_permits"]:
                reason = "permit has already been used"
            if reason is not None:
                self._reject(parsed, permit, reason)

            # Burn the permit durably before acting: a crash from here on can
            # lose this action but can never let the same permit act twice.
            now = self._clock().isoformat()
            self._state["consumed_permits"][permit["permit_id"]] = now
            atomic_write_json(self.state_path, self._state)

            effect = {
                "permit_id": permit["permit_id"],
                "decision_id": permit["decision_id"],
                "work_id": parsed.work_id,
                "action": parsed.action,
                "contract_digest": parsed.digest(),
                "ledger_entry_hash": permit["ledger_entry_hash"],
                "at": now,
            }
            try:
                effect["result"] = self._effect(parsed)
            except Exception as exc:
                effect["error"] = f"{type(exc).__name__}: {exc}"
                self._state["effects"].append(effect)
                atomic_write_json(self.state_path, self._state)
                raise
            self._state["effects"].append(effect)
            atomic_write_json(self.state_path, self._state)
            return {"executed": True, "resource": self.resource, **effect}

    def effects(self) -> list[dict[str, Any]]:
        with self._lock:
            return json.loads(json.dumps(self._state["effects"]))

    def rejections(self) -> list[dict[str, Any]]:
        with self._lock:
            return json.loads(json.dumps(self._state["rejections"]))

    def _reject(self, contract: Optional[ActionContract], permit: Any, reason: str):
        permit_id = permit.get("permit_id") if isinstance(permit, Mapping) else None
        self._state["rejections"].append({
            "at": self._clock().isoformat(),
            "reason": reason,
            "work_id": contract.work_id if contract else None,
            "action": contract.action if contract else None,
            "permit_id": permit_id if isinstance(permit_id, str) else None,
        })
        atomic_write_json(self.state_path, self._state)
        raise PermitRejected(reason)


class PerformRequest(BaseModel):
    contract: dict[str, Any]
    permit: Optional[dict[str, Any]] = None


def create_resource_app(resource: ProtectedResource):
    """HTTP front for a ProtectedResource. The only route that acts is /perform."""
    app = FastAPI(title="Ledgato protected resource")

    @app.post("/perform")
    def perform(req: PerformRequest):
        try:
            return resource.perform(req.contract, req.permit)
        except PermitRejected as exc:
            raise HTTPException(403, {"rejected": True, "reason": exc.reason}) from exc

    @app.get("/effects")
    def effects():
        return {"resource": resource.resource, "effects": resource.effects()}

    @app.get("/rejections")
    def rejections():
        return {"resource": resource.resource, "rejections": resource.rejections()}

    return app


class RemoteProtectedResource:
    """Client for a ProtectedResource running in another process."""

    def __init__(self, base_url: str, *, timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def perform(self, contract: Any, permit: Any) -> dict[str, Any]:
        from urllib import error, request

        body = {
            "contract": contract.to_dict() if isinstance(contract, ActionContract) else contract,
            "permit": permit,
        }
        req = request.Request(
            self.base_url + "/perform",
            data=json.dumps(body).encode(),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode())
        except error.HTTPError as exc:
            if exc.code == 403:
                detail = json.loads(exc.read().decode()).get("detail", {})
                raise PermitRejected(detail.get("reason", "rejected")) from exc
            raise


def main(argv: list[str] | None = None) -> int:
    import uvicorn

    p = argparse.ArgumentParser(prog="ledgato-protected-resource")
    p.add_argument("--resource", required=True)
    p.add_argument("--state", required=True)
    p.add_argument("--trusted-key", action="append", required=True)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8801)
    args = p.parse_args(argv)
    resource = ProtectedResource(
        resource=args.resource, state_path=args.state, trusted_keys=args.trusted_key
    )
    uvicorn.run(create_resource_app(resource), host=args.host, port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
