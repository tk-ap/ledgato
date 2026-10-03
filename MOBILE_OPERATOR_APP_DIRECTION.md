# LEDGATo Native Operator App Direction

> Status: **approved product direction; implementation intentionally deferred**
>
> Decision date: 2026-10-03
>
> Implementation gate: do not begin the product build until AgentOS has independently demonstrated the required end-to-end autonomy and persistence proof. This record exists so AgentOS can move directly from proven infrastructure into bounded implementation without reopening product ideation.

## Decision

LEDGATo should become a native iOS/Android **operator app** for consequential agent authority decisions.

The app is not the enforcement system and is not a second runtime. It is a trusted human decision client for the existing LEDGATo authorization/enforcement system.

The target interaction replaces Telegram as the canonical human approval surface:

```text
agent/runtime
    ↓
LEDGATo enforced boundary
    ↓
durable approval challenge
    ↓
APNs / FCM notification
    ↓
LEDGATo mobile app
    ↓
biometric-gated device signing
    ↓
LEDGATo verifies scoped decision
    ↓
durable evidence
    ↓
originating AgentOS workflow resumes or remains blocked
```

Telegram may remain during migration as an out-of-band fallback and observability channel. It must not remain an independent source of authorization truth.

## Non-negotiable trust boundary

Use this separation everywhere:

> **Push is notification. LEDGATo is authorization. The mobile app is an authenticated decision client. AgentOS remains execution.**

Consequences:

- APNs/FCM delivery must never constitute approval.
- The app must fetch the authoritative request from LEDGATo after opening.
- LEDGATo server state is canonical for request scope, policy, expiry, status, evidence, and consumption.
- No valid network connection means no new approval; fail closed.
- Closing, uninstalling, crashing, or losing the app must not weaken an already configured enforcement boundary.
- An approval is valid only for the exact stored action it was created for.
- AgentOS must resume from the verified LEDGATo decision, not from a local app event or push receipt.

## Recommended implementation stack

### Mobile client

- **React Native + Expo**
- **Expo Router**
- development builds / EAS for iOS and Android packaging
- `expo-notifications` for notification handling
- `expo-local-authentication` for the local biometric ceremony
- `expo-secure-store` for session material and small client secrets

Do not use Capacitor as the default for this app. LEDGATo's mobile client sits in a security-sensitive authorization path and should have a deliberately narrow native security boundary rather than making a general-purpose webview the center of the trust path.

### Existing product/backend

Preserve LEDGATo's current web/backend infrastructure on Vercel unless implementation evidence justifies a migration.

Use durable **Postgres** state for approval truth. Supabase is an acceptable implementation candidate if LEDGATo does not already have a suitable durable Postgres layer; do not add it merely because it shortens a tutorial path.

### Push transport

- iOS: APNs
- Android: FCM

Prefer LEDGATo backend delivery directly to APNs/FCM for the production path. Expo may provide client libraries/build tooling without becoming the authorization intermediary.

Apple/Google push services are delivery dependencies, not authorization dependencies.

### Device security

The approval-signing key must be device-bound and non-exportable where the platform supports it:

- iOS: Secure Enclave / Keychain-backed key material plus App Attest
- Android: Android Keystore plus Play Integrity

Biometrics should authorize use of the device-bound signing operation. A successful Face ID/fingerprint prompt by itself is not server proof of approval.

Conceptual flow:

```text
Face ID / biometric
    ↓
allows local key operation
    ↓
device-bound private key signs exact LEDGATo challenge
    ↓
LEDGATo verifies signature + device + attestation + nonce + expiry + scope
```

## Approval record and lifecycle

The backend should own a durable state machine such as:

```text
PENDING
 ├─ APPROVED
 ├─ DENIED
 ├─ EXPIRED
 ├─ REVOKED
 └─ SUPERSEDED
```

An approval record should be capable of binding at least:

- approval/request ID
- principal / agent ID
- originating workflow/task ID
- exact requested action
- resource / environment
- applicable policy and policy version/hash
- requested scope
- created/expiry timestamps
- single-use nonce/challenge
- approver identity
- trusted device identity
- final decision
- decision timestamp
- device signature
- attestation result
- permit/resume reference
- execution/evidence receipt reference

Decision consumption must be atomic. Two devices, retries, Telegram fallback, notification redelivery, or replay must not permit the same approval to authorize multiple executions.

## Required security properties

The first serious acceptance suite must prove, not merely assert:

- an approval cannot be replayed;
- an approval cannot be reused for a different action/resource/principal;
- an expired approval cannot execute;
- a revoked device cannot authorize;
- a push payload does not contain executable authority;
- notification delivery/interaction cannot itself approve;
- local biometric success is not treated as server authentication;
- the approval signing key cannot be exported as ordinary application data;
- simultaneous decisions from multiple devices resolve at most once;
- changing the action after approval invalidates that approval;
- AgentOS cannot bypass the LEDGATo protected path within the tested boundary;
- failure defaults to blocked/approval-required rather than allowed;
- successful execution produces evidence that binds the approved action to the actual result;
- provider-side verification remains the final witness of consequential impact.

