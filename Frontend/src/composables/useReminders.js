/**
 * 任务提醒：页面内提醒 + 系统通知 / 安卓本地通知。在 MainLayout 中调用。
 *
 * - 网页 / 电脑端：页面打开期间每 20 秒检查一次，到点弹出 Toast，已授权时同时发浏览器通知；
 *   同一条提醒（任务 id + 提醒时间）只触发一次，任务完成 / 删除后接口不再返回它，自然不会提醒。
 * - 安卓 App：登录后与任务变化后，把未来 7 天的任务提醒和课前 10 分钟提醒排进系统通知
 *   （先取消本模块排过的旧通知再重排），App 关闭也能按时提醒。
 */
import { onBeforeUnmount, onMounted, reactive, watch } from 'vue'
import { useRouter } from 'vue-router'
import dayjs from 'dayjs'
import { plannerApi } from '@/api/planner'
import { isNativeApp } from '@/api/server'
import { tokenStorage } from '@/api/request'
import { useTasksStore } from '@/stores/tasks'
import { useTimetableStore } from '@/stores/timetable'
import { useUiStore } from '@/stores/ui'
import { coursesOnDate } from '@/utils/dates'
import { reminderEnabled as classReminderEnabled } from './useClassReminder'

const ENABLED_KEY = 'task-reminder-enabled'
const LEAD_KEY = 'task-reminder-lead'
const FIRED_KEY = 'task-reminders-fired'
const ASKED_KEY = 'notify-permission-asked'
const CLASS_LEAD = 10
const LATE_WINDOW = 15 * 60 * 1000

// 系统通知 id 分段（Java int 范围内，互不冲突）：课前提醒 900000+，测试 999999，任务 1000000+任务 id
const ID_COURSE = 900000
const ID_TEST = 999999
const ID_TASK = 1000000
const CHANNEL = 'study-reminders'

const storedLead = localStorage.getItem(LEAD_KEY)

/** 提醒设置（本机保存）：enabled 任务提醒总开关；lead 新建定时任务时默认提前几分钟（null 表示不自动设置）。 */
export const reminderSettings = reactive({
  enabled: localStorage.getItem(ENABLED_KEY) !== '0',
  lead: storedLead === null ? 15 : storedLead === '' ? null : Number(storedLead),
})

export const setTaskReminderEnabled = (value) => {
  reminderSettings.enabled = value
  localStorage.setItem(ENABLED_KEY, value ? '1' : '0')
  scheduleResync()
}

export const setDefaultLead = (value) => {
  reminderSettings.lead = value
  localStorage.setItem(LEAD_KEY, value === null ? '' : String(value))
}

// ---------------------------------------------------------------- 系统通知权限
let pluginPromise = null
const plugin = () => {
  if (!isNativeApp()) return Promise.resolve(null)
  pluginPromise ||= import('@capacitor/local-notifications').then((m) => m.LocalNotifications).catch(() => null)
  return pluginPromise
}

/** 'granted' | 'denied' | 'prompt' | 'unsupported' */
export async function notificationPermission() {
  const native = await plugin()
  if (native) {
    const { display } = await native.checkPermissions()
    return display === 'granted' ? 'granted' : display === 'denied' ? 'denied' : 'prompt'
  }
  if (!('Notification' in window)) return 'unsupported'
  return Notification.permission === 'default' ? 'prompt' : Notification.permission
}

export async function requestNotificationPermission() {
  localStorage.setItem(ASKED_KEY, '1')
  const native = await plugin()
  if (native) {
    const { display } = await native.requestPermissions()
    scheduleResync()
    return display === 'granted' ? 'granted' : display === 'denied' ? 'denied' : 'prompt'
  }
  if (!('Notification' in window)) return 'unsupported'
  const result = await Notification.requestPermission().catch(() => Notification.permission)
  return result === 'default' ? 'prompt' : result
}

const webNotify = (title, body, tag) => {
  if (isNativeApp() || !('Notification' in window) || Notification.permission !== 'granted') return
  try {
    new Notification(title, { body, tag })
  } catch {
    // 部分浏览器（如安卓 Chrome）只允许 Service Worker 发通知，失败时只保留页面内提醒
  }
}

const describe = (item) => {
  const when = item.start_time ? `${item.due_date === dayjs().format('YYYY-MM-DD') ? '' : `${dayjs(item.due_date).format('M月D日')} `}${item.start_time} 开始` : '到时间了'
  return `${item.title}${item.subject ? ` · ${item.subject}` : ''}（${when}）`
}

/** 测试提醒：立即弹出页面提醒；手机上 5 秒后发一条系统通知。 */
export async function testReminder() {
  const ui = useUiStore()
  ui.toast('这是一条测试提醒：复习高数（19:00 开始）', 'warning', 5000)
  webNotify('学习提醒', '这是一条测试提醒：复习高数（19:00 开始）', 'reminder-test')
  const native = await plugin()
  if (native) {
    await ensureChannel(native)
    await native.schedule({
      notifications: [{ id: ID_TEST, title: '学习提醒', body: '这是一条测试提醒，5 秒前发出', channelId: CHANNEL, schedule: { at: new Date(Date.now() + 5000), allowWhileIdle: true } }],
    })
    ui.toast('5 秒后会收到一条系统通知，可以先切到桌面看看', 'info', 4000)
  }
}

