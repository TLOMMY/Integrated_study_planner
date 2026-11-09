import { test } from 'node:test'
import assert from 'node:assert/strict'
import { clearDate, commitDate, groupTasksByDate } from './proposalGroups.js'
import { friendlyLabel, modelLabel } from './aiModels.js'

const items = () => [
  { key: 't0', date: '2026-11-02', group: '2026-11-02', duration_minutes: 45 },
  { key: 't1', date: '2026-11-02', group: '2026-11-02', duration_minutes: 30 },
  { key: 't2', date: '2026-11-03', group: '2026-11-03', duration_minutes: 60 },
]

test('编辑日期时（未提交）条目不换组，输入框不会被重建', () => {
  const list = items()
  // 模拟逐位输入"28"：先变成 2026-11-02 → 2026-11-28 之间的中间值
  list[0].date = '2026-11-20'
  list[0].date = '2026-11-28'
  const groups = groupTasksByDate(list)
  assert.deepEqual(groups.map((g) => g.date), ['2026-11-02', '2026-11-03'])
  assert.equal(groups[0].items[0], list[0], '仍在原来那组的第一位')
})

test('失焦提交后才重新分组；非法日期不提交', () => {
  const list = items()
  list[0].date = '2026-11-28'
  assert.equal(commitDate(list[0]), true)
  assert.deepEqual(groupTasksByDate(list).map((g) => [g.date, g.items.map((t) => t.key)]), [
    ['2026-11-02', ['t1']],
    ['2026-11-03', ['t2']],
    ['2026-11-28', ['t0']],
  ])
  list[1].date = ''
  assert.equal(commitDate(list[1]), false)
  assert.equal(groupTasksByDate(list)[0].items[0].key, 't1')
})

test('不定日期的条目归到最后一组；清空日期同时清掉开始时间', () => {
  const list = items()
  clearDate(list[0])
  assert.equal(list[0].start_time, '')
  assert.deepEqual(groupTasksByDate(list).map((g) => [g.date, g.items.map((t) => t.key)]), [
    ['2026-11-02', ['t1']],
    ['2026-11-03', ['t2']],
    ['', ['t0']],
  ])
  // AI 直接给出的无日期条目（没有 group）也归到这一组
  assert.deepEqual(groupTasksByDate([{ key: 'a', date: null }, { key: 'b', date: '2026-01-02' }]).map((g) => g.date), ['2026-01-02', ''])
})

test('改时间、时长不改变组内顺序；没有 group 时按 date 分组', () => {
  const list = items()
  list[1].start_time = '06:00'
  list[1].duration_minutes = 90
  const groups = groupTasksByDate(list)
  assert.deepEqual(groups[0].items.map((t) => t.key), ['t0', 't1'])
  assert.equal(groups[0].minutes, 135)
  assert.deepEqual(groupTasksByDate([{ key: 'a', date: '2026-01-02' }]).map((g) => g.date), ['2026-01-02'])
})

test('模型友好名', () => {
  assert.equal(modelLabel('deepseek-flash'), 'DeepSeek V4.1 Flash（快）')
  assert.equal(modelLabel('deepseek-v4-pro'), 'DeepSeek V4 Pro（强）')
  assert.equal(modelLabel('qwen-vl-max'), 'qwen-vl-max')
  assert.equal(friendlyLabel('DeepSeek（服务器配置） · deepseek-v4-pro'), 'DeepSeek（服务器配置） · DeepSeek V4 Pro（强）')
  assert.equal(friendlyLabel('我的 Kimi · moonshot-v1-8k'), '我的 Kimi · moonshot-v1-8k')
  assert.equal(friendlyLabel(''), '')
})
