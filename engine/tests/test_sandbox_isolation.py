"""Regression for LAB-001 — sandbox credential leakage.

A bwrap sandbox built the obvious way still handed the confined agent the
gateway credential: `--clearenv` clears the *child's* environment, but the
bwrap supervisor becomes PID 1 inside the namespace and retains the launching
environment, which /proc/1/environ exposes.

These tests use a synthetic sentinel. No real credential is involved.
"""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.sandbox

SENTINEL = "FAKE-ghp-DUMMY-NEVER-REAL-0000000000000000"
REPO_ROOT = Path(__file__).resolve().parents[2]
SANDBOX = REPO_ROOT / "lab" / "sandbox.sh"
PROBE = REPO_ROOT / "lab" / "probe.sh"


@pytest.fixture()
def lab_dirs(tmp_path):
    secrets = tmp_path / "gateway-secrets"
    secrets.mkdir()
    (secrets / "github_token").write_text(SENTINEL + "\n")
    work = tmp_path / "agent-work"
    work.mkdir()
    shutil.copy(PROBE, work / "probe.sh")
    os.chmod(work / "probe.sh", 0o755)
    return secrets, work


def run_probe(work, secrets, env):
    return subprocess.run(
        [str(SANDBOX), str(work), "/bin/sh", "/home/agent/work/probe.sh", str(secrets)],
        capture_output=True, text=True, env=env, timeout=60,
    )


def parse(stdout):
    out = {}
    for line in stdout.strip().splitlines():
        if "|" in line:
            k, v = line.split("|", 1)
            out[k] = v
    return out


def test_probe_detects_leakage_when_unsandboxed(lab_dirs):
    """Control. A probe that cannot detect a leak proves nothing."""
    secrets, work = lab_dirs
    env = {**os.environ, "LEDGATO_GITHUB_TOKEN": SENTINEL}
    result = subprocess.run(
        ["/bin/sh", str(PROBE), str(secrets)],
        capture_output=True, text=True, env=env, timeout=60,
    )
    vectors = parse(result.stdout)
    assert vectors["env-vars"] == "LEAKED"
    assert vectors["secret-file-by-path"] == "LEAKED"


def test_sandbox_blocks_every_leakage_vector(lab_dirs):
    secrets, work = lab_dirs
    env = {k: v for k, v in os.environ.items() if k != "LEDGATO_GITHUB_TOKEN"}
    result = run_probe(work, secrets, env)
    assert result.returncode == 0, result.stderr

    vectors = parse(result.stdout)
    for name in ("env-vars", "secret-file-by-path", "secret-dir-visible", "proc-environ"):
        assert vectors[name] == "blocked", f"{name} leaked: {vectors}"
    assert int(vectors["visible-pids"]) < 20, "sandbox should not see the host process table"


def test_launcher_refuses_when_credential_is_in_its_environment(lab_dirs):
    """The actual LAB-001 fix.

    Without this guard the credential is readable from /proc/1/environ inside
    the sandbox even though --clearenv is passed.
    """
    secrets, work = lab_dirs
    env = {**os.environ, "LEDGATO_GITHUB_TOKEN": SENTINEL}
    result = run_probe(work, secrets, env)
    assert result.returncode != 0
    assert "refusing to launch" in result.stderr
    assert SENTINEL not in result.stdout
    assert SENTINEL not in result.stderr, "the guard must not echo the credential"


@pytest.mark.parametrize("var", ["GITHUB_TOKEN", "GH_TOKEN", "LEDGATO_API_KEY"])
def test_launcher_guards_other_credential_variables(lab_dirs, var):
    secrets, work = lab_dirs
    env = {**os.environ, var: SENTINEL}
    result = run_probe(work, secrets, env)
    assert result.returncode != 0
    assert var in result.stderr
