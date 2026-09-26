# Agent Instructions

## Product Role

LEDGATo is the ecosystem's **governance and enforcement** surface. It is relevant when agent work materially involves release gating, declared scope, adversarial boundary testing, drift detection, attestations, enforcement evidence, or another concrete governance control.

LEDGATo is not the generic workforce router and should not absorb every sensitive action merely because it involves permissions or risk.

### Boundary

- Agent OS / Workforce owns shared workforce composition, task resolution, agents, skills, handoffs, workflows, host/harness selection, and execution semantics.
- Agent Control is the authorization-intelligence **role** inside the Agent OS control plane (not a separate product or repository): deciding whether an action is allowed, denied, scoped, or requires human approval. At the boundaries LEDGATo enforces, LEDGATo's decision engine fills that role; elsewhere, Agent OS applies its static autonomy policy. LEDGATo does not become the ecosystem-wide owner of every authorization question.
- ALVIRA / MeOS owns Context Intelligence.
- ailhat owns Portfolio Intelligence and may propose evidence-backed work.
- LEDGATo owns governance/enforcement behavior and evidence only where that behavior is actually implemented and relevant.

Do not redefine those roles locally.

## Evidence Truth

The repository contains an engine and public product claims, but agents must preserve execution-state distinctions:

- **implemented** means code exists;
- **tested** means relevant tests passed in a known environment;
- **previewed** means a preview/runtime was reachable;
- **verified** means the intended behavior was actually checked;
- **deployed** means it is running in the claimed target environment;
- **user-validated** means the intended user/operator accepted the behavior.

Do not claim production enforcement merely because a CLI/API path or test suite exists. Enforcement, release gating, distributed evidence, or signed-attestation claims should be tied to verifiable runtime evidence at the level being asserted.

Signed or tamper-evident evidence proves only what its verification actually establishes; it does not grant task authority by itself.

## Implemented Integration Surface

These exist in this repository. Report them at the evidence state shown, not higher.

| Surface | Where | Evidence state |
|---|---|---|
| Consequential-action checkpoint: action contract → decision → single-use signed permit → protected resource | `POST /v1/enforcement/decide`, `engine/ledgato/enforcement.py`, `protected_resource.py`, `integrations/protected_executor.py`, `contracts/action-contract.schema.json`, `contracts/enforcement-permit.schema.json` | implemented, tested, verified in a local two-process lab (`engine/ENFORCEMENT_BOUNDARY_PROOF.md`); **not deployed, not adopted by agent-os** |
| Authority resolution for declared governed work | `POST /v1/authority/resolve`, `GET /v1/authority/status/{work_id}`, `contracts/authority-*.schema.json`, `contracts/capability-manifest.schema.json` | implemented, tested; status is in-memory |
| Enforcement gateway with adapter-held credentials | `POST /v1/gateway/execute`, `engine/ENFORCEMENT.md` | implemented, tested; GitHub merge denial independently verified in a lab repository |

These evaluate declared policy **at a boundary Ledgato enforces**. That is governance/enforcement, not generic authorization intelligence: Ledgato does not become the ecosystem-wide owner of whether any action is allowed. Where an applicable authority/policy reference exists upstream, consume it rather than replacing it.

At completion of material work, report: product result, ecosystem implications, cross-product opportunities (subject to `policies/CROSS_MARKET_POLICY.md`), and a boundary check.

## Protocol Adapter Direction

For MCP, A2A, x402, AP2, UCP, Visa TAP, AP4M, or other agent-protocol integration work, read the protocol-integration section of `PRODUCT_DIRECTION.md` before planning or implementation.

Treat MCP, A2A, and x402 as the first **directional adapter targets** and AP2, UCP, Visa TAP, and AP4M as future interoperability targets. None are implemented-support claims unless the repository's evidence table and runtime verification explicitly say otherwise.

Protocol adapters must:

- map protocol-native actions/evidence into the existing Ledgato boundary model rather than inventing a separate authorization engine;
- preserve upstream authority provenance and consume applicable policy/authorization references;
- never widen delegated authority, scope, budget, context, tools, or time;
- keep reusable wallet/payment/provider credentials outside policy records;
- preserve `ALLOW / DENY / APPROVE → enforce → verify → evidence` semantics at the protected boundary;
- avoid displacing the current Agent Release Assurance / first-client enforcement proof without explicit reprioritization.

## Repository Safety

- Start material work from current `main` on a task branch.
- Inspect open pull requests before changing overlapping engine, API, scope, ledger, or deployment surfaces.
- Keep secrets, private keys, tokens, credentials, and reusable session material out of the repository.
- Preserve human/policy gates for merge, production, destructive actions, credential changes, and enforcement activation unless explicitly authorized for the task.
- Do not weaken a gate simply to make an integration or demo easier to complete.

## Agent OS Control-Plane Integration

This repository participates in `tk-ap/agent-os` as the canonical shared workforce/control-plane layer.

Before material planning or implementation:

1. Read Agent OS `BOOTSTRAP.md` and `registry/product-routing.yaml`.
2. Read this repository's `.agent-os/product.yaml` and `.agent-os/integration-surface.yaml`.
3. Confirm that governance/enforcement is materially part of the requested outcome before routing work into LEDGATo.
4. Use `contracts/work-item.schema.json` for cross-product governance/enforcement work and `contracts/capability-manifest.schema.json` when the relevant agent/tool surface must be declared.
5. Return gate/probe/attestation/enforcement evidence through `contracts/outcome-event.schema.json` when useful.
6. Do not interpret a reachable host, harness, credential, or signing capability as permission to use it.
7. Generic authorization requests remain with the authorization-intelligence layer; LEDGATo should consume the applicable authority/policy reference rather than silently becoming that decision owner.

The normal chain is:

`governed task → applicable authority/policy → declared capability/scope → LEDGATo governance or enforcement check → verifiable evidence → Agent OS outcome loop`

Agent OS / Workforce is shared infrastructure, not a public LEDGATo offering. LEDGATo should remain independently useful as governance/enforcement capability while composing with the wider control plane when appropriate.
