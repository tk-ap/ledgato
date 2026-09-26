"""One non-bypassable boundary: AgentOS → Ledgato → protected action → evidence.

The decisive question for every test is the stress-test directive's #3: *did
the protected action occur?* The resource's own persisted effect log is the
ground truth — never the executor's or Ledgato's account of it.
"""
from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from ledgato.crypto import Signer
from ledgato.enforcement import (
    CONTRACT_VERSION,
    OUTCOME_ALLOW,
    ActionContract,
    ContractError,
    DecisionStore,
    EnforcementPoint,
    policy_digest,
    sign_permit,
)
from ledgato.integrations.protected_executor import (
    APPROVAL_REQUIRED,
    DENIED,
    EXECUTED,
    FAILED_CLOSED,
    ProtectedExecutor,
)
from ledgato.ledger import Ledger
from ledgato.models import Policy
from ledgato.protected_resource import PermitRejected, ProtectedResource

AGENT = "agent-os-deployer"
RESOURCE = "service::billing-api"


def policy() -> Policy:
    return Policy(
        agent=AGENT,
        allow_tools={"release.deploy", "release.rollback"},
        deny_tools={"release.delete"},
        approval_tools={"release.rollback"},
        impact_max="exec",
        data_domains=["service::*"],
    )


def make_contract(action="release.deploy", *, work_id="work-1", impact="write",
                  resource=RESOURCE, policy_id=AGENT, **params) -> ActionContract:
    return ActionContract.from_dict({
        "version": CONTRACT_VERSION,
        "work_id": work_id,
        "agent": {"id": AGENT, "identity": f"iam:svc/{AGENT}"},
        "requested_action": {"name": action, "impact": impact, "params": params},
        "resource": resource,
        "policy": {"id": policy_id},
        "evidence": [{"kind": "work-item", "ref": f"agent-os:{work_id}"}],
    })


class Ledgato:
    """In-process stand-in for the Ledgato API, as the agent principal."""

    def __init__(self, point: EnforcementPoint):
        self.point = point

    def decide(self, contract):
        return self.point.decide(ActionContract.from_dict(contract), principal_id=AGENT)

    def record_outcome(self, decision_id, report):
        return self.point.record_outcome(decision_id, report, principal_id=AGENT)


class SpyResource:
    """Counts every call, so 'never called' is asserted, not inferred."""

    def __init__(self, inner: ProtectedResource):
        self.inner = inner
        self.calls = 0
        self.permits: list[dict] = []

    def perform(self, contract, permit):
        self.calls += 1
        if isinstance(permit, dict):
            self.permits.append(dict(permit))
        return self.inner.perform(contract, permit)


class World:
    def __init__(self, root: Path, signer: Signer | None = None):
        self.root = root
        keys = root / "keys"
        if signer is None:
            signer = Signer.load(keys) if keys.exists() else Signer()
            if not keys.exists():
                signer.save(keys)
        self.signer = signer
        ledger_path = root / "ledger.jsonl"
        self.ledger = Ledger.load(ledger_path, signer=signer) if ledger_path.exists() \
            else Ledger(signer=signer, path=ledger_path)
        self.point = EnforcementPoint(
            policies={AGENT: policy()}, ledger=self.ledger, signer=signer,
            store=DecisionStore(root / "decisions.json"),
        )
        self.resource = ProtectedResource(
            resource=RESOURCE, state_path=root / "resource.json",
            trusted_keys={signer.public_key_b64()},
        )
        self.spy = SpyResource(self.resource)
        self.executor = ProtectedExecutor(Ledgato(self.point), self.spy)


@pytest.fixture
def world(tmp_path):
    return World(tmp_path)


# ---- the three decisions ---------------------------------------------------
def test_allowed_action_executes_exactly_once(world):
    c = make_contract(version="2026.09.25")
    result = world.executor.run(c)

    assert result["status"] == EXECUTED and result["executed"] is True
    assert world.spy.calls == 1
    effects = world.resource.effects()
    assert len(effects) == 1
    assert effects[0]["decision_id"] == result["decision_id"]
    assert effects[0]["contract_digest"] == c.digest()

    # Replaying the exact permit AgentOS was issued never acts again.
    with pytest.raises(PermitRejected, match="already been used"):
        world.resource.perform(c, world.spy.permits[0])
    assert len(world.resource.effects()) == 1


