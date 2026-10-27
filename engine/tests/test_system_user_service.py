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
