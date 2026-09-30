# Product Direction — khrystal / Agent Assurance

> Status: product-direction scope corrected; public rename not yet implemented.

> **Commercial sequencing:** the broad Agent Assurance direction does not authorize a broad initial build. The current entry wedge, customer profile, six-week pilot, evidence gates, and stop conditions are defined in [`GO_TO_MARKET.md`](./GO_TO_MARKET.md). Recruiting must follow [`DESIGN_PARTNER_RECRUITING.md`](./DESIGN_PARTNER_RECRUITING.md).

## Working brand and category direction

**khrystal — Agent Assurance**

Working product principle:

> **Independent engine. Embedded experience.**

Working promise:

> Keep consequential agent actions inside understandable, enforceable, provable authority boundaries.

`khrystal` remains the working successor-brand candidate for Ledgato. The current repository, deployment, package, URLs, and public product name remain **Ledgato** until naming clearance and an explicit rename implementation decision are complete.

**Agent Assurance** is the current working category, not a claim that the category name is final. **Agent Release Assurance** remains a strong first product surface and wedge, but it is not the full definition of khrystal.

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

## Product loop

The long-term assurance loop is:

**Declare → Test → Decide → Enforce → Attest → Verify → Contain/Recover → Learn**

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

At a consequential boundary, evaluate policy, task context, evidence, and requested authority.

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

Create durable evidence of what was declared, tested, requested, decided, and authorized.

Attestations should make it possible to answer:

- what authority was requested;
- what policy applied;
- what evidence was available;
- who or what approved the crossing;
- whether scope drift was detected;
- what release/action the decision applied to.

Signed or tamper-evident evidence belongs here where it materially improves trust and auditability.

### 6. Verify

After a consequential action, compare what actually happened with what was declared and authorized.

Key question:

> **Did reality stay inside the authority we approved?**

This is verification, not generic surveillance.

### 7. Contain / Recover

Assume prevention can fail. When provider-side verification shows that a protected boundary was crossed outside intended authority, the assurance path should be able to reduce further damage and return the system to a known-safe state.

The protected resource or provider is the final witness of impact. A Ledgato decision, gateway log, or agent self-report is not sufficient proof that a protected action did or did not occur.

Where integrations permit, containment/recovery should be able to:

- mark the affected boundary or vector as breached / `BYPASS_FOUND`;
- revoke or invalidate related grants, permits, resume capability, and other reusable authority;
- prevent the same task or compromised execution path from continuing consequential work without a fresh decision;
- isolate or quarantine the affected principal, credential, adapter, or route when policy requires;
- preserve tamper-resistant evidence before remediation changes state;
- identify a known-safe provider/resource state;
- perform or request rollback/recovery under separately authorized authority;
- require independent provider-side verification before normal execution resumes.

This is not a promise that Ledgato can restore every external system itself. Recovery may be performed by AgentOS, the protected provider, an operator, or another authorized recovery mechanism. Ledgato's responsibility is to make the boundary incident explicit, narrow further authority, preserve evidence, and participate in a governed return to safety.

### 8. Learn

Use accumulated assurance records to improve future policies, approvals, boundaries, agent selection, and execution design.

Key question:

> **Where are our authority boundaries too broad, too weak, too costly, or unnecessarily restrictive?**

## Protocol integration direction: enforceable adapters, not protocol ownership

Emerging agent protocols increasingly define how agents call tools, delegate work, buy services, and prove commercial intent. Ledgato should integrate at the **consequential boundary** these protocols expose rather than invent competing transport, payment, identity, or commerce standards.

The architectural direction is:

```text
agent / runtime
      ↓
protocol adapter
      ↓
Ledgato boundary contract
      ↓
policy / authority evaluation
      ↓
ALLOW / DENY / APPROVE
      ↓
protocol-native execution
      ↓
receipt / result / verification evidence
```

A protocol adapter should normalize only the evidence needed for the existing Ledgato boundary model, including where available:

