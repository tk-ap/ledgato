# Real enforcement contract

LEDGATo only **actually stops** an agent when the protected capability is reachable through the LEDGATo gateway and is not independently reachable by the governed agent.

That means the deployment must satisfy this rule:

> **The credential that can cross the protected boundary belongs to the gateway/adapter, not to the agent.**

For the first GitHub proof:

```text
agent / agent-os
      |
      v
LEDGATo gateway
  ALLOW / DENY / APPROVE
      |
      v
GitHubAdapter (holds GitHub token)
      |
      v
GitHub
```

The agent must not receive an equivalent GitHub token. Otherwise it could bypass the gateway and LEDGATo would be advisory rather than enforcing.

## What v0.3.0 now provides

- tri-state `ALLOW / DENY / APPROVE` decisions;
- a gateway that never calls the protected adapter on `DENY`;
- pause → human approval/denial → one-time resume;
- task-bound, expiring JIT authority grants;
- delegated grant chains with parent expiry/revocation propagation;
- live adapter capability discovery and drift comparison;
- post-action readback verification;
- denial readback verification where an adapter can prove downstream state;
- Python HTTP SDK;
- native GitHub and allowlisted HTTP adapters;
- a thin `agent-os` boundary hook;
- API-key protection when `LEDGATO_API_KEY` is configured;
- signed ledger evidence for discovery, grants, approvals, decisions, execution receipts, and verification.

## First real proof

Use an open, intentionally unmerged PR in a controlled repository.

```bash
export LEDGATO_GITHUB_REPOSITORY=owner/repo
export LEDGATO_GITHUB_TOKEN=...
export LEDGATO_PROOF_PULL_NUMBER=123
python engine/examples/prove_github_denial.py
```

The proof policy explicitly denies `github.pull.merge`. A passing run means:

1. the real GitHub credential is held by `GitHubAdapter`;
2. LEDGATo receives a real merge request;
3. policy returns `DENY`;
4. the gateway does not call GitHub's merge endpoint;
5. the adapter reads the pull request afterward;
6. GitHub reports that the PR remains unmerged;
7. the denial and verification evidence are written to the signed ledger.

This is safe to run against an open PR because the proof path contains no allowed merge call.

## Production caveat

v0.3.0 is the enforcement **foundation and first-client proof slice**, not a claim that every agent platform or external service is already integrated. Each additional protected system needs either:

- a native adapter whose credential is isolated behind the gateway; or
- an equivalent non-bypassable enforcement point (for example, a required GitHub check or protected MCP server operation).
