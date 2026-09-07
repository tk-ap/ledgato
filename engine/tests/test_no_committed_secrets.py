"""Directive stage 8: no secret, auth header, or reusable credential in the repo.

The stress test handles real provider credentials, and its own reports quote
command output. That combination is exactly how a token reaches a commit, so
this is enforced rather than promised.
"""
import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

#: The synthetic sentinel used by the sandbox tests. Not a credential.
ALLOWED = {"FAKE-ghp-DUMMY-NEVER-REAL-0000000000000000"}

PATTERNS = {
    "github personal access token": re.compile(r"\bghp_[A-Za-z0-9]{30,}"),
    "github oauth token": re.compile(r"\bgho_[A-Za-z0-9]{30,}"),
    "github fine-grained pat": re.compile(r"\bgithub_pat_[A-Za-z0-9_]{40,}"),
    "github app token": re.compile(r"\bghs_[A-Za-z0-9]{30,}"),
    "aws access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "private key block": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "slack token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}"),
}


def tracked_files() -> list[Path]:
    out = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", "-z"],
        capture_output=True, text=True, check=True,
    )
    return [REPO_ROOT / p for p in out.stdout.split("\0") if p]


@pytest.mark.parametrize("label,pattern", sorted(PATTERNS.items()))
def test_no_credential_pattern_in_tracked_files(label, pattern):
    hits = []
    for path in tracked_files():
        if not path.is_file():
            continue
        try:
            text = path.read_text(errors="ignore")
        except OSError:
            continue
        for match in pattern.findall(text):
            if match not in ALLOWED:
                hits.append(f"{path.relative_to(REPO_ROOT)}: {match[:12]}...")
    assert not hits, f"{label} committed:\n" + "\n".join(hits)


def test_no_authorization_header_values_committed():
    """`Authorization: Bearer <something long>` in a tracked file."""
    bearer = re.compile(r"[Aa]uthorization[\"']?\s*[:=]\s*[\"']?Bearer\s+([A-Za-z0-9._\-]{20,})")
    hits = []
    for path in tracked_files():
        if not path.is_file():
            continue
        try:
            text = path.read_text(errors="ignore")
        except OSError:
            continue
        for value in bearer.findall(text):
            if value not in ALLOWED:
                hits.append(f"{path.relative_to(REPO_ROOT)}: Bearer {value[:8]}...")
    assert not hits, "authorization header value committed:\n" + "\n".join(hits)


def test_scanner_would_catch_a_real_token():
    """Guard the guard: a scanner that matches nothing passes vacuously."""
    fake = "ghp_" + "A" * 36
    assert PATTERNS["github personal access token"].findall(fake) == [fake]


# --- the lab-repo guard itself --------------------------------------------

def _guard_accepts(repo_name: str) -> bool:
    """Mirror of conftest.live_repository's disposability check."""
    name = repo_name.split("/")[-1].lower()
    if name in ("ledgato", "ailhat", "alvira", "agent-os", "ashwood"):
        return False
    segments = set(name.replace("_", "-").split("-"))
    return bool(segments & {"lab", "test", "sandbox", "scratch"})


@pytest.mark.parametrize("repo", [
    "tk-ap/agent-availability",   # 'lab' hides inside 'availability'
    "tk-ap/collaboration-tools",  # and inside 'collaboration'
    "tk-ap/ledgato",
    "tk-ap/ailhat",
    "tk-ap/ashwood-info",
])
def test_guard_rejects_non_disposable_repositories(repo):
    assert not _guard_accepts(repo), f"guard would have accepted {repo}"


@pytest.mark.parametrize("repo", [
    "tk-ap/ledgato-enforcement-lab",
    "tk-ap/ledgato-test",
    "tk-ap/enforcement-sandbox",
])
def test_guard_accepts_genuinely_disposable_repositories(repo):
    assert _guard_accepts(repo)
