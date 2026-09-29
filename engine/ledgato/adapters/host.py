"""Narrow host-action adapter for owner-approved AgentOS runtime operations.

This adapter is deliberately not a shell adapter.  It maps a tiny set of
Ledgato action names onto fixed invocations of a root-owned helper.  Caller
parameters are never appended to the privileged command.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import subprocess
from typing import Any, Callable

from .base import ExecutionReceipt
from ..models import Action

RUNTIME_ACTIVATE_TOOL = "host.agentos.runtime.activate"
RUNTIME_STATUS_TOOL = "host.agentos.runtime.status"

_OPERATIONS: dict[str, tuple[str, str]] = {
    RUNTIME_ACTIVATE_TOOL: ("agentos-runtime-activate", "write"),
    RUNTIME_STATUS_TOOL: ("agentos-runtime-status", "readonly"),
}


class HostActionAdapter:
    """Execute a fixed host operation through one root-owned helper.

    The surrounding Ledgato policy still decides ALLOW / DENY / APPROVE.
    This class is the final execution seam after ALLOW.  It never accepts a
    caller supplied executable, argument list, path, unit name, or environment.
    """

    name = "host"
    is_live_provider = True

    def __init__(
        self,
        *,
        resource: str,
        helper_path: str = "/usr/local/libexec/ledgato-host-op",
        sudo_path: str = "/usr/bin/sudo",
        timeout_seconds: float = 120.0,
        validate_helper: bool = True,
        runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
    ):
        if not resource or not resource.strip():
            raise ValueError("host adapter requires a non-empty resource")
        helper = Path(helper_path)
        if not helper.is_absolute():
            raise ValueError("host helper path must be absolute")
        sudo = Path(sudo_path)
        if not sudo.is_absolute():
            raise ValueError("sudo path must be absolute")

        self.resource = resource.strip()
        self.boundary_resource = self.resource
        self.helper_path = str(helper)
        self.sudo_path = str(sudo)
        self.timeout_seconds = float(timeout_seconds)
        self._runner = runner or subprocess.run

        if validate_helper:
            self._validate_helper_installation(helper)

    @staticmethod
    def _validate_helper_installation(helper: Path) -> None:
        if helper.is_symlink():
            raise RuntimeError(f"Ledgato host helper must not be a symlink: {helper}")
        try:
            info = helper.stat()
        except FileNotFoundError as exc:
            raise RuntimeError(f"Ledgato host helper is not installed: {helper}") from exc
        if not stat.S_ISREG(info.st_mode):
            raise RuntimeError(f"Ledgato host helper is not a regular file: {helper}")
        if info.st_uid != 0:
            raise RuntimeError(f"Ledgato host helper must be owned by root: {helper}")
        if info.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
            raise RuntimeError(
                f"Ledgato host helper must not be group/world writable: {helper}"
            )
        if not os.access(helper, os.X_OK):
            raise RuntimeError(f"Ledgato host helper is not executable: {helper}")

    def discover(self, agent: str) -> set[str]:
        return set(_OPERATIONS)

    def execute(self, action: Action) -> ExecutionReceipt:
        operation = self._validate_action(action)
        result = self._invoke(operation)
        return ExecutionReceipt(
            adapter=self.name,
            action=action.tool,
            executed=True,
            status=str(result.get("status", "ok")),
            external_id=result.get("runtime_sha"),
            result=result,
        )

    def verify(self, action: Action, receipt: ExecutionReceipt) -> dict[str, Any]:
        self._validate_action(action)
        status = self._invoke("agentos-runtime-status")
        healthy = bool(status.get("healthy"))
        return {
            "verified": healthy,
            "method": "root_helper_status",
            "resource": self.resource,
            "status": status,
        }

    def verify_denied(self, action: Action) -> dict[str, Any]:
        # Critical boundary property: a DENY must not invoke sudo or the helper,
        # even for a harmless status read.  The gateway's non-execution record
        # is the evidence available on this path.
        return {
            "verified": True,
            "method": "gateway_non_execution_receipt",
            "resource": self.resource,
            "helper_invoked": False,
        }

    def _validate_action(self, action: Action) -> str:
        configured = _OPERATIONS.get(action.tool)
        if configured is None:
            raise ValueError(f"host action '{action.tool}' is not allowlisted")

        operation, required_impact = configured
        if action.params:
            raise ValueError("host actions do not accept caller parameters")
        if action.domain != self.resource:
            raise ValueError(
                f"host action domain must exactly match configured resource '{self.resource}'"
            )
        if action.impact != required_impact:
            raise ValueError(
                f"host action '{action.tool}' requires impact '{required_impact}'"
            )
        return operation

    def _invoke(self, operation: str) -> dict[str, Any]:
        # operation originates only from _OPERATIONS or this class's fixed
        # post-action status check.  Never concatenate caller input here.
        if operation not in {"agentos-runtime-activate", "agentos-runtime-status"}:
            raise ValueError(f"unsupported host helper operation '{operation}'")

        completed = self._runner(
            [self.sudo_path, "-n", self.helper_path, operation],
            check=False,
            capture_output=True,
            text=True,
            timeout=self.timeout_seconds,
            env={
                "PATH": "/usr/sbin:/usr/bin:/sbin:/bin",
                "LANG": "C.UTF-8",
            },
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip()[:2000]
            raise RuntimeError(
                f"host helper '{operation}' failed with exit {completed.returncode}"
                + (f": {detail}" if detail else "")
            )
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError("host helper returned malformed JSON") from exc
        if not isinstance(payload, dict):
            raise RuntimeError("host helper returned a non-object result")
        if payload.get("operation") != operation:
            raise RuntimeError("host helper result is not bound to the requested operation")
        return payload
