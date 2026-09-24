# Ledgato pilot offer — governed GitHub merge

Issue: #31. Status: **defined, not yet installable by an outside team** — see
`PILOT_READINESS_AUDIT.md` (#32) for what stands between this and a safe pilot.

This document defines exactly one bounded offer around the wedge that is already
proven in the lab. It deliberately does not describe the whole product.

## The wedge

```
agent attempts a protected GitHub merge
  -> Ledgato authority check (DENY / APPROVE / ALLOW)
  -> the gateway calls GitHub only on ALLOW or a consumed approval
  -> provider verification reads the real merge state back
  -> a durable, signed evidence record
```

## The customer promise

> An autonomous agent in your workflow cannot merge a pull request into a
> protected branch unless a Ledgato policy currently authorizes that exact
> action. When authorization is required from a human, the merge pauses until a
> named approver decides. Every attempt — allowed, paused, or denied — leaves a
> signed, independently checkable record of what was requested, what Ledgato
> decided, and what actually happened on GitHub.

What makes the promise real rather than advisory: **the GitHub credential that
can perform the merge lives in the Ledgato gateway, not in the agent.** The
gateway is the only code path that calls GitHub (`engine/ledgato/gateway.py`,
the single `target.execute` call site). If the agent also holds a token that can
merge, Ledgato is advisory for that boundary and the promise does not hold. This
is the load-bearing setup condition, not a footnote.

## What the customer connects / provides

- **One repository** (`owner/name`) whose `main` (or chosen branch) is protected
  by a GitHub branch protection rule or ruleset that requires a PR and blocks
  direct pushes.
- **A GitHub credential for the gateway** scoped to that repository, able to
  merge — held only by the gateway process.
- **A Ledgato policy** (fence) declaring what the agent may do, what requires
  approval, and the impact ceiling.
- **Named approver identity** for the human who may decide paused merges.
- A place to run the gateway process (one host) reachable by the agent.

## Supported actions (v0)

| Action | Enforced | Verified by |
| --- | --- | --- |
| `github.pull.merge` | DENY / APPROVE / ALLOW | dual-signal merge readback + merge-commit existence |
| `github.issue.comment` | DENY / APPROVE / ALLOW | comment readback |

Merge is the wedge; comment is the low-impact companion that exercises the same
doorway.

## Not supported in the pilot

Direct pushes, branch/tag creation or deletion, release publishing, repository
administration, secrets, Actions/workflow changes, org-level actions, and any
non-GitHub system. Multiple repositories, multiple agents at once, and any
production-scale or high-availability guarantee are also out of scope. Ledgato
does not manage the customer's branch protection — it relies on it.

## Acceptance criteria for a successful pilot

A pilot is successful when, against the customer's real repository:

1. A merge the policy does not authorize is **denied before any GitHub merge
   call is made**, and provider readback confirms the PR remains unmerged.
2. A merge requiring approval **pauses**, and only executes after the named
   approver decides — and executes **exactly once**.
3. An authorized merge **executes and is confirmed merged** by independent
   readback.
4. Every one of the above produces a **signed evidence record** whose chain the
   customer can verify without trusting Ledgato's word.
5. Across the pilot window, **no merge to the protected branch occurs without a
   corresponding ALLOW/approval evidence record** — checked against GitHub's own
   history, not against Ledgato's log.

Criterion 5 is the real proof: it is falsifiable from the customer's side.

## Evidence the customer receives

Per governed action, a ledger entry containing: the agent, the requested action,
the decision and its reasons, the authority grant (if any), whether the
downstream call was made (`downstream_execute_called`), whether the boundary was
crossed (`boundary_crossed`), and the provider readback. Entries are hash-chained
and signed; the customer can run ledger verification independently.

## Setup assumptions

- Branch protection is configured and enforced by the customer on GitHub.
- The agent's own credentials cannot merge the protected branch directly
  (verified at onboarding — see the audit).
- One host, one repository, one agent identity for the pilot.
- The gateway process is trusted and its host is not shared with the agent's
  credential store.

## Claims we will not make

- Not "the agent cannot reach GitHub" — only that it cannot cross *this* merge
  boundary without authorization.
- Not "Ledgato secures your repository" — it governs one action class on one
  protected branch.
- Not high availability, multi-tenant isolation, or protection against a
  compromised gateway host.
- Not "AI safety." This is one enforceable authority boundary with evidence.
- A blocked attempt proves the boundary held *for that attempt*, not that no
  other route exists.
