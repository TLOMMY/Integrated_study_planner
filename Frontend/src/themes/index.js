/**
 * 主题注册表。
 *
 * 界面所有颜色都来自 CSS 变量（见 tailwind.config.js），主题就是一组变量取值。
 * 新增一个主题只需在 THEMES 里加一个对象：
 *
 *   {
 *     id: 'sakura',               // 小写字母、数字、短横线，2–30 位（会同步到账号的 theme 字段）
 *     name: '樱花',                // 设置页显示的名称
 *     description: '柔和粉色调',     // 一句话说明
 *     dark: false,                 // 是否深色主题：决定 color-scheme（原生控件、滚动条）和缺省继承的基础主题
 *     glass: false,                // 是否启用 Liquid Glass（导航层玻璃 + 壁纸底色），见 style.css 的 data-glass 段
 *     extends: 'default',          // 可选：没写的变量从哪个主题继承，缺省时浅色继承 default、深色继承 dark
 *     preview: ['#F472B6', '#FFF1F5', '#1F2937'],   // 设置页卡片上的 3 个预览色块
 *     vars: { primary: '#F472B6', ... },             // 只写和基础主题不同的变量
 *   }
 *
 * 变量取值规则：#RRGGBB 是颜色，写成 --c-<名称>: R G B（Tailwind 透明度写法需要）；
 * 其他字符串（阴影、渐变、滤镜、rgba）原样写成 --<名称>。完整清单见下面的 BASE。
 * Liquid Glass 主题用 glassTheme() 按配色文档的数值生成（见文件后半部分）。
 */

/* ------------------------------------------------------------------ 颜色工具 */

/** '#4F6EF7' → '79 110 247'（Tailwind 透明度写法需要空格分隔的 RGB 通道）。 */
export const hexToChannels = (hex) => {
  let value = String(hex).trim().replace('#', '')
  if (!/^[0-9a-fA-F]{3}$|^[0-9a-fA-F]{6}$/.test(value)) return null
  if (value.length === 3) value = [...value].map((c) => c + c).join('')
  const n = Number.parseInt(value, 16)
  return `${(n >> 16) & 255} ${(n >> 8) & 255} ${n & 255}`
}
const isHex = (value) => hexToChannels(value) !== null
const toRgb = (hex) => hexToChannels(hex).split(' ').map(Number)
const toHex = (rgb) => `#${rgb.map((v) => Math.round(Math.max(0, Math.min(255, v))).toString(16).padStart(2, '0')).join('').toUpperCase()}`

/** 把 a 往 b 混合 t（0 = a，1 = b），返回 #RRGGBB。 */
export const mix = (a, b, t) => {
  const x = toRgb(a)
  const y = toRgb(b)
  return toHex(x.map((v, i) => v + (y[i] - v) * t))
}
const rgba = (hex, alpha) => `rgba(${toRgb(hex).join(', ')}, ${alpha})`

/** 相对亮度与对比度（WCAG 2.x）。 */
const luminance = (hex) => {
  const [r, g, b] = toRgb(hex).map((c) => {
    const v = c / 255
    return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4
  })
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}
export const contrast = (a, b) => {
  const [x, y] = [luminance(a), luminance(b)].sort((m, n) => n - m)
  return (x + 0.05) / (y + 0.05)
}

/** fg 在一组底色上的最低对比度。 */
const minContrast = (fg, backgrounds) => Math.min(...backgrounds.map((bg) => contrast(fg, bg)))
/** 把 fg 逐步往 toward 推，直到在所有底色上都达到 target（最多推到 toward 本身）。 */
const ensure = (fg, backgrounds, target, toward) => {
  for (let i = 0; i <= 20; i++) {
    const c = mix(fg, toward, i * 0.05)
    if (minContrast(c, backgrounds) >= target) return c
  }
  return toward
}
/** 候选前景色里对比度最高的那个。 */
const bestOn = (bg, candidates) => candidates.reduce((best, c) => (contrast(c, bg) > contrast(best, bg) ? c : best))

