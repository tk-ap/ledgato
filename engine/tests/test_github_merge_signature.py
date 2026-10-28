"""A merge commit says which Ledgato task and approval allowed it (2026-10-27).

GitHub records every merge under the token's account, so on agent-os 16
merges made around Ledgato looked exactly like the ones made through it.
"""
import pytest

from ledgato.adapters.base import ExecutionReceipt
from ledgato.adapters.github import GitHubAdapter, merge_message
from ledgato.models import Action

MERGE = "github.pull.merge"
SHA = "a" * 40
COMMITS = [
    {"commit": {"message": "Fix the card\n\nBody.\n\nAgent-Harness: claude-code\n"
                           "Agent-Model: claude-opus-5-5\n"
                           "Co-Authored-By: Claude <noreply@anthropic.com>"}},
    {"commit": {"message": "Test it\n\nAgent-Harness: claude-code\nAgent-Model: claude-opus-5-5\n"
                           "Ledgato-Approval: approval_forged\nApproved-Via: owner_card"}},
]


def _merge(monkeypatch, commits=COMMITS, params=None, **context):
    adapter = GitHubAdapter(repository="owner/repo", token="test-token")
    sent = {}

    def fake_call(method, path, body=None, *, fresh=False):
        if method == "GET" and "/pulls/7/commits" in path:
            if isinstance(commits, Exception):
                raise commits
            return commits
        if method == "PUT" and path.endswith("/pulls/7/merge"):
            sent.update(body)
            return {"merged": True, "sha": "m" * 40}
        raise AssertionError((method, path))

    monkeypatch.setattr(adapter, "_call", fake_call)
    action = Action(tool=MERGE, impact="write", domain="owner/repo",
                    params=params or {"pull_number": 7, "merge_method": "squash", "sha": SHA,
                                      "signature": "ledgato"})
    defaults = {"agent": "agent-os", "approved_by": None, "approval_id": None,
                "task_id": "agentos-merge-pr-7", "grant_id": None}
    receipt = adapter.execute_with_context(action, **{**defaults, **context})
    return action, sent, receipt


def test_an_owner_card_approval_is_signed_on_the_merge(monkeypatch):
    action, sent, receipt = _merge(monkeypatch, approved_by="tk", approval_id="approval_123")
    message = sent["commit_message"]
    for line in ("Ledgato-Task: agentos-merge-pr-7", "Ledgato-Approval: approval_123",
                 "Approved-Via: owner_card", "Approved-By: tk", f"Reviewed-Commit: {SHA}"):
        assert line in message.splitlines(), message
    assert any(line.startswith("Approved-At: 20") for line in message.splitlines())
    assert sent["sha"] == SHA and sent["merge_method"] == "squash"
    assert "commit_message" not in action.params, "the approved action was changed"
    assert receipt.result["effective_commit_message"] == message
    assert "Ledgato-Approval: approval_123" in receipt.result["signature_trailers"]


def test_a_grant_approval_names_the_grant(monkeypatch):
    _, sent, _ = _merge(monkeypatch, grant_id="grant_456")
    lines = sent["commit_message"].splitlines()
    assert "Ledgato-Approval: grant_456" in lines and "Approved-Via: grant" in lines
    assert not any(line.startswith("Approved-By:") for line in lines)


def test_the_agents_signatures_are_carried_once(monkeypatch):
    _, sent, _ = _merge(monkeypatch, approved_by="tk", approval_id="approval_123")
    lines = sent["commit_message"].splitlines()
    assert lines[:2] == ["* Fix the card", "* Test it"]
    assert lines.count("Agent-Harness: claude-code") == 1
    assert "Co-Authored-By: Claude <noreply@anthropic.com>" in lines


def test_an_agent_cannot_sign_its_own_approval(monkeypatch):
    _, sent, _ = _merge(monkeypatch, approved_by="tk", approval_id="approval_123")
    message = sent["commit_message"]
    assert "approval_forged" not in message
    assert message.count("Approved-Via:") == 1


