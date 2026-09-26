# Proof: one non-bypassable Ledgato enforcement boundary

**Status:** proven in a local, two-process lab. **Not activated in production.**

This document covers one narrow boundary, end to end:

```text
request → Ledgato decision → protected executor → actual outcome → evidence
```

The division of responsibility stays fixed:

- **IAM identifies.** The Ledgato principal presented by the caller decides *who* is asking. The contract's `agent.id` must match it.
- **AgentOS executes.** `ProtectedExecutor` is the only path AgentOS uses to reach the protected resource.
- **Ledgato is the mandatory checkpoint.** Only Ledgato can mint the permit the resource demands, and it mints one only on ALLOW.

## Why this is non-bypassable, not advisory

The existing gateway (`gateway.py`) enforces only when every caller routes through it. Here, the protected resource enforces the decision itself:

1. The resource holds the capability and pins Ledgato's Ed25519 public key.
2. It performs nothing unless it is shown a permit that meets all of these conditions:
   - Ledgato signed it.
   - It is bound to the SHA-256 of *this exact* contract.
   - It names *this* resource.
   - It has not expired.
   - It has never been used.
3. Ledgato issues a permit **only on ALLOW**. DENY and APPROVAL_REQUIRED carry nothing a caller could present.
4. AgentOS never holds the signing key, so it cannot forge, widen, re-target, or reuse a permit.

Skipping Ledgato therefore leaves AgentOS with nothing the resource will accept.

```text
 AgentOS process                 Ledgato process                  Resource process
 ───────────────                 ───────────────                  ────────────────
 ProtectedExecutor.run(contract)
   │  POST /v1/enforcement/decide ─▶ authenticate principal (IAM)
   │                                 contract.agent.id == principal?
   │                                 evaluate_action(policy, contract)
   │                                 append signed ledger entry
   │                                 persist decision record
   │  ◀── decision (+ permit on ALLOW only)
   │
   ├─ DENY / APPROVAL_REQUIRED ─▶ stop; resource never called
   ├─ no/invalid decision ──────▶ FAILED_CLOSED; resource never called
   └─ ALLOW ─ POST /perform {contract, permit} ─────────────────▶ verify permit
                                                                  burn permit (durable)
                                                                  perform effect once
   ◀──────────────────────────────────────────────────────────── receipt
   │  POST /v1/enforcement/decisions/{id}/outcome ─▶ append OUTCOME entry
```

## The action contract

The schema is in `contracts/action-contract.schema.json` and is enforced by `ActionContract.from_dict`. Unknown fields are rejected.

```json
{
  "version": "ledgato.action-contract/v1",
  "work_id": "work-allow",
  "agent": {"id": "agent-os-deployer", "identity": "iam:svc/agent-os-deployer"},
  "requested_action": {"name": "release.deploy", "impact": "write", "params": {"version": "2026.09.25"}},
  "resource": "service::billing-api",
  "policy": {"id": "agent-os-deployer", "digest": "<optional sha256 of applied policy>"},
  "evidence": [{"kind": "work-item", "ref": "agent-os:work-allow"}]
}
```

| Field | Rule |
|---|---|
| `work_id` | Required. Recorded in the decision, the permit, the resource effect, and the ledger. |
| `agent.id` | Must equal the authenticated Ledgato principal. An approver, admin, or verifier credential gets a 403. |
| `agent.identity` | The IAM subject. It is recorded and grants nothing. |
| `requested_action` | `name` + `impact` (`readonly`, `write`, `exec`, `destructive`) + `params`. |
| `resource` | The permit is valid only at the resource with this id. |
| `policy.id` | Must name the policy Ledgato applies to that agent, otherwise the decision is DENY. The caller cannot pick a laxer policy. |
| `policy.digest` | Optional. A mismatch means DENY (stale policy). |
| `evidence` | Recorded verbatim in the ledger. It informs review and never grants authority. |

On ALLOW the response carries a permit (`contracts/enforcement-permit.schema.json`), signed over every field except `signature`.

## Components

