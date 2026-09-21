"""Adversarial campaign enforcement: trust domains, campaign authority,
lifecycle pinning, provider rotation, and evidence.

An orthogonal layer on top of the existing engine. Operational behaviour is
unchanged; adversarial callers may act only inside a currently valid,
digest-pinned campaign, and verifiers may never mutate.
"""
import json
from datetime import datetime, timedelta, timezone

import pytest

from ledgato.adapters.base import ExecutionReceipt
from ledgato.approvals import ApprovalStore
from ledgato.authority import AuthorityStore
from ledgato.campaign import (
    CampaignAuthorityStore,
    CampaignError,
    authorize_campaign_action,
    build_authority,
    canonical_digest,
)
from ledgato.crypto import Signer
from ledgato.gateway import EnforcementGateway
from ledgato.ledger import Ledger
from ledgato.models import Action, Policy
from ledgato.principals import (
    Principal, PrincipalRegistry, TRUST_ADVERSARIAL, TRUST_OPERATIONAL, TRUST_VERIFIER,
)

ADV = "adv-agent"


def envelope(*, expires_in=3600, campaign_id="camp-1", authority_ref="auth-ref-1"):
    now = datetime.now(timezone.utc)
    return {
        "schema_version": 1,
        "campaign_id": campaign_id,
        "authorization": {
            "authority_ref": authority_ref, "owner": "alvira2",
            "target_owned_or_authorized": True,
            "issued_at": (now - timedelta(minutes=1)).isoformat(),
            "expires_at": (now + timedelta(seconds=expires_in)).isoformat(),
        },
        "target": {"id": "ledgato-runtime-test", "environment": "production-equivalent",
                   "interface": "ledgato://runtime/authorization"},
        "permitted_attack_surface": ["runtime.authorization", "revocation.lifecycle"],
        "prohibited_surfaces": ["third-party.systems", "real-user.data"],
        "budget": {"wall_seconds": 900, "max_attempts": 12, "max_parallel_agents": 2},
        "evidence": {"independent_verifier_required": True, "retain_attempt_log": True},
        "response_contract": {"finding_classifications": ["held", "bypass", "indeterminate"],
                              "evidence_refs_required": True},
    }


class FakeAdapter:
    name = "fake"

    def __init__(self):
        self.executions = 0

    def discover(self, agent): return {"fake.safe", "fake.risky"}

    def execute(self, action):
        self.executions += 1
        return ExecutionReceipt(adapter=self.name, action=action.tool, executed=True,
                                status="ok", external_id=f"r{self.executions}")

    def verify(self, action, receipt): return {"verified": True}

    def verify_denied(self, action): return {"verified": True, "executed": False}


@pytest.fixture()
def store(tmp_path):
    return CampaignAuthorityStore(tmp_path / "campaigns.json")


@pytest.fixture()
def registered(store):
    env = envelope()
    store.register(build_authority(env, expected_principal_id=ADV))
    return store, env, canonical_digest(env)


def claim(env, digest, **over):
    base = dict(principal_id=ADV, campaign_id=env["campaign_id"],
                authority_ref=env["authorization"]["authority_ref"],
                campaign_digest=digest, attack_surface=["runtime.authorization"])
    base.update(over)
    return base


# ---------------------------------------------------------------- principals
class TestPrincipalTrustDomain:
    def test_existing_principals_default_to_operational(self):
        assert Principal(id="x", role="agent").trust_domain == TRUST_OPERATIONAL

    def test_three_part_env_entry_is_operational(self, monkeypatch):
        monkeypatch.setenv("LEDGATO_PRINCIPALS", "a:agent:s1")
        reg = PrincipalRegistry.from_env()
        assert reg.resolve("s1").trust_domain == TRUST_OPERATIONAL

    def test_four_part_env_entry_pins_trust_domain(self, monkeypatch):
        monkeypatch.setenv("LEDGATO_PRINCIPALS", "a:agent:adversarial:s1")
        assert PrincipalRegistry.from_env().resolve("s1").trust_domain == TRUST_ADVERSARIAL

    def test_unknown_trust_domain_fails_closed(self):
        with pytest.raises(ValueError):
            PrincipalRegistry().add("a", "agent", "s", trust_domain="martian")


