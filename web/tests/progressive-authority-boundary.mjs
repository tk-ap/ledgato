import fs from 'node:fs'
import path from 'node:path'

const webRoot=path.resolve(new URL('..',import.meta.url).pathname)
const repoRoot=path.resolve(webRoot,'..')
const api=fs.readFileSync(path.join(repoRoot,'api/control/approvals.js'),'utf8')
const ui=fs.readFileSync(path.join(webRoot,'src/main.jsx'),'utf8')

function fail(message){throw new Error(message)}

if(!api.includes("/api/handoff/ledgato/session")) fail('control API must validate the persisted ALVIRA-backed owner session')
if(!api.includes("LEDGATO_ENGINE_APPROVER_TOKEN")) fail('control API must use a server-held approver credential')
if(!api.includes("LEDGATO_ENGINE_APPROVER_ID")) fail('control API must bind decisions to the configured approver principal')
if(!api.includes("/approve-and-resume")) fail('Allow once must use the engine approve-and-resume operation')
if(!api.includes("/v1/decision-prompts?status=PENDING")) fail('web control room must consume the canonical Decision Prompt contract')
if(api.includes("/resume") && !api.includes("/approve-and-resume")) fail('browser control API must not orchestrate a separate exposed resume token')
if(!api.includes("origin_mismatch")) fail('mutating owner decisions must reject cross-origin POSTs')
if(!api.includes("private, no-store")) fail('approval control responses must not be cacheable')

if(!ui.includes("Allow once")) fail('owner UI must expose the scoped allow-once choice')
if(!ui.includes("Deny")) fail('owner UI must expose deny')
if(!ui.includes("/api/control/approvals")) fail('owner UI must call the same-origin control API')
if(ui.includes("LEDGATO_ENGINE_APPROVER_TOKEN")||ui.includes("LEDGATO_ENGINE_URL")) fail('browser bundle must not contain engine credential/config references')
if(!ui.includes("Routine agent work does not require this tab to stay open")) fail('UI must preserve the autonomous-runtime product invariant')
if(!ui.includes("this exact pending action")) fail('authority prompt must expose the bounded scope')
if(!ui.includes("prompt?.why_held")) fail('owner UI must render the canonical reason from the Decision Prompt')

console.log('progressive-authority-boundary: ok')
