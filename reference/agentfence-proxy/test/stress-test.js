'use strict';

// Archived stress-test patterns from AgentFence. Reference only.
// These scenarios found two real prototype defects:
// 1) legitimate tools could be falsely reported unknown before tools/list
// 2) destroying oversized request sockets caused ECONNRESET instead of 413

const http = require('node:http');

function rawRequest(base, { method = 'POST', path = '/mcp', headers = {}, body }) {
  return new Promise((resolve, reject) => {
    const data = body === undefined ? undefined : (typeof body === 'string' ? body : JSON.stringify(body));
    const req = http.request(base + path, {
      method,
      headers: {
        'Content-Type': 'application/json',
        ...(data ? { 'Content-Length': Buffer.byteLength(data) } : {}),
        ...headers,
      },
    }, (res) => {
      const chunks = [];
      res.on('data', (c) => chunks.push(c));
      res.on('end', () => resolve({
        status: res.statusCode,
        headers: res.headers,
        body: Buffer.concat(chunks).toString('utf8'),
      }));
    });
    req.on('error', reject);
    if (data !== undefined) req.write(data);
    req.end();
  });
}

async function scenarioConcurrentSessions({ base, sessionIds, rpc }) {
  const calls = [
    { name: 'docs.search', arguments: { query: 'normal' }, expect: 'allowed' },
    { name: 'web.fetch', arguments: { url: 'https://docs.internal.example.com/x' }, expect: 'allowed' },
    { name: 'web.fetch', arguments: { url: 'https://exfil.example.net/' }, expect: 'blocked' },
    { name: 'web.upload', arguments: { url: 'https://x', data: 'y' }, expect: 'blocked' },
    { name: 'docs.write', arguments: { path: '/x', content: 'y' }, expect: 'blocked' },
  ];

  const results = [];
  await Promise.all(sessionIds.map(async (sid) => {
    await rpc(sid, { jsonrpc: '2.0', id: 0, method: 'tools/list', params: {} });
    for (const call of calls) {
      const response = await rpc(sid, {
        jsonrpc: '2.0',
        id: Math.floor(Math.random() * 1e9),
        method: 'tools/call',
        params: { name: call.name, arguments: call.arguments },
      });
      const blocked = !!(response.parsed && response.parsed.error);
      results.push({ expected: call.expect, blocked, name: call.name });
    }
  }));

  return results;
}

async function scenarioHostileInput({ base, sid, rpc }) {
  return [
    () => rawRequest(base, { headers: { 'Mcp-Session-Id': sid }, body: '{not json' }),
    () => rawRequest(base, { headers: { 'Mcp-Session-Id': sid }, body: '' }),
    () => rpc(sid, { jsonrpc: '2.0', id: 1, method: 'tools/call', params: { name: 'docs.search', arguments: { query: 'x'.repeat(1_500_000) } } }),
    () => rawRequest(base, { headers: { 'Mcp-Session-Id': sid }, body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'tools/call', params: { name: 'docs.search', arguments: { query: 'x'.repeat(3_000_000) } } }) }),
    () => rpc(sid, { jsonrpc: '1.0', id: 1, method: 'tools/call', params: {} }),
    () => rpc(sid, { jsonrpc: '2.0', id: 1, params: {} }),
    () => rpc(sid, { jsonrpc: '2.0', id: 1, method: 'tools/call', params: null }),
    () => rpc(sid, { jsonrpc: '2.0', id: 1, method: 'tools/call', params: { name: '../../etc/passwd', arguments: {} } }),
    () => rpc(sid, { jsonrpc: '2.0', id: 1, method: 'system/shutdown', params: {} }),
  ];
}

async function scenarioFlood({ sid, rpc, count = 300 }) {
  return Promise.all(Array.from({ length: count }, (_, i) => rpc(sid, {
    jsonrpc: '2.0',
    id: i,
    method: 'tools/call',
    params: { name: 'web.upload', arguments: { url: `https://x${i}`, data: 'y' } },
  })));
}

module.exports = {
  rawRequest,
  scenarioConcurrentSessions,
  scenarioHostileInput,
  scenarioFlood,
};
