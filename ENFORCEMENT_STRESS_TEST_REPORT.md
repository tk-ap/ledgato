# Ledgato Enforcement Stress Test — Report

**Status: IN PROGRESS — boundary `github_lab_merge` is `UNVERIFIED`.**

This report is the running evidence record required by
`CLAUDE_ENFORCEMENT_HANDOFF.md` (execution override) and
`AGENT_DIRECTIVE_ENFORCEMENT_STRESS_TEST.md` (base directive).

No PASS claim is made in this document. The mission statement quoted in the
handoff is deliberately **not** reproduced here, because the live-provider proof
has not run.

---

## 1. Run metadata

| Field | Value |
| --- | --- |
| Date started | 2026-09-07 |
| Repository | `tk-ap/ledgato` (local `/home/tk/Work/LEDGATo`) |
| Base `main` SHA | `cd7f4fc32010af499a68ef10404515f18e3717bd` |
| Implementation branch | `proof/enforcement-stress-test` |
| Executing model/agent | Claude Opus 5 (`claude-opus-5`), Claude Code harness |
| Host OS | Linux 7.1.9-arch1-2 |
| Python | 3.14.7 (`/usr/bin/python3`) |
| Test venv | ephemeral, session scratchpad |
| Production deployments changed | **none** |

### Dependency versions (test venv)

```
pytest==9.1.1        PyYAML==6.0.3        cryptography==50.0.1
fastapi==0.141.1     starlette==1.6.0     uvicorn==0.52.4
httpx==0.28.1        pydantic==2.13.5     pydantic_core==2.46.5
```

### Exact commands

```bash
python3 -m venv <venv> && <venv>/bin/pip install -e "engine[dev]"
cd engine && <venv>/bin/python -m pytest tests/ -q
```

---

## 2. Stage 0 — branch and baseline

| Step | Status | Evidence |
| --- | --- | --- |
| Record current `main` SHA | DONE | `cd7f4fc32010af499a68ef10404515f18e3717bd` |
| Create dedicated implementation branch | DONE | `proof/enforcement-stress-test` |
| No production deployment changed | HOLDS | no deploy/push/merge performed |
| Start this report | DONE | this file |
| Record runtime/dep versions + commands | DONE | section 1 |

Note: local `main` was 6 commits behind `origin/main` at session start and was
fast-forwarded to `cd7f4fc` before branching. Working tree was clean (0 modified
tracked files) at that point.

---

## 3. Stage 1 — baseline of existing engine tests

Command: `<venv>/bin/python -m pytest tests/ -q`

Result: **69 passed, 0 failed** (2 unrelated deprecation warnings from
`starlette.testclient`).

The handoff requires explicit confirmation of five invariants. Each was read at
source level to confirm the test body asserts what its name claims — a passing
name alone was not accepted as evidence.

| Required invariant | Test | Asserts (verified by reading the test body) |
| --- | --- | --- |
| DENY never calls downstream execute | `test_deny_never_calls_downstream_execute` | `status == DENY`, `executed is False`, `boundary_crossed is False`, `adapter.executions == 0` |
| ALLOW executes and verifies | `test_allow_executes_and_verifies_afterward` | `adapter.executions == 1`, `adapter.verifications == 1`, `verification.verified is True` |
| APPROVE pauses and resumes once | `test_approval_pauses_then_resumes_exactly_once` | pause with `executions == 0`; resume → `executions == 1`; second resume raises `ValueError` and `executions` stays `1` |
| Revoked authority blocks future execution | `test_revoked_grant_blocks_future_execution` | post-revoke call returns `DENY` with reason `expired or revoked`; `executions` stays `1` |
| Discovery reports drift | `test_live_discovery_reports_permission_drift` | `drift is True`, `undeclared_gains == ["fake.evil"]` |

**Regressions found: none.** No existing gateway behavior was rewritten.

**Scope limit on this evidence:** all five tests run against `FakeAdapter`, an
in-process double. They establish gateway *control flow* only. Per handoff gap
#6 they are not bypass-resistance evidence and contribute nothing toward
`VERIFIED`.

