'use strict';

const http = require('node:http');
const crypto = require('node:crypto');

const MAX_BODY_BYTES = 2 * 1024 * 1024;

class HttpTransport {
  constructor(proxyServer, {
    port = 8787,
    allowedOrigins = null,
    bearerToken = null,
  } = {}) {
    this.proxyServer = proxyServer;
    this.port = port;
    this.allowedOrigins = allowedOrigins;
    this.bearerToken = bearerToken;
    this.sessions = new Map();
    this.server = http.createServer((req, res) => this._handleRequest(req, res));
  }

  listen() {
    return new Promise((resolve) => this.server.listen(this.port, () => resolve(this)));
  }

  close() {
    return new Promise((resolve) => this.server.close(() => resolve()));
  }

  _checkOrigin(req) {
    if (!this.allowedOrigins) return true;
    const origin = req.headers.origin;
    if (!origin) return true;
    return this.allowedOrigins.includes(origin);
  }

  _checkAuth(req) {
    if (!this.bearerToken) return true;
    const header = req.headers.authorization || '';
    return header === `Bearer ${this.bearerToken}`;
  }

  _readBody(req) {
    return new Promise((resolve, reject) => {
      let size = 0;
      let oversize = false;
      const chunks = [];
      req.on('data', (chunk) => {
        size += chunk.length;
        if (size > MAX_BODY_BYTES) {
          // Preserve the stress-test fix: stop retaining bytes but drain
          // the request rather than destroying the socket mid-write.
          // Destroying immediately produced ECONNRESET instead of a clean 413.
          oversize = true;
          return;
        }
        chunks.push(chunk);
      });
      req.on('end', () => {
        if (oversize) reject(Object.assign(new Error('payload too large'), { statusCode: 413 }));
        else resolve(Buffer.concat(chunks).toString('utf8'));
      });
      req.on('error', reject);
    });
  }

  async _handleRequest(req, res) {
    const url = new URL(req.url, `http://${req.headers.host}`);

    if (url.pathname === '/' || url.pathname === '/healthz') {
      res.writeHead(200, { 'Content-Type': 'application/json' })
        .end(JSON.stringify({ status: 'ok', service: 'agentfence-proxy' }));
      return;
    }

    if (url.pathname !== '/mcp') {
      res.writeHead(404).end();
      return;
    }

    if (!this._checkOrigin(req)) {
      res.writeHead(403, { 'Content-Type': 'application/json' }).end(JSON.stringify({ error: 'origin not allowed' }));
      return;
    }
    if (!this._checkAuth(req)) {
      res.writeHead(401, { 'Content-Type': 'application/json' }).end(JSON.stringify({ error: 'unauthorized' }));
      return;
    }

    if (req.method === 'POST') return this._handlePost(req, res);
    if (req.method === 'GET') {
      res.writeHead(405, { Allow: 'POST' }).end();
      return;
    }
    if (req.method === 'DELETE') {
      const sid = req.headers['mcp-session-id'];
      if (sid) this.sessions.delete(sid);
      res.writeHead(204).end();
      return;
    }

    res.writeHead(405, { Allow: 'POST, GET, DELETE' }).end();
  }

  async _handlePost(req, res) {
    let bodyText;
    try {
      bodyText = await this._readBody(req);
    } catch (err) {
      res.writeHead(err.statusCode || 400, { 'Content-Type': 'application/json' })
        .end(JSON.stringify({ error: err.message }));
      return;
    }

    let parsed;
    try {
      parsed = JSON.parse(bodyText);
    } catch {
      res.writeHead(400, { 'Content-Type': 'application/json' })
        .end(JSON.stringify({ jsonrpc: '2.0', id: null, error: { code: -32700, message: 'invalid JSON' } }));
      return;
    }

    const messages = Array.isArray(parsed) ? parsed : [parsed];
    if (messages.length === 0) {
      res.writeHead(400, { 'Content-Type': 'application/json' }).end(JSON.stringify({ error: 'empty batch' }));
      return;
    }

    const isInitialize = messages.some((m) => m && m.method === 'initialize');
    let sessionId = req.headers['mcp-session-id'];

    if (isInitialize) {
      sessionId = crypto.randomUUID();
      this.sessions.set(sessionId, { createdAt: Date.now() });
    } else if (this.sessions.size > 0) {
      if (!sessionId || !this.sessions.has(sessionId)) {
        res.writeHead(400, { 'Content-Type': 'application/json' })
          .end(JSON.stringify({ error: 'missing or unknown Mcp-Session-Id' }));
        return;
      }
    }

    const responses = [];
    for (const msg of messages) {
      let response;
      try {
        response = await this.proxyServer.handleMessage(msg);
      } catch (err) {
        response = { jsonrpc: '2.0', id: msg && msg.id, error: { code: -32000, message: err.message } };
      }
      if (response) responses.push(response);
    }

    const headers = { 'Content-Type': 'application/json' };
    if (sessionId) headers['Mcp-Session-Id'] = sessionId;

    if (responses.length === 0) {
      res.writeHead(202, headers).end();
      return;
    }

    const payload = Array.isArray(parsed) ? responses : responses[0];
    const accept = req.headers.accept || '';
    if (accept.includes('text/event-stream') && !accept.includes('application/json')) {
      res.writeHead(200, { ...headers, 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache' });
      res.write(`data: ${JSON.stringify(payload)}\n\n`);
      res.end();
      return;
    }

    res.writeHead(200, headers).end(JSON.stringify(payload));
  }
}

module.exports = { HttpTransport };
