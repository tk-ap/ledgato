import pytest
from fastapi.testclient import TestClient

from ledgato.api import create_app


FENCE = """
policies:
  - agent: ops-agent
    allow_tool:
      - read.docs
      - search
    deny_tool:
      - db.write
    impact_max: readonly
    data_domains:
      - sandbox::*
"""


@pytest.fixture()
def client(tmp_path):
    cfg = tmp_path / "fence.yaml"
    cfg.write_text(FENCE)
    keys = tmp_path / "keys"
    ledger = tmp_path / "ledger.jsonl"
    app = create_app(config_path=cfg, ledger_path=ledger, key_dir=keys)
    return TestClient(app)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert "ops-agent" in r.json()["policies"]


def test_check_allow(client):
    r = client.post("/v1/actions/check", json={"agent": "ops-agent", "action": {"tool": "read.docs", "domain": "sandbox::x", "impact": "readonly"}})
    assert r.status_code == 200
    assert r.json()["allow"] is True


def test_check_deny(client):
    r = client.post("/v1/actions/check", json={"agent": "ops-agent", "action": {"tool": "db.write", "impact": "write"}})
    assert r.status_code == 200
    assert r.json()["allow"] is False


def test_unknown_agent_404(client):
    r = client.post("/v1/actions/check", json={"agent": "nope", "action": {"tool": "x"}})
    assert r.status_code == 404


def test_probes(client):
    r = client.post("/v1/probes/run", json={"agent": "ops-agent"})
    assert r.status_code == 200
    body = r.json()
    assert body["passed"] > 0
    assert body["total"] > 0


def test_attest_approved(client):
    r = client.post("/v1/releases/attest", json={"agent": "ops-agent", "release": "v1.0"})
    assert r.status_code == 200
    assert r.json()["verdict"] == "APPROVED"


def test_attest_gated_with_drift(client):
    r = client.post("/v1/releases/attest", json={"agent": "ops-agent", "release": "v1.0", "drift": True})
    assert r.status_code == 200
    assert r.json()["verdict"] == "GATED"


def test_ledger_endpoints(client):
    client.post("/v1/releases/attest", json={"agent": "ops-agent", "release": "v1.0"})
    r = client.get("/v1/ledger", params={"verify": True})
    assert r.status_code == 200
    body = r.json()
    assert body["count"] > 0
    assert body["verified"] is True
    vr = client.post("/v1/ledger/verify")
    assert vr.json()["verified"] is True


def test_ledger_status_and_chain(client):
    client.post("/v1/releases/attest", json={"agent": "ops-agent", "release": "v1.0"})
    st = client.get("/v1/ledger/status").json()
    assert st["entries"] > 0
    assert st["verified"] is True
    ch = client.get("/v1/ledger/chain").json()
    assert len(ch["entries"]) == st["entries"]


def test_ledger_reconcile(client):
    client.post("/v1/releases/attest", json={"agent": "ops-agent", "release": "v1.0"})
    chain = client.get("/v1/ledger/chain").json()["entries"]
    r = client.post("/v1/ledger/reconcile", json={"chain": chain})
    assert r.status_code == 200
    # equal-length, valid -> keeps local
    assert r.json()["sync"]["adopted"] is False


def test_attestation_verify_and_report(client):
    client.post("/v1/releases/attest", json={"agent": "ops-agent", "release": "v1.0"})
    v = client.post("/v1/attestations/verify", json={"agent": "ops-agent", "release": "v1.0"}).json()
    assert v["verdict"] == "APPROVED"
    assert v["verified"] is True
    rep = client.post("/v1/attestations/report", json={"agent": "ops-agent", "release": "v1.0"}).json()
    assert rep["agent"] == "ops-agent"
    rv = client.post("/v1/attestations/report/verify", json=rep).json()
    assert rv["verified"] is True


def test_health_reports_difficulty(client):
    r = client.get("/health").json()
    assert "difficulty" in r
    assert r["version"] == "0.2.0"