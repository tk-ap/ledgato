# Ledgato pilot readiness — lab-only assumption audit

Issue: #32. Scope: the verified GitHub merge wedge (#31). Question answered:
**if we put Ledgato in front of one real team tomorrow, what exactly are we
promising, and what would stop us from proving it safely?**

Each assumption is classified:

- **MUST FIX** — blocks any external pilot.
- **PARTNER** — acceptable constraint for a first design partner who knows it.
- **HARDENING** — nice-to-have; not blocking.

Severity is the risk if the assumption is wrong in the customer's environment.

## The one gate everything rests on

The enforcement claim is real only if the agent cannot reach the merge boundary
except through the gateway. The gateway is the sole caller of the protected
adapter (`engine/ledgato/gateway.py`, the single `target.execute` call site),
and the GitHub adapter's own docstring states it: *"For enforcement to be
non-bypassable, the governed agent must not also possess an equivalent token."*
If the customer's agent already holds a merge-capable GitHub credential, Ledgato
is advisory, not enforcing — and we would be proving nothing. This must be
**verified at onboarding**, per repository. It is filed as its own blocker.

## Gap table

| # | Assumption (evidence) | Severity | Customer impact | Required fix | Blocks first partner? |
| --- | --- | --- | --- | --- | --- |
| 1 | **Agent may separately hold a merge-capable token.** Enforcement is non-bypassable only if it does not (`gateway.py` sole doorway; `adapters/github.py` docstring). | Critical | If false, every "DENY" is theater; the agent merges directly. | Onboarding check that the agent credential cannot merge the protected branch; document credential separation as a precondition. | **YES** |
| 2 | **Gateway credential is a long-lived PAT with no rotation/revocation path.** `_default_adapters_from_env` reads `LEDGATO_GITHUB_TOKEN`/`GITHUB_TOKEN`; adapter holds it for its lifetime. | High | A leaked or over-scoped token is a standing risk; no documented way to cut access fast. | Least-privilege, short-lived where possible; a documented instant-revocation runbook (rotate token / stop gateway). GitHub App is the productionizing path (#4). | **YES** (revocation runbook); PAT itself is PARTNER |
| 3 | **File-backed, single-host state** for authority, approvals, idempotency, campaigns (fcntl `flock` in each store; idempotency docstring: "not a distributed lock… single-process pilot"). | Medium | No HA; a second gateway host would not share state; host loss loses in-flight approvals. | Keep to one host for the pilot; state it plainly. Multi-host is post-pilot. | No — **PARTNER** (must be disclosed) |
| 4 | **PAT operating model, not GitHub App.** No installation tokens, no per-repo app scoping. | Medium | Coarser scoping and manual rotation than an App; harder to offer to a security-conscious team at scale. | GitHub App with short-lived installation tokens as the pilot-to-product step. | No — **PARTNER** for one partner |
| 5 | **Branch protection / ruleset is assumed, not enforced by Ledgato.** The merge DENY only matters if direct pushes are blocked on GitHub. | High | If protection is misconfigured, the agent bypasses the PR path entirely and Ledgato never sees the action. | Onboarding verification that protection blocks direct pushes and requires a PR; re-check periodically. | **YES** (verify at setup) |
| 6 | **Static bearer principal secrets; approver identity is a bearer token.** `principals.py` constant-time compare of static secrets; approver is whoever holds the approver secret. | High | A leaked approver secret lets an attacker approve merges; no MFA, no per-decision human proof. | Rotate secrets; scope the approver secret tightly; document that approval identity == secret custody. SSO/MFA is post-pilot. | No — **PARTNER** (with disclosure); rotation is HARDENING→MUST if pilot is long |
| 7 | **Sandbox/process isolation of the agent from the gateway credential** is assumed by the deployment, exercised in tests via bubblewrap (`test_sandbox_isolation.py`). | High | If the agent process can read the gateway's token/env/keyring, #1 fails at the OS layer. | Deploy the gateway credential outside the agent's process/user; document the isolation requirement. | **YES** (deployment requirement) |
| 8 | **Idempotency fails closed on a PENDING record** — a crash mid-execute leaves the key PENDING and blocks retries until an operator resolves it (`idempotency.py`). | Medium | A crash at the wrong moment stalls the workflow and needs a human to clear it; safe, but operationally rough. | An operator runbook for resolving PENDING; document the stall as intended fail-closed behavior. | No — **PARTNER** (needs runbook) |
| 9 | **GitHub-unavailable behavior:** `_call` raises on HTTP/URL error; the gateway surfaces 502. If failure happens after the merge call but before receipt completion, the key stays PENDING. | Medium | Transient GitHub outages produce errors and possible PENDING stalls, not silent wrong decisions. | Document retry/timeout behavior and the PENDING-resolution path; confirm no path treats an error as ALLOW. | No — **PARTNER** (with docs) |
| 10 | **Provider readback freshness** is already handled: dual-signal readback with `no-cache` headers and merge-commit existence, failing closed on disagreement (`adapters/github.py::_pull_readback`). | Low | Low — this is a strength; stale caches can't fake a merge. | None. Keep the dual-signal check under test. | No — **HARDENING** only |
| 11 | **Evidence durability:** hash-chained signed ledger on local disk; verifiable, but single-host and not backed up by Ledgato. | Medium | Host loss loses evidence; evidence integrity is strong but availability is not. | Customer-side backup / export of the ledger; document retention. | No — **PARTNER** (with export) |
| 12 | **Installation/configuration burden:** fence YAML, keys, principal secrets, adapter env, branch-protection setup, credential separation — all manual. | Medium | A team cannot self-serve; onboarding is hands-on. | An onboarding checklist + a scripted setup; acceptable to do it with the partner by hand for pilot #1. | No — **PARTNER** |
| 13 | **Enforcement-doorway completeness:** only `github.pull.merge` and `github.issue.comment` are adapter actions; unknown tools are denied out of scope. No non-gateway route reaches `execute` (grep-verified). | Low | Low — the doorway is narrow and closed by default. | Keep the "gateway is the only `execute` caller" invariant under a test. | No — **HARDENING** |

## Verdict

**Blocks the first design partner (MUST FIX before onboarding a real team):**
credential separation (#1), branch-protection verification (#5), gateway
credential isolation at the OS layer (#7), and a documented revocation runbook
(part of #2). These are onboarding-and-deployment gates, not engine rewrites —
the enforcement engine itself is sound and its tests pass.

**Acceptable for a first partner who is told (PARTNER):** PAT model, single-host
file-backed state, static bearer/approver secrets, PENDING-resolution and
GitHub-outage runbooks, local evidence with export, manual onboarding.

**Not blocking (HARDENING):** readback freshness (already strong), doorway
completeness test, secret rotation cadence.

The honest one-line answer to #32: the **code** is ready to prove the wedge; the
**onboarding and deployment** are what would stop us from proving it *safely*,
and those are checklist-and-runbook work, not new runtime features.
