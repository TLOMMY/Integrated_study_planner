import { onBeforeUnmount, onMounted, ref } from 'vue'
import dayjs from 'dayjs'
import { isNativeApp } from '@/api/server'
import { useHomeStore } from '@/stores/home'
import { useUiStore } from '@/stores/ui'

const ENABLED_KEY = 'class-reminder-enabled'
const LEAD_MINUTES = 10

export const reminderEnabled = ref(localStorage.getItem(ENABLED_KEY) !== '0')

export const setReminderEnabled = async (value) => {
  reminderEnabled.value = value
  localStorage.setItem(ENABLED_KEY, value ? '1' : '0')
  if (value && 'Notification' in window && Notification.permission === 'default' && !isNativeApp()) {
    await Notification.requestPermission().catch(() => {})
  }
}

/**
 * 课前提醒（对标 WakeUp）：页面打开期间，上课前 10 分钟弹出提醒；
 * 已授权浏览器通知时同时发送系统通知。每节课每天只提醒一次。
 */
export function useClassReminder() {
  const home = useHomeStore()
  const ui = useUiStore()
  let timer = null

  const check = async () => {
    if (!reminderEnabled.value) return
    if (!home.summary || home.summary.date !== dayjs().format('YYYY-MM-DD')) await home.refresh()
    const courses = home.summary?.courses || []
    const now = dayjs()
    for (const course of courses) {
      const start = dayjs(`${home.summary.date} ${course.start_time}`)
      const minutes = start.diff(now, 'minute', true)
      const key = `reminded-${home.summary.date}-${course.id}`
      if (minutes > 0 && minutes <= LEAD_MINUTES && !sessionStorage.getItem(key)) {
        sessionStorage.setItem(key, '1')
        const text = `${course.title} ${Math.ceil(minutes)} 分钟后开始${course.location ? ` · ${course.location}` : ''}`
        ui.toast(text, 'warning', 6000)
        // 安卓 App 里课前提醒已由 useReminders 排进系统通知，这里只弹页面内提醒，避免重复
        if (!isNativeApp() && 'Notification' in window && Notification.permission === 'granted') {
          try {
            new Notification('上课提醒', { body: text, tag: key })
          } catch {
            // 部分浏览器只允许 Service Worker 发通知
          }
        }
      }
    }
  }

  onMounted(() => {
    check()
    timer = setInterval(check, 60000)
  })
  onBeforeUnmount(() => clearInterval(timer))
}
