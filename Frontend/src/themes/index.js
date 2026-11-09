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

/* ------------------------------------------------------------------ 默认主题：莫兰迪 × 珊瑚 */

/**
 * 默认主题的色板（原型修改意见指定的数值，原样使用）。
 * 珊瑚是唯一的强调色：任务块、主按钮、选中态。空闲蓝、课程沙色只用在日程时间轴；火苗、金徽只用于激励。
 * 不用纯白：最亮的颜色是卡片色 #FBF9F4。
 */
const CORAL = {
  // 强调色梯：浅底 → 描边 → 中 → 主色 → 按压
  primary: '#D85A30',
  'primary-dark': '#B54A28', // 按压、悬停
  'primary-light': '#FAECE7', // 选中 chip、浅珊瑚底
  'primary-soft': '#F5C4B3', // 完成的任务块、描边
  'primary-mid': '#F0997B', // 珠点轴的任务段、优先级"中"
  'primary-text': '#B54A28', // 珊瑚色的文字（#D85A30 在浅底上对比度不到 4.5）
  // 底盘
  background: '#F4F1EA',
  surface: '#FBF9F4',
  ink: '#2C2C2A',
  'ink-soft': '#6B675E',
  'ink-mute': '#6B675E',
  'ink-line': '#E5E0D4',
  bead: '#CFC9BA', // 时间轴珠点的中性色
  // 空闲段（只在日程时间轴）
  idle: '#DCE8F0',
  'idle-bead': '#9CC3E8',
  'idle-ink': '#4A7BA6',
  link: '#185FA5',
  // 课程块：日程页用中性沙色，课表页用下面的分科色
  course: '#DCD9C8',
  'course-line': '#B8B2A0',
  'course-icon': '#8A867B',
  // 激励：火苗是全 App 唯一允许渐变的地方（flame-glow → flame-deep），升级用金徽
  flame: '#F2743F',
  'flame-light': '#FAECE7',
  'flame-glow': '#FF9D5C',
  'flame-deep': '#E8542F',
  gold: '#D9A441',
  'gold-light': '#F7EBD3',
  // 等级 / XP 的文字与小图标：用珊瑚深字，不另加紫色
  xp: '#993C1D',
  'xp-light': '#FAECE7',
  // 功能色：完成绿只用在勾上，不铺块
  success: '#6F9B4F',
  'success-light': '#E8ECDF',
  danger: '#C4554D',
  'danger-light': '#F7E4E0',
  'danger-soft': '#F0D3CD',
  // 色块上的文字："on-primary" 用卡片色而不是纯白
  'on-primary': '#FBF9F4',
  'on-success': '#2C2C2A',
  'on-flame': '#2C2C2A',
  'on-danger': '#FBF9F4',
  'on-xp': '#FBF9F4',
  // 反色块（Toast、撤销条）：墨色底 + 底盘色字
  inverse: '#2C2C2A',
  'inverse-ink': '#F4F1EA',
  'inverse-accent': '#F0997B',
  scrim: '#2C2C2A',
  hero: '#D85A30',
  // 专注页：暖墨色底，三个停靠点几乎同色，看起来是一整块
  'deep-from': '#2C2925',
  'deep-via': '#2F2A26',
  'deep-to': '#332B26',
  'deep-ink': '#993C1D',
  'ring-start': '#F5C4B3',
  'ring-end': '#F2743F',
  // 图表：珊瑚 / 空闲蓝 / 完成绿 / 金 / 课程沙 / 灰 / 逾期红
  'chart-axis': '#6B675E',
  'chart-grid': '#ECE8DF',
  'chart-faint': '#CFC9BA',
  'chart-label': '#6B675E',
  'chart-1': '#D85A30',
  'chart-2': '#4A7BA6',
  'chart-3': '#6F9B4F',
  'chart-4': '#D9A441',
  'chart-5': '#9CC3E8',
  'chart-6': '#B8B2A0',
  'chart-7': '#C4554D',
  page: '#ECE8DF',
  'page-glow-1': '#F5E4DA',
  'page-glow-2': '#E3E9EC',
  'bezel-inner': '#2C2C2A',
  'bezel-outer': '#6B675E',
  'skeleton-base': '#ECE8DF',
  'skeleton-shine': '#F7F4EE',
  scrollbar: '#CFC9BA',
  'hc-ink-mute': '#4A4741',
  'hc-ink-line': '#B8B2A0',
}

