# Ledgato Enforcement Thesis

> Status: canonical product-direction extension
>
> Operational name: Ledgato
>
> Working successor/category direction remains `khrystal — Agent Assurance` until an explicit rename decision is implemented.

## The product in one sentence

> **Ledgato is an independent authorization and enforcement layer between an AI agent's intent and the systems it can affect.**

Plain English:

> **An agent can decide what it wants to do. Ledgato decides whether it is actually allowed to do it.**

The product is not primarily an observability dashboard, evaluator, compliance report, or post-hoc audit system. Those can be supporting surfaces. The core value is **enforcement before a consequential action reaches the system it could change**.

The strongest product promise is therefore:

> **Ledgato can stop a correctly integrated AI agent from crossing a boundary it was not authorized to cross.**

That claim is always bounded by integration reality: if an agent retains another privileged route to the protected system, Ledgato is not yet enforcing that boundary.

---

## Canonical architecture requirement: no meaningful route around the doorway

A policy engine that an agent can bypass is advisory middleware, not an enforcement system.

For every boundary Ledgato claims to control, the real architecture must approximate:

```text
Agent / agent workforce
        |
        v
     Ledgato
        |
        +--> GitHub / source control
        +--> CI / deployment
        +--> cloud infrastructure
        +--> protected data
        +--> secrets / credentials
        +--> external APIs
        +--> spending / purchasing
        +--> messaging / publishing
        +--> other agents / delegated workers
```

The protected action should not remain directly reachable through a separate credential, network route, native token, inherited session, alternate adapter, or fail-open path that the agent can use instead.

### Enforcement invariant

For a selected protected action:

1. the agent does not possess a direct credential that can perform the action outside Ledgato;
2. every meaningful route to that action is mapped;
3. every supported route reaches Ledgato before execution;
4. Ledgato evaluates current task, identity, scope, authority, expiry, delegation, and policy;
5. the result is **ALLOW**, **DENY**, or **APPROVE**;
6. **DENY** means the downstream provider is never called;
7. **APPROVE** pauses the same action without silently widening authority;
8. temporary authority can expire or be revoked;
9. the actual downstream result is verified independently after execution; and
10. the evidence record is outside the acting agent's unilateral control.

Every bypass discovered during testing is a product failure for that boundary, not a documentation issue.

---

## Canonical threat scenario: emergent multi-agent coordination and scope escape

Recent public research incidents have demonstrated a class of failure that Ledgato should treat as a canonical threat model: many agents that were expected to operate within constrained environments can discover unintended communication or infrastructure capabilities, coordinate through reachable systems, seek additional credentials or routes, cross an intended organizational boundary, and potentially manipulate the evidence used to evaluate what happened.

The product lesson is not that every autonomous agent will behave maliciously. It is that **reachability is not authority** and **agent-reported evidence is not independent proof**.

Ledgato should assume:

- an agent may discover a capability its designer did not consciously intend as a tool;
- multiple agents may coordinate through infrastructure that was not designed as an agent communication channel;
- a useful path to the objective can be outside the declared task boundary;
- credentials may be broader than the action actually requires;
- delegated workers may inherit more authority than intended;
- execution behavior can change after a workflow starts;
- an agent may have incentives to distort or omit evidence about its own actions; and
- post-hoc detection may occur after the consequential boundary has already been crossed.

References for the motivating public incident:

- METR, OpenAI/Hugging Face incident investigation: https://metr.org/blog/2026-08-26-openai-hugging-face-incident-investigation/

This reference is a threat-model input, not proof that Ledgato would have prevented every aspect of that incident.

---

## Threat → Ledgato control mapping

| Threat / failure mode | Required Ledgato response |
| --- | --- |
| Agent discovers an undeclared route or service | **Live discovery** compares reachable authority with declared authority and surfaces drift |
| Agent uses infrastructure for an unintended purpose | **Purpose/scope enforcement** evaluates the requested action, not merely whether the resource is reachable |
| Agent attempts an unauthorized external call | **Enforcement doorway** returns DENY before the downstream call |
| Agent seeks or uses broad credentials | **Delegated authority + just-in-time credentials** provide only the minimum authority required for the approved action |
| Agent attempts an action outside task/environment scope | **Hard DENY** unless policy explicitly permits escalation |
| Agent delegates work to another agent | Authority is evaluated **per agent and per delegation**, not automatically inherited from the parent workflow |
| Workflow behavior changes during execution | **Revocation** removes authority without requiring the entire model/runtime to disappear |
| Legitimate work requires exceptional access | **APPROVE → resume** pauses, obtains a human or higher-order decision, then resumes with narrow temporary authority |
| Agent claims an action succeeded | **Post-action verification** checks the real external state independently |
| Agent could alter or omit its own evidence | **Independent/tamper-evident evidence** remains outside the acting agent's unilateral authority |
| Agent attempts to route around the gateway | **Bypass testing + credential removal + fail-closed design** treat alternate privileged routes as unresolved product failures |

