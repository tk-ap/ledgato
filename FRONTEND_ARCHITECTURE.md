# Ledgato Frontend Architecture

Status: canonical migration contract for Issue #17

## Why this exists

The current public UI was deployed from local prebuilt Vercel output. The exact editable source that produced the live homepage/app shell is not present on `main`. That means the present deployment is useful as a visual/behavioral reference, but it cannot remain the production source of truth.

This document defines the permanent frontend architecture before any further production homepage promotion.

## Permanent source-of-truth rules

1. **GitHub commit = production source.** Every production deployment must be reproducible from one commit in `tk-ap/ledgato`.
2. **One repo-owned frontend package owns all browser routes.** `/`, `/login`, `/signup`, and `/app/**` must be built from editable source in this repository.
3. **No historical deployment may be a build dependency.** Production builds must not fetch HTML, JS, CSS, assets, or route bundles from a previous Ledgato deployment.
4. **Vercel Git integration is canonical.** Production and previews must carry Git commit metadata. Local `vercel --prebuilt` output is not an accepted production source path.
5. **Generated artifacts are never source.** `dist/`, `.vercel/output/`, minified bundles, and recovered deployment snapshots can be fixtures only.
6. **Visual parity is a migration requirement, not a reason to keep opaque bundles.** The current production site is the design oracle while source is reconstructed.
7. **Claims are editable source content.** Demo/live labels and enforcement claims must be defined in normal source files/components and covered by tests.
8. **Engine status is explicit.** Frontend state must distinguish `demo`, `connected`, `unavailable`, and `user-entered`. It must never infer live enforcement from a page render alone.

## Target repository shape

```text
web/
  package.json
  tsconfig.json
  vite.config.*
  src/
    routes/
      index.*
      login.*
      signup.*
      app/
    components/
    content/
      claims.*
    data/
      engine-status.*
    styles/
  public/
  tests/
```

The current production bundle identifies a React/TanStack/Vite lineage. Preserve that family unless implementation evidence shows a lower-risk path. This migration is not permission for a framework rewrite.

## Route ownership

### `/`

Owns the public homepage. Preserve the current layout, typography, motion, graph interaction, marquee, FAQ, CTA, and overall visual hierarchy.

### `/login` and `/signup`

Own authentication entry points and guest-demo entry. Preserve current visual language and make demo state explicit.

### `/app/**`

Owns the browser control-plane experience. UI must consume a typed runtime-status contract instead of embedding assumptions about Python availability in route copy.

## Authenticated console charter

The authenticated site is a **control room for autonomous enforcement**, not a workspace the user must keep open and not the mechanism that activates Ledgato.

Core invariant:

> **Closing the Ledgato tab must not weaken, disable, or pause an already configured enforcement boundary.**

The console should answer these owner questions before exposing internal implementation terminology:

1. **Is everything under control?** — current protected-boundary health, runtime availability, and anything requiring attention.
2. **What can each agent do?** — understandable authority envelopes: allowed, approval-required, and denied.
3. **What systems are actually protected?** — integrations where Ledgato is in the real execution path, with evidence state clearly distinguished from configured-only connections.
4. **Does anything need me?** — pending approvals or unresolved drift, with scoped approve/deny actions.
5. **What actually happened?** — activity and evidence showing attempted action, decision, execution result, downstream verification, and bypass/drift status.
6. **How do I change the rules?** — policy and authority configuration.
7. **How do I protect another boundary?** — integrations/onboarding for adapters, SDKs, gateways, and supported protocols.

Preferred authenticated information architecture:

```text
Overview
Agents
Protected Systems
Approvals
Activity / Evidence
Policies
Integrations
```

Names may evolve, but the responsibilities should stay legible. Internal concepts such as PEART, permit formats, policy-engine internals, or raw authority-resolution structures belong behind progressive disclosure rather than as the primary overview.

The default successful state should be quiet and legible, for example: no action required, governed actions completed automatically, verification status healthy. The console should demand attention only when an approval, drift, verification failure, or configuration problem requires the owner.

## Progressive authority calibration UX

The console should support **progressive authority calibration**, not force users through a comprehensive permissions questionnaire before the product becomes useful.

The authority interview remains available as a structured question surface, but it serves three narrower jobs:

1. **minimal onboarding calibration** for the few high-value defaults needed to begin safely;
2. **contextual just-in-time decisions** when an agent reaches a consequential boundary not covered by standing policy;
3. **policy refinement** when repeated approvals create enough evidence to propose a narrower standing rule.

### Onboarding

