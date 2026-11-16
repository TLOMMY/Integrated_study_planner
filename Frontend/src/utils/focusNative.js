/**
 * 安卓 App 的番茄钟原生能力（App 自带的 FocusTimer 插件，见 android/.../FocusTimerPlugin.java）：
 *  · 锁屏 / 通知栏倒计时：开始、暂停、继续时更新常驻通知，结束或放弃时收起；
 *  · 熄屏判断：离开期间发生过熄屏，就把这次离开算作"熄屏"，不算切到别的应用。
 * 网页版和旧版 App 没有这个插件：所有方法安静地什么都不做。
 */
import { isNativeApp } from '@/api/server'

const LOCK_KEY = 'focus-lock-screen'
const SCREEN_OFF_KEY = 'focus-screen-off-counts'

/** 锁屏显示倒计时（本机开关，默认开） */
export const lockScreenEnabled = () => localStorage.getItem(LOCK_KEY) !== '0'
export const setLockScreenEnabled = (on) => localStorage.setItem(LOCK_KEY, on ? '1' : '0')
/** 熄屏是否也算切出（本机开关，默认不算） */
export const screenOffCounts = () => localStorage.getItem(SCREEN_OFF_KEY) === '1'
export const setScreenOffCounts = (on) => localStorage.setItem(SCREEN_OFF_KEY, on ? '1' : '0')

// 插件是代理对象，不能直接作为 Promise 的结果（会被当成 thenable），所以包一层 { native }
const native = () => {
  if (!isNativeApp()) return null
  const plugin = window.Capacitor?.Plugins?.FocusTimer
  return plugin && window.Capacitor?.isPluginAvailable?.('FocusTimer') ? plugin : null
}

export const hasFocusNative = () => Boolean(native())

/** 同步通知：state = { status, endAt, title, text } */
export async function syncLockScreen(state) {
  const plugin = native()
  if (!plugin) return
  try {
    if (!lockScreenEnabled() || !['running', 'paused'].includes(state.status)) {
      await plugin.hide()
      return
    }
    await plugin.show({ title: state.title, text: state.text, endAt: state.endAt || 0, paused: state.status === 'paused' })
  } catch {
    // 通知失败不影响计时
  }
}

export async function hideLockScreen() {
  const plugin = native()
  if (plugin) await plugin.hide().catch(() => {})
}

/** 第一次开始专注时请求通知权限（安卓 13+ 需要）；用户拒绝后不再追问。 */
export async function ensureLockScreenPermission() {
  const plugin = native()
  if (!plugin || !lockScreenEnabled()) return 'unsupported'
  try {
    const { display } = await plugin.checkPermissions()
    if (display !== 'prompt') return display
    if (localStorage.getItem('focus-lock-asked')) return display
    localStorage.setItem('focus-lock-asked', '1')
    return (await plugin.requestPermissions()).display
  } catch {
    return 'unsupported'
  }
}

export async function lockScreenPermission() {
  const plugin = native()
  if (!plugin) return 'unsupported'
  try {
    return (await plugin.checkPermissions()).display
  } catch {
    return 'unsupported'
  }
}

export async function requestLockScreenPermission() {
  const plugin = native()
  if (!plugin) return 'unsupported'
  try {
    return (await plugin.requestPermissions()).display
  } catch {
    return 'unsupported'
  }
}

/**
 * 这次离开（leftAt 起）是不是熄屏：离开后发生过熄屏，或现在仍然熄屏。
 * 没有插件时返回 false（网页版分辨不出熄屏，只能都算切出）。
 */
export async function leftByScreenOff(leftAt) {
  const plugin = native()
  if (!plugin) return false
  try {
    const { lastScreenOff } = await plugin.screenState()
    // 熄屏广播比 Activity 进入后台稍晚或稍早都有可能：前后 1.5 秒内都算
    return Boolean(lastScreenOff) && lastScreenOff >= leftAt - 1500
  } catch {
    return false
  }
}
