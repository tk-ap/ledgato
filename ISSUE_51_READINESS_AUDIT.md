# Issue #51 — External Design-Partner Readiness Audit

Date: 2026-09-07

This record reconciles the external-user readiness review against current `main` and the bounded remediation performed on the Issue #51 branch.

## Readiness result

| Level | Status | Reason |
| --- | --- | --- |
| Interview-ready | **YES** | Problem interviews do not require an installed customer environment. |
| Founder-led demo | **CONDITIONAL** | The public/demo experience is strong enough to explain the product, but illustrative state must not be confused with externally verified enforcement. |
| Design-partner-ready | **NOT YET** | One repeatable fresh-repository GitHub integration must pass credential-isolation, restart, deny, approve/resume, exactly-once, and downstream verification gates. |
| Self-serve-ready | **NO / DEFERRED** | Full onboarding, tenant operations, billing/admin and generalized integrations should follow design-partner evidence, not precede it. |

## What is already implemented

The merged enforcement foundation already contains:

- `ALLOW / DENY / APPROVE` decisions;
- a gateway that does not call the protected adapter after `DENY`;
- approval pause, human decision and resume;
- delegated/JIT grants with expiry and revocation;
- GitHub and allowlisted HTTP adapters;
- post-action verification/readback;
- signed ledger evidence;
- a Python HTTP SDK and API surface;
- a real GitHub denial proof in CI.

This means the next step is not a broad rewrite. It is turning the existing foundation into one repeatable external pilot path.

## Durable-state audit

### Existing support

`create_app()` uses file-backed state paths for:

- `ledger.jsonl`;
- `authority.json`;
- `approvals.json`;
- signing keys under `keys/`;
- on this branch, protected-execution idempotency in `idempotency.json`.

`AuthorityStore` loads/saves grants when a path is configured. `ApprovalStore` loads/saves pending/decided/consumed approvals when a path is configured. The ledger is also file-backed.

### Constraint

This persistence model is suitable only for a deliberately constrained single-process pilot after restart testing. Plain JSON files do not establish safe multi-instance concurrency.

### Idempotency remediation on this branch

The Issue #51 branch adds `IdempotencyStore` and an optional caller-supplied `idempotency_key` on protected gateway execution.

Behavior:

- the first request records a durable `PENDING` operation before policy/adapter execution proceeds;
- a completed operation stores the full gateway result and returns that result on identical retries without invoking the protected adapter again;
- reuse of the same key with a different request fingerprint is rejected;
- an operation left `PENDING` after an uncertain/crashed attempt fails closed after restart rather than risking another protected execution;
- state writes use a temporary file + replace operation to reduce partial-write risk in the single-process pilot model.

Regression tests were added for same-process replay, restart replay, conflicting-key rejection, and unresolved-PENDING fail-closed behavior.

**Evidence status:** implementation and tests are present on the branch. They are not considered proven until CI/test execution confirms them.

### Important boundary

This is not a distributed idempotency service or a transaction coordinated with GitHub. If a process dies after a downstream action but before the local result is completed, the durable record remains `PENDING`; the safe behavior is to stop and verify downstream state rather than automatically retry.

## Fail-closed audit

### Gateway behavior

Within the gateway, missing policy/adapter/authority state produces an error or denial rather than silently returning `ALLOW`. A policy `DENY` never calls the protected adapter.

The new idempotency path also fails closed on an unresolved prior operation instead of retrying an action whose downstream outcome may be uncertain.

### System behavior still required

Fail-closed is an end-to-end property, not only a gateway property. The governed agent/harness must be configured so timeout, network failure, service crash, malformed response or unavailable Ledgato **cannot fall back to a direct GitHub credential**.

The first-pilot runbook therefore makes no-bypass credential custody and outage behavior hard gates.

## Credential-custody audit

Current code places the credential inside the GitHub adapter/runtime environment, which is the correct architectural location for enforcement. The product does not yet provide a complete secret-management, rotation or customer onboarding system.

For the first pilot, credential custody remains an explicit operator contract:

- minimum GitHub scope;
- gateway-only storage;
- proof that the agent lacks equivalent protected authority;
- documented rotation/revocation owner;
- break-glass events recorded separately from Ledgato enforcement evidence.

## Public/live claim audit

A fresh review of `https://ledgato.vercel.app/` observed production copy including broad language such as:

- `LIVE · ENFORCING POLICY`;
- `If an agent shouldn't be able to do it, Ledgato stops it.`;
- `If it can reach your stack, Ledgato can see it.`;
- broad continuous-mapping and blocking language.

The same live experience exposes sign-in/signup/demo flows and labels the guest product experience `sample data · not connected`, which is a useful disclosure.

### Source-of-truth mismatch

Current repository `main` contains a static `index.html`, while the observed production Vercel site is a different bundled application experience. Therefore a claim correction committed to the repository cannot honestly be reported as a live production correction until the production deployment source/branch is identified and reconciled.

**Blocker:** identify the exact source/deployment path for `ledgato.vercel.app` before changing production claims. Do not overwrite or promote an unknown deployment merely to make the copy match.

### Required claim boundary

Public language should reflect this condition:

> Ledgato enforces selected consequential actions when they are routed through its non-bypassable gateway and the protected credential is not also available to the governed agent.

Demo/illustrative content should be visibly distinct from real external proof.

The branch README has been tightened to this bounded claim, but that is repository documentation only until the production Vercel source is reconciled and deployed.

## Canonical first-pilot path

The exact operating path is now recorded in `DESIGN_PARTNER_GITHUB_PILOT.md`:

```text
coding agent → Ledgato gateway → protected GitHub action → verification/readback → signed evidence
```

The runbook defines:

- credential custody;
- no-bypass proof;
- policy setup;
- durable state paths;
- request idempotency;
- DENY proof;
- APPROVE/resume proof;
- restart test;
- fail-closed recovery;
- evidence packet;
- fresh-repository external E2E acceptance gate.

## P0 status after this tranche

| P0 item | Status after remediation | Next action |
| --- | --- | --- |
| Public claim boundary | **Repo language tightened; live production unresolved** | Identify Vercel production source, then patch and verify live copy. |
| Canonical GitHub integration path | **RUNBOOK DEFINED** | Exercise it on a fresh external repository. |
| Credential custody | **CONTRACT DEFINED** | Implement/verify against the pilot environment and record bypass test. |
| Durable state | **PARTIALLY IMPLEMENTED** | Run restart test; do not claim multi-instance safety. |
| Idempotency | **IMPLEMENTED ON BRANCH / UNVERIFIED** | Run CI and restart tests; remediate any failures before merge. |
| Fail-closed behavior | **GATE DEFINED + IDEMPOTENCY FAIL-CLOSED ADDED** | Verify harness cannot bypass on outage/error. |
| Fresh external E2E proof | **NOT RUN** | Requires external/fresh repo and credential authorization; do not fabricate. |

## Recommended next tranche

1. Run CI/test suite for the Issue #51 branch and fix any regression.
2. Add/execute an API-level regression proving `idempotency_key` survives service recreation and duplicate calls return the original result.
3. Run persistence/restart tests across approval, authority, idempotency and ledger state.
4. Identify the production Vercel source and reconcile public claims without broadening scope.
5. Run the fresh-repository GitHub E2E only after explicit external credential/repository authorization is available.

## Non-goals

Do not use Issue #51 to justify:

- generalized self-serve SaaS onboarding;
- multiple new provider integrations;
- billing/team/admin infrastructure;
- a new policy engine;
- universal containment claims;
- production deployment changes whose source/ownership is ambiguous.
