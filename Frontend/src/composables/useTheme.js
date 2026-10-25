/**
 * 界面主题。
 *
 * - applyStoredTheme()：main.js 在挂载前调用，从本地读取主题并写入 CSS 变量，避免闪烁。
 * - setTheme(id)：立即应用 + 存本地 + 已登录时同步到账号（PUT /users/me 的 theme 字段）。
 * - syncThemeFromAccount(id)：登录 / 拉取用户信息后调用，账号里存的主题与本地不同时以账号为准。
 * - themeColor(name, alpha)：给 ECharts、canvas 等不能用 CSS 类的地方取当前主题的颜色（响应式，切换主题后依赖它的 computed 会重算）。
 * - a11y / setA11y(key, on)：设置页的"降低透明度""增强对比度""显示边框"开关（系统的 prefers-* 设置之外的兜底），只存本机。
 */
import { computed, ref } from 'vue'
import { DEFAULT_THEME_ID, SYSTEM_THEME, THEMES, getTheme, resolveVars, themeCss } from '@/themes'
import { userApi } from '@/api'
import { useAuthStore } from '@/stores/auth'

const STORAGE_KEY = 'app-theme'
// 给 index.html 里的内联脚本用：在 JS 包加载前先把底色和 color-scheme 设对
const BOOT_KEY = 'app-theme-boot'
const A11Y_KEY = 'app-a11y'

const choice = ref(DEFAULT_THEME_ID) // 用户的选择：主题 id 或 'system'
const systemDark = ref(false)
let media = null

/**
 * 无障碍开关：transparency 降低透明度、contrast 增强对比度、borders 显示边框。
 * transparency / contrast 为 null 时跟随系统（prefers-reduced-transparency / prefers-contrast），
 * true / false 为用户在设置页明确选择（可以覆盖系统设置，例如 Windows 关了"透明效果"但仍想看玻璃）。
 */
const a11y = ref({ transparency: null, contrast: null, borders: false })
const systemPrefs = ref({ transparency: false, contrast: false })

const isValid = (id) => id === SYSTEM_THEME.id || THEMES.some((theme) => theme.id === id)

/** 实际生效的主题对象（"跟随系统"时按系统深浅色解析）。 */
const active = computed(() => {
  if (choice.value === SYSTEM_THEME.id) return getTheme(systemDark.value ? 'dark' : DEFAULT_THEME_ID)
  return getTheme(choice.value)
})
const activeVars = computed(() => resolveVars(active.value))

const readLocal = () => {
  try {
    const id = localStorage.getItem(STORAGE_KEY)
    return isValid(id) ? id : DEFAULT_THEME_ID
  } catch {
    return DEFAULT_THEME_ID
  }
}

const writeLocal = (id) => {
  try {
    localStorage.setItem(STORAGE_KEY, id)
  } catch {
    /* 隐私模式等情况下无法写入，忽略 */
  }
}

/** 把当前生效的主题写进页面。 */
function paint() {
  const theme = active.value
  const vars = activeVars.value
  let style = document.getElementById('theme-vars')
  if (!style) {
    style = document.createElement('style')
    style.id = 'theme-vars'
    document.head.appendChild(style)
  }
  style.textContent = themeCss(theme)

  const root = document.documentElement
  root.dataset.theme = theme.id
  root.style.colorScheme = theme.dark ? 'dark' : 'light'
  root.style.background = ''
  // Liquid Glass 只在玻璃主题下启用（style.css 的 data-glass 段）
  if (theme.glass) root.dataset.glass = ''
  else delete root.dataset.glass
  paintA11y()

  // 浏览器 / 安装后窗口的标题栏颜色：普通浅色主题用主色，深色与玻璃主题用页面底色
  const barColor = theme.dark || theme.glass ? vars.page : vars.primary
  let meta = document.querySelector('meta[name="theme-color"]')
  if (!meta) {
    meta = document.createElement('meta')
    meta.name = 'theme-color'
    document.head.appendChild(meta)
  }
  meta.content = barColor
  document.querySelector('meta[name="apple-mobile-web-app-status-bar-style"]')?.setAttribute('content', theme.dark ? 'black' : 'default')

  try {
    localStorage.setItem(BOOT_KEY, JSON.stringify({ dark: theme.dark, bg: vars.page }))
  } catch {
    /* 忽略 */
  }
}

