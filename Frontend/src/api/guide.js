/** 新手教程完成状态。 */
import http from './request'

export const guideApi = {
  /** 标记已看完 / 跳过，返回最新的用户信息（含 onboarded）。 */
  done: () => http.put('/users/me/onboarding', { done: true }),
  /** 重置为未看过（下次登录会再次弹出）。 */
  reset: () => http.put('/users/me/onboarding', { done: false }),
}