Keep first-run calibration intentionally short. Establish the safe baseline, protect initial systems, and let the user leave the product.

Do not require every agent/action/resource combination to be preconfigured before protection starts.

### Contextual decisions

When a real boundary is encountered, show the actual context already known:

- agent/principal;
- requested action;
- protected system/resource;
- environment;
- consequence / impact;
- requested scope;
- expiry or task duration;
- delegation implications when applicable.

Default action choices should support scoped decisions such as **Allow once**, **Allow for this task**, **Allow until expiry**, **Allow under these conditions**, **Ask me each time**, and **Deny**.

After an allowed decision, the originating agent workflow should be able to resume automatically.

### Question controls

This is not a generic chat surface. Use close-ended controls—single-select, multi-select, toggles, bounded numeric inputs, named-resource selectors, and explicit conditional choices—whenever consequential authority is being granted.

Requirements:

- show one consequential authority decision at a time;
- do not preselect an authority-expanding answer from ALVIRA context;
- ALVIRA-derived context may reorder, suppress, or propose questions, but any authority-expanding result requires an explicit user selection;
- preserve unanswered/unknown states rather than filling gaps with inference;
- show proposed policy separately from active policy;
- before activation, summarize exactly what will become automatic, approval-required, or denied;
- let users amend prior rules without editing YAML or raw policy;
- repeated behavior may produce a policy suggestion, never an automatic authority expansion.

The interview/calibration UI produces typed policy inputs suitable for the engine. An LLM-generated prose summary is explanatory only and cannot be the activated source of truth.

## Runtime-status contract

The frontend must receive or derive exactly one of these presentation states:

```ts
type RuntimePresentationState =
  | { mode: 'demo'; source: 'sample'; connected: false }
  | { mode: 'connected'; source: 'engine'; connected: true; observedAt: string }
  | { mode: 'unavailable'; source: 'engine'; connected: false; reason: string }
  | { mode: 'user-entered'; source: 'workspace'; connected: false };
```

Rules:

- `demo` may show sample interactions but never `LIVE · ENFORCING`.
- `connected` may show engine-derived claims only when a successful engine response supplies the data.
- `unavailable` must say the engine is unavailable and must not retain stale live badges.
- `user-entered` must not imply discovery or enforcement occurred automatically.

## Claim ownership

Create one source module for public product claims. It must separate:

- product capability claims;
- sample/demo labels;
- tested proof statements;
- runtime-state labels.

The tested GitHub proof may say, in substance:

> A protected `github.pull.merge` request routed through Ledgato returned `DENY`; the merge endpoint was not invoked and readback confirmed the pull request remained open.

It must not be generalized into universal containment.

## Production-reference policy

Reference deployment:

- deployment: `dpl_C5wMNA4Xq8pV7jxYmCLeT5sAojbL`
- host: `ledgato-47k586kdi-alvira2.vercel.app`

Allowed use:

- screenshots;
- manual comparison;
- automated screenshot/parity baselines;
- copy/route inventory while reconstructing source.

Forbidden use after migration:

- build-time fetch;
- runtime proxy dependency;
- copying its minified bundle into production as the canonical editable implementation;
- treating it as the latest source after Git-backed production is established.

## Migration order

1. Reconstruct the frontend package from repo-owned source while matching production visuals.
2. Recreate `/`, `/login`, `/signup`, and `/app/**` routes.
3. Replace embedded engine assumptions with the runtime-status contract.
4. Move claim fixes from PR #16 into editable source.
5. Add claim-boundary tests.
6. Add route/deep-link tests.
7. Produce a Git-backed Vercel preview.
8. Compare desktop/mobile against the current production reference.
9. Verify no historical deployment URL is a source dependency.
10. Promote the Git-backed build.
11. Only then retire the temporary recovery implementation in PR #16.

## Release gate

A frontend change is not production-ready unless all of these are true:

- build succeeds from a clean checkout;
- build does not fetch a historical Ledgato deployment;
- Vercel preview identifies its Git commit;
- `/`, `/login`, `/signup`, `/app`, and known deep links render;
- demo/live labels are truthful;
- current production visual parity is acceptable;
- claim tests pass;
- no route regresses into `ENGINE NOT AVAILABLE HERE` while simultaneously presenting current engine-derived state as live.

## What not to do

- Do not merge PR #16's recovery script as the permanent frontend.
- Do not replace the current design with the old root `index.html` merely because that file is editable.
- Do not rebuild the frontend in a different framework for aesthetic architecture reasons.
- Do not combine the Python engine runtime into the browser bundle.
- Do not publish reconstructed source until visual and route parity are tested.
