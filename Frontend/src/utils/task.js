// 优先级用珊瑚的深浅：高 = 主色、中 = 中间色、低 = 浅珊瑚（文字仍写"高 / 中 / 低"，不只靠颜色区分）
export const PRIORITIES = [
  { value: 0, label: '无', color: 'text-ink-mute', ring: 'border-ink-line', bg: 'bg-ink-mute' },
  { value: 1, label: '低', color: 'text-primary-dark', ring: 'border-primary-soft', bg: 'bg-primary-soft' },
  { value: 2, label: '中', color: 'text-primary', ring: 'border-primary-mid', bg: 'bg-primary-mid' },
  { value: 3, label: '高', color: 'text-primary', ring: 'border-primary', bg: 'bg-primary' },
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
