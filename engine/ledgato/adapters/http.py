"""Allowlisted HTTP gateway adapter.

The agent chooses an action name, not an arbitrary URL. The adapter owns the
base URL, credentials, and route mapping so a DENY means no network request is
made to the protected service.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib import request

from .base import ExecutionReceipt
from ..models import Action


@dataclass(frozen=True)
class Route:
    method: str
    path: str
    verify_method: str | None = None
    verify_path: str | None = None


class HTTPAdapter:
    name = "http"

    def __init__(
        self,
        *,
        base_url: str,
        routes: dict[str, Route],
        headers: dict[str, str] | None = None,
        timeout: float = 15.0,
        name: str | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.routes = dict(routes)
        self.headers = dict(headers or {})
        self.timeout = timeout
        if name:
            self.name = name

    def discover(self, agent: str) -> set[str]:
        return set(self.routes)

    def execute(self, action: Action) -> ExecutionReceipt:
        route = self.routes.get(action.tool)
        if not route:
            raise ValueError(f"HTTP action '{action.tool}' is not configured")
        body = json.dumps(action.params).encode() if route.method.upper() not in {"GET", "HEAD"} else None
        req = request.Request(
            self._url(route.path, action.params),
            data=body,
            method=route.method.upper(),
            headers={"Content-Type": "application/json", **self.headers},
        )
        with request.urlopen(req, timeout=self.timeout) as resp:  # nosec - URL is administrator-configured
            raw = resp.read().decode()
            parsed = _json_or_text(raw)
            return ExecutionReceipt(
                adapter=self.name,
                action=action.tool,
                executed=True,
                status=str(resp.status),
                external_id=resp.headers.get("X-Request-Id") or resp.headers.get("X-GitHub-Request-Id"),
                result={"body": parsed, "headers": {"content-type": resp.headers.get("Content-Type")}},
            )

    def verify(self, action: Action, receipt: ExecutionReceipt) -> dict[str, Any]:
        route = self.routes[action.tool]
        if not route.verify_path:
            return {"verified": receipt.executed, "method": "execution_receipt", "status": receipt.status}
        req = request.Request(
            self._url(route.verify_path, action.params),
            method=(route.verify_method or "GET").upper(),
            headers=self.headers,
        )
        with request.urlopen(req, timeout=self.timeout) as resp:  # nosec - URL is administrator-configured
            raw = resp.read().decode()
            return {
                "verified": 200 <= resp.status < 300,
                "method": "post_action_readback",
                "status": resp.status,
                "body": _json_or_text(raw),
            }

    def _url(self, path: str, params: dict[str, Any]) -> str:
        rendered = path
        for key, value in params.items():
            rendered = rendered.replace("{" + key + "}", str(value))
        if "{" in rendered or "}" in rendered:
            raise ValueError(f"missing route parameter for '{path}'")
        if not rendered.startswith("/"):
            rendered = "/" + rendered
        return self.base_url + rendered


def _json_or_text(raw: str) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw
