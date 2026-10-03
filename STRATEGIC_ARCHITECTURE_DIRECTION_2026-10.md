# LEDGATo Strategic Architecture Direction — October 2026

> Status: **canonical planning reference**
>
> Decision horizon: post-AgentOS E2E autonomy/persistence proof
>
> Purpose: preserve what LEDGATo has actually proven, what remains production-incomplete, and the external protocol/security changes that should shape the next implementation phase. This document is a direction record, not evidence that unimplemented capabilities exist.

## Executive direction

LEDGATo should remain narrowly focused on **consequential-action assurance and enforcement**.

The surrounding AI ecosystem is increasingly standardizing pieces that are useful but not sufficient differentiation by themselves:

- agent/workload identity;
- OAuth and connection authorization;
- MCP/A2A protocol transport;
- framework-level human approval;
- runtime guardrail hooks;
- audit/event plumbing.

LEDGATo should consume or interoperate with those layers rather than rebuilding them.

The durable product wedge is:

```text
identity
  ↓
authority lineage
  ↓
exact consequential intent
  ↓
non-bypassable enforcement
  ↓
human decision when required
  ↓
exact execution
  ↓
provider-side truth
  ↓
independent evidence
  ↓
revocation / containment / recovery
```

A concise rule:

> **An approval is not enough. LEDGATo should establish that the governed actor could not bypass the boundary, that the exact authorized action is the action executed, and that the resulting effect is independently verifiable.**

## What is already proven

Do not reduce the evidence state to "prototype only." LEDGATo has real proof, but the proof is bounded.

### Live provider-backed GitHub enforcement proof

The independently verified `github_lab_merge` campaign established, for the documented lab architecture:

- real provider-backed `DENY / APPROVE / ALLOW` behavior;
- fail-closed authentication;
- credential-bound principal separation;
- an agent cannot approve its own request;
- direct bypass attempts did not produce unauthorized protected merges;
- the governed agent could not recover the gateway credential through the tested leakage surfaces;
- authority-escalation attempts failed;
- one human-approved action executed exactly once;
- approval replay was refused;
- GitHub provider-side readback, rather than LEDGATo self-report, established the resulting state;
- independent verification re-derived important race/remediation failures rather than trusting the implementation author.

Canonical evidence: `INDEPENDENT_VERIFICATION_RESULT.md`.

The `VERIFIED` label is scoped to the documented attack suite and lab architecture. It is not a universal bypass-resistance claim.

### Resource-enforced signed-permit proof

The local two-process enforcement proof establishes a stronger execution-boundary mechanism:

- an action is represented by a strict action contract;
- LEDGATo produces a decision;
- only `ALLOW` can produce a signed permit;
- the permit is bound to the exact action-contract digest and protected resource;
- the protected resource refuses execution without a valid LEDGATo permit;
- replay is refused;
- state/evidence survive process restart;
- a tampered evidence chain can be detected;
- provider/resource state, rather than the executor's assertion, is treated as the ground truth in the proof.

Canonical evidence: `engine/ENFORCEMENT_BOUNDARY_PROOF.md`.

### Important evidence lesson

The two proofs should converge.

The live GitHub gateway has stronger real-provider evidence. The signed-permit path has the stronger non-bypassable execution architecture. The next production design should not choose one and discard the other; it should combine their strongest properties.

## Production convergence target

The desired canonical path is:

```text
agent / runtime
    ↓
normalized exact action envelope
    ↓
LEDGATo deterministic decision
    ├── DENY → stop
    ├── APPROVE → durable human challenge
    │               ↓
    │          verified human decision
    │               ↓
    │          re-evaluate current state
    │
    └── ALLOW / approved resume
            ↓
      short-lived signed one-use permit
            ↓
      protected provider adapter/resource
            ↓
       provider performs effect
            ↓
 provider/resource-originated receipt/readback
            ↓
       LEDGATo evidence record
            ↓
 independent verification where required
```

The protected adapter/resource must be the sole holder of the downstream capability for the protected action. A governed agent retaining an equivalent credential means the boundary is advisory, not non-bypassable.

## Production gaps that remain real

These are not all first-mobile-slice blockers, but they must remain visible.

### P0 — approval and signed-permit convergence

