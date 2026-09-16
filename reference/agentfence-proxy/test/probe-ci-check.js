'use strict';

// Archived CI gate concept from AgentFence. Reference only.
// Known limitation: the original score path can treat downstream failure
// as a successful policy block. See ../README.md before reusing.

const path = require('node:path');
const fs = require('node:fs');
const { DownstreamClient } = require('../src/downstream-client');
const { ProxyServer } = require('../src/proxy-server');
const { EvidenceLog } = require('../src/evidence');

const ROOT = path.join(__dirname, '..');
const EVIDENCE_PATH = path.join(ROOT, 'logs', 'ci-probe-evidence.jsonl');
const SECRET = process.env.AGENTFENCE_SIGNING_SECRET || 'ci-secret';

function loadJson(p) {
  return JSON.parse(fs.readFileSync(p, 'utf8'));
}

async function main() {
  fs.rmSync(EVIDENCE_PATH, { force: true });

  const configDir = process.env.AGENTFENCE_CONFIG_DIR || path.join(ROOT, 'config');
  const serversConfig = loadJson(path.join(configDir, 'servers.json'));
  const policy = loadJson(path.join(configDir, 'policy.json'));
  const evidenceLog = new EvidenceLog(EVIDENCE_PATH, { secret: SECRET });

  const downstreams = new Map();
  for (const [name, cfg] of Object.entries(serversConfig.servers)) {
    downstreams.set(name, new DownstreamClient(name, cfg));
  }

  const proxyServer = new ProxyServer({ downstreams, policy, evidenceLog });
  const response = await proxyServer.handleMessage({
    jsonrpc: '2.0', id: 'ci-gate', method: 'agentfence/probe', params: {},
  });
  const scorecard = response.result;

  console.log(`Containment score: ${scorecard.containmentScore}% (${scorecard.caught}/${scorecard.attackProbes} attack probes caught)`);
  console.log(`Control probes: ${scorecard.controlProbes}, false positives: ${scorecard.falsePositives.length}`);

  const verification = EvidenceLog.verify(EVIDENCE_PATH, SECRET);
  console.log(`Evidence chain: ${verification.ok ? `intact (${verification.checked} records)` : `BROKEN — ${verification.error}`}`);

  for (const client of downstreams.values()) client.close();

  const pass = scorecard.missed.length === 0
    && scorecard.falsePositives.length === 0
    && verification.ok;
  process.exit(pass ? 0 : 1);
}

main().catch((err) => {
  console.error('probe-ci-check crashed:', err);
  process.exit(1);
});