/** HSV 饱和度（0–100）与色相（0–360），用于壁纸自查。 */
const hsv = (hex) => {
  const [r, g, b] = toRgb(hex).map((c) => c / 255)
  const max = Math.max(r, g, b)
  const min = Math.min(r, g, b)
  const d = max - min
  let h = 0
  if (d) h = max === r ? ((g - b) / d) % 6 : max === g ? (b - r) / d + 2 : (r - g) / d + 4
  return { h: (h * 60 + 360) % 360, s: max ? (d / max) * 100 : 0, v: max * 100 }
}
/** CIE L*（0–100），用于"明度跨度"。 */
const lightness = (hex) => {
  const y = luminance(hex)
  return y > 216 / 24389 ? 116 * Math.cbrt(y) - 16 : (24389 / 27) * y
}

/* ------------------------------------------------------------------ 默认主题（与 v3 配色完全一致） */

const BASE = {
  // 品牌主色：按钮、选中态、链接
  primary: '#4F6EF7',
  'primary-dark': '#3B57E0', // 主色按钮悬停
  'primary-light': '#EEF1FE', // 选中 chip、浅色主色底
  'primary-soft': '#C7D2FE', // 主色描边、未选中柱状图
  // 页面底色 / 卡片底色
  background: '#F5F7FB',
  surface: '#FFFFFF',
  // 文字与分隔线
  ink: '#0F172A',
  'ink-soft': '#475569',
  'ink-mute': '#94A3B8',
  'ink-line': '#E2E8F0',
  // 语义色：primary 进行中 / 主操作；success 已完成；flame 被打断 / 超时 / 连续打卡；danger 删除
  flame: '#FF8A00',
  'flame-light': '#FFF4E5',
  'flame-glow': '#FCD34D', // 成就徽章渐变的亮端（from-flame-glow to-flame）
  xp: '#8B5CF6',
  'xp-light': '#F3EEFF',
  success: '#10B981',
  'success-light': '#ECFDF5',
  danger: '#EF4444',
  'danger-light': '#FEF2F2',
  'danger-soft': '#FEE2E2', // 危险按钮悬停
  // "色块上的文字"：bg-primary 上用 text-on-primary，bg-success 上用 text-on-success……
  // 亮色强调色（如夜读靛的亮青）上白字看不清，所以不能写死 text-white
  'on-primary': '#FFFFFF',
  'on-success': '#FFFFFF',
  'on-flame': '#FFFFFF',
  'on-danger': '#FFFFFF',
  'on-xp': '#FFFFFF',
  // 语义色当文字用时的颜色（text-primary / text-success……）。强调色本身对比度不够时，主题可单独压深
  'primary-text': '#4F6EF7',
  'success-text': '#10B981',
  'flame-text': '#FF8A00',
  'danger-text': '#EF4444',
  // 反色块（Toast、专注小条、选中的周次）：底色与其上文字
  inverse: '#0F172A',
  'inverse-ink': '#FFFFFF',
  'inverse-accent': '#C7D2FE', // 反色块上的主色图标
  // 遮罩（弹窗背后的半透明层，使用时带透明度，如 bg-scrim/45）
  scrim: '#0F172A',
  // 首页概览卡、登录页渐变的中间色（from-primary via-hero to-xp）
  hero: '#5B6CF9',
  // 专注页沉浸式背景（深色渐变）与其上白色按钮的文字色
  'deep-from': '#1E2A5E',
  'deep-via': '#26357A',
  'deep-to': '#3B2C7A',
  'deep-ink': '#26357A',
  // 专注页进度环渐变
  'ring-start': '#9DB0FF',
  'ring-end': '#FFB86B',
  // 图表：坐标轴文字、网格线、淡色刻度、数值标签
  'chart-axis': '#94A3B8',
  'chart-grid': '#F1F5F9',
  'chart-faint': '#CBD5E1',
  'chart-label': '#64748B',
  // 分类配色（饼图、彩纸等），依次取用
  'chart-1': '#4F6EF7',
  'chart-2': '#8B5CF6',
  'chart-3': '#10B981',
  'chart-4': '#FF8A00',
  'chart-5': '#06B6D4',
  'chart-6': '#94A3B8',
  'chart-7': '#F43F5E',
  // 窗口底色（平板"手机框"演示时手机外面的区域）与两处光晕
  page: '#E8ECF6',
  'page-glow-1': '#DFE6FF',
  'page-glow-2': '#F3E8FF',
  // 平板演示时的手机边框
  'bezel-inner': '#0F172A',
  'bezel-outer': '#334155',
  // 骨架屏、滚动条
  'skeleton-base': '#EEF1F6',
  'skeleton-shine': '#F8FAFC',
  scrollbar: '#CBD5E1',
  // 增强对比度（系统 prefers-contrast: more 或设置页开关）时替换的次要文字与分隔线
  'hc-ink-mute': '#475569',
  'hc-ink-line': '#94A3B8',
  // ---- 以下为原样输出的变量（不是 #RRGGBB）
  // 阴影
  'shadow-soft': '0 6px 24px -10px rgba(15, 23, 42, 0.18)',
  'shadow-lift': '0 18px 40px -16px rgba(79, 110, 247, 0.45)',
  'shadow-phone': '0 40px 80px -30px rgba(30, 41, 99, 0.45)',
  // 内容层（bg-surface）的不透明度：普通主题为 1；玻璃主题按文档的"内容层标准材质"取值
  'surface-alpha': '1',
  // "显示边框"开关打开时的描边色
  'outline-strong': 'rgba(15, 23, 42, 0.7)',
}

