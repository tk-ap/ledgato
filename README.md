# Ledgato

**A release gate + signed-evidence layer for agentic AI.**

Ledgato maps what your AI agents can actually access, probes those boundaries with adversarial attacks, and gates every release with signed, tamper-evident attestations. If an agent isn't verified — or has drifted from its declared scope — Ledgato blocks it before it reaches production.

> *An unverified agent doesn't ship.*

> **Product direction:** the repository now records `khrystal — Execution Intelligence` as the working successor-brand direction, with pre-ship Review as the current wedge and Verify/Learn as later expansion. This is a direction note only; the operational/public product remains Ledgato until an explicit rename implementation is approved. See [`PRODUCT_DIRECTION.md`](./PRODUCT_DIRECTION.md).

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

`/health` · `/v1/actions/check` · `/v1/probes/run` · `/v1/releases/attest` ·
`/v1/ledger` (+ `status`, `chain`, `reconcile`) ·
`/v1/attestations/verify` · `/v1/attestations/report`

See [`/engine/README.md`](./engine/README.md) for full docs.

## Deployment

Ledgato runs as a proxy layer or via a lightweight SDK shim — your agents keep operating normally, with the gate sitting between them and the tools they call. It deploys in your infrastructure (VPC / on-prem) so scopes and data never leave your boundary.

---

This repository hosts the public landing page for Ledgato (`index.html`) and the working engine (`/engine/`).