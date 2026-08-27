# Ledgato Product Viability Thesis

## The problem

AI agents are moving from answering questions to taking actions across real systems: repositories, deployment infrastructure, APIs, credentials, customer data, billing, messaging, and internal tools.

The core problem is no longer only what an agent can understand. It is what that agent is actually allowed to do once it can act.

A useful analogy is a new employee. You would not give one person production deployment rights, billing access, customer data, secrets, and destructive permissions on day one and rely on “please behave” as the control model. You assign authority intentionally, constrain it, verify it, and require approval for higher-risk actions.

AI agents need the same kind of deterministic authorization boundary.

## Ledgato in one sentence

> Tell me what my agents can do, test whether that’s actually true, and stop them when they cross the line.

## The control-loop thesis

Ledgato should sit between agent intent and execution.

1. **Agent intent** — an agent proposes an action.
2. **Identity** — who is attempting the action?
3. **Action** — what exactly is being attempted?
4. **Resource** — what system, data, tool, or destination is affected?
5. **Authority** — what authority has actually been granted?
6. **Policy** — is this action allowed under the current boundary?
7. **Decision** — ALLOW, DENY, or REQUIRE APPROVAL.
8. **Evidence** — record who attempted what, which rule applied, the outcome, and when it happened.

The agent may decide what it wants to do. Ledgato should independently decide whether the action may execute.

## Why the problem is real

The market is converging on agent identity, authorization, governance, least-privilege access, runtime controls, and auditability. Large identity and security platforms are actively validating that AI agents require first-class identity and authorization controls.

This is positive validation for the problem, but it creates a strategic warning: Ledgato should not attempt to win by becoming merely “Okta for AI agents” or a generic IAM dashboard. Large incumbent identity vendors are structurally advantaged in that category.

## The stronger wedge

Ledgato’s more differentiated thesis is **capability verification + runtime authorization**.

The product should not stop at declaring what an agent is allowed to do. It should test whether those boundaries actually hold in practice.

Example:

| Declared boundary | Verification attempt | Expected result |
| --- | --- | --- |
| `web-agent` cannot deploy production | attempt `production.deploy` | DENY |
| `web-agent` may create pull requests | attempt `github.pr.create` | ALLOW |
| `web-agent` cannot read production secrets | attempt `secrets.read` | DENY |

A stronger product statement is therefore not:

> We assigned this agent the correct permissions.

It is:

> We continuously tested the agent’s effective capabilities and verified that the intended boundaries still hold.

## Declared permission vs. verified containment

Configuration is only an assertion. Real systems drift.

Credentials change. Tools are added. APIs gain new capabilities. Delegation creates indirect access. New integrations expose resources that were not reachable when a policy was written.

Ledgato should care about effective capability, not only declared configuration.

The desired state is:

- boundary declared;
- boundary tested;
- result verified;
- drift detected when reality changes;
- enforcement applied when the line is crossed;
- evidence retained from the real event.

## Current viability experiment

The first meaningful validation does not require a broad platform.

Prove one vertical slice:

- **1 real agent**
- **3 declared boundaries**
- **3 verification attempts**
- **1 real enforced action**
- **1 evidence trail produced from the actual event**

The key product question is:

> Does Ledgato make an operator materially more comfortable granting an AI agent greater autonomy?

If the answer is yes, the product is creating measurable trust and control value.

If Ledgato does not materially change the operator’s willingness to delegate authority, that is evidence to reconsider the product thesis before investing heavily in broader engineering.

## First laboratory

The best initial environment is a real agent workforce already operating across repositories, deployment infrastructure, and product work.

For one agent, document:

- repositories it may read;
- repositories it may modify;
- whether it may create branches;
- whether it may create pull requests;
- whether it may merge;
- whether it may deploy previews;
- whether it may deploy production;
- whether it may access secrets;
- whether it may spend money or trigger paid services;
- which actions require human approval.

Then deliberately probe several of those boundaries and compare declared policy with actual capability.

## What exists today

Ledgato currently has:

- a working product interface and owner control surface;
- an agent/policy model;
- a Python enforcement engine and local execution path;
- permission, verification, and evidence concepts represented in the product.

## What is being proved now

The next milestone is to connect the production web app to a remotely reachable enforcement path and return a real decision into the interface.

The target loop is:

`Ledgato UI → authenticated API → enforcement engine → real decision → evidence → dashboard`

The product should not represent simulated decisions, scores, probes, or enforcement events as live security outcomes.

## Product principle

Security credibility is part of the product.

Ledgato should be explicit about what is real, what is simulated, what is locally functional, and what remains under validation. Build transparency is not temporary scaffolding; it is useful evidence that the system is being developed around falsifiable claims rather than marketing assertions.

## Positioning direction

A concise framing:

> **Know what your agents can actually do.**
>
> Ledgato discovers effective agent capabilities, verifies that declared boundaries hold, and enforces the line between permitted action and unauthorized behavior.

A plain-language framing:

> **Tell me what my agents can do, test whether that’s actually true, and stop them when they cross the line.**

These should remain stronger than generic “AI security platform” or “agent control plane” language until the differentiated verification loop is proven.
