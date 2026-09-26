const ALVIRA_AUTH_URL = process.env.ALVIRA_AUTH_URL || 'https://alviratech.vercel.app'
const SESSION_COOKIE = 'ledgato_owner_session'

function parseCookies(header = '') {
  return Object.fromEntries(String(header).split(';').map(part => {
    const i = part.indexOf('=')
    if (i < 0) return ['', '']
    return [part.slice(0, i).trim(), decodeURIComponent(part.slice(i + 1).trim())]
  }).filter(([key]) => key))
}

module.exports = async function handler(req, res) {
  res.setHeader('Cache-Control', 'no-store')
  if (req.method !== 'POST') {
    res.setHeader('Allow', 'POST')
    return res.status(405).json({ ok: false, error: 'method_not_allowed' })
  }
  const token = parseCookies(req.headers.cookie || '')[SESSION_COOKIE]
  if (token) {
    try {
      await fetch(new URL('/api/handoff/ledgato/revoke', ALVIRA_AUTH_URL), {
        method: 'POST',
        headers: { authorization: `Bearer ${token}` },
        cache: 'no-store',
      })
    } catch {}
  }
  res.setHeader('Set-Cookie', `${SESSION_COOKIE}=; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=0`)
  return res.status(200).json({ ok: true })
}