/** 深色主题：相对 surface 的对比度 ink 13.6:1、ink-soft 8.1:1、ink-mute 4.6:1、主色 4.7:1（自检见 utils/themes.test.js）。 */
const DARK = {
  primary: '#6382FF',
  'primary-dark': '#5272F5',
  'primary-light': '#1C2748',
  'primary-soft': '#3A4C8F',
  background: '#0B1120',
  surface: '#182133',
  ink: '#E7ECF5',
  'ink-soft': '#AEB8CA',
  'ink-mute': '#7F8AA0',
  'ink-line': '#2A3449',
  flame: '#FF9A2E',
  'flame-light': '#33230F',
  xp: '#A48BFA',
  'xp-light': '#251C45',
  success: '#2DD4A0',
  'success-light': '#0F2E27',
  danger: '#F87171',
  'danger-light': '#3A1619',
  'danger-soft': '#4C1D22',
  // 深色下强调色都较亮，色块上的文字用深色（白字只有 1.9–3.4:1）
  'on-primary': '#0A1028',
  'on-success': '#05261C',
  'on-flame': '#2B1700',
  'on-danger': '#2A0A0A',
  'on-xp': '#1A1033',
  'primary-text': '#6382FF',
  'success-text': '#2DD4A0',
  'flame-text': '#FF9A2E',
  'danger-text': '#F87171',
  inverse: '#334155',
  'inverse-ink': '#F8FAFC',
  'inverse-accent': '#A5B4FC',
  scrim: '#000000',
  hero: '#5868E8',
  'deep-from': '#0E1430',
  'deep-via': '#161F4A',
  'deep-to': '#251B4F',
  'deep-ink': '#1A2456',
  'ring-start': '#9DB0FF',
  'ring-end': '#FFB86B',
  'chart-axis': '#7F8AA0',
  'chart-grid': '#232C3F',
  'chart-faint': '#59647A',
  'chart-label': '#AEB8CA',
  'chart-1': '#6382FF',
  'chart-2': '#A48BFA',
  'chart-3': '#2DD4A0',
  'chart-4': '#FF9A2E',
  'chart-5': '#22D3EE',
  'chart-6': '#7F8AA0',
  'chart-7': '#FB7185',
  page: '#05080F',
  'page-glow-1': '#151F45',
  'page-glow-2': '#24163D',
  'bezel-inner': '#000000',
  'bezel-outer': '#2A3449',
  'skeleton-base': '#1C2539',
  'skeleton-shine': '#26304A',
  scrollbar: '#3A455C',
  'hc-ink-mute': '#AEB8CA',
  'hc-ink-line': '#56627A',
  // 深色下阴影几乎看不见，加一圈极淡的内描边让卡片、分段控件的选中块浮起来
  'shadow-soft': '0 6px 24px -10px rgba(0, 0, 0, 0.6), inset 0 0 0 1px rgba(255, 255, 255, 0.08)',
  'shadow-lift': '0 18px 40px -16px rgba(99, 130, 255, 0.4)',
  'shadow-phone': '0 40px 80px -30px rgba(0, 0, 0, 0.8)',
  'outline-strong': 'rgba(231, 236, 245, 0.7)',
}
/* ------------------------------------------------------------------ Liquid Glass 主题 */

