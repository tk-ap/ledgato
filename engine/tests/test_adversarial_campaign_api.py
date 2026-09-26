"""API-level proof that /v1/gateway/execute reaches principal + campaign
enforcement, and that trust domains are enforced over HTTP."""
import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from ledgato.adapters.base import ExecutionReceipt
from ledgato.api import create_app
from ledgato.campaign import canonical_digest
from ledgato.models import Action
from ledgato.principals import PrincipalRegistry

ADV = "adv-agent"
OPS = "ops-agent"

FENCE = """
policies:
  - agent: adv-agent
    allow_tools: [fake.safe]
    impact_max: write
  - agent: ops-agent
    allow_tools: [fake.safe]
    impact_max: write
"""


class FakeAdapter:
    name = "fake"

    def __init__(self):
        self.executions = 0

    def discover(self, agent): return {"fake.safe"}

    def execute(self, action):
        self.executions += 1
        return ExecutionReceipt(adapter=self.name, action=action.tool, executed=True,
                                status="ok", external_id=f"r{self.executions}")

    def verify(self, action, receipt): return {"verified": True}

    def verify_denied(self, action): return {"verified": True, "executed": False}


def envelope():
    now = datetime.now(timezone.utc)
    return {
        "schema_version": 1, "campaign_id": "camp-1",
        "authorization": {"authority_ref": "auth-1", "owner": "alvira2",
                          "target_owned_or_authorized": True,
                          "issued_at": (now - timedelta(minutes=1)).isoformat(),
                          "expires_at": (now + timedelta(hours=1)).isoformat()},
        "target": {"id": "t", "environment": "production-equivalent", "interface": "i"},
        "permitted_attack_surface": ["runtime.authorization"],
        "prohibited_surfaces": ["real-user.data"],
        "budget": {"wall_seconds": 900, "max_attempts": 12, "max_parallel_agents": 2},
        "evidence": {"independent_verifier_required": True, "retain_attempt_log": True},
        "response_contract": {"finding_classifications": ["held", "bypass", "indeterminate"],
                              "evidence_refs_required": True},
    }


@pytest.fixture()
def ctx(tmp_path):
    fence = tmp_path / "fence.yaml"
    fence.write_text(FENCE)
    registry = PrincipalRegistry([
        (ADV, "agent", "adversarial", "advsecret"),
        (OPS, "agent", "opssecret"),                       # operational (3-part)
        ("verifier1", "verifier", "verifier", "vsecret"),
        ("approver1", "approver", "apsecret"),
        ("admin1", "admin", "adsecret"),
    ])
    adapter = FakeAdapter()
    app = create_app(
        config_path=fence, ledger_path=tmp_path / "l.jsonl", key_dir=tmp_path / "keys",
        authority_path=tmp_path / "authority.json", approvals_path=tmp_path / "approvals.json",
        idempotency_path=tmp_path / "idem.json", campaigns_path=tmp_path / "campaigns.json",
        adapters={"fake": adapter}, principals=registry,
    )
    return TestClient(app), adapter


def hdr(secret):
    return {"Authorization": f"Bearer {secret}"}


def register_campaign(client, env):
    r = client.post("/v1/campaigns", json={"principal_id": ADV, "envelope": env},
                    headers=hdr("adsecret"))
    assert r.status_code == 200, r.text
    return r.json()


class TestTrustDomainOverHTTP:
    def test_operational_agent_unchanged(self, ctx):
        client, adapter = ctx
        r = client.post("/v1/gateway/execute", headers=hdr("opssecret"),
                        json={"agent": OPS, "adapter": "fake",
                              "action": {"tool": "fake.safe", "impact": "write"}})
        assert r.status_code == 200 and r.json()["status"] == "ALLOW"
        assert adapter.executions == 1

    def test_verifier_cannot_execute(self, ctx):
        client, adapter = ctx
        r = client.post("/v1/gateway/execute", headers=hdr("vsecret"),
                        json={"agent": "verifier1", "adapter": "fake",
                              "action": {"tool": "fake.safe"}})
        assert r.status_code == 403 and adapter.executions == 0

    def test_verifier_cannot_issue_grants(self, ctx):
        client, _ = ctx
        r = client.post("/v1/authority/grants", headers=hdr("vsecret"),
                        json={"agent": ADV, "purpose": "x"})
        assert r.status_code == 403

    def test_verifier_cannot_decide_approvals(self, ctx):
        client, _ = ctx
        r = client.post("/v1/approvals/none/approve", headers=hdr("vsecret"), json={})
        assert r.status_code == 403

    def test_adversarial_without_campaign_is_denied(self, ctx):
        client, adapter = ctx
        r = client.post("/v1/gateway/execute", headers=hdr("advsecret"),
                        json={"agent": ADV, "adapter": "fake",
                              "action": {"tool": "fake.safe", "impact": "write"}})
        assert r.status_code == 200 and r.json()["status"] == "DENY"
        assert r.json()["boundary_crossed"] is False and adapter.executions == 0


