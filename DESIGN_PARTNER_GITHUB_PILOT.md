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

The HTTP API supports file-backed state:

- ledger: `ledger.jsonl` or an operator-chosen durable path;
- delegated/JIT authority: `authority.json`;
- approvals/resume state: `approvals.json`;
- protected-execution idempotency: `idempotency.json`;
- signing key directory: `keys/`.

For the pilot, these paths must be on storage that survives process restart. Do not rely on ephemeral container filesystems.

Every protected execution request should include a stable `idempotency_key` for that logical operation. A completed key returns its recorded result instead of calling the protected adapter again. Reusing the same key for a different request is rejected. If a previous attempt is left unresolved/PENDING after a crash, Ledgato fails closed and requires downstream-state verification rather than risking a second execution.

This is intentionally a single-process pilot mechanism, not a distributed lock.

### 5. Run the DENY proof

1. Agent requests the protected action through Ledgato with a stable `idempotency_key`.
2. Policy resolves `DENY`.
3. Confirm the adapter execution method was not invoked.
4. Ledgato performs denial readback/verification.
5. Verify GitHub shows the protected action did not occur.
6. Preserve the signed evidence/attestation ID.
7. Retry the identical request with the same key and confirm no new downstream execution occurs.

Pass condition: the downstream provider confirms the action did not happen and evidence shows the gateway did not execute it.

### 6. Run the APPROVE → resume proof

1. Agent requests an action whose policy resolves `APPROVE`, with a stable `idempotency_key`.
2. Ledgato creates one pending approval and does not execute downstream.
3. Retrying the same initial request with the same key returns the same recorded approval result rather than creating another approval.
4. Named human reviews exact action, task, repository/PR scope, and expiry.
5. Human approves.
6. Ledgato issues the bounded JIT grant if configured.
7. The same pending action resumes using its one-time resume token.
8. Ledgato executes the GitHub adapter exactly once.
9. Post-action readback verifies the expected GitHub state.
10. Preserve the signed evidence/attestation ID.

The approval store marks a consumed approval `CONSUMED`, which prevents the same resume token from being reused.

### 7. Restart test

Before declaring the pilot operational:

1. create a completed protected execution with an `idempotency_key`;
2. restart the Ledgato service;
3. retry that same logical operation and confirm the recorded result is returned without another adapter execution;
4. create a pending approval;
5. restart again and confirm the pending approval still exists;
6. confirm authority grants/revocations still exist;
7. confirm ledger/evidence remains verifiable;
8. complete or deny the pending action after restart.

Also test an intentionally unresolved PENDING idempotency record: after restart, Ledgato must refuse to execute it again until an operator verifies downstream state.

Failure of any item blocks design-partner readiness.

## Fail-closed operating rule

For the selected protected GitHub action:

> If Ledgato cannot produce a valid authorization decision, the protected action does not proceed through the governed path.

The coding agent must not treat timeout, connection failure, malformed response, missing policy, unknown grant, missing approval state, unresolved idempotency state, or unavailable gateway as permission to bypass Ledgato.

### Recovery

When the gateway is unavailable or an operation is left in uncertain/PENDING state:

1. stop the protected action; do not fall back to direct provider credentials;
2. notify the technical owner with task/action/idempotency identity;
3. verify the downstream GitHub state before deciding whether another execution is safe;
4. restore the gateway and durable state;
5. confirm policy, credential custody, grants/revocations, approvals, idempotency records, and ledger health;
6. reuse a completed key only to retrieve its prior result; do not mutate the request behind an old key;
7. create a new operation key only after verifying the prior attempt did not already cross the boundary;
8. verify the downstream GitHub state before resuming normal automation.

Emergency manual intervention is an explicit human break-glass event and must be recorded separately; it is not evidence that Ledgato enforced the action.

## Evidence packet

For each proof run, retain:

- partner/repository identifier;
- agent/harness identifier;
- task ID;
- idempotency key;
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
5. request an unauthorized action with a stable idempotency key;
6. receive `DENY`;
7. verify the action did not occur;
8. retry and verify no downstream action occurs;
9. request an approval-required legitimate action with a new stable idempotency key;
10. retry the initial request and verify no duplicate approval is created;
11. approve with bounded authority;
12. resume and execute exactly once;
13. verify the action occurred;
14. restart the service and confirm durable approvals, authority, idempotency and evidence;
15. retry the completed operation after restart and verify the adapter is not called again;
16. produce the evidence packet.

Until this passes outside the founder environment, status remains **design-partner candidate**, not externally production-proven.

## Known gaps this runbook does not hide

- Persistent request-level idempotency is implemented on the Issue #51 branch but must pass CI and the real restart/external E2E tests before it is treated as proven.
- File-backed JSON state is adequate for a tightly controlled single-process pilot only after restart testing; it is not a multi-instance concurrency design.
- Credential storage/rotation is an operator deployment responsibility today, not a complete Ledgato secret-management product.
- The public Vercel experience is not the canonical installation mechanism for this pilot.
- Additional providers/actions need their own non-bypassable adapter and verification path.

These are readiness gates or constraints, not reasons to broaden the product before the first external GitHub proof.