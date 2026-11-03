/**
 * 新手教程的开关与完成状态。界面见 components/common/OnboardingTour.vue（挂在 App.vue）。
 * 完成状态随账号保存在服务器（PUT /users/me/onboarding）；接口失败时记在本机，避免反复弹出。
 * 自动化测试可以在 localStorage 里设置 tour-disabled=1 关闭自动弹出。
 */
import { reactive } from 'vue'
import { guideApi } from '@/api/guide'
import { useAuthStore } from '@/stores/auth'

export const tour = reactive({ open: false, step: 0, startedFor: null })

const localKey = (userId) => `onboarded-${userId}`
export const locallyDone = (userId) => localStorage.getItem(localKey(userId)) === '1' || localStorage.getItem('tour-disabled') === '1'

/** 打开教程（设置 / 使用手册里的"重新查看"也调这个）。 */
export function startTour() {
  tour.step = 0
  tour.open = true
}

/** 看完或跳过：记到账号上（演示账号不记录）。 */
export async function finishTour() {
  tour.open = false
  const auth = useAuthStore()
  const user = auth.user
  if (!user || user.is_demo || user.onboarded) return
  localStorage.setItem(localKey(user.id), '1')
  auth.user = { ...user, onboarded: true }
  try {
    auth.user = await guideApi.done()
    localStorage.removeItem(localKey(user.id))
  } catch {
    /* 网络问题：本机已记住，下次登录时 shouldAutoStart 会看到 localDone */
  }
}