- principal / agent identity and provenance;
- delegated authority and upstream authorization reference;
- requested action and target resource;
- declared scope, budget, time, environment, and other constraints;
- protocol-native mandate, credential, receipt, or proof material;
- conditions requiring approval;
- downstream execution result;
- post-action verification evidence.

The adapter does **not** make Ledgato the owner of the underlying protocol. Existing upstream identity, authorization, delegation, mandate, payment, and commerce semantics should be consumed where applicable rather than silently reissued or replaced.

### Initial protocol targets

The first protocol adapters are:

1. **MCP** — tool/resource invocation boundaries. Ledgato can evaluate consequential MCP operations before invocation and preserve downstream verification evidence. **Directional target; not implemented support.**
2. **A2A** — agent-to-agent delegation boundaries. Ledgato should preserve the rule that delegation may narrow but never widen authority, scope, budget, context, tools, or time. **Directional target; not implemented support.**
3. **x402** — machine-payment boundaries. Ledgato governs the authority to spend without becoming the wallet or payment rail. The `x402.pay` adapter is **implemented and CI-tested** as of PR #60, but no production wallet is configured or funded and no live spending boundary is claimed.

All protocol adapters should use the same underlying action/authority contracts rather than creating protocol-specific authorization engines.

### x402 activation and funding sequence

x402 activation is intentionally **dormant until the POC-first milestone in #63 makes the existing GitHub enforcement boundary understandable and demonstrable**. Protocol breadth must not outrun proof of the core product.

When x402 work resumes, activate it as a bounded second proof of the same enforcement model:

1. create a **dedicated disposable EVM test wallet** used only for the x402 proof;
2. enable **Base Sepolia only** for the first live test; do not authorize a mainnet network;
3. choose **one x402 test resource** and add only its exact hostname to the adapter allowlist;
4. configure a **very small hard spend ceiling** at the x402 SDK/adapter layer;
5. fund the disposable wallet only with the **testnet asset/funds required by the selected Base Sepolia x402 resource**; do not fund a production/mainnet wallet for the first proof;
6. configure the existing adapter through the protected gateway environment (`LEDGATO_X402_EVM_PRIVATE_KEY`, `LEDGATO_X402_ALLOWED_HOSTS`, `LEDGATO_X402_NETWORKS`, and the spend ceiling) without exposing reusable wallet material to the governed agent;
7. record an end-to-end proof:
   `agent requests purchase → Ledgato DENY or APPROVE → authorized resume → x402 payment/settlement → resource returned → settlement evidence recorded`;
8. prove **DENY and pre-approval states produce zero signing/payment attempts**, and approval/resume executes at most once;
9. verify the agent has **no alternate wallet, credential, transport, or direct payment path** that can bypass the Ledgato enforcement boundary;
10. surface the result in the product using the same plain-language proof model as the GitHub boundary: what was attempted, what Ledgato decided, whether money moved, what resource was returned, how settlement was verified, and whether bypass/drift remains possible.

Only after that bounded test is independently understandable and reproducible should a mainnet/funded-wallet decision be considered. That decision requires a separate explicit activation review covering credential custody, funding source, loss ceiling, revocation/rotation, supported vendors/assets/networks, settlement verification, and bypass assumptions.

The x402 adapter is therefore **implemented capability, not activated spending authority**. Funding a wallet or setting production environment variables is an enforcement activation event, not routine configuration.

### Future interoperability targets

Design the adapter boundary so additional commerce/payment protocols can be supported without changing the core decision model. Current watch-list targets include:

- **AP2** — payment authorization / mandate evidence;
- **UCP** — agentic commerce lifecycle actions;
- **Visa Trusted Agent Protocol (TAP)** — merchant-facing agent identity / authorization proof;
- **Mastercard Agent Pay for Machines (AP4M)** — machine-to-machine payment authorization and execution.

These are future interoperability targets only. Presence in this document does not mean the repository implements, deploys, or verifies them.

### Guardrails