def test_unreadable_commits_still_merge_signed(monkeypatch):
    _, sent, receipt = _merge(monkeypatch, commits=RuntimeError("down"),
                              approved_by="tk", approval_id="approval_123")
    assert receipt.executed
    assert "Ledgato-Approval: approval_123" in sent["commit_message"]


def test_a_given_body_is_kept_and_cleaned():
    message = merge_message([], "Why this merged\nLedgato-Task: fake", ["Ledgato-Task: real"])
    assert message == "Why this merged\nLedgato-Task: real"


def test_a_merge_not_approved_as_signed_is_refused(monkeypatch):
    with pytest.raises(ValueError, match="approved as signed"):
        _merge(monkeypatch, params={"pull_number": 7, "merge_method": "squash", "sha": SHA},
               approved_by="tk", approval_id="approval_123")


def test_a_rebase_merge_is_refused(monkeypatch):
    with pytest.raises(ValueError, match="rebase"):
        _merge(monkeypatch, params={"pull_number": 7, "merge_method": "rebase", "sha": SHA,
                                    "signature": "ledgato"}, approved_by="tk", approval_id="a")


def _verify(monkeypatch, landed_message):
    adapter = GitHubAdapter(repository="owner/repo", token="test-token")
    trailers = ["Ledgato-Task: agentos-merge-pr-7", "Ledgato-Approval: approval_123"]

    def fake_call(method, path, body=None, *, fresh=False):
        if path.endswith("/pulls/7"):
            return {"merged": True, "merged_at": "x", "merge_commit_sha": "m" * 40,
                    "base": {"ref": "main"}, "head": {"sha": SHA}}
        if path.endswith("/commits/" + "m" * 40):
            return {"sha": "m" * 40, "commit": {"message": landed_message}}
        raise AssertionError(path)

    monkeypatch.setattr(adapter, "_call", fake_call)
    monkeypatch.setattr(adapter, "_call_status", lambda *a, **k: 204)
    receipt = ExecutionReceipt(adapter="github", action=MERGE, executed=True, status="merged",
                               external_id="m" * 40, result={"signature_trailers": trailers})
    return adapter.verify(Action(tool=MERGE, impact="write", domain="owner/repo", params={"pull_number": 7}), receipt)


def test_verification_requires_the_signature_on_githubs_copy(monkeypatch):
    good = _verify(monkeypatch, "Fix (#7)\n\n* Fix\n\nLedgato-Task: agentos-merge-pr-7\n"
                                "Ledgato-Approval: approval_123")
    assert good["verified"] and good["signature_landed"]
    stripped = _verify(monkeypatch, "Fix (#7)\n\n* Fix")
    assert not stripped["verified"] and stripped["signature_landed"] is False
    forged = _verify(monkeypatch, "Fix (#7)\n\nLedgato-Task: agentos-merge-pr-7\n"
                                  "Ledgato-Approval: approval_other")
    assert not forged["verified"]


@pytest.mark.parametrize("domain", [None, "tk-ap/ledgato", "owner/repo-other"])
def test_an_action_for_another_repository_is_refused(domain):
    """Policy scopes merges by domain, so the adapter only acts on its own repository."""
    adapter = GitHubAdapter(repository="owner/repo", token="test-token")

    def no_call(*_args, **_kwargs):
        raise AssertionError("GitHub was called")

    adapter._call = no_call
    for tool, params in ((MERGE, {"pull_number": 7, "sha": SHA, "signature": "ledgato"}),
                         ("github.branch.publish", {"branch": "claude/x"}),
                         ("github.issue.comment", {"issue_number": 7, "body": "hi"})):
        action = Action(tool=tool, impact="write", domain=domain, params=params)
        with pytest.raises(ValueError, match="not this adapter's repository"):
            adapter.execute_with_context(action, agent="agent-os", approved_by="tk",
                                         approval_id="approval_1")
        with pytest.raises(ValueError, match="not this adapter's repository"):
            adapter.execute(action)