| File | Side | Role |
|---|---|---|
| `ledgato/enforcement.py` | Ledgato | `ActionContract`, `EnforcementPoint` (decide / record_outcome / evidence), permit signing and verification, `DecisionStore` |
| `ledgato/protected_resource.py` | Protected system | `ProtectedResource`, its HTTP app, `RemoteProtectedResource` client, and a CLI to run it as its own process |
| `ledgato/integrations/protected_executor.py` | AgentOS | `ProtectedExecutor`: Ledgato first, execute only on ALLOW, fail closed otherwise |
| `ledgato/api.py` | Ledgato | `POST /v1/enforcement/decide`, `POST /v1/enforcement/decisions/{id}/outcome`, `GET /v1/enforcement/decisions/{id}/evidence`, `GET /v1/enforcement/public-key` |
| `ledgato/sdk.py` | AgentOS | `decide`, `record_outcome`, `evidence`, `public_key` |
| `examples/agent-os-protected-executor-fence.yaml` | Policy | `release.deploy` → ALLOW, `release.rollback` → APPROVAL_REQUIRED, `release.delete` → DENY |
| `examples/prove_enforcement_boundary.py` | Proof | Runs the whole flow across real processes |

### Executor outcomes

| Status | When | Resource called? |
|---|---|---|
| `EXECUTED` | ALLOW, and the resource accepted the permit | Yes, and it acts exactly once |
| `DENIED` | DENY | No |
| `APPROVAL_REQUIRED` | APPROVAL_REQUIRED | No |
| `FAILED_CLOSED` | Any of: Ledgato unreachable or timed out; a non-decision response; an unknown outcome; a decision on a different contract digest; ALLOW with no matching permit; a permit on a non-ALLOW decision; the resource refused the permit | Only in the last case, and the refusal means nothing ran |

## Durability across restart

| State | File | Written |
|---|---|---|
| Signed, hash-chained ledger | `ledger.jsonl` | Append per decision and per outcome |
| Decision records (decision → ledger entry hash, permit id, outcome report) | `decisions.json` | Atomic temp-file + `fsync` + rename |
| Burned permits, effects, rejected attempts | `resource.json` | Burn is persisted **before** the effect runs, so at most one effect per permit |
| Ledgato signing key | `keys/ledgato_private.pem` | Once |

`EnforcementPoint.evidence()` rebuilds its answer from these files and does not trust memory. It re-verifies the whole ledger chain and every signature, and checks that the decision entry matches the record, that the recorded contract hashes to the digest, and that the outcome entry references the decision entry's hash.

## Run the proof

```bash
cd engine
python examples/prove_enforcement_boundary.py            # exits 0 only if every check passes
python -m pytest -q tests/test_enforcement_boundary.py   # 25 tests, including the cross-process proof
```

Expected output of the proof script (23 checks):

```text
1. start Ledgato and the protected resource as separate processes
2. AgentOS runs three contracts through the protected executor
  [PASS] allowed contract executed
  [PASS] denied contract stopped
  [PASS] approval-required contract stopped
  [PASS] exactly one side effect, for the allowed contract
3. bypass attempts
  [PASS] bypass rejected: direct call with no permit
  [PASS] bypass rejected: replay of an already-used permit
  [PASS] bypass rejected: valid permit re-targeted to a different contract
  [PASS] bypass rejected: valid permit presented for a denied contract
  [PASS] bypass rejected: permit signed by a non-Ledgato key
  [PASS] bypass rejected: permit with a tampered field
  [PASS] human approver credential cannot obtain a permit
  [PASS] verifier credential cannot obtain a permit
  [PASS] agent cannot request a permit as another agent
  [PASS] still exactly one side effect after every bypass attempt
4. restart both processes; state is reloaded from disk
  [PASS] allowed: evidence verified after restart
  [PASS] denied: evidence verified after restart
  [PASS] approval-required: evidence verified after restart
  [PASS] resource effect is bound to the ledger decision entry
  [PASS] bypass rejected: permit replay after restart
5. Ledgato unavailable: the executor fails closed
  [PASS] no Ledgato decision -> FAILED_CLOSED, nothing executed
  [PASS] side effects unchanged after outage
```

### Acceptance → test map