/**
 * 按配色文档（四套 Liquid Glass 主题规格）的数值生成一套主题。
 * spec 里的值全部照抄文档；文档没给的派生色（悬停、浅底、分隔线、图表……）由强调色 / 文字色 / 壁纸混合得到，
 * 并用 ensure() 保证在内容层上的对比度达标（正文 ≥ 4.5:1）。
 */
function glassTheme(spec) {
  const { dark, accent, onAccent, ink, ink2Alpha, walls, bases, semantic, xp, content, glass, a11y } = spec
  const paper = dark ? null : '#FFFFFF'
  // 内容层的实际底色：内容层材质叠在每一处壁纸色上（用于对比度计算与实色派生）
  const contentOn = (wall) => (dark ? mix(wall, content.color, content.alpha) : mix(wall, paper, content.alpha))
  const surfaces = [...walls, ...bases].map(contentOn)
  // 内容层颜色：浅色按文档为白色（实际以 surface-alpha 透明度叠在壁纸上），深色为文档的 --surface 色
  const surfaceSolid = dark ? content.color : paper
  const field = dark ? mix(bases[1], '#FFFFFF', 0.06) : mix(bases[0], ink, 0.035)
  const fieldSurfaces = [field, ...surfaces]

  // 次要文字：文档给的 ink-2 透明度先合成，再确保 ≥ 4.5:1；更淡的一级（ink-mute）同样要 ≥ 4.5:1
  const inkSoft = ensure(mix(surfaceSolid, ink, ink2Alpha), fieldSurfaces, 4.6, ink)
  // ink-mute：在 ink-soft 基础上尽量淡一点，但不低于 4.5:1
  let inkMute = inkSoft
  for (let t = 0.02; t <= 0.3; t += 0.02) {
    const c = mix(inkSoft, surfaceSolid, t)
    if (minContrast(c, fieldSurfaces) < 4.5) break
    inkMute = c
  }
  const line = mix(surfaceSolid, ink, dark ? 0.16 : 0.12)

  // 语义色当文字用时，在内容层上也要 ≥ 4.5:1（强调色本身保持文档数值，只压深 / 提亮"文字版"）
  const textOf = (color) => ensure(color, fieldSurfaces, 4.5, ink)
  const onOf = (color) => bestOn(color, dark ? [mix(color, '#000000', 0.82), ink] : ['#FFFFFF', ink])
  const tint = (color, t) => (dark ? mix(surfaceSolid, color, t) : mix('#FFFFFF', color, t))

  return {
    primary: accent,
    'primary-dark': dark ? mix(accent, '#FFFFFF', 0.18) : mix(accent, ink, 0.16),
    'primary-light': tint(accent, dark ? 0.2 : 0.12),
    'primary-soft': tint(accent, dark ? 0.42 : 0.32),
    background: field,
    surface: surfaceSolid,
    ink,
    'ink-soft': inkSoft,
    'ink-mute': inkMute,
    'ink-line': line,
    flame: semantic.flame,
    'flame-light': tint(semantic.flame, dark ? 0.2 : 0.14),
    'flame-glow': mix(semantic.flame, dark ? ink : '#FFFFFF', 0.4),
    xp,
    'xp-light': tint(xp, dark ? 0.2 : 0.13),
    success: semantic.success,
    'success-light': tint(semantic.success, dark ? 0.2 : 0.13),
    danger: semantic.danger,
    'danger-light': tint(semantic.danger, dark ? 0.2 : 0.1),
    'danger-soft': tint(semantic.danger, dark ? 0.3 : 0.18),
    'on-primary': onAccent,
    'on-success': onOf(semantic.success),
    'on-flame': onOf(semantic.flame),
    'on-danger': onOf(semantic.danger),
    'on-xp': onOf(xp),
    'primary-text': textOf(accent),
    'success-text': textOf(semantic.success),
    'flame-text': textOf(semantic.flame),
    'danger-text': textOf(semantic.danger),
    inverse: dark ? mix(content.color, '#FFFFFF', 0.16) : mix(ink, accent, 0.08),
    'inverse-ink': dark ? ink : mix(bases[0], '#FFFFFF', 0.6),
    'inverse-accent': dark ? accent : mix(accent, '#FFFFFF', 0.6),
    scrim: dark ? mix(bases[2], '#000000', 0.5) : ink,
    hero: mix(accent, xp, 0.5),
    // 专注页始终是深色沉浸背景：浅色主题从正文墨色出发，深色主题从壁纸最深的底色出发
    'deep-from': mix(dark ? bases[2] : ink, accent, 0.22),
    'deep-via': mix(dark ? bases[1] : ink, mix(accent, xp, 0.5), 0.28),
    'deep-to': mix(dark ? bases[0] : ink, xp, 0.32),
    'deep-ink': mix(dark ? bases[2] : ink, accent, 0.35),
    'ring-start': mix(accent, '#FFFFFF', 0.45),
    'ring-end': mix(semantic.flame, '#FFFFFF', 0.35),
    'chart-axis': inkMute,
    'chart-grid': mix(surfaceSolid, ink, 0.07),
    'chart-faint': mix(surfaceSolid, ink, 0.3),
    'chart-label': inkSoft,
    'chart-1': accent,
    'chart-2': xp,
    'chart-3': semantic.success,
    'chart-4': semantic.flame,
    'chart-5': mix(accent, walls[2], 0.5),
    'chart-6': inkMute,
    'chart-7': semantic.danger,
    page: bases[1],
    'page-glow-1': walls[0],
    'page-glow-2': walls[3],
    'skeleton-base': mix(surfaceSolid, ink, 0.06),
    'skeleton-shine': mix(surfaceSolid, ink, 0.02),
    scrollbar: mix(surfaceSolid, ink, 0.25),
    'hc-ink-mute': inkSoft,
    'hc-ink-line': mix(surfaceSolid, ink, 0.45),
    'shadow-soft': `0 8px 24px -12px ${rgba(ink, dark ? 0.7 : 0.22)}`,
    'shadow-lift': `0 16px 36px -16px ${rgba(accent, dark ? 0.5 : 0.5)}`,
    // ---- 原样输出：壁纸、玻璃、内容层、无障碍三态
    wallpaper: [
      ...spec.wallLayers.map((l, i) => `radial-gradient(${l} ${walls[i]} 0%, transparent ${spec.wallStops[i]})`),
      ...(spec.extraLayer ? [spec.extraLayer] : []),
      `linear-gradient(168deg, ${bases[0]} 0%, ${bases[1]} ${spec.baseMid}, ${bases[2]} 100%)`,
    ].join(', '),
    'glass-fill': glass.fill,
    'glass-stroke': glass.stroke,
    'glass-filter': glass.filter,
    'glass-shadow': glass.shadow,
    'glass-sheen': glass.sheen,
    'content-filter': content.filter,
    'surface-alpha': String(content.alpha),
    'rt-glass-fill': a11y.reduceFill,
    'rt-surface-alpha': dark ? '0.96' : '0.97',
    'hc-glass-stroke': a11y.contrastStroke,
    'hc-glass-fill': a11y.contrastFill,
    'outline-strong': a11y.outline,
  }
}

