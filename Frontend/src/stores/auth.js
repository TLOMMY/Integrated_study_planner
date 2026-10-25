import { defineStore } from 'pinia'
import { authApi, userApi } from '@/api'
import { tokenStorage } from '@/api/request'

const decodeExp = (token) => {
  try {
    const payload = JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')))
    return payload.exp ? payload.exp * 1000 : null
  } catch {
    return null
  }
}

let refreshTimer = null

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: tokenStorage.get(),
    user: null,
  }),

  getters: {
    isLoggedIn: (state) => Boolean(state.token),
    isDemo: (state) => Boolean(state.user?.is_demo),
    displayName: (state) => state.user?.display_name || '同学',
  },

  actions: {
    _accept(data) {
      this.token = data.access_token
      tokenStorage.set(data.access_token)
      if (data.user) this.user = data.user
      this.scheduleRefresh()
    },

    async login(identifier, password) {
      this._accept(await authApi.login(identifier, password))
    },

    async register(payload) {
      this._accept(await authApi.register(payload))
    },

    async loginDemo() {
      this._accept(await authApi.demo())
    },

    async fetchMe() {
      this.user = await userApi.me()
      this.scheduleRefresh()
      return this.user
    },

    async updateProfile(payload) {
      this.user = await userApi.update(payload)
      return this.user
    },

    /** 改密码 / 退出其他设备：后端会换发新凭证，当前设备保持登录。 */
    async changePassword(payload) {
      this._accept(await userApi.changePassword(payload))
    },
    async logoutOthers() {
      this._accept(await userApi.logoutAll())
    },
    async changeEmail(payload) {
      this.user = await userApi.changeEmail(payload)
    },
    async changePhone(payload) {
      this.user = await userApi.changePhone(payload)
    },
    /** 用验证码验证当前邮箱（先 authApi.sendEmailCode(email, 'bind')）。 */
    async verifyEmail(code) {
      this.user = await userApi.verifyEmail(code)
    },

    /** 在凭证到期前自动续期，长时间挂着页面也不会突然掉线。 */
    scheduleRefresh() {
      clearTimeout(refreshTimer)
      const exp = this.token && decodeExp(this.token)
      if (!exp) return
      const delay = (exp - Date.now()) * 0.8
      if (delay <= 0) return
      refreshTimer = setTimeout(async () => {
        try {
          const data = await authApi.refresh()
          this.token = data.access_token
          tokenStorage.set(data.access_token)
          this.scheduleRefresh()
        } catch {
          /* 续期失败时等下一次请求触发 401 再处理 */
        }
      }, Math.min(delay, 2 ** 31 - 1))
    },

    logout() {
      clearTimeout(refreshTimer)
      tokenStorage.clear()
      this.token = ''
      this.user = null
      // 清空其他模块的缓存，避免切换账号后看到上一个人的数据；进行中的番茄一并丢弃
      for (const store of this._p._s.values()) {
        if (store.$id === 'focus') store.abandon()
        else if (!['auth', 'ui'].includes(store.$id)) store.$reset?.()
      }
    },
  },
})