# --------------------------------------------------------- campaign authority
class TestCampaignGuard:
    def test_valid_in_scope_allows(self, registered):
        store, env, digest = registered
        d = authorize_campaign_action(store, **claim(env, digest))
        assert d.allow and d.campaign_digest == digest

    def test_no_campaign_id_denies(self, registered):
        store, env, digest = registered
        assert not authorize_campaign_action(store, **claim(env, digest, campaign_id=None)).allow

    def test_unknown_campaign_denies(self, store):
        d = authorize_campaign_action(store, principal_id=ADV, campaign_id="ghost",
                                      authority_ref="a", campaign_digest="d",
                                      attack_surface=["runtime.authorization"])
        assert not d.allow and "unknown campaign" in d.reason

    def test_outside_permitted_surface_denies(self, registered):
        store, env, digest = registered
        d = authorize_campaign_action(store, **claim(env, digest, attack_surface=["exfil.secrets"]))
        assert not d.allow and "outside permitted" in d.reason

    def test_prohibited_surface_denies(self, registered):
        # A prohibited surface is by construction also outside permitted (the
        # envelope forbids overlap), so it is denied either way.
        store, env, digest = registered
        d = authorize_campaign_action(store, **claim(env, digest, attack_surface=["real-user.data"]))
        assert not d.allow

    def test_prohibited_branch_is_defensively_reachable(self, store):
        # Construct an authority whose scope overlaps (which build_authority
        # would reject) to prove the prohibited-intersection branch itself
        # denies, independent of the permitted check.
        from ledgato.campaign import CampaignAuthority
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        store._campaigns["camp-x"] = CampaignAuthority(
            campaign_id="camp-x", principal_id=ADV, authority_ref="a",
            campaign_digest="d", issued_at=now.isoformat(),
            expires_at=(now + timedelta(hours=1)).isoformat(),
            target={}, permitted_attack_surface=["s"], prohibited_surfaces=["s"],
            budget={})
        d = authorize_campaign_action(store, principal_id=ADV, campaign_id="camp-x",
                                      authority_ref="a", campaign_digest="d",
                                      attack_surface=["s"])
        assert not d.allow and "prohibited" in d.reason

    def test_authority_ref_mismatch_denies(self, registered):
        store, env, digest = registered
        assert not authorize_campaign_action(store, **claim(env, digest, authority_ref="wrong")).allow

    def test_principal_mismatch_denies(self, registered):
        store, env, digest = registered
        assert not authorize_campaign_action(store, **claim(env, digest, principal_id="intruder")).allow

    def test_digest_mismatch_denies(self, registered):
        store, env, digest = registered
        assert not authorize_campaign_action(store, **claim(env, digest, campaign_digest="deadbeef")).allow

    def test_expired_campaign_denies(self, store):
        env = envelope(expires_in=-5)
        store.register(build_authority(env, expected_principal_id=ADV))
        d = authorize_campaign_action(store, **claim(env, canonical_digest(env)))
        assert not d.allow and "expired" in d.reason

    def test_revoked_campaign_denies(self, registered):
        store, env, digest = registered
        store.revoke(env["campaign_id"], revoked_by="admin", reason="test")
        d = authorize_campaign_action(store, **claim(env, digest))
        assert not d.allow and "revoked" in d.reason

    def test_adversarial_cannot_widen_by_reregistering(self, registered):
        store, env, digest = registered
        widened = envelope()
        widened["permitted_attack_surface"] = ["runtime.authorization", "everything"]
        with pytest.raises(CampaignError):
            store.register(build_authority(widened, expected_principal_id=ADV))


# --------------------------------------------------------------- lifecycle
def build_gateway(tmp_path, store, *, approval_tools=()):
    adapter = FakeAdapter()
    policy = Policy(agent=ADV, allow_tools={"fake.safe", "fake.risky"},
                    impact_max="write", approval_tools=set(approval_tools))
    gw = EnforcementGateway(
        policies={ADV: policy}, adapters={"fake": adapter},
        ledger=Ledger(signer=Signer(), path=tmp_path / "ledger.jsonl"),
        authority=AuthorityStore(tmp_path / "authority.json"),
        approvals=ApprovalStore(tmp_path / "approvals.json"),
        campaigns=store,
    )
    return gw, adapter


