# Boundary Proof Portfolio

> Status: canonical proof-expansion plan
>
> Machine-readable maturity source: `.agent-os/boundary-proof-registry.yaml`

## Rule

Ledgato expands one proven enforcement boundary at a time.

An implemented adapter is not automatically a proven boundary. A policy decision
is not automatically enforcement. A blocked request is not enough to claim a
non-bypassable path.

## Standard proof grammar

Every boundary case study must document:

1. protected resource;
2. consequential action;
3. requesting principal;
4. custody of the capability that can create the effect;
5. alternate-route inventory;
6. declared authority;
7. ALLOW / DENY / APPROVE behavior;
8. exact request binding;
9. human approval binding where applicable;
10. replay, mutation, and stale-authority tests;
11. concurrency behavior;
12. restart and crash behavior;
13. downstream resource truth;
14. revocation behavior;
15. recovery / break-glass behavior;
16. independent verification;
17. known limitations;
18. the exact claim earned.

## Evidence grades

| Grade | Meaning |
| --- | --- |
| `EXTERNAL_CUSTOMER_VERIFIED` | independently verified in a real external customer workflow |
| `LIVE_PROVIDER_VERIFIED` | real provider/resource, bypass-tested and independently verified in a controlled lab |
| `LOCAL_RESOURCE_VERIFIED` | separate protected process/resource with cryptographic enforcement, but synthetic/local |
| `IMPLEMENTED_BOUNDED` | narrow real integration exists; complete boundary proof remains |
| `IMPLEMENTED_UNVERIFIED` | adapter exists/tests pass; no complete live boundary proof |
| `CORE_SEMANTICS_TESTED` | underlying authority semantics tested, but no complete case study |
| `DIRECTION_ONLY` | product/architecture target only |

No lower state should be rendered, described, or sold as a higher state.

## Current portfolio

### GitHub protected merge

Grade: **LIVE_PROVIDER_VERIFIED**

This is the reference proof. It has real-provider execution/readback, bypass
testing, approval-abuse testing, and independent verification under the
documented lab architecture.

It is not an external-customer proof and it does not generalize automatically
to other GitHub actions or provider classes.

### Signed-permit protected resource

Grade: **LOCAL_RESOURCE_VERIFIED**

A separate protected resource requires an exact Ledgato-signed single-use
permit. This is the strongest architecture proof for resource-enforced
authorization, but the resource is local/synthetic.

### Privileged AgentOS host action

Grade: **IMPLEMENTED_BOUNDED**

This is the immediate next case study because it exercises OS/root privilege.

Target proof:

    bounded host action
    -> Ledgato decision / approval
    -> exact one-use permit
    -> root-owned broker/helper
    -> only the intended operation occurs
    -> replay and mutation fail
    -> equivalent direct privileged route is unavailable to the governed worker
    -> host readback establishes the result

### Protected credential-backed operation

Grade: **DIRECTION_ONLY**

Prove that an agent can receive an authorized outcome that requires a protected
credential without receiving the reusable credential itself.

### Outbound communication / publishing

Grade: **DIRECTION_ONLY**

Use this as the clearest WYSIWYS proof: exact destination/content is reviewed,
post-approval mutation fails, send/publish occurs at most once, and provider
readback confirms the external effect.

### x402 spending

Grade: **IMPLEMENTED_UNVERIFIED**

The adapter exists and is CI-tested. A safe test-network proof still needs
destination/amount binding, replay/mutation tests, no alternate payment path,
settlement/resource evidence, and independent verification.

### Protected data mutation/deletion

Grade: **DIRECTION_ONLY**

Use a disposable database/storage resource. Bind the exact affected records,
show create/modify/replace/delete impact, verify post-action state, and test
recovery/reversibility.

### Agent-to-agent delegation

Grade: **CORE_SEMANTICS_TESTED**

The authority machinery has test evidence, but there is no coherent live
supervisor -> worker -> protected-effect case study yet.

### Cloud infrastructure

Grade: **DIRECTION_ONLY**

Use one disposable/reversible staging resource and a narrowly scoped provider
identity. Do not start with broad account administration.

## Mandatory attack matrix

Every new case study must address:

- direct bypass;
- alternate tool/adapter/path;
- capability leakage;
- identity spoofing;
- privilege escalation;
- exact-parameter mutation;
- approval replay;
- concurrent duplicate execution;
- stale approval/grant/policy;
- restart/crash ambiguity;
- revocation;
- downstream readback disagreement;
- evidence tampering;
- fail-closed behavior when Ledgato is unavailable.

If a vector is not applicable, record `NOT_APPLICABLE` with a reason.

## Impact verification

Each proof should progressively use the canonical Impact Envelope.

Before the decision:

    requested action
    -> expected material delta
    -> related resources/workstreams
    -> reversibility
    -> novelty
    -> KNOWN / INFERRED / UNKNOWN

After execution:

    provider/resource truth
    -> observed impact
    -> MATCHED / PARTIAL / DRIFTED / UNKNOWN

The acting agent's completion statement is never the final witness.

## Claim governance

The machine registry is the evidence ceiling for website copy, product UI,
sales/demo language, and agent-generated summaries.

## Proof sequence

1. GitHub merge remains the reference proof and first external pilot wedge.
2. Privileged host action.
3. Protected credential-backed operation.
4. Outbound publish/send.
5. x402 spending.
6. Protected data mutation/deletion.
7. Agent delegation.
8. Cloud infrastructure.

The goal is not adapter count. The goal is to show the same enforcement
invariant surviving materially different forms of authority.
