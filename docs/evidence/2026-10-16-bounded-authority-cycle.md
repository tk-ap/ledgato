# Bounded authority-boundary evidence cycle — 2026-10-16

**Status: SOURCE REVIEW COMPLETE; NEW REGRESSION SUITE COMMITTED; EXECUTION AND INDEPENDENT RE-VERIFICATION PENDING.**

## Frozen reference
- Canonical Ledgato branch: `main` at review time; exact immutable reference for this cycle's addition: `8634a712b4293d2c7bdf3ee58627a29b27a430e3` (branch commit; parent pins the reviewed main).
- Agent OS: `tk-ap/agent-os` private, not checked out or executed in this session. No host integration or live deployment was changed.
- Existing independent provider-lab result: `INDEPENDENT_VERIFICATION_RESULT.md` (2026-09-08, historical `f960f10`); **not re-executed today**.
- Existing local two-process proof: `engine/examples/prove_enforcement_boundary.py`, documented in `engine/ENFORCEMENT_BOUNDARY_PROOF.md`; **not re-executed today**.

## Documented prior adversarial observations (historical, not newly reproduced)
- Without BLK-1 locking, a child grant was committed after parent revocation (142 microseconds); patch subsequently restored.
- Without BLK-2 vector-specific remediation matching, evidence for one attack vector could close another; patch subsequently restored.
- Independent live GitHub lab reported zero unauthorized merges across direct bypass, leakage, escalation and approval-abuse families; authoritative GitHub readback confirmed state.
- F-3: pluralized `deny_tools` and `approve_tools` once silently disabled gates. Current `engine/ledgato/models.py` has `_POLICY_KEYS`, `_validate_policy_keys`, and `_aliased_tool_set`; new regression tests pin those semantics.

## New deterministic fixture
`engine/tests/test_authority_config_regression.py`: five tests for denial alias, approval alias, unknown-key rejection, restrictive allow-alias intersection, and deny/approval-alias union.

### Reproduce locally (isolated checkout, no provider credentials)
```sh
git fetch origin evidence/2026-10-16-boundary-proof
git checkout 8634a712b4293d2c7bdf3ee58627a29b27a430e3
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e './engine[dev]'
python -m pytest -q engine/tests/test_authority_config_regression.py engine/tests/test_enforcement_boundary.py
python engine/examples/prove_enforcement_boundary.py
```
Do not supply GitHub production credentials or enable `LEDGATO_LIVE_TESTS`.

### Independent verification protocol
A reviewer who did not author or change this fixture must:
1. Check out the exact commit above and record `git rev-parse HEAD` and `git status --porcelain`.
2. Run the five regression tests and the existing two-process proof, recording counts and full raw logs.
3. Independently read the protected resource's persisted effects, rejected attempts and burned permits; verify DENY/APPROVE have zero effect and ALLOW exactly one.
4. Try direct no-permit, forged signature, re-targeted contract, replay (including after restart), identity spoofing and unavailable-Ledgato paths. Verify no new effects. Review any untested matrix entry as a gap, not a pass.
5. Audit alternate execution paths in Agent OS, especially credentials and `gh` subprocess paths. Until those are removed or bounded, no non-bypassability claim for the whole runtime.
6. Sign a separate report identifying reviewer, source SHA, execution environment, raw logs, outcomes and outstanding gaps. Reviewer independence is **not yet established** for this cycle.

## What can and cannot be claimed
- **Claim supported by existing records:** A lab GitHub merge boundary received historical independent verification, within the documented scope. A synthetic resource was previously reported to enforce one-use signed permits in a two-process lab.
- **Newly evidenced here:** The current policy parser source contains mitigation for the previously reported plural-key ambiguity, and dedicated regression tests have been committed.
- **Not evidenced here:** Successful execution of these new tests, a newly observed bypass, independent re-verification, a live AgentOS-to-Ledgato boundary, production safety or general protection from agent escapes.
- **Release decision:** **NO GO** for promoting enforcement maturity or expanding production authorization based on this cycle alone. Existing canonical maturity grades remain unchanged.

## Disclosure for BlueDot
Proposed work should independently challenge the remaining bypasses in a credential-separated Agent OS execution environment, publish failures and readback, and test whether authorization boundaries remain enforced after revocation, delegation and restart. This is a research hypothesis, not a certified product claim.


## Follow-up audit — 2026-10-16, CI and Agent OS source

### Execution evidence recovered
- GitHub Actions run [39002375596](https://github.com/tk-ap/ledgato/actions/runs/39002375596), `engine-tests` job 117307824421: **318 passed, 10 skipped, 1 warning** on Python 3.12. The suite includes `test_end_to_end_proof_across_processes_and_restart` and five new parser-regression tests, but the aggregate quiet-mode log does not show individual test names or resource effects.
- Same run, `github-denial-proof` job 117307824550: DENY of `github.pull.merge` for PR #100; `executed=false`, `boundary_crossed=false`; authenticated GitHub dual-signal readback returned unmerged with merge-status HTTP 404. This is a real-provider negative control, **not** proof of Agent OS credential isolation.
- Raw evidence is in CI logs and uploaded artifacts of that run. No independently executed resource-state audit occurred in this follow-up.

### Agent OS bypass-path audit
- Current private `tk-ap/agent-os` `runtime/executor.py` blob `ac7c229f55e13529ee5c704f485ebfd94c62263f` contains a direct `subprocess.run(["gh", "api", path])` helper for **read-only repository metadata/content calls**. This establishes direct GitHub CLI connectivity in that path, **not** that this helper can merge.
- Existing `docs/decisions/OWNER_INITIATED_AUTHORITY.md` records an intended `adapters.hermes.ledgato_merge` gate for merges, but a procedure document cannot prove worker credential custody or exclude other native API, subprocess, credential or inherited-session paths.
- No trusted inspection of the current host's `gh auth status`, environment, credential stores, subprocess capabilities, runner service identity, or GitHub effective permissions was performed. Therefore **cannot establish** that Agent OS lacks a merge-capable credential or equivalent bypass.
- The synthetic protected resource's persisted `resource.json` was not independently extracted from the CI artifact and read back in this session; the aggregate pytest green status is not the independent witness required for a higher maturity grade.

### Final bounded-cycle disposition
**PASS** for full CI suite and provider denial negative control. **INCONCLUSIVE / NOT VERIFIED** for fresh independent protected-resource readback and real Agent OS no-bypass claim. **NO GO** on promotion of runtime integration maturity. Keep the PR draft; do not activate or rotate any live credentials as part of this audit.
