# Ledgato

**An agent-assurance + signed-evidence layer for consequential AI actions.**

Ledgato declares and maps the authority an AI agent is intended to have, probes those boundaries adversarially, checks consequential crossings against policy, and records tamper-evident evidence of what was allowed, denied, or approved. Release gating is one important boundary — not the only one.

> *An agent should not gain authority just because it can reach it.*

> **Product direction:** this repository records **`khrystal — Agent Assurance`** as the working successor-brand/category direction. **Agent Release Assurance** is the first concrete wedge, not the full product definition. The operational/public product remains Ledgato until an explicit rename implementation is approved. See [`PRODUCT_DIRECTION.md`](./PRODUCT_DIRECTION.md).

## Why

Agentic systems can cross important boundaries before a pull request or deployment ever exists. Tool access, credentials, data domains, external endpoints, impact levels, infrastructure permissions, and release authority can all drift beyond what a task actually requires.

A one-time security review is only a snapshot. The assurance problem is continuous:

> **Is this agent authorized to cross this boundary, under this task, with this evidence, right now?**

Ledgato/khrystal is intended to make that question enforceable and provable without becoming a second agent runtime, an identity provider, or a generic observability stack.

## Product boundary

Ledgato/khrystal is **not** trying to replace IAM, credential issuance, or the system that actually executes agent work.

A useful division of responsibility is:

- **Identity / IAM** — establishes the agent or workload identity, credentials, roles, and baseline grants.
- **agent-os / runtime / host** — performs the governed work.
- **Ledgato / khrystal** — independently evaluates consequential uses of authority, challenges declared boundaries, returns **ALLOW / DENY / APPROVE**, records provenance/evidence, and verifies whether reality stayed inside what was authorized.

The phrase **authorization control plane** can describe an integration mechanism, but the working product category is **Agent Assurance**. The differentiated question is not merely “what permissions does this agent have?” It is:

> **Given this agent, this task, this delegated authority, this requested action, and this evidence: should this boundary be crossed right now?**

## What it does

1. **Discover / declare** — Represent the tools, data domains, endpoints, impact, credentials, and other authority an agent can reach and is intended to have.
2. **Probe / verify** — Run adversarial checks for scope escape, impact escalation, exfiltration, injection, and other boundary failures.
3. **Decide** — Resolve consequential boundary requests as **ALLOW / DENY / APPROVE** according to policy, task context, authority provenance, and evidence.
4. **Enforce where integrated** — Feed the decision into the tool proxy, execution control plane, GitHub/CI gate, deployment path, or external system that can actually allow or block the action.
5. **Attest / prove** — Produce signed/tamper-evident evidence of what was tested, requested, delegated, decided, and authorized.
6. **Verify outcomes** — Compare what actually happened with the authority and result that were approved.
7. **Gate releases** — Use the same assurance model at PR, merge, and deployment boundaries through **Agent Release Assurance**.

The product should reduce reachable authority and blast radius where its integrations can enforce policy. It does **not** claim to prevent every exploit, escape, zero-day, or malicious behavior.

## Authority provenance

Authority is not just a permission bit. For consequential actions, Ledgato/khrystal should increasingly be able to explain:

- who or what granted the authority;
- why and for which task/workflow it was granted;
- which identity, credential, role, or token carries it;
- the agent's effective reachable authority versus declared scope;
- whether the authority is direct, borrowed, or delegated;
- when it expires;
- whether it has drifted;
- whether and how it can be revoked;
- what decision was made when the authority was exercised;
- what actually happened afterward.

Future aligned work includes just-in-time / expiring grants and revocation-aware assurance. Ledgato/khrystal should consume and evaluate upstream identity/grant state rather than recreate the identity provider.

## The engine (working MVP)

The working engine lives in [`engine/`](./engine/) — a Python package (FastAPI backend + CLI) implementing the current assurance/release-gate foundation:

