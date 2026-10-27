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

eq(linkedTask('?task=t_second'), 't_second', 'reads the task parameter')
eq(linkedTask(''), '', 'no parameter means no link')
eq(linkedTask('?task=' + encodeURIComponent('<script>')), '', 'rejects non-token task ids')
eq(linkedTask('?task=' + 'x'.repeat(161)), '', 'rejects overlong task ids')

eq(pickApproval(approvals, '').approval.id, 'a-1', 'without a link the first pending approval is shown')
eq(pickApproval(approvals, 't_second').approval.id, 'a-2', 'a link selects the matching approval via prompt.task_id')
eq(pickApproval(approvals, 't_first').approval.id, 'a-1', 'a link selects the matching approval via task_id')
const gone = pickApproval(approvals, 't_decided')
eq(gone.missing, true, 'a link to a task with no pending approval is reported')
eq(gone.approval.id, 'a-1', 'and the next pending approval is shown instead')
eq(pickApproval([], 't_decided').approval, undefined, 'no approvals means nothing selected')

if (!ui.includes("import {linkedTask,pickApproval} from './approval-link.js'")) fail('Overview must use the shared approval-link selection')
if (!ui.includes('pickApproval(state.approvals,linkedTask(location.search))')) fail('Overview must select the linked approval')
if (!ui.includes('decide(approval.id,')) fail('decisions must still post the selected approval\'s own id')

console.log('approval-task-link: ok')
