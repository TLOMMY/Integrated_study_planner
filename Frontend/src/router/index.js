import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const MainLayout = () => import('@/layouts/MainLayout.vue')

const routes = [
  {
    path: '/',
    component: MainLayout,
    children: [
      { path: '', redirect: '/today-task' },
      { path: 'today-task', name: 'home', component: () => import('@/views/HomeView.vue'), meta: { title: '今日' } },
      { path: 'timetable', name: 'timetable', component: () => import('@/views/TimetableView.vue'), meta: { title: '课表' } },
      { path: 'ai', name: 'ai', component: () => import('@/views/AiAssistantView.vue'), meta: { title: 'AI 规划' } },
      { path: 'view', name: 'view', component: () => import('@/views/DayView.vue'), meta: { title: '日程' } },
      { path: 'day', redirect: '/view' },
      { path: 'statistics', name: 'statistics', component: () => import('@/views/StatisticsView.vue'), meta: { title: '成长' } },
      { path: 'profile', name: 'profile', component: () => import('@/views/ProfileView.vue'), meta: { title: '我的' } },
      { path: 'plans', name: 'plans', component: () => import('@/views/PlansView.vue'), meta: { title: '学习计划' } },
      { path: 'settings', name: 'settings', component: () => import('@/views/SettingsView.vue'), meta: { title: '设置' } },
    ],
  },
  { path: '/focus-timer', name: 'focus', component: () => import('@/views/FocusTimerView.vue'), meta: { title: '专注' } },
  { path: '/login', name: 'login', component: () => import('@/views/LoginView.vue'), meta: { title: '登录', public: true } },
  { path: '/:pathMatch(.*)*', redirect: '/today-task' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 }),
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (to.meta.public) {
    return auth.isLoggedIn && to.name === 'login' ? { name: 'home' } : true
  }
  if (!auth.isLoggedIn) return { name: 'login', query: { redirect: to.fullPath } }
  if (!auth.user) {
    try {
      await auth.fetchMe()
    } catch {
      // 401 已由全局处理器清理并跳转；网络错误时仍放行，让页面展示具体错误
      if (!auth.isLoggedIn) return { name: 'login', query: { redirect: to.fullPath } }
    }
  }
  return true
})

router.afterEach((to) => {
  document.title = to.meta.title ? `${to.meta.title} · 学业管家` : '学业管家'
})

export default router
