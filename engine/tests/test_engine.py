import pytest

from ledgato.engine import detect_drift, evaluate_action
from ledgato.models import Action, Policy

POL = Policy(
    agent="ops-agent",
    allow_tools={"read.docs", "search"},
    deny_tools={"db.write"},
    impact_max="readonly",
    data_domains=["sandbox::*"],
)


def test_allow_in_scope():
    d = evaluate_action(POL, Action(tool="read.docs", impact="readonly", domain="sandbox::docs"))
    assert d.allow is True


def test_deny_explicit_deny_list():
    d = evaluate_action(POL, Action(tool="db.write", impact="write", domain="prod::billing"))
    assert d.allow is False
    assert "deny" in d.reason.lower()


def test_deny_tool_not_allowlisted():
    d = evaluate_action(POL, Action(tool="exec.shell", impact="exec"))
    assert d.allow is False


def test_deny_impact_escalation():
    d = evaluate_action(POL, Action(tool="read.docs", impact="destructive"))
    assert d.allow is False
    assert "impact" in d.reason.lower()


def test_deny_domain_out_of_scope():
    d = evaluate_action(POL, Action(tool="search", impact="readonly", domain="prod::customers"))
    assert d.allow is False


def test_drift_detection():
    drift = detect_drift({"read.docs", "search"}, {"read.docs", "db.write"}, "ops-agent")
    assert drift["drift"] is True
    assert drift["undeclared_gains"] == ["db.write"]


def test_no_drift_when_match():
    drift = detect_drift({"read.docs"}, {"read.docs"}, "ops-agent")
    assert drift["drift"] is False