- **Scope as code** — each agent's attack surface declared in `fence.yaml` (allow/deny tools, max impact, data domains).
- **Action checks** — policy checks can be made before a consequential tool/action crossing.
- **Adversarial probes** — a battery (scope escape, impact escalation, exfiltration, injection) for testing declared boundaries.
- **Release attestations** — release decisions can be gated when verification or declared scope does not hold.
- **Signed, proof-of-work ledger** — decisions are written into an append-only, Ed25519-signed, hash-chained ledger.
- **Distributed ledger** — independent nodes can reconcile evidence via longest-valid-chain consensus.
- **Attestation verification & ops** — verify decisions in the live chain, or export a self-contained verifiable report an auditor can check offline.

### Quick start

```bash
cd engine
pip install -e .[dev]
ledgato init --dir .
ledgato attestation --agent ops-agent --release v2.4          # APPROVED (PoW-mined)
ledgato attestation --agent researcher --release v2.4 --drift # GATED (blocked)
ledgato report --agent ops-agent --release v2.4 --out report.json
ledgato report --verify report.json                          # offline verify
ledgato sync --remote http://peer:8000                        # distributed consensus
```

### API

```bash
ledgato api --port 8000
```

`/health` · `/v1/actions/check` · `/v1/probes/run` · `/v1/releases/attest` ·
`/v1/ledger` (+ `status`, `chain`, `reconcile`) ·
`/v1/attestations/verify` · `/v1/attestations/report`

See [`/engine/README.md`](./engine/README.md) for full docs.

## First product surface: Agent Release Assurance

GitHub/CI is the clearest initial surface because it already has a consequential boundary and a native required-check model.

A khrystal-powered release check should be able to surface:

- what the agent changed and why;
- whether the change stayed inside the task and declared authority;
- test and probe evidence;
- permission or scope drift;
- impact/cost context when available;
- **ALLOW / DENY / APPROVE**;
- a durable attestation of the decision.

The same assurance engine should later be embeddable at other boundaries without forcing users through a separate khrystal workflow.

## First-client proof target

The next product claim must be **earned in a real integration**:

> **LEDGATo can actually stop an AI agent from crossing a boundary it was not authorized to cross.**

This does **not** mean merely returning `DENY`. The protected action must be routed through an enforcement point that obeys LEDGATo, so a denied action never reaches the protected system.

The first proof should demonstrate a real **ALLOW** and a real **DENY**, with evidence showing what happened. The preferred initial slice is **agent-os / governed workflow → LEDGATo → GitHub protected action**, unless a controlled HTTP/MCP gateway provides a clearer non-bypassable test.

See [`FIRST_CLIENT_PROOF.md`](./FIRST_CLIENT_PROOF.md) for the acceptance criteria, what does and does not count as proof, and the first-client readiness gate.

## PEART evidence model

PEART remains an internal assurance/evidence model:

- **P — Provenance**: task, workflow, agent, harness, host, model, initiator, delegator, and authority source.
- **E — Evidence**: tests, artifacts, validations, probe results, receipts, and supporting outputs.
- **A — Authority**: policy, permissions, budget, environment, grant/delegation chain, effective authority, expiry, revocation state, and approval context.
- **R — Result**: expected result before execution and actual result after verification.
- **T — Trace**: ordered actions, handoffs, retries, boundary requests, grants/revocations, and decisions.

The goal is for accountability to be **derived from evidence** rather than treated as a vague field.

## Deployment and embedding

Ledgato currently runs as a proxy layer or via a lightweight SDK shim — agents keep operating through their normal execution environment, with the assurance gate sitting between them and consequential tools/actions where integration allows.

The intended khrystal architecture is **independent engine, embedded experience**. Assurance can surface through:

- ailhat approval/review surfaces;
- GitHub pull requests and required checks;
- CI/deployment systems;
- agent-os / Workforce execution boundaries;
- external systems that support a pre-action policy check;
- a standalone khrystal console for policy, evidence history, audit, and integrations.

It can deploy in the user's infrastructure (VPC / on-prem) so scopes and sensitive evidence can remain inside the user's boundary.

---

This repository hosts the public landing page for Ledgato (`index.html`) and the working engine (`/engine/`).
