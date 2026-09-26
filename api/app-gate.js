const ALVIRA_AUTH_URL = process.env.ALVIRA_AUTH_URL || 'https://alviratech.vercel.app'
const SESSION_COOKIE = 'ledgato_owner_session'

function parseCookies(header = '') {
  return Object.fromEntries(String(header).split(';').map(part => {
    const i = part.indexOf('=')
    if (i < 0) return ['', '']
    return [part.slice(0, i).trim(), decodeURIComponent(part.slice(i + 1).trim())]
  }).filter(([key]) => key))
}

function safeNext(value) {
  const raw = Array.isArray(value) ? value[0] : value
  return typeof raw === 'string' && raw.startsWith('/app') && !raw.startsWith('//') ? raw : '/app'
}

function loginRedirect(res, next) {
  const location = `/login?next=${encodeURIComponent(next)}`
  res.statusCode = 302
  res.setHeader('Location', location)
  return res.end()
}

module.exports = async function handler(req, res) {
  res.setHeader('Cache-Control', 'private, no-store')
  const next = safeNext(req.query && req.query.next)
  const token = parseCookies(req.headers.cookie || '')[SESSION_COOKIE]
  if (!token) return loginRedirect(res, next)

  let session
  try {
    session = await fetch(new URL('/api/handoff/ledgato/session', ALVIRA_AUTH_URL), {
      method: 'POST',
      headers: { authorization: `Bearer ${token}` },
      cache: 'no-store',
    })
  } catch {
    return res.status(503).send('Owner session validation is temporarily unavailable.')
  }

  if (session.status === 401) {
    res.setHeader('Set-Cookie', `${SESSION_COOKIE}=; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=0`)
    return loginRedirect(res, next)
  }
  if (!session.ok) return res.status(503).send('Owner session validation is temporarily unavailable.')

  const host = String(req.headers['x-forwarded-host'] || req.headers.host || '')
  const proto = String(req.headers['x-forwarded-proto'] || 'https').split(',')[0]
  const headers = { 'user-agent': 'Ledgato owner app gate' }
  if (req.headers.cookie) headers.cookie = req.headers.cookie
  if (req.headers['x-vercel-protection-bypass']) headers['x-vercel-protection-bypass'] = req.headers['x-vercel-protection-bypass']

  let shell
  try {
    shell = await fetch(`${proto}://${host}/index.html`, { headers, cache: 'no-store' })
  } catch {
    return res.status(503).send('Owner workspace shell is unavailable.')
  }
  if (!shell.ok) return res.status(503).send('Owner workspace shell is unavailable.')

  res.statusCode = 200
  res.setHeader('Content-Type', 'text/html; charset=utf-8')
  return res.end(await shell.text())
}