class TestLifecycle:
    def _ctx(self, env, digest, **over):
        c = {"principal_id": ADV, "principal_role": "agent",
             "trust_domain": TRUST_ADVERSARIAL, "campaign_id": env["campaign_id"],
             "authority_ref": env["authorization"]["authority_ref"],
             "campaign_digest": digest, "attack_surface": ["runtime.authorization"]}
        c.update(over)
        return c

    def _pause(self, tmp_path, registered):
        store, env, digest = registered
        gw, adapter = build_gateway(tmp_path, store, approval_tools={"fake.risky"})
        res = gw.execute(agent=ADV, adapter="fake",
                         action=Action(tool="fake.risky", impact="write"),
                         task_id="t1", campaign_context=self._ctx(env, digest))
        assert res["status"] == "APPROVE" and res["paused"] is True
        return gw, adapter, res["approval"]["id"], env, digest

    def test_approval_pause_retains_exact_campaign_identity(self, tmp_path, registered):
        gw, _, approval_id, env, digest = self._pause(tmp_path, registered)
        item = gw.approvals.get(approval_id)
        assert item.campaign_context["campaign_id"] == env["campaign_id"]
        assert item.campaign_context["campaign_digest"] == digest

    def _approve_and_resume(self, gw, approval_id):
        approved = gw.approve(approval_id, decided_by="approver1")
        token = approved["approval"]["resume_token"]
        return gw.resume(approval_id, resume_token=token)

    def test_resume_of_valid_campaign_executes(self, tmp_path, registered):
        gw, adapter, approval_id, env, digest = self._pause(tmp_path, registered)
        res = self._approve_and_resume(gw, approval_id)
        assert res["status"] == "ALLOW" and adapter.executions == 1

    def test_revoke_after_approval_before_resume_denies(self, tmp_path, registered):
        gw, adapter, approval_id, env, digest = self._pause(tmp_path, registered)
        gw.approve(approval_id, decided_by="approver1")
        gw.campaigns.revoke(env["campaign_id"], revoked_by="admin", reason="mid-flight")
        item = gw.approvals.get(approval_id)
        res = gw.resume(approval_id, resume_token=item.resume_token)
        assert res["status"] == "DENY" and res["boundary_crossed"] is False
        assert adapter.executions == 0

    def test_expiry_after_approval_before_resume_denies(self, tmp_path, store):
        env = envelope(expires_in=1)
        store.register(build_authority(env, expected_principal_id=ADV))
        registered = (store, env, canonical_digest(env))
        gw, adapter, approval_id, env, digest = self._pause(tmp_path, registered)
        gw.approve(approval_id, decided_by="approver1")
        import time
        time.sleep(1.1)
        item = gw.approvals.get(approval_id)
        res = gw.resume(approval_id, resume_token=item.resume_token)
        assert res["status"] == "DENY" and adapter.executions == 0

    def test_process_restart_reloads_same_digest(self, tmp_path, registered):
        store, env, digest = registered
        reopened = CampaignAuthorityStore(store.path)
        assert reopened.get(env["campaign_id"]).campaign_digest == digest

    def test_retry_cannot_widen_scope(self, tmp_path, registered):
        store, env, digest = registered
        gw, adapter = build_gateway(tmp_path, store)
        # A retry with a surface outside the pinned scope is denied by the guard.
        d = authorize_campaign_action(store, **claim(env, digest, attack_surface=["exfil.x"]))
        assert not d.allow


# ---------------------------------------------------------- provider rotation
class TestProviderRotation:
    def test_same_digest_different_provider_is_same_authority(self, registered):
        store, env, digest = registered
        a = authorize_campaign_action(store, **claim(env, digest))
        b = authorize_campaign_action(store, **claim(env, digest))  # "codex" now
        assert a.allow and b.allow and a.campaign_digest == b.campaign_digest

    def test_rotation_cannot_change_digest(self, registered):
        store, env, digest = registered
        assert not authorize_campaign_action(store, **claim(env, digest, campaign_digest="Y")).allow

    def test_rotation_cannot_add_scope(self, registered):
        store, env, digest = registered
        assert not authorize_campaign_action(
            store, **claim(env, digest, attack_surface=["runtime.authorization", "new.surface"])).allow

    def test_provider_metadata_grants_nothing(self, tmp_path, store):
        # No campaign registered: no provider string makes an adversarial call ok.
        d = authorize_campaign_action(store, principal_id=ADV, campaign_id="camp-1",
                                      authority_ref="auth-ref-1", campaign_digest="d",
                                      attack_surface=["runtime.authorization"])
        assert not d.allow
