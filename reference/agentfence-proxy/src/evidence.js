'use strict';

const fs = require('node:fs');
const crypto = require('node:crypto');

function sealRecord(body, prevHash, secret) {
  const sealed = { ...body, prevHash };
  const canonical = JSON.stringify(sealed);
  const recordHash = crypto.createHash('sha256').update(canonical).digest('hex');
  const signature = crypto.createHmac('sha256', secret).update(recordHash).digest('hex');
  return { ...sealed, recordHash, signature };
}

function verifyChain(records, secret) {
  let prevHash = '0'.repeat(64);
  for (let i = 0; i < records.length; i++) {
    const rec = records[i];
    const { recordHash, signature, ...body } = rec;
    if (body.prevHash !== prevHash) {
      return { ok: false, checked: i, error: `record ${i}: prevHash mismatch (chain broken)` };
    }
    const canonical = JSON.stringify(body);
    const expectedHash = crypto.createHash('sha256').update(canonical).digest('hex');
    if (expectedHash !== recordHash) {
      return { ok: false, checked: i, error: `record ${i}: hash mismatch (record altered)` };
    }
    const expectedSig = crypto.createHmac('sha256', secret).update(recordHash).digest('hex');
    if (expectedSig !== signature) {
      return { ok: false, checked: i, error: `record ${i}: signature invalid` };
    }
    prevHash = recordHash;
  }
  return { ok: true, checked: records.length };
}

class EvidenceLog {
  constructor(filePath, { secret }) {
    this.filePath = filePath;
    this.secret = secret;
    this.prevHash = this._loadLastHash();
  }

  _loadLastHash() {
    if (!fs.existsSync(this.filePath)) return '0'.repeat(64);
    const lines = fs.readFileSync(this.filePath, 'utf8').trim().split('\n').filter(Boolean);
    if (lines.length === 0) return '0'.repeat(64);
    const last = JSON.parse(lines[lines.length - 1]);
    return last.recordHash;
  }

  record(entry) {
    const record = sealRecord({ ts: new Date().toISOString(), ...entry }, this.prevHash, this.secret);
    fs.appendFileSync(this.filePath, JSON.stringify(record) + '\n');
    this.prevHash = record.recordHash;
    return record;
  }

  static verify(filePath, secret) {
    if (!fs.existsSync(filePath)) return { ok: true, checked: 0 };
    const lines = fs.readFileSync(filePath, 'utf8').trim().split('\n').filter(Boolean);
    return verifyChain(lines.map((l) => JSON.parse(l)), secret);
  }
}

class InMemoryEvidenceLog {
  constructor({ secret }) {
    this.secret = secret;
    this.prevHash = '0'.repeat(64);
    this.records = [];
  }

  record(entry) {
    const record = sealRecord({ ts: new Date().toISOString(), ...entry }, this.prevHash, this.secret);
    this.records.push(record);
    this.prevHash = record.recordHash;
    return record;
  }

  verify() {
    return verifyChain(this.records, this.secret);
  }
}

module.exports = { EvidenceLog, InMemoryEvidenceLog };