function watchSystem() {
  if (media || !window.matchMedia) return
  media = window.matchMedia('(prefers-color-scheme: dark)')
  systemDark.value = media.matches
  media.addEventListener?.('change', (event) => {
    systemDark.value = event.matches
    if (choice.value === SYSTEM_THEME.id) paint()
  })
}

/** 写到 <html> 上：未选择时不写属性，由 style.css 里的媒体查询跟随系统；明确选择时写 reduce / normal、more / normal。 */
function paintA11y() {
  const root = document.documentElement
  const { transparency, contrast, borders } = a11y.value
  if (transparency === null) delete root.dataset.transparency
  else root.dataset.transparency = transparency ? 'reduce' : 'normal'
  if (contrast === null) delete root.dataset.contrast
  else root.dataset.contrast = contrast ? 'more' : 'normal'
  if (borders) root.dataset.borders = 'on'
  else delete root.dataset.borders
}

const triState = (value) => (value === true || value === false ? value : null)
const readA11y = () => {
  try {
    const saved = JSON.parse(localStorage.getItem(A11Y_KEY) || '{}')
    return { transparency: triState(saved.transparency), contrast: triState(saved.contrast), borders: Boolean(saved.borders) }
  } catch {
    return { transparency: null, contrast: null, borders: false }
  }
}

function watchA11yPrefs() {
  if (!window.matchMedia) return
  for (const [key, query] of [['transparency', '(prefers-reduced-transparency: reduce)'], ['contrast', '(prefers-contrast: more)']]) {
    const mq = window.matchMedia(query)
    systemPrefs.value = { ...systemPrefs.value, [key]: mq.matches }
    mq.addEventListener?.('change', (event) => (systemPrefs.value = { ...systemPrefs.value, [key]: event.matches }))
  }
}

/** 开关显示的状态：用户选过就用用户的，否则显示系统当前的设置。 */
const a11yEffective = computed(() => ({
  transparency: a11y.value.transparency ?? systemPrefs.value.transparency,
  contrast: a11y.value.contrast ?? systemPrefs.value.contrast,
  borders: a11y.value.borders,
}))

/** 设置页的无障碍开关。 */
export function setA11y(key, on) {
  if (!(key in a11y.value)) return
  // 与系统设置一致时回到"跟随系统"，以后系统改了也能跟着变
  if (key !== 'borders' && Boolean(on) === systemPrefs.value[key]) on = null
  a11y.value = { ...a11y.value, [key]: on === null ? null : Boolean(on) }
  try {
    localStorage.setItem(A11Y_KEY, JSON.stringify(a11y.value))
  } catch {
    /* 忽略 */
  }
  paintA11y()
}

/** main.js 挂载前调用。 */
export function applyStoredTheme() {
  watchSystem()
  watchA11yPrefs()
  choice.value = readLocal()
  a11y.value = readA11y()
  paint()
}

/** 只在本地应用，不同步账号。 */
function applyLocal(id) {
  choice.value = isValid(id) ? id : DEFAULT_THEME_ID
  writeLocal(choice.value)
  paint()
}

/** 用户在设置页切换主题。 */
export async function setTheme(id) {
  if (!isValid(id)) return
  applyLocal(id)
  const auth = useAuthStore()
  if (!auth.isLoggedIn || !auth.user || auth.user.theme === id) return
  auth.user = { ...auth.user, theme: id } // 先改本地，避免 App.vue 的同步逻辑把它改回去
  try {
    await userApi.update({ theme: id })
  } catch {
    /* 离线或服务器暂不可用：本地已生效，下次切换时再同步 */
  }
}

/** 登录后用账号里的主题覆盖本地（账号没存过时保持本地选择）。 */
export function syncThemeFromAccount(id) {
  if (!id || !isValid(id) || id === choice.value) return
  applyLocal(id)
}

/** 当前主题的某个颜色，返回 ECharts 可用的 rgba() 字符串。 */
export function themeColor(name, alpha = 1) {
  const hex = activeVars.value[name] || '#000000'
  const n = Number.parseInt(hex.replace('#', ''), 16)
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`
}

export function useTheme() {
  return {
    themes: THEMES,
    system: SYSTEM_THEME,
    choice: computed(() => choice.value),
    active,
    isDark: computed(() => active.value.dark),
    a11y: a11yEffective,
    setA11y,
    setTheme,
    themeColor,
  }
}
