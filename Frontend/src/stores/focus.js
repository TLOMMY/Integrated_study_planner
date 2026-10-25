import { defineStore } from 'pinia'
import { studyApi } from '@/api'
import { playChime } from '@/utils/chime'
import { localIso } from '@/utils/dates'
import { guardEnabled, noise, noisePrefs } from '@/utils/noise'
import { useHomeStore } from './home'
import { useTasksStore } from './tasks'
import { useUiStore } from './ui'

const STORAGE_KEY = 'focus-session-v2'
let ticker = null

// 跨设备同步用的时钟：本机时间 + 与服务器的偏差（由 useFocusSync 校准），只用于比较"谁更新"
let clockOffset = 0
export const setClockOffset = (offset) => {
  clockOffset = Number.isFinite(offset) ? offset : 0
}
export const syncNow = () => Date.now() + clockOffset

const newSessionId = () => `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`

// 防切出：离开超过这个时长才算一次
const AWAY_THRESHOLD = 3000
let guardInstalled = false

/**
 * 番茄钟（对标滴答清单）。
 * 用"累计已专注毫秒 + 当前段开始时间戳"计时，而不是 setInterval 递减，
 * 切页面、锁屏、刷新后时间依然准确。
 * v4：每轮有 sessionId 与 updatedAt，供跨设备同步（useFocusSync）判断新旧与去重；
 *     白噪音随开始 / 暂停 / 结束联动；专注中切走页面会记录次数并在回来时温和提醒。
 */
