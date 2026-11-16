/**
 * 一行快速新建：任务 / 课程 / 考试。按"内容的样子"识别（顺序随意，空格分开），认不出的部分当名称。
 *
 *   任务  "复习高数 明天 45分钟 高"         → 名称 + 日期 + 时长 + 优先级（时间、重复也能写，其余默认）
 *   课程  "离散数学 A1205 周三3-4节 1-16周"  → 名称 + 教室 + 星期节次 + 周数（周数不写 = 整学期）
 *   考试  "数据结构 1月8日 9:00 教一201"     → 名称 + 日期 + 时间 + 考场
 *
 * 连写（"复习高数明天45分钟"）只能整句当成名称：名称里还带着日期 / 时长 / 节次这类字样时报错，提示用空格分开。
 * 纯函数，便于单元测试。返回 { ok, error, data, tokens }，tokens 用于输入框下方的识别结果标签。
 */
import dayjs from 'dayjs'
import { parseQuickAdd } from './quickAdd.js'

const WEEK = { 一: 1, 二: 2, 三: 3, 四: 4, 五: 5, 六: 6, 日: 7, 天: 7, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7 }
const WEEK_LABEL = ['', '周一', '周二', '周三', '周四', '周五', '周六', '周日']

// 名称里还残留这些字样 = 多半是连写了没分开
const GLUED = /(今天|明天|后天|周[一二三四五六日天]|星期|\d{1,2}[月/]\d{1,2}|\d+\s*(分钟|小时|节|周)|\d{1,2}[:：]\d{2}|[高中低]$)/

export const EXAMPLES = {
  task: '复习高数 明天 45分钟 高',
  course: '离散数学 A1205 周三3-4节 1-16周',
  exam: '数据结构 1月8日 9:00 教一201',
}

const tokensOf = (input) => String(input || '').trim().split(/\s+/).filter(Boolean)

const fail = (error, kind) => ({ ok: false, error: `${error}，例如：${EXAMPLES[kind]}`, data: null, tokens: [] })

/** 名称检查：空 → 报错；带着日期 / 时长 / 节次字样 → 多半连写了。 */
const checkTitle = (title, kind, hadSpace) => {
  if (!title) return fail('请写上名称', kind)
  if (GLUED.test(title)) return fail(hadSpace ? `「${title}」里像是混着别的信息，请用空格分开` : '各部分之间请用空格分开', kind)
  return null
}

// ---------------------------------------------------------------- 任务
/** 在 parseQuickAdd 的基础上：单独的"高 / 中 / 低"也算优先级；只有名称时用默认值（今天、30 分钟）。 */
export function parseTaskLine(input, ref = dayjs()) {
  const parts = tokensOf(input)
  if (!parts.length) return fail('请写上要做的事', 'task')
  let priority = 0
  const rest = parts.filter((part) => {
    const level = { 高: 3, 中: 2, 低: 1 }[part.replace(/优先级?$/, '')]
    if (level && !priority) {
      priority = level
      return false
    }
    return true
  })
  // 连写检查要在解析前做：parseQuickAdd 会把"明天""45分钟"从整句里抠掉，剩下的看起来就像正常名称了。
  // 规则：一个词里既有普通文字、又夹着日期 / 时长这类字样 = 没用空格分开
  const glued = rest.find((part) => GLUED.test(part) && part.replace(GLUED, '').replace(/[\d\s]/g, '').length >= 2)
  if (glued) return fail(rest.length > 1 ? `「${glued}」里像是混着别的信息，请用空格分开` : '各部分之间请用空格分开', 'task')
  const parsed = parseQuickAdd(rest.join(' '), ref)
  const bad = checkTitle(parsed.title, 'task', parts.length > 1)
  if (bad) return bad
  const today = dayjs(ref).format('YYYY-MM-DD')
  const data = {
    title: parsed.title.slice(0, 200),
    due_date: parsed.due_date || today,
    start_time: parsed.start_time,
    duration_minutes: parsed.duration_minutes || 30,
    priority: priority || parsed.priority || 0,
    repeat_rule: parsed.repeat_rule,
  }
  const tokens = [{ icon: 'lucide:calendar', text: data.due_date === today ? '今天' : dayjs(data.due_date).format('M月D日') }]
  if (data.start_time) tokens.push({ icon: 'lucide:clock', text: data.start_time })
  tokens.push({ icon: 'lucide:hourglass', text: `${data.duration_minutes} 分钟` })
  if (data.priority) tokens.push({ icon: 'lucide:flag', text: ['', '低', '中', '高'][data.priority] })
  if (data.repeat_rule !== 'none') tokens.push({ icon: 'lucide:repeat', text: { daily: '每天', weekdays: '工作日', weekly: '每周' }[data.repeat_rule] })
  return { ok: true, error: '', data, tokens }
}

// ---------------------------------------------------------------- 课程
/** 周数："1-16周" / "1-16周(单)" / "1-8,10-16周" / "单周" → 周次列表；不写 = 整学期。 */
export function parseWeeks(text, total = 20) {
  const m = String(text).match(/^(?:第)?([\d,，\-~、]+)?\s*周?\s*[(（]?(单|双)?[周)）]?$/)
  if (!m || (!m[1] && !m[2])) return null
  const weeks = new Set()
  if (m[1]) {
    for (const piece of m[1].split(/[,，、]/).filter(Boolean)) {
      const [a, b] = piece.split(/[-~]/).map(Number)
      if (!a || a > 30 || (b && (b < a || b > 30))) return null
      for (let w = a; w <= (b || a); w++) weeks.add(w)
    }
  } else {
    for (let w = 1; w <= total; w++) weeks.add(w)
  }
  let list = [...weeks].sort((x, y) => x - y)
  if (m[2]) list = list.filter((w) => (m[2] === '单' ? w % 2 === 1 : w % 2 === 0))
  return list.length ? list : null
}

