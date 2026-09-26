"""Reproducible Ledgato gateway for independent live verification.

Holds the scoped GitHub credential in THIS process. The agent sandbox never
sees it. Refuses to point at a production repository.

Env:
  LEDGATO_GITHUB_TOKEN        scoped, lab-only fine-grained PAT (required)
  LEDGATO_GITHUB_REPOSITORY   owner/lab-repo (required; must look like a lab)
  LAB_GATEWAY_PORT            default 8770
  LAB_FENCE                   path to fence yaml (default lab/fence-deny.yaml)
  LAB_AGENT_SECRET / LAB_APPROVER_SECRET / LAB_ADMIN_SECRET  principal secrets

Run from the repo root with the engine importable:
  PYTHONPATH=engine python lab/gateway-serve.py
"""
import os, sys, pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "engine"))

import uvicorn
from ledgato.api import create_app
from ledgato.adapters.github import GitHubAdapter
from ledgato.boundary import BoundaryStore
from ledgato.principals import PrincipalRegistry

REPO = os.environ["LEDGATO_GITHUB_REPOSITORY"]
name = REPO.split("/")[-1].lower()
if name in ("ledgato", "ailhat", "alvira", "agent-os", "ashwood", "ashwood-info"):
    raise SystemExit(f"refusing: {REPO} looks like a production repository")
if not (set(name.replace("_", "-").split("-")) & {"lab", "test", "sandbox", "scratch"}):
    raise SystemExit(f"refusing: {REPO} must identify itself as a disposable lab")

GW = pathlib.Path(os.getenv("LAB_STATE_DIR", "lab/.state"))
GW.mkdir(parents=True, exist_ok=True)

app = create_app(
    config_path=os.getenv("LAB_FENCE", "lab/fence-deny.yaml"),
    ledger_path=str(GW / "ledger.jsonl"),
    key_dir=str(GW / "keys"),
    authority_path=str(GW / "authority.json"),
    approvals_path=str(GW / "approvals.json"),
    idempotency_path=str(GW / "idempotency.json"),
    adapters={"github": GitHubAdapter(
        repository=REPO, token=os.environ["LEDGATO_GITHUB_TOKEN"])},
    principals=PrincipalRegistry([
        ("lab-agent", "agent", os.environ["LAB_AGENT_SECRET"]),
        ("reviewer", "approver", os.environ["LAB_APPROVER_SECRET"]),
        ("ops", "admin", os.environ["LAB_ADMIN_SECRET"]),
    ]),
)
app.state.gateway.boundaries = BoundaryStore(str(GW / "boundaries.json"))
uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("LAB_GATEWAY_PORT", "8770")),
            log_level="warning")
