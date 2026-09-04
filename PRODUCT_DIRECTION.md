# Product Direction — khrystal / Agent Assurance

> Status: product-direction scope corrected; public rename not yet implemented.

## Working brand and category direction

**khrystal — Agent Assurance**

Working product principle:

> **Independent engine. Embedded experience.**

Working promise:

> Keep consequential agent actions inside understandable, enforceable, provable authority boundaries.

`khrystal` remains the working successor-brand candidate for Ledgato. The current repository, deployment, package, URLs, and public product name remain **Ledgato** until naming clearance and an explicit rename implementation decision are complete.

**Agent Assurance** is the current working category, not a claim that the category name is final. **Agent Release Assurance** remains a strong first product surface and wedge, but it is not the full definition of khrystal.

### Category guardrail: assurance, not generic IAM

Ledgato/khrystal should not position itself as the identity provider, the universal agent IAM system, or a replacement for an execution control plane.

Identity and access infrastructure can establish who or what an agent is, issue credentials, assign roles, and grant baseline permissions. Execution infrastructure can perform the work. khrystal's differentiated role begins at the consequential crossing:

> **Given this agent, this task, this delegated authority, this requested action, and this evidence: should this boundary be crossed right now — and can we prove afterward that reality stayed inside what was authorized?**

The phrase **authorization control plane** may describe an integration surface or mechanism in specific implementations, but it should not become the primary product category. That framing creates unnecessary overlap with IAM, runtime security, and agent execution systems.

The preferred conceptual stack is:

**Identity / IAM → governed runtime or agent-os → consequential boundary → khrystal assurance decision → execution continues or stops → verified evidence**

## Why the scope is broader than release assurance

A release is only one consequential boundary an agent can cross.

Agent failures can happen before a pull request or deployment exists: an agent may attempt to reach a tool outside its task, access a credential, communicate externally, escalate impact, cross a data boundary, invoke infrastructure, spend money, or otherwise use authority it was not intended to have.

A product that only asks **“Should this PR ship?”** can be useful, but it may arrive after the more important boundary was already crossed.

The broader khrystal question is:

> **Is this agent authorized to cross this boundary, under this task, with this evidence, right now?**

The product should help answer that question with policy, evidence, adversarial testing, approval when needed, and a durable record of the decision.

## Core object: the authority boundary

khrystal should model consequential crossings such as:

- agent → tool;
- agent → internet or external endpoint;
- agent → credential or secret;
- agent → private repository;
- agent → production data;
- agent → cloud or privileged infrastructure;
- agent → another agent or delegated worker;
- agent → external API;
- agent → send/publish action;
- agent → spend or budget action;
- agent → deployment or release.

Not every action needs a human review. Policies should be able to resolve a boundary as:

- **ALLOW** — the action is inside declared authority;
- **DENY** — the action is outside authority or violates policy;
- **APPROVE** — the action is consequential enough to require a human or higher-order policy decision.

The aim is not to add approval ceremony everywhere. The aim is to make consequential authority explicit and enforceable.

## Authority provenance

Authority should be treated as something that has a source, purpose, scope, lifetime, and revocation path — not merely as a static permission bit.

The authority graph should evolve from only showing reachable capability toward explaining **why that capability exists**.

A useful conceptual chain is:

**Human / organization → delegation → agent identity → credential / role / token → tool → action → resource/data/destination → task/workflow → khrystal boundary decision → PEART evidence**

For consequential authority, the assurance layer should eventually be able to answer:

- who or what granted the authority;
- why it was granted;
- which task, workflow, release, or period it applies to;
- which identity, credential, role, or token carries it;
- what the effective reachable authority is, not only the declared permission;
- whether the authority is direct, borrowed, or delegated;
- when it expires;
- whether it has drifted from the original purpose or scope;
- whether and how it can be revoked;
- what decision was made when the authority was exercised;
- what actually happened after execution.

This should complement upstream IAM rather than recreate it. khrystal consumes identity and grant facts, evaluates their use at consequential boundaries, and produces assurance evidence around exercised authority.

## Product loop

The long-term assurance loop is:

**Declare → Test → Decide → Enforce → Attest → Verify → Learn**

The current product experience may communicate this more simply as **Discover → Declare → Verify → Enforce → Prove**. That public loop is compatible with the deeper assurance lifecycle and should be preserved where it is clearer for users.

### 1. Declare

Represent the authority an agent is intended to have for a task, workflow, release, environment, or period of execution.

Useful declaration dimensions include:

