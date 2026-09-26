# Issue #51 — External Design-Partner Readiness Audit

Date: 2026-09-07

This record reconciles the external-user readiness review against current `main` and the bounded remediation performed on this branch.

## Readiness result

| Level | Status | Reason |
| --- | --- | --- |
| Interview-ready | **YES** | Problem interviews do not require an installed customer environment. |
| Founder-led demo | **CONDITIONAL** | The public/demo experience can explain the product, but illustrative state must not be confused with externally verified enforcement. |
| Design-partner-ready | **NOT YET** | A fresh-repository GitHub integration still must pass credential-isolation, real pilot restart, approve/resume, exactly-once, and downstream verification gates. |
| Self-serve-ready | **NO / DEFERRED** | Full onboarding, tenant operations, billing/admin and generalized integrations should follow design-partner evidence. |

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

The next step is not a broad rewrite. It is turning the existing foundation into one repeatable external pilot path.

## Durable-state and idempotency audit

### Existing support

`create_app()` uses file-backed state paths for:

- `ledger.jsonl`;
- `authority.json`;
- `approvals.json`;
- signing keys under `keys/`;
- on this branch, protected-execution idempotency in `idempotency.json`.

`AuthorityStore` and `ApprovalStore` load/save state when paths are configured. The ledger is file-backed as well.

### Constraint

This persistence model is suitable only for a deliberately constrained **single-process pilot** after real deployment restart testing. Plain JSON files do not establish safe multi-instance concurrency.

### Idempotency remediation on this branch

This branch adds `IdempotencyStore` and an optional caller-supplied `idempotency_key` on protected gateway execution.

Behavior:

- deterministic local prerequisites (policy, adapter, grant/decision) are validated before a key is reserved, so harmless configuration errors do not poison an operation key;
- immediately before a protected decision is materialized, the operation is durably recorded as `PENDING`;
- a completed operation stores the full gateway result and returns that result on identical retries without invoking the protected adapter again;
- reuse of the same key with a different request fingerprint is rejected;
- an operation left `PENDING` after an uncertain/crashed attempt fails closed after restart rather than risking another protected execution;
- state writes use a temporary file + replace operation to reduce partial-write risk in the single-process pilot model;
- the Python SDK exposes the same idempotency key.

Regression coverage includes same-process replay, store reload/restart replay, conflicting-key rejection, unresolved-PENDING fail-closed behavior, API replay, and API service recreation.

### Validation result

GitHub Actions run `34150297103` completed successfully on this branch:

- `test`: **SUCCESS** — install and full test step completed successfully;
- `github-denial-proof`: **SUCCESS** — the existing real GitHub denial proof still passed and uploaded signed proof evidence.

This validates the branch in CI, including the new idempotency regression coverage. It does **not** substitute for a real external pilot restart/no-bypass test.

### Important boundary

This is not a distributed idempotency service or a transaction coordinated with GitHub. If a process dies after a downstream action but before the local result is completed, the durable record remains `PENDING`; the safe behavior is to stop and verify downstream state rather than automatically retry.

## Fail-closed audit

Within the gateway, missing policy/adapter/authority state produces an error or denial rather than silently returning `ALLOW`. A policy `DENY` never calls the protected adapter. The new idempotency path also fails closed on an unresolved prior operation.

Fail-closed is still an **end-to-end property**. The governed agent/harness must be configured so timeout, network failure, service crash, malformed response or unavailable Ledgato cannot fall back to a direct GitHub credential.

## Credential-custody audit

Current code places the protected credential inside the GitHub adapter/runtime environment, which is the correct architectural location for enforcement. The product does not yet provide a complete secret-management, rotation or customer onboarding system.

For the first pilot, credential custody is an explicit operator contract:

- minimum GitHub scope;
- gateway-only storage;
- proof that the governed agent lacks equivalent protected authority;
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

Current repository `main` contains a static `index.html`, while the observed production Vercel site is a different bundled application experience. Therefore a claim correction committed to this repository cannot honestly be reported as a live production correction until the production deployment source/branch is identified and reconciled.

**Blocker:** identify the exact source/deployment path for `ledgato.vercel.app` before changing production claims. Do not overwrite or promote an unknown deployment merely to make copy match.

### Required claim boundary

Public language should reflect this condition:

> Ledgato enforces selected consequential actions when they are routed through its non-bypassable gateway and the protected credential is not also available to the governed agent.

Demo/illustrative content should be visibly distinct from real external proof.

The current canonical README/`ENFORCEMENT_THESIS.md` already center the correctly integrated/non-bypassable condition. The live deployment must be reconciled separately.

## Canonical first-pilot path

The operating path is recorded in `DESIGN_PARTNER_GITHUB_PILOT.md`:

```text
coding agent → Ledgato gateway → protected GitHub action → verification/readback → signed evidence
```

The runbook defines credential custody, no-bypass proof, policy setup, durable state paths, request idempotency, DENY proof, APPROVE/resume proof, restart test, fail-closed recovery, evidence packet, and fresh-repository external E2E acceptance.

## P0 status after this tranche

| P0 item | Status | Next action |
| --- | --- | --- |
| Public claim boundary | **Canonical repo language bounded; live production unresolved** | Identify Vercel production source, patch there, verify live. |
| Canonical GitHub integration path | **RUNBOOK DEFINED** | Exercise on a fresh external repository. |
| Credential custody | **CONTRACT DEFINED** | Verify in pilot environment and record bypass test. |
| Durable state | **CI RECREATION TESTED; REAL PILOT RESTART STILL REQUIRED** | Run actual service restart on pilot host; do not claim multi-instance safety. |
| Idempotency | **CI VERIFIED ON BRANCH** | Validate against the real GitHub pilot path before calling external proof complete. |
| Fail-closed behavior | **GATE DEFINED + IDEMPOTENCY FAIL-CLOSED VERIFIED IN CI** | Verify harness cannot bypass on outage/error. |
| Fresh external E2E proof | **NOT RUN** | Requires fresh repo and explicit credential/repository authorization. |

## Next gates

1. Identify the production Vercel source and reconcile live claims without broadening scope.
2. Run real pilot persistence/restart checks across approval, authority, idempotency and ledger state.
3. Verify the governed harness has no direct/fail-open GitHub credential path.
4. Run the fresh-repository GitHub E2E only with explicit external credential/repository authorization.

## Non-goals

Do not use Issue #51 to justify generalized self-serve SaaS onboarding, multiple new provider integrations, billing/team/admin infrastructure, a new policy engine, universal containment claims, or ambiguous production deployment changes.
