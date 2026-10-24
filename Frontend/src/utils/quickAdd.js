/**
 * 快速添加的自然语言解析（对标滴答清单）：
 *   "明天下午3点 复习高数 !高 每天" -> { title: '复习高数', due_date: 明天, start_time: '15:00', priority: 3, repeat_rule: 'daily' }
 * 纯函数，便于单元测试。
 */
import dayjs from 'dayjs'

const CN = { 零: 0, 一: 1, 二: 2, 两: 2, 三: 3, 四: 4, 五: 5, 六: 6, 七: 7, 八: 8, 九: 9, 十: 10 }
const WEEK = { 一: 1, 二: 2, 三: 3, 四: 4, 五: 5, 六: 6, 日: 7, 天: 7 }

const toNumber = (token) => {
  if (/^\d+$/.test(token)) return Number(token)
  if (token.startsWith('十')) return 10 + (CN[token[1]] || 0)
  if (token.length === 2 && token[1] === '十') return CN[token[0]] * 10
  if (token.length === 3 && token[1] === '十') return CN[token[0]] * 10 + CN[token[2]]
  return CN[token] ?? NaN
}

const NUM = '(\\d{1,2}|[零一二两三四五六七八九十]{1,3})'

export function parseQuickAdd(input, ref = dayjs()) {
  let text = ` ${String(input || '').trim()} `
  const base = dayjs(ref).startOf('day')
  const result = { due_date: null, start_time: null, priority: 0, repeat_rule: 'none', duration_minutes: 30 }
  const take = (regex, handler) => {
    const match = text.match(regex)
    if (!match) return false
    handler(match)
    text = text.replace(match[0], ' ')
    return true
  }

  // 优先级：!高 / !!! / ！中
  take(/[!！](高|中|低|!{1,2})/, (m) => {
    result.priority = { 高: 3, 中: 2, 低: 1, '!': 2, '!!': 3 }[m[1]]
  })
  // 重复
  take(/每个?工作日/, () => (result.repeat_rule = 'weekdays'))
  take(/每天|每日/, () => (result.repeat_rule = 'daily'))
  take(/每周|每星期/, () => (result.repeat_rule = 'weekly'))

  // 日期
  take(/今天|今日/, () => (result.due_date = base))
  take(/明天|明日/, () => (result.due_date = base.add(1, 'day')))
  take(/后天/, () => (result.due_date = base.add(2, 'day')))
  take(/(下)?(?:周|星期|礼拜)([一二三四五六日天])/, (m) => {
    const target = WEEK[m[2]]
    const current = base.day() || 7
    let diff = target - current
    if (m[1]) diff += 7
    else if (diff < 0) diff += 7
    result.due_date = base.add(diff, 'day')
  })
  take(/(\d{1,2})[月/](\d{1,2})[日号]?/, (m) => {
    let date = base.month(Number(m[1]) - 1).date(Number(m[2]))
    if (date.isBefore(base)) date = date.add(1, 'year')
    result.due_date = date
  })
  take(new RegExp(`${NUM}天后`), (m) => (result.due_date = base.add(toNumber(m[1]), 'day')))

  // 时间：19:30 / 晚上8点 / 下午3点半
  if (!take(/([01]?\d|2[0-3])[:：]([0-5]\d)/, (m) => (result.start_time = `${m[1].padStart(2, '0')}:${m[2]}`))) {
    take(new RegExp(`(早上|上午|中午|下午|晚上|今晚)?\\s*${NUM}\\s*[点时](半|(\\d{1,2})分?)?`), (m) => {
      let hour = toNumber(m[2])
      if (Number.isNaN(hour) || hour > 23) return
      if (['下午', '晚上', '今晚'].includes(m[1]) && hour < 12) hour += 12
      if (m[1] === '中午' && hour < 6) hour += 12
      const minute = m[3] === '半' ? 30 : Number(m[4] || 0)
      result.start_time = `${String(hour).padStart(2, '0')}:${String(Math.min(minute, 59)).padStart(2, '0')}`
      if (m[1] === '今晚' && !result.due_date) result.due_date = base
    })
  }
  // 时长：45分钟 / 1小时
  take(new RegExp(`${NUM}\\s*(分钟|小时)`), (m) => {
    const value = toNumber(m[1])
    if (!Number.isNaN(value)) result.duration_minutes = Math.min(480, m[2] === '小时' ? value * 60 : value)
  })

  // 定了时刻或设置了重复却没给日期时，归到今天（后端按日期生成下一次重复）
  if ((result.start_time || result.repeat_rule !== 'none') && !result.due_date) result.due_date = base
  result.title = text.replace(/\s+/g, ' ').trim().replace(/^[,，、]+|[,，、]+$/g, '')
  result.due_date = result.due_date ? result.due_date.format('YYYY-MM-DD') : null

  result.tokens = []
  if (result.due_date) result.tokens.push({ icon: 'lucide:calendar', text: result.due_date === base.format('YYYY-MM-DD') ? '今天' : dayjs(result.due_date).format('M/D') })
  if (result.start_time) result.tokens.push({ icon: 'lucide:clock', text: result.start_time })
  if (result.priority) result.tokens.push({ icon: 'lucide:flag', text: ['', '低', '中', '高'][result.priority] })
  if (result.repeat_rule !== 'none') result.tokens.push({ icon: 'lucide:repeat', text: { daily: '每天', weekdays: '工作日', weekly: '每周' }[result.repeat_rule] })
  return result
}
