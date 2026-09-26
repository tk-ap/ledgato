# Ledgato core product mental model

## Short version

> **Ledgato watches consequential agent actions, checks authority, stops unauthorized moves, and leaves evidence.**

A useful plain-language analogy is:

> **bouncer + referee + black box recorder**

The analogy is intentionally operational, not brand copy. The important distinction is that Ledgato is not merely observing or reporting after the fact. Its value comes from intervening at an enforceable boundary before a consequential unauthorized action completes.

## What Ledgato should do

For a consequential agent action, Ledgato should be able to:

1. **See the attempted action** — identify the action, target, task context, principal, requested scope, and relevant evidence.
2. **Check authority** — determine whether the action is inside declared authority and policy.
3. **Intervene** — resolve the boundary as `ALLOW`, `DENY`, or `APPROVE`.
4. **Stop or pause unauthorized/consequential action** — where Ledgato is integrated into an enforceable path, the downstream action must not proceed on `DENY`, and must pause on `APPROVE` until valid scoped approval exists.
5. **Resume only within approved scope** — approval must not become blanket permission or authorize a changed action, target, resource, or principal.
6. **Verify the real outcome** — after an allowed/approved action, confirm what actually happened at the downstream system.
7. **Leave durable evidence** — preserve the attempted action, policy/authority decision, approval where applicable, execution result, verification result, and any drift or bypass evidence.

## What Ledgato is not

A pure monitoring product says:

> "An agent did something risky."

A pure audit product says:

> "Here is the record of what the agent already did."

Ledgato's stronger product claim is:

> "The agent tried to cross a boundary it was not authorized to cross. Ledgato stopped or paused the action before completion, recorded why, and can show what approval would be required to continue."

That active intervention is the product.

## Product test

When evaluating a proposed feature, integration, claim, or design, ask:

> **Does this help Ledgato actually control a consequential boundary, or does it only observe/report one?**

Observation, alerts, dashboards, and evidence can support the product, but they are not a substitute for enforcement.

A strong implementation should make the following sequence true:

`attempt → authority check → ALLOW / DENY / APPROVE → enforce → verify → evidence`

## Truth standard

Do not claim that Ledgato "stopped" an agent merely because its policy engine returned `DENY`.

A stop claim requires evidence that:

- the protected downstream action did not occur;
- the agent did not possess or successfully use an equivalent bypass path;
- the enforced boundary was actually in the execution path; and
- the result was verified at the downstream provider/system.

If those conditions have not been demonstrated, describe the boundary as unverified or partially verified rather than implying prevention.

## Relationship to current product direction

This mental model is a plain-language compression of the existing Agent Assurance direction:

- **policy/authority** decides whether a crossing is permitted;
- **enforcement** makes that decision affect the real action;
- **approval** handles consequential but potentially legitimate crossings;
- **verification** confirms what happened afterward;
- **evidence** makes the result inspectable and provable.

It should guide product architecture, stress testing, first-client proof, messaging, and future integrations without narrowing Ledgato into a generic monitoring, SIEM, or audit-log product.
