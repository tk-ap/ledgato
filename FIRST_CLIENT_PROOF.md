# First Client Proof — Real Enforcement

## The claim we must earn

> **LEDGATo can actually stop an AI agent from crossing a boundary it was not authorized to cross.**

This is the next product milestone.

The current engine can evaluate policy, return an allow/deny decision, record evidence, detect declared-scope drift, and produce attestations. That is necessary but not sufficient.

A real product proof requires LEDGATo to sit in an execution path that the protected agent cannot bypass for the selected action.

## What counts as proof

The first client proof must demonstrate one real consequential action end to end:

1. A real agent or governed workflow attempts a real action against a real integration.
2. The action is routed through an enforcement point that consults LEDGATo before execution.
3. LEDGATo receives enough context to evaluate the request: agent, task, requested action, relevant authority/policy, and available evidence.
4. LEDGATo returns **ALLOW**, **DENY**, or **APPROVE**.
5. The execution path obeys the decision.
   - **ALLOW**: the action proceeds.
   - **DENY**: the action does not reach the protected system.
   - **APPROVE**: the action pauses until approval is resolved.
6. LEDGATo records the decision and supporting evidence.
7. Verification confirms what actually happened after the decision.

The critical acceptance test is:

> **A denied action is attempted, and we can prove the protected system never executed it.**

## Recommended first integration

Start with one narrow integration rather than multiple platforms.

Preferred first proof:

**agent-os / governed workflow → LEDGATo assurance check → GitHub protected action**

The exact GitHub action may be a protected merge, deployment/release step, or another consequential operation that can be blocked reliably by the integration.

Why this is a good first slice:

- it fits the existing ecosystem;
- GitHub already has native gating/check concepts;
- success and failure are easy to observe;
- it produces a concrete story for an early client;
- it exercises the separation between execution (agent-os/runtime) and assurance (LEDGATo).

A controlled HTTP/MCP tool gateway is an acceptable alternative if it produces a clearer non-bypassable enforcement proof.

## What does not count as proof

The following are useful development artifacts, but do **not** satisfy this milestone on their own:

- a dashboard showing a simulated denied action;
- an API returning `DENY` while the agent can still call the external system directly;
- a synthetic probe battery only;
- a signed attestation of a hypothetical action;
- a UI button that visually says blocked without a real protected action behind it;
- a policy document or `fence.yaml` rule that is not connected to enforcement;
- post-hoc detection after the unauthorized action already happened.

## Minimum integration contract

The first enforcement adapter only needs a small contract.

### Request

- agent identity
- task/workflow identifier
- requested tool/action
- relevant resource/destination
- impact or risk context
- authority/policy reference
- evidence available at decision time

### Decision

- `ALLOW`
- `DENY`
- `APPROVE`
- human-readable reason
- policy/evidence reference
- decision identifier for later verification

### Verification

After an allowed or approved action, record whether the observed result stayed inside what was authorized.

After a denied action, record evidence that the protected action was not executed.

## First-client readiness gate

LEDGATo is ready for a first paid pilot when all of the following are true:

- [ ] one real integration is connected;
- [ ] the protected action cannot bypass the LEDGATo decision path under the tested configuration;
- [ ] one allowed action succeeds;
- [ ] one unauthorized action is denied and does not execute;
- [ ] one approval-required action can pause and resume, or is explicitly deferred from the first pilot scope;
- [ ] the decision record includes task, agent, policy/authority context, reason, and evidence;
- [ ] verification can show what happened after the decision;
- [ ] the demo uses real integration behavior, not simulated UI data;
- [ ] setup is documented well enough for an external design partner;
- [ ] public claims accurately distinguish proven enforcement from simulated/future capabilities.

## First client promise

The first sale should be narrow and concrete:

> **LEDGATo helps stop your AI agent from performing a protected action outside its approved scope, and gives you evidence of the decision and outcome.**

Do not sell the full long-term platform before this proof exists.

## Build order

1. Pick the one protected action.
2. Build the non-bypassable integration point.
3. Connect it to the existing LEDGATo decision engine.
4. Demonstrate ALLOW and DENY against the real system.
5. Add approval pause/resume if needed for the pilot.
6. Attach PEART evidence to the real decision/outcome.
7. Test with an external design partner.
8. Charge for the pilot before expanding integrations.

Until this milestone is complete, new dashboards, broader simulations, extra ledger complexity, additional platform integrations, and public rename work are secondary.