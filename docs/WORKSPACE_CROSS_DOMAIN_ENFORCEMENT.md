# Cross-domain Workspace enforcement requirements

**Status:** Future integration requirements, not a claim of deployed enforcement. **Canonical operating mandate:** [AgentOS Workspace Operating Mandate](https://github.com/tk-ap/agent-os/blob/docs/workspace-operating-mandate-20260923/docs/WORKSPACE_OPERATING_MANDATE.md). Update to main after merge.

LEDGATo remains an independent authorization and enforcement boundary for consequential protected crossings. This document extends possible protected action classes for the AgentOS / ASHWOOD long-term workflow; it does not broaden the current commercial wedge or claim all domains are supported. Preserve the existing [enforcement thesis](../ENFORCEMENT_THESIS.md), product direction and go-to-market gates.

## Action classes and proposed gates
| Domain | Example protected action | Required policy considerations |
| --- | --- | --- |
| AgentMail / communications | Send consequential external correspondence, disclose private records | Recipient, data scope, delegated authority, approval and post-send evidence |
| Career | Submit applications, withdraw candidacy, respond to offers | Destination, version of materials, user approval, audit trail |
| Auditions / agency | Submit audition materials, accept bookings or contractual terms | Agency identity, deadlines, rights/terms, explicit approval |
| Business / publishing | Publish public claims, send sponsor/investor commitments | Publication scope, claim provenance, identity, approval |
| Finance | Initiate payments or alter financial accounts | Strong explicit authority, amount/recipient limits, independent verification; no implied permission from read access |
| Administration | Send legally consequential notices or share sensitive documents | Recipient, exact document scope, explicit human decision |
| Engineering | Merge, deploy, access secrets or make destructive changes | Preserve current enforcement and verifier-independence requirements |

## Cross-cutting contract
Before a protected action, bind the decision to task/work identity, actor, delegated authority, exact action and target, resource/data scope, expiry, revocation state and evidence. Return ALLOW, DENY or APPROVE as appropriate. Require non-bypassable enforcement at the actual action boundary before claiming prevention. Persist decision provenance and independently verify downstream outcome where supported. A draft or proposed action is not authorization; a UI click must not silently grant broad future authority.

AgentOS owns orchestration and durable task state; Agent Control owns generic authorization intelligence where integrated; LEDGATo supplies independent enforcement where materially relevant and correctly integrated; ASHWOOD presents approvals and evidence without becoming an alternate authority source. External systems retain their own source records.

## Rollout
Treat this as a roadmap contract. Complete the current coding-agent enforcement wedge and independently verified AgentOS lifecycle work first. Add cross-domain enforcement only alongside a real adapter, scoped policy, revocation path, non-bypassable integration and test evidence. Never represent future coverage as live.
