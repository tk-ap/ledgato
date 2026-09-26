# Ledgato Go-to-Market: Validation Before Expansion

> Status: current commercial operating plan
>
> Decision horizon: six-week validation sprint
>
> Investment posture: continue only as a tightly scoped customer-and-enforcement proof; do not fund a broad platform build yet

## The decision in one sentence

Ledgato will first sell **change control for autonomous coding agents**: agents can work normally, while Ledgato independently authorizes and proves every merge, deployment, secret access, and destructive infrastructure change.

This wedge is narrower than the long-term Agent Assurance direction. It is chosen because the boundary is consequential, understandable, testable, and already has native integration points in GitHub and CI/CD.

## What we are—and are not—proving

### First proof

For one real customer workflow, prove that:

1. the agent does not hold a direct credential that bypasses Ledgato;
2. every selected consequential action reaches Ledgato before execution;
3. Ledgato returns **ALLOW**, **DENY**, or **APPROVE** from deterministic policy and current authority;
4. denied actions do not reach the downstream provider;
5. approval pauses and resumes the same action without widening its authority;
6. expiration and revocation take effect in the downstream path;
7. the actual result is verified after execution; and
8. the customer receives a durable record of request, authority, decision, approver, action, and result.

### Claim boundary

Until this proof exists outside the founder's own environment, Ledgato may claim only that it:

- blocks tested actions where its gateway is correctly integrated and cannot be bypassed;
- reduces reachable authority and blast radius;
- requires approval when policy says a human decision is necessary; and
- produces evidence about tested authorization decisions and outcomes.

Ledgato must not claim that it stops every AI agent, prevents every exploit, guarantees containment, or is production-proven across customers.

## Initial ideal customer

The first customer is not a large enterprise security department. It is a technically capable, AI-native software team that can adopt quickly and has already crossed from agent experimentation into consequential execution.

### Required signals

- 3–30 engineers or an equivalently small product/engineering organization;
- uses Codex, Claude Code, Cursor, Devin, OpenHands, or a custom coding-agent harness every week;
- permits agents to open pull requests, run CI, access cloud environments, or participate in deployments;
- has at least one action the team refuses to let an agent perform without human review;
- currently relies on broad credentials, repository permissions, branch protection, manual Slack approval, or custom scripts;
- can run a six-week pilot without a six-month procurement process; and
- has an engineering leader or security-minded founder who owns the risk.

### Strong urgency signals

- an agent changed or nearly changed the wrong repository, environment, or resource;
- a prompt-injection, secret exposure, runaway-cost, or permission-scope concern delayed deployment;
- the team is increasing agent autonomy but cannot explain effective authority end to end;
- reviewers cannot distinguish human and agent responsibility for a change;
- the team wants agents to deploy, but only under explicit task, environment, and approval limits.

### Disqualifiers for the first sprint

- the team only uses AI for chat, drafting, or local autocomplete;
- there is no consequential external action to govern;
- the buyer wants generic monitoring rather than prevention;
- adoption requires broad compliance certification before any pilot;
- the team cannot isolate credentials behind the enforcement path; or
- the team wants a guarantee that no agent can ever escape or behave maliciously.

## The first offer

### Six-week Agent Change-Control Pilot

The partner chooses one workflow and one or two high-consequence action classes, such as:

- merge to a protected branch;
- deploy to staging or production;
- read or use a protected secret;
- change cloud infrastructure;
- perform a destructive repository or infrastructure action.

Ledgato provides:

- workflow and authority mapping;
- a policy definition for the selected boundary;
- an enforcement gateway or adapter in the real execution path;
- **ALLOW / DENY / APPROVE** decisions;
- approval/resume, expiry, and revocation;
- pre-pilot and adversarial bypass tests;
- post-action verification;
- an evidence report and end-of-pilot recommendation.

The design partner provides:

- a named technical owner;
- access to a safe test or staging workflow;
- a real consequential boundary and its current workaround;
- weekly feedback;
- permission to measure aggregate pilot outcomes; and
- a final paid-continuation decision.

### Commercial structure

- Discovery interviews are free and last 25 minutes.
- A design-partner pilot may be free or founder-priced only when the partner provides real integration access, weekly feedback, measurement permission, and a buying decision.
- “Free pilot” must never mean an open-ended custom build.
- By the third qualified partner, test a paid pilot or refundable implementation deposit.
- Final pricing is not set before interviews reveal the budget owner, present workaround cost, and consequence of failure.

