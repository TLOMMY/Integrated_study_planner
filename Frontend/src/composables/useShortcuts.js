/**
 * 全局键盘快捷键（电脑端，≥1024px）。在 MainLayout 中调用。
 *
 *   / 或 Ctrl+K   聚焦首页搜索         N   新建任务
 *   G 然后 T/C/A/V/S  跳到 今日/课表/AI/日程/成长
 *   F   开始专注          ?   快捷键说明          Esc  关闭弹层
 *
 * 输入框、文本域、可编辑区域里不触发（Esc 除外由各弹层自己处理）。
 * 首页配合：派发可取消的 window 事件 'app:focus-search' / 'app:new-task'，
 * 页面处理后调用 event.preventDefault()；没人处理时退回到按 aria-label 找搜索框 / 添加按钮。
 */
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useUiStore } from '@/stores/ui'

/** 快捷键说明弹窗的开关（设置页也可以打开）。 */
export const shortcutsHelpOpen = ref(false)
export const openShortcutsHelp = () => (shortcutsHelpOpen.value = true)

export const SHORTCUTS = [
  { keys: ['/'], alt: ['Ctrl', 'K'], label: '搜索任务' },
  { keys: ['N'], label: '新建任务' },
  { keys: ['F'], label: '开始专注' },
  { keys: ['G', 'T'], label: '跳到今日待办' },
  { keys: ['G', 'C'], label: '跳到课表' },
  { keys: ['G', 'A'], label: '跳到 AI 规划' },
  { keys: ['G', 'V'], label: '跳到日程' },
  { keys: ['G', 'S'], label: '跳到成长' },
  { keys: ['?'], label: '显示快捷键说明' },
  { keys: ['Esc'], label: '关闭弹窗 / 抽屉' },
]

const GOTO = { t: 'home', c: 'timetable', a: 'ai', v: 'view', s: 'statistics' }
const DESKTOP = '(min-width: 1024px)'

const isTyping = (target) => {
  if (!(target instanceof HTMLElement)) return false
  if (target.isContentEditable) return true
  const tag = target.tagName
  if (tag === 'TEXTAREA' || tag === 'SELECT') return true
  if (tag !== 'INPUT') return false
  return !['checkbox', 'radio', 'button', 'submit', 'reset', 'range', 'color', 'file'].includes(target.type)
}

/** 派发可取消事件；页面调用 preventDefault() 表示已处理。 */
const emitHandled = (name) => !window.dispatchEvent(new CustomEvent(name, { cancelable: true }))

export function useShortcuts() {
  const router = useRouter()
  const ui = useUiStore()
  let pendingG = 0

  /** 先回到首页（如有需要），再交给首页处理。 */
  const onHome = async (eventName, fallback) => {
    if (router.currentRoute.value.name !== 'home') {
      await router.push({ name: 'home' })
      await nextTick()
      await new Promise((resolve) => setTimeout(resolve, 120))
    }
    if (!emitHandled(eventName)) fallback()
  }

  const focusSearch = () =>
    onHome('app:focus-search', () => {
      const input = document.querySelector('input[aria-label="搜索任务"]')
      input?.focus()
      input?.select?.()
    })
  const newTask = () => onHome('app:new-task', () => document.querySelector('button[aria-label="添加任务"]')?.click())

  /** Esc：关闭全局确认框 / 庆祝层 / 快捷键说明；BottomSheet 自己监听 Esc。 */
  const closeOverlays = () => {
    if (shortcutsHelpOpen.value) shortcutsHelpOpen.value = false
    else if (ui.dialog) ui.closeDialog(false)
    else if (ui.celebrations.length) ui.nextCelebration()
  }

  const onKey = (event) => {
    if (event.defaultPrevented || event.isComposing || event.repeat) return
    if (!window.matchMedia(DESKTOP).matches) return
    if (event.key === 'Escape') return closeOverlays()
    if (isTyping(event.target)) return
    // 有弹层打开时，除 Esc 外不响应，避免在弹窗背后乱跳
    if (document.querySelector('#overlay-root [role="dialog"]') || ui.dialog) return

    const key = event.key.toLowerCase()
    if ((event.ctrlKey || event.metaKey) && key === 'k') {
      event.preventDefault()
      return focusSearch()
    }
    if (event.ctrlKey || event.metaKey || event.altKey) return

    if (pendingG && Date.now() - pendingG < 1500 && GOTO[key]) {
      pendingG = 0
      event.preventDefault()
      return router.push({ name: GOTO[key] })
    }
    pendingG = 0

    if (event.key === '?') {
      event.preventDefault()
      shortcutsHelpOpen.value = true
    } else if (event.key === '/') {
      event.preventDefault()
      focusSearch()
    } else if (key === 'g') {
      pendingG = Date.now()
    } else if (key === 'n') {
      event.preventDefault()
      newTask()
    } else if (key === 'f') {
      event.preventDefault()
      router.push({ name: 'focus' })
    }
  }

  onMounted(() => window.addEventListener('keydown', onKey))
  onBeforeUnmount(() => window.removeEventListener('keydown', onKey))
}
