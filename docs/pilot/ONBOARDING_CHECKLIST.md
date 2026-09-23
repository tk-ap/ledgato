# Ledgato pilot onboarding checklist

Operationalizes the gates in `PILOT_READINESS_AUDIT.md` and the blocker in
issue #46. Work through it **with** the design partner, once, before the first
governed action. Every MUST-PASS step is a go/no-go gate: if it fails, do not
start the pilot until it is fixed. Record the outcome of each step; the record
is the proof the pilot was set up honestly.

Placeholders: `OWNER/REPO` the pilot repository, `BRANCH` the protected branch
(usually `main`), `AGENT_TOKEN` the credential the agent runs with, and
`GATEWAY_TOKEN` the credential held only by the Ledgato gateway.

---

## Section A — Enforcement validity (MUST PASS, blocker #46)

The whole pilot is meaningless if the agent can merge without the gateway. These
steps prove it cannot.

### A1. The agent credential cannot merge the protected branch directly

This is the single most important check. Prove that `AGENT_TOKEN` is refused by
GitHub for a direct merge, so the agent has no route around the gateway.

1. Open a throwaway PR into `BRANCH` in `OWNER/REPO`.
2. Attempt to merge it **using the agent credential**:
   ```
   GH_TOKEN=$AGENT_TOKEN gh api -X PUT \
     repos/OWNER/REPO/pulls/<PR_NUMBER>/merge -f merge_method=merge
   ```
3. **PASS** only if GitHub refuses (403/404/405, or a protection error) and the
   PR is still unmerged. Confirm with a fresh readback.
4. **FAIL** if the merge succeeds — the agent is not actually constrained. Stop.
   Reduce `AGENT_TOKEN`'s permissions until this step passes.

> Record: the exact response and the PR's unmerged state.

### A2. The agent credential cannot push directly to the protected branch

1. With the agent credential, attempt a direct push to `BRANCH`.
2. **PASS** only if the push is rejected by branch protection.

### A3. Credential separation is real, not nominal

- The gateway holds `GATEWAY_TOKEN`; the agent holds `AGENT_TOKEN`; they are
  **different credentials**, and `AGENT_TOKEN` lacks merge/push on `BRANCH`.
- **PASS** only if both are true. If the agent and gateway share one token, the
  pilot is advisory, not enforcing.

---

## Section B — Branch protection (MUST PASS, audit #5)

The merge DENY only means something if GitHub blocks every other route to the
protected branch.

### B1. Protection requires a PR and blocks direct pushes

```
gh api repos/OWNER/REPO/branches/BRANCH/protection
```

**PASS** only if the ruleset/protection: requires a pull request before merging,
blocks direct pushes to `BRANCH`, and (recommended) enforces for admins. Record
the settings.

### B2. No alternate merge path is left open

Confirm there is no second unprotected branch or automation (an Action with
write scope, a bot with merge rights) that can reach `BRANCH` without a PR.
**PASS** only if the PR path is the sole route in.

---

## Section C — Gateway credential isolation (MUST PASS, audit #7)

The OS-layer version of A3: the agent's process must not be able to read the
gateway's credential.

### C1. The gateway credential is not visible to the agent

- The gateway runs as a **different OS user / process / container** than the
  agent, and `GATEWAY_TOKEN` is not present in the agent's environment,
  keyring, config files, or shared mounts.
- **PASS** only if the agent process demonstrably cannot read `GATEWAY_TOKEN`
  (check env, `~/.config`, any shared volume the agent can reach).

### C2. The gateway host is trusted

- The host running the gateway is not the agent's own workspace, and its access
  is limited to operators. Record who can reach it.

---

## Section D — Revocation runbook (MUST PASS to exist, audit #2)

You must be able to cut the gateway's GitHub access immediately if something
goes wrong. Write this down before the pilot, do not improvise it during an
incident.

### D1. A one-command kill switch exists and is tested

- Documented steps to revoke `GATEWAY_TOKEN` at GitHub (delete/rotate the PAT,
  or revoke the App installation) **and** stop the gateway process.
- **PASS** only after you have dry-run the revocation on a throwaway token and
  confirmed the gateway can no longer merge afterward.

### D2. Owner and reachability

- Name the person who can execute D1 and how they are reached out of hours.

---

## Section E — Operating runbooks (PARTNER — disclose and prepare)

These are acceptable first-partner constraints, but the partner must be told and
the runbooks must exist.

- **E1. Single host / file-backed state (audit #3, #11).** One gateway host for
  the pilot; no HA. Evidence ledger lives on that host — set up a customer-side
  export/backup and state retention.
- **E2. PENDING resolution (audit #8).** If a governed execution crashes
  mid-flight, its idempotency key stays PENDING and blocks retries by design.
  Document how an operator inspects and resolves a PENDING record.
- **E3. GitHub outage behavior (audit #9).** Errors surface as failures, never
  as silent ALLOW; a mid-execute outage may leave a key PENDING (see E2).
  Confirm with the partner that a transient outage stalls rather than bypasses.
- **E4. Approver secret custody (audit #6).** Approval identity == who holds the
  approver secret. Scope it tightly, document rotation, and disclose that there
  is no MFA on approval in the pilot.

---

## Section F — Scope confirmation

- **F1.** Governed actions for the pilot are exactly `github.pull.merge` and
  `github.issue.comment` on `OWNER/REPO` — confirmed with the partner.
- **F2.** The partner has seen `GITHUB_ENFORCEMENT_OFFER.md`, including the
  "claims we will not make" section, and agrees the pilot is scoped to one
  action class on one protected branch.

---

## Go / no-go

The pilot may begin only when **every MUST-PASS step in Sections A–D passes**
and the Section E runbooks exist. Any FAIL in A–D is a hard stop.

| Gate | Result | Evidence / note | Date | Operator |
| --- | --- | --- | --- | --- |
| A1 agent cannot merge | ☐ pass ☐ fail | | | |
| A2 agent cannot push | ☐ pass ☐ fail | | | |
| A3 credential separation | ☐ pass ☐ fail | | | |
| B1 protection requires PR | ☐ pass ☐ fail | | | |
| B2 no alternate path | ☐ pass ☐ fail | | | |
| C1 gateway cred isolated | ☐ pass ☐ fail | | | |
| C2 gateway host trusted | ☐ pass ☐ fail | | | |
| D1 kill switch tested | ☐ pass ☐ fail | | | |
| D2 revocation owner named | ☐ pass ☐ fail | | | |
| E1–E4 runbooks exist | ☐ done | | | |
| F1–F2 scope confirmed | ☐ done | | | |

Sign-off (operator): ____________________  Date: __________

Sign-off (design partner): ____________________  Date: __________
