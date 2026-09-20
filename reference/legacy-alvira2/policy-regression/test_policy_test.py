"""Tests for the Claw Patrol-style policy regression harness (ledgato test)."""
import json
import pytest
from ledgato.cli import main
from ledgato.policy_test import (
    generate_cases,
    record_fixtures,
    load_fixtures,
    run_policy_test,
    Case,
)


@pytest.fixture
def proj(tmp_path, monkeypatch):
    """Scaffold init in tmp_path and chdir there so relative defaults resolve."""
    monkeypatch.chdir(tmp_path)
    rc = main(["init", "--dir", str(tmp_path), "--difficulty", "1"])
    assert rc == 0
    return tmp_path


def test_record_writes_fixture_files(proj):
    rc = main(["test", "--record", str(proj)])
    assert rc == 0
    fixtures = proj / "fixtures"
    assert (fixtures / "ops-agent.json").exists()
    assert (fixtures / "researcher.json").exists()
    # Every fixture case carries an expected decision.
    for name in ("ops-agent.json", "researcher.json"):
        data = json.loads((fixtures / name).read_text())
        assert all("decision" in c and "tool" in c for c in data["cases"])


def test_generate_cases_covers_intent(proj):
    from ledgato.models import parse_fence
    policy = parse_fence(str(proj / "fence.yaml"))
    cases = generate_cases(policy)
    tools = {(c.agent, c.tool, c.source) for c in cases}
    # an allowed tool (ALLOW), a denied tool, out-of-scope, escalation
    assert ("ops-agent", "db.read", "allow") in tools
    assert ("ops-agent", "db.write", "deny") in tools
    assert ("ops-agent", "shell.exec", "outside") in tools
    # all allow-sourced cases must expect ALLOW
    for c in cases:
        if c.source == "allow":
            assert c.decision == "ALLOW"
        elif c.source in ("deny", "outside", "escalate"):
            assert c.decision == "DENY"


def test_replay_zero_mismatch_on_unchanged_policy(proj, capsys):
    assert main(["test", "--record", str(proj)]) == 0
    rc = main(["test", str(proj)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "0 mismatch(es)" in out


def test_flip_detection_removed_allow_tool(proj, capsys):
    assert main(["test", "--record", str(proj)]) == 0
    fence = proj / "fence.yaml"
    text = fence.read_text()
    # Remove db.read from ops-agent's allow set so the recorded ALLOW flips.
    fence.write_text(text.replace("      - db.read\n", "      - db.read_renamed\n", 1))
    rc = main(["test", str(proj)])
    out = capsys.readouterr().out
    assert rc == 1  # build fails
    assert "want=ALLOW got=DENY" in out
    assert "case=db.read" in out
    assert "1 mismatch(es)" in out


def test_flip_detection_restores_after_revert(proj, capsys):
    assert main(["test", "--record", str(proj)]) == 0
    fence = proj / "fence.yaml"
    original = fence.read_text()
    fence.write_text(original.replace("      - db.read\n", "      - db.read_renamed\n", 1))
    assert main(["test", str(proj)]) == 1
    fence.write_text(original)  # revert
    rc = main(["test", str(proj)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "0 mismatch(es)" in out


def test_record_probes_includes_probe_cases(proj):
    assert main(["test", "--record", str(proj), "--probes"]) == 0
    fixtures = proj / "fixtures"
    data = json.loads((fixtures / "ops-agent.json").read_text())
    assert any(c["source"] == "probe" for c in data["cases"])


def test_run_policy_test_reports_mismatch_count():
    # Unit-level: hand-build a fixture whose recorded verdict is stale.
    import tempfile, os
    from ledgato.policy_test import run_policy_test

    with tempfile.TemporaryDirectory() as fd:
        fence = os.path.join(fd, "fence.yaml")
        with open(fence, "w") as fh:
            fh.write(
                "agents:\n  ops:\n    allow: [db.read]\n"
                "    deny: []\n    max_impact: read\n"
            )
        fixtures = os.path.join(fd, "fixtures")
        os.mkdir(fixtures)
        # Expect ALLOW, but the real (current) policy allows db.read so it
        # matches; now record a stale DENY to force a flip detection.
        with open(os.path.join(fixtures, "ops.json"), "w") as fh:
            json.dump({"agent": "ops", "cases": [
                {"agent": "ops", "tool": "db.read", "impact": "read",
                 "data_domain": None, "decision": "DENY", "source": "allow"}
            ]}, fh)
        checked, mismatches = run_policy_test(fence, fixtures)
        assert checked == 1
        assert len(mismatches) == 1
        assert mismatches[0]["want"] == "DENY"
        assert mismatches[0]["got"] == "ALLOW"


def test_load_fixtures_empty_dir(tmp_path):
    assert load_fixtures(str(tmp_path / "nope")) == []


def test_case_label():
    c = Case("ops", "db.read", "read", "prod", "ALLOW")
    assert c.label() == "ops.db.read"
