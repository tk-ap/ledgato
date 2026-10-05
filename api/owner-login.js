const crypto = require('node:crypto')

const ALVIRA_AUTH_URL = process.env.ALVIRA_AUTH_URL || 'https://alviratech.vercel.app'

function safeNext(value) {
  const raw = Array.isArray(value) ? value[0] : value
  return typeof raw === 'string' && raw.startsWith('/app') && !raw.startsWith('//') ? raw : '/app'
}

function cookie(name, value, maxAge) {
  return `${name}=${encodeURIComponent(value)}; Path=/api/auth/alvira; HttpOnly; Secure; SameSite=Lax; Max-Age=${maxAge}`
}

function landing(next) {
  const continueHref = `/login?continue=1&next=${encodeURIComponent(next)}`
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <meta name="color-scheme" content="dark" />
  <title>Sign in · LEDGATo</title>
  <style>
    :root{font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#f5f3ee;background:#080907}
    *{box-sizing:border-box}
    body{margin:0;min-height:100vh;background:
      radial-gradient(circle at 18% 18%,rgba(255,193,67,.08),transparent 34rem),
      radial-gradient(circle at 82% 70%,rgba(74,160,103,.08),transparent 30rem),
      #080907;display:grid;place-items:center;padding:24px}
    main{width:min(100%,520px)}
    .brand{font-size:22px;letter-spacing:.08em;font-weight:650;margin-bottom:48px}
    .brand b{font-weight:650;color:#efb848}
    .eyebrow{font:600 11px/1.2 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.16em;color:#9c9b91;margin-bottom:14px}
    h1{font-size:clamp(36px,8vw,58px);line-height:.98;letter-spacing:-.045em;margin:0 0 22px;max-width:8ch}
    p{color:#aaa99f;font-size:16px;line-height:1.65;margin:0}
    .card{margin-top:34px;border:1px solid rgba(255,255,255,.12);background:rgba(255,255,255,.025);padding:24px;border-radius:18px}
    .card strong{display:block;font-size:15px;margin-bottom:8px}
    .actions{display:grid;gap:12px;margin-top:22px}
    .primary,.secondary{display:flex;align-items:center;justify-content:center;min-height:50px;border-radius:999px;text-decoration:none;font-weight:650}
    .primary{background:#f5f3ee;color:#11120f}
    .secondary{border:1px solid rgba(255,255,255,.14);color:#f5f3ee}
    .meta{margin-top:18px;font:500 11px/1.55 ui-monospace,SFMono-Regular,Menlo,monospace;color:#6f7069}
    .note{margin-top:30px;padding-top:22px;border-top:1px solid rgba(255,255,255,.08);font-size:13px;color:#7e7f77}
  </style>
</head>
<body>
  <main>
    <div class="brand">LEDGAT<b>o</b></div>
    <div class="eyebrow">OWNER ACCESS</div>
    <h1>Sign in to LEDGATo.</h1>
    <p>Use your ALVIRA owner identity to establish a scoped LEDGATo owner session. You return here after identity verification.</p>

    <section class="card">
      <strong>Continue with ALVIRA</strong>
      <p>ALVIRA confirms who you are. LEDGATo keeps its own owner session and authorization boundary.</p>
      <div class="actions">
        <a class="primary" href="${continueHref}">Continue with ALVIRA →</a>
        <a class="secondary" href="/app">Open LEDGATo</a>
      </div>
      <div class="meta">No LEDGATo password · no parallel identity store · server-bound handoff</div>
    </section>

    <p class="note">If your ALVIRA session has expired, the next step may ask you to sign in there before returning to LEDGATo.</p>
  </main>
</body>
</html>`
}

module.exports = function handler(req, res) {
  if (req.method !== 'GET') {
    res.setHeader('Allow', 'GET')
    return res.status(405).send('Method Not Allowed')
  }

  const next = safeNext(req.query && req.query.next)
  const shouldStart = String((req.query && req.query.continue) || '') === '1'

  res.setHeader('Cache-Control', 'no-store')

  if (!shouldStart) {
    res.statusCode = 200
    res.setHeader('Content-Type', 'text/html; charset=utf-8')
    return res.end(landing(next))
  }

  const verifier = crypto.randomBytes(32).toString('base64url')
  const challenge = crypto.createHash('sha256').update(verifier).digest('base64url')
  const state = crypto.randomBytes(24).toString('base64url')

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
