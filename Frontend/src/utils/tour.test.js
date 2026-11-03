import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { TOUR_STEPS, placeCard, shouldAutoStart, spotlight, targetFor } from './tour.js'

const SRC = new URL('..', import.meta.url).pathname.replace(/^\/(\w:)/, '$1')
const walk = (dir) => readdirSync(dir).flatMap((n) => (statSync(join(dir, n)).isDirectory() ? walk(join(dir, n)) : /\.vue$/.test(n) ? [join(dir, n)] : []))

test('步骤顺序：导入课表 → 添加任务 → 开始专注 → AI 助手 → 成长', () => {
  assert.deepEqual(TOUR_STEPS.map((s) => s.key), ['welcome', 'import', 'task', 'focus', 'ai', 'growth', 'done'])
  for (const step of TOUR_STEPS) assert.ok(step.title && step.text && step.icon, step.key)
})

test('每个目标在页面里都有对应的 data-tour（电脑与手机分别检查）', () => {
  const source = walk(SRC).map((f) => readFileSync(f, 'utf8')).join('\n')
  for (const step of TOUR_STEPS) {
    for (const desktop of [true, false]) {
      const name = targetFor(step, desktop)
      if (name) assert.ok(source.includes(`data-tour="${name}"`) || source.includes(`'${name}'`), `${step.key} → ${name}`)
    }
  }
})

test('气泡：优先目标下方，放不下放上方，侧边栏放右侧，始终在屏幕内', () => {
  const view = { width: 390, height: 844 }
  const card = { width: 320, height: 200 }
  assert.equal(placeCard(null, view, card).placement, 'center')
  const top = placeCard({ top: 60, left: 330, width: 40, height: 40 }, view, card)
  assert.equal(top.placement, 'bottom')
  assert.ok(top.left + card.width <= view.width - 12, '靠右的目标气泡不出界')
  const bottomNav = placeCard({ top: 780, left: 160, width: 70, height: 64 }, view, card)
  assert.equal(bottomNav.placement, 'top')
  assert.ok(bottomNav.top + card.height <= 780)
  const desk = { width: 1440, height: 900 }
  const sidebar = placeCard({ top: 0, left: 0, width: 240, height: 900 }, desk, card)
  assert.equal(sidebar.placement, 'right')
  assert.equal(sidebar.left, 254)
})

test('高亮框外扩并夹在屏幕内', () => {
  assert.equal(spotlight(null, { width: 100, height: 100 }), null)
  assert.deepEqual(spotlight({ top: 10, left: 10, width: 20, height: 20 }, { width: 100, height: 100 }), { left: 4, top: 4, width: 32, height: 32 })
  const edge = spotlight({ top: 0, left: 0, width: 100, height: 30 }, { width: 100, height: 100 })
  assert.equal(edge.left, 2)
  assert.equal(edge.left + edge.width, 98)
})

test('自动弹出：首次登录的真实账号；演示账号、已看过、本机已记录都不弹', () => {
  assert.equal(shouldAutoStart({ id: 1, onboarded: false }), true)
  assert.equal(shouldAutoStart({ id: 1, onboarded: true }), false)
  assert.equal(shouldAutoStart({ id: 1, onboarded: false, is_demo: true }), false)
  assert.equal(shouldAutoStart({ id: 1, onboarded: false }, true), false)
  assert.equal(shouldAutoStart(null), false)
})