def test_denied_action_has_no_side_effect_and_resource_is_never_called(world):
    result = world.executor.run(make_contract("release.delete", impact="exec"))

    assert result["status"] == DENIED and result["executed"] is False
    assert world.spy.calls == 0
    assert world.resource.effects() == []


def test_approval_required_action_has_no_side_effect(world):
    result = world.executor.run(make_contract("release.rollback", to="2026.09.24"))

    assert result["status"] == APPROVAL_REQUIRED and result["executed"] is False
    assert world.spy.calls == 0
    assert world.resource.effects() == []
    record = world.point.store.get(result["decision_id"])
    assert record["permit_id"] is None


@pytest.mark.parametrize("action,impact,why", [
    ("release.deploy", "destructive", "exceeds impact_max"),
    ("db.drop", "write", "not in allow_tools"),
])
def test_out_of_policy_actions_are_denied(world, action, impact, why):
    result = world.executor.run(make_contract(action, impact=impact))
    assert result["status"] == DENIED
    assert any(why in r for r in world.point.store.get(result["decision_id"])["reasons"])
    assert world.resource.effects() == []


def test_contract_cannot_choose_a_different_or_stale_policy(world):
    other = world.executor.run(make_contract(policy_id="lenient-policy"))
    assert other["status"] == DENIED

    stale = make_contract().to_dict()
    stale["policy"]["digest"] = "0" * 64
    result = world.executor.run(ActionContract.from_dict(stale))
    assert result["status"] == DENIED

    current = make_contract().to_dict()
    current["policy"]["digest"] = policy_digest(policy())
    assert world.executor.run(ActionContract.from_dict(current))["status"] == EXECUTED


def test_unknown_agent_is_denied_not_errored(tmp_path):
    w = World(tmp_path)
    w.point.policies = {}
    result = w.executor.run(make_contract())
    assert result["status"] == DENIED
    assert w.resource.effects() == []


# ---- fail closed -----------------------------------------------------------
class Broken:
    def __init__(self, response=None, raises=None):
        self.response, self.raises = response, raises
        self.outcomes = []

    def decide(self, contract):
        if self.raises:
            raise self.raises
        return self.response(contract) if callable(self.response) else self.response

    def record_outcome(self, decision_id, report):
        self.outcomes.append((decision_id, report))
        return {}


def _allow_without_permit(contract):
    return {"decision_id": "d1", "outcome": OUTCOME_ALLOW,
            "contract_digest": ActionContract.from_dict(contract).digest(), "permit": None}


@pytest.mark.parametrize("ledgato", [
    Broken(raises=ConnectionRefusedError("ledgato down")),
    Broken(raises=TimeoutError("timed out")),
    Broken(response=None),
    Broken(response={"outcome": "ALLOW"}),
    Broken(response=lambda c: {"decision_id": "d1", "outcome": "MAYBE",
                               "contract_digest": ActionContract.from_dict(c).digest()}),
    Broken(response={"decision_id": "d1", "outcome": "ALLOW", "contract_digest": "not-this-one"}),
    Broken(response=_allow_without_permit),
], ids=["unreachable", "timeout", "empty", "no-id", "unknown-outcome", "digest-mismatch", "allow-no-permit"])
def test_no_valid_decision_fails_closed(world, ledgato):
    executor = ProtectedExecutor(ledgato, world.spy)
    result = executor.run(make_contract())
    assert result["status"] == FAILED_CLOSED
    assert result["executed"] is False
    assert world.spy.calls == 0
    assert world.resource.effects() == []