const weeksLabel = (weeks, total) => {
  if (weeks.length === total && weeks[0] === 1) return '整学期'
  const first = weeks[0]
  const last = weeks[weeks.length - 1]
  if (weeks.length === last - first + 1) return `${first}-${last} 周`
  if (weeks.every((w, i) => i === 0 || w - weeks[i - 1] === 2)) return `${first}-${last} 周（${first % 2 ? '单' : '双'}）`
  return `${weeks.length} 周`
}

/**
 * 课程一行："名称 教室 周三3-4节 1-16周"。at = { day_of_week, start_period, end_period }：从课表格子带进来的位置，
 * 一行里没写星期节次时用它。periods = 每天节数，total = 学期周数。
 */
export function parseCourseLine(input, { at = null, periods = 12, total = 20 } = {}) {
  const parts = tokensOf(input)
  if (!parts.length) return fail('请写上课程名', 'course')
  let day = null
  let start = null
  let end = null
  let weeks = null
  let classroom = ''
  const rest = []
  for (const part of parts) {
    const slot = part.match(/^(?:周|星期)([一二三四五六日天1-7])(?:第?(\d{1,2})(?:[-~](\d{1,2}))?节?)?$/)
    if (slot && day === null) {
      day = WEEK[slot[1]]
      if (slot[2]) {
        start = Number(slot[2])
        end = Number(slot[3] || slot[2])
      }
      continue
    }
    const onlyPeriods = part.match(/^第?(\d{1,2})(?:[-~](\d{1,2}))?节$/)
    if (onlyPeriods && start === null) {
      start = Number(onlyPeriods[1])
      end = Number(onlyPeriods[2] || onlyPeriods[1])
      continue
    }
    const w = /周|单|双/.test(part) ? parseWeeks(part, total) : null
    if (w && !weeks) {
      weeks = w
      continue
    }
    // 教室：带数字的短词（A1205、教一201、机房B203），且不是第一个词（第一个是课程名）
    if (!classroom && rest.length && /\d/.test(part) && part.length <= 20) {
      classroom = part
      continue
    }
    rest.push(part)
  }
  const title = rest.join(' ')
  const bad = checkTitle(title, 'course', parts.length > 1)
  if (bad) return bad
  day = day || at?.day_of_week || null
  if (start === null && at?.start_period) {
    start = at.start_period
    end = at.end_period || at.start_period
  }
  if (!day) return fail('还差上课星期，如 周三3-4节', 'course')
  if (start === null) return fail('还差节次，如 周三3-4节', 'course')
  if (start < 1 || end > periods || end < start) return fail(`节次要在 1-${periods} 之间`, 'course')
  weeks = weeks || Array.from({ length: total }, (_, i) => i + 1)
  const data = { course_name: title.slice(0, 160), classroom: classroom.slice(0, 80), day_of_week: day, start_period: start, end_period: end, weeks }
  const tokens = [
    { icon: 'lucide:calendar-days', text: `${WEEK_LABEL[day]} ${start === end ? `第${start}节` : `${start}-${end}节`}` },
    { icon: 'lucide:repeat', text: weeksLabel(weeks, total) },
  ]
  if (classroom) tokens.push({ icon: 'lucide:map-pin', text: classroom })
  return { ok: true, error: '', data, tokens }
}

// ---------------------------------------------------------------- 考试
/** 考试一行："数据结构 1月8日 9:00 教一201"。日期必填（没写就报错），时间、考场可选。 */
export function parseExamLine(input, ref = dayjs()) {
  const parts = tokensOf(input)
  if (!parts.length) return fail('请写上考试名称', 'exam')
  const base = dayjs(ref).startOf('day')
  let date = null
  let start = null
  let end = null
  let location = ''
  const rest = []
  for (const part of parts) {
    const full = part.match(/^(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})[日号]?$/)
    const md = part.match(/^(\d{1,2})[月/.](\d{1,2})[日号]?$/)
    if (!date && (full || md)) {
      let d = full ? dayjs(`${full[1]}-${full[2]}-${full[3]}`) : base.month(Number(md[1]) - 1).date(Number(md[2]))
      if (!full && d.isBefore(base)) d = d.add(1, 'year')
      if (d.isValid()) {
 date = d
        continue
      }
    }
    const rel = { 今天: 0, 明天: 1, 后天: 2 }[part]
    if (!date && rel !== undefined) {
      date = base.add(rel, 'day')
      continue
    }
    const time = part.match(/^([01]?\d|2[0-3])[:：]([0-5]\d)(?:[-~]([01]?\d|2[0-3])[:：]([0-5]\d))?$/)
    if (time && !start) {
      start = `${time[1].padStart(2, '0')}:${time[2]}`
      if (time[3]) end = `${time[3].padStart(2, '0')}:${time[4]}`
      continue
    }
    if (!location && rest.length && /\d/.test(part) && part.length <= 30) {
      location = part
      continue
    }
    rest.push(part)
  }
  const title = rest.join(' ')
  const bad = checkTitle(title, 'exam', parts.length > 1)
  if (bad) return bad
  if (!date) return fail('还差考试日期，如 1月8日', 'exam')
  const data = { title: title.slice(0, 100), exam_date: date.format('YYYY-MM-DD'), start_time: start || '', end_time: end || '', location: location.slice(0, 100) }
  const tokens = [{ icon: 'lucide:calendar', text: date.format('M月D日') }]
  if (start) tokens.push({ icon: 'lucide:clock', text: end ? `${start}-${end}` : start })
  if (location) tokens.push({ icon: 'lucide:map-pin', text: location })
  return { ok: true, error: '', data, tokens }
}
