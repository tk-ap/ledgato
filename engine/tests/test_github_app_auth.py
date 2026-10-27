"""LEDGATo merges as a GitHub App, so a ruleset on main can admit only it (2026-10-27)."""
import base64
import io
import json

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from ledgato import api
from ledgato.adapters.github import GitHubAdapter, GitHubAppCredential

KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PEM = KEY.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                        serialization.NoEncryption())


class FakeGitHub:
    def __init__(self, permissions=None, repos=("owner/repo",)):
        self.requests = []
        self.permissions = permissions or {"contents": "write", "pull_requests": "write",
                                           "metadata": "read"}
        self.repos = repos
        self.issued = 0

    def __call__(self, req, timeout=None):
        self.requests.append(req)
        self.issued += 1
        body = {"token": f"ghs_test_{self.issued}", "expires_at": "2026-10-27T19:00:00Z",
                "permissions": self.permissions,
                "repositories": [{"full_name": name} for name in self.repos]}
        return io.BytesIO(json.dumps(body).encode())


def _credential(github, now=1_793_120_000.0):  # 2026-10-27T17:33:20Z
    return GitHubAppCredential(app_id="123", installation_id="456", private_key_pem=PEM,
                               repository="owner/repo", opener=github, clock=lambda: now)


def _b64(part):
    return base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))


def test_the_token_request_is_signed_by_the_app_and_limited_to_the_repository():
    github = FakeGitHub()
    assert _credential(github).token() == "ghs_test_1"
    [req] = github.requests
    assert req.full_url == "https://api.github.com/app/installations/456/access_tokens"
    assert json.loads(req.data) == {"repositories": ["repo"]}
    header, claims, signature = req.headers["Authorization"].removeprefix("Bearer ").split(".")
    assert json.loads(_b64(claims))["iss"] == "123"
    KEY.public_key().verify(_b64(signature), f"{header}.{claims}".encode(),
                            padding.PKCS1v15(), hashes.SHA256())


def test_a_live_token_is_reused_and_renewed_before_it_expires():
    github = FakeGitHub()
    now = [1_793_120_000.0]
    credential = GitHubAppCredential(app_id="123", installation_id="456", private_key_pem=PEM,
                                     repository="owner/repo", opener=github, clock=lambda: now[0])
    credential.token()
    credential.token()
    assert github.issued == 1
    now[0] = 1_793_127_600.0 - credential.REFRESH_BEFORE + 1  # 5 minutes before expires_at
    assert credential.token() == "ghs_test_2"


def test_a_token_for_another_repository_is_refused():
    with pytest.raises(RuntimeError, match="does not cover"):
        _credential(FakeGitHub(repos=("owner/other",))).token()


def test_merge_capability_comes_from_the_installation_permissions():
    adapter = GitHubAdapter(repository="owner/repo", app=_credential(FakeGitHub()))
    assert "github.pull.merge" in adapter.discover("agent-os")
    assert "github.repo.admin" not in adapter.discover("agent-os")
    read_only = GitHubAdapter(repository="owner/repo", app=_credential(
        FakeGitHub(permissions={"contents": "read", "pull_requests": "write"})))
    assert "github.pull.merge" not in read_only.discover("agent-os")


def test_requests_carry_the_installation_token():
    adapter = GitHubAdapter(repository="owner/repo", app=_credential(FakeGitHub()))
    assert adapter._headers()["Authorization"] == "Bearer ghs_test_1"


def test_an_adapter_needs_some_credential():
    with pytest.raises(ValueError):
        GitHubAdapter(repository="owner/repo")


def test_the_app_replaces_the_token_when_configured(tmp_path, monkeypatch):
    key_file = tmp_path / "app.pem"
    key_file.write_bytes(PEM)
    monkeypatch.setenv("LEDGATO_GITHUB_REPOSITORY", "owner/repo")
    monkeypatch.setenv("LEDGATO_GITHUB_TOKEN", "personal-token")
    monkeypatch.setenv("LEDGATO_GITHUB_APP_ID", "123")
    monkeypatch.setenv("LEDGATO_GITHUB_APP_INSTALLATION_ID", "456")
    monkeypatch.setenv("LEDGATO_GITHUB_APP_PRIVATE_KEY_FILE", str(key_file))
    adapter = api._default_adapters_from_env()["github"]
    assert adapter.app is not None and adapter.token is None
    monkeypatch.delenv("LEDGATO_GITHUB_APP_ID")
    assert api._default_adapters_from_env()["github"].token == "personal-token"
