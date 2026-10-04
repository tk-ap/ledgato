"""Owner session grants: one owner approval covers a bounded working session."""
from datetime import timedelta

import pytest

from ledgato.adapters.session import SESSION_GRANT_TOOL, SessionGrantAdapter, SessionGrantError
from ledgato.approvals import ApprovalStore
from ledgato.authority import AuthorityStore
from ledgato.crypto import Signer
from ledgato.gateway import EnforcementGateway
from ledgato.ledger import Ledger
from ledgato.models import Action, Policy
from ledgato.models import utcnow

from test_gateway import FakeAdapter

SESSION_DOMAIN = "ledgato-session::agent-os"


def _policy(approve_session=True):
    return Policy(
        agent="agent",
        allow_tools={"fake.risky", "fake.other", SESSION_GRANT_TOOL},
        approval_tools={"fake.risky", "fake.other"} | ({SESSION_GRANT_TOOL} if approve_session else set()),
        impact_max="write",
        data_domains=["ledgato-session::*", "box", "other-box"],
    )


@pytest.fixture()
def world(tmp_path):
    fake = FakeAdapter()
    authority = AuthorityStore(tmp_path / "authority.json")
    gateway = EnforcementGateway(
        policies={"agent": _policy()},
        adapters={"fake": fake,
                  "session": SessionGrantAdapter(authority, grantable_tools={"fake.risky"})},
        ledger=Ledger(signer=Signer(), path=tmp_path / "ledger.jsonl"),
        authority=authority,
        approvals=ApprovalStore(tmp_path / "approvals.json"),
    )
    return gateway, fake, authority, tmp_path


def _request_session(gateway, **params):
    params = {"tools": ["fake.risky"], "data_domains": ["box"], "ttl_seconds": 3600,
              "purpose": "merge and install agent-os", **params}
    return gateway.execute(
        agent="agent", adapter="session",
        action=Action(tool=SESSION_GRANT_TOOL, impact="write", domain=SESSION_DOMAIN, params=params),
    )


def _open_session(gateway, **params):
    pending = _request_session(gateway, **params)
    assert pending["status"] == "APPROVE", "a session must wait for the owner"
    result = gateway.approve_and_resume(pending["approval"]["id"], decided_by="tk")
    return result["execution"]["receipt"]["result"]["grant_id"]


def _risky(gateway, grant_id=None, domain="box", tool="fake.risky"):
    return gateway.execute(agent="agent", adapter="fake",
                           action=Action(tool=tool, impact="write", domain=domain),
                           grant_id=grant_id)


def test_one_owner_approval_covers_later_actions_in_scope(world):
    gateway, fake, authority, _ = world
    grant_id = _open_session(gateway)
    grant = authority.get(grant_id)
    assert grant.satisfies_approval is True
    assert grant.granted_by == "owner-session:tk"
    assert grant.tools == {"fake.risky"}

    first = _risky(gateway, grant_id)
    second = _risky(gateway, grant_id)
    assert first["status"] == second["status"] == "ALLOW"
    assert fake.executions == 2
    assert "owner session grant" in " ".join(first["decision"]["reasons"])


def test_without_the_session_grant_the_owner_is_still_asked(world):
    gateway, fake, _, _ = world
    _open_session(gateway)
    assert _risky(gateway)["status"] == "APPROVE"
    assert fake.executions == 0


def test_the_grant_never_reaches_outside_its_scope(world):
    gateway, fake, _, _ = world
    grant_id = _open_session(gateway)
    assert _risky(gateway, grant_id, domain="other-box")["status"] == "DENY"
    assert _risky(gateway, grant_id, tool="fake.other")["status"] == "DENY"
    assert fake.executions == 0


def test_an_expired_session_no_longer_covers_anything(world):
    gateway, fake, authority, _ = world
    grant_id = _open_session(gateway)
    grant = authority.get(grant_id)
    grant.expires_at = (utcnow() - timedelta(seconds=1)).isoformat()
    authority._save()
    assert _risky(gateway, grant_id)["status"] == "DENY"
    assert fake.executions == 0


def test_an_ordinary_grant_does_not_stand_in_for_approval(world):
    gateway, fake, authority, _ = world
    grant = authority.issue(agent="agent", granted_by="admin", purpose="routine",
                            tools={"fake.risky"}, data_domains=["box"], impact_max="write",
                            ttl_seconds=600)
    assert _risky(gateway, grant.id)["status"] == "APPROVE"
    assert fake.executions == 0


def test_the_flag_survives_a_reload(world):
    gateway, _, _, tmp_path = world
    grant_id = _open_session(gateway)
    assert AuthorityStore(tmp_path / "authority.json").get(grant_id).satisfies_approval is True


@pytest.mark.parametrize("params", [
    {"tools": []},
    {"tools": ["fake.other"]},                     # not grantable
    {"tools": ["fake.risky", SESSION_GRANT_TOOL]},  # no grant that grants grants
    {"data_domains": []},
    {"impact_max": "destructive"},
    {"ttl_seconds": 4 * 3600 + 1},
])
def test_a_session_cannot_ask_for_more_than_a_session_may_carry(world, params):
    gateway, _, authority, _ = world
    pending = _request_session(gateway, **params)
    with pytest.raises(SessionGrantError):
        gateway.approve_and_resume(pending["approval"]["id"], decided_by="tk")
    assert not [g for g in authority.list() if g.satisfies_approval]


def test_a_session_grant_is_never_issued_without_an_owner_approval(tmp_path):
    """Even if policy were misconfigured to ALLOW the session tool directly."""
    authority = AuthorityStore(tmp_path / "authority.json")
    gateway = EnforcementGateway(
        policies={"agent": _policy(approve_session=False)},
        adapters={"fake": FakeAdapter(),
                  "session": SessionGrantAdapter(authority, grantable_tools={"fake.risky"})},
        ledger=Ledger(signer=Signer(), path=tmp_path / "ledger.jsonl"),
        authority=authority,
        approvals=ApprovalStore(tmp_path / "approvals.json"),
    )
    with pytest.raises(SessionGrantError):
        _request_session(gateway)
    assert not [g for g in authority.list() if g.satisfies_approval]