- Protocol support must be **adapter-based** and reuse the canonical Ledgato boundary contracts wherever possible.
- A protocol adapter may translate a native request into a Ledgato decision envelope; it must not quietly broaden the user's or agent's authority.
- Wallet keys, payment credentials, provider secrets, and equivalent reusable credentials remain outside Ledgato policy records and should stay with the appropriate protected adapter/host.
- An upstream authorization, mandate, identity assertion, or protocol credential is evidence/input; it does not by itself prove that the requested action satisfies Ledgato policy.
- An `ALLOW` decision is not proof of enforcement. Support claims still require evidence that the adapter was in the real execution path, the protected action respected the decision, bypass was not available within the tested boundary, and the downstream result was verified.
- The existing Agent Release Assurance / first-client enforcement proof remains the current wedge. Protocol-adapter work should not displace that proof target without an explicit reprioritization decision.

This direction makes Ledgato a **protocol-agnostic governance/enforcement layer at protected boundaries**, not a universal authorization service and not a replacement for MCP, A2A, payment rails, commerce protocols, IAM, or Agent OS.

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

## Product delivery model: infrastructure first, console second

Ledgato should **not require its website to be open for enforcement to work**.

The product is attached to an agent's real execution path once, then operates without a human actively using the console. The browser experience is a control room for configuration, exception handling, and evidence; it is not the execution engine and must not be an activation dependency.

The preferred packaging model has three primary surfaces:

1. **Ledgato Engine** — evaluates and records boundary decisions.
2. **Ledgato Adapters / SDK / gateway integrations** — place the engine in the actual execution path for MCP, A2A, GitHub, x402, APIs, runtimes, and other protected systems.
3. **Ledgato Console** — lets a human define authority, inspect protected systems, handle approval-required actions, review drift, and inspect evidence.

A lightweight **agent kit / skill** may teach an agent how to interpret Ledgato responses, approval states, permits, and resume semantics. It is an integration aid, **not the security boundary**. A prompt, skill, or agent instruction that says "ask Ledgato first" is not sufficient enforcement because the agent may ignore it, lose it, or reach the protected system through another path.

The protected capability or credential should sit behind an enforceable adapter/gateway wherever possible:

```text
agent
  ↓
Ledgato adapter / gateway
  ↓
ALLOW / DENY / APPROVE
  ↓
protected credential / tool / API
  ↓
downstream verification
```

### Autonomy invariant

> **Closing the Ledgato tab must not weaken, disable, or pause governance.**

If enforcement depends on an open browser session, a foreground dashboard, or a human continuously watching the product, the integration does not satisfy the intended autonomous-agent model.

Human interaction should occur only when policy requires it, for example an `APPROVE` decision. The approval may be surfaced through the Ledgato console or an embedded/native notification surface, and a valid scoped approval should allow the agent to resume automatically without turning the console into an operating workspace.

### Commercial / onboarding shape

The product should be understandable as:

**Connect the agent/runtime → connect protected systems → define the authority envelope → leave it running.**

The website should communicate that the value happens while the user is **not** in Ledgato. The product is not "another AI dashboard"; the dashboard exists so the human can understand and control an otherwise autonomous enforcement system.

## Progressive Authority Calibration

Ledgato should not depend on a comprehensive upfront permissions interview. The authority interview is a **bootstrap and exception-resolution component** inside a broader progressive calibration model.

The operating pattern is:

```text
connect agent/runtime + protected systems
        ↓
discover available principals / actions / resources
        ↓
establish a minimal safe baseline
        ↓
short initial calibration for high-value boundaries only
        ↓
agent works autonomously
        ↓
new consequential boundary is encountered
        ↓
ask a precise contextual authority question
        ↓
explicit scoped decision
        ↓
typed authority record / permit / policy
        ↓
agent resumes automatically when allowed
        ↓
verify outcome + expire / revoke as applicable
        ↓
observe repeated decisions
        ↓
propose narrower standing rule for explicit confirmation
```

This model reduces the need for users to predict every future agent behavior during onboarding while preserving explicit authority.

### Safe baseline

