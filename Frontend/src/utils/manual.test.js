import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { exampleChips, highlight, safeAnchor, searchManual } from './manual.js'

const read = (path) => readFileSync(new URL(path, import.meta.url), 'utf8')
const RULES = JSON.parse(read('../manual/rule-templates.json'))
const CONTENT = read('../manual/content.js')

const SECTIONS = [
  { id: 'focus', title: '专注', summary: '番茄钟', keywords: [], blocks: [{ type: 'p', text: '预设 25 分钟' }, { type: 'list', items: ['白噪音与雨声', '防切出提醒'] }] },
  { id: 'growth', title: '成长与打卡规则', summary: '', blocks: [{ type: 'tip', text: '专注满 5 分钟或完成 1 个任务' }] },
  { id: 'rule-engine', title: '本地规则引擎', summary: '', blocks: [{ type: 'rules', groups: [{ title: '日期范围', patterns: ['今天 / 明天'], examples: [{ text: '今晚复习高数' }] }] }] },
]

test('搜索：标题命中整节、正文只留命中块、多关键词同时满足、忽略大小写', () => {
  assert.equal(searchManual(SECTIONS, '').length, 3)
  const byTitle = searchManual(SECTIONS, '专注')
  assert.equal(byTitle[0].section.id, 'focus')
  assert.equal(byTitle[0].blocks.length, 2, '标题命中显示整节')
  const byBody = searchManual(SECTIONS, '雨声')
  assert.equal(byBody.length, 1)
  assert.deepEqual(byBody[0].blocks.map((b) => b.type), ['list'])
  assert.equal(searchManual(SECTIONS, '白噪音 防切出').length, 1)
  assert.equal(searchManual(SECTIONS, '白噪音 考研').length, 0)
  assert.equal(searchManual(SECTIONS, '今晚')[0].section.id, 'rule-engine', '规则引擎的例句也能搜到')
  assert.equal(searchManual(SECTIONS, '5 分钟').length, 2)
})

test('高亮切分', () => {
  assert.deepEqual(highlight('专注满 5 分钟', '分钟'), [{ text: '专注满 5 ', hit: false }, { text: '分钟', hit: true }])
  assert.deepEqual(highlight('PDF 与 pdf', 'pdf'), [{ text: 'PDF', hit: true }, { text: ' 与 ', hit: false }, { text: 'pdf', hit: true }])
  assert.deepEqual(highlight('abc', ''), [{ text: 'abc', hit: false }])
})

test('锚点只接受安全的 id', () => {
  assert.equal(safeAnchor('#rule-engine'), 'rule-engine')
  assert.equal(safeAnchor('rule-dates'), 'rule-dates')
  assert.equal(safeAnchor('#a"]<script>'), '')
  assert.equal(safeAnchor(''), '')
})

test('规则引擎例句都能生成说明标签', () => {
  for (const group of RULES.groups) {
    for (const example of group.examples) {
      const chips = exampleChips(example.expect, RULES.ref_date)
      assert.ok(chips.length >= 2, example.text)
      assert.ok(chips.some((c) => c.startsWith('科目')), example.text)
    }
  }
  assert.deepEqual(exampleChips({ offset: 0, days: 1, prefer: 'evening', minutes: 90, subjects: ['高等数学'] }, RULES.ref_date), ['从今天起', '1 天', '优先晚上', '每天 90 分钟', '科目：高等数学'])
  assert.ok(exampleChips({ offset: 11, days: 10, subjects: [] }, '2026-10-21').includes('从11月1日起'))
  assert.ok(exampleChips({ offset: 0, days: 16, deadline: 15, subjects: ['概率论'] }, '2026-10-21').includes('截止 11月5日'))
  assert.ok(exampleChips({ intensity: 1.3, exam: true, subjects: ['x'] }, '2026-10-21').includes('强度 ×1.3'))
})

test('手册覆盖要求的章节，界面上用到的锚点都存在', () => {
  for (const id of ['import', 'tasks', 'schedule', 'focus', 'growth', 'ai', 'rule-engine', 'themes', 'devices', 'feedback', 'import-ai', 'growth-checkin']) {
    assert.ok(CONTENT.includes(`id: '${id}'`), id)
  }
  // 规则引擎各组的子锚点 rule-<id> 由 ManualView 生成
  assert.deepEqual(RULES.groups.map((g) => g.id), ['dates', 'minutes', 'segments', 'subjects', 'intensity', 'followup', 'limits'])
  // 打卡规则与成长页口径一致
  assert.match(CONTENT, /专注满 5 分钟，或完成至少 1 个任务/)
})
