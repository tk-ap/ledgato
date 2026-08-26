# Minimal live product slice

## Production-safety constraints

- Preserve both `/` and `/app`; add no catch-all redirects.
- Develop and deploy from a non-production branch.
- Never run `vercel --prod`, `vercel promote`, or alias/domain commands in this work.
- Treat preview state as ephemeral until durable storage and managed keys are connected.

## Incremental delivery

1. **Restore repeatable Git builds.** Add the missing Vite manifest and explicit multi-page inputs for `/` and `/app`.
2. **Expose one real vertical slice.** Route a single request through policy evaluation, adversarial probes, the release gate, and signed-ledger verification.
3. **Make product truth visible.** Label the app `PREVIEW / EPHEMERAL`; state that Ledgato authorizes but does not execute the external tool.
4. **Verify before review.** Run engine tests, web contract tests, a production build, route-output checks, and browser/API checks on a preview deployment.
5. **Promote only after explicit approval.** Durable storage, stable signing-key custody, authentication, rate limits, and audit retention remain prerequisites for production promotion.

## Acceptance story

At `/app`, a user selects a real policy-bound action and runs a containment check. The backend evaluates the request, blocks an out-of-scope attempt, runs adversarial probes, gates the release, writes signed hash-chained evidence, verifies that chain, and returns the evidence to the UI in one atomic request.
