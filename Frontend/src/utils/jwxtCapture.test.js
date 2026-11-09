import { test } from 'node:test'
import assert from 'node:assert/strict'
import { FRAME_MARKER, MAX_BYTES, MESSAGE_TYPE, captureFileName, captureScript, readCapture, shrinkHtml } from './jwxtCapture.js'

test('注入脚本：语法正确、只在顶层页面加一个按钮、用后端同一个 frame 分隔符', () => {
  const code = captureScript('#D85A30')
  assert.doesNotThrow(() => new Function(code))
  assert.ok(code.includes(FRAME_MARKER) && code.includes(MESSAGE_TYPE) && code.includes('#D85A30'))
  assert.ok(code.includes('window.top !== window'), '只在顶层页面注入')
  assert.ok(!/=>|\blet\b|\bconst\b|`/.test(code.replace(/^\(function\(\)\{/, '')), '只用 ES5 语法')
})

test('只认本功能的消息', () => {
  const html = '<table><tr><td>高等数学</td></tr></table>'
  assert.deepEqual(readCapture({ detail: { type: MESSAGE_TYPE, html, url: 'https://jw.x.edu.cn/kb', title: '课表' } }), { html, url: 'https://jw.x.edu.cn/kb', title: '课表' })
  // 插件有时会把数据再包一层 detail
  assert.equal(readCapture({ detail: { detail: { type: MESSAGE_TYPE, html } } }).html, html)
  assert.equal(readCapture({ detail: { type: 'other', html } }), null)
  assert.equal(readCapture({ detail: { type: MESSAGE_TYPE, html: '  ' } }), null)
  assert.equal(readCapture(null), null)
})

test('页面太大时去掉脚本和样式，保留 frame 分隔符；仍然太大返回 null', () => {
  const small = '<html><body><table></table></body></html>'
  assert.equal(shrinkHtml(small), small)
  const junk = `<script>${'x'.repeat(MAX_BYTES)}</script>`
  const big = `<html>${junk}<table>课</table></html>${FRAME_MARKER}<html><style>a{}</style><table>表</table></html>`
  const shrunk = shrinkHtml(big)
  assert.ok(shrunk && !shrunk.includes('<script') && !shrunk.includes('<style') && shrunk.includes(FRAME_MARKER) && shrunk.includes('课'))
  assert.equal(shrinkHtml(`<table>${'课'.repeat(MAX_BYTES)}</table>`), null)
})

test('文件名用教务系统的域名', () => {
  assert.equal(captureFileName('https://jwxt.example.edu.cn/xskb/index'), 'jwxt.example.edu.cn-课表.html')
  assert.equal(captureFileName('not a url'), '教务系统-课表.html')
})
