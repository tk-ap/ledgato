# Product Direction — khrystal / Execution Intelligence

> Status: product-direction decision recorded; public rename not yet implemented.

## Working brand direction

**khrystal — Execution Intelligence**

Current positioning direction:

> Evidence, decisions, cost, and accountability before work ships.

`khrystal` is the working successor brand candidate for Ledgato. The current repository, deployment, and public product name remain **Ledgato** until naming clearance and an explicit rename implementation decision are complete.

## Core product wedge: pre-ship Review

The current product is not a post-execution surveillance platform.

Its primary job is to help a human answer:

> **Should this agent-produced work ship?**

The product should make proposed work legible before release by surfacing the evidence needed to review and approve it with confidence, including:

- what the agent proposes to change;
- why the work was produced;
- what evidence supports it;
- what risk or scope implications exist;
- what it is expected to cost;
- what authorization or approval applies; and
- what result is expected if the work is allowed to ship.

Anything that directly improves this decision belongs in the core product now.

## Lifecycle

The long-term product lifecycle is:

**Review → Approve → Execute → Verify → Learn**

### 1. Review — current wedge

Inspect proposed agent work before it reaches production.

Key question: **Should this ship?**

### 2. Approve

Capture the human or policy decision that authorizes the proposed work to proceed.

Key question: **What was actually authorized?**

### 3. Execute

Execution happens through the governed runtime/control plane rather than becoming a second execution engine inside khrystal.

Key question: **What was permitted to run?**

### 4. Verify — future expansion

After execution, verify that what actually happened corresponds to what was proposed and approved.

Key question: **Did what shipped match what we approved?**

This is deliberately framed as **verification, not surveillance**. khrystal should not become a generic always-on agent-monitoring product simply because agents are running.

### 5. Learn — long-term intelligence

Use accumulated evidence to understand the gap between proposed, approved, and delivered work across agents, workflows, harnesses, models, hosts, costs, and outcomes.

Key question: **What should we do differently next time?**

This is where long-term Execution Intelligence compounds: the product can learn which workflows, agents, harnesses, approvals, and execution patterns produce reliable outcomes and which create avoidable risk, cost, or failure.

## Product boundary

### In scope now

- pre-ship review;
- evidence for release decisions;
- proposed-change inspection;
- scope/risk review;
- release gating;
- approval records;
- cost and impact visibility when available;
- signed/tamper-evident review evidence where useful.

### Future, but aligned

- post-ship verification against the approved proposal;
- expected-result vs. actual-result comparison;
- longitudinal execution learning;
- comparative intelligence across agents, workflows, harnesses, hosts, and models;
- feedback from verified outcomes into future governance and review.

### Explicitly not the product thesis

- generic runtime observability;
- continuous surveillance of every agent action for its own sake;
- rebuilding OpenTelemetry or commodity tracing;
- becoming a second agent execution runtime;
- positioning post-execution monitoring as the primary wedge.

## Relationship to agent-os

The intended separation is:

- **agent-os / Workforce**: governed execution infrastructure and control plane;
- **khrystal**: intelligence and evidence around consequential execution decisions.

Conceptually:

**Propose → khrystal Review → Approve → agent-os Execute → khrystal Verify → Learn**

The two systems should eventually close the loop without collapsing into one product.

## PEART record model

PEART remains an **internal execution-evidence model**, not a second customer-facing product or public standard at this stage.

Working expansion:

- **P — Provenance**: where the work came from — task, workflow, agent, harness, host, model, initiator.
- **E — Evidence**: tests, artifacts, tool outputs, screenshots, validations, receipts, or other support for the proposed result.
- **A — Authority**: permissions, policy, budget, requestor, and human or automated approval context.
- **R — Result**: the expected result before execution and, later, the actual result after verification.
- **T — Trace**: the ordered path of actions, handoffs, retries, and decisions that connects the work to the result.

A pre-ship review can create the initial PEART record. Later verification can complete the same evidence chain with the actual outcome.

This allows accountability to be **derived from evidence** rather than treated as a vague field.

## Naming guardrail

Do not rename the repository, deployment, package, URLs, or public UI from Ledgato to khrystal solely because this document exists.

The rename should happen only after:

1. naming/trademark clearance is considered sufficient;
2. domain and namespace strategy is chosen;
3. migration impact is reviewed; and
4. an explicit implementation PR is approved.

Until then, **Ledgato remains the operational name; khrystal is the recorded product-direction candidate.**
