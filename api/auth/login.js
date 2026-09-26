const {
  configured,
  credentialsMatch,
  createSessionToken,
  sessionCookie
} = require('../../lib/owner-auth')

module.exports = async function handler(req, res) {
  res.setHeader('Cache-Control', 'no-store')

  if (req.method !== 'POST') {
    res.setHeader('Allow', 'POST')
    return res.status(405).json({ ok: false, error: 'method_not_allowed' })
  }

  if (!configured()) {
    return res.status(503).json({ ok: false, error: 'owner_auth_not_configured' })
  }

  const body = typeof req.body === 'string' ? JSON.parse(req.body || '{}') : (req.body || {})
  if (!credentialsMatch(body.email, body.password)) {
    return res.status(401).json({ ok: false, error: 'invalid_credentials' })
  }

  const token = createSessionToken()
  res.setHeader('Set-Cookie', sessionCookie(token))
  return res.status(200).json({ ok: true })
}
