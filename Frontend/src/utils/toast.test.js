import { test } from 'node:test'
import assert from 'node:assert/strict'
import { helpForError, toastDuration } from './toast.js'

test('提示停留时间：短文字保持原时长，长文字按字数延长，最多 9 秒', () => {
  assert.equal(toastDuration('已保存', 2400), 2400)
  assert.equal(toastDuration('x'.repeat(24), 2400), 2400)
  assert.equal(toastDuration('x'.repeat(34), 2400), 3000)
  assert.equal(toastDuration('x'.repeat(500), 2400), 9000)
  // 调用方本来就给了更长的时长时不缩短
  assert.equal(toastDuration('x'.repeat(500), 12000), 12000)
  assert.equal(toastDuration('', 1600), 1600)
})

test('失败原因对应到使用手册', () => {
  assert.deepEqual(helpForError({ data: { reason: 'ai_quota' } }), { label: '查看说明', hash: '#ai' })
  assert.equal(helpForError({ data: { reason: 'no_vision' } }).hash, '#import-ai')
  assert.equal(helpForError({ data: { reason: 'unknown' } }), null)
  assert.equal(helpForError(new Error('x')), null)
  assert.equal(helpForError(null), null)
})
