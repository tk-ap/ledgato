# Production UI recovery — preserve the live design

Date: 2026-09-07

## Decision

Preserve the current `ledgato.vercel.app` homepage design, visual system, layout, motion, navigation, and interaction model. Do **not** promote the older reconstructed launch-candidate UI; it was technically useful but visually degraded relative to the current production experience.

The immediate production change is claim accuracy and demo/live labeling only, plus the strongest technical-proof affordances demonstrated in the preview.

## Why this recovery layer exists

The current public homepage was traced to Vercel deployment `dpl_C5wMNA4Xq8pV7jxYmCLeT5sAojbL` (`ledgato-47k586kdi-alvira2.vercel.app`). Vercel reports that deployment as a CLI deployment of prebuilt output, with no GitHub commit metadata. Current GitHub `main` no longer contains the source tree that produced that UI, and current automatic Vercel builds from `main` fail because the Vercel project is still configured as Vite while the repository now primarily contains the engine/docs.

Therefore, editing the static `index.html` on `main` and claiming the live site was fixed would be false. Replacing production with the closed launch-candidate would also violate the explicit design decision.

Until the original source tree is recovered, `scripts/recover-production-ui.mjs` uses the immutable READY production deployment as the artifact source of truth, copies its static application into `dist/`, and applies text-only truth patches. It does not alter CSS, component geometry, motion classes, route bundles, or visual assets.

This is a recovery bridge, not the desired permanent frontend architecture. Once the original source is recovered or faithfully reconstructed and proven visually equivalent, that source should become canonical and this artifact-recovery build can be removed.

## Claim changes

The recovered preview changes only claims/labels that exceeded demonstrated enforcement:

- `LIVE · ENFORCING POLICY` → `DEMO · SAMPLE ENVIRONMENT`
- authority graph `LIVE · ENFORCING` → `DEMO · SAMPLE ENVIRONMENT`
- removes universal `If it can reach your stack, Ledgato can see it` language
- bounds enforcement to actions routed through the Ledgato gateway
- bounds discovery/verification language to connected integrations and protected workflows
- labels the interactive runtime card as a demo that executes no external action
- updates metadata/FAQ/footer positioning toward independent authorization and enforcement rather than universal control

## Useful technical-preview behavior preserved

The old technical preview was useful where it separated demonstration from proof. The current visual design is retained, while its existing verification/probe section is repurposed to surface the real tested GitHub boundary:

1. protected GitHub credential held by the Ledgato gateway;
2. workflow requested `github.pull.merge`;
3. policy returned `DENY`;
4. GitHub merge endpoint was not called;
5. downstream readback confirmed the pull request remained open;
6. signed evidence exists.

This is the correct place to use a real-enforcement label because that specific boundary was actually tested. The rest of the illustrative homepage remains clearly labeled as sample/demo state.

## Deployment rule

Do not promote this branch directly to production.

Required sequence:

1. Vercel preview builds successfully from this branch.
2. Compare the preview with current production on desktop and mobile for visual parity.
3. Confirm `/`, `/login`, `/signup`, `/app`, and refresh/deep-link behavior.
4. Confirm the broad claims listed above are absent from the rendered preview.
5. Confirm the real GitHub proof is clearly distinguished from the sample authority/runtime content.
6. Only then merge/promote.

If recovery of any required production asset or any critical text replacement fails, the build must fail rather than silently publish a partial or redesigned site.
