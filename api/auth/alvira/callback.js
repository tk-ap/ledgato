const crypto = require('node:crypto')

const ALVIRA_AUTH_URL = process.env.ALVIRA_AUTH_URL || 'https://alviratech.vercel.app'
const SESSION_COOKIE = 'ledgato_owner_session'

function parseCookies(header = '') {
  return Object.fromEntries(String(header).split(';').map(part => {
    const i = part.indexOf('=')
    if (i < 0) return ['', '']
    return [part.slice(0, i).trim(), decodeURIComponent(part.slice(i + 1).trim())]
  }).filter(([key]) => key))
}

function safeEqual(a, b) {
  const left = Buffer.from(String(a || ''))
  const right = Buffer.from(String(b || ''))
  return left.length === right.length && crypto.timingSafeEqual(left, right)
}

function clearHandshakeCookies() {
  return [
    'ledgato_auth_verifier=; Path=/api/auth/alvira; HttpOnly; Secure; SameSite=Lax; Max-Age=0',
    'ledgato_auth_state=; Path=/api/auth/alvira; HttpOnly; Secure; SameSite=Lax; Max-Age=0',
  ]
}

module.exports = async function handler(req, res) {
  res.setHeader('Cache-Control', 'no-store')
  if (req.method !== 'GET') {
    res.setHeader('Allow', 'GET')
    return res.status(405).send('Method Not Allowed')
  }

  const token = String((req.query && req.query.token) || '').trim()
  const state = String((req.query && req.query.state) || '').trim()
  const cookies = parseCookies(req.headers.cookie || '')
  const verifier = cookies.ledgato_auth_verifier || ''
  const expectedState = cookies.ledgato_auth_state || ''

  if (!token || !verifier || !state || !safeEqual(state, expectedState)) {
    res.setHeader('Set-Cookie', clearHandshakeCookies())
    return res.status(401).send('Owner sign-in handoff was invalid. Return to /login and try again.')
  }

  let response
  try {
    response = await fetch(new URL('/api/handoff/ledgato/consume', ALVIRA_AUTH_URL), {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ token, verifier, state }),
      cache: 'no-store',
    })
  } catch {
    res.setHeader('Set-Cookie', clearHandshakeCookies())
    return res.status(503).send('Owner identity service is temporarily unavailable.')
  }

  if (!response.ok) {
    res.setHeader('Set-Cookie', clearHandshakeCookies())
    return res.status(401).send('Owner sign-in handoff expired or was already used. Return to /login and try again.')
  }

  const data = await response.json()
  const expiresAt = new Date(data.expiresAt).getTime()
  const maxAge = Number.isFinite(expiresAt) ? Math.max(60, Math.min(12 * 60 * 60, Math.floor((expiresAt - Date.now()) / 1000))) : 12 * 60 * 60
  const returnPath = typeof data.returnPath === 'string' && data.returnPath.startsWith('/app') && !data.returnPath.startsWith('//') ? data.returnPath : '/app'

  res.setHeader('Set-Cookie', [
    ...clearHandshakeCookies(),
    `${SESSION_COOKIE}=${encodeURIComponent(data.sessionToken)}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=${maxAge}`,
  ])
  res.statusCode = 302
  res.setHeader('Location', returnPath)
  return res.end()
}
