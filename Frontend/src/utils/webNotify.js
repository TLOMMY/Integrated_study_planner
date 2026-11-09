import { isNativeApp } from '@/api/server'

/**
 * 网页 / 电脑端发系统通知（安卓 App 由本地通知插件负责，这里直接跳过）。
 * 手机浏览器（如安卓 Chrome）不允许页面直接 new Notification，只能经 Service Worker 发出，
 * 所以有注册好的 Service Worker 时优先走它，否则退回页面通知；都不支持时静默跳过，只保留页面内提醒。
 */
export async function webNotify(title, body, tag) {
  if (isNativeApp() || typeof window === 'undefined' || !('Notification' in window) || Notification.permission !== 'granted') return
  try {
    const registration = 'serviceWorker' in navigator ? await navigator.serviceWorker.getRegistration() : null
    if (registration?.showNotification) {
      await registration.showNotification(title, { body, tag, icon: '/icons/icon-192.png' })
      return
    }
  } catch {
    // Service Worker 不可用时退回页面通知
  }
  try {
    new Notification(title, { body, tag })
  } catch {
    // 不支持时只保留页面内提醒
  }
}
