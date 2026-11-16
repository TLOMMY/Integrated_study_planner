import { test } from 'node:test'
import assert from 'node:assert/strict'
import dayjs from 'dayjs'
import { parseCourseLine, parseExamLine, parseTaskLine, parseWeeks } from './quickLine.js'

// 2026-10-22 是周四
const ref = dayjs('2026-10-22')

test('任务：名称 + 日期 + 时长 + 优先级，顺序随意', () => {
  const r = parseTaskLine('复习高数 明天 45分钟 高', ref)
  assert.ok(r.ok, r.error)
  assert.deepEqual(
    { title: r.data.title, due: r.data.due_date, min: r.data.duration_minutes, p: r.data.priority, repeat: r.data.repeat_rule },
    { title: '复习高数', due: '2026-10-23', min: 45, p: 3, repeat: 'none' },
  )
  assert.equal(parseTaskLine('高 45分钟 复习高数 明天', ref).data.title, '复习高数')
})

test('任务：只写名称用默认值（今天、30 分钟、无优先级）', () => {
  const r = parseTaskLine('背单词', ref)
  assert.ok(r.ok)
  assert.equal(r.data.due_date, '2026-10-22')
  assert.equal(r.data.duration_minutes, 30)
  assert.equal(r.data.priority, 0)
})

test('任务：连写没分开时报错并给示例', () => {
  const r = parseTaskLine('复习高数明天45分钟', ref)
  assert.equal(r.ok, false)
  assert.match(r.error, /空格/)
  assert.match(r.error, /例如/)
})

test('课程：名称 + 教室 + 星期节次 + 周数', () => {
  const r = parseCourseLine('离散数学 A1205 周三3-4节 1-16周', { total: 20 })
  assert.ok(r.ok, r.error)
  assert.equal(r.data.course_name, '离散数学')
  assert.equal(r.data.classroom, 'A1205')
  assert.deepEqual([r.data.day_of_week, r.data.start_period, r.data.end_period], [3, 3, 4])
  assert.equal(r.data.weeks.length, 16)
})

test('课程：从课表格子带位置，只写名称和教室；不写周数 = 整学期', () => {
  const r = parseCourseLine('高等数学 A1408', { at: { day_of_week: 1, start_period: 1, end_period: 2 }, total: 18 })
  assert.ok(r.ok, r.error)
  assert.deepEqual([r.data.day_of_week, r.data.start_period, r.data.end_period, r.data.weeks.length], [1, 1, 2, 18])
})

test('课程：缺星期节次、节次越界、连写都报错', () => {
  assert.match(parseCourseLine('离散数学 A1205').error, /星期/)
  assert.match(parseCourseLine('离散数学 周三11-14节', { periods: 12 }).error, /1-12/)
  assert.match(parseCourseLine('离散数学周三3-4节').error, /空格/)
})

test('周数写法', () => {
  assert.deepEqual(parseWeeks('1-8周(单)', 20), [1, 3, 5, 7])
  assert.deepEqual(parseWeeks('1-3,18周', 20), [1, 2, 3, 18])
  assert.equal(parseWeeks('双周', 6).join(), '2,4,6')
  assert.equal(parseWeeks('第一周', 20), null)
})

test('考试：名称 + 日期 + 时间 + 考场；日期已过补到明年', () => {
  const r = parseExamLine('数据结构 1月8日 9:00-11:00 教一201', ref)
  assert.ok(r.ok, r.error)
  assert.deepEqual(r.data, { title: '数据结构', exam_date: '2027-01-08', start_time: '09:00', end_time: '11:00', location: '教一201' })
  assert.match(parseExamLine('数据结构 9:00', ref).error, /日期/)
})
