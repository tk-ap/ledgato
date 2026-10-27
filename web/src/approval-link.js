// Deep link to one pending approval: /app?task=<agent task id>.
// Selection only. The decision is still posted by the selected approval's own
// id, and the owner still sees its full details before choosing.

export function linkedTask(search) {
  try {
    const value = new URLSearchParams(search || '').get('task') || ''
    // Task ids are short opaque tokens; ignore anything else.
    return /^[A-Za-z0-9._:-]{1,160}$/.test(value) ? value : ''
  } catch {
    return ''
  }
}

export function pickApproval(approvals, task) {
  const list = Array.isArray(approvals) ? approvals : []
  if (!task) return { approval: list[0], linked: '', missing: false }
  const hit = list.find(a => a?.task_id === task || a?.prompt?.task_id === task)
  return hit
    ? { approval: hit, linked: task, missing: false }
    : { approval: list[0], linked: task, missing: true }
}
