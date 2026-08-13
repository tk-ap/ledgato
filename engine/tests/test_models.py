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


def test_action_severity():
    assert Action(tool="a", impact="readonly").severity() == 1
    assert Action(tool="a", impact="destructive").severity() == 4