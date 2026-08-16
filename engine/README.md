# Ledgato — Engine

The working core of **Ledgato**: a release gate + signed-evidence layer for
agentic AI. This is the real product behind the landing page.

> *An unverified agent doesn't ship.*

## What it does

Ledgato maps what an agent can actually access, probes those boundaries with
adversarial attacks, and gates every release with **signed, tamper-evident
attestations**. If anything is out of scope, drifted, or unverified, the release
is blocked — with evidence.

- **Scope** — declare each agent's attack surface "as code" (`fence.yaml`):
  allow/deny tools, max impact, data domains.
- **Probe** — run an adversarial battery (scope escape, impact escalation,
  exfiltration, injection) against each policy.
- **Gate** — every release is approved only if every action is in scope, every
  probe holds, and the live map hasn't drifted.
- **Signed ledger** — every decision is written to an append-only,
  hash-chained, Ed25519-signed ledger. Altering any entry breaks its hash chain
  and signature. Designed for SOC 2 / ISO 27001 evidence.

## Fullest-MVP features

- **Proof-of-work** — every ledger entry is mined with a nonce so its block
  hash must begin with `difficulty` leading zeros. Rewriting history now costs
  real work on top of the signature chain: an attacker must re-sign *and*
  re-mine every block after a fork.
- **Distributed ledger** — independent nodes each hold a full copy of the chain
  and reconcile via **longest-valid-chain** consensus. A chain is only adopted
  if it fully verifies (hashes + signatures + proof-of-work); a tampered or
  shorter fork is rejected. Exposed over HTTP for real node gossip.
- **Attestation verification & ops** — verify a release's attestations in the
  live chain, or export a **self-contained verifiable report** that an auditor
  can check offline (recomputed hashes, signatures, and proof-of-work) without
  trusting any Ledgato server.

## Layout

```
ledgato/
  models.py       Policy / Action / scope parsing (fence.yaml)
  engine.py       real-time allow/deny evaluation + drift detection
  probes.py       adversarial probe simulator
  gate.py         release attestation (APPROVED / GATED)
  ledger.py       append-only hash-chained signed ledger (+ PoW mining)
  pow.py          proof-of-work: mine & verify block hashes
  distributed.py  Node + longest-valid-chain reconciliation
  attestation.py  release verification + verifiable report export/verify
  crypto.py       Ed25519 identity (sign / verify)
  cli.py          CLI (init, check, probe, attestation, ledger, status,
                  report, sync, api)
  api.py          FastAPI backend (/v1/...)
tests/            51 tests (engine, ledger, probes, gate, api, pow,
                  distributed, attestation)
```

## Install

```bash
cd ledgato-engine
pip install -e .[dev]     # or: pip install -r requirements
```

> **Note for S3-backed mounts:** if `import ledgato` hangs, export
> `PYTHONDONTWRITEBYTECODE=1` (the mount can't do the atomic write Python uses
> for `.pyc` caches). Not needed on normal disk.

## Quick start (CLI)

```bash
ledgato init --dir .            # scaffold fence.yaml + signing keys
ledgato check  --agent ops-agent --tool db.write --impact write   # DENY
ledgato probe  --agent ops-agent                                  # 6/6 held
ledgato attestation --agent ops-agent --release v2.4              # APPROVED (PoW mined)
ledgato attestation --agent researcher --release v2.4 --drift     # GATED (blocked)
ledgato ledger --ledger ledger.jsonl --keys keys                  # integrity OK
ledgato status --ledger ledger.jsonl                              # head + difficulty
ledgato report --agent ops-agent --release v2.4 --out report.json # export evidence
ledgato report --verify report.json                               # offline verify
ledgato sync --remote http://node:8000                            # distributed consensus
```

```
$ ledgato attestation --agent researcher --release v2.4 --drift
# gating release v2.4 · agent researcher · attack surface signed
[SIGN] docs.write   verified · attestation #54673433cf25
[SIGN] github.read  verified · attestation #4667be484b34
[DRIFT] researcher → scope_drift · map changed
[GATE ] release v2.4 BLOCKED · not re-verified + alert
[chain] ledger integrity: OK (11 entries, pow=2)
```

## API

```bash
ledgato api --port 8000
curl localhost:8000/health
curl -X POST localhost:8000/v1/actions/check \
  -d '{"agent":"ops-agent","action":{"tool":"db.write","impact":"write"}}'
curl -X POST localhost:8000/v1/releases/attest \
  -d '{"agent":"ops-agent","release":"v3.1","drift":true}'
curl -X POST localhost:8000/v1/ledger/verify
curl localhost:8000/v1/ledger/status
curl localhost:8000/v1/ledger/chain
curl -X POST localhost:8000/v1/ledger/reconcile \
  -d '{"chain":[]}'                                    # consensus with a peer chain
curl -X POST localhost:8000/v1/attestations/verify \
  -d '{"agent":"ops-agent","release":"v3.1"}'
curl -X POST localhost:8000/v1/attestations/report \
  -d '{"agent":"ops-agent","release":"v3.1"}'
```

Endpoints: `GET /health`, `POST /v1/actions/check`, `POST /v1/probes/run`,
`POST /v1/releases/attest`, `GET /v1/ledger`, `POST /v1/ledger/verify`,
`GET /v1/ledger/status`, `GET /v1/ledger/chain`,
`POST /v1/ledger/reconcile`, `POST /v1/attestations/verify`,
`POST /v1/attestations/report`, `POST /v1/attestations/report/verify`.

## Distributed ledger

Each node keeps a full signed, mined chain. To reconcile with a peer:

```bash
ledgato sync --remote http://peer:8000          # pull + longest-valid-chain
ledgato sync --file remote-chain.json           # reconcile from a JSON export
```

Consensus rule: a candidate chain is adopted only if it fully verifies and is
**at least as long** as the local chain. A valid-but-shorter chain is rejected
(local stays authoritative); an invalid chain is rejected outright. This is what
makes the evidence distributed — no single node can silently rewrite history.

## Test

```bash
cd ledgato-engine && python3 -m pytest tests/ -p no:cacheprovider
# 51 passed
```

## Examples

`examples/fence.yaml` is a two-agent example (ops-agent, researcher) that
mirrors the landing page.