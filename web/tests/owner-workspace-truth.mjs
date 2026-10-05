import fs from 'node:fs'
import path from 'node:path'

const webRoot=path.resolve(new URL('..',import.meta.url).pathname)
const ui=fs.readFileSync(path.join(webRoot,'src/main.jsx'),'utf8')

function fail(message){throw new Error(message)}

if(ui.includes("sessionStorage.setItem('ledgatoGuest'")) fail('authenticated /app must not be reachable through a client-side guest bypass')
if(ui.includes('function Auth({signup=false})')) fail('/login and /signup must remain server-owned; do not ship a fake client-side auth form')
if(!ui.includes("const serverOwned = to === '/login' || to === '/signup' || (to.startsWith('/app') && !location.pathname.startsWith('/app'))")) {
  fail('public-to-owner navigation must hard-navigate through the server gate')
}
if(!ui.includes("if(path==='/login'||path==='/signup'){location.replace(path);return null;}")) {
  fail('client router must fail back to the server-owned auth route if login/signup is reached in SPA state')
}
if(!ui.includes('LIVE SOURCE · NOT CONNECTED')) fail('unwired authenticated routes must render honest live-source state')
if(!ui.includes('The authenticated workspace does not substitute sample agents for live inventory.')) {
  fail('authenticated agent inventory must not silently fall back to sample agents')
}
if(!ui.includes('Your owner session is valid, but the production app has no configured route to the LEDGATo engine yet.')) {
  fail('engine configuration failure must be distinguished from owner authentication failure')
}
if(!ui.includes('<a href="/login?next=/app">Restore owner session →</a>')) {
  fail('owner-session recovery must use a hard server handoff, not SPA login')
}

console.log('owner-workspace-truth: ok')
