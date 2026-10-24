import { defineStore } from 'pinia'
import { studyApi } from '@/api'
import { playChime } from '@/utils/chime'
import { localIso } from '@/utils/dates'
import { useHomeStore } from './home'
import { useTasksStore } from './tasks'
import { useUiStore } from './ui'

const STORAGE_KEY = 'focus-session-v2'
let ticker = null

/**
 * 番茄钟（对标滴答清单）。
 * 用"累计已专注毫秒 + 当前段开始时间戳"计时，而不是 setInterval 递减，
 * 切页面、锁屏、刷新后时间依然准确。
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
      this.$patch({ status: 'idle', task, plannedMinutes: minutes, accumulatedMs: 0, segmentStart: null, startedAt: null, lastResult: null })
      return true
    },

    start() {
      this.startedAt = this.startedAt || localIso()
      this.segmentStart = Date.now()
      this.status = 'running'
      this.persist()
      this.startTicker()
    },

    pause() {
      if (this.status !== 'running') return
      this.accumulatedMs += Date.now() - this.segmentStart
      this.segmentStart = null
      this.status = 'paused'
      this.persist()
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
      localStorage.removeItem(STORAGE_KEY)
      if (natural) playChime()
      document.title = '学业管家'

      const ui = useUiStore()
      if (minutes < 1) {
        ui.toast('专注不足 1 分钟，本次不计入记录', 'warning')
        this.lastResult = { minutes: 0 }
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
        })
        this.lastResult = { minutes, record: result.record, task: result.task }
        ui.reward(result.reward)
        useHomeStore().refresh()
        if (this.task) useTasksStore().loadToday().catch(() => {})
      } catch (error) {
        this.lastResult = { minutes, error: error.message, pending: true }
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
      this.$reset()
    },

    persist() {
      const { status, task, plannedMinutes, accumulatedMs, segmentStart, startedAt } = this
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ status, task, plannedMinutes, accumulatedMs, segmentStart, startedAt }))
    },

    /** 刷新页面后恢复进行中的番茄。 */
    restore() {
      if (this.active) return
      try {
        const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null')
        if (!saved || !['running', 'paused'].includes(saved.status)) return
        this.$patch({ ...saved, now: Date.now() })
        this.startTicker()
        this.tick()
      } catch {
        localStorage.removeItem(STORAGE_KEY)
      }
    },
  },
})
