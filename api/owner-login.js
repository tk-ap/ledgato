const crypto = require('node:crypto')

const ALVIRA_AUTH_URL = process.env.ALVIRA_AUTH_URL || 'https://alviratech.vercel.app'

function safeNext(value) {
  const raw = Array.isArray(value) ? value[0] : value
  return typeof raw === 'string' && raw.startsWith('/app') && !raw.startsWith('//') ? raw : '/app'
}

function cookie(name, value, maxAge) {
  return `${name}=${encodeURIComponent(value)}; Path=/api/auth/alvira; HttpOnly; Secure; SameSite=Lax; Max-Age=${maxAge}`
}

module.exports = function handler(req, res) {
  if (req.method !== 'GET') {
    res.setHeader('Allow', 'GET')
    return res.status(405).send('Method Not Allowed')
  }

  const verifier = crypto.randomBytes(32).toString('base64url')
  const challenge = crypto.createHash('sha256').update(verifier).digest('base64url')
  const state = crypto.randomBytes(24).toString('base64url')
  const next = safeNext(req.query && req.query.next)

  res.setHeader('Cache-Control', 'no-store')
  res.setHeader('Set-Cookie', [
    cookie('ledgato_auth_verifier', verifier, 300),
    cookie('ledgato_auth_state', state, 300),
  ])

  const start = new URL('/api/handoff/ledgato/start', ALVIRA_AUTH_URL)
  start.searchParams.set('challenge', challenge)
  start.searchParams.set('state', state)
  start.searchParams.set('next', next)
  res.statusCode = 302
  res.setHeader('Location', start.toString())
  return res.end()
}
