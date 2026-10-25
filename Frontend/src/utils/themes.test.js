// 主题注册表自检：变量齐全、默认主题保持 v3 原配色、各主题实测对比度达标、玻璃主题壁纸数值符合配色文档
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { COLOR_KEYS, GLASS_KEYS, THEMES, contrast, contrastReport, getTheme, hexToChannels, resolveVars, themeCss, wallpaperStats } from '../themes/index.js'

const GLASS = ['apricot-dawn', 'mist-pine', 'night-indigo', 'terracotta-paper']

test('每个主题的变量都能解析出完整的颜色表', () => {
  for (const theme of THEMES) {
    assert.match(theme.id, /^[a-z0-9-]{2,30}$/, `${theme.id} 不符合账号 theme 字段格式`)
    assert.equal(theme.preview.length, 3)
    const vars = resolveVars(theme)
    for (const key of COLOR_KEYS) assert.ok(hexToChannels(vars[key]), `${theme.id}.${key} 不是合法的 #RRGGBB：${vars[key]}`)
    if (theme.glass) for (const key of GLASS_KEYS) assert.ok(vars[key], `${theme.id} 缺少玻璃变量 ${key}`)
  }
})

test('默认主题与 v3 配色一致', () => {
  const css = themeCss(getTheme('default'))
  const vars = resolveVars(getTheme('default'))
  assert.equal(vars.primary, '#4F6EF7')
  assert.equal(vars.ink, '#0F172A')
  assert.equal(vars.background, '#F5F7FB')
  assert.equal(vars['on-primary'], '#FFFFFF')
  assert.equal(vars['surface-alpha'], '1')
  assert.match(css, /--c-primary: 79 110 247;/)
  assert.match(css, /color-scheme:light/)
  assert.doesNotMatch(css, /--wallpaper/, '默认主题不应启用壁纸')
})

test('配色文档给定的数值原样使用', () => {
  const expect = {
    'apricot-dawn': { primary: '#0471DE', 'on-primary': '#FFFFFF', ink: '#14121A', success: '#34C759', flame: '#E8833A', danger: '#D93A3A' },
    'mist-pine': { primary: '#0F766E', 'on-primary': '#FFFFFF', ink: '#10201E', success: '#2E9E5B', flame: '#C97A32', danger: '#C4342E' },
    'night-indigo': { primary: '#64D2FF', 'on-primary': '#06212B', ink: '#F5F4F8', success: '#3DDC84', flame: '#FFA24C', danger: '#FF6B6B' },
    'terracotta-paper': { primary: '#B4553A', 'on-primary': '#FFFFFF', ink: '#2A1D16', success: '#5C7A3E', flame: '#B98A2E', danger: '#A3302A' },
  }
  for (const [id, values] of Object.entries(expect)) {
    const vars = resolveVars(getTheme(id))
    for (const [k, v] of Object.entries(values)) assert.equal(vars[k], v, `${id}.${k}`)
    assert.ok(getTheme(id).glass)
    assert.equal((vars.wallpaper.match(/radial-gradient/g) || []).length >= 4, true)
    assert.match(vars.wallpaper, /linear-gradient\(168deg/)
  }
  assert.ok(getTheme('night-indigo').dark)
})

test('文档里的对比度实测值', () => {
  const near = (a, b) => Math.abs(a - b) < 0.02
  assert.ok(near(contrast('#0471DE', '#FFFFFF'), 4.75))
  // 文档写 16.84:1"在浅底"，实测在 #FFF4E3 上为 17.06，在最深的壁纸色 #FFB0C4 上为 10.84，均 ≥ 7
  assert.ok(contrast('#14121A', '#FFF4E3') >= 16.84)
  assert.ok(near(contrast('#0F766E', '#FFFFFF'), 5.47))
  assert.ok(near(contrast('#10201E', '#D8F0E4'), 14.03))
  assert.ok(near(contrast('#64D2FF', '#FFFFFF'), 1.72), '亮青配白字应只有 1.72:1')
  assert.ok(near(contrast('#06212B', '#64D2FF'), 9.68))
  assert.ok(near(contrast('#F5F4F8', '#1B1630'), 15.93))
  assert.ok(near(contrast('#B4553A', '#FFFFFF'), 4.88))
  assert.ok(near(contrast('#2A1D16', '#F7DCC4'), 12.44))
})

test('玻璃主题：色块上的文字与正文在内容层上全部 ≥ 4.5:1', () => {
  for (const id of GLASS) {
    const r = contrastReport(id)
    for (const key of ['onPrimary', 'inkOnContent', 'inkSoft', 'inkMute', 'primaryText', 'successText', 'onSuccess', 'onFlame', 'onDanger', 'onXp', 'toast']) {
      assert.ok(r[key] >= 4.5, `${id}.${key} = ${r[key].toFixed(2)}`)
    }
    assert.ok(r.inkOnWall >= 7, `${id} 正文在壁纸上 ${r.inkOnWall.toFixed(2)}`)
  }
})

test('深色主题对比度达标，主色上不用白字', () => {
  const r = contrastReport('dark')
  assert.ok(r.inkOnContent >= 12)
  assert.ok(r.inkSoft >= 7)
  assert.ok(r.inkMute >= 4.5)
  assert.ok(r.primaryText >= 4.5)
  assert.ok(r.onPrimary >= 4.5, `深色主色上的文字 ${r.onPrimary.toFixed(2)}`)
  assert.ok(r.toast >= 7)
  assert.match(themeCss(getTheme('dark')), /color-scheme:dark/)
})

test('壁纸自查：饱和度上限与色相数', () => {
  const apricot = wallpaperStats('apricot-dawn')
  assert.ok(apricot.maxSaturation <= 35, `晨光杏桃饱和度 ${apricot.maxSaturation}%`)
  assert.ok(apricot.hueCount >= 3, `晨光杏桃色相 ${apricot.hueCount}`)
  const mist = wallpaperStats('mist-pine')
  assert.ok(mist.maxSaturation <= 22, `雾松青饱和度 ${mist.maxSaturation}%`)
  assert.ok(mist.hueCount >= 3, `雾松青色相 ${mist.hueCount}`)
  for (const id of GLASS) assert.ok(wallpaperStats(id).inkLightnessSpan >= 40, `${id} 文字与壁纸明度跨度`)
})

test('未知主题回退到默认主题', () => {
  assert.equal(getTheme('nope').id, 'default')
})