The signed-permit enforcement path currently proves `APPROVAL_REQUIRED` stops execution, but the full human approval → re-evaluation → fresh signed permit → exactly-once provider effect path must become canonical.

This is the backend counterpart to the native mobile approval client.

### P0 — exact request / parameter binding

The exact request LEDGATo evaluates must be the exact request the adapter executes and the exact effect later verified.

Target invariant:

> **what was requested == what was authorized == what was executed == what was verified**

Where exact equality is impossible, any transformation must be deterministic, declared, versioned, and evidenced.

Canonical issue: #54.

### P0 — durable shared transactional state

File-backed/single-node state is sufficient for bounded proof, not a production mobile/multi-process authorization service.

Approval consumption, permits, revocations, decision state, evidence references, and policy versions need transactional shared persistence. Postgres remains the default direction unless evidence supports another implementation.

### P0 — provider/resource-originated result evidence

A governed executor must not be able to make a consequential action appear successful or unsuccessful by controlling the only outcome report.

The protected adapter/resource/provider should produce or substantiate the decisive receipt/readback. LEDGATo should reconcile missing or contradictory outcomes.

### P0 — eliminate equivalent bypass credentials

Onboarding/activation must prove that the governed actor cannot perform the protected action through an equivalent direct credential, alternate adapter, path, or unguarded provider route.

Canonical issue: #46.

### P1 — production key and credential lifecycle

Move away from lab-grade static bearer secrets and local unencrypted signing PEMs toward:

- workload/service identity;
- minimum-scoped provider credentials;
- dedicated permit-signing keys;
- managed key custody where appropriate;
- key rotation and overlapping trust;
- credential revocation;
- device/approver credential lifecycle.

### P1 — crash reconciliation and idempotency

A crash between permit consumption and provider effect must have an explicit recovery contract. Prefer provider idempotency keys and target-system reconciliation over blind replay.

`UNKNOWN` / `PARTIAL` must never be silently treated as `FAILED`.

### P1 — transport / service identity

Multi-host production operation needs authenticated transport and service identity appropriate to the deployment topology. Localhost/plain HTTP is not a general production trust boundary.

### P1 — policy lifecycle

Policy versions, changes, activation time, provenance, and the exact policy applied to a decision should become durable evidence.

### P1 — revocation after permit issuance

A permit already issued should have a bounded revocation strategy: very short TTL, resource-side revocation check, or another mechanism appropriate to the protected action.

## Three architecture requirements added for the mobile era

These requirements are now P0 design constraints for the native operator app and the enforcement envelope.

### 1. What-you-see-is-what-you-sign

The operator must not approve a friendly summary that can diverge from the bytes/semantics actually authorized.

Target invariant:

```text
canonical normalized request
      ↓
deterministic human-readable representation
      ↓
operator sees representation
      ↓
device signs request digest + representation/version binding
      ↓
LEDGATo verifies
      ↓
same request reaches protected adapter
```

The approval record should preserve enough information to prove what representation/version the operator was shown.

UI copy may be clearer than the machine envelope, but it must be deterministically derived from it.

### 2. Tool/server/schema provenance

A familiar tool name is not sufficient identity.

The canonical action envelope should be able to bind, where relevant:

- authenticated server/provider identity;
- tool/capability identity;
- tool/schema/protocol version or fingerprint;
- action name;
- normalized arguments;
- protected resource;
- destination/environment;
- acting principal;
- delegation/authority reference.

A tool whose schema or provider identity materially changes should not silently inherit prior standing authority merely because its display name is unchanged.

### 3. Context-source provenance for consequential parameters

LEDGATo should not become a prompt-injection detector or another reasoning agent.

It should, however, be able to preserve useful provenance for consequential values when supplied by the runtime, for example:

- explicit owner instruction;
- standing typed authority;
- delegated agent request;
- retrieved webpage/document;
- email/message content;
- persisted memory/context;
- generated model output.

Policy may then require additional approval when a high-impact parameter originates from an untrusted or materially different source.

Core rule:

> **Context provenance can change the required assurance level. Context does not itself grant authority.**

This preserves the ecosystem boundary: ALVIRA may understand context; AgentOS carries work/provenance; LEDGATo makes deterministic authority/enforcement decisions over explicit inputs.

## Sector / protocol changes that affect the roadmap

These are interoperability inputs, not reasons to broaden the initial product build.

### MCP

