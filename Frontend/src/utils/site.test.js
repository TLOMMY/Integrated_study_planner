// 备案号链接与 AI 额度提示：为空不显示、链接指向工信部 / 公安部、剩余次数文字
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { MIIT_URL, MPS_URL, beianLinks, formatTokens, loadSiteInfo, quotaText } from './site.js'

test('备案号为空时不显示任何链接', () => {
  assert.deepEqual(beianLinks({ icp_number: '', police_beian: '  ' }), [])
  assert.deepEqual(beianLinks(null), [])
})

test('ICP 备案链接到工信部，公安备案链接到公安部', () => {
  const links = beianLinks({ icp_number: '京ICP备00000000号-1', police_beian: '京公网安备11010502000000号', police_url: '' })
  assert.equal(links.length, 2)
  assert.deepEqual(links[0], { key: 'icp', text: '京ICP备00000000号-1', url: MIIT_URL })
  assert.equal(links[1].url, MPS_URL)
  assert.equal(beianLinks({ police_beian: 'x', police_url: `${MPS_URL}#/query/webSearch?code=1` })[0].url.startsWith(MPS_URL), true)
})

test('AI 额度：自己的 Key / 管理员不显示，服务器 Key 显示剩余次数', () => {
  assert.equal(quotaText(null), null)
  assert.equal(quotaText({ limited: false, exempt: true }), null)
  assert.deepEqual(quotaText({ limited: true, calls_left: 12, tokens_left: 9000 }), { exceeded: false, text: '今日剩余 12 次' })
  assert.deepEqual(quotaText({ limited: true, calls_left: null, tokens_left: 45000 }), { exceeded: false, text: '今日剩余 45k tokens' })
  assert.equal(quotaText({ limited: true, exceeded: true, calls_left: 0 }).exceeded, true)
})

test('token 数字缩写', () => {
  assert.equal(formatTokens(800), '800')
  assert.equal(formatTokens(15000), '15k')
  assert.equal(formatTokens(1500000), '1.5M')
})

test('站点信息读取失败时返回默认值', async () => {
  const info = await loadSiteInfo(() => Promise.reject(new Error('offline')))
  assert.equal(info.icp_number, '')
  assert.equal(info.app_name, '学业管家')
})
