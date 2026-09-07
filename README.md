# Ledgato

**An agent-assurance + signed-evidence layer for consequential AI actions.**

Ledgato declares and maps the authority an AI agent is intended to have, probes those boundaries adversarially, checks consequential crossings against policy, and records tamper-evident evidence of what was allowed, denied, or approved. Release gating is one important boundary — not the only one.

> *An agent should not gain authority just because it can reach it.*

> **Product direction:** this repository records **`khrystal — Agent Assurance`** as the working successor-brand/category direction. **Agent Release Assurance** is the first concrete wedge, not the full product definition. The operational/public product remains Ledgato until an explicit rename implementation is approved. See [`PRODUCT_DIRECTION.md`](./PRODUCT_DIRECTION.md).

## Current go-to-market decision

Ledgato is not entering the market as a universal “AI control” platform. The first commercial wedge is deliberately narrower:

> **Change control for autonomous coding agents: let agents work, but place selected merges, deployments, secret access, and destructive infrastructure changes behind an independent authorization boundary.**

The first offer is a **six-week design-partner pilot** for small AI-native software teams already allowing coding agents to make or propose consequential changes. The pilot must place at least one real action behind a non-bypassable Ledgato enforcement path, measure whether unsafe or unauthorized actions are stopped without making normal work unusable, and end with a paid-continuation decision.

The canonical first pilot path is documented in [`DESIGN_PARTNER_GITHUB_PILOT.md`](./DESIGN_PARTNER_GITHUB_PILOT.md): **coding agent → Ledgato gateway → protected GitHub action → downstream verification + signed evidence**.

This is a validation-first investment. Do not expand the product, rename it, or market it as production-proven until the customer and technical gates in [`GO_TO_MARKET.md`](./GO_TO_MARKET.md) have been met. The recruiting plan, qualification rules, interview script, and outreach copy are in [`DESIGN_PARTNER_RECRUITING.md`](./DESIGN_PARTNER_RECRUITING.md).

### Current readiness boundary

- **Interview-ready:** yes. Discovery interviews do not require customer integration.
- **Founder-led demo:** available, but demo/sample state must remain clearly distinguished from real enforcement evidence.
- **External design-partner pilot:** not yet declared ready; the fresh-repository E2E gate in `DESIGN_PARTNER_GITHUB_PILOT.md` must pass first.
- **Self-serve SaaS:** deliberately deferred until design-partner evidence determines what should be productized.

## What has actually been proven

The first real enforcement proof used GitHub. The protected credential was held by the Ledgato adapter, Ledgato received a request to perform `github.pull.merge`, policy returned `DENY`, the gateway did not call GitHub's merge endpoint, and a real GitHub readback confirmed the pull request remained unmerged. Signed evidence was produced for the decision.

That supports this bounded claim:

> **Ledgato can stop a governed agent/workflow from crossing a selected boundary when the protected credential is isolated behind the Ledgato gateway and the governed agent cannot bypass that gateway.**

It does **not** establish that Ledgato sees every permission in an arbitrary stack, protects actions that bypass its enforcement path, or stops every exploit/escape/malicious behavior.

## Why

Agentic systems can cross important boundaries before a pull request or deployment ever exists. Tool access, credentials, data domains, external endpoints, impact levels, infrastructure permissions, and release authority can all drift beyond what a task actually requires.

A one-time security review is only a snapshot. The assurance problem is continuous:

> **Is this agent authorized to cross this boundary, under this task, with this evidence, right now?**

Ledgato/khrystal is intended to make that question enforceable and provable without becoming a second agent runtime or a generic observability stack.

## What it does

1. **Declare & map** — Represent the tools, data domains, endpoints, impact, and other authority an agent is intended to have, then compare that declaration with the surface its configured integrations can observe.
2. **Probe** — Run adversarial checks for scope escape, impact escalation, exfiltration, injection, and other boundary failures within the configured test surface.
3. **Decide** — Resolve consequential boundary requests as **ALLOW / DENY / APPROVE** according to policy, task context, and evidence.
4. **Enforce where integrated** — Feed the decision into the tool proxy, execution control plane, GitHub/CI gate, deployment path, or external system that can actually allow or block the action.
5. **Attest** — Produce signed/tamper-evident evidence of what was tested, requested, decided, and authorized.
6. **Gate releases** — Use the same assurance model at PR, merge, and deployment boundaries through **Agent Release Assurance**.

The product should reduce reachable authority and blast radius where its integrations can enforce policy. It does **not** claim to prevent every exploit, escape, zero-day, or malicious behavior.

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

## Deployment and embedding

Ledgato currently runs as a proxy layer or via a lightweight SDK shim — agents keep operating through their normal execution environment, with the assurance gate sitting between them and selected consequential tools/actions where integration allows.

For real enforcement, the protected credential must live with the gateway/adapter and must not also be available to the governed agent. Otherwise the agent can bypass the decision path and Ledgato is advisory rather than enforcing.

The intended khrystal architecture is **independent engine, embedded experience**. Assurance can surface through:

- ailhat approval/review surfaces;
- GitHub pull requests and required checks;
- CI/deployment systems;
- agent-os / Workforce execution boundaries;
- external systems that support a pre-action policy check;
- a standalone khrystal console for policy, evidence history, audit, and integrations.

It can deploy in the user's infrastructure (VPC / on-prem) so scopes and sensitive evidence can remain inside the user's boundary.

### Pilot persistence constraint

The current API supports file-backed ledger, approval, authority, and signing-key state. A constrained single-process pilot must place these files on durable storage and pass restart testing. This should not be represented as multi-instance production persistence or concurrency safety.

The approval/resume path is one-time: a consumed approval cannot be resumed again. General request-level idempotency for repeated direct `ALLOW` requests remains a design-partner readiness gap.

---

This repository hosts the public landing page for Ledgato (`index.html`) and the working engine (`/engine/`). The production Vercel experience must be reconciled separately before public claim changes are considered deployed.