import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { addCollection } from '@iconify/vue'

import App from './App.vue'
import router from './router'
import icons from './assets/icons.json'
import { onUnauthorized } from './api/request'
import { useAuthStore } from './stores/auth'
import { useUiStore } from './stores/ui'
import './style.css'

// 图标随包打入，不访问 Iconify 在线接口
addCollection(icons)

const app = createApp(App)
const pinia = createPinia()
app.use(pinia)
app.use(router)

onUnauthorized(() => {
  const auth = useAuthStore()
  if (!auth.token) return
  auth.logout()
  useUiStore().toast('登录已过期，请重新登录', 'warning')
  const current = router.currentRoute.value
  if (current.name !== 'login') router.replace({ name: 'login', query: { redirect: current.fullPath } })
})

app.config.errorHandler = (error) => {
  console.error(error)
  useUiStore().toast(error?.message || '出了点问题，请重试', 'error')
}

app.mount('#app')

// 生产环境注册 Service Worker：浏览器地址栏会出现"安装"按钮，装成电脑上的独立应用窗口
// App 外壳里资源本来就在安装包里，不需要 Service Worker
if (import.meta.env.PROD && 'serviceWorker' in navigator && location.protocol !== 'file:' && !window.Capacitor) {
  window.addEventListener('load', () => navigator.serviceWorker.register('/sw.js').catch(() => {}))
}