/**
 * 课表页的分科色（只在课表页用；日程页课程块保持沙色，只加 6px 分科色点）。
 * subj-*：块底色；subj-*-ink：教室文字、色点。课名一律用墨色。
 */
export const SUBJECTS = [
  { key: 'sci', label: '理工', bg: '#D5E2EA', ink: '#5B84A8' },
  { key: 'bio', label: '生化', bg: '#D8E0CE', ink: '#6E8B54' },
  { key: 'his', label: '史地', bg: '#E6D9C3', ink: '#A0793F' },
  { key: 'art', label: '文艺', bg: '#E3D3D3', ink: '#A56A6A' },
  { key: 'soc', label: '社科', bg: '#DCD5E4', ink: '#7E6C9C' },
  { key: 'def', label: '其他', bg: '#DCD9C8', ink: '#8A867B' },
]
const subjectVars = (map) => Object.fromEntries(SUBJECTS.flatMap((s) => {
  const { bg, ink } = map(s)
  return [[`subj-${s.key}`, bg], [`subj-${s.key}-ink`, ink]]
}))
const LIGHT_SUBJECTS = subjectVars((s) => ({ bg: s.bg, ink: s.ink }))

/**
 * 暖深色：深底上珊瑚提亮一档，不加块投影；分科色按"深底混一点科目色 + 提亮的科目字色"生成。
 * 相对内容层的对比度：ink 14:1、ink-soft 8:1、ink-mute 5.6:1、珊瑚字 7:1（自检见 utils/themes.test.js）。
 */
const WARM_DARK = {
  primary: '#E2714A',
  'primary-dark': '#C85E3A',
  'primary-light': '#3A2419',
  'primary-soft': '#6B3522',
  'primary-mid': '#B4573A',
  'primary-text': '#F2B49A',
  background: '#1C1A17',
  surface: '#26231F',
  ink: '#EEE9E1',
  'ink-soft': '#C9C2B6',
  'ink-mute': '#A39D91',
  'ink-line': '#38342E',
  bead: '#4E493F',
  idle: '#1F2A33',
  'idle-bead': '#4F7395',
  'idle-ink': '#8DB4D6',
  link: '#9CC3E8',
  course: '#36322B',
  'course-line': '#545046',
  'course-icon': '#A39D91',
  flame: '#F2743F',
  'flame-light': '#3A2419',
  'flame-glow': '#FF9D5C',
  'flame-deep': '#E8542F',
  gold: '#D9A441',
  'gold-light': '#3A3120',
  xp: '#F2B49A',
  'xp-light': '#3A2419',
  success: '#8DB46E',
  'success-light': '#28301F',
  danger: '#E07A70',
  'danger-light': '#3A2220',
  'danger-soft': '#4A2A27',
  'on-primary': '#1C1A17',
  'on-success': '#1C1A17',
  'on-flame': '#1C1A17',
  'on-danger': '#1C1A17',
  'on-xp': '#1C1A17',
  inverse: '#3D3832',
  'inverse-ink': '#EEE9E1',
  'inverse-accent': '#F0997B',
  scrim: '#000000',
  hero: '#E2714A',
  'deep-from': '#1A1815',
  'deep-via': '#1C1916',
  'deep-to': '#1F1B17',
  'deep-ink': '#C85E3A',
  'ring-start': '#B4573A',
  'ring-end': '#F2743F',
  'chart-axis': '#A39D91',
  'chart-grid': '#312D28',
  'chart-faint': '#4E493F',
  'chart-label': '#C9C2B6',
  'chart-1': '#E2714A',
  'chart-2': '#8DB4D6',
  'chart-3': '#8DB46E',
  'chart-4': '#D9A441',
  'chart-5': '#4F7395',
  'chart-6': '#7A7468',
  'chart-7': '#E07A70',
  page: '#141210',
  'page-glow-1': '#2E2018',
  'page-glow-2': '#1A2128',
  'bezel-inner': '#000000',
  'bezel-outer': '#38342E',
  'skeleton-base': '#2E2A25',
  'skeleton-shine': '#38342E',
  scrollbar: '#4E493F',
  'hc-ink-mute': '#C9C2B6',
  'hc-ink-line': '#6B655A',
}
const DARK_SUBJECTS = subjectVars((s) => ({ bg: mix('#26231F', s.ink, 0.22), ink: mix(s.ink, '#FFFFFF', 0.38) }))

