const ALVIRA_AUTH_URL = process.env.ALVIRA_AUTH_URL || 'https://alviratech.vercel.app'
const SESSION_COOKIE = 'ledgato_owner_session'

function parseCookies(header = '') {
  return Object.fromEntries(String(header).split(';').map(part => {
    const i = part.indexOf('=')
    if (i < 0) return ['', '']
    return [part.slice(0, i).trim(), decodeURIComponent(part.slice(i + 1).trim())]
  }).filter(([key]) => key))
}

function requestOrigin(req) {
  const host = String(req.headers['x-forwarded-host'] || req.headers.host || '')
  const proto = String(req.headers['x-forwarded-proto'] || 'https').split(',')[0]
  return host ? `${proto}://${host}` : ''
}

function publicApproval(item) {
  if (!item || typeof item !== 'object') return null
  if (item.version === 'ledgato.decision-prompt/v1') {
    return {
      id: item.decision_id,
      agent: item.agent,
      task_id: item.task_id || null,
      adapter: item.boundary?.adapter || null,
      action: {
        tool: item.requested_action?.tool,
        domain: item.requested_action?.resource,
        impact: item.requested_action?.impact,
        intent: item.requested_action?.intent || null,
      },
      requested_at: item.requested_at,
      requested_by: null,
      status: item.state,
      prompt: item,
    }
  }
  return {
    id: item.id,
    agent: item.agent,
    task_id: item.task_id || null,
    adapter: item.adapter,
    action: item.action || {},
    requested_at: item.requested_at,
    requested_by: item.requested_by || null,
    status: item.status,
    prompt: item.decision_prompt || null,
  }
}

function publicExecution(result) {
  if (!result || typeof result !== 'object') return null
  const verification = result.verification && typeof result.verification === 'object'
    ? {
        verified: Boolean(result.verification.verified),
        method: result.verification.method || null,
      }
    : null
  return {
    status: result.status || null,
    executed: Boolean(result.executed),
    paused: Boolean(result.paused),
    boundary_crossed: Boolean(result.boundary_crossed),
    verification,
    attestation_id: result.attestation_id || null,
  }
}

async function validateOwner(req) {
  const token = parseCookies(req.headers.cookie || '')[SESSION_COOKIE]
  if (!token) return { ok: false, status: 401, error: 'owner_session_required' }

  let response
  try {
    response = await fetch(new URL('/api/handoff/ledgato/session', ALVIRA_AUTH_URL), {
      method: 'POST',
      headers: { authorization: `Bearer ${token}` },
      cache: 'no-store',
    })
  } catch {
    return { ok: false, status: 503, error: 'owner_identity_unavailable' }
  }

  if (response.status === 401) return { ok: false, status: 401, error: 'owner_session_invalid' }
  if (!response.ok) return { ok: false, status: 503, error: 'owner_identity_unavailable' }

  const body = await response.json().catch(() => ({}))
  if (!body.authenticated || !body.owner?.id || !body.owner?.email) {
    return { ok: false, status: 401, error: 'owner_session_invalid' }
  }
  return { ok: true, owner: body.owner }
}

function engineConfig() {
  const base = String(process.env.LEDGATO_ENGINE_URL || '').trim()
  const token = String(process.env.LEDGATO_ENGINE_APPROVER_TOKEN || '').trim()
  const principal = String(process.env.LEDGATO_ENGINE_APPROVER_ID || '').trim()
  if (!base || !token || !principal) return null
  let url
  try { url = new URL(base) } catch { return null }
  if (!['http:', 'https:'].includes(url.protocol)) return null
  return { url, token, principal }
}

async function engineRequest(config, path, init = {}) {
  const url = new URL(path, config.url)
  const headers = {
    authorization: `Bearer ${config.token}`,
    ...(init.body ? { 'content-type': 'application/json' } : {}),
    ...(init.headers || {}),
  }
  return fetch(url, { ...init, headers, cache: 'no-store' })
}

function validApprovalId(value) {
  return typeof value === 'string' && /^approval_[A-Za-z0-9_-]{8,200}$/.test(value)
}

module.exports = async function handler(req, res) {
  res.setHeader('Cache-Control', 'private, no-store')

  if (req.method === 'POST') {
    const origin = String(req.headers.origin || '')
    const expected = requestOrigin(req)
    if (origin && expected && origin !== expected) {
      return res.status(403).json({ ok: false, error: 'origin_mismatch' })
    }
  }

  const owner = await validateOwner(req)
  if (!owner.ok) return res.status(owner.status).json({ ok: false, error: owner.error })

  const config = engineConfig()
  if (!config) return res.status(503).json({ ok: false, error: 'engine_control_not_configured' })

  if (req.method === 'GET') {
    let response
    try {
      response = await engineRequest(config, '/v1/decision-prompts?status=PENDING')
    } catch {
      return res.status(503).json({ ok: false, error: 'engine_unreachable' })
    }
    if (!response.ok) return res.status(502).json({ ok: false, error: 'engine_approval_read_failed' })
    const body = await response.json().catch(() => ({}))
    const approvals = Array.isArray(body.prompts) ? body.prompts.map(publicApproval).filter(Boolean) : []
    return res.status(200).json({
      ok: true,
      owner: { id: owner.owner.id, email: owner.owner.email },
      approvals,
    })
  }

  if (req.method !== 'POST') {
    res.setHeader('Allow', 'GET, POST')
    return res.status(405).json({ ok: false, error: 'method_not_allowed' })
  }

  const approvalId = req.body && req.body.approval_id
  const decision = req.body && req.body.decision
  if (!validApprovalId(approvalId) || !['allow_once', 'deny'].includes(decision)) {
    return res.status(400).json({ ok: false, error: 'invalid_decision_request' })
  }

  if (decision === 'deny') {
    let response
    try {
      response = await engineRequest(config, `/v1/approvals/${encodeURIComponent(approvalId)}/deny`, {
        method: 'POST',
        body: JSON.stringify({
          decided_by: config.principal,
          reason: 'Owner denied this contextual authority request from the Ledgato control room.',
        }),
      })
    } catch {
      return res.status(503).json({ ok: false, error: 'engine_unreachable' })
    }
    if (!response.ok) {
      const status = response.status === 404 ? 404 : response.status === 409 ? 409 : 502
      return res.status(status).json({ ok: false, error: 'deny_failed' })
    }
    const denied = await response.json().catch(() => ({}))
    return res.status(200).json({
      ok: true,
      decision: 'deny',
      approval: publicApproval(denied),
      execution: { status: 'DENY', executed: false, paused: false, boundary_crossed: false, verification: null, attestation_id: null },
    })
  }

  let response
  try {
    response = await engineRequest(config, `/v1/approvals/${encodeURIComponent(approvalId)}/approve-and-resume`, {
      method: 'POST',
      body: JSON.stringify({
        decided_by: config.principal,
        reason: 'Owner selected Allow once from the Ledgato control room.',
        jit_ttl_seconds: 60,
      }),
    })
  } catch {
    return res.status(503).json({ ok: false, error: 'engine_unreachable' })
  }

  if (!response.ok) {
    const status = response.status === 404 ? 404 : response.status === 409 ? 409 : 502
    return res.status(status).json({ ok: false, error: 'approve_and_resume_failed' })
  }

  const result = await response.json().catch(() => ({}))
  return res.status(200).json({
    ok: true,
    decision: 'allow_once',
    approval: publicApproval(result.approval),
    execution: publicExecution(result.execution),
  })
}
