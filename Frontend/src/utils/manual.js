/**
 * 使用手册：搜索、高亮、规则引擎例句的解析结果展示。纯函数，便于单测。
 * 手册正文见 src/manual/content.js；规则引擎模板见 src/manual/rule-templates.json。
 */

const SEGMENT_LABEL = { morning: '上午', afternoon: '下午', evening: '晚上' }

/** 把搜索词拆成若干关键词（空格分隔，忽略大小写）。 */
export const terms = (query) => String(query || '').toLowerCase().split(/\s+/).filter(Boolean)

/** 一个内容块里可被搜索的文字。 */
export function blockText(block) {
  if (!block) return ''
  const parts = [block.title, block.text, ...(block.items || [])]
  if (block.type === 'rules') {
    for (const group of block.groups || []) {
      parts.push(group.title, ...(group.patterns || []), ...(group.examples || []).map((e) => e.text))
    }
  }
  return parts.filter(Boolean).join('\n').toLowerCase()
}

/**
 * 搜索：所有关键词都出现在"章节标题 + 该块"里才算命中。
 * 返回 [{ section, blocks }]；章节标题命中时整节都显示。query 为空时返回全部。
 */
export function searchManual(sections, query) {
  const words = terms(query)
  if (!words.length) return sections.map((section) => ({ section, blocks: section.blocks }))
  const result = []
  for (const section of sections) {
    const head = `${section.title}\n${section.summary || ''}\n${(section.keywords || []).join(' ')}`.toLowerCase()
    if (words.every((w) => head.includes(w))) {
      result.push({ section, blocks: section.blocks })
      continue
    }
    const blocks = section.blocks.filter((block) => {
      const text = `${head}\n${blockText(block)}`
      return words.every((w) => text.includes(w)) && words.some((w) => blockText(block).includes(w))
    })
    if (blocks.length) result.push({ section, blocks })
  }
  return result
}

/** 把文字按关键词切成 [{ text, hit }]，界面逐段渲染（不用 v-html，避免注入）。 */
export function highlight(text, query) {
  const source = String(text ?? '')
  const words = terms(query)
  if (!words.length || !source) return [{ text: source, hit: false }]
  const lower = source.toLowerCase()
  const marks = new Array(source.length).fill(false)
  for (const word of words) {
    let from = 0
    while ((from = lower.indexOf(word, from)) !== -1) {
      marks.fill(true, from, from + word.length)
      from += word.length
    }
  }
  const parts = []
  for (let i = 0; i < source.length; i++) {
    const last = parts[parts.length - 1]
    if (last && last.hit === marks[i]) last.text += source[i]
    else parts.push({ text: source[i], hit: marks[i] })
  }
  return parts
}

function dayLabel(refIso, offset) {
  if (offset === 0) return '今天'
  if (offset === 1) return '明天'
  if (offset === 2) return '后天'
  const [y, m, d] = refIso.split('-').map(Number)
  const date = new Date(Date.UTC(y, m - 1, d + offset))
  return `${date.getUTCMonth() + 1}月${date.getUTCDate()}日`
}

/** 例句的期望解析结果 → 界面上的小标签（与后端测试断言的是同一份 expect）。 */
export function exampleChips(expect, refIso) {
  const chips = []
  const start = expect.offset ?? 0
  if ('offset' in expect || expect.days) chips.push(`从${dayLabel(refIso, start)}起`)
  chips.push(expect.days ? `${expect.days} 天` : '天数：默认（平时 7 天 / 备考 14 天）')
  if (expect.deadline !== undefined) chips.push(`截止 ${dayLabel(refIso, expect.deadline)}`)
  if (expect.prefer) chips.push(`优先${SEGMENT_LABEL[expect.prefer] || expect.prefer}`)
  if (expect.minutes) chips.push(`每天 ${expect.minutes} 分钟`)
  if (expect.intensity && expect.intensity !== 1) chips.push(`强度 ×${expect.intensity}`)
  if (expect.exam) chips.push('备考模式')
  if (expect.subjects?.length) chips.push(`科目：${expect.subjects.join('、')}`)
  else chips.push('科目：沿用上一轮 / 按课表')
  return chips
}

/** 锚点 id 只允许字母数字和连字符，防止把任意字符串塞进选择器。 */
export const safeAnchor = (hash) => {
  const id = String(hash || '').replace(/^#/, '')
  return /^[a-z0-9-]{1,40}$/.test(id) ? id : ''
}
