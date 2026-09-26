import fs from 'node:fs'
import path from 'node:path'

const webRoot=path.resolve(new URL('..',import.meta.url).pathname)
const ui=fs.readFileSync(path.join(webRoot,'src/main.jsx'),'utf8')

function fail(message){throw new Error(message)}

if(!ui.includes("['/app/boundaries','Boundaries']")) fail('Boundaries must be a first-class owner route')
if(!ui.includes('A boundary is the unit LEDGATo is allowed to call verified.')) fail('owner UI must define the scoped verification object')
if(!ui.includes('VERIFIED applies to this boundary only.')) fail('owner UI must prevent global VERIFIED interpretation')
if(!ui.includes('Material drift automatically weakens this claim.')) fail('owner UI must explain re-verification after drift')
if(!ui.includes('No valid permit or decision path means no protected effect.')) fail('owner UI must state the enforcement invariant')
if(!ui.includes('Historical verified lab boundary only')) fail('historical proof must remain visibly bounded')
if(ui.includes('SYSTEM · VERIFIED')||ui.includes('ESCAPE-PROOF SYSTEM')) fail('UI must not imply global escape-proof verification')

console.log('boundary-object: ok')
