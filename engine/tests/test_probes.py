import pytest

from ledgato.models import Policy
from ledgato.probes import run_probes, summarize


def _policy():
    return Policy(
        agent="ops-agent",
        allow_tools={"read.docs", "search", "github.read"},
        deny_tools={"db.write", "exec.shell"},
        impact_max="readonly",
        data_domains=["sandbox::*"],
    )


def test_all_dangerous_probes_denied():
    results = run_probes(_policy())
    for r in results:
        if r.expected_deny:
            assert r.decision.allow is False, f"{r.name} should be denied"
            assert r.passed is True


def test_benign_probe_allowed():
    results = run_probes(_policy())
    benign = [r for r in results if not r.expected_deny]
    assert benign
    assert benign[0].decision.allow is True


def test_injection_intent_denied():
    results = run_probes(_policy())
    inj = [r for r in results if r.name == "injection_intent"]
    assert inj and inj[0].decision.allow is False


def test_summary_shape():
    summary = summarize(run_probes(_policy()))
    assert summary["total"] == len(run_probes(_policy()))
    assert summary["passed"] == summary["total"] - len(summary["gap"])
    assert isinstance(summary["results"], list)