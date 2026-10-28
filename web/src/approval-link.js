// Deep link to one pending approval: /app?task=<agent task id>.
// Selection only. The decision is still posted by the selected approval's own
// id, and the owner still sees its full details before choosing.

export function linkedTask(search) {
  try {
    const params = new URLSearchParams(search || '')
    if (!params.has('task')) return { state: 'absent', task: '' }
    const value = params.get('task') || ''
    // Task ids are short opaque tokens; ignore anything else.
    return /^[A-Za-z0-9._:-]{1,160}$/.test(value)
      ? { state: 'valid', task: value }
      : { state: 'invalid', task: '' }
  } catch {
    return { state: 'invalid', task: '' }
  }
}

export function pickApproval(approvals, link) {
  const list = Array.isArray(approvals) ? approvals : []
  if (link.state === 'absent') return { approval: list[0], linked: '', missing: false, invalid: false, ambiguous: false }
  if (link.state !== 'valid') return { approval: undefined, linked: '', missing: false, invalid: true, ambiguous: false }
  const hits = list.filter(a => a?.task_id === link.task || a?.prompt?.task_id === link.task)
  if (hits.length === 1) return { approval: hits[0], linked: link.task, missing: false, invalid: false, ambiguous: false }
  if (hits.length > 1) return { approval: undefined, linked: link.task, missing: false, invalid: false, ambiguous: true }
  return { approval: list[0], linked: link.task, missing: true, invalid: false, ambiguous: false }
}
