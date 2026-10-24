/**
 * 后端地址。
 *
 * - 网页版（浏览器打开、电脑端 exe 外壳）：页面和接口同源，固定走 /api，由 Vite 代理或 Nginx 转发。
 * - 手机 App（Capacitor 打包）：页面打包在安装包里，必须写完整地址。默认取构建时的 VITE_SERVER_URL
 *   （正式版为 https://app.xueyeguanjia.com），用户也可以在登录页改成局域网里的电脑，例如 http://192.168.1.5:5173。
 */
import axios from 'axios'

const STORAGE_KEY = 'server-url'
export const DEFAULT_SERVER = import.meta.env.VITE_SERVER_URL || 'https://app.xueyeguanjia.com'

/** 是否运行在原生外壳里（Capacitor 会注入 window.Capacitor）。 */
export const isNativeApp = () => Boolean(window.Capacitor?.isNativePlatform?.())

export const normalizeServer = (value) => {
  let url = String(value || '').trim().replace(/\/+$/, '')
  if (!url) return ''
  if (!/^https?:\/\//i.test(url)) url = `http://${url}`
  return url.replace(/\/api$/i, '')
}

export const getServer = () => (isNativeApp() ? normalizeServer(localStorage.getItem(STORAGE_KEY)) || DEFAULT_SERVER : '')

export const setServer = (value) => {
  const url = normalizeServer(value)
  if (url) localStorage.setItem(STORAGE_KEY, url)
  else localStorage.removeItem(STORAGE_KEY)
  return getServer()
}

/** 接口前缀：网页版是 /api，App 里是 "服务器地址/api"。 */
export const apiBase = () => `${getServer()}/api`

/** 测试某个地址能否连上后端，返回耗时（毫秒）。 */
export const probeServer = async (value) => {
  const started = performance.now()
  const response = await axios.get(`${normalizeServer(value)}/api/health`, { timeout: 8000 })
  if (response.data?.code !== 200) throw new Error('地址可以访问，但不是学业管家的服务器')
  return Math.round(performance.now() - started)
}
