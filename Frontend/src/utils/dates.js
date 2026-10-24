import dayjs from 'dayjs'

export const WEEKDAYS = ['日', '一', '二', '三', '四', '五', '六']

export const todayStr = () => dayjs().format('YYYY-MM-DD')

/** 本地时间的 ISO 字符串（不带时区），与后端的 naive datetime 对齐。 */
export const localIso = (date = new Date()) => dayjs(date).format('YYYY-MM-DDTHH:mm:ss')

export const weekdayLabel = (date) => `周${WEEKDAYS[dayjs(date).day()]}`

/** "今天 / 明天 / 昨天 / 周三 / 10月28日" */
export const relativeDay = (date) => {
  if (!date) return '无日期'
  const target = dayjs(date).startOf('day')
  const diff = target.diff(dayjs().startOf('day'), 'day')
  if (diff === 0) return '今天'
  if (diff === 1) return '明天'
  if (diff === 2) return '后天'
  if (diff === -1) return '昨天'
  if (diff > 2 && diff < 7) return weekdayLabel(target)
  return target.year() === dayjs().year() ? target.format('M月D日') : target.format('YYYY年M月D日')
}

export const formatMinutes = (minutes) => {
  const value = Math.max(0, Math.round(minutes || 0))
  if (value < 60) return `${value} 分钟`
  const hours = Math.floor(value / 60)
  const rest = value % 60
  return rest ? `${hours} 小时 ${rest} 分` : `${hours} 小时`
}

export const shortMinutes = (minutes) => {
  const value = Math.max(0, Math.round(minutes || 0))
  return value >= 60 ? `${(value / 60).toFixed(value % 60 ? 1 : 0)}h` : `${value}m`
}

export const mondayOf = (date) => {
  const d = dayjs(date)
  return d.subtract((d.day() + 6) % 7, 'day').startOf('day')
}

/** 与后端 schedule.teaching_week 同一算法：未设置开学日期返回 null，学期外返回 0。 */
export const teachingWeek = (semesterStart, totalWeeks, date) => {
  if (!semesterStart) return null
  const week = mondayOf(date).diff(mondayOf(semesterStart), 'week') + 1
  return week >= 1 && week <= totalWeeks ? week : 0
}

/** 某天真正要上的课（星期匹配 + 当周在上课周次内）。 */
export const coursesOnDate = (courses, meta, date) => {
  const week = teachingWeek(meta?.semester_start, meta?.total_weeks || 20, date)
  if (week === 0) return []
  const weekday = dayjs(date).day() || 7
  return courses
    .filter((course) => course.day_of_week === weekday && (week === null || course.weeks.includes(week)))
    .sort((a, b) => a.start_time.localeCompare(b.start_time))
}
