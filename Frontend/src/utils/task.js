export const PRIORITIES = [
  { value: 0, label: '无', color: 'text-ink-mute', ring: 'border-ink-line', bg: 'bg-ink-mute' },
  { value: 1, label: '低', color: 'text-sky-500', ring: 'border-sky-400', bg: 'bg-sky-500' },
  { value: 2, label: '中', color: 'text-amber-500', ring: 'border-amber-400', bg: 'bg-amber-500' },
  { value: 3, label: '高', color: 'text-danger', ring: 'border-danger', bg: 'bg-danger' },
]

export const priorityMeta = (value) => PRIORITIES[value] || PRIORITIES[0]

export const REPEATS = [
  { value: 'none', label: '不重复' },
  { value: 'daily', label: '每天' },
  { value: 'weekdays', label: '工作日' },
  { value: 'weekly', label: '每周' },
]

export const DURATIONS = [15, 25, 30, 45, 60, 90, 120]

export const FOCUS_MIN = 1
export const FOCUS_MAX = 180

/** 番茄钟时长：直接用任务的预计时长（限制在 1-180 分钟），专注页里还可以再改。 */
export const focusMinutesFor = (task) => {
  const minutes = Math.round(Number(task?.duration_minutes) || 25)
  return Math.min(Math.max(minutes, FOCUS_MIN), FOCUS_MAX)
}

export const focusRoute = (task) => ({
  name: 'focus',
  query: task ? { taskId: task.id, minutes: focusMinutesFor(task) } : {},
})
