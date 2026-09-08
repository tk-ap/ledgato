"""Stage 4/5 — mandatory auth and separation of duties.

These are the automated spoof tests required by the enforcement stress-test
directive. They target the two confirmed pre-existing defects:

* `_auth` returned successfully when no key was configured (fail-open);
* `agent`, `decided_by`, `granted_by`, `revoked_by` were caller-supplied
  strings, so one shared key let an agent approve its own request.
"""
import pytest
from fastapi.testclient import TestClient

from ledgato.adapters.base import ExecutionReceipt
from ledgato.api import create_app
from ledgato.models import Action
from ledgato.principals import PrincipalRegistry

FENCE = """
policies:
  - agent: ops-agent
    allow_tool:
      - fake.safe
      - fake.risky
    approve_tool:
      - fake.risky
    impact_max: destructive
"""


class FakeAdapter:
    name = "fake"

    def __init__(self):
        self.executions: list[str] = []

    def discover(self, agent: str) -> set[str]:
        return {"fake.safe", "fake.risky"}

    def execute(self, action: Action) -> ExecutionReceipt:
        self.executions.append(action.tool)
        return ExecutionReceipt(
            adapter=self.name, action=action.tool, executed=True,
            status="ok", external_id="r1", result={},
        )

    def verify(self, action, receipt):
        return {"verified": True}

    def verify_denied(self, action):
        return {"verified": True, "executed": False}


def build(tmp_path, adapter=None, **kw):
    cfg = tmp_path / "fence.yaml"
    if not cfg.exists():
        cfg.write_text(FENCE)
    return create_app(
        config_path=cfg,
        ledger_path=tmp_path / "ledger.jsonl",
        key_dir=tmp_path / "keys",
        authority_path=tmp_path / "authority.json",
        approvals_path=tmp_path / "approvals.json",
        idempotency_path=tmp_path / "idempotency.json",
        adapters={"fake": adapter or FakeAdapter()},
        **kw,
    )


def registry():
    return PrincipalRegistry(
        [
            ("ops-agent", "agent", "agent-key"),
            ("other-agent", "agent", "other-agent-key"),
            ("tk", "approver", "approver-key"),
            ("ops", "admin", "admin-key"),
        ]
    )


@pytest.fixture()
def setup(tmp_path):
    adapter = FakeAdapter()
    return TestClient(build(tmp_path, adapter, principals=registry())), adapter


AGENT = {"Authorization": "Bearer agent-key"}
OTHER_AGENT = {"Authorization": "Bearer other-agent-key"}
APPROVER = {"Authorization": "Bearer approver-key"}
ADMIN = {"Authorization": "Bearer admin-key"}


# --- Stage 4: auth must be mandatory and fail closed ----------------------

def test_missing_auth_configuration_fails_closed(tmp_path, monkeypatch):
    """The original bug: no key configured meant no authentication at all."""
    monkeypatch.delenv("LEDGATO_API_KEY", raising=False)
    monkeypatch.delenv("LEDGATO_PRINCIPALS", raising=False)
    with pytest.raises(RuntimeError, match="refuses to start unauthenticated"):
        build(tmp_path)


def test_explicit_opt_out_is_required_for_unauthenticated_instance(tmp_path, monkeypatch):
    monkeypatch.delenv("LEDGATO_API_KEY", raising=False)
    monkeypatch.delenv("LEDGATO_PRINCIPALS", raising=False)
    app = build(tmp_path, require_auth=False)
    assert TestClient(app).get("/health").status_code == 200


@pytest.mark.parametrize(
    "path,payload",
    [
        ("/v1/gateway/execute", {"agent": "ops-agent", "adapter": "fake", "action": {"tool": "fake.safe"}}),
        ("/v1/authority/grants", {"agent": "ops-agent", "granted_by": "ops", "purpose": "p"}),
        ("/v1/approvals/x/approve", {"decided_by": "tk"}),
    ],
)
def test_missing_credentials_rejected(setup, path, payload):
    client, _ = setup
    assert client.post(path, json=payload).status_code == 401


@pytest.mark.parametrize("header", [
    {"Authorization": "Bearer wrong-key"},
    {"Authorization": "agent-key"},          # missing Bearer scheme
    {"Authorization": "Bearer "},
    {"Authorization": ""},
])
def test_invalid_credentials_rejected(setup, header):
    client, _ = setup
    r = client.post(
        "/v1/gateway/execute",
        headers=header,
        json={"agent": "ops-agent", "adapter": "fake", "action": {"tool": "fake.safe"}},
    )
    assert r.status_code == 401


def test_shared_key_still_supported_but_is_an_admin_principal(tmp_path):
    client = TestClient(build(tmp_path, api_key="shared"))
    # A shared key is an admin, so it may administer authority ...
    ok = client.post(
        "/v1/authority/grants",
        headers={"Authorization": "Bearer shared"},
        json={"agent": "ops-agent", "granted_by": "shared-key", "purpose": "p", "tools": ["fake.safe"]},
    )
    assert ok.status_code == 200
    # ... but it is NOT an agent, so it cannot drive governed execution.
    denied = client.post(
        "/v1/gateway/execute",
        headers={"Authorization": "Bearer shared"},
        json={"agent": "ops-agent", "adapter": "fake", "action": {"tool": "fake.safe"}},
    )
    assert denied.status_code == 403


# --- Stage 5: identity comes from the credential, not the body ------------

