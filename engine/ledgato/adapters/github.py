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
import stat
import subprocess
import tempfile
from pathlib import Path
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any
from urllib import error, request

from .base import ExecutionReceipt
from ..models import Action


class GitHubAdapter:
    name = "github"
    API = "https://api.github.com"
    is_live_provider = True

    def __init__(self, *, repository: str, token: str, api_url: str | None = None,
                 inbox: str | None = None, mirror: str | None = None, git_url: str | None = None,
                 name: str | None = None):
        if "/" not in repository:
            raise ValueError("repository must be owner/name")
        if name:
            self.name = name
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

    def execute_with_context(self, action: Action, *, agent: str, approved_by: str | None,
                             approval_id: str | None, task_id: str | None = None,
                             grant_id: str | None = None) -> ExecutionReceipt:
        """Merge with Ledgato's approval signed onto the merge commit.

        GitHub records every merge under the token's account, so the merge
        commit itself says which Ledgato task and approval allowed it. Only the
        gateway knows those at execution time, which is why the agent never
        writes them.

        The approved action must say so (`signature: "ledgato"`), so what TK
        approved includes that the merge is signed; the exact message sent is
        recorded in the receipt as `effective_commit_message`, and verify()
        reads it back from GitHub. A rebase merge has no merge commit to carry
        the signature and is refused.
        """
        if action.tool != "github.pull.merge":
            return self.execute(action)
        self._require_own_repository(action)
        if action.params.get("signature") != SIGNATURE:
            raise ValueError("a merge must be approved as signed (params.signature = 'ledgato')")
        if action.params.get("merge_method") == "rebase":
            raise ValueError("a rebase merge leaves no merge commit to carry the approval")
        number = _required_int(action.params, "pull_number")
        via = "owner_card" if approved_by else ("grant" if grant_id else "policy")
        signature = [("Ledgato-Task", task_id),
                     ("Ledgato-Approval", approval_id or grant_id),
                     ("Approved-Via", via),
                     ("Approved-By", approved_by),
                     ("Approved-At", datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")),
                     ("Reviewed-Commit", action.params.get("sha"))]
        message = merge_message(self._pull_commits(number), action.params.get("commit_message"),
                                [f"{key}: {value}" for key, value in signature if value])
        receipt = self.execute(replace(action, params={**action.params, "commit_message": message}))
        receipt.result = {**(receipt.result or {}), "effective_commit_message": message,
                          "signature_trailers": [line for line in message.splitlines()
                                                 if _is_signature(line)]}
        return receipt

    def _pull_commits(self, number: int) -> list[str]:
        """The pull request's commit messages, or none if they can't be read.

        Unreadable commits cost the agents' signatures, not the merge: the
        approval TK gave is still carried out and signed.
        """
        try:
            commits = self._call("GET", f"/repos/{self.repository}/pulls/{number}/commits?per_page=250")
        except RuntimeError:
            return []
        return [str((item.get("commit") or {}).get("message") or "") for item in commits or []]

    def _require_own_repository(self, action: Action) -> None:
        """The approved domain must be this adapter's repository.

        Policy and grants are scoped by domain, and each repository has its
        own adapter. An action naming another repository, or none, could be
        approved under one scope and carried out in another.
        """
        if action.domain != self.repository:
            raise ValueError(f"action domain {action.domain!r} is not this adapter's "
                             f"repository {self.repository!r}")

    def execute(self, action: Action) -> ExecutionReceipt:
        self._require_own_repository(action)
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
        if params.get("force"):
            # Rewriting a branch is not routine work; v1 only adds to one.
            raise ValueError("force-publishing a branch is not allowed")
        bundle = self._take_bundle(Path(str(params.get("bundle") or "")),
                                   str(params.get("sha256") or ""))
        try:
            env = self._git_env()
            if not (self.mirror / "HEAD").exists():
                self.mirror.parent.mkdir(parents=True, exist_ok=True)
                self._git(["init", "--quiet", "--bare", str(self.mirror)], env, cwd=None)
            self._git(["fetch", "--quiet", self.git_url, "+refs/heads/main:refs/remotes/origin/main"], env)
            # The branch's own published history too, so a bundle that only adds
            # to it resolves; a new branch simply has none yet.
            self._git(["fetch", "--quiet", self.git_url,
                       f"+refs/heads/{branch}:refs/remotes/origin/{branch}"], env, missing_ok=True)
            heads = self._git(["bundle", "list-heads", str(bundle)], env).split()
            if heads != [head, f"refs/heads/{branch}"]:
                raise ValueError("the bundle must carry exactly the declared branch at the declared head")
            self._git(["bundle", "verify", "--quiet", str(bundle)], env)
            self._git(["fetch", "--quiet", str(bundle), f"+refs/heads/{branch}:refs/ledgato/{branch}"], env)
            # Never forced: a branch only moves forward through the gateway.
            self._git(["push", "--quiet", self.git_url, f"{head}:refs/heads/{branch}"], env)
        finally:
            bundle.unlink(missing_ok=True)
        return ExecutionReceipt(adapter=self.name, action=action.tool, executed=True,
                                status="published", external_id=head,
                                result={"branch": branch, "head": head})

    def _take_bundle(self, given: Path, sha256: str) -> Path:
        """Copy the agent's bundle into a gateway-private file, once, and check that copy.

        The inbox is agent-writable, so the path could be swapped after any
        check made on it. Read it through one descriptor that refuses
        symlinks, keep those bytes in a file only the gateway can reach, and
        let git see only that file.
        """
        if given.name in {"", ".", ".."} or given.parent.resolve() != self.inbox.resolve():
            raise ValueError("the bundle must be a regular file directly in the gateway inbox")
        try:
            fd = os.open(given, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_NONBLOCK", 0))
        except OSError as exc:
            raise ValueError("the bundle must be a regular file directly in the gateway inbox") from exc
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode):
                raise ValueError("the bundle must be a regular file directly in the gateway inbox")
            if info.st_size > MAX_BUNDLE_BYTES:
                raise ValueError("bundle is too large")
            chunks, size = [], 0
            while chunk := os.read(fd, 1 << 20):
                size += len(chunk)
                if size > MAX_BUNDLE_BYTES:
                    raise ValueError("bundle is too large")
                chunks.append(chunk)
        finally:
            os.close(fd)
            given.unlink(missing_ok=True)
        data = b"".join(chunks)
        if hashlib.sha256(data).hexdigest() != sha256:
            raise ValueError("bundle does not match the declared sha256")
        private = self.mirror.parent / "bundles"
        private.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(private, 0o700)
        fd, name = tempfile.mkstemp(suffix=".bundle", dir=private)
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        return Path(name)

    def _git_env(self) -> dict[str, str]:
        # The token goes in the environment, never the command line, which
        # other accounts can read in the process table.
        basic = base64.b64encode(f"x-access-token:{self.token}".encode()).decode()
        return {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_COUNT": "1",
                "GIT_CONFIG_KEY_0": "http.https://github.com/.extraheader",
                "GIT_CONFIG_VALUE_0": f"AUTHORIZATION: basic {basic}"}

    def _git(self, args: list[str], env: dict[str, str], cwd: Path | None | str = "mirror",
             missing_ok: bool = False) -> str:
        command = ["git", *([] if cwd is None else ["--git-dir", str(self.mirror)]), *args]
        done = subprocess.run(command, env=env, capture_output=True, text=True, timeout=300)
        if done.returncode and missing_ok and "couldn't find remote ref" in done.stderr:
            return ""
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
            signed = None
            expected = (receipt.result or {}).get("signature_trailers")
            if receipt.executed and expected:
                # The provider's own copy of the merge commit must carry every
                # line the gateway signed; a receipt alone is not proof.
                landed = [line for line in str(state.get("merge_commit_message") or "").splitlines()
                          if _is_signature(line)]
                signed = landed == expected
                verified = verified and signed
            return {
                "verified": verified,
                "method": "github_pull_dual_readback",
                **{k: v for k, v in state.items() if k != "merge_commit_message"},
                "receipt_sha": receipt.external_id,
                "receipt_sha_matches": receipt_sha_matches,
                "signature_landed": signed,
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
        merge_commit_message: str | None = None
        if endpoint_merged:
            if merge_commit_sha:
                try:
                    commit = self._call(
                        "GET",
                        f"/repos/{self.repository}/commits/{merge_commit_sha}",
                        fresh=True,
                    )
                    merge_commit_exists = str(commit.get("sha")) == str(merge_commit_sha)
                    merge_commit_message = (commit.get("commit") or {}).get("message")
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
            "merge_commit_message": merge_commit_message,
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


SIGNATURE = "ledgato"
SIGNATURE_KEYS = ("ledgato-", "approved-", "reviewed-commit")


def _is_signature(line: str) -> bool:
    return line.partition(":")[0].strip().lower().startswith(SIGNATURE_KEYS) and ":" in line


# Commit trailers carried from a pull request's commits onto its merge commit:
# the agents' own signatures and GitHub co-author credit.
CARRIED_TRAILERS = ("agent-harness", "agent-model", "co-authored-by")


def merge_message(commits: list[str], body: str | None, signature: list[str]) -> str:
    """A squash body listing the commits, their signatures, then Ledgato's.

    Setting commit_message replaces GitHub's default squash body, which is
    where the agents' trailers would otherwise survive, so they are carried
    here. Any Ledgato-* or Approved-* line an agent wrote is dropped: only the
    gateway signs an approval.
    """
    carried: list[str] = []
    for message in commits:
        for line in message.strip().splitlines():
            key = line.partition(":")[0].strip().lower()
            if key in CARRIED_TRAILERS and line.strip() not in carried:
                carried.append(line.strip())
    if body is None:
        body = "\n".join(f"* {message.strip().splitlines()[0]}" for message in commits if message.strip())
    kept = [line for line in str(body).splitlines() if not _is_signature(line)]
    return "\n".join(part for part in ("\n".join(kept).strip(), "\n".join(carried + signature)) if part)


def _required_int(params: dict[str, Any], key: str) -> int:
    if key not in params:
        raise ValueError(f"missing required parameter '{key}'")
    return int(params[key])