/** 文档里每套主题的原始数值。 */
const GLASS_SPECS = {
  'apricot-dawn': {
    dark: false,
    accent: '#0471DE',
    onAccent: '#FFFFFF',
    ink: '#14121A',
    ink2Alpha: 0.62,
    walls: ['#FFD9A8', '#FFB0C4', '#B7D6FF', '#E4C4FF'],
    bases: ['#FFF4E3', '#F4E7FF', '#E4EFFF'],
    wallLayers: ['120% 80% at 6% 4%,', '100% 70% at 96% 10%,', '95% 70% at 14% 96%,', '120% 90% at 92% 86%,'],
    wallStops: ['55%', '55%', '62%', '62%'],
    baseMid: '46%',
    semantic: { success: '#34C759', flame: '#E8833A', danger: '#D93A3A' },
    xp: '#6E5BC4', // 等级 / XP：取壁纸紫的低饱和深色，避免第二个高饱和强调色
    content: { alpha: 0.66, filter: 'blur(32px) saturate(150%)' },
    glass: {
      fill: 'rgba(255, 255, 255, 0.16)',
      stroke: 'rgba(255, 255, 255, 0.52)',
      filter: 'blur(22px) saturate(185%) brightness(1.09)',
      shadow: 'inset 0 1px 0 rgba(255,255,255,.62), inset 0 -1px 0 rgba(255,255,255,.30), inset 0 0 22px rgba(255,255,255,.14), 0 10px 28px -12px rgba(28,14,48,.50), 0 2px 7px -3px rgba(28,14,48,.30)',
      sheen: 'radial-gradient(125% 95% at 16% -12%, rgba(255,255,255,.6), transparent 58%)',
    },
    a11y: { reduceFill: 'rgba(250, 250, 252, 0.94)', contrastStroke: 'rgba(0, 0, 0, 0.55)', contrastFill: 'rgba(255, 255, 255, 0.42)', outline: 'rgba(0, 0, 0, 0.7)' },
  },
  'mist-pine': {
    dark: false,
    accent: '#0F766E',
    onAccent: '#FFFFFF',
    ink: '#10201E',
    ink2Alpha: 0.6,
    walls: ['#D8F0E4', '#CFE8EC', '#DCE6F6', '#E6F2E4'],
    bases: ['#F2FAF6', '#EAF3F2', '#E9EFF9'],
    wallLayers: ['120% 80% at 8% 6%,', '100% 70% at 94% 12%,', '95% 70% at 12% 96%,', '120% 90% at 90% 88%,'],
    wallStops: ['55%', '55%', '62%', '62%'],
    baseMid: '48%',
    semantic: { success: '#2E9E5B', flame: '#C97A32', danger: '#C4342E' },
    xp: '#4F6A8C', // 低饱和石板蓝，不另加鲜艳色
    content: { alpha: 0.68, filter: 'blur(30px)' },
    glass: {
      fill: 'rgba(255, 255, 255, 0.18)',
      stroke: 'rgba(255, 255, 255, 0.55)',
      filter: 'blur(24px) saturate(160%) brightness(1.06)',
      shadow: 'inset 0 1px 0 rgba(255,255,255,.65), inset 0 -1px 0 rgba(255,255,255,.28), 0 10px 26px -14px rgba(12,32,30,.45)',
      sheen: 'radial-gradient(125% 95% at 16% -12%, rgba(255,255,255,.55), transparent 58%)',
    },
    // 文档未单列三态数值：沿用晨光杏桃的做法，描边 / 描线色换成本主题的文字色
    a11y: { reduceFill: 'rgba(246, 250, 248, 0.94)', contrastStroke: 'rgba(16, 32, 30, 0.55)', contrastFill: 'rgba(255, 255, 255, 0.42)', outline: 'rgba(16, 32, 30, 0.7)' },
  },
  'night-indigo': {
    dark: true,
    accent: '#64D2FF',
    onAccent: '#06212B',
    ink: '#F5F4F8',
    ink2Alpha: 0.66,
    walls: ['#3B2A5E', '#7A2F52', '#10365C', '#14364A'],
    bases: ['#191325', '#1B1630', '#0F1626'],
    wallLayers: ['120% 80% at 8% 6%,', '100% 70% at 94% 12%,', '95% 70% at 12% 94%,', '120% 90% at 90% 88%,'],
    wallStops: ['58%', '58%', '62%', '62%'],
    // 文档建议的"桌面反射"底光
    extraLayer: 'radial-gradient(90% 60% at 50% 112%, rgba(255,255,255,.18), transparent 60%)',
    baseMid: '46%',
    semantic: { success: '#3DDC84', flame: '#FFA24C', danger: '#FF6B6B' },
    xp: '#B9A6F2', // 提亮、降饱和的淡紫
    content: { color: '#1E182C', alpha: 0.42, filter: 'blur(28px)' },
    glass: {
      fill: 'rgba(255, 255, 255, 0.09)',
      stroke: 'rgba(255, 255, 255, 0.22)',
      filter: 'blur(26px) saturate(150%) brightness(1.04)',
      shadow: 'inset 0 1px 0 rgba(255,255,255,.28), inset 0 -1px 0 rgba(255,255,255,.10), 0 12px 30px -14px rgba(0,0,0,.80)',
      sheen: 'radial-gradient(125% 95% at 16% -12%, rgba(255,255,255,.35), transparent 58%)',
    },
    a11y: { reduceFill: 'rgba(28, 24, 36, 0.94)', contrastStroke: 'rgba(255, 255, 255, 0.6)', contrastFill: 'rgba(30, 24, 44, 0.86)', outline: 'rgba(245, 244, 248, 0.75)' },
  },
  'terracotta-paper': {
    dark: false,
    accent: '#B4553A',
    onAccent: '#FFFFFF',
    ink: '#2A1D16',
    ink2Alpha: 0.6,
    walls: ['#F7DCC4', '#F2C3B0', '#EBD9BE', '#E8C9C0'],
    bases: ['#FBF1E4', '#F6E6D8', '#F1DED4'],
    wallLayers: ['120% 80% at 6% 4%,', '100% 70% at 96% 10%,', '95% 70% at 14% 96%,', '120% 90% at 92% 86%,'],
    wallStops: ['55%', '55%', '62%', '62%'],
    baseMid: '46%',
    semantic: { success: '#5C7A3E', flame: '#B98A2E', danger: '#A3302A' },
    xp: '#7A5A44', // 暖棕：禁止冷色或紫蓝强调
    content: { alpha: 0.7, filter: 'blur(26px)' },
    glass: {
      fill: 'rgba(255, 255, 255, 0.14)',
      stroke: 'rgba(255, 255, 255, 0.48)',
      filter: 'blur(18px) saturate(200%) brightness(1.05)',
      shadow: 'inset 0 1px 0 rgba(255,255,255,.70), inset 0 -1px 0 rgba(255,255,255,.32), 0 8px 22px -14px rgba(48,28,18,.40)',
      sheen: 'radial-gradient(125% 95% at 14% -12%, rgba(255,255,255,.62), transparent 55%)',
    },
    a11y: { reduceFill: 'rgba(251, 246, 240, 0.94)', contrastStroke: 'rgba(42, 29, 22, 0.55)', contrastFill: 'rgba(255, 255, 255, 0.42)', outline: 'rgba(42, 29, 22, 0.7)' },
  },
}
/* ------------------------------------------------------------------ 注册表 */

