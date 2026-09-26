"""Prove a real GitHub merge boundary without merging anything.

Required environment:
  LEDGATO_GITHUB_REPOSITORY=owner/repo
  LEDGATO_GITHUB_TOKEN=<token held by the gateway>
  LEDGATO_PROOF_PULL_NUMBER=<open, unmerged PR number>

The policy explicitly denies merge. The gateway therefore MUST NOT issue a
GitHub merge request. It performs only a readback afterward and asserts the PR
remains unmerged.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from ledgato.adapters.github import GitHubAdapter
from ledgato.approvals import ApprovalStore
from ledgato.authority import AuthorityStore
from ledgato.crypto import Signer
from ledgato.gateway import EnforcementGateway
from ledgato.ledger import Ledger
from ledgato.models import Action, Policy


def required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise SystemExit(f"missing required environment variable: {name}")
    return value


def main() -> None:
    repository = required("LEDGATO_GITHUB_REPOSITORY")
    token = required("LEDGATO_GITHUB_TOKEN")
    pull_number = int(required("LEDGATO_PROOF_PULL_NUMBER"))

    state_dir = Path(os.getenv("LEDGATO_PROOF_STATE", ".ledgato-proof"))
    state_dir.mkdir(parents=True, exist_ok=True)

    adapter = GitHubAdapter(repository=repository, token=token)
    policy = Policy(
        agent="proof-agent",
        allow_tools={"github.repo.read"},
        deny_tools={"github.pull.merge"},
        impact_max="destructive",
    )
    gateway = EnforcementGateway(
        policies={policy.agent: policy},
        adapters={"github": adapter},
        ledger=Ledger(signer=Signer(), path=state_dir / "ledger.jsonl"),
        authority=AuthorityStore(state_dir / "authority.json"),
        approvals=ApprovalStore(state_dir / "approvals.json"),
    )

    discovery = gateway.discover(agent="proof-agent", adapter="github")
    result = gateway.execute(
        agent="proof-agent",
        adapter="github",
        task_id=f"proof-pr-{pull_number}",
        requested_by="first-client-proof",
        action=Action(
            tool="github.pull.merge",
            impact="destructive",
            domain=f"github::{repository}",
            params={"pull_number": pull_number},
        ),
    )

    if result["status"] != "DENY":
        raise SystemExit(f"proof failed: expected DENY, got {result['status']}")
    if result["executed"] or result["boundary_crossed"]:
        raise SystemExit("proof failed: denied action crossed the boundary")
    if not result.get("verification", {}).get("verified"):
        raise SystemExit("proof failed: downstream readback did not verify non-execution")

    print(json.dumps({"discovery": discovery, "enforcement": result}, indent=2))
    print("\nPASS: LEDGATo denied the merge, made no merge call, and GitHub confirms the PR remains unmerged.")


if __name__ == "__main__":
    main()
