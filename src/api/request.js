import axios from 'axios'
import router from '@/router'

const request = axios.create({
  /**
   * 后端接口地址
   */
  baseURL: '/api',

  /**
   * 超时时间
   */
  timeout: 10000
})

/**
 * 请求拦截器
 * 自动携带 token
 */
request.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token')

    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }

    return config
  },

  (error) => {
    return Promise.reject(error)
  }
)

/**
 * 响应拦截器
 */
request.interceptors.response.use(
  (response) => {
    /**
     * 后端统一返回:
     * {
     *   code,
     *   message,
     *   data
     * }
     */

    return response.data
  },

  (error) => {
    console.error('接口错误:', error)

    /**
     * token 失效
     */
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token')

      router.push('/login')
    }

    return Promise.reject(error)
  }
)

export default request