"""Agents' branches reach GitHub through the gateway, never main (2026-10-27).

Their own credential is read-only on agent-os, so this is the only way
their work becomes a pull request, and it cannot touch main.
"""
import hashlib
import subprocess

import pytest

from ledgato.adapters.github import GitHubAdapter
from ledgato.models import Action


def git(*args, cwd=None):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=cwd,
                          check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def world(tmp_path):
    remote = tmp_path / "github.git"
    git("init", "-q", "--bare", "-b", "main", str(remote))
    work = tmp_path / "work"
    git("clone", "-q", str(remote), str(work))
    (work / "a.txt").write_text("a\n")
    git("add", ".", cwd=work)
    git("commit", "-qm", "base", cwd=work)
    git("push", "-q", "origin", "HEAD:main", cwd=work)
    git("checkout", "-qb", "claude/fix", cwd=work)
    (work / "b.txt").write_text("b\n")
    git("add", ".", cwd=work)
    git("commit", "-qm", "fix", cwd=work)
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    adapter = GitHubAdapter(repository="owner/repo", token="test-token", inbox=str(inbox),
                            mirror=str(tmp_path / "mirror"), git_url=str(remote))
    return adapter, work, inbox, remote


def bundle(work, inbox, ref="claude/fix", name="x.bundle"):
    path = inbox / name
    git("bundle", "create", "-q", str(path), f"origin/main..{ref}", cwd=work)
    return path


def publish(adapter, path, branch="claude/fix", head=None, sha=None, **extra):
    params = {"branch": branch, "bundle": str(path), "head": head,
              "sha256": sha or hashlib.sha256(path.read_bytes()).hexdigest(), **extra}
    return adapter.execute(Action(tool="github.branch.publish", impact="write", params=params))


def test_a_branch_is_published_from_its_bundle(world):
    adapter, work, inbox, remote = world
    head = git("rev-parse", "HEAD", cwd=work)
    path = bundle(work, inbox)
    receipt = publish(adapter, path, head=head)
    assert receipt.executed and receipt.status == "published" and receipt.external_id == head
    assert git("rev-parse", "refs/heads/claude/fix", cwd=remote) == head
    assert not path.exists(), "the bundle was left in the inbox"


@pytest.mark.parametrize("branch", ["main", "MAIN", "master", "HEAD", "../main", "a..b", "x.lock", "-f", ""])
def test_main_and_odd_names_are_refused(world, branch):
    adapter, work, inbox, remote = world
    path = bundle(work, inbox)
    before = git("rev-parse", "main", cwd=remote)
    with pytest.raises(ValueError):
        publish(adapter, path, branch=branch, head=git("rev-parse", "HEAD", cwd=work))
    assert git("rev-parse", "main", cwd=remote) == before


def test_a_bundle_carrying_main_is_refused(world):
    adapter, work, inbox, remote = world
    git("branch", "-f", "main", "HEAD", cwd=work)
    path = inbox / "sneaky.bundle"
    git("bundle", "create", "-q", str(path), "origin/main..main", cwd=work)
    with pytest.raises(ValueError, match="exactly the declared branch"):
        publish(adapter, path, head=git("rev-parse", "HEAD", cwd=work))
    assert git("rev-parse", "main", cwd=remote) != git("rev-parse", "HEAD", cwd=work)


def test_a_bundle_outside_the_inbox_is_refused(world, tmp_path):
    adapter, work, inbox, _ = world
    elsewhere = tmp_path / "elsewhere.bundle"
    git("bundle", "create", "-q", str(elsewhere), "origin/main..claude/fix", cwd=work)
    with pytest.raises(ValueError, match="inbox"):
        publish(adapter, elsewhere, head=git("rev-parse", "HEAD", cwd=work))
    link = inbox / "link.bundle"
    link.symlink_to(elsewhere)
    with pytest.raises(ValueError, match="inbox"):
        publish(adapter, link, head=git("rev-parse", "HEAD", cwd=work))


def test_a_changed_bundle_is_refused(world):
    adapter, work, inbox, _ = world
    path = bundle(work, inbox)
    with pytest.raises(ValueError, match="sha256"):
        publish(adapter, path, head=git("rev-parse", "HEAD", cwd=work), sha="0" * 64)


def test_the_declared_head_must_match(world):
    adapter, work, inbox, remote = world
    path = bundle(work, inbox)
    with pytest.raises(ValueError, match="declared head"):
        publish(adapter, path, head="1" * 40)


def test_the_token_never_appears_on_a_command_line(world, monkeypatch):
    adapter, work, inbox, _ = world
    seen = []
    real = subprocess.run

    def spy(command, **kwargs):
        seen.append(command)
        return real(command, **kwargs)

    monkeypatch.setattr(subprocess, "run", spy)
    publish(adapter, bundle(work, inbox), head=git("rev-parse", "HEAD", cwd=work))
    assert seen and not any("test-token" in part for command in seen for part in command)


def test_a_bundle_that_only_adds_to_a_published_branch_resolves(world):
    """The mailbox's coordination branch grows one message at a time."""
    adapter, work, inbox, remote = world
    publish(adapter, bundle(work, inbox), head=git("rev-parse", "HEAD", cwd=work))
    git("fetch", "-q", "origin", cwd=work)
    (work / "c.txt").write_text("c\n")
    git("add", ".", cwd=work)
    git("commit", "-qm", "more", cwd=work)
    path = inbox / "more.bundle"
    git("bundle", "create", "-q", str(path), "claude/fix", "^origin/main", "^origin/claude/fix", cwd=work)
    head = git("rev-parse", "HEAD", cwd=work)
    publish(adapter, path, head=head)
    assert git("rev-parse", "refs/heads/claude/fix", cwd=remote) == head
