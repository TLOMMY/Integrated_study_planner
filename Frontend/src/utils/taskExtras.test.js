import { test } from 'node:test'
import assert from 'node:assert/strict'
import { linksInNote, taskLinks } from '../components/task/extras.js'

test('从备注里提取学习资源链接，网址前的文字作标题', () => {
  const note = '先看第 3 章\n学习资源：\n· 线代期末速成 https://www.bilibili.com/video/BV1Ey4y147xn\n· https://b23.tv/abc。'
  const links = linksInNote(note)
  assert.equal(links.length, 2)
  assert.deepEqual(links[0], { title: '线代期末速成', url: 'https://www.bilibili.com/video/BV1Ey4y147xn', source: 'bilibili' })
  assert.equal(links[1].url, 'https://b23.tv/abc')
  assert.equal(links[1].title, 'b23.tv')
})

test('links 字段与备注里的链接合并去重', () => {
  const task = { links: [{ title: '已有', url: 'https://a.com/x', source: 'manual' }], note: '看 https://a.com/x 和 https://b.com/y' }
  assert.deepEqual(taskLinks(task).map((l) => l.url), ['https://a.com/x', 'https://b.com/y'])
  assert.deepEqual(taskLinks({ note: 'javascript:alert(1) ftp://x' }), [])
})