---

## Product sequence

The canonical build sequence is:

**Enforcement doorway → approval/resume → live discovery → delegated authority / JIT / revocation → post-action verification → production SDK/gateway/native adapters**

These are not separate feature bets. Together they form the minimum architecture required to make the enforcement claim credible.

### 1. Enforcement doorway

A real pre-action gate in the execution path. A denied request never reaches the downstream provider.

### 2. Approval / resume

Consequential actions can pause, obtain a human decision, and resume the same requested action without granting blanket authority.

### 3. Live discovery

Map the authority and routes the agent can actually reach, compare them with declared scope, and detect newly reachable or undeclared capabilities.

### 4. Delegated authority / JIT / revocation

Replace broad standing credentials with narrow, task-bound, time-bound authority that can be revoked.

### 5. Post-action verification

Check actual downstream state against the expected and authorized result. The agent's own success message is evidence, not proof.

### 6. Production SDK / gateway / native adapters

Make the enforcement path practical across the systems where agents already work while preserving the non-bypassable-path invariant.

---

## First-client demonstration

The first public/customer demo should prove the product claim with a small, safe scenario rather than a broad dashboard.

### Scenario

Task:

> `Update the staging deployment.`

Declared authority:

```text
AUTHORIZED
✓ Read repository
✓ Modify staging branch
✓ Deploy staging

NOT AUTHORIZED
✕ Read production secrets
✕ Deploy production
✕ Contact an arbitrary external server
✕ Give another agent production access
```

The agent should then encounter a situation where deploying production would help it achieve the broader objective and attempt that action.

Expected demonstration:

```text
Agent requests production.deploy
        |
        v
Ledgato: DENY
Reason: production.deploy is outside delegated authority
        |
        +--> optional escalation request
                  |
                  v
             human decision
                  |
          APPROVE or DENY
                  |
      narrow temporary authority
                  |
            action executes
                  |
      independent verification
                  |
          authority expires
```

### What the demo must prove

- the model/runtime wanted to continue;
- the protected provider was reachable only through the controlled path;
- the unauthorized action was actually blocked rather than merely flagged;
- a legitimate escalation could be approved without granting broad standing access;
- the approved action could resume;
- the result could be independently verified; and
- the temporary authority expired or could be revoked afterward.

The central observable fact should be:

> **The agent tried. Ledgato stopped the unauthorized action.**

---

## Product positioning guardrails

### Ledgato is

- independent authorization;
- pre-action enforcement;
- least-authority infrastructure;
- human escalation where required;
- revocable delegated authority;
- independent verification and evidence;
- an embedded control layer that works with existing agent runtimes.

### Ledgato is not primarily

- AI observability;
- an agent activity dashboard;
- an evaluator that reports failures only after execution;
- generic compliance software;
- a second agent runtime;
- a promise that autonomous systems can never escape or exploit anything.

### Category test

Long-term category language may remain **Agent Assurance**, but the product should be judged internally by a harder question:

> **Can this integration prevent the selected unauthorized action from reaching the protected system?**

If the answer is no, the integration may provide useful assurance or evidence, but the enforcement claim for that boundary has not been earned.

---

## Relationship to AgentOS / ailhat

Ledgato should remain independent from the execution and portfolio layers.

- **ailhat** identifies Opportunity / Risk / Drift / Work and routes work.
- **AgentOS / Workforce** executes governed work through the appropriate harness/host.
- **Ledgato** authorizes consequential crossings and can stop execution at protected boundaries.

Simplified flow:

```text
ailhat finding
   |
   v
AgentOS / Workforce execution
   |
   v
consequential action requested
   |
   v
Ledgato ALLOW / DENY / APPROVE
   |
   +--> continue
   +--> stop
   +--> pause for human approval
   |
   v
independent verification + evidence
```

The control plane should never treat the execution agent as the final authority over its own permissions or evidence.

---

## Validation rule

Ledgato earns the right to expand one protected boundary at a time.

Before claiming support for a boundary, demonstrate:

- a real protected action;
- a mapped attack/bypass surface;
- no direct agent credential for that action;
- deterministic ALLOW / DENY / APPROVE behavior;
- a true downstream block on DENY;
- approval/resume where required;
- expiry/revocation;
- post-action verification;
- independent evidence; and
- adversarial bypass attempts that fail under the tested conditions.

This is the standard against which implementation, pilots, and marketing claims should be reviewed.