// ---------------------------------------------------------------- 已触发记录（本机）
const readFired = () => {
  try {
    return JSON.parse(localStorage.getItem(FIRED_KEY) || '{}') || {}
  } catch {
    return {}
  }
}
const markFired = (key) => {
  const fired = readFired()
  const cutoff = Date.now() - 2 * 86400000
  for (const [k, at] of Object.entries(fired)) if (at < cutoff) delete fired[k]
  fired[key] = Date.now()
  localStorage.setItem(FIRED_KEY, JSON.stringify(fired))
}

// ---------------------------------------------------------------- 安卓本地通知
let channelReady = false
const ensureChannel = async (native) => {
  if (channelReady) return
  channelReady = true
  await native.createChannel({ id: CHANNEL, name: '学习提醒', description: '任务提醒与课前提醒', importance: 4, vibration: true }).catch(() => {})
}

let resyncTimer = null
let resyncHandler = null
/** 任务变化后稍等再重排，避免连续操作时频繁取消 / 重排。 */
function scheduleResync(delay = 1500) {
  clearTimeout(resyncTimer)
  resyncTimer = setTimeout(() => resyncHandler?.(), delay)
}

export async function cancelNativeReminders() {
  const native = await plugin()
  if (!native) return
  const { notifications } = await native.getPending().catch(() => ({ notifications: [] }))
  const ours = notifications.filter((n) => Number(n.id) >= ID_COURSE)
  if (ours.length) await native.cancel({ notifications: ours.map((n) => ({ id: Number(n.id) })) }).catch(() => {})
}

async function syncNative(items) {
  const native = await plugin()
  if (!native) return
  let permission = await notificationPermission()
  // 第一次使用时主动申请一次权限；之后只在设置页手动开启
  if (permission === 'prompt' && !localStorage.getItem(ASKED_KEY)) permission = await requestNotificationPermission()
  await cancelNativeReminders()
  if (permission !== 'granted') return
  await ensureChannel(native)

  const now = Date.now()
  const list = []
  if (reminderSettings.enabled) {
    for (const item of items) {
      const at = dayjs(item.remind_at).valueOf()
      if (at > now) list.push({ id: ID_TASK + item.id, title: '任务提醒', body: describe(item), at, extra: { route: '/' } })
    }
  }
  if (classReminderEnabled.value) {
    const timetable = useTimetableStore()
    await timetable.ensure().catch(() => {})
    for (let offset = 0; offset < 7; offset++) {
      const date = dayjs().add(offset, 'day').format('YYYY-MM-DD')
      coursesOnDate(timetable.courses, timetable.meta, date).forEach((course, index) => {
        const at = dayjs(`${date} ${course.start_time}`).subtract(CLASS_LEAD, 'minute').valueOf()
        if (at > now && index < 100) {
          const where = course.classroom ? ` · ${course.classroom}` : ''
          list.push({ id: ID_COURSE + offset * 100 + index, title: '上课提醒', body: `${course.course_name} ${CLASS_LEAD} 分钟后开始${where}`, at, extra: { route: '/day' } })
        }
      })
    }
  }
  if (!list.length) return
  // 安卓对单个应用的待发通知数量有限制，只排最近的 60 条
  list.sort((a, b) => a.at - b.at)
  await native.schedule({
    notifications: list.slice(0, 60).map(({ at, ...n }) => ({ ...n, channelId: CHANNEL, schedule: { at: new Date(at), allowWhileIdle: true } })),
  })
}

// ---------------------------------------------------------------- 组合式函数
let actionListener = null

export function useReminders() {
  const tasks = useTasksStore()
  const ui = useUiStore()
  const router = useRouter()
  let items = []
  let fetchedAt = 0
  let checkTimer = null

  const fetchItems = async () => {
    if (!tokenStorage.get()) return
    try {
      items = (await plannerApi.reminders(7)).items
      fetchedAt = Date.now()
    } catch {
      // 断网或服务器暂不可用时沿用上次的数据
    }
  }

  const check = async () => {
    if (!reminderSettings.enabled) return
    if (Date.now() - fetchedAt > 5 * 60000) await fetchItems()
    const now = Date.now()
    const fired = readFired()
    for (const item of items) {
      const at = dayjs(item.remind_at).valueOf()
      const key = `${item.id}@${item.remind_at}`
      if (at <= now && now - at < LATE_WINDOW && !fired[key]) {
        markFired(key)
        const text = describe(item)
        ui.toast(`提醒：${text}`, 'warning', 8000)
        webNotify('任务提醒', text, `task-${key}`)
      }
    }
  }

  resyncHandler = async () => {
    await fetchItems()
    await syncNative(items).catch(() => {})
    check()
  }

  const onVisible = () => document.visibilityState === 'visible' && scheduleResync(300)

  watch(() => tasks.version, () => scheduleResync())
  watch(classReminderEnabled, () => scheduleResync())

  onMounted(() => {
    scheduleResync(800)
    checkTimer = setInterval(check, 20000)
    document.addEventListener('visibilitychange', onVisible)
    // 点系统通知打开 App 后跳到对应页面（任务 → 首页，课程 → 日程）
    plugin().then((native) => {
      if (!native || actionListener) return
      actionListener = native.addListener('localNotificationActionPerformed', (event) => {
        const route = event?.notification?.extra?.route
        if (route) router.push(route).catch(() => {})
      })
    })
  })
  onBeforeUnmount(() => {
    clearInterval(checkTimer)
    clearTimeout(resyncTimer)
    document.removeEventListener('visibilitychange', onVisible)
    resyncHandler = null
    // 退出登录时取消已排的系统通知，换账号后不会收到上一个人的提醒
    if (!tokenStorage.get()) cancelNativeReminders().catch(() => {})
  })
}
