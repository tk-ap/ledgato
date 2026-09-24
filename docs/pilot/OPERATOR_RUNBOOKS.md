# Ledgato pilot operator runbooks

The step-by-step procedures the onboarding checklist's Section E only names.
Written for the operator running the pilot gateway. Each is grounded in the
current engine behavior; where a procedure is manual because no tool exists yet,
that gap is called out rather than hidden.

Default state files (paths as configured for the gateway; these are the
conventional names): `ledger.jsonl`, `authority.json`, `approvals.json`,
`idempotency.json`. All live on the single gateway host.

---

## RB-1 — Revoke the gateway's GitHub access (kill switch)

Use when anything looks wrong: unexpected merges, a suspected credential leak,
or a partner request to stop. The goal is to make the gateway unable to touch
GitHub within seconds, then investigate.

1. **Cut GitHub access first.** Revoke or delete `GATEWAY_TOKEN` at GitHub
   (Settings → Developer settings → PAT, or revoke the App installation). This
   is the real stop: even a running gateway can no longer merge.
2. **Stop the gateway process** so it accepts no new requests.
3. **Confirm** the token is dead:
   ```
   GH_TOKEN=$GATEWAY_TOKEN gh api repos/OWNER/REPO >/dev/null && echo STILL_LIVE || echo REVOKED
   ```
   Proceed only when this prints `REVOKED`.
4. **Optional, at the Ledgato layer:** revoke any live authority grants so a
   later restart cannot resume them (admin credential required):
   ```
   curl -s -X POST localhost:PORT/v1/authority/grants/<grant_id>/revoke \
     -H "Authorization: Bearer $ADMIN_SECRET" -d '{"reason":"kill switch"}'
   ```
5. **Record** who executed this, when, and why, in the pilot log.

This procedure must be **dry-run once during onboarding** (checklist D1) against
a throwaway token, so the first time it runs for real is not the first time.

---

## RB-2 — Resolve a stuck PENDING execution

An idempotency key is marked PENDING the moment a governed execution starts and
COMPLETED only after its receipt is written (`engine/ledgato/idempotency.py`).
If the gateway crashes, or GitHub errors, between those points, the key stays
PENDING and any retry with the same key is refused:

> `IdempotencyPending: idempotency key '…' has an unresolved prior attempt;
> verify downstream state before retrying`

This is deliberate fail-closed behavior: Ledgato will not re-execute a protected
action it is unsure about. Resolving it is a human decision.

**Do not simply retry or delete the record blind.** First establish what really
happened on GitHub.

1. **Stop the gateway** (so nothing races your inspection).
2. **Find the record** in `idempotency.json` by its key; note the request
   fingerprint and `created_at`.
3. **Establish ground truth on GitHub** — did the merge actually happen?
   ```
   GH_TOKEN=$GATEWAY_TOKEN gh api repos/OWNER/REPO/pulls/<PR>/merge -i | head -1
   # 204 => merged, 404 => not merged
   ```
   Cross-check the PR's `merged` / `merge_commit_sha`.
4. **Decide:**
   - **The action did NOT happen downstream** → the operation is safe to retry.
     Remove that key's entry from `idempotency.json` so a fresh attempt can run.
   - **The action DID happen** → do not re-execute. Record the observed result
     as the outcome and leave the key resolved (do not retry with it).
5. **Restart the gateway** and confirm the workflow proceeds.
6. **Record** the key, what GitHub showed, and the decision.

> **Known gap (hardening, not blocking):** there is no `ledgato` CLI command to
> inspect or resolve a PENDING record — step 4 is a manual JSON edit under a
> stopped gateway. A small `ledgato idempotency {list,resolve}` helper would
> make this safer and is worth filing as a follow-up before scaling past one
> partner. It is not a pilot blocker because the manual procedure is safe when
> done with the gateway stopped.

---

## RB-3 — Export, verify, and back up evidence

The evidence ledger is a hash-chained, signed file on the gateway host. It is
strong on integrity and weak on availability (single host, no built-in backup),
so the operator owns durability.

1. **Check integrity any time:**
   ```
   ledgato ledger --tail 20      # entries + "chain integrity: OK/BROKEN"
   ledgato status                # head, height, proof-of-work
   ```
2. **Export a verifiable report** for a given agent/release, which anyone can
   verify without trusting this host:
   ```
   ledgato report --agent AGENT --release RELEASE --out evidence-bundle.json
   ledgato report --verify evidence-bundle.json   # VERIFIED ✓ / NOT VERIFIED
   ```
   The full signed chain is also available at `GET /v1/ledger/chain`.
3. **Back up** `ledger.jsonl` off-host on a schedule agreed with the partner
   (the chain detects tampering; it cannot survive host loss on its own).
4. **Retention:** agree with the partner how long evidence is kept and where the
   authoritative copy lives.

Give the partner the `ledgato report --verify` command explicitly: their ability
to check evidence themselves, without trusting Ledgato, is the point.

---

## RB-4 — Rotate the approver (or a principal) secret

Approval identity in the pilot is bearer-secret custody: whoever holds the
approver secret can decide approvals (`engine/ledgato/principals.py`). Rotate on
a schedule and immediately on any suspected exposure.

1. Generate a new secret for the principal.
2. Update `LEDGATO_PRINCIPALS` (or the injected registry) with the new
   `id:role[:trust_domain]:secret`, keeping id and role the same.
3. **Restart the gateway** — the registry is read at startup, so rotation takes
   effect on restart (there is no hot-reload; note this to the partner).
4. Distribute the new secret to the approver over a secure channel; retire the
   old one.
5. Record the rotation (who, when) — but never the secret value.

> Constraint to disclose: there is no MFA on approval and no per-decision human
> proof beyond secret custody in the pilot. Scope the approver secret tightly.

---

## RB-5 — Respond to a GitHub outage

When GitHub is unreachable, a downstream call raises and the gateway surfaces a
`502`; no path turns an error into ALLOW. The failure modes are stall, not
bypass.

1. **A denied or paused action during an outage** is unaffected — the gateway
   made no GitHub call. No action needed.
2. **An authorized execution that started before the outage** may leave its key
   PENDING if the outage hit between the merge call and the receipt. Treat it
   with **RB-2** once GitHub is reachable — verify downstream truth first.
3. **Do not** relax any policy, widen scope, or bypass the gateway to "get work
   through" during an outage. The correct behavior is to wait and then resolve
   any PENDING keys.
4. Communicate the stall to the partner; the workflow resumes when GitHub
   recovers and any PENDING keys are resolved.

---

## Quick index

| Situation | Runbook |
| --- | --- |
| Something is wrong, stop GitHub access now | RB-1 |
| Retry refused: "unresolved prior attempt" | RB-2 |
| Give the partner / keep evidence | RB-3 |
| Approver secret exposed or due for rotation | RB-4 |
| GitHub is down | RB-5 |
