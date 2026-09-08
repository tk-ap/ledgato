import yaml
import pytest

from ledgato.models import Action, Policy, load_policies, parse_policy


FENCE = """
policies:
  - agent: ops-agent
    allow_tool:
      - read.docs
      - search
      - github.read
    deny_tool:
      - db.write
    impact_max: readonly
    data_domains:
      - sandbox::*
    on_deny:
      - alert
      - human_review
"""


def test_parse_policy():
    doc = yaml.safe_load(FENCE)
    policies = load_policies(doc)
    assert "ops-agent" in policies
    pol = policies["ops-agent"]
    assert pol.agent == "ops-agent"
    assert "read.docs" in pol.allow_tools
    assert "db.write" in pol.deny_tools
    assert pol.impact_max == "readonly"
    assert pol.data_domains == ["sandbox::*"]
    assert pol.on_deny == ["alert", "human_review"]


def test_plural_aliases_preserve_deny_and_approval_gates():
    pol = parse_policy(
        {
            "agent": "ops-agent",
            "allow_tools": ["github.pull.merge"],
            "deny_tools": ["github.pull.merge"],
            "approve_tools": ["db.write"],
        }
    )
    assert pol.allow_tools == {"github.pull.merge"}
    assert pol.deny_tools == {"github.pull.merge"}
    assert pol.approval_tools == {"db.write"}


def test_dual_aliases_resolve_to_stricter_authority():
    pol = parse_policy(
        {
            "allow_tool": ["read.docs", "github.pull.merge"],
            "allow_tools": ["read.docs"],
            "deny_tool": ["db.write"],
            "deny_tools": ["github.pull.merge"],
            "approve_tool": ["deploy"],
            "approve_tools": ["db.write"],
        }
    )
    assert pol.allow_tools == {"read.docs"}
    assert pol.deny_tools == {"db.write", "github.pull.merge"}
    assert pol.approval_tools == {"deploy", "db.write"}


def test_explicit_empty_allow_alias_cannot_widen_authority():
    pol = parse_policy(
        {
            "allow_tool": [],
            "allow_tools": ["github.pull.merge"],
        }
    )
    assert pol.allow_tools == set()


@pytest.mark.parametrize(
    "bad_key",
    [
        "approve_toolz",
        "deny_toolz",
        "allow_toolz",
        "approval_tool",
        "denny_tool",
    ],
)
def test_unknown_policy_keys_fail_closed(bad_key):
    with pytest.raises(ValueError, match="unknown policy key"):
        parse_policy({"agent": "ops-agent", bad_key: ["github.pull.merge"]})


def test_action_severity():
    assert Action(tool="a", impact="readonly").severity() == 1
    assert Action(tool="a", impact="destructive").severity() == 4
