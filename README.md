# Ledgato

**The headless authorization service for Agent OS.**

Ledgato accepts capability manifests and authority requests from Agent OS, resolves what an agent may do, and returns an explicit allow, deny, or approval-required decision with signed evidence before any harness executes the work.

> *An unverified agent doesn't ship.*

## Why

Agentic systems fail silently. A tool access list, an endpoint, a data domain — any of it can drift between a security review and the next release. A one-time audit is a point-in-time snapshot; Ledgato is continuous.

## What it does

1. **Map** — Builds a versioned, reviewable attack-surface map of every tool, data domain, and endpoint each agent can reach.
2. **Probe & sign** — Runs adversarial probes against those boundaries and produces a signed attestation for every check.
3. **Gate the release** — Blocks anything unverified or drifted from reaching production. Every gate emits tamper-evident evidence.

## The engine (working MVP)

The real product lives in [`engine/`](./engine/) — a Python package (FastAPI backend + CLI) implementing the full release gate:

- **Scope as code** — each agent's attack surface declared in `fence.yaml` (allow/deny tools, max impact, data domains).
- **Adversarial probes** — a battery (scope escape, impact escalation, exfiltration, injection) that must all hold before a release ships.
- **Signed, proof-of-work ledger** — every decision is a mined block in an append-only, Ed25519-signed, hash-chained ledger. Rewriting history costs real work on top of the signatures.
- **Distributed ledger** — independent nodes reconcile via longest-valid-chain consensus, so no single node can silently rewrite the evidence.
- **Attestation verification & ops** — verify a release in the live chain, or export a self-contained verifiable report an auditor can check offline.

### Agent OS contract

`POST /v1/authority/resolve` is the primary headless integration. It accepts:

- an `authority_request` describing the requesting agent, intended actions, resources, and constraints;
- a `capability_manifest` describing the workforce and tools Agent OS proposes to use.

Ledgato verifies that both contracts describe the same work, checks the requested authority against `fence.yaml`, and returns an `authority-decision` containing:

- `allow`, `deny`, or `approval_required`;
- human-readable reasons;
- the number of action/resource paths evaluated;
- a signed, hash-chained ledger reference.

Canonical JSON Schemas live in [`contracts/`](./contracts/).

`GET /v1/authority/status/{work_id}` exposes only the resulting authorization state—`authorized`, `blocked`, or `awaiting_approval`—for AILHAT outcome and readiness tracking. It does not expose or accept portfolio priority.

### Quick start

```bash
cd engine
pip install -e .[dev]
ledgato init --dir .
ledgato attestation --agent ops-agent --release v2.4          # APPROVED (PoW-mined)
ledgato attestation --agent researcher --release v2.4 --drift # GATED (blocked)
ledgato report --agent ops-agent --release v2.4 --out report.json
ledgato report --verify report.json                          # offline verify
ledgato sync --remote http://peer:8000                        # distributed consensus
```

### API

```bash
ledgato api --port 8000
```

`/health` · `/v1/authority/resolve` · `/v1/actions/check` · `/v1/probes/run` · `/v1/releases/attest` ·
`/v1/ledger` (+ `status`, `chain`, `reconcile`) ·
`/v1/attestations/verify` · `/v1/attestations/report`

See [`/engine/README.md`](./engine/README.md) for full docs.

## Deployment

Ledgato runs as a proxy layer or via a lightweight SDK shim — your agents keep operating normally, with the gate sitting between them and the tools they call. It deploys in your infrastructure (VPC / on-prem) so scopes and data never leave your boundary.

---

The working product is the headless service in `/engine/`. The public page is explanatory; Agent OS and execution harnesses consume the service through contracts.
