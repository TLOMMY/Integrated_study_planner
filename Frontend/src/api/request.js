import axios from 'axios'
import { reactive } from 'vue'
import { apiBase } from './server'

const TOKEN_KEY = 'access_token'

export const tokenStorage = {
  get() {
    const token = localStorage.getItem(TOKEN_KEY)?.trim()
    if (!token || token === 'undefined' || token === 'null') return ''
    return token
  },
  set(token) {
    localStorage.setItem(TOKEN_KEY, token)
  },
  clear() {
    clearOffline(userKey(localStorage.getItem(TOKEN_KEY)))
    localStorage.removeItem(TOKEN_KEY)
  },
}

/** 统一的接口异常：status 与后端信封里的 code 一致，message 是可直接展示的中文。 */
export class ApiError extends Error {
  constructor(status, message, data = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.data = data
  }
}

let unauthorizedHandler = null
/** 由 main.js 注册：登录失效时清理状态并跳转登录页。 */
export const onUnauthorized = (handler) => {
  unauthorizedHandler = handler
}

/* ------------------------------------------------------------------
 * 断网可看：白名单里的 GET 接口把最近一次成功的数据存到本地（按用户隔离、有大小上限），
 * 连不上服务器时返回缓存并把 network.offline 置为 true，界面据此显示离线横幅。
 * 写操作在离线时给出"离线状态下无法保存"的提示。
 * ------------------------------------------------------------------ */

/** 全局网络状态（响应式）：offline 连不上服务器；cached 当前展示的是缓存数据。 */
export const network = reactive({ offline: false, cached: false })

const OFFLINE_PATHS = new Set(['/home/summary', '/task/list', '/timetable', '/day/timeline', '/study/stats', '/users/me'])
const CACHE_PREFIX = 'offline:'
const ENTRY_LIMIT = 200 * 1024 // 单条最多约 200KB 字符
const USER_LIMIT = 1.5 * 1024 * 1024 // 每个用户合计最多约 1.5MB 字符

/** 从凭证里取用户 id，作为缓存的隔离键；取不到就不缓存。 */
const userKey = (token) => {
  try {
    const payload = JSON.parse(atob(String(token).split('.')[1].replace(/-/g, '+').replace(/_/g, '/')))
    const id = payload.user_id ?? payload.sub
    return id ? String(id) : ''
  } catch {
    return ''
  }
}

const cachePath = (config) => {
  const url = String(config?.url || '').split('?')[0]
  return url.startsWith('/') ? url : `/${url}`
}

const cacheKey = (config) => {
  const params = config?.params || {}
  const query = Object.keys(params)
    .filter((k) => params[k] !== undefined && params[k] !== null && params[k] !== '')
    .sort()
    .map((k) => `${k}=${params[k]}`)
    .join('&')
  return `${cachePath(config)}?${query}`
}

const cacheable = (config) => (config?.method || 'get').toLowerCase() === 'get' && OFFLINE_PATHS.has(cachePath(config))
const isWrite = (config) => Boolean(config) && (config.method || 'get').toLowerCase() !== 'get'

const indexKey = (uid) => `${CACHE_PREFIX}${uid}:index`
const readIndex = (uid) => {
  try {
    return JSON.parse(localStorage.getItem(indexKey(uid)) || '{}')
  } catch {
    return {}
  }
}

function saveOffline(config, data) {
  if (!cacheable(config)) return
  const uid = userKey(tokenStorage.get())
  if (!uid) return
  try {
    const text = JSON.stringify(data)
    if (text.length > ENTRY_LIMIT) return
    const key = cacheKey(config)
    const index = readIndex(uid)
    index[key] = { size: text.length, at: Date.now() }
    // 超出总量时从最旧的开始淘汰
    let total = Object.values(index).reduce((sum, item) => sum + item.size, 0)
    for (const [k] of Object.entries(index).sort((a, b) => a[1].at - b[1].at)) {
      if (total <= USER_LIMIT || k === key) continue
      total -= index[k].size
      delete index[k]
      localStorage.removeItem(`${CACHE_PREFIX}${uid}:${k}`)
    }
    localStorage.setItem(`${CACHE_PREFIX}${uid}:${key}`, text)
    localStorage.setItem(indexKey(uid), JSON.stringify(index))
  } catch {
    /* 本地存储满了：不影响正常使用 */
  }
}

function loadOffline(config) {
  if (!cacheable(config)) return undefined
  const uid = userKey(tokenStorage.get())
  if (!uid) return undefined
  const text = localStorage.getItem(`${CACHE_PREFIX}${uid}:${cacheKey(config)}`)
  if (text === null) return undefined
  try {
    return JSON.parse(text)
  } catch {
    return undefined
  }
}