/* ------------------------------------------------------------------ Liquid Glass 主题 */

/**
 * 按配色文档（四套 Liquid Glass 主题规格）的数值生成一套主题。
 * spec 里的值全部照抄文档；文档没给的派生色（悬停、浅底、分隔线、图表……）由强调色 / 文字色 / 壁纸混合得到，
 * 并用 ensure() 保证在内容层上的对比度达标（正文 ≥ 4.5:1）。
 */
function glassTheme(spec) {
  const { dark, accent, onAccent, ink, ink2Alpha, walls, bases, semantic, xp, content, glass, a11y } = spec
  // 浅色内容层的底色：文档主题为白色；珊瑚主题不用纯白，用卡片色
  const paper = dark ? null : spec.paper || '#FFFFFF'
  const light = paper || '#FFFFFF'
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
  const onOf = (color) => bestOn(color, dark ? [mix(color, '#000000', 0.82), ink] : [light, ink])
  const tint = (color, t) => (dark ? mix(surfaceSolid, color, t) : mix(light, color, t))
  // 时间轴用的空闲色、课程沙色：每套主题有自己的空闲色相（spec.idle），课程沙色从底盘与文字色混出来
  const idleHue = spec.idle || accent
  const sand = dark ? mix(surfaceSolid, ink, 0.1) : mix(bases[0], ink, 0.12)
  const subjects = subjectVars((s) => (dark ? { bg: mix(surfaceSolid, s.ink, 0.22), ink: mix(s.ink, '#FFFFFF', 0.38) } : { bg: s.bg, ink: s.ink }))

  return {
    primary: accent,
    'primary-dark': dark ? mix(accent, '#FFFFFF', 0.18) : mix(accent, ink, 0.16),
    'primary-light': tint(accent, dark ? 0.2 : 0.12),
    'primary-soft': tint(accent, dark ? 0.42 : 0.32),
    'primary-mid': tint(accent, dark ? 0.62 : 0.6),
    background: field,
    surface: surfaceSolid,
    ink,
    'ink-soft': inkSoft,
    'ink-mute': inkMute,
    'ink-line': line,
    bead: mix(surfaceSolid, ink, dark ? 0.26 : 0.22),
    idle: tint(idleHue, dark ? 0.18 : 0.16),
    'idle-bead': tint(idleHue, dark ? 0.5 : 0.45),
    'idle-ink': textOf(idleHue),
    link: textOf(idleHue),
    course: sand,
    'course-line': mix(sand, ink, dark ? 0.18 : 0.2),
    'course-icon': inkMute,
    flame: semantic.flame,
    'flame-light': tint(semantic.flame, dark ? 0.2 : 0.14),
    'flame-glow': mix(semantic.flame, dark ? ink : light, 0.4),
    'flame-deep': mix(semantic.flame, dark ? '#000000' : ink, 0.12),
    gold: dark ? '#D9A441' : '#C9952F',
    'gold-light': tint('#D9A441', dark ? 0.18 : 0.2),
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
    'inverse-ink': dark ? ink : mix(bases[0], light, 0.6),
    'inverse-accent': dark ? accent : mix(accent, light, 0.6),
    scrim: dark ? mix(bases[2], '#000000', 0.5) : ink,
    hero: mix(accent, xp, 0.5),
    // 专注页始终是深色沉浸背景：浅色主题从正文墨色出发，深色主题从壁纸最深的底色出发
    'deep-from': mix(dark ? bases[2] : ink, accent, 0.22),
    'deep-via': mix(dark ? bases[1] : ink, mix(accent, xp, 0.5), 0.28),
    'deep-to': mix(dark ? bases[0] : ink, xp, 0.32),
    'deep-ink': mix(dark ? bases[2] : ink, accent, 0.35),
    'ring-start': mix(accent, light, 0.45),
    'ring-end': mix(semantic.flame, light, 0.35),
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
    ...subjects,
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
    idle: '#2E8F86', // 时间轴空闲段：主色是蓝，空闲改用青绿，两者分得开
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
    idle: '#4F6A8C', // 主色是松青，空闲用石板蓝
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
    idle: '#7C95C9', // 主色是亮青，空闲用灰蓝
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
    idle: '#5E7F8C', // 主色是赤陶，空闲用灰蓝（与默认主题的空闲蓝同一思路）
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
  /**
   * 默认主题（莫兰迪 × 珊瑚）的玻璃参数。色板见上面的 CORAL，这里只给壁纸与材质：
   * 壁纸是几乎平的暖沙底 + 三块很淡的色斑（珊瑚 / 空闲蓝 / 沙），只给玻璃一点可折射的层次，不算大面积渐变；
   * 玻璃的高光、描边用卡片色 #FBF9F4（不用纯白），描边另加一道沙色细线，避免在浅底上看不出边。
   */
  coral: {
    dark: false,
    paper: '#FBF9F4',
    accent: '#D85A30',
    onAccent: '#FBF9F4',
    ink: '#2C2C2A',
    ink2Alpha: 0.62,
    walls: ['#F6E3D9', '#E1EAEF', '#EDE6D7', '#F2E7DE'],
    bases: ['#F4F1EA', '#F2EEE6', '#EFEBE2'],
    wallLayers: ['120% 70% at 4% 0%,', '90% 60% at 100% 34%,', '110% 70% at 0% 100%,', '100% 70% at 96% 96%,'],
    wallStops: ['58%', '60%', '62%', '60%'],
    baseMid: '50%',
    semantic: { success: '#6F9B4F', flame: '#F2743F', danger: '#C4554D' },
    xp: '#993C1D',
    idle: '#4A7BA6',
    content: { alpha: 0.78, filter: 'blur(28px) saturate(140%)' },
    glass: {
      fill: 'rgba(251, 249, 244, 0.52)',
      stroke: 'rgba(184, 178, 160, 0.42)',
      filter: 'blur(24px) saturate(165%) brightness(1.03)',
      shadow: 'inset 0 1px 0 rgba(251,249,244,.95), inset 0 -1px 0 rgba(251,249,244,.4), inset 0 0 20px rgba(251,249,244,.32), 0 10px 26px -14px rgba(44,44,42,.26), 0 2px 6px -3px rgba(44,44,42,.14)',
      sheen: 'radial-gradient(125% 95% at 16% -12%, rgba(251,249,244,.85), transparent 58%)',
    },
    a11y: { reduceFill: 'rgba(251, 249, 244, 0.96)', contrastStroke: 'rgba(44, 44, 42, 0.55)', contrastFill: 'rgba(251, 249, 244, 0.8)', outline: 'rgba(44, 44, 42, 0.7)' },
  },
  /** 暖深色：同一套布局与分族关系，深底玻璃。 */
  'warm-dark': {
    dark: true,
    accent: '#E2714A',
    onAccent: '#1C1A17',
    ink: '#EEE9E1',
    ink2Alpha: 0.72,
    walls: ['#33241C', '#1D262E', '#2B2620', '#2A221D'],
    bases: ['#1C1A17', '#1A1815', '#171512'],
    wallLayers: ['120% 70% at 4% 0%,', '90% 60% at 100% 34%,', '110% 70% at 0% 100%,', '100% 70% at 96% 96%,'],
    wallStops: ['58%', '60%', '62%', '60%'],
    baseMid: '50%',
    semantic: { success: '#8DB46E', flame: '#F2743F', danger: '#E07A70' },
    xp: '#F2B49A',
    idle: '#8DB4D6',
    content: { color: '#26231F', alpha: 0.8, filter: 'blur(26px)' },
    glass: {
      fill: 'rgba(38, 35, 31, 0.5)',
      stroke: 'rgba(238, 233, 225, 0.14)',
      filter: 'blur(24px) saturate(140%) brightness(1.02)',
      shadow: 'inset 0 1px 0 rgba(238,233,225,.16), inset 0 -1px 0 rgba(238,233,225,.06), 0 12px 30px -14px rgba(0,0,0,.7)',
      sheen: 'radial-gradient(125% 95% at 16% -12%, rgba(238,233,225,.12), transparent 58%)',
    },
    a11y: { reduceFill: 'rgba(38, 35, 31, 0.96)', contrastStroke: 'rgba(238, 233, 225, 0.6)', contrastFill: 'rgba(38, 35, 31, 0.9)', outline: 'rgba(238, 233, 225, 0.75)' },
  },
}

/**
 * 默认主题、深色主题的完整变量表：玻璃材质由 glassTheme() 按上面的参数生成，色板用 CORAL / WARM_DARK 的指定值覆盖。
 * BASE 也是其他主题缺省变量的来源。
 */
const BASE = {
  ...glassTheme(GLASS_SPECS.coral),
  ...CORAL,
  ...LIGHT_SUBJECTS,
  'shadow-soft': '0 1px 2px rgba(44, 44, 42, 0.06), 0 8px 24px -14px rgba(44, 44, 42, 0.18)',
  'shadow-lift': '0 2px 6px rgba(216, 90, 48, 0.22), 0 12px 28px -16px rgba(216, 90, 48, 0.4)',
  'shadow-phone': '0 40px 80px -30px rgba(44, 44, 42, 0.45)',
}
const DARK = {
  ...glassTheme(GLASS_SPECS['warm-dark']),
  ...WARM_DARK,
  ...DARK_SUBJECTS,
  // 深底上不加块投影，只留一圈极淡的内描边
  'shadow-soft': '0 6px 24px -12px rgba(0, 0, 0, 0.6), inset 0 0 0 1px rgba(238, 233, 225, 0.06)',
  'shadow-lift': '0 0 #0000',
  'shadow-phone': '0 40px 80px -30px rgba(0, 0, 0, 0.8)',
}
/* ------------------------------------------------------------------ 注册表 */

export const THEMES = [
  { id: 'default', name: '默认', description: '暖白 · 珊瑚 · 玻璃质感', dark: false, glass: true, preview: ['#D85A30', '#F4F1EA', '#9CC3E8'], vars: BASE },
  { id: 'dark', name: '深色', description: '暖调深底 · 夜间护眼', dark: true, glass: true, preview: ['#E2714A', '#1C1A17', '#8DB4D6'], vars: DARK },
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

/** 测试与报告用：每套主题的关键对比度。id 可以是主题 id（default / dark 对应 coral / warm-dark 的玻璃参数）。 */
const SPEC_OF = { default: 'coral', dark: 'warm-dark' }
export const contrastReport = (id) => {
  const theme = getTheme(id)
  const v = resolveVars(theme)
  const spec = GLASS_SPECS[SPEC_OF[id] || id]
  // 正文所在的实际底色：玻璃主题为"内容层叠在每一处壁纸色上"，普通主题为 surface 与 background
  const grounds = spec
    ? [...spec.walls, ...spec.bases].map((w) => mix(w, spec.dark ? spec.content.color : spec.paper || '#FFFFFF', spec.content.alpha)).concat(v.background)
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