| Requirement | Test(s) in `tests/test_enforcement_boundary.py` |
|---|---|
| Allowed action executes once | `test_allowed_action_executes_exactly_once` (includes a permit replay) |
| Denied action has no side effect | `test_denied_action_has_no_side_effect_and_resource_is_never_called`, `test_out_of_policy_actions_are_denied` |
| Approval-required action has no side effect | `test_approval_required_action_has_no_side_effect` |
| Direct/bypass invocation is rejected | `test_direct_bypass_invocations_are_rejected` (10 vectors), `test_permit_for_one_resource_is_useless_at_another`, `test_allow_carrying_a_forged_permit_fails_closed_at_the_resource`, plus the cross-process bypass checks |
| Fails closed with no valid decision | `test_no_valid_decision_fails_closed` (7 cases), `test_unknown_agent_is_denied_not_errored`, `test_contract_cannot_choose_a_different_or_stale_policy` |
| Decision/evidence persist across restart | `test_decision_and_evidence_survive_process_restart`, cross-process restart in `test_end_to_end_proof_across_processes_and_restart` |
| Ledger evidence proves the result | `test_ledger_evidence_proves_each_result`, `test_tampered_ledger_is_detected_after_restart`, `test_execution_claimed_on_a_denied_decision_is_recorded_as_inconsistent` |

The ground truth for "did the action happen" is always the resource's own persisted effect log, never the executor's or Ledgato's account of it.

## Remaining production gaps

This proves the mechanism for one boundary in a lab. None of the following is done, and nothing here should be described as production enforcement until the relevant gaps are closed.

1. **AgentOS has not adopted it.** `tk-ap/agent-os` `runtime/executor.py` still calls GitHub through its own `gh` subprocess and credential. That is the bypass named in `wi-2026-09-05-ledgato-boundary-integration`. AgentOS must route consequential actions through `ProtectedExecutor` **and lose its equivalent credential**, or the boundary is still advisory for AgentOS.
2. **No real downstream system behind the resource.** The protected effect is a recorded state change. A production resource must be the *sole* holder of the downstream credential (for example a `GitHubAdapter` token), deployed where AgentOS cannot read its environment, files, or memory.
3. **Approval does not produce a permit.** APPROVAL_REQUIRED stops correctly, but nothing turns a human approval into a permit yet. Approved work stays paused. It should reuse the gateway's approve → one-time resume path, re-evaluate at resume, and issue a fresh permit.
4. **Key management.** The Ledgato signing key is an unencrypted PEM on local disk. The same key signs ledger entries and permits, there is no rotation or revocation, and the resource's pinned key is distributed by hand. Production needs KMS/HSM custody, a separate permit-signing key, and a rotation procedure with overlapping trust.
5. **Permits cannot be revoked once issued.** A kill switch or policy change after ALLOW does not stop a permit presented within its TTL (default 120 s, not configurable through the API). The resource should check a revocation feed, or the TTL should be seconds.
6. **The outcome report comes from the governed side.** The executor reports the outcome. A compromised executor could skip or falsify it. The resource's effect log is authoritative but is not written into the Ledgato ledger. The resource needs to sign its receipts and report them to Ledgato directly, with reconciliation that flags decisions missing an outcome.
7. **Single-node state only.** JSON files with in-process locks are not safe for several Ledgato replicas or several resource workers. The burned-permit set in particular needs a shared transactional store. `Ledger.append` is also not serialized between `EnforcementGateway` and `EnforcementPoint` inside one process.
8. **Crash window.** The resource burns the permit before acting, so a crash between burn and effect loses the action rather than repeating it. There is no reconciliation or re-decision path for that case yet, and the downstream system's own idempotency keys are not used.
9. **Transport and exposure.** Everything runs as plain HTTP on localhost. There is no TLS or mTLS between AgentOS, Ledgato, and the resource. The resource's `/effects` and `/rejections` read endpoints are unauthenticated.
10. **Clock trust.** Permit expiry is checked against the resource's clock. Clock skew handling is not addressed.
11. **Parameters are not constrained.** Policy governs `name`, `impact`, and `resource`, but `params` are free-form. A per-action parameter schema or allowlist is needed before a `write` or `exec` permit can be treated as tightly scoped.
12. **Policy lifecycle.** Policies load from `fence.yaml` at startup. The digest check catches stale contracts, but policy versions and changes are not recorded in the ledger.
13. **PR #1 authority-status store is in memory.** `/v1/authority/resolve` status (from the rebased PR #1) is still lost on restart. This PR does not change that path.
14. **Not activated.** No production configuration, deployment, or runbook enables this path. Production activation is explicitly out of scope and requires owner approval.
