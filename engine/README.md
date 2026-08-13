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

## Layout

```
ledgato/
  models.py      Policy / Action / scope parsing (fence.yaml)
  engine.py      real-time allow/deny evaluation + drift detection
  probes.py      adversarial probe simulator
  gate.py        release attestation (APPROVED / GATED)
  ledger.py      append-only hash-chained signed ledger
  crypto.py      Ed25519 identity (sign / verify)
  cli.py         CLI (init, check, probe, attestation, ledger, api)
  api.py         FastAPI backend (/v1/...)
tests/           31 tests (engine, ledger, probes, gate, api)
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
ledgato attestation --agent ops-agent --release v2.4              # APPROVED
ledgato attestation --agent researcher --release v2.4 --drift     # GATED (blocked)
ledgato ledger --ledger ledger.jsonl --keys keys                  # integrity OK
```

```
$ ledgato attestation --agent researcher --release v2.4 --drift
# gating release v2.4 · agent researcher · attack surface signed
[SIGN] docs.write   verified · attestation #54673433cf25
[SIGN] github.read  verified · attestation #4667be484b34
[DRIFT] researcher → scope_drift · map changed
[GATE ] release v2.4 BLOCKED · not re-verified + alert
[chain] ledger integrity: OK (11 entries)
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
```

Endpoints: `GET /health`, `POST /v1/actions/check`, `POST /v1/probes/run`,
`POST /v1/releases/attest`, `GET /v1/ledger`, `POST /v1/ledger/verify`.

## Test

```bash
cd ledgato-engine && python3 -m pytest tests/ -p no:cacheprovider
# 31 passed
```

## Run the tests / examples

`examples/fence.yaml` is a two-agent example (ops-agent, researcher) that
mirrors the landing page.