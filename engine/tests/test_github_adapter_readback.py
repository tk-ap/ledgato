from ledgato.adapters.base import ExecutionReceipt
from ledgato.adapters.github import GitHubAdapter
from ledgato.models import Action


MERGE = "github.pull.merge"


def _adapter() -> GitHubAdapter:
    return GitHubAdapter(repository="owner/repo", token="test-token")


def test_stale_negative_pr_readback_fails_closed(monkeypatch):
    """F-4: stale PR JSON must not override GitHub's merged-status endpoint."""
    adapter = _adapter()

    def fake_call(method, path, body=None, *, fresh=False):
        assert fresh is True
        if path.endswith("/pulls/7"):
            return {
                "merged": False,
                "merged_at": None,
                "merge_commit_sha": None,
                "base": {"ref": "staging"},
                "head": {"sha": "head-sha"},
            }
        raise AssertionError(path)

    monkeypatch.setattr(adapter, "_call", fake_call)
    monkeypatch.setattr(
        adapter,
        "_call_status",
        lambda method, path, *, fresh=False, expected_statuses=None: 204,
    )

    result = adapter.verify_denied(
        Action(tool=MERGE, impact="destructive", params={"pull_number": 7})
    )

    assert result["verified"] is False
    assert result["merged"] is True
    assert result["pr_reports_merged"] is False
    assert result["readback_consistent"] is False


def test_denied_merge_requires_two_unmerged_signals(monkeypatch):
    adapter = _adapter()

    def fake_call(method, path, body=None, *, fresh=False):
        assert fresh is True
        if path.endswith("/pulls/7"):
            return {
                "merged": False,
                "merged_at": None,
                "merge_commit_sha": None,
                "base": {"ref": "main"},
                "head": {"sha": "head-sha"},
            }
        raise AssertionError(path)

    monkeypatch.setattr(adapter, "_call", fake_call)
    monkeypatch.setattr(
        adapter,
        "_call_status",
        lambda method, path, *, fresh=False, expected_statuses=None: 404,
    )

    result = adapter.verify_denied(
        Action(tool=MERGE, impact="destructive", params={"pull_number": 7})
    )

    assert result["verified"] is True
    assert result["merged"] is False
    assert result["pr_reports_merged"] is False
    assert result["readback_consistent"] is True


def test_successful_merge_requires_commit_readback(monkeypatch):
    adapter = _adapter()
    merge_sha = "abc123"

    def fake_call(method, path, body=None, *, fresh=False):
        assert fresh is True
        if path.endswith("/pulls/7"):
            return {
                "merged": True,
                "merged_at": "2026-09-08T15:00:00Z",
                "merge_commit_sha": merge_sha,
                "base": {"ref": "staging"},
                "head": {"sha": "head-sha"},
            }
        if path.endswith(f"/commits/{merge_sha}"):
            return {"sha": merge_sha}
        raise AssertionError(path)

    monkeypatch.setattr(adapter, "_call", fake_call)
    monkeypatch.setattr(
        adapter,
        "_call_status",
        lambda method, path, *, fresh=False, expected_statuses=None: 204,
    )

    receipt = ExecutionReceipt(
        adapter="github",
        action=MERGE,
        executed=True,
        status="merged",
        external_id=merge_sha,
        result={"merged": True, "sha": merge_sha},
    )
    result = adapter.verify(
        Action(tool=MERGE, impact="destructive", params={"pull_number": 7}), receipt
    )

    assert result["verified"] is True
    assert result["merge_commit_exists"] is True
    assert result["receipt_sha_matches"] is True


def test_successful_merge_fails_if_commit_readback_missing(monkeypatch):
    adapter = _adapter()
    merge_sha = "abc123"

    def fake_call(method, path, body=None, *, fresh=False):
        assert fresh is True
        if path.endswith("/pulls/7"):
            return {
                "merged": True,
                "merged_at": "2026-09-08T15:00:00Z",
                "merge_commit_sha": merge_sha,
                "base": {"ref": "staging"},
                "head": {"sha": "head-sha"},
            }
        if path.endswith(f"/commits/{merge_sha}"):
            raise RuntimeError("commit readback unavailable")
        raise AssertionError(path)

    monkeypatch.setattr(adapter, "_call", fake_call)
    monkeypatch.setattr(
        adapter,
        "_call_status",
        lambda method, path, *, fresh=False, expected_statuses=None: 204,
    )

    receipt = ExecutionReceipt(
        adapter="github",
        action=MERGE,
        executed=True,
        status="merged",
        external_id=merge_sha,
        result={"merged": True, "sha": merge_sha},
    )
    result = adapter.verify(
        Action(tool=MERGE, impact="destructive", params={"pull_number": 7}), receipt
    )

    assert result["verified"] is False
    assert result["merge_commit_exists"] is False
