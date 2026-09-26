# Independent Verification Runbook — `github_lab_merge`

**You are an independent verifier. You did NOT write this code or its
remediations. Do not trust the executor's claims — reproduce them.** Your job is
to decide, on your own evidence, whether `github_lab_merge` may move from
`PARTIALLY_VERIFIED` to `VERIFIED`, and to record that decision. A clean pass is
not the goal; a correct verdict is.

Read `INDEPENDENT_VERIFICATION_HANDOFF.md` first for context, then work this
runbook. Where it says "confirm", actually run it — do not accept a prose claim.

---

## 0. Independence and canonical state

- [ ] You are a session distinct from the executor and did not author these
      fixes. If you cannot assert that, stop.
- [ ] Work against a clean checkout of `main`. Confirm it carries both blocker
      fixes:
      ```
      git show origin/main:engine/ledgato/authority.py | grep -c _validate_parent   # expect >=1
      git show origin/main:engine/ledgato/boundary.py  | grep -c resolves_vector     # expect >=1
      ```

## 1. Unit suite from scratch

- [ ] Fresh venv, install the engine, run the whole suite:
      ```
      python -m venv .venv && .venv/bin/pip install -e "engine[dev]"
      cd engine && ../.venv/bin/python -m pytest tests/ -q
      ```
- [ ] All pass, only the 4 `live` tests skipped. Note the count yourself.

## 2. Re-derive the two blocker fixes (do not trust them)

For EACH blocker, prove the regression fails without the fix:

- [ ] **Parent-revoke TOCTOU** — revert `engine/ledgato/authority.py` to the
      pre-fix shape (validation before the lock), run
      `tests/test_resume_race.py -k parent`. It MUST fail (a child issued at/after
      the parent's `revoked_at`). Restore the fix; it MUST pass.
- [ ] **Vector-bound remediation** — with the fix in place, confirm
      `test_unrelated_remediation_does_not_close_a_breach` passes and that
      removing the `vector`/`resolves_vector` matching in `unresolved_bypasses`
      makes it fail.

## 3. Falsify the VERIFIED gate (prove it cannot be fooled)

Using a scratch `BoundaryStore`, confirm the gate REFUSES `VERIFIED` when:

- [ ] only decisions/`provider_readback` are present (no adversarial families);
- [ ] only ONE attack family is present;
- [ ] all families present but NO `provider_readback` (fakes only);
- [ ] a recorded breach lacks same-vector remediation + clean retest.

If any of those is accepted as `VERIFIED`, STOP — the gate is unsound; record
`BYPASS_FOUND`-adjacent findings and do not promote.

## 4. Mint YOUR OWN lab credential (do not reuse the executor's)

The executor's token is revoked. Ask TK to mint a FRESH fine-grained PAT:
- repository access: ONLY `tk-ap/ledgato-enforcement-lab`
- permissions: Contents R/W, Pull requests R/W, Administration R/W
- short expiry
Have TK place it at a path only you read; never print it; never commit it.

Confirm scope yourself before use:
```
curl -sS -o /dev/null -w "%{http_code}\n" -H "Authorization: Bearer $TOK" \
  https://api.github.com/repos/tk-ap/ledgato-enforcement-lab            # 200
for r in ledgato ailhat ALVIRA agent-os; do
  curl -sS -o /dev/null -w "$r %{http_code}\n" -H "Authorization: Bearer $TOK" \
    https://api.github.com/repos/tk-ap/$r/collaborators; done            # 403 each
```

## 5. Live suite (the only provider-backed evidence)

- [ ] Point the opt-in suite at the preserved lab and run it:
      ```
      LEDGATO_LIVE_TESTS=1 LEDGATO_GITHUB_TOKEN=$TOK \
      LEDGATO_GITHUB_REPOSITORY=tk-ap/ledgato-enforcement-lab \
      LEDGATO_LAB_PR_NUMBER=1 \
      .venv/bin/python -m pytest engine/tests/test_live_github.py -v
      ```
- [ ] Denial passes; GitHub independently shows PR #1 still `OPEN`, never merged.

## 6. Re-run the four families against the live gateway

- [ ] Stand up the gateway (holds YOUR token, not the executor's):
      ```
      LEDGATO_GITHUB_TOKEN=$TOK \
      LEDGATO_GITHUB_REPOSITORY=tk-ap/ledgato-enforcement-lab \
      LAB_AGENT_SECRET=... LAB_APPROVER_SECRET=... LAB_ADMIN_SECRET=... \
      PYTHONPATH=engine python lab/gateway-serve.py &
      ```
- [ ] Run each family from inside the sandbox and confirm ZERO unauthorized
      merges (`lab/sandbox.sh` + `lab/direct-bypass-attack.sh`,
      `lab/leakage-attack.sh`, `lab/escalation-attack.sh`).
- [ ] For the approval family, use `lab/fence-approve.yaml`, a throwaway PR into
      an unprotected base, and confirm: agent self-approve → 403; human approves;
      resume merges once; replay refused; exactly one merge commit.
- [ ] After each, verify the CLAIM against GitHub directly, not the gateway's
      own report.

## 7. Weigh the limitations

- [ ] Read §6 of the handoff. Decide whether each residual limitation is
      acceptable for the scope you are verifying, or must be closed first.
      Record your decision per item.

## 8. Record the verdict

Only if EVERYTHING above holds and you accept the limitations:
```
store.set_status("github_lab_merge", "VERIFIED",
    attested_by="<your reviewer id>",
    justification="independently re-ran the full live suite and all four "
                  "families against a freshly minted lab credential; zero "
                  "unauthorized merges; one authorized merge verified; gate "
                  "falsification confirmed; limitations accepted")
```
The gate will refuse unless all four families + a `provider_readback` are present
with no unresolved breach.

If anything fails: record the specific failure, set the status honestly
(`BYPASS_FOUND` if a real bypass, otherwise leave `PARTIALLY_VERIFIED`), and do
NOT promote. Report back to TK either way.

## 9. Cleanup (only after the verdict is recorded)

- [ ] Have TK revoke the fresh lab token.
- [ ] TK may then delete `tk-ap/ledgato-enforcement-lab`.
- [ ] Do not delete anything before the verdict is recorded.

---

`VERIFIED` means verified against this documented attack suite and lab
architecture — not universal impossibility of bypass.
