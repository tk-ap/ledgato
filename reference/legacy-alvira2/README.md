# Archived alvira2/ledgato salvage

Source: `alvira2/ledgato` at commit `db691c8a0e6b2190af678e549a5092ceb1044fd0` (2026-08-24).

This directory is **reference-only**. Nothing here is production Ledgato code.

## Deployment boundary

The canonical Ledgato implementation remains in:

- `engine/ledgato/` — current enforcement engine
- `web/` and root `index.html` — current live web surfaces
- root `vercel.json` — deployment configuration

Nothing under `reference/legacy-alvira2/` is imported by those paths, registered as a route, included in the current web source tree, or referenced by Vercel configuration. Do not wire these files into production without a separate reviewed migration.

## Preserved material

### Policy regression concept

`policy-regression/` preserves the old fixture-based policy regression harness and its tests. It is kept for its design: record expected decisions, replay them after policy changes, and fail when verdicts unexpectedly flip.

It targets the older policy API and is **not current runnable engine code**. Port the idea to the current `evaluate_action()` / gateway model before use.

### UI reference

`ui/` preserves selected authority/runtime visualization work:

- interactive authority graph
- path inspector
- attack/proof replay visualization
- authority route composition
- runtime decision surface

These files retain stale imports and old ALVIRA-specific assumptions by design. They are design/source references only and must not supersede the current live UI.

## Deliberately not preserved

The old parallel Python runtime, old overlapping engine/API/ledger implementations, bundled ALVIRA source snapshots, auth/database code, deployment scripts, fonts, and old build system were not copied because the canonical repository has newer implementations or those files belonged to the obsolete site.
