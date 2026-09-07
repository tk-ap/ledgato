# GitHub Design-Partner Pilot Runbook

> Status: required path for the first external design-partner pilot
>
> Scope: one coding-agent workflow → Ledgato → one protected GitHub action
>
> This is deliberately not a general self-serve onboarding guide.

## The claim this pilot is allowed to prove

Ledgato can prevent a governed agent/workflow from crossing a selected GitHub boundary **when the protected GitHub credential is held behind the Ledgato enforcement gateway and is not also available to the governed agent**.

The pilot does not prove universal agent containment, universal permission discovery, or protection for systems that can bypass Ledgato.

## First protected action

Prefer one consequential GitHub action with an objectively verifiable downstream result. The default is:

- `github.pull.merge` on a designated pilot repository and protected branch.

A design partner may substitute another supported GitHub action only if the adapter can execute it, verify it, and demonstrate that the agent has no bypass credential.

## Architecture

```text
coding agent / harness
        |
        | request (no protected credential)
        v
Ledgato enforcement gateway
        |
        | ALLOW / DENY / APPROVE
        |
        | protected GitHub credential lives here
        v
GitHub protected action
        |
        v
post-action readback + signed evidence
```

The gateway is the security boundary. A policy decision that the agent can ignore is not enforcement.

## Credential custody contract

Before the pilot begins, record all of the following:

| Field | Required record |
| --- | --- |
| GitHub identity | app/token identity used by the gateway |
| Credential owner | person/team responsible for the credential |
| Storage location | secret store/runtime location; never repository plaintext |
| Repository scope | exact pilot repository or installation scope |
| Action scope | permissions required for the selected action only |
| Agent credential check | evidence that the governed agent does not hold an equivalent bypass credential |
| Rotation path | how the credential is replaced |
| Revocation path | how access is disabled immediately |
| Emergency owner | named human who can revoke/recover the integration |

### Hard gate

Do not call the pilot enforced if the governed agent can directly invoke the same protected GitHub action with another credential.

## Setup sequence

### 1. Choose the pilot repository

Use a fresh repository or a safely constrained repository that was not used for the founder proof. Record:

- repository owner/name;
- protected branch;
- technical owner;
- business/budget owner;
- agent/harness performing the work;
- exact protected action.

### 2. Establish the no-bypass credential path

1. Create or select the minimum-scope GitHub credential for the gateway.
2. Store it only in the Ledgato gateway runtime/adapter environment.
3. Remove equivalent merge/write authority from the governed agent where the selected boundary requires it.
4. Verify from the agent environment that the protected action cannot be performed directly.
5. Record the test result before continuing.

If step 4 fails, stop. The integration is advisory, not enforcing.

### 3. Define the policy

Start from the existing first-client example and make the human intent explicit. For example:

> The coding agent may open and update pull requests. It may not merge the protected branch by default. A merge requires a named human approval tied to this task and pull request. The approval expires after 15 minutes and may be used once.

Compile that intent into the existing `Policy`/authority model; do not create a second policy engine for the pilot.

### 4. Start Ledgato with persistent state paths

The HTTP API already supports file-backed state when explicit paths are supplied:

- ledger: `ledger.jsonl` or an operator-chosen durable path;
- delegated/JIT authority: `authority.json`;
- approvals/resume state: `approvals.json`;
- signing key directory: `keys/`.

For the pilot, these paths must be on storage that survives process restart. Do not rely on ephemeral container filesystems.

### 5. Run the DENY proof

1. Agent requests the protected action through Ledgato.
2. Policy resolves `DENY`.
3. Confirm the adapter execution method was not invoked.
4. Ledgato performs denial readback/verification.
5. Verify GitHub shows the protected action did not occur.
6. Preserve the signed evidence/attestation ID.

Pass condition: the downstream provider confirms the action did not happen and evidence shows the gateway did not execute it.

### 6. Run the APPROVE → resume proof

1. Agent requests an action whose policy resolves `APPROVE`.
2. Ledgato creates a pending approval and does not execute downstream.
3. Named human reviews exact action, task, repository/PR scope, and expiry.
4. Human approves.
5. Ledgato issues the bounded JIT grant if configured.
6. The same pending action resumes using its one-time resume token.
7. Ledgato executes the GitHub adapter exactly once.
8. Post-action readback verifies the expected GitHub state.
9. Preserve the signed evidence/attestation ID.

The existing approval store marks a consumed approval `CONSUMED`, which prevents the same resume token from being reused. This protects the approval/resume path; it is **not yet a general idempotency guarantee for every direct `ALLOW` request**.

### 7. Restart test

Before declaring the pilot operational:

1. create a pending approval;
2. restart the Ledgato service;
3. confirm the pending approval still exists;
4. confirm authority grants/revocations still exist;
5. confirm ledger/evidence remains verifiable;
6. complete or deny the pending action after restart.

Failure of any item blocks design-partner readiness.

## Fail-closed operating rule

For the selected protected GitHub action:

> If Ledgato cannot produce a valid authorization decision, the protected action does not proceed through the governed path.

The coding agent must not treat timeout, connection failure, malformed response, missing policy, unknown grant, missing approval state, or unavailable gateway as permission to bypass Ledgato.

### Recovery

When the gateway is unavailable:

1. stop/retry the protected action; do not fall back to direct provider credentials;
2. notify the technical owner with task/action identity;
3. restore the gateway and durable state;
4. confirm policy, credential custody, grants/revocations, approvals, and ledger health;
5. submit a **new** request unless an existing approval is durably present and valid;
6. verify the downstream GitHub state before resuming normal automation.

Emergency manual intervention is an explicit human break-glass event and must be recorded separately; it is not evidence that Ledgato enforced the action.

## Evidence packet

For each proof run, retain:

- partner/repository identifier;
- agent/harness identifier;
- task ID;
- requested action and target;
- policy decision;
- grant/approval identifiers where applicable;
- approver and expiry where applicable;
- whether the downstream execute method was called;
- downstream execution receipt;
- downstream verification/readback;
- attestation/evidence ID;
- timestamp;
- bypass-credential test result.

## Fresh-repository external E2E acceptance test

A design-partner-ready result requires one fresh external workflow to complete this sequence without modifying Ledgato core code specifically for that repository:

1. connect/configure the GitHub adapter;
2. isolate the protected credential;
3. prove the governed agent cannot bypass the gateway;
4. define one boundary;
5. request an unauthorized action;
6. receive `DENY`;
7. verify the action did not occur;
8. request an approval-required legitimate action;
9. approve with bounded authority;
10. resume and execute exactly once;
11. verify the action occurred;
12. restart the service and confirm durable state/evidence;
13. produce the evidence packet.

Until this passes outside the founder environment, status remains **design-partner candidate**, not externally production-proven.

## Known gaps this runbook does not hide

- Direct `ALLOW` requests do not yet have a general request-level idempotency key/receipt cache in the gateway.
- File-backed JSON state is adequate for a tightly controlled single-process pilot only after restart testing; it is not a multi-instance concurrency design.
- Credential storage/rotation is an operator deployment responsibility today, not a complete Ledgato secret-management product.
- The public Vercel experience is not the canonical installation mechanism for this pilot.
- Additional providers/actions need their own non-bypassable adapter and verification path.

These are readiness gates or constraints, not reasons to broaden the product before the first external GitHub proof.