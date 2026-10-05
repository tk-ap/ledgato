import fs from 'node:fs'
import path from 'node:path'

const webRoot=path.resolve(new URL('..',import.meta.url).pathname)
const repoRoot=path.resolve(webRoot,'..')
const config=JSON.parse(fs.readFileSync(path.join(repoRoot,'vercel.json'),'utf8'))
const gate=fs.readFileSync(path.join(repoRoot,'api/app-gate.js'),'utf8')
const login=fs.readFileSync(path.join(repoRoot,'api/owner-login.js'),'utf8')
const callback=fs.readFileSync(path.join(repoRoot,'api/auth/alvira/callback.js'),'utf8')

function fail(message){throw new Error(message)}

const bySource=(source)=>(config.rewrites||[]).find(rule=>rule.source===source)
if(bySource('/login')?.destination!=='/api/owner-login') fail('/login must stay on the server-owned LEDGATo owner-access route')
if(bySource('/app')?.destination!=='/api/app-gate?next=/app') fail('/app must be server-gated')
if(bySource('/app/:path*')?.destination!=='/api/app-gate?next=/app/:path*') fail('/app/** must be server-gated')
const signup=(config.redirects||[]).find(rule=>rule.source==='/signup')
if(signup?.destination!=='/login') fail('/signup must not expose a second account path')

for(const [source,label] of [[login,'owner login'],[callback,'callback'],[gate,'app gate']]){
  if(source.includes('LEDGATO_OWNER_PASSWORD')||source.includes('password_hash')) fail(`${label} must not create a parallel password authority`)
}
if(!login.includes('Sign in to LEDGATo.')||!login.includes('Continue with ALVIRA')) fail('/login must present a LEDGATo-branded sign-in landing before identity handoff')
if(!login.includes("const shouldStart = String((req.query && req.query.continue) || '') === '1'")) fail('ALVIRA handoff must require an explicit continue action from the LEDGATo landing')
if(!login.includes('if (!shouldStart)')) fail('owner login must not redirect to ALVIRA before the user chooses to continue')
if(!login.includes('challenge')||!login.includes('verifier')||!login.includes('state')) fail('owner login continuation must use PKCE-style handoff binding')
if(!callback.includes('/api/handoff/ledgato/consume')) fail('callback must consume the ALVIRA handoff server-side')
if(!gate.includes('/api/handoff/ledgato/session')) fail('app gate must validate the session against ALVIRA')
if(!gate.includes("SESSION_COOKIE = 'ledgato_owner_session'")) fail('app gate must use the opaque owner session cookie')

console.log('owner-session-boundary: ok')
