import pytest

from ledgato.authority import AuthorityStore


def test_child_grant_cannot_expand_parent(tmp_path):
    store = AuthorityStore(tmp_path / "authority.json")
    parent = store.issue(
        agent="agent",
        granted_by="owner",
        purpose="task",
        tools={"github.issue.comment"},
        impact_max="write",
        task_id="task-1",
        ttl_seconds=300,
    )

    with pytest.raises(ValueError):
        store.issue(
            agent="agent",
            granted_by="approver",
            purpose="bad escalation",
            tools={"github.pull.merge"},
            impact_max="destructive",
            task_id="task-1",
            parent_grant_id=parent.id,
            ttl_seconds=60,
        )


def test_parent_revocation_invalidates_child(tmp_path):
    store = AuthorityStore(tmp_path / "authority.json")
    parent = store.issue(
        agent="agent",
        granted_by="owner",
        purpose="task",
        tools={"github.pull.merge"},
        impact_max="destructive",
        task_id="task-1",
        ttl_seconds=300,
    )
    child = store.issue(
        agent="agent",
        granted_by="approver",
        purpose="approved merge",
        tools={"github.pull.merge"},
        impact_max="destructive",
        task_id="task-1",
        parent_grant_id=parent.id,
        ttl_seconds=60,
    )

    assert store.validate(child.id) == (True, None)
    store.revoke(parent.id, revoked_by="owner", reason="task cancelled")
    valid, reason = store.validate(child.id)
    assert valid is False
    assert parent.id in reason
