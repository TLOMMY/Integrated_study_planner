/**
 * 进行中的专注跨设备同步。在 MainLayout 与专注页中调用（专注页在 MainLayout 之外）。
 *
 * - 本机开始 / 暂停 / 继续 / 结束 / 放弃时上报（PUT /study/focus-state）；
 * - 每 30 秒、以及页面重新可见时拉取；
 * - 以 updated_at 较新的为准：本机空闲而服务器上有进行中的专注时接管并提示；
 *   同一轮在其他设备上暂停 / 继续时跟随；在其他设备上结束时本机停下（不会重复记录，服务器按会话 id 去重）。
 * 计时仍完全由 stores/focus.js 的"累计毫秒 + 段开始时间戳"负责，这里只搬运状态。
 */
import { onBeforeUnmount, onMounted } from 'vue'
import { focusSyncApi } from '@/api/growth'
import { isNativeApp } from '@/api/server'
import { tokenStorage } from '@/api/request'
import { setClockOffset, syncNow, useFocusStore } from '@/stores/focus'
import { useUiStore } from '@/stores/ui'

const POLL_MS = 30000
const PUSH_ACTIONS = new Set(['start', 'pause', 'resume', 'finish', 'abandon'])

let users = 0
let timer = null
let unsubscribe = null
let pulling = false
let chain = Promise.resolve()
// 本机已结束的会话：服务器若还显示它在进行中（旧状态），不接管、而是补发结束
const endedHere = new Set()

export const deviceName = () => {
  const ua = navigator.userAgent || ''
  if (isNativeApp()) return '手机 App'
  if (/Electron/i.test(ua)) return '电脑客户端'
  if (/iPad|Tablet/i.test(ua)) return '平板浏览器'
  if (/Android|iPhone|Mobile/i.test(ua)) return '手机浏览器'
  return '电脑浏览器'
}

function push() {
  const focus = useFocusStore()
  if (!tokenStorage.get()) return chain
  const snapshot = focus.syncSnapshot(deviceName())
  if (!snapshot.session_id) return chain
  chain = chain
    .then(() => focusSyncApi.put(snapshot))
    .then((result) => {
      if (!result.accepted) reconcile(result.state, result.session_id, result.updated_at)
    })
    .catch(() => {})
  return chain
}

/** 对比服务器与本机，决定接管、跟随、停下还是补发。 */
function reconcile(remote, remoteSession, remoteAt) {
  const focus = useFocusStore()
  const ui = useUiStore()
  const localAt = focus.updatedAt || 0

  if (remote && endedHere.has(remote.session_id)) {
    if (localAt > remoteAt) push()
    return
  }
  if (!remote) {
    // 服务器上没有进行中的专注
    if (focus.active && remoteSession === focus.sessionId && remoteAt > localAt) {
      focus.endedElsewhere(remoteAt)
      ui.toast('这一轮专注已在其他设备上结束', 'info')
    } else if (focus.active && remoteAt < localAt) {
      push()
    }
    return
  }
  if (remoteAt <= localAt) {
    if (focus.active) push()
    return
  }
  // 服务器较新
  if (focus.active && focus.sessionId === remote.session_id) {
    if (focus.status !== remote.status) ui.toast(remote.status === 'paused' ? `已在${remote.device || '其他设备'}上暂停` : `已在${remote.device || '其他设备'}上继续`, 'info')
    focus.applyRemote(remote)
    return
  }
  if (!focus.active || focus.status === 'finished') {
    focus.applyRemote(remote)
    ui.toast(`已同步${remote.device ? `「${remote.device}」` : '其他设备'}上的专注`, 'success', 3200)
    return
  }
  // 两台设备各自开了一轮：以较新的为准
  focus.applyRemote(remote)
  ui.toast('其他设备上有更新的专注，已切换过来', 'info', 3200)
}

async function pull() {
  if (pulling || !tokenStorage.get() || document.hidden) return
  pulling = true
  try {
    await chain
    const result = await focusSyncApi.get()
    if (result.server_time) setClockOffset(result.server_time - Date.now())
    reconcile(result.state, result.session_id, result.updated_at)
  } catch {
    // 离线或未登录时静默跳过，下次再试
  } finally {
    pulling = false
  }
}

const onVisible = () => {
  if (!document.hidden) pull()
}

function install() {
  const focus = useFocusStore()
  unsubscribe = focus.$onAction(({ name, store, after }) => {
    if (!PUSH_ACTIONS.has(name)) return
    const sessionBefore = store.sessionId
    after(() => {
      if (name === 'finish' || name === 'abandon') {
        if (!sessionBefore) return
        endedHere.add(sessionBefore)
        // 放弃后 store 已重置，补上会话 id 发出"已结束"
        const snapshot = store.syncSnapshot(deviceName())
        snapshot.session_id = sessionBefore
        snapshot.status = 'idle'
        snapshot.updated_at = Math.max(store.updatedAt || 0, syncNow())
        if (!tokenStorage.get()) return
        chain = chain.then(() => focusSyncApi.put(snapshot)).catch(() => {})
        return
      }
      push()
    })
  })
  document.addEventListener('visibilitychange', onVisible)
  timer = setInterval(pull, POLL_MS)
}

function uninstall() {
  unsubscribe?.()
  unsubscribe = null
  clearInterval(timer)
  timer = null
  document.removeEventListener('visibilitychange', onVisible)
}

export function useFocusSync() {
  onMounted(() => {
    users += 1
    if (users === 1) install()
    // 等本机 restore() 先从 localStorage 恢复，再与服务器比对
    setTimeout(pull, 300)
  })
  onBeforeUnmount(() => {
    users = Math.max(0, users - 1)
    if (users === 0) uninstall()
  })
}