class TestCampaignEnforcementOverHTTP:
    def _exec(self, client, env, digest, surface):
        return client.post("/v1/gateway/execute", headers=hdr("advsecret"),
                           json={"agent": ADV, "adapter": "fake",
                                 "action": {"tool": "fake.safe", "impact": "write"},
                                 "campaign_id": env["campaign_id"],
                                 "authority_ref": env["authorization"]["authority_ref"],
                                 "campaign_digest": digest, "attack_surface": surface,
                                 "executor_provider": "claude"})

    def test_valid_campaign_in_scope_reaches_policy_and_allows(self, ctx):
        client, adapter = ctx
        env = envelope(); register_campaign(client, env)
        r = self._exec(client, env, canonical_digest(env), ["runtime.authorization"])
        assert r.status_code == 200 and r.json()["status"] == "ALLOW"
        assert adapter.executions == 1

    def test_over_scope_denies_before_adapter(self, ctx):
        client, adapter = ctx
        env = envelope(); register_campaign(client, env)
        r = self._exec(client, env, canonical_digest(env), ["exfil.secrets"])
        body = r.json()
        assert body["status"] == "DENY" and body["boundary_crossed"] is False
        assert body["executed"] is False and adapter.executions == 0
        entries = client.get("/v1/ledger", headers=hdr("adsecret")).json()["entries"]
        deny = [e for e in entries if e.get("evidence", {}).get("campaign")][-1]
        assert deny["evidence"]["downstream_execute_called"] is False

    def test_evidence_records_principal_and_campaign(self, ctx):
        client, adapter = ctx
        env = envelope(); register_campaign(client, env)
        self._exec(client, env, canonical_digest(env), ["runtime.authorization"])
        entries = client.get("/v1/ledger", headers=hdr("adsecret")).json()["entries"]
        camp = [e for e in entries if (e.get("evidence") or {}).get("campaign")]
        assert camp, "expected campaign evidence in the ledger"
        c = camp[-1]["evidence"]["campaign"]
        assert c["principal_id"] == ADV and c["trust_domain"] == "adversarial"
        assert c["campaign_id"] == env["campaign_id"]
        # No private attack material may ever be persisted.
        blob = json.dumps(entries)
        for banned in ("attacker_prompt", "exploit", "tactics", "chain_of_thought"):
            assert banned not in blob

    def test_registration_requires_admin(self, ctx):
        client, _ = ctx
        r = client.post("/v1/campaigns", json={"principal_id": ADV, "envelope": envelope()},
                        headers=hdr("advsecret"))  # adversarial cannot self-register
        assert r.status_code == 403

    def test_idempotent_replay_cannot_bypass_revoked_campaign(self, ctx):
        client, adapter = ctx
        env = envelope(); register_campaign(client, env)
        digest = canonical_digest(env)
        body = {"agent": ADV, "adapter": "fake",
                "action": {"tool": "fake.safe", "impact": "write"},
                "campaign_id": env["campaign_id"],
                "authority_ref": env["authorization"]["authority_ref"],
                "campaign_digest": digest, "attack_surface": ["runtime.authorization"],
                "idempotency_key": "k1"}
        r1 = client.post("/v1/gateway/execute", headers=hdr("advsecret"), json=body)
        assert r1.json()["status"] == "ALLOW" and adapter.executions == 1
        # Revoke, then replay the SAME idempotency key. The campaign guard runs
        # before idempotency, so the cached success cannot be re-served.
        client.post(f"/v1/campaigns/{env['campaign_id']}/revoke",
                    headers=hdr("adsecret"), json={"reason": "revoked"})
        r2 = client.post("/v1/gateway/execute", headers=hdr("advsecret"), json=body)
        assert r2.json()["status"] == "DENY"
        assert adapter.executions == 1  # no second execution