- tools and endpoints;
- data domains;
- credentials and privilege classes;
- allowed actions;
- maximum impact;
- budget/cost boundaries;
- environment;
- requestor and task context;
- authority source / delegator;
- authority lifetime or expiry;
- conditions that require human approval.

The current `fence.yaml` direction is one implementation of this idea, not the only possible policy interface.

### 2. Test

Probe declared boundaries before consequential execution where possible.

Adversarial checks can test for classes such as:

- scope escape;
- impact escalation;
- exfiltration;
- injection;
- unintended external access;
- permission drift;
- mismatch between declared and reachable authority.

The goal is to discover weak or contradictory boundaries before an agent relies on them.

### 3. Decide

At a consequential boundary, evaluate policy, task context, evidence, requested authority, and authority provenance.

Key question:

> **ALLOW, DENY, or APPROVE?**

This decision may be surfaced inside another product or execution environment rather than requiring a user to open khrystal directly.

### 4. Enforce

Where khrystal is integrated into an enforceable path, the decision should affect whether the boundary can be crossed.

Examples include:

- a tool/proxy check before invocation;
- a GitHub required check before merge;
- a CI/deployment gate;
- an agent-os execution pause pending approval;
- an external-system policy check before a consequential action.

khrystal is **not** a second agent runtime. It supplies assurance decisions and evidence to the runtime or system that performs the work.

### 5. Attest

Create durable evidence of what was declared, tested, requested, decided, authorized, and delegated.

Attestations should make it possible to answer:

- what authority was requested;
- where that authority came from;
- what task or purpose justified it;
- what policy applied;
- what evidence was available;
- who or what approved the crossing;
- whether scope or permission drift was detected;
- what release/action the decision applied to;
- whether the grant was time-bounded or revocable.

Signed or tamper-evident evidence belongs here where it materially improves trust and auditability.

### 6. Verify

After a consequential action, compare what actually happened with what was declared and authorized.

Key question:

> **Did reality stay inside the authority we approved?**

This is verification, not generic surveillance.

### 7. Learn

Use accumulated assurance records to improve future policies, approvals, boundaries, agent selection, and execution design.

Key question:

> **Where are our authority boundaries too broad, too weak, too costly, or unnecessarily restrictive?**

## First concrete wedge: Agent Release Assurance

GitHub/CI release gating remains a strong first wedge because it is legible, consequential, and already has a native approval/check surface.

A release-assurance integration can answer:

> **Should this agent-produced change be allowed to merge or deploy?**

It can surface:

- what changed and why;
- whether the work stayed inside the task and declared scope;
- tests and supporting evidence;
- adversarial probe results;
- permission/scope drift;
- cost or impact where available;
- the final **ALLOW / DENY / APPROVE** decision;
- a signed/tamper-evident attestation where useful.

This wedge should prove the assurance model without redefining the entire company as a PR tool.

## Next proof milestone: one real enforced boundary

The next important proof is not another dashboard or broader simulation. It is one end-to-end integration where a real consequential request passes through khrystal and a **DENY** or **APPROVE** decision actually changes what the agent/runtime is able to do.

A credible slice should demonstrate:

1. a real agent or governed workflow requests a consequential action;
2. the request carries task context, identity, delegated authority, and evidence;
3. khrystal evaluates the boundary;
4. **ALLOW / DENY / APPROVE** is returned;
5. the integrated runtime/tool path obeys the decision;
6. the decision and provenance are attested;
7. post-action verification records what actually happened.

This is the product proof point that turns assurance language into enforceable behavior.

## JIT authority and revocation

Future authority models should support **just-in-time, purpose-bound authority** rather than assuming permanent grants.

Aligned future capabilities include:

- temporary grants tied to a task/workflow;
- explicit expiry / lease duration;
- approval-triggered elevation for consequential actions;
- revocation when the task finishes, policy changes, drift appears, or a human withdraws authority;
- evidence that a grant was active at the moment a decision was made;
- verification that revoked authority is no longer reachable.

khrystal should not become the system that must issue every credential. It should be able to consume and evaluate upstream grant/revocation state and, where integrations allow, require or trigger appropriate authority changes before execution continues.

## Embedded experience

khrystal should not become an extra mandatory destination in the user’s workflow.

The engine can remain technically and product-wise independent while its decisions appear natively where work already happens:

- **ailhat** — surface “this work needs approval” within portfolio/work orchestration;
- **GitHub** — required checks and PR release assurance;
- **CI / deployment platforms** — allow/block/approval gates;
- **agent-os / Workforce** — execution-boundary policy checks;
- **external systems** — policy checks before consequential actions;
- **khrystal console** — deeper policy configuration, assurance history, audit, evidence, and integration management.