export const THEMES = [
  { id: 'default', name: '默认', description: '清爽的蓝紫配色', dark: false, preview: ['#4F6EF7', '#F5F7FB', '#8B5CF6'], vars: BASE },
  { id: 'dark', name: '深色', description: '夜间护眼，低亮度', dark: true, preview: ['#6382FF', '#0B1120', '#A48BFA'], vars: DARK },
  { id: 'apricot-dawn', name: '晨光杏桃', description: '暖色晨光 · 玻璃质感', dark: false, glass: true, preview: ['#0471DE', '#FFF4E3', '#FFB0C4'], vars: glassTheme(GLASS_SPECS['apricot-dawn']) },
  { id: 'mist-pine', name: '雾松青', description: '低饱和 · 长时间不累眼', dark: false, glass: true, preview: ['#0F766E', '#F2FAF6', '#CFE8EC'], vars: glassTheme(GLASS_SPECS['mist-pine']) },
  { id: 'night-indigo', name: '夜读靛', description: '深色玻璃 · 夜间阅读', dark: true, glass: true, preview: ['#64D2FF', '#1B1630', '#7A2F52'], vars: glassTheme(GLASS_SPECS['night-indigo']) },
  { id: 'terracotta-paper', name: '赤陶纸', description: '暖土色 · 印刷纸感', dark: false, glass: true, preview: ['#B4553A', '#FBF1E4', '#F2C3B0'], vars: glassTheme(GLASS_SPECS['terracotta-paper']) },
  // ↓ 在这里追加自定义主题（结构见文件顶部注释）
]