---

## 4. Independently confirmed pre-existing defects

The handoff lists these as known gaps. They were re-confirmed at source rather
than taken on trust.

### 4.1 CONFIRMED — API authentication fails open (handoff gap #2)

`engine/ledgato/api.py:173-180`

```python
configured_key = api_key or os.getenv("LEDGATO_API_KEY")

def _auth(authorization: str | None = Header(default=None)) -> None:
    if not configured_key:
        return          # <-- fails OPEN
    ...
```

If neither the `api_key` argument nor `LEDGATO_API_KEY` is set, `_auth` returns
successfully and **every** endpoint carrying `Depends(_auth)` is unauthenticated.
That set includes `/v1/gateway/execute`, `/v1/authority/grants`,
`/v1/authority/grants/{id}/revoke`, `/v1/approvals/{id}/approve`, and
`/v1/approvals/{id}/resume`.

Severity for this proof: **blocking**. A misconfigured or env-stripped
deployment silently has no enforcement boundary at all.

### 4.2 CONFIRMED — identities are caller-supplied strings (handoff gap #3)

`engine/ledgato/api.py:240-315`

`gateway_execute` passes `agent=req.agent` and `requested_by=req.requested_by`;
`issue_grant` passes `granted_by`; `revoke_grant` passes `revoked_by`;
`approve`/`deny_approval` pass `decided_by` — all straight from the request body,
with no binding to the presented credential.

Consequence: a single shared API key is sufficient to act as any agent, issue or
revoke grants as any granter, and **approve one's own pending request as any
human**. Separation of duties does not currently exist.

Severity for this proof: **blocking**. Stage 6's "only human principal approves"
cannot be honestly demonstrated until identity is bound to credentials.

---

## 5. Stage 2 — enforcement-boundary record

Implemented in `engine/ledgato/boundary.py` (`EnforcementBoundary`,
`BoundaryEvidence`, `BoundaryStore`). Statuses: `UNVERIFIED`,
`PARTIALLY_VERIFIED`, `VERIFIED`, `BYPASS_FOUND`.

The directive's central rule — *a successful ALLOW/DENY/APPROVE decision must
never automatically set `VERIFIED`* — is enforced structurally, not by
convention:

* `record_decision()` files decisions as `kind="decision"` audit evidence and
  is incapable of raising `bypass_status`.
* `set_status("VERIFIED")` refuses unless adversarial evidence
  (`bypass_attempt` / `leakage_attempt` / `escalation_attempt` /
  `approval_abuse_attempt`) has been recorded.
* Any attempt recorded with `protected_action_occurred=True` latches
  `BYPASS_FOUND`, which cannot be left without `remediation` evidence.
* A Ledgato outage that left the action impossible is explicitly *not* counted
  as a bypass — only a protected action that actually happened is.

Live check against the real boundary id:

```
registered github_lab_merge -> bypass_status = UNVERIFIED
after 3 recorded DENY decisions -> bypass_status = UNVERIFIED
set_status("VERIFIED") -> ValueError: cannot mark VERIFIED: no bypass/leakage/
  escalation attempts recorded. Policy decisions alone are not
  bypass-resistance evidence.
```

Tests: `engine/tests/test_boundary.py`, 15 passing.

Not yet done: the gateway does not yet write decisions into a `BoundaryStore`.
That wiring is deferred to Stage 6, when real provider decisions exist to
record. Nothing in the current claim depends on it.

---

## 6. Stage 4 — mandatory, fail-closed API authentication

`create_app()` now refuses to start when no credential is configured, instead
of silently serving every protected endpoint unauthenticated:

```
RuntimeError: Ledgato refuses to start unauthenticated: set LEDGATO_API_KEY or
LEDGATO_PRINCIPALS, or pass require_auth=False for an explicitly
unauthenticated local development instance.
```

