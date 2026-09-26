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
