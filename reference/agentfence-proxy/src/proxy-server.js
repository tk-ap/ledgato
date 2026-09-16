'use strict';

const { attachReader, writeMessage } = require('./jsonrpc');
const { evaluateCall, diffPermissions } = require('./policy');
const { buildProbes, scoreResults } = require('./prober');

class ProxyServer {
  constructor({ downstreams, policy, evidenceLog }) {
    this.downstreams = downstreams;
    this.policy = policy;
    this.evidenceLog = evidenceLog;
    this.toolIndex = new Map();
  }

  attachStdio(input, output) {
    attachReader(input, (msg) => {
      this.handleMessage(msg)
        .then((res) => { if (res) writeMessage(output, res); })
        .catch((err) => writeMessage(output, this._errorEnvelope(msg && msg.id, -32000, err.message)));
    });
  }

  _okEnvelope(id, result) {
    return { jsonrpc: '2.0', id, result };
  }

  _errorEnvelope(id, code, message) {
    return { jsonrpc: '2.0', id, error: { code, message } };
  }

  async _listAllTools() {
    const liveToolsByServer = {};
    const flatTools = [];
    for (const [serverName, client] of this.downstreams.entries()) {
      const result = await client.request('tools/list', {});
      const tools = (result && result.tools) || [];
      liveToolsByServer[serverName] = tools.map((t) => t.name);
      const declaredTools = new Set((this.policy.declaredTools || {})[serverName] || []);
      for (const t of tools) {
        flatTools.push({
          name: `${serverName}.${t.name}`,
          description: t.description,
          inputSchema: t.inputSchema,
          _agentfence: { server: serverName, declared: declaredTools.has(t.name) },
        });
        this.toolIndex.set(`${serverName}.${t.name}`, { server: serverName, tool: t.name });
      }
    }
    return { flatTools, liveToolsByServer };
  }

  async handleMessage(msg) {
    if (!msg || typeof msg !== 'object' || msg.jsonrpc !== '2.0' || !msg.method) {
      return this._errorEnvelope(msg && msg.id, -32600, 'invalid JSON-RPC request');
    }

    const hasId = msg.id !== undefined && msg.id !== null;

    if (msg.method === 'notifications/initialized') return null;

    if (msg.method === 'initialize') {
      return this._okEnvelope(msg.id, {
        protocolVersion: '2025-03-26',
        serverInfo: { name: 'agentfence-proxy', version: '0.2.0' },
        capabilities: { tools: {} },
      });
    }

    if (msg.method === 'tools/list') {
      const { flatTools } = await this._listAllTools();
      return this._okEnvelope(msg.id, { tools: flatTools });
    }

    if (msg.method === 'agentfence/drift') {
      const { liveToolsByServer } = await this._listAllTools();
      const drift = diffPermissions(this.policy, liveToolsByServer);
      return this._okEnvelope(msg.id, { drift, checkedAt: new Date().toISOString() });
    }

    if (msg.method === 'agentfence/probe') {
      const scorecard = await this.runProbeBattery();
      return this._okEnvelope(msg.id, scorecard);
    }

    if (msg.method === 'tools/call') return this._handleToolCall(msg, 'agent');

    if (!hasId) return null;
    return this._errorEnvelope(msg.id, -32601, `method not found: ${msg.method}`);
  }

  async _handleToolCall(msg, source = 'agent', evidenceLogOverride = null) {
    const evidenceLog = evidenceLogOverride || this.evidenceLog;
    const flatName = msg.params && msg.params.name;
    const args = (msg.params && msg.params.arguments) || {};
    let entry = this.toolIndex.get(flatName);

    if (!entry) {
      await this._listAllTools();
      entry = this.toolIndex.get(flatName);
    }

    if (!entry) {
      const record = evidenceLog.record({
        decision: 'blocked',
        source,
        ruleId: 'unknown-tool',
        tool: flatName,
        args,
        reason: `"${flatName}" is not a known tool on any connected server.`,
      });
      return this._errorEnvelope(msg.id, -32001, `blocked by AgentFence [${record.recordHash.slice(0, 12)}]: unknown tool`);
    }

    const { server, tool } = entry;
    const decision = evaluateCall(this.policy, { server, tool, args });

    if (!decision.allowed) {
      const record = evidenceLog.record({
        decision: 'blocked',
        source,
        ruleId: decision.ruleId,
        server,
        tool,
        args,
        reason: decision.reason,
      });
      return this._errorEnvelope(msg.id, -32001, `blocked by AgentFence [${record.recordHash.slice(0, 12)}]: ${decision.reason}`);
    }

    const client = this.downstreams.get(server);
    try {
      const result = await client.request('tools/call', { name: tool, arguments: args });
      evidenceLog.record({ decision: 'allowed', source, server, tool, args });
      return this._okEnvelope(msg.id, result);
    } catch (err) {
      evidenceLog.record({ decision: 'error', source, server, tool, args, reason: err.message });
      return this._errorEnvelope(msg.id, -32002, `downstream error: ${err.message}`);
    }
  }

  async getPermissionsSnapshot() {
    const { liveToolsByServer } = await this._listAllTools();
    const drift = diffPermissions(this.policy, liveToolsByServer);
    return { liveToolsByServer, drift };
  }

  async runProbeBattery({ evidenceLog: evidenceLogOverride } = {}) {
    const evidenceLog = evidenceLogOverride || this.evidenceLog;
    const { liveToolsByServer, drift } = await this.getPermissionsSnapshot();
    const probes = buildProbes(this.policy, liveToolsByServer, drift);

    const results = [];
    for (const probe of probes) {
      const syntheticMsg = {
        jsonrpc: '2.0',
        id: `probe:${probe.id}`,
        method: 'tools/call',
        params: { name: probe.name, arguments: probe.arguments },
      };
      const response = await this._handleToolCall(syntheticMsg, 'probe', evidenceLog);
      // Known flaw retained from prototype: any JSON-RPC error is counted
      // as "blocked", including downstream failure after policy allowance.
      results.push({ ...probe, actualBlocked: !!response.error });
    }

    const scorecard = scoreResults(results);
    evidenceLog.record({
      decision: 'probe-run-complete',
      source: 'probe',
      containmentScore: scorecard.containmentScore,
      attackProbes: scorecard.attackProbes,
      caught: scorecard.caught,
      missedCount: scorecard.missed.length,
      falsePositiveCount: scorecard.falsePositives.length,
    });

    return { ...scorecard, runAt: new Date().toISOString(), probesRun: probes.length };
  }

  async runSingleProbe(probeId, { evidenceLog: evidenceLogOverride } = {}) {
    const evidenceLog = evidenceLogOverride || this.evidenceLog;
    const { liveToolsByServer, drift } = await this.getPermissionsSnapshot();
    const probes = buildProbes(this.policy, liveToolsByServer, drift);
    const probe = probes.find((p) => p.id === probeId);
    if (!probe) return null;

    const syntheticMsg = {
      jsonrpc: '2.0',
      id: `probe:${probe.id}`,
      method: 'tools/call',
      params: { name: probe.name, arguments: probe.arguments },
    };
    const response = await this._handleToolCall(syntheticMsg, 'probe', evidenceLog);
    const actualBlocked = !!response.error;
    return {
      ...probe,
      actualBlocked,
      verdict: probe.expectBlocked === actualBlocked ? 'as-expected' : (actualBlocked ? 'false-positive' : 'MISSED'),
      decisionMessage: actualBlocked ? response.error.message : 'call was allowed through to the downstream tool',
    };
  }
}

module.exports = { ProxyServer };
