import fs from 'node:fs'
import path from 'node:path'

const root=path.resolve(new URL('..',import.meta.url).pathname)
const files=['src/main.jsx','src/content/claims.js']
const text=files.map(f=>fs.readFileSync(path.join(root,f),'utf8')).join('\n')
const banned=[
  'If it can reach your stack, Ledgato can see it',
  'Anything that escapes, drifts, or exfiltrates is caught and blocked before release',
  'LIVE · ENFORCING POLICY',
  'REAL · ALVIRA · ENGINE-DERIVED'
]
for(const phrase of banned){
  if(text.includes(phrase)) throw new Error(`Universal/live claim reintroduced: ${phrase}`)
}
const required=[
  'When a protected action is routed through Ledgato',
  'DEMO · SAMPLE ENVIRONMENT',
  'ALVIRA · CONNECTION STATUS',
  'INTERACTIVE DEMO · NO EXTERNAL ACTION',
  'Real GitHub denial proof.'
]
for(const phrase of required){
  if(!text.includes(phrase)) throw new Error(`Required claim/state distinction missing: ${phrase}`)
}
console.log('claim-boundary: ok')
