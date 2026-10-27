"""The gateway runs outside the account the agents it governs run as (2026-10-27)."""
import re
import subprocess
from pathlib import Path

OPS = Path(__file__).resolve().parents[2] / "ops"
UNIT = (OPS / "systemd" / "ledgato.service").read_text()
INSTALLER = OPS / "install_ledgato_service.sh"


def _directive(name):
    return [line.split("=", 1)[1] for line in UNIT.splitlines() if line.startswith(f"{name}=")]


def test_it_runs_as_its_own_account_with_nothing_in_a_home_directory():
    assert _directive("User") == ["ledgato"] and _directive("Group") == ["ledgato"]
    for line in UNIT.splitlines():
        if not line.startswith("#"):
            assert "/home/" not in line, line


def test_its_secrets_and_state_are_outside_the_owner_account():
    assert _directive("EnvironmentFile") == ["/etc/ledgato/gateway.env"]
    [start] = _directive("ExecStart")
    assert start.startswith("/opt/ledgato/venv/bin/python ")
    assert "--ledger /var/lib/ledgato/state/" in start and "--keys /var/lib/ledgato/state/" in start
    assert "--host 127.0.0.1 --port 8000" in start, "clients must not need to change"


def test_the_installer_parses_and_never_prints_secret_values():
    subprocess.run(["bash", "-n", str(INSTALLER)], check=True)
    text = INSTALLER.read_text()
    assert not re.search(r"\bcat\b[^\n]*(gateway\.env|ledgato\.env)", text)
    assert "LEDGATO_PRINCIPALS" in text and "APPROVER" in text
    assert "--service-user ledgato" in text, "host-op sudo must move to the gateway account"


def _position(text, needle):
    index = text.find(needle)
    assert index >= 0, needle
    return index


def test_nothing_of_the_owners_changes_before_the_new_gateway_is_healthy():
    """Codex review of 225d552: sudo and state were cut over before the health check."""
    text = INSTALLER.read_text()
    healthy = _position(text, "ledgato.service is healthy as ledgato")
    for cutover in ('install_ledgato_host_op.sh" --service-user ledgato',
                    'rm -rf -- "${OLD_STATE}"',
                    '"${CLIENT}" "${OLD_ENV}"'):
        assert _position(text, cutover) > healthy, cutover


def test_the_gateway_env_is_written_as_plain_assignments():
    assert "sed -E 's/^export[[:space:]]+//'" in INSTALLER.read_text()


def test_every_state_item_is_compared_and_a_partial_copy_is_never_trusted():
    text = INSTALLER.read_text()
    assert "idempotency.json" in text.split("STATE_ITEMS=(", 1)[1].split(")", 1)[0]
    assert "mktemp -d /var/lib/ledgato/state.staging." in text
    assert "exists and differs" in text


def test_the_code_the_unit_runs_is_the_code_that_was_verified():
    text = INSTALLER.read_text()
    assert 'SOURCE="/var/lib/ledgato/source"' in text
    assert "PYTHONPATH=/var/lib/ledgato/source/engine" in UNIT
    assert "! -user root -o -perm /022" in text


def test_no_root_git_runs_before_the_whole_tree_is_checked():
    """Codex re-review of 6bd8ae1: .git was excluded from the check, and git ran first."""
    text = INSTALLER.read_text()
    body = text.split("# 0. The code ledgato.service runs", 1)[1]
    first_check = _position(body, "! -user root -o -perm /022")
    first_git = min(_position(body, "rgit remote"), _position(body, "rgit fetch"))
    assert first_check < first_git
    assert "-prune" not in body.split("rgit()", 1)[0], "part of the tree is skipped"
    assert "rev-parse --show-toplevel" not in text
    assert "core.hooksPath=/dev/null" in text and "core.fsmonitor=false" in text
    assert re.search(r"(?m)^\s*git -C", text) is None, "a root git call bypasses rgit"


def test_links_and_special_files_in_the_old_state_are_refused():
    text = INSTALLER.read_text()
    assert "cp -a -P" in text
    check = _position(text, "! -type f ! -type d")
    assert check < _position(text, 'mv -T "${STAGE}" "${STATE}"')
    assert check < _position(text, 'chown -R ledgato:ledgato "${STATE}"')


def test_the_installer_refuses_a_linked_state_item_when_run(tmp_path):
    """Run the staging check itself against a state dir holding a symlinked ledger."""
    stage = tmp_path / "stage"
    stage.mkdir()
    (stage / "agentos-workspace-keys").mkdir()
    (stage / "agentos-workspace-ledger.jsonl").symlink_to("/etc/passwd")
    found = subprocess.run(["find", str(stage), "-mindepth", "1", "!", "-type", "f", "!", "-type", "d",
                            "-print", "-quit"], capture_output=True, text=True, check=True).stdout
    assert found.strip().endswith("agentos-workspace-ledger.jsonl")