Modern MCP increasingly provides protocol-native metadata and authorization/elicitation primitives useful at a gateway boundary.

Direction:

- investigate a first-class MCP adapter;
- consume authenticated MCP/server identity and method/tool metadata;
- normalize the full consequential request, including arguments/resource/destination, before decision;
- do not authorize from tool name or MCP metadata alone;
- preserve LEDGATo's own exact-scope decision, enforcement and downstream verification semantics.

MCP login/connection authorization should not become LEDGATo's product thesis.

### Runtime control standards / hooks

Runtime interception and policy hooks are becoming a recognizable category. Prefer adapter compatibility with emerging standards (including OWASP Agent Control Standard work) rather than creating a proprietary hook merely to own the hook layer.

LEDGATo's differentiation should remain the stronger end-to-end assurance contract.

### A2A and workload identity

Agent-to-agent delegation makes authority lineage more important.

Target invariant:

> **Delegation may narrow authority. It must not silently widen authority.**

Investigate compatibility with A2A identity/security evidence and workload-identity standards such as SPIFFE where useful. LEDGATo should consume verified identity, not reinvent enterprise IAM.

### Signed intent / agentic commerce

Signed agent intent in commerce protocols reinforces a useful architectural distinction:

- a signature can establish provenance/integrity;
- it does not by itself establish authorization under LEDGATo policy.

Protocol-native signed intent should therefore become evidence/input to the canonical LEDGATo decision envelope, not a bypass around the decision layer.

## Native operator app relationship

Canonical mobile details live in `MOBILE_OPERATOR_APP_DIRECTION.md`.

The app is a first-party operator surface, not the execution runtime.

Core rule remains:

> **Push is notification. LEDGATo is authorization. The mobile app is an authenticated decision client. AgentOS remains execution.**

The mobile client should eventually make the enforcement model tangible:

- waiting authority decisions;
- what exact action is being requested;
- what the user is signing;
- whether the action occurred;
- how provider truth proves the result;
- boundary health/drift;
- trusted approver devices;
- revocation/containment.

## Privileged host-action broker direction

For bounded host operations that need elevated OS privilege but do not genuinely require human interactive execution, use the architecture in [`PRIVILEGED_HOST_ACTION_BROKER.md`](./PRIVILEGED_HOST_ACTION_BROKER.md).

Core rule:

> **Do not forward the human's reusable sudo password. Authorize one exact privileged host action and let a root-owned protected broker execute it.**

The broker should reuse the existing LEDGATo action-contract and signed one-use permit model. It is a protected resource, not a second authorization system.

This creates three distinct lanes:

1. normal governed action;
2. privileged governed host action via the broker;
3. genuinely interactive human operator action via Moshi/SSH.

"Needs sudo" should not automatically mean "needs a terminal."

## Operator terminal / SSH / Moshi direction

A remote terminal is realistic and potentially valuable, but it must be architected as **operator access**, not as a second LEDGATo authority or AgentOS execution path.

The ecosystem already has the correct conceptual boundary:

> **Moshi / SSH / Mosh provides owner access to a host. It does not itself grant an AgentOS or LEDGATo approval.**

AgentOS PR #242 deliberately corrected earlier overreach by treating Moshi as operator access rather than authority transport.

### Why it belongs near the app

Some boundaries cannot be resolved by an approval signature alone. Examples include:

- a local/root action intentionally unavailable to agents;
- interactive login or 2FA;
- OS trust dialogs;
- credential/bootstrap operations;
- manual recovery;
- terminal inspection when the operator wants to see the live host/session.

The LEDGATo operator app may therefore expose a distinct **Operator Session** capability.

### Required separation

The app must keep these actions visually and technically distinct:

```text
APPROVE
  = authorize the exact stored agent action
  = signed LEDGATo decision
  = agent/runtime may resume

OPEN TERMINAL
  = start/resume a human operator shell
  = no LEDGATo approval is created
  = no agent authority is expanded
  = manual operator actions are not disguised as agent actions
```

A terminal session can help a human satisfy a required intervention. It must never be treated as evidence that an approval occurred merely because the user opened a shell or ran something.

### Near-term integration: use Moshi rather than rebuilding Moshi

The lowest-risk first integration is an app-to-Moshi handoff for active sessions.

