const { configured, sessionFromRequest } = require('../lib/owner-auth')

function safeNext(value) {
  const path = Array.isArray(value) ? value[0] : value
  if (typeof path === 'string' && path.startsWith('/app') && !path.startsWith('//')) return path
  return '/app'
}

module.exports = async function handler(req, res) {
  res.setHeader('Cache-Control', 'private, no-store')

  const next = safeNext(req.query && req.query.next)
  if (!configured() || !sessionFromRequest(req)) {
    const login = new URL('/login', `https://${req.headers.host}`)
    login.searchParams.set('next', next)
    if (!configured()) login.searchParams.set('auth', 'unconfigured')
    res.statusCode = 302
    res.setHeader('Location', login.pathname + login.search)
    return res.end()
  }

  const proto = String(req.headers['x-forwarded-proto'] || 'https').split(',')[0]
  const host = String(req.headers['x-forwarded-host'] || req.headers.host)
  const indexResponse = await fetch(`${proto}://${host}/index.html`, {
    headers: { 'User-Agent': 'Ledgato owner app gate' },
    redirect: 'follow'
  })

  if (!indexResponse.ok) {
    return res.status(502).send('Owner workspace shell is unavailable.')
  }

  const html = await indexResponse.text()
  res.setHeader('Content-Type', 'text/html; charset=utf-8')
  return res.status(200).send(html)
}