def test_allow_carrying_a_forged_permit_fails_closed_at_the_resource(world):
    """A compromised decision channel still cannot make the resource act."""
    rogue = Signer()

    def forged(contract):
        c = ActionContract.from_dict(contract)
        return {"decision_id": "d1", "outcome": OUTCOME_ALLOW, "contract_digest": c.digest(),
                "permit": _permit(rogue, c, decision_id="d1")}

    result = ProtectedExecutor(Broken(response=forged), world.spy).run(make_contract())
    assert result["status"] == FAILED_CLOSED
    assert "not a trusted Ledgato key" in result["reason"]
    assert world.resource.effects() == []


def test_malformed_contracts_are_rejected_before_any_decision():
    base = make_contract().to_dict()
    for mutate in (
        lambda d: d.pop("work_id"),
        lambda d: d["agent"].pop("identity"),
        lambda d: d.update(resource=""),
        lambda d: d["requested_action"].update(impact="godmode"),
        lambda d: d.update(version="v0"),
        lambda d: d.update(extra="field"),
        lambda d: d.update(evidence=[{"kind": "x"}]),
    ):
        d = json.loads(json.dumps(base))
        mutate(d)
        with pytest.raises(ContractError):
            ActionContract.from_dict(d)


# ---- direct / bypass invocation --------------------------------------------
def _permit(signer: Signer, c: ActionContract, *, decision_id="d-forged", expires_in=60,
            resource=None, entry_hash="h"):
    now = datetime.now(timezone.utc)
    return sign_permit(signer, {
        "version": "ledgato.permit/v1", "permit_id": "p-" + decision_id,
        "decision_id": decision_id, "contract_digest": c.digest(),
        "work_id": c.work_id, "agent_id": c.agent_id, "action": c.action,
        "resource": resource or c.resource, "ledger_entry_id": "e",
        "ledger_entry_hash": entry_hash, "issued_at": now.isoformat(),
        "expires_at": (now + timedelta(seconds=expires_in)).isoformat(),
        "issuer_public_key": signer.public_key_b64(),
    })


def test_direct_bypass_invocations_are_rejected(world):
    """AgentOS skips the executor and calls the protected resource itself."""
    c = make_contract(version="direct")
    real = world.point.decide(make_contract(version="real"), principal_id=AGENT)["permit"]
    denied_c = make_contract("release.delete", impact="exec")
    other_resource = make_contract(resource="service::payroll", version="real")

    attempts = {
        "no permit": (c, None),
        "empty permit": (c, {}),
        "non-Ledgato signer": (c, _permit(Signer(), c)),
        "real permit, different contract": (c, real),
        "real permit, denied contract": (denied_c, real),
        "real permit, tampered action": (make_contract(version="real"), {**real, "action": "release.delete"}),
        "real permit, stripped signature": (make_contract(version="real"), {**real, "signature": ""}),
        "real permit, other resource": (other_resource, real),
        "expired Ledgato permit": (c, _permit(world.signer, c, expires_in=-1)),
        "permit with extra field": (make_contract(version="real"), {**real, "scope": "*"}),
    }
    for label, (contract, permit) in attempts.items():
        with pytest.raises(PermitRejected):
            world.resource.perform(contract, permit)
    assert world.resource.effects() == [], "a bypass attempt produced a side effect"
    assert len(world.resource.rejections()) == len(attempts)


def test_permit_for_one_resource_is_useless_at_another(tmp_path, world):
    payroll = ProtectedResource(
        resource="service::payroll", state_path=tmp_path / "payroll.json",
        trusted_keys={world.signer.public_key_b64()},
    )
    c = make_contract(version="x")
    permit = world.point.decide(c, principal_id=AGENT)["permit"]
    with pytest.raises(PermitRejected, match="not valid for resource"):
        payroll.perform(c, permit)
    assert payroll.effects() == []


def test_resource_refuses_to_start_without_a_pinned_key(tmp_path):
    with pytest.raises(ValueError):
        ProtectedResource(resource=RESOURCE, state_path=tmp_path / "r.json", trusted_keys=set())