The module-level ASGI app is now built lazily via PEP 562 `__getattr__`, so
`uvicorn ledgato.api:app` still resolves and still fails closed, while merely
importing the module does not trigger the check.

| Required behavior | Status | Test |
| --- | --- | --- |
| Missing auth configuration fails closed | DONE | `test_missing_auth_configuration_fails_closed` |
| Unauthenticated instance requires explicit opt-in | DONE | `test_explicit_opt_out_is_required_for_unauthenticated_instance` |
| Missing credentials rejected (401) | DONE | `test_missing_credentials_rejected` (3 endpoints) |
| Invalid credentials rejected (401) | DONE | `test_invalid_credentials_rejected` (4 malformed forms) |

`/health` remains public. It exposes status, version, difficulty, ledger entry
count, and the *names* of configured policies and adapters. No secret and no
mutable capability. Recorded as accepted minor information disclosure, not
remediated.

---

## 7. Stage 5 — authenticated principal separation

`engine/ledgato/principals.py` introduces `Principal`, `PrincipalRegistry` and
`enforce_claim`. Identity is derived from the presented bearer credential;
`agent`, `granted_by`, `revoked_by` and `decided_by` became *optional claims*
that are rejected when they disagree with the authenticated principal, rather
than being silently overwritten — so spoofing shows up as a 403 rather than a
quietly corrected request. Secrets are compared with `hmac.compare_digest`.

Roles: `agent`, `approver`, `admin`.

| Required property | Enforced by | Test |
| --- | --- | --- |
| Identity comes from credentials, not body strings | `enforce_claim` | `test_recorded_identity_is_the_credential_not_the_claim` |
| Agent cannot approve its own request | role gate on `/approve` | `test_agent_cannot_approve_its_own_request` |
| Agent cannot deny approvals | role gate on `/deny` | `test_agent_cannot_deny_approvals` |
| Agent cannot issue grants | role gate | `test_agent_cannot_issue_grants` |
| Agent cannot revoke grants | role gate | `test_agent_cannot_revoke_grants` |
| Agent cannot act as another agent | `enforce_claim` | `test_agent_cannot_execute_as_another_agent` |
| Approver cannot impersonate another human | `enforce_claim` | `test_approver_cannot_impersonate_a_different_human` |
| Human credential cannot launder an agent action | role gate | `test_approver_cannot_drive_agent_execution` |
| Legitimate flow still works | — | `test_full_legitimate_flow_still_works` |

A shared `LEDGATO_API_KEY` is still supported for single-tenant use, but is
mapped onto an explicit **admin** principal — so it can administer authority and
*cannot* drive governed agent execution
(`test_shared_key_still_supported_but_is_an_admin_principal`).

**Scope limit:** these are bearer secrets in a process-local registry. There is
no key rotation, expiry, or per-request signing, and a leaked secret is a full
impersonation of that principal. Adequate to prove separation of duties in an
isolated lab; not an identity system.

---

## 8. Test results after stages 2/4/5

```
engine $ <venv>/bin/python -m pytest tests/ -q
103 passed, 2 warnings
```

84 pre-existing (69 original + 15 boundary) plus 19 new principal/auth tests.
No pre-existing gateway behavior was rewritten. Commit: `f3facc6` on
`proof/enforcement-stress-test`.

---

## 9. Stage 3 — BLOCKED. Disposable GitHub lab cannot be built to standard

Stage 3 states: *"Do not continue until the agent has no merge-equivalent
credential."* That condition cannot currently be met. Execution stopped here
rather than proceeding, per the handoff's runtime-gap protocol.

### What the runtime supports today

| Requirement | Available? | Evidence |
| --- | --- | --- |
| Isolated agent sandbox | **Partially** | `bwrap` works rootless; a sandbox with `--unshare-all --share-net` and tmpfs `/home` could not see the host `gh` credential directory. Docker daemon is permission-denied; no podman/lxc; no microVM. |
| Disposable GitHub repo | Yes, on request | `gh` can create and later delete (`delete_repo` scope held) |
| **Ledgato-held scoped credential** | **NO** | see below |
| Agent sandbox without merge capability | Blocked by the above | — |

