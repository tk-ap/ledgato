"""Small dependency-free Python SDK for the Ledgato gateway API."""
from __future__ import annotations

import json
from typing import Any
from urllib import error, request


class LedgatoClient:
    def __init__(self, base_url: str, *, api_key: str | None = None, timeout: float = 20.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def discover(self, *, agent: str, adapter: str) -> dict[str, Any]:
        return self._call("POST", "/v1/discovery", {"agent": agent, "adapter": adapter})

    def issue_grant(self, **payload: Any) -> dict[str, Any]:
        return self._call("POST", "/v1/authority/grants", payload)

    def revoke_grant(self, grant_id: str, *, revoked_by: str, reason: str) -> dict[str, Any]:
        return self._call(
            "POST",
            f"/v1/authority/grants/{grant_id}/revoke",
            {"revoked_by": revoked_by, "reason": reason},
        )

    def execute(
        self,
        *,
        agent: str,
        adapter: str,
        action: dict[str, Any],
        task_id: str | None = None,
        grant_id: str | None = None,
        requested_by: str | None = None,
    ) -> dict[str, Any]:
        return self._call(
            "POST",
            "/v1/gateway/execute",
            {
                "agent": agent,
                "adapter": adapter,
                "task_id": task_id,
                "grant_id": grant_id,
                "requested_by": requested_by,
                "action": action,
            },
        )

    def approve(
        self,
        approval_id: str,
        *,
        decided_by: str,
        reason: str | None = None,
        jit_ttl_seconds: int | None = 300,
    ) -> dict[str, Any]:
        return self._call(
            "POST",
            f"/v1/approvals/{approval_id}/approve",
            {"decided_by": decided_by, "reason": reason, "jit_ttl_seconds": jit_ttl_seconds},
        )

    def deny_approval(self, approval_id: str, *, decided_by: str, reason: str | None = None) -> dict[str, Any]:
        return self._call(
            "POST",
            f"/v1/approvals/{approval_id}/deny",
            {"decided_by": decided_by, "reason": reason},
        )

    def resume(self, approval_id: str, *, resume_token: str) -> dict[str, Any]:
        return self._call(
            "POST",
            f"/v1/approvals/{approval_id}/resume",
            {"resume_token": resume_token},
        )

    def _call(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        data = json.dumps(body).encode() if body is not None else None
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        req = request.Request(self.base_url + path, data=data, method=method, headers=headers)
        try:
            with request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode()
                return json.loads(raw) if raw else {}
        except error.HTTPError as exc:
            raw = exc.read().decode()
            try:
                detail = json.loads(raw)
            except json.JSONDecodeError:
                detail = {"detail": raw}
            raise LedgatoError(exc.code, detail) from exc


class LedgatoError(RuntimeError):
    def __init__(self, status_code: int, detail: Any):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Ledgato API error {status_code}: {detail}")
