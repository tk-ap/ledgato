# Agent Instructions

## Product Role

LEDGATo is the ecosystem's **governance and enforcement** surface. It is relevant when agent work materially involves release gating, declared scope, adversarial boundary testing, drift detection, attestations, enforcement evidence, or another concrete governance control.

LEDGATo is not the generic workforce router and should not absorb every sensitive action merely because it involves permissions or risk.

### Boundary

- Agent OS / Workforce owns shared workforce composition, task resolution, agents, skills, handoffs, workflows, host/harness selection, and execution semantics.
- Agent Control owns generic authorization intelligence where integrated: whether an action is allowed, denied, scoped, or requires human approval.
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
