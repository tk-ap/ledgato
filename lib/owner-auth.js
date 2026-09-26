const crypto = require('node:crypto')

const COOKIE_NAME = 'ledgato_owner'
const SESSION_TTL_SECONDS = 12 * 60 * 60

function configured() {
  const email = process.env.LEDGATO_OWNER_EMAIL || ''
  const passwordHash = process.env.LEDGATO_OWNER_PASSWORD_SHA256 || ''
  const sessionSecret = process.env.LEDGATO_SESSION_SECRET || ''
  return Boolean(email && /^[a-f0-9]{64}$/i.test(passwordHash) && sessionSecret.length >= 32)
}

function ownerEmail() {
  return (process.env.LEDGATO_OWNER_EMAIL || '').trim().toLowerCase()
}

function hashPassword(password) {
  return crypto.createHash('sha256').update(String(password || ''), 'utf8').digest('hex')
}

function constantTimeHexEqual(left, right) {
  if (!/^[a-f0-9]{64}$/i.test(left || '') || !/^[a-f0-9]{64}$/i.test(right || '')) return false
  return crypto.timingSafeEqual(Buffer.from(left, 'hex'), Buffer.from(right, 'hex'))
}

function credentialsMatch(email, password) {
  if (!configured()) return false
  const emailMatches = String(email || '').trim().toLowerCase() === ownerEmail()
  return emailMatches && constantTimeHexEqual(hashPassword(password), process.env.LEDGATO_OWNER_PASSWORD_SHA256)
}

function sign(payload) {
  return crypto.createHmac('sha256', process.env.LEDGATO_SESSION_SECRET).update(payload).digest('base64url')
}

function createSessionToken() {
  if (!configured()) throw new Error('owner auth is not configured')
  const payload = Buffer.from(JSON.stringify({
    sub: ownerEmail(),
    exp: Math.floor(Date.now() / 1000) + SESSION_TTL_SECONDS
  })).toString('base64url')
  return `${payload}.${sign(payload)}`
}

function verifySessionToken(token) {
  if (!configured() || typeof token !== 'string') return null
  const [payload, signature, extra] = token.split('.')
  if (!payload || !signature || extra) return null
  const expected = sign(payload)
  const a = Buffer.from(signature)
  const b = Buffer.from(expected)
  if (a.length !== b.length || !crypto.timingSafeEqual(a, b)) return null

  try {
    const decoded = JSON.parse(Buffer.from(payload, 'base64url').toString('utf8'))
    if (decoded.sub !== ownerEmail()) return null
    if (!Number.isFinite(decoded.exp) || decoded.exp <= Math.floor(Date.now() / 1000)) return null
    return decoded
  } catch {
    return null
  }
}

function parseCookies(header = '') {
  return Object.fromEntries(
    String(header).split(';').map(part => {
      const index = part.indexOf('=')
      if (index < 0) return ['', '']
      return [part.slice(0, index).trim(), decodeURIComponent(part.slice(index + 1).trim())]
    }).filter(([key]) => key)
  )
}

function sessionFromRequest(req) {
  const cookies = parseCookies(req.headers.cookie || '')
  return verifySessionToken(cookies[COOKIE_NAME])
}

function sessionCookie(token) {
  return `${COOKIE_NAME}=${encodeURIComponent(token)}; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=${SESSION_TTL_SECONDS}`
}

function clearSessionCookie() {
  return `${COOKIE_NAME}=; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=0`
}

module.exports = {
  COOKIE_NAME,
  configured,
  credentialsMatch,
  createSessionToken,
  sessionFromRequest,
  sessionCookie,
  clearSessionCookie
}