### The blocker

The only GitHub credential on this machine is the host's `gh` OAuth token for
account `tk-ap`, scopes `delete_repo, gist, read:org, repo, workflow`.

Measured blast radius: **10 repositories reachable, including all four
production repos — `ledgato`, `ALVIRA`, `agent-os`, `ailhat`.**

Installing that token as "the Ledgato-held GitHub credential" would violate the
base directive's own safety boundaries:

* boundary 1 — do not test against ALVIRA/ailhat/AgentOS/Ledgato production;
* boundary 7 — every stress test must remain scoped to assets created for the test.

Stage 7 requires *actively attempting to steal the gateway credential from the
sandbox*. Staging a token with production write access as the theft target is
precisely the wrong experiment: a successful leak test would compromise every
production repository rather than a disposable lab.

`gh` cannot mint a narrower credential. Its `auth` subcommands are
`login, logout, refresh, setup-git, status, token, switch` — there is no
command to create a fine-grained PAT or a GitHub App, and GitHub exposes no API
for PAT creation. Both require an interactive browser session as the account
owner.

### Missing contract

A Ledgato deployment needs a **gateway credential whose authority is bounded to
the boundary it guards**. Today `EnforcementBoundary.gateway_credential_owner`
records *who owns* the credential but nothing constrains *what that credential
can reach*, so a boundary can be declared over a lab repo while the credential
behind it reaches production. That is a product gap, not just a lab-setup
inconvenience.

### Smallest fix to unblock (requires TK — interactive, cannot be automated)

1. Create a **fine-grained PAT** at `github.com/settings/personal-access-tokens`
   with: repository access limited to **only** `tk-ap/ledgato-enforcement-lab`;
   permissions Contents `read/write`, Pull requests `read/write`,
   Administration `read/write` (to configure branch protection); short expiry.
2. Provide it as `LEDGATO_GITHUB_TOKEN` to the gateway process **only**.
3. Confirm the lab repo may be created (it must be **public** if branch
   protection is required without a paid plan).

Then stages 3, 6, 7, 8 and 10 can run as written.

### Preserved state for resumption

* Branch `proof/enforcement-stress-test`, base `cd7f4fc`, commit `f3facc6`.
* Boundary `github_lab_merge` registered and correctly reporting `UNVERIFIED`.
* Stage 4/5 remediation is complete and tested, and is independent of the lab —
  it does not need to be redone when the credential arrives.

---

## 10. Boundary status

| Boundary | Status | Reason |
| --- | --- | --- |
| `github_lab_merge` | **`UNVERIFIED`** | No lab exists. No live GitHub action performed. No bypass attempt executed. |

---

## 11. Attempts, bypass matrix, provider evidence

**None.** No live GitHub action of any kind has been performed under this
directive. The credential-ownership table required before testing is not
reproduced, because the architecture it describes has not been built.

---

## 12. Outcome so far

**BLOCKED — not PASS, not FAIL.**

The PASS sentence defined in the handoff is deliberately not stated anywhere in
this report, because zero protected-boundary attempts have been made and zero
bypass routes have been tested.

Real defects found and fixed (two confirmed pre-existing security defects:
fail-open authentication, and unbound caller-supplied identity). Those are
genuine progress on the engineering-priority list (items 2, 3, 4), but they are
*not* boundary verification and do not move `github_lab_merge` off `UNVERIFIED`.

Unresolved limitations:

* file-backed stores are single-writer MVP state (handoff gap #5) — restart
  behavior is covered by existing idempotency tests, concurrent-writer behavior
  is not tested;
* principal secrets are static bearer tokens with no rotation or expiry;
* `/health` discloses policy and adapter names;
* bubblewrap is same-UID rootless isolation, weaker than the preferred microVM;
  it would need to be documented as a limitation even once the credential exists;
* provider-level (GitHub-side) revocation remains untested and unclaimed
  (handoff gap #4).
