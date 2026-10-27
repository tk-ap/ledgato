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
