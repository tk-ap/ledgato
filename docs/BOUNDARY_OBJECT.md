# Boundary as the first-class LEDGATo object

Status: product/runtime contract.

## Core rule

LEDGATo does not make a global claim that an agent, runtime, or system is
"escape-proof." The strongest claim is scoped to one **enforcement boundary**:

```text
principal + protected action + protected resource + enforcement route + evidence
```

A boundary is the smallest unit LEDGATo may mark `VERIFIED`.

That means "VERIFIED" answers:

> Under the recorded integration/configuration, did this exact protected
> action/resource boundary survive the required attack families and independent
> readback?

It does **not** answer:

> Can this agent never escape anything?

## Product object

The canonical runtime record remains `engine/ledgato/boundary.py::EnforcementBoundary`.
`verification_summary()` derives the owner/API-facing status contract. It does
not introduce a second authority or status source.

Contract: `contracts/enforcement-boundary-status.schema.json`.

Key fields:

- identity: `id`, `provider`, `resource`, `action`;
- enforcement posture: `failure_mode`, `gateway_credential_owner`;
- claim: `bypass_status`;
- attack coverage: required/covered/missing families and tested vector ids;
- open failures: unresolved bypass count;
- independent proof: provider/resource readback present or absent;
- time: last verified, last bypass, last material drift.

## Claim ladder

- `UNVERIFIED`: boundary exists, but bypass resistance has not been earned.
- `PARTIALLY_VERIFIED`: some proof exists, or prior full verification has been
  weakened by material drift.
- `VERIFIED`: all required attack families + independent readback are present
  and no recorded bypass remains unresolved.
- `BYPASS_FOUND`: a protected action occurred through a tested unauthorized
  route. This latches until remediation + a clean vector-bound retest.

Ordinary ALLOW / DENY / APPROVE decisions are operational evidence. They never
promote bypass status.

## Required attack families

The current VERIFIED gate requires evidence from all four:

1. direct/bypass-route attempts;
2. credential leakage attempts;
3. authority escalation attempts;
4. approval abuse attempts.

It also requires provider/resource readback so an in-process fake cannot satisfy
the claim by itself.

## Drift invalidation

Verification is configuration-specific. Material changes can make old evidence
stale even if no bypass has yet been observed.

Examples:

- gateway credential scope or custody changes;
- provider adapter/version behavior changes;
- identity/principal binding changes;
- policy digest or enforcement semantics change;
- delegation/JIT/revocation behavior changes;
- protected resource stops checking the permit;
- network topology or alternate provider routes change;
- a new equivalent credential/session becomes reachable by the agent.

`BoundaryStore.record_drift()` records that evidence and automatically weakens
`VERIFIED → PARTIALLY_VERIFIED`. It never promotes a claim and never clears
`BYPASS_FOUND`.

Future live discovery should call this path when it observes material route or
authority drift. A drift entry starts a new verification epoch: pre-drift attack
evidence remains in history but cannot be reused to restore VERIFIED. Fresh
attack-family coverage and fresh provider/resource readback are required.

## Owner UI

`/app/boundaries` is the primary answer to:

> What exactly is LEDGATo protecting, and how do we know the agent cannot go
> around it?

Verification remains the place to run/review attack suites. Evidence remains
the receipt trail. Authority remains what an agent may do. A boundary is where
those concepts become an enforceable, testable claim.

Historical lab proof must stay visibly labeled as historical/lab evidence until
a live deployment reports engine-derived boundary state.