# ---- evidence and restart --------------------------------------------------
def test_ledger_evidence_proves_each_result(world):
    allowed = world.executor.run(make_contract(version="1"))
    denied = world.executor.run(make_contract("release.delete", impact="exec"))
    paused = world.executor.run(make_contract("release.rollback"))

    for result, outcome, executed in (
        (allowed, "ALLOW", True), (denied, "DENY", False), (paused, "APPROVAL_REQUIRED", False),
    ):
        ev = world.point.evidence(result["decision_id"])
        assert ev["verified"], ev["problems"]
        assert ev["outcome"] == outcome
        assert ev["executed"] is executed
        assert ev["consistent"] is True
        assert ev["decision_entry"]["decision"] == outcome
        assert ev["outcome_entry"]["evidence"]["decision_entry_hash"] == ev["decision_entry"]["hash"]

    effect = world.resource.effects()[0]
    assert effect["ledger_entry_hash"] == world.point.evidence(allowed["decision_id"])["decision_entry"]["hash"]


def test_decision_and_evidence_survive_process_restart(tmp_path):
    first = World(tmp_path)
    allowed = first.executor.run(make_contract(version="1"))
    denied = first.executor.run(make_contract("release.delete", impact="exec"))
    used_permit = first.spy.permits[0]
    del first  # nothing in memory carries over

    second = World(tmp_path)
    for result, executed in ((allowed, True), (denied, False)):
        ev = second.point.evidence(result["decision_id"])
        assert ev["verified"], ev["problems"]
        assert ev["executed"] is executed

    # The burned permit stays burned across the resource restart too.
    with pytest.raises(PermitRejected, match="already been used"):
        second.resource.perform(make_contract(version="1"), used_permit)
    assert len(second.resource.effects()) == 1


def test_tampered_ledger_is_detected_after_restart(tmp_path):
    first = World(tmp_path)
    result = first.executor.run(make_contract("release.delete", impact="exec"))
    ledger_file = tmp_path / "ledger.jsonl"
    lines = ledger_file.read_text().splitlines()
    entry = json.loads(lines[0])
    entry["decision"] = "ALLOW"  # rewrite history: pretend it was allowed
    lines[0] = json.dumps(entry)
    ledger_file.write_text("\n".join(lines) + "\n")

    ev = World(tmp_path).point.evidence(result["decision_id"])
    assert ev["verified"] is False
    assert ev["chain_valid"] is False


def test_outcome_is_recorded_once_and_only_by_the_deciding_agent(world):
    c = make_contract("release.delete", impact="exec")
    decision = world.point.decide(c, principal_id=AGENT)
    with pytest.raises(PermissionError):
        world.point.record_outcome(decision["decision_id"], {"executed": False}, principal_id="someone-else")
    world.point.record_outcome(decision["decision_id"], {"executed": False}, principal_id=AGENT)
    with pytest.raises(ValueError):
        world.point.record_outcome(decision["decision_id"], {"executed": False}, principal_id=AGENT)


def test_execution_claimed_on_a_denied_decision_is_recorded_as_inconsistent(world):
    decision = world.point.decide(make_contract("release.delete", impact="exec"), principal_id=AGENT)
    world.point.record_outcome(decision["decision_id"], {"executed": True}, principal_id=AGENT)
    ev = world.point.evidence(decision["decision_id"])
    assert ev["consistent"] is False


# ---- end to end across real processes --------------------------------------
def _load_proof():
    path = Path(__file__).resolve().parents[1] / "examples" / "prove_enforcement_boundary.py"
    spec = importlib.util.spec_from_file_location("prove_enforcement_boundary", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_end_to_end_proof_across_processes_and_restart(tmp_path):
    result = _load_proof().run_proof(tmp_path / "proof")
    failed = [c for c in result["checks"] if not c["passed"]]
    assert not failed, failed
    names = {c["check"] for c in result["checks"]}
    # The negative bypass checks must have actually run, not been skipped.
    assert "bypass rejected: direct call with no permit" in names
    assert "bypass rejected: permit replay after restart" in names
    assert "no Ledgato decision -> FAILED_CLOSED, nothing executed" in names
