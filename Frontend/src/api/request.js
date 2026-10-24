import axios from 'axios'
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

// 网页端走同源 /api（开发时由 Vite 代理，部署时由 Nginx 转发）；
// 手机 App 里页面不在服务器上，每次请求按当前设置的服务器地址拼接（见 server.js）
const http = axios.create({ baseURL: '/api', timeout: 15000 })

http.interceptors.request.use((config) => {
  config.baseURL = apiBase()
  const token = tokenStorage.get()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

http.interceptors.response.use(
  (response) => {
    const payload = response.data
    if (payload && typeof payload === 'object' && 'code' in payload) {
      if (payload.code !== 200) throw new ApiError(payload.code, payload.message, payload.data)
      return payload.data
    }
    return payload
  },
  (error) => {
    const payload = error.response?.data
    const status = error.response?.status ?? 0
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
