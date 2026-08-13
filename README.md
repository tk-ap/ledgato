# Ledgato

**A release gate + signed-evidence layer for agentic AI.**

Ledgato maps what your AI agents can actually access, probes those boundaries with adversarial attacks, and gates every release with signed, tamper-evident attestations. If an agent isn't verified — or has drifted from its declared scope — Ledgato blocks it before it reaches production.

> *An unverified agent doesn't ship.*

## Why

Agentic systems fail silently. A tool access list, an endpoint, a data domain — any of it can drift between a security review and the next release. A one-time audit is a point-in-time snapshot; Ledgato is continuous.

## What it does

1. **Map** — Builds a versioned, reviewable attack-surface map of every tool, data domain, and endpoint each agent can reach.
2. **Probe & sign** — Runs adversarial probes against those boundaries and produces a signed attestation for every check.
3. **Gate the release** — Blocks anything unverified or drifted from reaching production. Every gate emits tamper-evident evidence.

## Deployment

Ledgato runs as a proxy layer or via a lightweight SDK shim — your agents keep operating normally, with the gate sitting between them and the tools they call. It deploys in your infrastructure (VPC / on-prem) so scopes and data never leave your boundary.

---

This repository hosts the public landing page for Ledgato (`index.html`).