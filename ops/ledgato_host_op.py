#!/usr/bin/env python3
"""Root-owned Ledgato helper for one bounded AgentOS host operation.

Installed at /usr/local/libexec/ledgato-host-op.  This file intentionally has
no generic command execution mode and accepts exactly one operation token.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any

SOURCE_ROOT = Path("/var/lib/ledgato/agent-os-source")
SOURCE_PARENT = SOURCE_ROOT.parent
SOURCE_BUNDLE = Path("/var/lib/ledgato/agent-os-main.bundle")
RUNTIME_ROOT = Path("/home/agentos/.local/share/agent-os/runtime")
REMOTE = "https://github.com/tk-ap/agent-os.git"

UNIT_FILES = (
    (
        "runtime/systemd/agentos-runtime-checkout.service",
        "/etc/systemd/system/agentos-runtime-checkout.service",
    ),
    (
        "runtime/systemd/agentos-runtime-checkout.timer",
        "/etc/systemd/system/agentos-runtime-checkout.timer",
    ),
    (
        "runtime/systemd/agentos-board-projection.service",
        "/etc/systemd/system/agentos-board-projection.service",
    ),
    (
        "runtime/systemd/agentos-board-projection.timer",
        "/etc/systemd/system/agentos-board-projection.timer",
    ),
    (
        "runtime/systemd/agentos-workspace-board-publisher.service",
        "/etc/systemd/system/agentos-workspace-board-publisher.service",
    ),
    (
        "runtime/systemd/agentos-board-projection.service.d/20-workspace-board-publisher.conf",
        "/etc/systemd/system/agentos-board-projection.service.d/20-workspace-board-publisher.conf",
    ),
    (
        "runtime/systemd/agentos-youtube-ingestion.service",
        "/etc/systemd/system/agentos-youtube-ingestion.service",
    ),
    (
        "runtime/systemd/agentos-youtube-ingestion.timer",
        "/etc/systemd/system/agentos-youtube-ingestion.timer",
    ),
)

RUNTIME_EXECUTABLES = (
    (
        "runtime/agentos_runtime_sync.sh",
        "/usr/local/libexec/agentos-runtime-sync",
    ),
)

VERIFY_UNITS = (
    "runtime/systemd/agentos-runtime-checkout.service",
    "runtime/systemd/agentos-runtime-checkout.timer",
    "runtime/systemd/agentos-board-projection.service",
    "runtime/systemd/agentos-board-projection.timer",
    "runtime/systemd/agentos-workspace-board-publisher.service",
    "runtime/systemd/agentos-youtube-ingestion.service",
    "runtime/systemd/agentos-youtube-ingestion.timer",
)

ENABLED_TIMERS = (
    "agentos-runtime-checkout.timer",
    "agentos-board-projection.timer",
    "agentos-youtube-ingestion.timer",
)

OPERATIONS = {"agentos-runtime-activate", "agentos-runtime-status"}


class HostOperationError(RuntimeError):
    pass


def _run(
    argv: list[str],
    *,
    check: bool = True,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        argv,
        cwd=str(cwd) if cwd else None,
        check=False,
        capture_output=True,
        text=True,
        env={
            "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
            "LANG": "C.UTF-8",
            "HOME": "/root",
            "GIT_TERMINAL_PROMPT": "0",
        },
    )
    if check and completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()[:3000]
        raise HostOperationError(
            f"command failed ({completed.returncode}): {' '.join(argv)}"
            + (f": {detail}" if detail else "")
        )
    return completed


def _require_root() -> None:
    if os.geteuid() != 0:
        raise HostOperationError("ledgato-host-op must run as root")


def _git(*args: str, root: Path = SOURCE_ROOT, check: bool = True) -> subprocess.CompletedProcess[str]:
    return _run(["/usr/bin/git", "-C", str(root), *args], check=check)


def _git_text(*args: str, root: Path = SOURCE_ROOT) -> str:
    return _git(*args, root=root).stdout.strip()


def _assert_root_owned_path(path: Path) -> None:
    info = path.stat()
    if info.st_uid != 0:
        raise HostOperationError(f"source path is not root-owned: {path}")
    if info.st_mode & 0o022:
        raise HostOperationError(f"source path is group/world writable: {path}")


def _bundle_main_sha() -> str:
    if SOURCE_BUNDLE.is_symlink() or not SOURCE_BUNDLE.is_file():
        raise HostOperationError(
            f"staged AgentOS bundle is missing or not a regular file: {SOURCE_BUNDLE}"
        )
    _assert_root_owned_path(SOURCE_BUNDLE)
    listed = _run(
        ["/usr/bin/git", "bundle", "list-heads", str(SOURCE_BUNDLE), "refs/heads/main"]
    ).stdout.strip().splitlines()
    if len(listed) != 1:
        raise HostOperationError("staged AgentOS bundle must expose exactly refs/heads/main")
    parts = listed[0].split()
    if len(parts) != 2 or parts[1] != "refs/heads/main":
        raise HostOperationError("staged AgentOS bundle has an unexpected main ref")
    sha = parts[0].strip()
    if len(sha) != 40 or any(ch not in "0123456789abcdef" for ch in sha.lower()):
        raise HostOperationError("staged AgentOS bundle main is not a full commit SHA")
    return sha


def _ensure_source() -> str:
    SOURCE_PARENT.mkdir(parents=True, exist_ok=True, mode=0o755)
    _assert_root_owned_path(SOURCE_PARENT)
    bundle_sha = _bundle_main_sha()

    if not (SOURCE_ROOT / ".git").exists():
        if SOURCE_ROOT.exists():
            raise HostOperationError(
                f"refusing to replace non-git source path: {SOURCE_ROOT}"
            )
        _run(
            [
                "/usr/bin/git",
                "clone",
                "--no-hardlinks",
                "--branch",
                "main",
                "--single-branch",
                str(SOURCE_BUNDLE),
                str(SOURCE_ROOT),
            ]
        )
        _git("remote", "set-url", "origin", REMOTE)

    _assert_root_owned_path(SOURCE_ROOT)
    _assert_root_owned_path(SOURCE_ROOT / ".git")

    if _git_text("remote", "get-url", "origin") != REMOTE:
        raise HostOperationError("root-owned AgentOS mirror has unexpected origin")
    if _git_text("branch", "--show-current") != "main":
        raise HostOperationError("root-owned AgentOS mirror is not on main")
    if _git_text("status", "--porcelain"):
        raise HostOperationError("root-owned AgentOS mirror is dirty")

    # Refresh only from the owner-staged immutable bundle. Root never receives a
    # GitHub credential and never performs a network fetch.
    _git("update-ref", "-d", "refs/remotes/staged/main", check=False)
    _git(
        "fetch",
        str(SOURCE_BUNDLE),
        "refs/heads/main:refs/remotes/staged/main",
    )
    staged_sha = _git_text("rev-parse", "refs/remotes/staged/main")
    if staged_sha != bundle_sha:
        raise HostOperationError("staged bundle SHA changed during refresh")

    ancestor = _git(
        "merge-base", "--is-ancestor", "HEAD", "refs/remotes/staged/main", check=False
    )
    if ancestor.returncode != 0:
        raise HostOperationError(
            "root-owned AgentOS mirror is not a fast-forward ancestor of staged main"
        )
    _git("merge", "--ff-only", "refs/remotes/staged/main")
    _git("update-ref", "refs/remotes/origin/main", "refs/remotes/staged/main")
    _git("update-ref", "-d", "refs/remotes/staged/main")

    head = _git_text("rev-parse", "HEAD")
    upstream = _git_text("rev-parse", "refs/remotes/origin/main")
    if head != bundle_sha or upstream != bundle_sha:
        raise HostOperationError(
            "root-owned AgentOS mirror did not converge to staged canonical main"
        )
    if _git_text("status", "--porcelain"):
        raise HostOperationError("root-owned AgentOS mirror became dirty after update")
    return head


def _validated_source(relative: str) -> Path:
    source = SOURCE_ROOT / relative
    if source.is_symlink() or not source.is_file():
        raise HostOperationError(f"expected regular non-symlink source file: {relative}")
    resolved = source.resolve()
    try:
        resolved.relative_to(SOURCE_ROOT.resolve())
    except ValueError as exc:
        raise HostOperationError(f"source escaped canonical mirror: {relative}") from exc
    _assert_root_owned_path(source)
    return source


def _install_units() -> None:
    # systemd-analyze verify resolves absolute ExecStart paths. Install the
    # fixed root-owned runtime executable first so verification validates the
    # real final command path instead of failing merely because this is the
    # first activation on the host.
    for relative, destination_text in RUNTIME_EXECUTABLES:
        source = _validated_source(relative)
        destination = Path(destination_text)
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
        _run(
            [
                "/usr/bin/install",
                "-o",
                "root",
                "-g",
                "root",
                "-m",
                "0755",
                str(source),
                str(destination),
            ]
        )

    verify_paths = [str(_validated_source(relative)) for relative in VERIFY_UNITS]
    _run(["/usr/bin/systemd-analyze", "verify", *verify_paths])

    for relative, destination_text in UNIT_FILES:
        source = _validated_source(relative)
        destination = Path(destination_text)
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
        _run(
            [
                "/usr/bin/install",
                "-o",
                "root",
                "-g",
                "root",
                "-m",
                "0644",
                str(source),
                str(destination),
            ]
        )


def _runtime_git_text(*args: str) -> str | None:
    if not (RUNTIME_ROOT / ".git").exists():
        return None
    # The privileged helper reads an account-owned checkout. Git correctly
    # rejects cross-owner repositories by default, so allow exactly this fixed
    # runtime path for this one read-only invocation instead of changing any
    # global safe.directory configuration.
    completed = _run(
        [
            "/usr/bin/git",
            "-c",
            f"safe.directory={RUNTIME_ROOT}",
            "-C",
            str(RUNTIME_ROOT),
            *args,
        ],
        check=False,
    )
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()


def _unit_state(unit: str, verb: str) -> str:
    completed = _run(["/usr/bin/systemctl", verb, unit], check=False)
    value = (completed.stdout or completed.stderr or "").strip().splitlines()
    return value[-1] if value else f"exit:{completed.returncode}"


def _status(*, mirror_sha: str | None = None) -> dict[str, Any]:
    if mirror_sha is None and (SOURCE_ROOT / ".git").exists():
        try:
            mirror_sha = _git_text("rev-parse", "HEAD")
        except Exception:
            mirror_sha = None

    runtime_sha = _runtime_git_text("rev-parse", "HEAD")
    runtime_branch = _runtime_git_text("branch", "--show-current")
    runtime_origin = _runtime_git_text("remote", "get-url", "origin")
    runtime_dirty = _runtime_git_text("status", "--porcelain")

    timers = {
        timer: {
            "active": _unit_state(timer, "is-active"),
            "enabled": _unit_state(timer, "is-enabled"),
        }
        for timer in ENABLED_TIMERS
    }

    runtime_valid = bool(
        runtime_sha
        and runtime_branch == "main"
        and runtime_origin == REMOTE
        and runtime_dirty == ""
    )
    timers_valid = all(
        state["active"] == "active" and state["enabled"] in {"enabled", "static"}
        for state in timers.values()
    )
    revision_match = bool(mirror_sha and runtime_sha and mirror_sha == runtime_sha)

    return {
        "operation": "agentos-runtime-status",
        "status": "ok" if runtime_valid and timers_valid and revision_match else "degraded",
        "healthy": bool(runtime_valid and timers_valid and revision_match),
        "mirror_sha": mirror_sha,
        "runtime_sha": runtime_sha,
        "runtime": {
            "branch": runtime_branch,
            "origin": runtime_origin,
            "dirty": None if runtime_dirty is None else bool(runtime_dirty),
            "valid": runtime_valid,
        },
        "timers": timers,
        "revision_match": revision_match,
    }


def _activate() -> dict[str, Any]:
    mirror_sha = _ensure_source()
    _install_units()
    _run(["/usr/bin/systemctl", "daemon-reload"])

    # The old publisher timer was intentionally retired in AgentOS #232.
    _run(
        ["/usr/bin/systemctl", "disable", "--now", "agentos-workspace-board-publisher.timer"],
        check=False,
    )

    # Provision/update the account-owned runtime before any runtime service uses it.
    _run(["/usr/bin/systemctl", "start", "agentos-runtime-checkout.service"])

    # The ingestion service writes only to this fixed runtime-owned state path.
    # Create it here rather than granting the service write access to a broader
    # /var/lib parent.
    _run([
        "/usr/bin/install", "-d", "-o", "agentos", "-g", "agentos", "-m", "0750",
        "/var/lib/agent-os/youtube-ingestion",
    ])

    _run(["/usr/bin/systemctl", "enable", "--now", *ENABLED_TIMERS])

    # Force one bounded ingestion pass now. A missing transcript is represented
    # by the worker as NEEDS_REVIEW; transport/acquisition failures fail closed.
    _run(["/usr/bin/systemctl", "start", "agentos-youtube-ingestion.service"])

    # Force one bounded projection now; its OnSuccess hook publishes the matching
    # snapshot through the existing publisher service.
    _run(["/usr/bin/systemctl", "start", "agentos-board-projection.service"])

    status = _status(mirror_sha=mirror_sha)
    if not status["healthy"]:
        raise HostOperationError(
            "activation completed commands but post-action status is not healthy"
        )
    return {
        **status,
        "operation": "agentos-runtime-activate",
        "status": "ok",
        "activated": True,
    }


def run_operation(operation: str) -> dict[str, Any]:
    _require_root()
    if operation not in OPERATIONS:
        raise HostOperationError(f"unsupported operation: {operation}")
    if operation == "agentos-runtime-status":
        return _status()
    return _activate()


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1 or args[0] not in OPERATIONS:
        print(
            json.dumps(
                {
                    "status": "error",
                    "error": "expected exactly one allowlisted operation",
                    "allowed": sorted(OPERATIONS),
                },
                sort_keys=True,
            )
        )
        return 64

    try:
        result = run_operation(args[0])
    except Exception as exc:
        print(
            json.dumps(
                {
                    "operation": args[0],
                    "status": "error",
                    "error": str(exc),
                },
                sort_keys=True,
            )
        )
        return 1

    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
