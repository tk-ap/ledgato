import pytest
from fastapi.testclient import TestClient

from ledgato.adapters.base import ExecutionReceipt
from ledgato.api import create_app
from ledgato.models import Action


FENCE = """
policies:
  - agent: ops-agent
    allow_tool:
      - fake.safe
      - fake.risky
    deny_tool:
      - fake.evil
    approve_tool:
      - fake.risky
    impact_max: destructive
"""


class FakeAdapter:
    name = "fake"

    def __init__(self):
        self.executions = []

    def discover(self, agent: str):
        return {"fake.safe", "fake.risky", "fake.unexpected"}

    def execute(self, action: Action):
        self.executions.append(action.tool)
        return ExecutionReceipt(adapter="fake", action=action.tool, executed=True, status="ok")

    def verify(self, action: Action, receipt: ExecutionReceipt):
        return {"verified": True, "tool": action.tool}

    def verify_denied(self, action: Action):
        return {"verified": True, "executed": False, "tool": action.tool}


@pytest.fixture()
def setup(tmp_path):
    cfg = tmp_path / "fence.yaml"
    cfg.write_text(FENCE)
    adapter = FakeAdapter()
    app = create_app(
        config_path=cfg,
        ledger_path=tmp_path / "ledger.jsonl",
        key_dir=tmp_path / "keys",
        authority_path=tmp_path / "authority.json",
        approvals_path=tmp_path / "approvals.json",
        adapters={"fake": adapter},
        api_key="test-key",
    )
    return TestClient(app), adapter


def headers():
    return {"Authorization": "Bearer test-key"}


def test_gateway_requires_api_key(setup):
    client, _ = setup
    r = client.post(
        "/v1/gateway/execute",
        json={"agent": "ops-agent", "adapter": "fake", "action": {"tool": "fake.safe"}},
    )
    assert r.status_code == 401


def test_deny_does_not_execute_adapter(setup):
    client, adapter = setup
    r = client.post(
        "/v1/gateway/execute",
        headers=headers(),
        json={"agent": "ops-agent", "adapter": "fake", "task_id": "t1", "action": {"tool": "fake.evil", "impact": "write"}},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "DENY"
    assert r.json()["boundary_crossed"] is False
    assert adapter.executions == []


def test_approval_pause_approve_resume(setup):
    client, adapter = setup
    pending = client.post(
        "/v1/gateway/execute",
        headers=headers(),
        json={"agent": "ops-agent", "adapter": "fake", "task_id": "t2", "requested_by": "agent-os", "action": {"tool": "fake.risky", "impact": "destructive"}},
    ).json()
    assert pending["status"] == "APPROVE"
    assert adapter.executions == []

    approval_id = pending["approval"]["id"]
    approved = client.post(
        f"/v1/approvals/{approval_id}/approve",
        headers=headers(),
        json={"decided_by": "owner", "jit_ttl_seconds": 60},
    ).json()
    assert approved["jit_grant"]["task_id"] == "t2"

    resumed = client.post(
        f"/v1/approvals/{approval_id}/resume",
        headers=headers(),
        json={"resume_token": approved["approval"]["resume_token"]},
    )
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "ALLOW"
    assert adapter.executions == ["fake.risky"]


def test_live_discovery_reports_unexpected_capability(setup):
    client, _ = setup
    result = client.post(
        "/v1/discovery",
        headers=headers(),
        json={"agent": "ops-agent", "adapter": "fake"},
    ).json()
    assert result["drift"]["drift"] is True
    assert result["drift"]["undeclared_gains"] == ["fake.unexpected"]


def test_issue_and_revoke_jit_grant(setup):
    client, _ = setup
    issued = client.post(
        "/v1/authority/grants",
        headers=headers(),
        json={
            "agent": "ops-agent",
            "granted_by": "owner",
            "purpose": "test task",
            "tools": ["fake.safe"],
            "impact_max": "write",
            "task_id": "t3",
            "ttl_seconds": 60,
        },
    )
    assert issued.status_code == 200
    grant = issued.json()
    assert grant["expires_at"] is not None

    revoked = client.post(
        f"/v1/authority/grants/{grant['id']}/revoke",
        headers=headers(),
        json={"revoked_by": "owner", "reason": "task complete"},
    )
    assert revoked.status_code == 200
    assert revoked.json()["revoked_at"] is not None