Moshi currently supports public deep links for active tmux/Herdr session cards. The LEDGATo app can therefore expose, where context exists:

- **Open operator session**
- **Open relevant Herdr workspace**
- **Open relevant tmux session**

This preserves the already working Tailscale/SSH/Mosh/Moshi path and avoids making the first LEDGATo mobile slice responsible for a terminal emulator, SSH client, Mosh implementation, host discovery and terminal credential lifecycle.

Do not depend on undocumented `moshi-hook` internals. Treat public/documented integration surfaces as the contract.

### Host/network direction

The existing AgentOS host direction remains preferred:

```text
LEDGATo operator device
        ↓
OS-level private network (for example Tailscale)
        ↓
key-only SSH / Mosh
        ↓
owner account on local host
        ↓
tmux / Herdr / shell
```

No public inbound shell endpoint should be introduced merely for app convenience.

### Later first-party embedded terminal

A terminal embedded directly inside LEDGATo is technically realistic, but it is a later decision, not part of the first approval vertical slice.

Potential shape:

- native terminal renderer;
- native SSH client implementation/library;
- device-keystore-backed SSH key;
- host-key pinning / verification;
- private-network reachability;
- explicit operator-session audit metadata;
- optional durable tmux/Herdr attachment.

Mosh is more complex to embed than SSH because it adds native/UDP/client dependencies and licensing considerations. The upstream Mosh implementation is GPLv3. Do not copy or embed Mosh/Blink/Moshi code into LEDGATo without an explicit license/architecture review.

A first-party SSH-only embedded terminal may be simpler than embedded Mosh. Mosh can remain delegated to Moshi until the product value of an integrated terminal justifies the additional native and licensing surface.

### Better default for "terminal-level approval"

When the user only needs to authorize an agent to execute a terminal command, **do not make the human open a terminal**.

Prefer:

```text
AgentOS exact bounded command/action
        ↓
LEDGATo approval challenge
        ↓
phone shows exact command + cwd + host + privilege + consequence
        ↓
biometric signed approval
        ↓
AgentOS executes through its governed host path
        ↓
verification/evidence
```

Use the remote terminal only when the operation genuinely requires the human to act manually.

### Deferred operator actions

Where AgentOS has a durable owner-only/deferred action, a future ecosystem integration may surface it in the LEDGATo operator app as a **Host Action** card with:

- host;
- repository/workspace;
- reason human intervention is required;
- exact bounded command or requested interaction;
- privilege/sudo indicator;
- verification command/evidence expectation;
- linked task/workflow;
- **Open operator session** action.

AgentOS remains canonical for the deferred work item. LEDGATo remains canonical only for actual authority decisions it owns.

Completion should be based on runtime/provider evidence, not merely a user tapping "done."

## Implementation sequencing

Do not let new protocol research or the terminal idea derail the current gates.

### Before the mobile build

1. Complete the AgentOS E2E autonomy/persistence proof required by the mobile direction.
2. Preserve the current LEDGATo proof artifacts and outstanding production gaps.
3. Define the production approval → permit convergence contract.
4. Define the canonical exact-action envelope with the three new P0 requirements:
   - what-you-see-is-what-you-sign;
   - tool/server/schema provenance;
   - consequential context-source provenance.

### First mobile slice

Build only the signed approval vertical slice in `MOBILE_OPERATOR_APP_DIRECTION.md`.

A Moshi deep-link handoff may be added if it is truly trivial and does not change acceptance criteria, but the approval proof must not depend on Moshi.

### After the first mobile slice

Evaluate:

1. Moshi/Herdr/tmux deep-link operator handoff;
2. Host Action projection from AgentOS;
3. emergency suspend/revoke;
4. first-party SSH terminal only if repeated operator use shows the handoff is insufficient;
5. embedded Mosh only after security/licensing/product-value review.

## Product guardrail

LEDGATo should not become:

- another generic terminal app;
- an SSH management product;
- a second AgentOS runtime;
- an agent chat client whose approvals exist only in UI;
- a replacement for IAM, MCP authorization, A2A identity, Tailscale, or Moshi.

The operator-terminal capability is valuable only insofar as it reduces friction when a real human must intervene in an otherwise governed autonomous system.

The product remains **Agent Assurance / consequential-boundary enforcement**, with the phone serving as the operator's trusted decision and intervention surface.
