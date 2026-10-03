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

## Product Delivery Invariant

Ledgato enforcement must not depend on the user keeping the website open. Treat the browser UI as a control room for configuration, approvals, protected-system status, activity/evidence, policies, and integrations—not as the runtime that activates or sustains governance.

Before material authenticated-frontend work, read `FRONTEND_ARCHITECTURE.md` and preserve this invariant:

> **Closing the Ledgato tab must not weaken, disable, or pause an already configured enforcement boundary.**

### Inline Decision Prompt invariant

When a governed action pauses for human approval, the authority question should
appear in the surface the owner is already using (web control room, agent chat,
TUI, Telegram, or another approved client) rather than requiring a visit to the
Ledgato site.

All channels must render the same server-derived `DecisionPrompt` contract.
A channel may change layout, button style, or verbosity; it may not invent a
different scope, approval object, or decision semantics.

The default consequential choices are `Allow once`, `Deny`, and
`Why was this held?`. `Allow once` must resume the exact stored action
server-side and must not create standing authority. Informational inspection
must never grant authority.

A skill/prompt may help an agent understand Ledgato responses, but it is not an enforcement boundary. Prefer adapters, SDK/gateway hooks, or other execution-path controls that the agent cannot simply reason around.

## Strategic Architecture Reference

Before material enforcement architecture, protocol interoperability, production-hardening, or operator-terminal work, read `STRATEGIC_ARCHITECTURE_DIRECTION_2026-10.md`.

Preserve these additional rules:

- converge the live provider-backed proof and signed-permit proof rather than creating parallel production paths;
- treat exact request/parameter binding, shared transactional state, provider/resource-originated evidence, and elimination of equivalent bypass credentials as production architecture requirements;
- preserve what-you-see-is-what-you-sign for human approval;
- bind consequential actions to relevant tool/server/schema provenance;
- preserve consequential context-source provenance when supplied by the runtime, without turning context into authority;
- prefer interoperability with MCP/A2A/runtime-control/workload-identity standards over rebuilding their commodity layers;
- signed protocol intent is provenance/evidence, not sufficient authorization.

## Native Operator App Guardrail

The approved native mobile direction is recorded in `MOBILE_OPERATOR_APP_DIRECTION.md`. Read it before planning or implementing mobile approvals, push notifications, trusted-device enrollment, biometric confirmation, device signing, App Store / Play Store clients, or changes intended to replace Telegram as an approval surface.

Preserve these rules:

- the mobile app is an authenticated decision client, not the authorization authority or execution runtime;
- push is notification only; APNs/FCM delivery or interaction must never constitute approval;
- LEDGATo server state remains authoritative for scope, status, expiry, decision consumption, and evidence;
- approvals must be exact-scope, expiring, replay-resistant, single-use, and fail closed;
- biometric success gates a device-bound signing operation; it is not sufficient server proof by itself;
- Telegram may remain a fallback during migration but must not become a second independent source of authorization truth;
- security-critical device/signing/resume paths require explicit tests and independent verification, not only an agent-authored security review;
- do not start the product build until the AgentOS E2E autonomy/persistence implementation gate in `MOBILE_OPERATOR_APP_DIRECTION.md` is satisfied.

### Operator terminal / Moshi guardrail

If mobile work touches SSH, Mosh, Moshi, Herdr, tmux, remote shell access, or terminal-level intervention:

- treat Moshi/SSH/Mosh as **operator access**, never as LEDGATo approval authority;
- opening a shell, attaching to a session, or typing a command must not create or imply an `APPROVE` decision;
- prefer documented Moshi deep links for active sessions before rebuilding a terminal client;
- preserve the existing private-network/key-only host-access posture; do not expose a public shell for convenience;
- when an exact command only needs human authorization, use the normal signed LEDGATo approval path and let AgentOS execute it;
- reserve manual terminal access for genuinely human-only/interactive intervention;
- AgentOS remains canonical for deferred operator actions and execution lifecycle;
- completion of a manual intervention requires runtime/provider evidence, not a UI checkbox;
- do not embed Mosh/Blink/Moshi-derived code without explicit license/security review.

## Progressive Authority Calibration Guardrail

When designing or implementing onboarding, authority configuration, approval learning, or policy refinement, read the Progressive Authority Calibration section of `PRODUCT_DIRECTION.md`.

Preserve these rules:

- do not require a comprehensive upfront authority interview when a minimal safe baseline plus contextual decisions can resolve authority more accurately;
- ALVIRA/context may decide what to ask, not what authority to grant;
- use close-ended, typed questions for consequential authority whenever possible;
- unknown/unanswered consequential authority must not expand authority;
- contextual approvals should be scoped by principal, action, resource, conditions, duration/expiry, and delegation where applicable;
- valid approval/resume should return control to the originating autonomous workflow rather than requiring the user to operate Ledgato continuously;
- repeated approvals may generate a proposed standing rule, but must never silently broaden active policy;
- the activated source of truth is structured authority produced from explicit answers, not an LLM prose interpretation.

## Jev Pre-Decision Guardrail

For Jev-related work, read `JEV_PREDECISION_BOOTSTRAP.md` and the Jev section of `PRODUCT_DIRECTION.md`.

Jev is advisory pre-decision intelligence only. It may classify requests, match candidate policy, detect novelty, identify missing authority dimensions, select minimal contextual questions, and propose narrow rule refinements. It may not grant authority, issue permits, activate policy, or return the authoritative enforcement decision.

Do not promote Jev into a live enforcement path until its benchmark is run and the architecture preserves a deterministic Ledgato policy decision between Jev output and execution.

## Protocol Adapter Direction

For MCP, A2A, x402, AP2, UCP, Visa TAP, AP4M, or other agent-protocol integration work, read the protocol-integration section of `PRODUCT_DIRECTION.md` before planning or implementation.

Treat MCP and A2A as the first **directional adapter targets**. Treat x402 as an **implemented but dormant adapter**: code/tests exist, but wallet activation, funding, and a live spending proof are deferred until the POC-first milestone in #63. AP2, UCP, Visa TAP, and AP4M remain future interoperability targets. Never infer activated support from design direction alone; use the repository evidence table and runtime verification state.

Protocol adapters must:

- map protocol-native actions/evidence into the existing Ledgato boundary model rather than inventing a separate authorization engine;
- preserve upstream authority provenance and consume applicable policy/authorization references;
- never widen delegated authority, scope, budget, context, tools, or time;
- keep reusable wallet/payment/provider credentials outside policy records;
- preserve `ALLOW / DENY / APPROVE → enforce → verify → evidence` semantics at the protected boundary;
- treat wallet funding, production network enablement, or production credential configuration as an **enforcement activation event** requiring explicit review rather than routine setup;
- for x402, follow the deferred test-wallet/Base-Sepolia/single-resource/tiny-cap activation sequence in `PRODUCT_DIRECTION.md` after #63;
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
