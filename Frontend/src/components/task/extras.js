/** 任务扩展字段的前端工具：子任务 id、学习资源链接、提醒时间的计算与反推。 */
import dayjs from 'dayjs'

export const TAG_MAX = 5
export const TAG_LEN = 12
export const LIST_LEN = 20
export const CHECKLIST_MAX = 30
export const LINKS_MAX = 10

export const newItemId = () => Math.random().toString(36).slice(2, 10)

export const isHttpUrl = (value) => /^https?:\/\/[^\s/]+\S*$/i.test(String(value || '').trim())

const hostOf = (url) => {
  try {
    return new URL(url).hostname.toLowerCase()
  } catch {
    return ''
  }
}

export const isBilibili = (link) => {
  const host = hostOf(link?.url)
  return link?.source === 'bilibili' || ['bilibili.com', 'b23.tv'].some((h) => host === h || host.endsWith(`.${h}`))
}

export const linkHost = (url) => hostOf(url).replace(/^www\./, '')

const URL_RE = /https?:\/\/[^\s<>"'，。；、）)]+/gi

/**
 * 从备注里提取链接（AI 推荐的学习资源统一写在备注里，每行「· 标题 网址」）。
 * 网址前面同一行的文字当作标题；没有标题时显示域名。
 */
export const linksInNote = (note) => {
  const found = []
  for (const line of String(note || '').split(/\r?\n/)) {
    for (const match of line.matchAll(URL_RE)) {
      const url = match[0].replace(/[.,;:!?]+$/, '')
      if (!isHttpUrl(url) || found.some((l) => l.url === url)) continue
      const title = line.slice(0, match.index).replace(/^[\s·•\-*\d.、]+/, '').replace(/[：:\s]+$/, '').trim()
      found.push({ title: title || linkHost(url) || url, url, source: isBilibili({ url }) ? 'bilibili' : 'note' })
    }
  }
  return found.slice(0, LINKS_MAX)
}

/** 任务的全部学习资源：links 字段 + 备注里的链接（去重）。 */
export const taskLinks = (task) => {
  const own = Array.isArray(task?.links) ? task.links : []
  const extra = linksInNote(task?.note).filter((l) => !own.some((o) => o.url === l.url))
  return [...own, ...extra]
}

// ---------------------------------------------------------------- 提醒
const FMT = 'YYYY-MM-DDTHH:mm'
const LEADS = [0, 5, 15, 30]

/** 编辑器里可选的提醒方式：有具体时刻的任务按"提前 N 分钟"，只有日期的按"当天 / 前一天"。 */
export const remindOptions = (dueDate, startTime) => {
  const options = [{ key: 'none', label: '不提醒' }]
  if (dueDate && startTime) {
    options.push(...LEADS.map((m) => ({ key: `m${m}`, label: m ? `提前 ${m} 分钟` : '准时' })))
  } else if (dueDate) {
    options.push({ key: 'd9', label: '当天 9:00' }, { key: 'd8', label: '当天 8:00' }, { key: 'e20', label: '前一天 20:00' })
  }
  options.push({ key: 'custom', label: '自定义' })
  return options
}

/** 按提醒方式算出绝对时间（YYYY-MM-DDTHH:mm），不提醒返回 null。 */
export const computeRemindAt = (mode, { dueDate, startTime, custom }) => {
  if (!mode || mode === 'none') return null
  if (mode === 'custom') return custom && dayjs(custom).isValid() ? dayjs(custom).format(FMT) : null
  if (!dueDate) return null
  if (mode.startsWith('m')) return startTime ? dayjs(`${dueDate} ${startTime}`).subtract(Number(mode.slice(1)), 'minute').format(FMT) : null
  if (mode === 'd9') return `${dueDate}T09:00`
  if (mode === 'd8') return `${dueDate}T08:00`
  if (mode === 'e20') return dayjs(dueDate).subtract(1, 'day').format('YYYY-MM-DD') + 'T20:00'
  return null
}

/** 从已保存的提醒时间反推提醒方式，便于编辑时回显。 */
export const inferRemindMode = (remindAt, dueDate, startTime) => {
  if (!remindAt) return 'none'
  for (const option of remindOptions(dueDate, startTime)) {
    if (option.key !== 'none' && option.key !== 'custom' && computeRemindAt(option.key, { dueDate, startTime }) === remindAt) return option.key
  }
  return 'custom'
}

/** 列表里显示的提醒时间："19:45" / "明天 09:00" / "6/12 20:00"。 */
export const remindLabel = (remindAt) => {
  if (!remindAt) return ''
  const at = dayjs(remindAt)
  const today = dayjs().startOf('day')
  const diff = at.startOf('day').diff(today, 'day')
  const prefix = diff === 0 ? '' : diff === 1 ? '明天 ' : diff === -1 ? '昨天 ' : `${at.format('M/D')} `
  return `${prefix}${at.format('HH:mm')}`
}
