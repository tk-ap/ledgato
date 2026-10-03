# Inline Decision Prompt contract

Status: implemented contract and engine projection.

## Product rule

Enforcement happens at the action. The owner decision should appear where the
owner already is. The Ledgato website is a control room, not a runtime switch.

A paused protected action creates one channel-neutral
`ledgato.decision-prompt/v1` object. Web, chat, TUI, Telegram, and future
clients render that same object.

The **approval remains the authority object**. The prompt is presentation only.

## Impact-aware approval-plane direction

The canonical approval plane is evolving to include the Impact Envelope defined in `IMPACT_ENVELOPE.md`.

This applies to **all** approval surfaces: web, Telegram, TUI, chat, mobile, and future clients.

Current implementation remains `ledgato.decision-prompt/v1`. Do not claim impact-aware approval is implemented merely because the v2 schema exists.

Migration target:

- `contracts/impact-envelope.schema.json` — advisory expected-impact context for the exact action;
- `contracts/decision-prompt-v2.schema.json` — channel-neutral prompt that binds the action digest and Impact Envelope digest.

V2 adds:

- direct create/modify/replace/delete/etc. classification;
- related dependency/workstream/authority/runtime/data/user/security impact;
- reversibility;
- novelty;
- explicit `KNOWN / INFERRED / UNKNOWN` confidence;
- an impact digest bound to the approval presentation.

A transport must not independently regenerate or reinterpret impact analysis. It renders the server-derived v2 semantics.

During migration, v1 and v2 may coexist. A boundary configured to require v2 must not silently downgrade to v1 because one transport has not upgraded.

## Default choices

- **Allow once** — approve and resume the exact stored action once. No standing
  rule is created.
- **Deny** — keep the action from executing and record the denial.
- **Why was this held?** — reveal reason, boundary, scope, consequence, and
  non-secret action facts. Inspection grants no authority.

## Exact-action binding

Every prompt carries a server-side `decision_id`, a `contract_digest` over
the exact pending approval binding, and a `parameters_digest` over exact
parameters even when values are hidden.

The client never submits replacement action parameters when approving. The
server resolves the stored approval and resumes that exact action.

## Display safety

At most six top-level scalar parameter facts are displayed. Keys containing
authorization, bearer, cookie, credential, key, password, secret, session, or
token are redacted. Structured values are omitted from display while remaining
covered by the digest.

## Engine API

Approver/admin principals may read:

```text
GET /v1/decision-prompts?status=PENDING
GET /v1/decision-prompts/{approval_id}
```

Authoritative mutations remain:

```text
POST /v1/approvals/{approval_id}/approve-and-resume
POST /v1/approvals/{approval_id}/deny
```

No client receives a resume token.

## Surface responsibility

Ledgato owns Decision Prompt semantics and the authoritative decision lifecycle.
Transport owners render/deliver it. Closing any UI must not weaken the
configured enforcement boundary.
