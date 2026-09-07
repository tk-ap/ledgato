# Ledgato

**Independent authorization and enforcement for consequential AI actions.**

> **An agent can decide what it wants to do. Ledgato decides whether it is actually allowed to do it.**

Ledgato sits between an AI agent's intent and the systems it can affect. It declares and maps authority, checks consequential crossings before execution, returns **ALLOW / DENY / APPROVE**, and—where correctly integrated—prevents denied actions from reaching the downstream system. It then records and verifies what actually happened.

> *An agent should not gain authority just because it can reach it.*

The canonical enforcement thesis, non-bypassable-path requirement, threat model, and first-client demonstration are in [`ENFORCEMENT_THESIS.md`](./ENFORCEMENT_THESIS.md).

> **Product direction:** this repository records **`khrystal — Agent Assurance`** as the working successor-brand/category direction. **Agent Release Assurance** is the first concrete wedge, not the full product definition. The operational/public product remains Ledgato until an explicit rename implementation is approved. See [`PRODUCT_DIRECTION.md`](./PRODUCT_DIRECTION.md).

## Current go-to-market decision

Ledgato is not entering the market as a universal “AI control” platform. The first commercial wedge is deliberately narrower:

> **Change control for autonomous coding agents: let agents work, but independently authorize and prove every merge, deployment, secret access, and destructive infrastructure change.**

The first offer is a **six-week design-partner pilot** for small AI-native software teams already allowing coding agents to make or propose consequential changes. The pilot must place at least one real action behind a non-bypassable Ledgato enforcement path, measure whether unsafe or unauthorized actions are stopped without making normal work unusable, and end with a paid-continuation decision.

This is a validation-first investment. Do not expand the product, rename it, or market it as production-proven until the customer and technical gates in [`GO_TO_MARKET.md`](./GO_TO_MARKET.md) have been met. The recruiting plan, qualification rules, interview script, and outreach copy are in [`DESIGN_PARTNER_RECRUITING.md`](./DESIGN_PARTNER_RECRUITING.md).

## Why

Agentic systems can cross important boundaries before a pull request or deployment ever exists. Tool access, credentials, data domains, external endpoints, impact levels, infrastructure permissions, delegated workers, and release authority can all drift beyond what a task actually requires.

A one-time security review is only a snapshot. The enforcement question is continuous:

> **Is this agent authorized to cross this boundary, under this task, with this evidence, right now?**

The key distinction is between **reachability** and **authority**. If an agent can technically reach a credential, endpoint, service, production environment, external system, or another agent, that does not mean it should be permitted to use it.

Ledgato/khrystal is intended to make that distinction enforceable and provable without becoming a second agent runtime or a generic observability stack.

## The hard architectural requirement

Ledgato only earns an enforcement claim when the protected action has **no meaningful privileged route around Ledgato**.

If an agent retains a direct credential, alternate adapter, inherited session, network path, or fail-open route that can perform the protected action without a Ledgato decision, then Ledgato is advisory middleware for that boundary—not an enforcement system.

For every protected action, the target architecture is:

```text
Agent / agent workforce
        |
        v
     Ledgato
        |
        +--> GitHub / source control
        +--> CI / deployment
        +--> cloud infrastructure
        +--> protected data
        +--> secrets / credentials
        +--> external APIs
        +--> spending / publishing
        +--> other agents / delegated workers
```

Every discovered bypass is a product failure for that boundary until remediated.

## What it does

1. **Declare & map** — Represent the tools, data domains, endpoints, impact, and other authority an agent is intended to have, then compare that declaration with the surface it can reach.
2. **Discover drift** — Detect newly reachable services, credentials, routes, delegated workers, or other capability that falls outside declared authority.
3. **Probe** — Run adversarial checks for scope escape, impact escalation, exfiltration, injection, bypass, replay, stale authority, and other boundary failures.
4. **Decide** — Resolve consequential boundary requests as **ALLOW / DENY / APPROVE** according to policy, task context, identity, delegation, expiry, and evidence.
5. **Enforce where integrated** — Feed the decision into the tool proxy, execution control plane, GitHub/CI gate, deployment path, or external system that can actually allow or block the action. A denied action must not reach the downstream provider.
6. **Approve & resume** — Pause consequential work when human escalation is required, then resume the same action with narrow temporary authority rather than blanket access.
7. **Delegate least authority** — Use task-bound, time-bound, revocable authority instead of broad standing credentials where integrations permit it.
8. **Verify** — Compare the actual downstream result with what was authorized. The acting agent's success message is evidence, not proof.
9. **Attest** — Produce signed/tamper-evident evidence of what was tested, requested, decided, authorized, executed, and verified.
10. **Gate releases** — Use the same enforcement model at PR, merge, and deployment boundaries through **Agent Release Assurance**.

The product should reduce reachable authority and blast radius where its integrations can enforce policy. It does **not** claim to prevent every exploit, escape, zero-day, or malicious behavior.

## Canonical build sequence

The current product sequence is:

> **Enforcement doorway → approval/resume → live discovery → delegated authority / JIT / revocation → post-action verification → production SDK/gateway/native adapters**

These are not separate feature bets. Together they form the minimum architecture required to make the enforcement claim credible.

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

## First-client proof

The first customer-facing demonstration should be deliberately simple:

> Task: `Update the staging deployment.`

The agent may read the repository, modify the staging branch, and deploy staging. It may **not** read production secrets, deploy production, contact an arbitrary external endpoint, or delegate production authority to another agent.

The demonstration should intentionally create a situation where a production deployment would help the agent accomplish its objective and allow the agent to attempt it.

The observable proof is:

> **The agent tried. Ledgato stopped the unauthorized action.**

Then demonstrate an optional approval flow: human approval → narrow temporary authority → action resume → independent result verification → authority expiry/revocation.

See [`ENFORCEMENT_THESIS.md`](./ENFORCEMENT_THESIS.md) for the complete validation scenario.

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
