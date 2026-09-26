import fs from 'node:fs'
import path from 'node:path'

const webRoot=path.resolve(new URL('..',import.meta.url).pathname)
const repoRoot=path.resolve(webRoot,'..')
const main=fs.readFileSync(path.join(webRoot,'src/main.jsx'),'utf8')
const vercel=JSON.parse(fs.readFileSync(path.join(repoRoot,'vercel.json'),'utf8'))
const gate=fs.readFileSync(path.join(repoRoot,'api/app-gate.js'),'utf8')
const login=fs.readFileSync(path.join(repoRoot,'api/auth/login.js'),'utf8')
const auth=fs.readFileSync(path.join(repoRoot,'lib/owner-auth.js'),'utf8')

function requireText(text, phrase, label=phrase) {
  if (!text.includes(phrase)) throw new Error(`Missing public-navigation requirement: ${label}`)
}

if (main.includes('Create account') || main.includes('Create one')) {
  throw new Error('Public self-serve account creation must not be exposed.')
}
if ((main.match(/Owner sign in/g)||[]).length < 3) {
  throw new Error('Owner sign in must remain visible across public navigation surfaces.')
}
requireText(main, "/api/auth/login", 'real owner login endpoint')
requireText(main, "Back to public site", 'login recovery path')
requireText(main, "Contact TK →", 'working founder-led access path')
requireText(main, "https://ashwood-info.vercel.app/connect?source=ledgato", 'access destination')

const appRewrites=(vercel.rewrites||[]).filter(rule=>rule.source==='/app'||rule.source==='/app/:path*')
if (appRewrites.length !== 2 || appRewrites.some(rule=>!rule.destination.startsWith('/api/app-gate'))) {
  throw new Error('/app and /app/** must route through the owner app gate.')
}
const signupRedirect=(vercel.redirects||[]).find(rule=>rule.source==='/signup')
if (!signupRedirect || signupRedirect.destination!=='/login') {
  throw new Error('/signup must redirect to owner login.')
}

requireText(gate, 'sessionFromRequest', 'server-side app session check')
requireText(login, 'credentialsMatch', 'server-side credential validation')
requireText(auth, 'HttpOnly', 'HttpOnly owner session cookie')
requireText(auth, 'SameSite=Strict', 'strict same-site owner session cookie')

console.log('public-navigation: ok')
