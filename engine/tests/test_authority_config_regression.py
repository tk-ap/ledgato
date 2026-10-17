"""Regression checks for authorization configuration ambiguity.

These tests deliberately include a once-reported fail-open configuration case.
They do NOT substitute for provider-backed / credential-custody verification.
"""
import pytest
from ledgato.models import parse_policy


def test_plural_deny_tools_cannot_silently_be_ignored():
    p = parse_policy({"agent": "runner", "allow_tool": ["github.pull.merge"],
                      "deny_tools": ["github.pull.merge"], "impact_max": "destructive"})
    assert "github.pull.merge" in p.deny_tools


def test_plural_approve_tools_cannot_silently_be_ignored():
    p = parse_policy({"agent": "runner", "allow_tool": ["github.pull.merge"],
                      "approve_tools": ["github.pull.merge"], "impact_max": "destructive"})
    assert "github.pull.merge" in p.approval_tools


def test_unknown_policy_key_rejected_instead_of_disarming_gate():
    with pytest.raises(ValueError, match="unknown policy key"):
        parse_policy({"agent": "runner", "allow_tool": ["github.pull.merge"],
                      "approove_tool": ["github.pull.merge"]})


def test_conflicting_allow_aliases_narrow_instead_of_widen():
    p = parse_policy({"agent": "runner", "allow_tool": [],
                      "allow_tools": ["github.pull.merge"]})
    assert p.allow_tools == set()


def test_conflicting_deny_and_approve_aliases_union():
    p = parse_policy({"agent": "runner", "deny_tool": ["one"],
                      "deny_tools": ["two"], "approve_tool": ["three"],
                      "approve_tools": ["four"]})
    assert p.deny_tools == {"one", "two"}
    assert p.approval_tools == {"three", "four"}
