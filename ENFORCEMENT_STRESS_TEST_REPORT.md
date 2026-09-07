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

## 5. Boundary status

| Boundary | Status | Reason |
| --- | --- | --- |
| `github_lab_merge` | `UNVERIFIED` | No boundary record implemented yet; no lab; no live provider test run |

---

## 6. Environment capability assessment (Stage 3 pre-check)

Recorded before building the lab, because it constrains what can be proven here.

| Capability | Result |
| --- | --- |
| `docker` binary | present (29.7.2) |
| docker daemon | **unusable** — `permission denied` on `/var/run/docker.sock`; user `tk` is in `tk,wheel`, not `docker` |
| `podman` / `lxc` | absent |
| `systemd-nspawn` | present (requires root) |
| `bwrap` (bubblewrap) | **present and working rootless** |
| `unshare` | present |
| `gh` CLI | 2.100.0, authenticated as `tk-ap`, scopes `delete_repo, gist, read:org, repo, workflow` |

Bubblewrap isolation was smoke-tested: a sandbox built with `--unshare-all
--share-net`, a `tmpfs` `/home`, and no bind of `~/.config` could not see the
host's `gh` credential directory.

**Material constraint on the whole exercise:** the shell executing this directive
holds a **merge-capable** GitHub token (`repo` scope on account `tk-ap`, and that
account owns production repositories). This shell therefore can never serve as
the agent sandbox, and the host `gho_` token must never be used as the
"Ledgato-held credential" — it is broad, it reaches production repos, and using
it would violate base-directive safety boundaries 1 and 7.

---

## 7. Attempts, bypass matrix, provider evidence

Not started. No live GitHub action of any kind has been performed under this
directive.

---

## 8. Open blockers

See section 9 of this report as it is updated. Current blocker is recorded in the
session hand-back: a scoped, disposable GitHub credential must exist before
Stage 6 can run, and only TK can mint one.