export const useFocusStore = defineStore('focus', {
  state: () => ({
    status: 'idle', // idle | running | paused | finished
    task: null,
    plannedMinutes: 25,
    accumulatedMs: 0,
    segmentStart: null,
    startedAt: null,
    now: Date.now(),
    saving: false,
    lastResult: null,
    sessionId: null,
    updatedAt: 0,
    distractions: 0,
    hiddenAt: null,
    noiseKind: noisePrefs.kind,
    noiseVolume: noisePrefs.volume,
  }),

  getters: {
    plannedMs: (state) => state.plannedMinutes * 60000,
    elapsedMs(state) {
      const running = state.status === 'running' && state.segmentStart ? state.now - state.segmentStart : 0
      return Math.min(this.plannedMs, state.accumulatedMs + running)
    },
    remainingMs() {
      return Math.max(0, this.plannedMs - this.elapsedMs)
    },
    progress() {
      return this.plannedMs ? this.elapsedMs / this.plannedMs : 0
    },
    clock() {
      const total = Math.ceil(this.remainingMs / 1000)
      return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`
    },
    active: (state) => state.status === 'running' || state.status === 'paused',
  },

  actions: {
    setup({ task = null, minutes = 25 } = {}) {
      if (this.active) return false
      this.$patch({ status: 'idle', task, plannedMinutes: minutes, accumulatedMs: 0, segmentStart: null, startedAt: null, lastResult: null, sessionId: null, distractions: 0 })
      return true
    },

    start() {
      this.startedAt = this.startedAt || localIso()
      this.sessionId = this.sessionId || newSessionId()
      this.segmentStart = Date.now()
      this.status = 'running'
      this.updatedAt = syncNow()
      this.persist()
      this.startTicker()
      this.installGuard()
      // start 总是由按钮点击触发，此时可以合法地开始播放音频
      if (this.noiseKind !== 'off') noise.play(this.noiseKind)
    },

    pause() {
      if (this.status !== 'running') return
      this.accumulatedMs += Date.now() - this.segmentStart
      this.segmentStart = null
      this.status = 'paused'
      this.updatedAt = syncNow()
      this.persist()
      noise.pause()
    },

    resume() {
      if (this.status === 'paused') this.start()
    },

    tick() {
      this.now = Date.now()
      if (this.status === 'running' && this.remainingMs <= 0) this.finish(true)
    },

    startTicker() {
      clearInterval(ticker)
      ticker = setInterval(() => {
        if (!this.active) {
          clearInterval(ticker)
          ticker = null
          document.title = '学业管家'
          return
        }
        this.tick()
        if (this.status === 'running') document.title = `${this.clock} · 专注中`
      }, 500)
    },

    /** 结束专注：natural=true 表示倒计时自然结束；否则是用户提前点"完成"。 */
    async finish(natural = false) {
      if (!this.active) return null
      if (this.status === 'running') {
        this.accumulatedMs += Date.now() - this.segmentStart
        this.segmentStart = null
      }
      const minutes = Math.min(this.plannedMinutes, Math.floor(this.accumulatedMs / 60000))
      this.status = 'finished'
      this.now = Date.now()
      this.updatedAt = syncNow()
      localStorage.removeItem(STORAGE_KEY)
      noise.stop()
      if (natural) playChime()
      document.title = '学业管家'

      const ui = useUiStore()
      if (minutes < 1) {
        ui.toast('专注不足 1 分钟，本次不计入记录', 'warning')
        this.lastResult = { minutes: 0, distractions: this.distractions }
        return this.lastResult
      }
      return this.save(minutes)
    },

    async save(minutes) {
      const ui = useUiStore()
      this.saving = true
      try {
        const result = await studyApi.record({
          task_id: this.task?.id || null,
          duration_minutes: minutes,
          planned_minutes: this.plannedMinutes,
          completed: minutes >= this.plannedMinutes,
          started_at: this.startedAt,
          session_id: this.sessionId,
        })
        if (result.duplicate) {
          this.lastResult = { minutes, duplicate: true, distractions: this.distractions }
          ui.toast('这轮专注已在其他设备上记录过了', 'info')
          return this.lastResult
        }
        this.lastResult = { minutes, record: result.record, task: result.task, distractions: this.distractions }
        ui.reward(result.reward)
        const freeze = result.reward?.streak_freeze
        if (freeze?.used?.length) ui.toast(`已用 ${freeze.used.length} 张保护卡保住连续记录`, 'success', 3200)
        else if (freeze?.earned?.length) ui.toast('连续学习满 7 天，获得 1 张断签保护卡', 'success', 3200)
        useHomeStore().refresh()
        if (this.task) useTasksStore().loadToday().catch(() => {})
      } catch (error) {
        this.lastResult = { minutes, error: error.message, pending: true, distractions: this.distractions }
        ui.fail(error, '专注记录保存失败')
      } finally {
        this.saving = false
      }
      return this.lastResult
    },

    retrySave() {
      if (this.lastResult?.pending) return this.save(this.lastResult.minutes)
    },

    abandon() {
      clearInterval(ticker)
      ticker = null
      localStorage.removeItem(STORAGE_KEY)
      document.title = '学业管家'
      noise.stop()
      const { noiseKind, noiseVolume } = this
      this.$reset()
      this.$patch({ noiseKind, noiseVolume, updatedAt: syncNow() })
    },

    persist() {
      const { status, task, plannedMinutes, accumulatedMs, segmentStart, startedAt, sessionId, updatedAt, distractions } = this
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ status, task, plannedMinutes, accumulatedMs, segmentStart, startedAt, sessionId, updatedAt, distractions }))
    },

    /** 刷新页面后恢复进行中的番茄。 */
    restore() {
      if (this.active) return
      try {
        const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null')
        if (!saved || !['running', 'paused'].includes(saved.status)) return
        this.$patch({ ...saved, now: Date.now() })
        this.startTicker()
        this.installGuard()
        this.tick()
      } catch {
        localStorage.removeItem(STORAGE_KEY)
      }
    },

    // ------------------------------------------------------------ 跨设备同步（useFocusSync 调用）
    /** 上报给服务器的快照。 */
    syncSnapshot(device) {
      const ended = !this.active
      return {
        status: ended ? 'idle' : this.status,
        session_id: this.sessionId,
        task: ended ? null : this.task,
        planned_minutes: this.plannedMinutes,
        accumulated_ms: Math.round(this.accumulatedMs),
        segment_start: this.status === 'running' ? this.segmentStart : null,
        started_at: this.startedAt,
        updated_at: this.updatedAt || syncNow(),
        device,
      }
    },

    /** 采用其他设备上较新的专注状态（接管或同步暂停 / 继续）。 */
    applyRemote(remote) {
      const wasRunning = this.status === 'running'
      this.$patch({
        status: remote.status,
        task: remote.task || null,
        plannedMinutes: remote.planned_minutes || 25,
        accumulatedMs: remote.accumulated_ms || 0,
        segmentStart: remote.status === 'running' ? remote.segment_start || Date.now() : null,
        startedAt: remote.started_at || localIso(),
        sessionId: remote.session_id,
        updatedAt: remote.updated_at,
        now: Date.now(),
        lastResult: null,
      })
      this.persist()
      this.startTicker()
      this.installGuard()
      if (wasRunning && remote.status !== 'running') noise.pause()
      this.tick()
    },

    /** 这一轮已在其他设备上结束：本机停下，不再重复记录。 */
    endedElsewhere(updatedAt) {
      clearInterval(ticker)
      ticker = null
      localStorage.removeItem(STORAGE_KEY)
      document.title = '学业管家'
      noise.stop()
      const { noiseKind, noiseVolume } = this
      this.$reset()
      this.$patch({ noiseKind, noiseVolume, updatedAt })
    },

    // ------------------------------------------------------------ 白噪音
    setNoise(kind) {
      this.noiseKind = kind
      noisePrefs.kind = kind
      if (kind === 'off') noise.stop()
      // 选择发生在点击里：专注进行中立即切换，未开始时试听一下
      else if (this.status === 'running' || this.status === 'idle' || this.status === 'finished') noise.play(kind)
    },
    setNoiseVolume(value) {
      this.noiseVolume = value
      noise.setVolume(value)
    },
    /** 离开专注页且未在专注时，停掉试听。 */
    stopPreview() {
      if (this.status !== 'running') noise.stop()
    },

    // ------------------------------------------------------------ 防切出提醒
    installGuard() {
      if (guardInstalled || typeof document === 'undefined') return
      guardInstalled = true
      document.addEventListener('visibilitychange', () => this.onVisibility())
    },
    onVisibility() {
      if (this.status !== 'running' || !guardEnabled()) {
        this.hiddenAt = null
        return
      }
      if (document.hidden) {
        this.hiddenAt = Date.now()
        return
      }
      if (!this.hiddenAt) return
      const away = Date.now() - this.hiddenAt
      this.hiddenAt = null
      if (away < AWAY_THRESHOLD) return
      this.distractions += 1
      this.persist()
      const seconds = Math.round(away / 1000)
      const span = seconds >= 60 ? `${Math.floor(seconds / 60)} 分 ${seconds % 60} 秒` : `${seconds} 秒`
      useUiStore().toast(`欢迎回来，刚才离开了 ${span}。本轮第 ${this.distractions} 次切出，继续加油`, 'warning', 3600)
    },
  },
})