/** "跟随系统"：系统深色时用 dark，否则用 default。 */
export const SYSTEM_THEME = { id: 'system', name: '跟随系统', description: '随系统的浅色 / 深色设置切换' }
export const DEFAULT_THEME_ID = 'default'

const byId = (id) => THEMES.find((theme) => theme.id === id)

/** 按 id 取主题；不存在时回退到默认主题。 */
export const getTheme = (id) => byId(id) || byId(DEFAULT_THEME_ID)

/** 主题的完整变量表（沿 extends 链合并，缺的变量用默认主题补齐）。 */
export const resolveVars = (theme, seen = new Set()) => {
  if (!theme || seen.has(theme.id)) return { ...BASE }
  seen.add(theme.id)
  const parentId = theme.extends || (theme.id === DEFAULT_THEME_ID || theme.id === 'dark' ? null : theme.dark ? 'dark' : DEFAULT_THEME_ID)
  const parent = parentId ? resolveVars(byId(parentId), seen) : { ...BASE }
  return { ...parent, ...theme.vars }
}

/** 生成写进 <style> 的变量声明：#RRGGBB → --c-xxx: R G B；其他值 → --xxx: 原值。 */
export const themeCss = (theme) => {
  const vars = resolveVars(theme)
  const lines = Object.entries(vars).map(([key, value]) => (isHex(value) ? `--c-${key}: ${hexToChannels(value)};` : `--${key}: ${value};`))
  return `:root{${lines.join('')}color-scheme:${theme.dark ? 'dark' : 'light'};}`
}