Unknown consequential authority must not silently default to broad autonomy.

For unresolved boundaries, policy should resolve to an explicit safe state such as:

- `DENY`; or
- `APPROVE` / ask the owner when the action is legitimate but not yet covered by standing authority.

The exact default may be configurable, but an unanswered authority dimension must never expand authority.

### Initial calibration

Onboarding should ask only the small set of questions needed to establish a useful starting envelope, such as:

- how unknown consequential actions should be handled;
- whether reversible development actions may run autonomously;
- whether production changes require approval initially;
- whether autonomous monetary authority begins at zero or a bounded threshold;
- whether agents may delegate any authority;
- which connected systems should be protected first.

The goal is not completeness. It is enough declared authority for the agent to begin useful autonomous work safely.

### Contextual just-in-time authority

When the runtime encounters a consequential action not covered by standing policy, Ledgato should ask about the **actual requested action**, with the principal, resource, consequence, scope, and duration already known.

Prefer choices such as:

- **Allow once**
- **Allow for this task**
- **Allow until [time / expiry]**
- **Allow automatically under these stated conditions**
- **Ask me each time**
- **Deny**

A valid scoped approval should allow the paused agent workflow to resume automatically without requiring the owner to operate Ledgato as a workspace.

### Low-ambiguity question contract

The contextual question itself should remain concise, close-ended, and typed.

The division of responsibility is:

- **ALVIRA** may supply relevant context and help prioritize which authority questions are worth asking;
- **Ledgato** owns the authority questions, structured answers, resulting enforcement profile, confirmation, and policy activation;
- **context may suggest a question or proposed rule, but context must never silently answer an authority question or grant authority.**

Core rule:

> **Context may reduce the number of questions. Context may not answer an authority question on the user's behalf.**

Each consequential question should identify, where applicable:

- principal / agent;
- action;
- resource or environment;
- condition;
- requested scope;
- expiry / duration;
- delegation behavior;
- authority decision being requested;
- response type;
- resulting policy field(s).

Question-design rules:

- ask one consequential decision at a time;
- make the consequence explicit, such as "production deployment" rather than "deploy";
- separate read, write, delete, spend, publish, delegate, approve, and credential access where those distinctions matter;
- never infer permission from tone, preference, past context, or prior approval of a different action;
- prefer structured choices, bounded numeric thresholds, named-resource selectors, and explicit conditions over free text;
- free text may collect labels, named resources, rationales, or custom thresholds, but should not be the primary mechanism for granting consequential authority;
- preserve an explicit unknown/unresolved state instead of filling policy gaps with model inference.

### Deterministic authority records

The source of truth is a typed authority record, not conversational prose.

A grant should be capable of representing at least:

```text
principal
action
resource
conditions
scope
duration / expiry
delegation rule
decision
authority provenance
```

Before a standing rule becomes active, show its effect in plain language: what Ledgato will allow automatically, what still requires approval, and what remains denied.

### Explicit refinement, never silent authority learning

Ledgato may learn **what policy to propose**, but it must not learn itself into broader authority.

Repeated approvals or recurring patterns may trigger a suggestion such as:

> You have approved this same preview deployment under the same conditions repeatedly. Keep asking, allow automatically under these conditions, or customize?

The existing policy remains in force until the user explicitly confirms a replacement or extension.

A concise product description is:

> **You do not need to predict everything your agent might do. Ledgato asks when a new boundary actually matters, records the rule you choose, and gets out of the way next time.**

A useful first-run sequence is therefore:

**Connect → Minimal calibration → Protect → Calibrate in context**

## Jev pre-decision intelligence

Jev is a candidate **pre-decision intelligence layer** for Progressive Authority Calibration. It may help Ledgato determine what kind of boundary is being encountered and what information is missing, but it must not become the source of authorization.

The intended placement is:

```text
agent action request
        ↓
Jev advisory analysis
(classify / match / novelty / missing decision / minimal question)
        ↓
Ledgato deterministic policy + authority records
        ↓
ALLOW / DENY / APPROVE
        ↓
enforcement
        ↓
independent downstream verification
```

