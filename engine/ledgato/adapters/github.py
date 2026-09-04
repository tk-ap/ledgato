"""GitHub adapter for a real protected merge boundary.

The GitHub token belongs to the gateway process. For enforcement to be
non-bypassable, the governed agent must not also possess an equivalent token.
"""
from __future__ import annotations

import json
from typing import Any
from urllib import error, request

from .base import ExecutionReceipt
from ..models import Action


class GitHubAdapter:
    name = "github"
    API = "https://api.github.com"

    def __init__(self, *, repository: str, token: str, api_url: str | None = None):
        if "/" not in repository:
            raise ValueError("repository must be owner/name")
        self.repository = repository
        self.token = token
        self.api_url = (api_url or self.API).rstrip("/")

    def discover(self, agent: str) -> set[str]:
        """Inspect the live repository permission carried by this credential."""
        repo = self._call("GET", f"/repos/{self.repository}")
        permissions = repo.get("permissions") or {}
        capabilities: set[str] = {"github.repo.read"}
        if permissions.get("push") or permissions.get("maintain") or permissions.get("admin"):
            capabilities.add("github.pull.merge")
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

    def verify(self, action: Action, receipt: ExecutionReceipt) -> dict[str, Any]:
        if action.tool == "github.pull.merge":
            number = _required_int(action.params, "pull_number")
            pr = self._call("GET", f"/repos/{self.repository}/pulls/{number}")
            merged = bool(pr.get("merged_at"))
            return {
                "verified": merged == receipt.executed,
                "method": "github_pull_readback",
                "merged": merged,
                "merged_at": pr.get("merged_at"),
                "merge_commit_sha": pr.get("merge_commit_sha"),
            }
        if action.tool == "github.issue.comment":
            comment_id = receipt.external_id
            if not comment_id:
                return {"verified": False, "method": "github_comment_readback", "reason": "missing comment id"}
            comment = self._call("GET", f"/repos/{self.repository}/issues/comments/{comment_id}")
            return {
                "verified": str(comment.get("id")) == str(comment_id),
                "method": "github_comment_readback",
                "id": comment.get("id"),
            }
        return {"verified": False, "reason": "unsupported verification action"}

    def _call(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        data = json.dumps(body).encode() if body is not None else None
        req = request.Request(
            self.api_url + path,
            data=data,
            method=method,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "X-GitHub-Api-Version": "2022-11-28",
                "Content-Type": "application/json",
                "User-Agent": "ledgato-gateway",
            },
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


def _required_int(params: dict[str, Any], key: str) -> int:
    if key not in params:
        raise ValueError(f"missing required parameter '{key}'")
    return int(params[key])