def test_agent_cannot_execute_as_another_agent(setup):
    """Spoof: authenticate as ops-agent, claim to be other-agent."""
    client, adapter = setup
    r = client.post(
        "/v1/gateway/execute",
        headers=AGENT,
        json={"agent": "other-agent", "adapter": "fake", "task_id": "t", "action": {"tool": "fake.safe", "impact": "write"}},
    )
    assert r.status_code == 403
    assert "does not match authenticated principal" in r.json()["detail"]
    assert adapter.executions == []


def test_agent_cannot_issue_grants(setup):
    client, _ = setup
    r = client.post(
        "/v1/authority/grants",
        headers=AGENT,
        json={"agent": "ops-agent", "granted_by": "ops", "purpose": "self-grant", "tools": ["fake.safe"]},
    )
    assert r.status_code == 403
    assert "may not issue authority grants" in r.json()["detail"]


def test_agent_cannot_revoke_grants(setup):
    client, _ = setup
    issued = client.post(
        "/v1/authority/grants",
        headers=ADMIN,
        json={"agent": "ops-agent", "granted_by": "ops", "purpose": "p", "tools": ["fake.safe"], "ttl_seconds": 60},
    ).json()
    r = client.post(
        f"/v1/authority/grants/{issued['id']}/revoke",
        headers=AGENT,
        json={"revoked_by": "ops", "reason": "cover tracks"},
    )
    assert r.status_code == 403


def test_agent_cannot_approve_its_own_request(setup):
    """The central separation-of-duties property."""
    client, adapter = setup
    pending = client.post(
        "/v1/gateway/execute",
        headers=AGENT,
        json={"agent": "ops-agent", "adapter": "fake", "task_id": "t2", "action": {"tool": "fake.risky", "impact": "destructive"}},
    ).json()
    assert pending["status"] == "APPROVE"
    approval_id = pending["approval"]["id"]

    # Agent credential, claiming to be the human approver.
    spoof = client.post(
        f"/v1/approvals/{approval_id}/approve",
        headers=AGENT,
        json={"decided_by": "tk", "jit_ttl_seconds": 60},
    )
    assert spoof.status_code == 403
    assert "may not decide approvals" in spoof.json()["detail"]
    assert adapter.executions == []


def test_agent_cannot_deny_approvals(setup):
    client, _ = setup
    pending = client.post(
        "/v1/gateway/execute",
        headers=AGENT,
        json={"agent": "ops-agent", "adapter": "fake", "task_id": "t3", "action": {"tool": "fake.risky", "impact": "destructive"}},
    ).json()
    r = client.post(
        f"/v1/approvals/{pending['approval']['id']}/deny",
        headers=AGENT,
        json={"decided_by": "tk", "reason": "no"},
    )
    assert r.status_code == 403


def test_approver_cannot_impersonate_a_different_human(setup):
    client, _ = setup
    pending = client.post(
        "/v1/gateway/execute",
        headers=AGENT,
        json={"agent": "ops-agent", "adapter": "fake", "task_id": "t4", "action": {"tool": "fake.risky", "impact": "destructive"}},
    ).json()
    r = client.post(
        f"/v1/approvals/{pending['approval']['id']}/approve",
        headers=APPROVER,
        json={"decided_by": "someone-else", "jit_ttl_seconds": 60},
    )
    assert r.status_code == 403
    assert "does not match authenticated principal" in r.json()["detail"]


def test_approver_cannot_drive_agent_execution(setup):
    """A human credential must not be usable to launder an agent action."""
    client, adapter = setup
    r = client.post(
        "/v1/gateway/execute",
        headers=APPROVER,
        json={"agent": "ops-agent", "adapter": "fake", "task_id": "t5", "action": {"tool": "fake.safe", "impact": "write"}},
    )
    assert r.status_code == 403
    assert adapter.executions == []


def test_recorded_identity_is_the_credential_not_the_claim(setup):
    """decided_by in the ledger must be the authenticated approver."""
    client, adapter = setup
    pending = client.post(
        "/v1/gateway/execute",
        headers=AGENT,
        json={"agent": "ops-agent", "adapter": "fake", "task_id": "t6", "action": {"tool": "fake.risky", "impact": "destructive"}},
    ).json()
    approved = client.post(
        f"/v1/approvals/{pending['approval']['id']}/approve",
        headers=APPROVER,
        json={"jit_ttl_seconds": 60},   # no decided_by supplied at all
    )
    assert approved.status_code == 200
    assert approved.json()["approval"]["decided_by"] == "tk"


def test_full_legitimate_flow_still_works(setup):
    """Separation of duties must not break the intended path."""
    client, adapter = setup
    pending = client.post(
        "/v1/gateway/execute",
        headers=AGENT,
        json={"agent": "ops-agent", "adapter": "fake", "task_id": "t7", "action": {"tool": "fake.risky", "impact": "destructive"}},
    ).json()
    approval_id = pending["approval"]["id"]
    approved = client.post(
        f"/v1/approvals/{approval_id}/approve",
        headers=APPROVER,
        json={"jit_ttl_seconds": 60},
    ).json()
    resumed = client.post(
        f"/v1/approvals/{approval_id}/resume",
        headers=AGENT,
        json={"resume_token": approved["approval"]["resume_token"]},
    )
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "ALLOW"
    assert adapter.executions == ["fake.risky"]