A generic AI security review for leaked keys, validation, and rate limiting is useful hygiene but is not sufficient acceptance evidence for the authorization core.

## AI-buildable surface vs. security core

AgentOS and its routed coding agents are expected to build this product. The implementation should explicitly separate fast AI-generated product work from the narrow security-critical kernel.

### AI-buildable product surface

Agents may rapidly scaffold and iterate:

- onboarding
- navigation
- approval inbox UI
- approval detail/explanation UI
- activity/evidence views
- agents/authority views
- settings
- app-store presentation assets
- public landing/support/privacy surfaces
- non-authoritative design-system components

### Security-critical kernel

Treat these as separately testable and independently reviewed:

- device enrollment
- trusted-device revocation/replacement
- challenge construction
- nonce and replay protection
- exact-scope binding
- device-bound key generation/use
- biometric-gated signing
- App Attest / Play Integrity integration
- signature verification
- atomic decision consumption
- server-side state transitions
- resume/permit issuance
- execution/evidence binding

AI may implement these components, but an agent's own statement that its security audit passed is not acceptance evidence. The critical path requires explicit automated tests plus independent verification under the AgentOS verifier-independence rules.

## First vertical slice

Do not begin with the full operator product. Prove one narrow loop:

1. Enroll one iPhone as a trusted LEDGATo approver device.
2. AgentOS reaches one real protected test action.
3. LEDGATo creates a durable `PENDING` approval challenge.
4. LEDGATo sends an APNs notification containing only enough information/deep link to locate the request safely.
5. Tapping the notification opens the exact approval in LEDGATo.
6. The app fetches the authoritative request from LEDGATo.
7. Face ID unlocks use of the device-bound signing key.
8. The app signs the exact challenge.
9. LEDGATo verifies device, attestation, signature, nonce, expiry, request state, and scope.
10. LEDGATo atomically records `APPROVED` or `DENIED`.
11. On approval, the exact originating AgentOS workflow resumes once.
12. LEDGATo records the approval + execution + downstream verification evidence.
13. The receipt becomes inspectable in the app.

Telegram remains fallback/observability during this proof and is not the canonical decision authority.

## First-slice stop conditions

Stop and report rather than broadening scope if:

- AgentOS has not yet passed the prerequisite E2E autonomy/persistence proof;
- the current LEDGATo approval/status path is still restart-volatile where durability is required;
- the protected AgentOS action can bypass the enforced LEDGATo boundary;
- the implementation requires treating push delivery as approval;
- a device-bound key cannot be proven non-exportable in the chosen implementation;
- approval/resume cannot be made single-use and idempotent;
- downstream execution cannot be independently verified;
- a proposed shortcut weakens fail-closed behavior.

## Explicitly deferred until after the vertical slice

Do not let these expand the first task:

- policy editing in the mobile app
- rich agent dashboards
- team/multi-human approval workflows
- quorum approvals
- organization administration
- generalized emergency containment UI
- Android parity before the iPhone proof is stable, unless implementation economics make a shared change trivial
- sophisticated approval-learning UX
- broad analytics

## Natural product expansion after proof

If the core loop is verified, the operator app may grow into:

- **Inbox** — authority requests awaiting the operator
- **Activity** — consequential actions and outcomes
- **Agents** — principals and current delegated authority
- **Policies** — what can happen autonomously vs. requires approval
- **Devices** — trusted approver devices and revocation
- **Evidence** — approval/execution/verification receipts
- **Emergency** — suspend/revoke an agent, workflow, credential path, or integration under separately authorized containment semantics

The emergency surface is a natural extension of LEDGATo's containment/recovery model, not part of the initial approval proof.

## AgentOS implementation gate

This direction is approved now, but **implementation is deliberately gated**.

AgentOS should pick this up only after the canonical E2E autonomy/persistence milestone demonstrates that it can:

- claim an authorized bounded task;
- persist the task/workflow state through the relevant runtime lifecycle;
- route to an available harness/host;
- survive pause/wait/restart boundaries as required;
- request human authorization without losing the original task state;
- resume the exact workflow after valid approval;
- preserve independently reviewable evidence;
- avoid silently closing work when an owner or verifier boundary is reached.

Once that proof exists, LEDGATo mobile is intended to be a strong real-world AgentOS build: AgentOS should use this document as product/architecture context rather than reopening the stack and trust-boundary decisions from scratch.

## Relationship to existing LEDGATo direction

This decision extends, rather than replaces, the existing principles:

- independent engine, embedded experience;
- `ALLOW / DENY / APPROVE → enforce → verify → evidence`;
- closing the web UI must not weaken enforcement;
- human questions should appear in the surface the operator is already using;
- approvals are scoped and never silently create standing authority;
- an approval client is not the enforcement boundary;
- provider-side evidence remains required to substantiate claims of impact.

The native operator app becomes the preferred first-party human approval surface. The web console remains useful for deeper configuration and evidence. Third-party channels become optional adapters/fallbacks rather than the canonical operator experience.
