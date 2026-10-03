import pytest
from fastapi.testclient import TestClient

from ledgato.adapters.base import ExecutionReceipt
from ledgato.api import create_app
from ledgato.principals import PrincipalRegistry
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


def build_app(tmp_path, adapter):
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
        adapters={"fake": adapter},
        principals=PrincipalRegistry(
            [
                ("ops-agent", "agent", "agent-key"),
                ("owner", "approver", "approver-key"),
                ("owner", "admin", "admin-key"),
            ]
        ),
    )


@pytest.fixture()
def setup(tmp_path):
    adapter = FakeAdapter()
    app = build_app(tmp_path, adapter)
    return TestClient(app), adapter


def headers():
    """Credential of the governed agent principal."""
    return {"Authorization": "Bearer agent-key"}


def approver_headers():
    return {"Authorization": "Bearer approver-key"}


def admin_headers():
    return {"Authorization": "Bearer admin-key"}


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
        headers=approver_headers(),
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
        headers=admin_headers(),
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
        headers=admin_headers(),
        json={"revoked_by": "owner", "reason": "task complete"},
    )
    assert revoked.status_code == 200
    assert revoked.json()["revoked_at"] is not None


def test_gateway_api_replays_same_operation_without_second_execution(setup):
    client, adapter = setup
    payload = {
        "agent": "ops-agent",
        "adapter": "fake",
        "task_id": "t-idem",
        "idempotency_key": "merge-pr-123",
        "action": {"tool": "fake.safe", "impact": "write"},
    }

    first = client.post("/v1/gateway/execute", headers=headers(), json=payload)
    second = client.post("/v1/gateway/execute", headers=headers(), json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["idempotent_replay"] is False
    assert second.json()["idempotent_replay"] is True
    assert second.json()["idempotency_key"] == "merge-pr-123"
    assert second.json()["attestation_id"] == first.json()["attestation_id"]
    assert adapter.executions == ["fake.safe"]


def test_gateway_api_idempotency_survives_service_recreation(tmp_path):
    first_adapter = FakeAdapter()
    first = TestClient(build_app(tmp_path, first_adapter))
    payload = {
        "agent": "ops-agent",
        "adapter": "fake",
        "task_id": "t-restart",
        "idempotency_key": "operation-after-restart",
        "action": {"tool": "fake.safe", "impact": "write"},
    }

    original = first.post("/v1/gateway/execute", headers=headers(), json=payload)
    assert original.status_code == 200
    assert first_adapter.executions == ["fake.safe"]

    second_adapter = FakeAdapter()
    second = TestClient(build_app(tmp_path, second_adapter))
    replay = second.post("/v1/gateway/execute", headers=headers(), json=payload)

    assert replay.status_code == 200
    assert replay.json()["idempotent_replay"] is True
    assert replay.json()["attestation_id"] == original.json()["attestation_id"]
    assert second_adapter.executions == []



def test_decision_prompt_is_channel_neutral_redacted_and_bound_to_exact_action(setup):
    client, adapter = setup
    pending = client.post(
        "/v1/gateway/execute",
        headers=headers(),
        json={
            "agent": "ops-agent",
            "adapter": "fake",
            "task_id": "t-prompt",
            "requested_by": "agent-os",
            "action": {
                "tool": "fake.risky",
                "domain": "prod::billing",
                "impact": "destructive",
                "intent": "perform one bounded operation",
                "params": {"record_id": "42", "api_token": "never-render-me"},
            },
        },
    )
    assert pending.status_code == 200
    assert pending.json()["status"] == "APPROVE"
    assert adapter.executions == []

    prompts = client.get("/v1/decision-prompts?status=PENDING", headers=approver_headers())
    assert prompts.status_code == 200
    prompt = next(row for row in prompts.json()["prompts"] if row["task_id"] == "t-prompt")
    assert prompt["version"] == "ledgato.decision-prompt/v1"
    assert prompt["boundary"]["adapter"] == "fake"
    assert prompt["boundary"]["resource"] == "prod::billing"
    assert prompt["requested_action"]["tool"] == "fake.risky"
    facts = {row["key"]: row for row in prompt["requested_action"]["facts"]}
    assert facts["record_id"]["value"] == "42"
    assert facts["api_token"]["value"] == "[redacted]"
    assert "never-render-me" not in str(prompt)
    assert [choice["id"] for choice in prompt["choices"]] == ["allow_once", "deny", "inspect"]
    assert len(prompt["contract_digest"]) == 64

    detail = client.get(f"/v1/decision-prompts/{prompt['decision_id']}", headers=approver_headers())
    assert detail.status_code == 200
    assert detail.json()["contract_digest"] == prompt["contract_digest"]

    agent_read = client.get("/v1/decision-prompts?status=PENDING", headers=headers())
    assert agent_read.status_code == 403



def test_decision_prompt_v2_is_opt_in_and_v1_remains_default(setup):
    client, _adapter = setup
    pending = client.post(
        "/v1/gateway/execute",
        headers=headers(),
        json={
            "agent": "ops-agent",
            "adapter": "fake",
            "task_id": "t-impact-v2",
            "action": {
                "tool": "fake.risky",
                "domain": "prod::billing",
                "impact": "destructive",
                "params": {"record_id": "42"},
            },
            "impact_context": {
                "resolution_state": "PARTIAL",
                "direct_changes": [{
                    "kind": "REPLACE",
                    "subject": "billing-config",
                    "summary": "Replaces the active billing configuration.",
                    "confidence": "KNOWN",
                }],
                "reversibility": {
                    "class": "REVERSIBLE",
                    "summary": "Previous configuration can be restored.",
                    "confidence": "KNOWN",
                },
                "novelty": {
                    "class": "KNOWN_CHANGED",
                    "summary": "Known operation with changed parameters.",
                    "confidence": "KNOWN",
                },
            },
        },
    )
    assert pending.status_code == 200
    approval_id = pending.json()["approval"]["id"]

    v1 = client.get(
        f"/v1/decision-prompts/{approval_id}",
        headers=approver_headers(),
    )
    assert v1.status_code == 200
    assert v1.json()["version"] == "ledgato.decision-prompt/v1"
    assert "impact_envelope_digest" not in v1.json()

    v2 = client.get(
        f"/v1/decision-prompts/{approval_id}?version=v2",
        headers=approver_headers(),
    )
    assert v2.status_code == 200
    prompt = v2.json()
    assert prompt["version"] == "ledgato.decision-prompt/v2"
    assert len(prompt["impact_envelope_digest"]) == 64
    assert prompt["impact_preview"]["direct_changes"][0]["kind"] == "REPLACE"
    assert prompt["impact_preview"]["reversibility"]["class"] == "REVERSIBLE"

    listed = client.get(
        "/v1/decision-prompts?status=PENDING&version=v2",
        headers=approver_headers(),
    )
    assert listed.status_code == 200
    selected = next(
        row for row in listed.json()["prompts"]
        if row["decision_id"] == approval_id
    )
    assert selected["impact_envelope_digest"] == prompt["impact_envelope_digest"]



def test_v2_requester_impact_hints_cannot_self_certify_known(setup):
    client, _adapter = setup
    pending = client.post(
        "/v1/gateway/execute",
        headers=headers(),
        json={
            "agent": "ops-agent",
            "adapter": "fake",
            "task_id": "t-impact-trust",
            "action": {
                "tool": "fake.risky",
                "domain": "prod::billing",
                "impact": "destructive",
            },
            "impact_context": {
                "resolution_state": "COMPLETE",
                "direct_changes": [{
                    "kind": "DELETE",
                    "subject": "billing-records",
                    "summary": "Deletes billing records.",
                    "confidence": "KNOWN",
                }],
                "reversibility": {
                    "class": "IRREVERSIBLE",
                    "summary": "Cannot be restored.",
                    "confidence": "KNOWN",
                },
                "novelty": {
                    "class": "NEW",
                    "summary": "First such action.",
                    "confidence": "KNOWN",
                },
            },
        },
    )
    approval_id = pending.json()["approval"]["id"]
    prompt = client.get(
        f"/v1/decision-prompts/{approval_id}?version=v2",
        headers=approver_headers(),
    ).json()
    assert prompt["impact_preview"]["direct_changes"][0]["confidence"] == "INFERRED"
    assert prompt["impact_preview"]["reversibility"]["confidence"] == "INFERRED"
    assert prompt["impact_preview"]["novelty"]["confidence"] == "INFERRED"


def test_approve_and_resume_rejects_stale_impact_binding(setup):
    client, adapter = setup
    pending = client.post(
        "/v1/gateway/execute",
        headers=headers(),
        json={
            "agent": "ops-agent",
            "adapter": "fake",
            "task_id": "t-impact-binding",
            "action": {
                "tool": "fake.risky",
                "domain": "prod::billing",
                "impact": "destructive",
            },
        },
    ).json()
    approval_id = pending["approval"]["id"]
    prompt = client.get(
        f"/v1/decision-prompts/{approval_id}?version=v2",
        headers=approver_headers(),
    ).json()

    result = client.post(
        f"/v1/approvals/{approval_id}/approve-and-resume",
        headers=approver_headers(),
        json={
            "decided_by": "owner",
            "jit_ttl_seconds": 60,
            "expected_contract_digest": prompt["contract_digest"],
            "expected_impact_digest": "f" * 64,
        },
    )
    assert result.status_code == 409
    assert adapter.executions == []


def test_allow_once_from_prompt_resumes_exact_pending_action(setup):
    client, adapter = setup
    pending = client.post(
        "/v1/gateway/execute",
        headers=headers(),
        json={
            "agent": "ops-agent",
            "adapter": "fake",
            "task_id": "t-inline",
            "action": {"tool": "fake.risky", "domain": "prod::billing", "impact": "destructive"},
        },
    ).json()
    approval_id = pending["approval"]["id"]
    prompt = client.get(f"/v1/decision-prompts/{approval_id}", headers=approver_headers()).json()

    result = client.post(
        f"/v1/approvals/{approval_id}/approve-and-resume",
        headers=approver_headers(),
        json={
            "decided_by": "owner",
            "reason": f"Allow once from inline prompt {prompt['contract_digest'][:12]}",
            "jit_ttl_seconds": 60,
        },
    )
    assert result.status_code == 200
    assert result.json()["execution"]["status"] == "ALLOW"
    assert result.json()["execution"]["executed"] is True
    assert result.json()["execution"]["verification"]["verified"] is True
    assert adapter.executions == ["fake.risky"]