Jev may:

- classify the requested action/boundary;
- identify candidate applicable policy or authority records;
- detect materially novel requests or scope differences;
- identify the minimum unresolved authority dimension;
- generate/select a concise contextual question for the user;
- detect repeated decision patterns;
- propose a narrowly scoped standing rule for explicit confirmation;
- abstain when confidence or evidence is insufficient.

Jev must not:

- return or activate an authoritative `ALLOW`, `DENY`, or `APPROVE` decision;
- issue permits, credentials, grants, or execution authority;
- silently expand scope from prior decisions;
- transform ALVIRA context into authority;
- modify standing policy without explicit confirmation;
- substitute model confidence for deterministic policy evaluation or downstream verification.

Jev output is therefore **advisory evidence** consumed by Ledgato. The authorization engine remains deterministic over explicit policy / authority records.

### Promotion gate

Do not place Jev into the live decision path merely because the integration interface exists.

First benchmark it against labeled historical/synthetic authority-boundary cases covering:

- boundary/action classification;
- policy-match retrieval;
- novelty / material-difference detection;
- unresolved-authority identification;
- minimal-question selection;
- repeated-pattern detection and narrow rule proposals;
- correct abstention under ambiguity or insufficient evidence.

The benchmark must preserve a structural safety invariant: **Jev cannot directly produce executable authority.** Any runtime promotion must keep a deterministic Ledgato decision layer between Jev output and enforcement.

The initial bootstrap/benchmark contract is documented in `JEV_PREDECISION_BOOTSTRAP.md`.

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
- **khrystal — Agent Assurance**: evaluates, tests, records, and where integrated enforces consequential authority boundaries around agent actions.

The systems should close a loop without collapsing into the same product.

A simplified flow is:

**Context → Portfolio decision → Route → Governed execution → consequential boundary → khrystal ALLOW / DENY / APPROVE → execution continues or stops → verification/evidence feeds learning**

khrystal is therefore **independent assurance, not an independent workflow**.

## Product boundary

### In scope

- declared agent authority / scope as policy;
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
- containment and governed recovery when provider-side truth shows a boundary was crossed;
- integrations that embed assurance into existing work surfaces.

### Future, but aligned

- richer runtime-boundary integrations without becoming the runtime itself;
- policy learning from prior approvals and violations;
- comparative assurance intelligence across agents, workflows, harnesses, hosts, models, and environments;
- expected-result vs. actual-result verification;
- reusable organization-level authority templates;
- feedback from verified outcomes into future governance.

### Explicitly not the product thesis

- generic runtime observability;
- continuous surveillance of every agent action for its own sake;
- a generic SIEM or replacement security stack;
- portfolio intelligence or work prioritization;
- rebuilding OpenTelemetry or commodity tracing;
- becoming a second agent execution runtime;
- requiring a manual approval step for every low-risk action;
- promising to prevent every exploit, escape, zero-day, or malicious behavior.

A defensible khrystal promise is to **reduce reachable authority, gate consequential crossings, detect provider-side boundary violations, limit blast radius where integration allows, preserve trustworthy evidence, and support governed recovery** — not to make autonomous systems infallible.

## PEART record model

PEART remains an **internal assurance/evidence model**, not a second customer-facing product or public standard at this stage.

Working expansion:

- **P — Provenance**: where the action/work came from — task, workflow, agent, harness, host, model, initiator.
- **E — Evidence**: tests, artifacts, tool outputs, screenshots, validations, probe results, receipts, or other support for the requested action/result.
- **A — Authority**: permissions, policy, budget, requestor, environment, allowed boundary, and human or automated approval context.
- **R — Result**: the expected result before execution and, later, the actual result after verification.
- **T — Trace**: the ordered path of actions, handoffs, retries, boundary requests, and decisions that connects provenance to result.

A boundary decision can create or append to a PEART record. Later verification can complete the same evidence chain with the actual outcome.

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