## Six-week execution plan

### Week 1 — Recruit and discover

- Build a list of 40 qualified teams.
- Ask 25 people for a 25-minute problem interview.
- Complete at least five interviews.
- Record current workflow, feared action, current control, failure consequence, buyer, urgency, and willingness to pilot.

### Week 2 — Complete ten interviews and select partners

- Complete ten qualified interviews total.
- Score each team using `DESIGN_PARTNER_RECRUITING.md`.
- Invite the five strongest candidates into a scoped pilot conversation.
- Secure three written design-partner commitments.

### Week 3 — Map one real boundary

- Select the fastest partner workflow.
- Diagram every route to the protected action.
- Remove or revoke direct agent credentials.
- Define policy, approval owner, expiry, revocation, expected result, and evidence fields.
- Establish baseline friction and current failure/near-miss history.

### Week 4 — Integrate and attack

- Put the action behind Ledgato in staging or a safe test repository.
- Test direct-call bypass, credential reuse, stale approval, forged approval, replay, revocation, concurrency, and fail-open behavior.
- Treat every bypass as a product failure, not a documentation issue.

### Week 5 — Run live pilot work

- Allow normal agent work through the controlled boundary.
- Measure correct allows, correct denials, approvals, false denials, decision latency, approval latency, bypass attempts, and verification mismatches.
- Interview the operator about friction immediately after consequential events.

### Week 6 — Prove value and ask for commitment

- Deliver the evidence report.
- Compare the pilot with the prior control/workaround.
- Ask for paid continuation, expansion to another boundary, or a clear rejection reason.
- Decide **continue**, **narrow**, or **pause** using the gates below.

## Gates for continued investment

Continue beyond the sprint only if all minimum gates are met:

| Gate | Minimum evidence |
| --- | --- |
| Problem | At least 6 of 10 qualified teams describe a real consequential-action control problem, not hypothetical interest |
| Partners | 3 teams commit a named owner, real workflow, weekly feedback, and final buying decision |
| Enforcement | 1 external workflow demonstrates that denied actions never reach the downstream provider under the tested conditions |
| Bypass resistance | Direct credentials are removed and documented red-team attempts cannot reach the protected action outside Ledgato |
| Usability | Normal authorized work remains usable; false denials and approval delays are measured and acceptable to the partner |
| Commercial | At least 1 partner pays, signs a paid continuation, or begins a credible procurement path with budget ownership identified |
| Trust | Credential handling, tenant isolation, audit integrity, recovery, and failure behavior have an accepted plan for the next boundary |

Pause or materially narrow Ledgato if any of the following is true after the sprint:

- fewer than six interviewed teams have an active problem;
- no team will place a real workflow behind the gateway;
- all interest is in generic dashboards or compliance theater;
- the controlled path can be bypassed without compromising a separate hardened system;
- the product creates more operational friction than the perceived risk justifies; or
- nobody with budget authority will pay or sponsor procurement.

## Metrics that matter

### Customer evidence

- qualified interviews completed;
- urgent problems confirmed;
- design-partner commitments;
- pilots activated;
- paid continuations;
- time from first call to protected action.

### Enforcement evidence

- percentage of selected consequential actions routed through Ledgato;
- unauthorized downstream calls made: target **zero** under tested conditions;
- direct credentials remaining in agent environments: target **zero** for the selected action;
- revocation propagation time;
- approval replay or stale-authority successes: target **zero**;
- verification mismatches detected and resolved.

### Workflow quality

- false-denial rate;
- policy-decision latency;
- human-approval latency;
- number of manual steps added;
- partner-reported confidence before and after the pilot.

## Product sequencing rule

During this sprint, implementation priority is determined by partner proof, not platform completeness.

Build now only when required to:

1. make the selected enforcement path non-bypassable;
2. protect credentials and tenant data;
3. support approval, revocation, recovery, verification, or evidence in that path; or
4. convert a qualified partner into a real pilot.

Defer broad adapter coverage, generalized dashboards, speculative AI supervision, category expansion, branding changes, and features without a committed partner workflow.

## Relationship to the wider product direction

Agent Change Control is the entry point, not the long-term ceiling. If the wedge is validated, the same assurance engine can expand from GitHub/CI into cloud changes, protected data, external communications, spending, and multi-agent delegation.

That expansion happens one proven boundary at a time. The long-term category remains Agent Assurance; the immediate job is to earn the right to expand it.