/** 清掉某个用户的离线数据（退出登录时调用，避免共用电脑时被别人看到）。 */
function clearOffline(uid) {
  if (!uid) return
  for (const key of Object.keys(readIndex(uid))) localStorage.removeItem(`${CACHE_PREFIX}${uid}:${key}`)
  localStorage.removeItem(indexKey(uid))
}

/** 没有收到服务器的业务响应：断网、超时、网关 / 代理报错。 */
const isUnreachable = (error) => {
  if (!error?.config) return false
  if (!error.response) return true
  const { status, data } = error.response
  const enveloped = data && typeof data === 'object' && 'code' in data
  return !enveloped && [500, 502, 503, 504].includes(status)
}

const writeOfflineMessage = (config) => {
  const disconnected = typeof navigator !== 'undefined' && navigator.onLine === false
  if (cachePath(config).startsWith('/auth/')) return disconnected ? '网络已断开，请联网后再登录' : '无法连接服务器，请确认后端已启动（端口 8000）'
  return disconnected ? '网络已断开，离线状态下无法保存，请联网后重试' : '无法连接服务器，离线状态下无法保存，请稍后重试'
}

let probeTimer = null
function markOffline() {
  network.offline = true
  // 离线期间每 15 秒探测一次，恢复后自动隐藏横幅
  if (probeTimer || typeof window === 'undefined') return
  probeTimer = setInterval(() => {
    axios.get(`${apiBase()}/health`, { timeout: 5000 }).then((r) => r.data?.code === 200 && markOnline(), () => {})
  }, 15000)
}
function markOnline() {
  if (!network.offline && !network.cached) return
  const wasOffline = network.offline
  network.offline = false
  network.cached = false
  clearInterval(probeTimer)
  probeTimer = null
  // 页面可监听此事件，联网后重新拉取数据
  if (wasOffline && typeof window !== 'undefined') window.dispatchEvent(new CustomEvent('app:online'))
}

if (typeof window !== 'undefined') {
  window.addEventListener('offline', markOffline)
  window.addEventListener('online', () => {
    axios.get(`${apiBase()}/health`, { timeout: 5000 }).then((r) => r.data?.code === 200 && markOnline(), () => {})
  })
}

/** 手动重试连接（横幅上的"重试"按钮）。 */
export const retryConnection = () =>
  axios.get(`${apiBase()}/health`, { timeout: 5000 }).then(
    (r) => {
      if (r.data?.code === 200) markOnline()
      return network.offline === false
    },
    () => false,
  )

// 网页端走同源 /api（开发时由 Vite 代理，部署时由 Nginx 转发）；
// 手机 App 里页面不在服务器上，每次请求按当前设置的服务器地址拼接（见 server.js）
const http = axios.create({ baseURL: '/api', timeout: 15000 })

http.interceptors.request.use((config) => {
  config.baseURL = apiBase()
  const token = tokenStorage.get()
  if (token) config.headers.Authorization = `Bearer ${token}`
  // 系统明确报告断网时，写操作直接提示，不必等超时
  if (isWrite(config) && typeof navigator !== 'undefined' && navigator.onLine === false) {
    markOffline()
    throw new ApiError(0, writeOfflineMessage(config))
  }
  return config
})

http.interceptors.response.use(
  (response) => {
    const payload = response.data
    markOnline()
    if (payload && typeof payload === 'object' && 'code' in payload) {
      if (payload.code !== 200) throw new ApiError(payload.code, payload.message, payload.data)
      saveOffline(response.config, payload.data)
      return payload.data
    }
    return payload
  },
  (error) => {
    if (error instanceof ApiError) return Promise.reject(error)
    const payload = error.response?.data
    const status = error.response?.status ?? 0
    // 连不上服务器（断网 / 超时 / 网关报错）：白名单里的 GET 接口返回最近一次的缓存
    if (isUnreachable(error)) {
      markOffline()
      const cached = loadOffline(error.config)
      if (cached !== undefined) {
        network.cached = true
        return cached
      }
      if (isWrite(error.config)) return Promise.reject(new ApiError(0, writeOfflineMessage(error.config)))
    }
    if (status === 401 && !error.config?.skipAuthRedirect) unauthorizedHandler?.()
    if (payload && typeof payload === 'object' && 'message' in payload) {
      return Promise.reject(new ApiError(status, payload.message, payload.data))
    }
    if (error.code === 'ECONNABORTED') return Promise.reject(new ApiError(0, '请求超时，请稍后重试'))
    if (!error.response) return Promise.reject(new ApiError(0, '无法连接服务器，请确认后端已启动（端口 8000）'))
    return Promise.reject(new ApiError(status, `请求失败（${status}）`))
  },
)

export default http
