import fs from 'node:fs'
import path from 'node:path'
import { linkedTask, pickApproval } from '../src/approval-link.js'

const webRoot = path.resolve(new URL('..', import.meta.url).pathname)
const ui = fs.readFileSync(path.join(webRoot, 'src/main.jsx'), 'utf8')

function fail(message) { throw new Error(message) }
function eq(actual, expected, message) { if (actual !== expected) fail(`${message}: expected ${expected}, got ${actual}`) }

const approvals = [
  { id: 'a-1', task_id: 't_first' },
  { id: 'a-2', prompt: { task_id: 't_second' } },
]

eq(linkedTask('?task=t_second').state, 'valid', 'reads a valid task parameter')
eq(linkedTask('?task=t_second').task, 't_second', 'keeps the valid task parameter')
eq(linkedTask('').state, 'absent', 'no parameter means no link')
eq(linkedTask('?task=' + encodeURIComponent('<script>')).state, 'invalid', 'rejects non-token task ids')
eq(linkedTask('?task=' + 'x'.repeat(161)).state, 'invalid', 'rejects overlong task ids')

eq(pickApproval(approvals, linkedTask('')).approval.id, 'a-1', 'without a link the first pending approval is shown')
eq(pickApproval(approvals, linkedTask('?task=t_second')).approval.id, 'a-2', 'a link selects the matching approval via prompt.task_id')
eq(pickApproval(approvals, linkedTask('?task=t_first')).approval.id, 'a-1', 'a link selects the matching approval via task_id')
const invalid = pickApproval(approvals, linkedTask('?task=' + encodeURIComponent('a b/&x')))
eq(invalid.invalid, true, 'invalid links are reported')
eq(invalid.approval, undefined, 'invalid links never select another approval')
const gone = pickApproval(approvals, linkedTask('?task=t_decided'))
eq(gone.missing, true, 'a link to a task with no pending approval is reported')
eq(gone.approval.id, 'a-1', 'and the next pending approval is shown instead')
const ambiguous = pickApproval([...approvals, { id: 'a-3', task_id: 't_first' }], linkedTask('?task=t_first'))
eq(ambiguous.ambiguous, true, 'duplicate task links are reported')
eq(ambiguous.approval, undefined, 'duplicate task links never select one approval')
eq(pickApproval([], linkedTask('?task=t_decided')).approval, undefined, 'no approvals means nothing selected')

if (!ui.includes("import {linkedTask,pickApproval} from './approval-link.js'")) fail('Overview must use the shared approval-link selection')
if (!ui.includes('pickApproval(state.approvals,linkedTask(location.search))')) fail('Overview must select the linked approval')
if (!ui.includes('decide(approval.id,')) fail('decisions must still post the selected approval\'s own id')
if (!ui.includes("This approval link is invalid.")) fail('invalid links must be visible to the owner')

if (!ui.includes("state.kind==='connected'&&waiting===0&&")) fail('an invalid or ambiguous link must not claim there are no pending approvals')
if (!ui.includes('waiting>0?')) fail('the heading must count pending approvals, not the selected one')
console.log('approval-task-link: ok')