The standalone console is a control and evidence surface, not a required detour for every action.

## Ecosystem boundary

The intended separation is:

- **ALVIRA — Context Intelligence**: understands the person, goals, preferences, history, constraints, identity, and working context;
- **ailhat — Portfolio Intelligence**: understands what the person is building, detects Opportunity / Risk / Drift / Work, prioritizes attention, and orchestrates portfolio work;
- **Agent Direct inside ailhat**: routes work toward the appropriate governed execution path;
- **agent-os / Workforce**: governed execution infrastructure and control plane that performs authorized work;
- **identity / IAM providers**: establish agent or workload identity, issue credentials, roles, and baseline access;
- **khrystal — Agent Assurance**: evaluates, tests, records, and where integrated enforces consequential authority boundaries around agent actions.

The systems should close a loop without collapsing into the same product.

A simplified flow is:

**Context → Portfolio decision → Route → Identity/grant → Governed execution → consequential boundary → khrystal ALLOW / DENY / APPROVE → execution continues or stops → verification/evidence feeds learning**

khrystal is therefore **independent assurance, not an independent workflow, identity provider, or second runtime**.

## Product boundary

### In scope

- declared agent authority / scope as policy;
- authority provenance and delegated-purpose context;
- action-boundary checks;
- **ALLOW / DENY / APPROVE** decisions;
- adversarial boundary probes;
- scope, permission, and authority-drift detection;
- least-authority / blast-radius reduction mechanisms where enforceable;
- evidence for consequential decisions;
- human approval gates where policy requires them;
- release gating and Agent Release Assurance;
- signed/tamper-evident attestations where useful;
- verification that actual outcomes remained inside approved authority;
- integrations that embed assurance into existing work surfaces.

### Future, but aligned

- just-in-time / expiring authority checks;
- revocation-aware assurance;
- richer runtime-boundary integrations without becoming the runtime itself;
- policy learning from prior approvals and violations;
- comparative assurance intelligence across agents, workflows, harnesses, hosts, models, and environments;
- expected-result vs. actual-result verification;
- reusable organization-level authority templates;
- feedback from verified outcomes into future governance.

### Explicitly not the product thesis

- replacing IAM or identity providers;
- becoming a universal credential issuer;
- generic runtime observability;
- continuous surveillance of every agent action for its own sake;
- a generic SIEM or replacement security stack;
- portfolio intelligence or work prioritization;
- rebuilding OpenTelemetry or commodity tracing;
- becoming a second agent execution runtime;
- requiring a manual approval step for every low-risk action;
- promising to prevent every exploit, escape, zero-day, or malicious behavior.

A defensible khrystal promise is to **reduce reachable authority, gate consequential crossings, limit blast radius where integration allows, and create evidence when policy is tested or violated** — not to make autonomous systems infallible.

## PEART record model

PEART remains an **internal assurance/evidence model**, not a second customer-facing product or public standard at this stage.

Working expansion:

- **P — Provenance**: where the action/work and authority came from — task, workflow, agent, harness, host, model, initiator, delegator, credential/role source, and purpose.
- **E — Evidence**: tests, artifacts, tool outputs, screenshots, validations, probe results, receipts, or other support for the requested action/result.
- **A — Authority**: permissions, policy, budget, requestor, environment, allowed boundary, grant/delegation chain, effective authority, expiry, revocation state, and human or automated approval context.
- **R — Result**: the expected result before execution and, later, the actual result after verification.
- **T — Trace**: the ordered path of actions, handoffs, retries, boundary requests, grants/revocations, and decisions that connects provenance to result.

A boundary decision can create or append to a PEART record. Later verification can complete the same evidence chain with the actual outcome.

For a consequential action, a mature PEART record should make it possible to reconstruct:

**who delegated what authority → for what purpose/task → through which identity/credential → what boundary was requested → what evidence and policy informed the decision → who/what approved it → what the agent actually did → whether the outcome remained inside the approved boundary.**

This allows accountability to be **derived from evidence** rather than treated as a vague field.

## Naming guardrail

Do not rename the repository, deployment, package, URLs, or public UI from Ledgato to khrystal solely because this document exists.

The rename should happen only after:

1. naming/trademark clearance is considered sufficient;
2. domain and namespace strategy is chosen;
3. migration impact is reviewed; and
4. an explicit implementation PR is approved.

Until then, **Ledgato remains the operational name; khrystal is the recorded successor-brand candidate.**

Likewise, **Agent Assurance** and **Agent Release Assurance** should be treated as working category/product language until the positioning is tested against real integrations and users.
