"""GitHub adapter for a real protected merge boundary.

The GitHub token belongs to the gateway process. For enforcement to be
non-bypassable, the governed agent must not also possess an equivalent token.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any
from urllib import error, request

from .base import ExecutionReceipt
from ..models import Action


class GitHubAdapter:
    name = "github"
    API = "https://api.github.com"
    is_live_provider = True

    def __init__(self, *, repository: str, token: str, api_url: str | None = None,
                 inbox: str | None = None, mirror: str | None = None, git_url: str | None = None):
        if "/" not in repository:
            raise ValueError("repository must be owner/name")
        self.repository = repository
        self.boundary_resource = repository
        self.token = token
        self.api_url = (api_url or self.API).rstrip("/")
        # Branch publishing: agents drop a git bundle in the inbox (a sticky
        # directory they can write to but not list), and the gateway pushes it.
        self.inbox = Path(inbox or "/var/lib/ledgato/inbox")
        self.mirror = Path(mirror or "git-mirror") / (repository.replace("/", "__") + ".git")
        self.git_url = git_url or f"https://github.com/{repository}.git"

    def discover(self, agent: str) -> set[str]:
        """Inspect the live repository permission carried by this credential."""
        repo = self._call("GET", f"/repos/{self.repository}")
        permissions = repo.get("permissions") or {}
        capabilities: set[str] = {"github.repo.read"}
        if permissions.get("push") or permissions.get("maintain") or permissions.get("admin"):
            capabilities.add("github.pull.merge")
            capabilities.add("github.branch.publish")
        if permissions.get("pull") or permissions.get("push") or permissions.get("triage"):
            capabilities.add("github.issue.comment")
        if permissions.get("admin"):
            capabilities.add("github.repo.admin")
        return capabilities

    def execute(self, action: Action) -> ExecutionReceipt:
        if action.tool == "github.pull.merge":
            number = _required_int(action.params, "pull_number")
            body: dict[str, Any] = {}
            for key in ("commit_title", "commit_message", "sha", "merge_method"):
                if action.params.get(key) is not None:
                    body[key] = action.params[key]
            result = self._call("PUT", f"/repos/{self.repository}/pulls/{number}/merge", body)
            return ExecutionReceipt(
                adapter=self.name,
                action=action.tool,
                executed=bool(result.get("merged")),
                status="merged" if result.get("merged") else "not_merged",
                external_id=result.get("sha"),
                result=result,
            )
        if action.tool == "github.branch.publish":
            return self._publish_branch(action)
        if action.tool == "github.issue.comment":
            number = _required_int(action.params, "issue_number")
            body = {"body": str(action.params.get("body", ""))}
            result = self._call("POST", f"/repos/{self.repository}/issues/{number}/comments", body)
            return ExecutionReceipt(
                adapter=self.name,
                action=action.tool,
                executed=True,
                status="created",
                external_id=str(result.get("id")) if result.get("id") is not None else None,
                result={"id": result.get("id"), "html_url": result.get("html_url")},
            )
        raise ValueError(f"unsupported GitHub action '{action.tool}'")

    def _publish_branch(self, action: Action) -> ExecutionReceipt:
        """Push one agent branch from a bundle. Never main, never another ref.

        The agents' own credential is read-only on this repository, so this is
        how their work reaches a pull request; merging it is still
        github.pull.merge. The bundle is checked against the hash and head the
        agent declared, and must carry exactly that one branch.
        """
        params = action.params
        branch = str(params.get("branch") or "")
        head = str(params.get("head") or "")
        if not BRANCH_NAME.fullmatch(branch) or ".." in branch or branch.endswith((".lock", "/")) \
                or branch.lower() in PROTECTED_BRANCHES:
            raise ValueError(f"refusing to publish branch {branch!r}")
        if not re.fullmatch(r"[0-9a-f]{40}", head):
            raise ValueError("head must be the full 40-character commit")
        bundle = Path(str(params.get("bundle") or ""))
        inbox = self.inbox.resolve()
        if bundle.is_symlink() or bundle.resolve().parent != inbox or not bundle.is_file():
            raise ValueError("the bundle must be a regular file directly in the gateway inbox")
        if bundle.stat().st_size > MAX_BUNDLE_BYTES:
            raise ValueError("bundle is too large")
        data = bundle.read_bytes()
        if hashlib.sha256(data).hexdigest() != str(params.get("sha256") or ""):
            raise ValueError("bundle does not match the declared sha256")
        try:
            env = self._git_env()
            if not (self.mirror / "HEAD").exists():
                self.mirror.parent.mkdir(parents=True, exist_ok=True)
                self._git(["init", "--quiet", "--bare", str(self.mirror)], env, cwd=None)
            self._git(["fetch", "--quiet", self.git_url, "+refs/heads/main:refs/remotes/origin/main"], env)
            heads = self._git(["bundle", "list-heads", str(bundle)], env).split()
            if heads != [head, f"refs/heads/{branch}"]:
                raise ValueError("the bundle must carry exactly the declared branch at the declared head")
            self._git(["bundle", "verify", "--quiet", str(bundle)], env)
            self._git(["fetch", "--quiet", str(bundle), f"+refs/heads/{branch}:refs/ledgato/{branch}"], env)
            push = ["push", "--quiet", self.git_url, f"{head}:refs/heads/{branch}"]
            if params.get("force") is True:
                push.insert(1, "--force")
            self._git(push, env)
        finally:
            bundle.unlink(missing_ok=True)
        return ExecutionReceipt(adapter=self.name, action=action.tool, executed=True,
                                status="published", external_id=head,
                                result={"branch": branch, "head": head})

    def _git_env(self) -> dict[str, str]:
        # The token goes in the environment, never the command line, which
        # other accounts can read in the process table.
        basic = base64.b64encode(f"x-access-token:{self.token}".encode()).decode()
        return {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_COUNT": "1",
                "GIT_CONFIG_KEY_0": "http.https://github.com/.extraheader",
                "GIT_CONFIG_VALUE_0": f"AUTHORIZATION: basic {basic}"}

    def _git(self, args: list[str], env: dict[str, str], cwd: Path | None | str = "mirror") -> str:
        command = ["git", *([] if cwd is None else ["--git-dir", str(self.mirror)]), *args]
        done = subprocess.run(command, env=env, capture_output=True, text=True, timeout=300)
        if done.returncode:
            raise RuntimeError(f"git {args[0]} failed: {done.stderr.strip()[:200]}")
        return done.stdout

    def verify(self, action: Action, receipt: ExecutionReceipt) -> dict[str, Any]:
        if action.tool == "github.branch.publish":
            branch = str(action.params.get("branch") or "")
            try:
                found = self._call("GET", f"/repos/{self.repository}/branches/{branch}", fresh=True)
            except RuntimeError as exc:
                return {"verified": False, "method": "github_branch_readback", "reason": str(exc)[:200]}
            sha = (found.get("commit") or {}).get("sha")
            return {"verified": sha == receipt.external_id, "method": "github_branch_readback",
                    "branch": branch, "head_sha": sha}
        if action.tool == "github.pull.merge":
            number = _required_int(action.params, "pull_number")
            state = self._pull_readback(number)
            receipt_sha_matches = (
                not receipt.executed
                or not receipt.external_id
                or state.get("merge_commit_sha") == receipt.external_id
            )
            verified = (
                state["readback_consistent"]
                and state["merged"] == receipt.executed
                and receipt_sha_matches
                and (not state["merged"] or state.get("merge_commit_exists") is True)
            )
            return {
                "verified": verified,
                "method": "github_pull_dual_readback",
                **state,
                "receipt_sha": receipt.external_id,
                "receipt_sha_matches": receipt_sha_matches,
            }
        if action.tool == "github.issue.comment":
            comment_id = receipt.external_id
            if not comment_id:
                return {"verified": False, "method": "github_comment_readback", "reason": "missing comment id"}
            comment = self._call(
                "GET", f"/repos/{self.repository}/issues/comments/{comment_id}", fresh=True
            )
            return {
                "verified": str(comment.get("id")) == str(comment_id),
                "method": "github_comment_readback",
                "id": comment.get("id"),
            }
        return {"verified": False, "reason": "unsupported verification action"}

    def verify_denied(self, action: Action) -> dict[str, Any]:
        if action.tool == "github.pull.merge":
            number = _required_int(action.params, "pull_number")
            state = self._pull_readback(number)
            return {
                "verified": state["readback_consistent"] and not state["merged"],
                "method": "github_pull_denial_dual_readback",
                **state,
                "note": (
                    "Gateway made no merge call; authenticated dual-signal provider "
                    "readback must agree that the PR remains unmerged."
                ),
            }
        return {
            "verified": True,
            "method": "gateway_non_execution_receipt",
            "note": "Gateway did not invoke the downstream adapter for this denied action.",
        }

    def _pull_readback(self, number: int) -> dict[str, Any]:
        """Read decisive merge state from two authenticated GitHub signals.

        GitHub's normal PR representation can be cache-stale. Evidence therefore
        cross-checks it against the dedicated merged-status endpoint. If those
        signals disagree, verification fails closed instead of choosing one.
        Successful merges also require the reported merge commit to exist.
        """
        pr = self._call(
            "GET", f"/repos/{self.repository}/pulls/{number}", fresh=True
        )
        merge_status = self._call_status(
            "GET", f"/repos/{self.repository}/pulls/{number}/merge", fresh=True,
            expected_statuses={204, 404},
        )
        endpoint_merged = merge_status == 204
        pr_merged = bool(pr.get("merged_at")) or bool(pr.get("merged"))
        consistent = endpoint_merged == pr_merged

        merge_commit_sha = pr.get("merge_commit_sha")
        merge_commit_exists: bool | None = None
        if endpoint_merged:
            if merge_commit_sha:
                try:
                    commit = self._call(
                        "GET",
                        f"/repos/{self.repository}/commits/{merge_commit_sha}",
                        fresh=True,
                    )
                    merge_commit_exists = str(commit.get("sha")) == str(merge_commit_sha)
                except RuntimeError:
                    merge_commit_exists = False
            else:
                merge_commit_exists = False

        return {
            "merged": endpoint_merged,
            "pr_reports_merged": pr_merged,
            "merged_status_http": merge_status,
            "readback_consistent": consistent,
            "merged_at": pr.get("merged_at"),
            "merge_commit_sha": merge_commit_sha,
            "merge_commit_exists": merge_commit_exists,
            "base_ref": (pr.get("base") or {}).get("ref"),
            "head_sha": (pr.get("head") or {}).get("sha"),
        }

    def _headers(self, *, fresh: bool = False) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
            "User-Agent": "ledgato-gateway",
        }
        if fresh:
            headers["Cache-Control"] = "no-cache, no-store, max-age=0"
            headers["Pragma"] = "no-cache"
        return headers

    def _call(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        *,
        fresh: bool = False,
    ) -> dict[str, Any]:
        data = json.dumps(body).encode() if body is not None else None
        req = request.Request(
            self.api_url + path,
            data=data,
            method=method,
            headers=self._headers(fresh=fresh),
        )
        try:
            with request.urlopen(req, timeout=20) as resp:  # nosec - fixed GitHub API or admin-configured enterprise API
                raw = resp.read().decode()
                return json.loads(raw) if raw else {}
        except error.HTTPError as exc:
            raw = exc.read().decode()
            try:
                detail = json.loads(raw)
            except json.JSONDecodeError:
                detail = {"message": raw}
            raise RuntimeError(f"GitHub {method} {path} failed ({exc.code}): {detail.get('message', raw)}") from exc

    def _call_status(
        self,
        method: str,
        path: str,
        *,
        fresh: bool = False,
        expected_statuses: set[int] | None = None,
    ) -> int:
        expected = expected_statuses or set()
        req = request.Request(
            self.api_url + path,
            method=method,
            headers=self._headers(fresh=fresh),
        )
        try:
            with request.urlopen(req, timeout=20) as resp:  # nosec - fixed GitHub API or admin-configured enterprise API
                return int(resp.status)
        except error.HTTPError as exc:
            if exc.code in expected:
                return int(exc.code)
            raw = exc.read().decode()
            try:
                detail = json.loads(raw)
            except json.JSONDecodeError:
                detail = {"message": raw}
            raise RuntimeError(f"GitHub {method} {path} failed ({exc.code}): {detail.get('message', raw)}") from exc


BRANCH_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,199}")
PROTECTED_BRANCHES = {"main", "master", "head"}
MAX_BUNDLE_BYTES = 50 * 1024 * 1024


def _required_int(params: dict[str, Any], key: str) -> int:
    if key not in params:
        raise ValueError(f"missing required parameter '{key}'")
    return int(params[key])
