# AgentFence Proxy — archived implementation reference

Status: **reference only — not active LEDGATo runtime code**

This directory preserves the high-signal implementation artifacts from the retired `tk-ap/agentfence-proxy` repository so that repository can be deleted without losing useful prior work.

Source provenance:

- original repository: `tk-ap/agentfence-proxy`
- original branch: `main`
- original commit: `e494bf3622d8c4bda571a94e60a777f361a1bdd1`
- source subtree: `agentfence-proxy 2/`
- preserved into LEDGATo: 2026-09-15

## Why this lives here

AgentOS already absorbed the durable architecture requirements around capacity, policy verification, evidence claims, and control probes. The executable ideas in this prototype are more directly relevant to LEDGATo's enforcement/gateway path, so the surviving source belongs here rather than in AgentOS runtime code.

Nothing under `reference/agentfence-proxy/` is imported by `engine/`, packaged, deployed, or treated as production evidence.

## Preserved source

- `src/policy.js` — declared-vs-effective permission drift and argument-level constraints, including the path-normalization fix that caught a real traversal bypass.
- `src/prober.js` — policy-derived hostile probes plus legitimate control calls.
- `src/proxy-server.js` — transport-agnostic interception path showing `tools/list`, `tools/call`, drift, probe execution, forwarding, and decision logging.
- `src/evidence.js` — the prototype's hash-chain/HMAC evidence mechanism, preserved primarily as a design reference and caution.
- `src/http-transport.js` — MCP Streamable HTTP/session/origin/body-limit handling and the clean-413 fix discovered under stress.
- `test/probe-ci-check.js` — the original CI enforcement gate concept.
- `test/stress-test.js` — concurrency, hostile-input, flood, and transport robustness scenarios.

## Known limitations — do not inherit silently

### Probe scoring bug

The preserved `proxy-server.js` marks any JSON-RPC error returned from `_handleToolCall()` as `actualBlocked`. That means a call which **passed policy but failed downstream** can be misclassified as a successful policy block.

Any future LEDGATo implementation must distinguish at least:

- `policy_denied`
- `policy_gated`
- `policy_allowed_completed`
- `policy_allowed_downstream_failed`
- `inconclusive`

A legitimate allowed control call is required; rejecting or failing everything is not proof of enforcement.

### Hash-chain completeness blind spot

The preserved `evidence.js` can detect mutation or deletion **inside the retained chain**, but an unanchored forward hash chain cannot prove that final records were not removed. Deleting a suffix leaves the surviving prefix internally consistent.

Do not reuse the old claim that this mechanism proves that "nothing was removed." Detecting tail deletion requires an external terminal commitment/anchor or another independent completeness witness.

### Prototype boundaries

This code was a scaffold, not a production gateway. It lacks the full authorization, approval/resume, revocation, post-action verification, SDK/native adapter, distributed-state, and production signing requirements of LEDGATo.

## What was intentionally not preserved

The old repository also contained duplicated root files, a ZIP copy, public marketing-demo API code, Render deployment configuration, mock servers, package scaffolding, and generic JSON-RPC/downstream-process plumbing. Those artifacts are not unique enough to justify carrying forward and should not become accidental dependencies.

## Reuse rule

Treat this directory as prior art. If a concept is reused, port the idea into owned LEDGATo code with current contracts and tests rather than importing this directory into runtime.