/** 所有颜色变量名（#RRGGBB 的那些），tailwind.config.js 与测试使用。 */
export const COLOR_KEYS = Object.keys(BASE).filter((key) => isHex(BASE[key]))

/** 玻璃主题必须提供的原样变量。 */
export const GLASS_KEYS = ['wallpaper', 'glass-fill', 'glass-stroke', 'glass-filter', 'glass-shadow', 'glass-sheen', 'content-filter', 'surface-alpha', 'rt-glass-fill', 'rt-surface-alpha', 'hc-glass-stroke', 'hc-glass-fill', 'outline-strong']

/**
 * 壁纸自查：4 个径向色 + 3 个线性色的 HSV 最大饱和度、CIE L* 明度跨度（壁纸内部、以及壁纸与正文文字之间）、
 * 色相数（饱和度 ≥ 5% 的颜色落在几个 30° 色相区间里）。
 */
export const wallpaperStats = (id) => {
  const spec = GLASS_SPECS[id]
  if (!spec) return null
  const colors = [...spec.walls, ...spec.bases]
  const ls = colors.map(lightness)
  const clusters = new Set(colors.map(hsv).filter((c) => c.s >= 5).map((c) => Math.floor(c.h / 30)))
  return {
    maxSaturation: Math.round(Math.max(...colors.map((c) => hsv(c).s))),
    wallLightnessSpan: Math.round(Math.max(...ls) - Math.min(...ls)),
    inkLightnessSpan: Math.round(Math.max(...ls.map((l) => Math.abs(l - lightness(spec.ink))))),
    hueCount: clusters.size,
  }
}

/** 测试与报告用：每套主题的关键对比度。 */
export const contrastReport = (id) => {
  const theme = getTheme(id)
  const v = resolveVars(theme)
  const spec = GLASS_SPECS[id]
  // 正文所在的实际底色：玻璃主题为"内容层叠在每一处壁纸色上"，普通主题为 surface 与 background
  const grounds = spec
    ? [...spec.walls, ...spec.bases].map((w) => mix(w, spec.dark ? spec.content.color : '#FFFFFF', spec.content.alpha)).concat(v.background)
    : [v.surface, v.background]
  return {
    onPrimary: contrast(v['on-primary'], v.primary),
    inkOnWall: spec ? minContrast(v.ink, [...spec.walls, ...spec.bases]) : contrast(v.ink, v.background),
    inkOnContent: minContrast(v.ink, grounds),
    inkSoft: minContrast(v['ink-soft'], grounds),
    inkMute: minContrast(v['ink-mute'], grounds),
    primaryText: minContrast(v['primary-text'], grounds),
    successText: minContrast(v['success-text'], grounds),
    onSuccess: contrast(v['on-success'], v.success),
    onFlame: contrast(v['on-flame'], v.flame),
    onDanger: contrast(v['on-danger'], v.danger),
    onXp: contrast(v['on-xp'], v.xp),
    toast: contrast(v['inverse-ink'], v.inverse),
  }
}