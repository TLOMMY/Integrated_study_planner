import { test } from 'node:test'
import assert from 'node:assert/strict'
import dayjs from 'dayjs'
import { parseQuickAdd } from './quickAdd.js'

// 2026-10-22 是周四
const ref = dayjs('2026-10-22')

test('解析日期、时间、优先级与重复', () => {
  const r = parseQuickAdd('明天下午3点 复习高数 !高 每天', ref)
  assert.equal(r.title, '复习高数')
  assert.equal(r.due_date, '2026-10-23')
  assert.equal(r.start_time, '15:00')
  assert.equal(r.priority, 3)
  assert.equal(r.repeat_rule, 'daily')
})

test('周几与下周几', () => {
  assert.equal(parseQuickAdd('周五 交实验报告', ref).due_date, '2026-10-23')
  assert.equal(parseQuickAdd('周二 交实验报告', ref).due_date, '2026-10-27')
  assert.equal(parseQuickAdd('下周一 开组会', ref).due_date, '2026-10-26')
})

test('只有时间时默认今天，并识别半点与 HH:MM', () => {
  const r = parseQuickAdd('晚上八点半 背单词', ref)
  assert.equal(r.due_date, '2026-10-22')
  assert.equal(r.start_time, '20:30')
  assert.equal(parseQuickAdd('19:05 跑步', ref).start_time, '19:05')
})

test('时长与具体日期', () => {
  const r = parseQuickAdd('11月3日 写论文 90分钟', ref)
  assert.equal(r.due_date, '2026-11-03')
  assert.equal(r.duration_minutes, 90)
  assert.equal(r.title, '写论文')
})

test('只写重复规则时默认从今天开始', () => {
  const r = parseQuickAdd('每天 背单词', ref)
  assert.equal(r.repeat_rule, 'daily')
  assert.equal(r.due_date, '2026-10-22')
  assert.equal(r.title, '背单词')
})

test('没有可识别信息时原样作为标题', () => {
  const r = parseQuickAdd('读完《原则》', ref)
  assert.equal(r.title, '读完《原则》')
  assert.equal(r.due_date, null)
  assert.deepEqual(r.tokens, [])
})
