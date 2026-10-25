/** 管理后台与「我的反馈」共用的标签、配色与格式化。 */
import dayjs from 'dayjs'

export const FEEDBACK_STATUS = [
  { key: 'open', label: '待处理', cls: 'bg-flame-light text-flame' },
  { key: 'processing', label: '处理中', cls: 'bg-primary-light text-primary' },
  { key: 'resolved', label: '已解决', cls: 'bg-success-light text-success' },
  { key: 'closed', label: '已关闭', cls: 'bg-background text-ink-mute' },
]
export const statusMeta = (key) => FEEDBACK_STATUS.find((s) => s.key === key) || FEEDBACK_STATUS[0]

export const FEEDBACK_CATEGORY = [
  { key: 'bug', label: '功能异常' },
  { key: 'ui', label: '界面问题' },
  { key: 'suggestion', label: '功能建议' },
  { key: 'other', label: '其他' },
]

/** "刚刚 / 5 分钟前 / 今天 14:20 / 10-24 14:20 / 2025-10-24" */
export const timeAgo = (value) => {
  if (!value) return '—'
  const t = dayjs(value)
  const minutes = dayjs().diff(t, 'minute')
  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes} 分钟前`
  if (t.isSame(dayjs(), 'day')) return `今天 ${t.format('HH:mm')}`
  return t.year() === dayjs().year() ? t.format('MM-DD HH:mm') : t.format('YYYY-MM-DD')
}
export const fullTime = (value) => (value ? dayjs(value).format('YYYY-MM-DD HH:mm') : '—')
