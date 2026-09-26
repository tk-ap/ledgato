# Inline Decision Prompt contract

Status: implemented contract and engine projection.

## Product rule

Enforcement happens at the action. The owner decision should appear where the
owner already is. The Ledgato website is a control room, not a runtime switch.

A paused protected action creates one channel-neutral
`ledgato.decision-prompt/v1` object. Web, chat, TUI, Telegram, and future
clients render that same object.

The **approval remains the authority object**. The prompt is presentation only.

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
