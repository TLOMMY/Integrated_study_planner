/**
 * 前端运行时错误上报（发到后端 POST /client-errors，按 message + 堆栈首行聚合）。
 * main.js 的全局错误处理会调用 reportError；installErrorReporting 监听未捕获的错误与 Promise 拒绝。
 *
 * - 同一个错误 1 分钟内只报一次，每个页面每分钟最多 5 条，避免刷屏；
 * - 业务接口错误（ApiError，已经给用户提示过）、网络断开、浏览器插件的错误不上报；
 * - 用 fetch keepalive（页面关闭时也能发出），失败静默忽略，绝不影响页面。
 */
import { apiBase } from '@/api/server'
import { tokenStorage } from '@/api/request'

const VERSION = import.meta.env.VITE_APP_VERSION || '4.0.0'
const PER_PAGE_PER_MINUTE = 5
const WINDOW = 60_000

const recent = new Map() // 指纹 -> 上次上报时间
let pageWindow = { page: '', start: 0, count: 0 }
let installed = false

const IGNORED = [/ResizeObserver loop/i, /Loading chunk .* failed/i, /^Script error\.?$/i, /NetworkError/i, /Failed to fetch/i]

const clip = (value, max) => String(value ?? '').slice(0, max)

const normalize = (error) => {
  if (error instanceof Error) return { message: `${error.name && !error.message.startsWith(error.name) ? `${error.name}: ` : ''}${error.message}`, stack: error.stack || '' }
  if (error && typeof error === 'object') {
    try {
      return { message: clip(error.message || JSON.stringify(error), 500), stack: '' }
    } catch {
      return { message: String(error), stack: '' }
    }
  }
  return { message: String(error ?? '未知错误'), stack: '' }
}

const shouldSkip = (error, message, stack) => {
  // 接口业务错误（如"密码错误"）与网络问题不属于前端缺陷
  if (error?.name === 'ApiError') return true
  if (!message || IGNORED.some((re) => re.test(message))) return true
  if (/(chrome|moz|safari)-extension:\/\//.test(stack)) return true
  return false
}

const allow = (key) => {
  const now = Date.now()
  for (const [k, t] of recent) if (now - t > WINDOW) recent.delete(k)
  if (recent.has(key)) return false
  const page = location.pathname
  if (pageWindow.page !== page || now - pageWindow.start > WINDOW) pageWindow = { page, start: now, count: 0 }
  if (pageWindow.count >= PER_PAGE_PER_MINUTE) return false
  pageWindow.count += 1
  recent.set(key, now)
  return true
}

const send = (payload) => {
  const url = `${apiBase()}/client-errors`
  const body = JSON.stringify(payload)
  try {
    const headers = { 'Content-Type': 'application/json' }
    const token = tokenStorage.get()
    if (token) headers.Authorization = `Bearer ${token}`
    if (typeof fetch === 'function') {
      fetch(url, { method: 'POST', headers, body, keepalive: true, credentials: 'omit' }).catch(() => {})
    } else if (navigator.sendBeacon) {
      navigator.sendBeacon(url, new Blob([body], { type: 'application/json' }))
    }
  } catch {
    /* 上报失败不影响页面 */
  }
}

/** 上报一个错误。info：Vue 的错误来源说明（如 "setup function"）等附加信息。 */
export function reportError(error, { info = '' } = {}) {
  try {
    const { message, stack } = normalize(error)
    if (shouldSkip(error, message, stack)) return
    const firstFrame = stack.split('\n').find((line) => line.trim() && !line.includes(message.slice(0, 60))) || ''
    if (!allow(`${message}|${firstFrame}`)) return
    send({
      message: clip(message, 2000),
      stack: clip(stack, 7000),
      page: clip(location.pathname + location.search, 500),
      info: clip(info, 200),
      version: VERSION,
      client: clip(navigator.userAgent, 500),
    })
  } catch {
    /* 上报本身出错时静默 */
  }
}

/** 监听未捕获的错误与未处理的 Promise 拒绝（只安装一次）。 */
export function installErrorReporting() {
  if (installed || typeof window === 'undefined') return
  installed = true
  window.addEventListener('error', (event) => {
    // 图片 / 脚本加载失败也会触发 error（target 是元素），不上报
    if (event.target && event.target !== window) return
    reportError(event.error || event.message, { info: event.filename ? `${event.filename}:${event.lineno}:${event.colno}` : 'window.onerror' })
  })
  window.addEventListener('unhandledrejection', (event) => {
    reportError(event.reason, { info: 'unhandledrejection' })
  })
}
