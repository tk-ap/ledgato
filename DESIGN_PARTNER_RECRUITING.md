# Recruiting 10 Teams and 3 Design Partners

This playbook supports the six-week validation plan in [`GO_TO_MARKET.md`](./GO_TO_MARKET.md). The immediate target is **10 qualified problem interviews**, leading to **3 design partners**, leading to **1 external enforcement proof and 1 paid continuation**.

## Funnel math

Do not search for only ten names. Build enough surface area to absorb silence and weak qualification.

| Stage | Target |
| --- | ---: |
| Qualified teams researched | 40 |
| Personal outreach messages | 25 |
| Warm-introduction requests | 10 |
| Replies or introductions | 15 |
| Qualified interviews completed | 10 |
| Pilot conversations | 5 |
| Design-partner commitments | 3 |
| Live external pilot | 1+ |
| Paid continuation or credible procurement | 1+ |

## Where to find the teams

Prioritize evidence that a team is already operating agents, not generic claims that it is “AI-first.”

### 1. Founder and engineering network

Ask former coworkers, founders, engineers, technical recruiters, and accelerator contacts one precise question:

> Who do you know that is already letting a coding agent open PRs, run CI, touch cloud resources, or participate in deployments?

A warm introduction to an active operator is worth more than a large cold audience.

### 2. GitHub evidence

Search public repositories and engineering posts for:

- bot-authored or agent-authored pull requests;
- mentions of Codex, Claude Code, Cursor, Devin, OpenHands, SWE-agent, or custom agents in contributor docs;
- workflow files that label or review AI-generated changes;
- issues discussing agent permissions, branch protection, secrets, sandboxing, approvals, or deployment safety;
- teams publishing their agent harness or autonomous-development workflow.

Contact the engineering lead or repository maintainer. Reference the concrete workflow you observed.

### 3. Communities where operators discuss implementation

Look for active practitioners in:

- AI Engineer and MLOps communities;
- GitHub, Hacker News, and relevant technical Discord or Slack groups;
- local Los Angeles AI/founder events;
- accelerator, indie-founder, and developer-tool communities;
- coding-agent product community forums and showcases.

Do not post a broad “who wants AI security?” advertisement. Ask for teams already granting agents meaningful permissions.

### 4. Adjacent vendors and consultants

Developer-tool agencies, fractional CTOs, cloud consultants, and agent-harness builders see the problem across several customers. They can become referral partners or design partners when they operate their own agent workflows.

Do not begin with large identity/security vendors. They are more useful for competitive learning than fast design-partner adoption.

## Qualification score

Score each team from 0–2 on every dimension. Interview teams scoring at least 8/12. Invite teams scoring at least 10/12 to a pilot discussion.

| Dimension | 0 | 1 | 2 |
| --- | --- | --- | --- |
| Agent use | Chat/autocomplete only | Agents propose code | Agents open PRs, run tools, or touch shared systems |
| Consequence | No external action | Shared code or staging | Merge, production, secrets, cloud, destructive action |
| Pain | Hypothetical | General concern | Incident, near miss, blocked rollout, or active manual burden |
| Control gap | Existing controls sufficient | Manual/custom workaround | Broad credentials, bypassable path, unclear effective authority |
| Adoption speed | Long procurement | Some review required | Founder/engineering owner can start in weeks |
| Commitment | Curiosity only | Will share workflow | Named owner, integration access, weekly feedback, buying decision |

## First outreach message

### Warm introduction request

> I’m testing Ledgato with small software teams already giving coding agents meaningful access. It sits outside the agent and can require policy or human approval before a merge, deployment, secret use, or destructive infrastructure action. I’m not looking for generic AI interest—I need to speak with someone whose agents already open PRs, run CI, or touch cloud systems. Is there one engineering lead you would feel comfortable introducing me to for a 25-minute problem interview?

### Direct message to an operator

> I saw that your team is using **[specific agent/workflow]** to **[observed action]**. I’m researching one narrow problem: once agents can act, how do teams prevent a valid credential or reachable tool from becoming accidental authority?
>
> I’m building Ledgato, an independent authorization gate for consequential agent actions. I’m not selling a platform on this call. I’m looking for 25 minutes to understand your current permissions, approval, and audit workflow. If the problem is real on both sides, I may invite a few teams into a six-week design-partner pilot.

### Public call for interviews

> Are your coding agents doing more than drafting code?
>
> I’m interviewing engineering teams whose agents can open PRs, run CI, access cloud environments, or participate in deployments. I want to understand what you still refuse to let an agent do—and what currently enforces that boundary.
>
> This is research for Ledgato, an independent authorization layer for consequential agent actions. I’m looking for 10 candid, 25-minute conversations with active operators—not general AI-security opinions.

## The 25-minute interview

Do not demo first. Do not teach the customer the problem. Ask for a recent concrete workflow.

1. What coding agents or harnesses did your team use in the last seven days?
2. Walk me through the most consequential thing one of those agents can currently do.
3. What can the agent reach because the human or runtime credential can reach it?
4. What is the highest-impact action you still refuse to delegate?
5. Tell me about the last time an agent crossed—or nearly crossed—the wrong boundary.
6. What stops that action today: provider permissions, branch rules, sandboxing, manual review, custom scripts, or trust?
7. How can the current control be bypassed accidentally or deliberately?
8. Who owns the risk and who would approve a new control?
9. What does the workaround cost in time, delayed autonomy, or engineering maintenance?
10. If one boundary could be independently enforced in six weeks, which would you choose?
11. What evidence would you need before placing that action behind a new gateway?
12. If the pilot worked, which budget would pay for continued use?

Listen for events, costs, workarounds, authority, and buying mechanics. “That sounds useful” is not validation.

## Design-partner commitment

A design partner agrees in writing to:

- name a technical owner and business/budget owner;
- select one real workflow and consequential action;
- provide a staging or safely constrained integration path;
- remove direct agent credentials for the protected action;
- meet weekly during the six-week pilot;
- permit measurement of aggregate outcomes;
- participate in bypass and failure testing; and
- make a paid-continuation decision at the end.

In exchange, Ledgato agrees to:

- scope the pilot to the selected boundary;
- document what is and is not protected;
- avoid using customer data or claims publicly without permission;
- provide the integration, policy, approval, revocation, verification, and evidence path;
- disclose observed failures and bypasses; and
- deliver an end-of-pilot evidence report.

## Interview record

Capture one row per team:

| Field | Record |
| --- | --- |
| Team / URL |  |
| Contact / role |  |
| Source / introducer |  |
| Agent and harness |  |
| Consequential action |  |
| Current credential path |  |
| Current control/workaround |  |
| Incident or near miss |  |
| Cost / urgency |  |
| Technical owner |  |
| Budget owner |  |
| Evidence required |  |
| Qualification score |  |
| Pilot candidate? |  |
| Next action / date |  |

## Weekly founder review

At the end of each week, answer:

- How many conversations involved a current problem rather than a hypothetical one?
- Which boundary was repeated most often?
- What do teams already trust to enforce it?
- What would make them refuse a gateway?
- Who owns the budget?
- Did any requested feature come from more than one qualified team?
- Are we learning, or merely collecting compliments?

The goal is not to persuade three friendly people to say yes. The goal is to discover whether three real operators will put a consequential action behind Ledgato and accept a buying decision when the proof is complete.
