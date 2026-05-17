import { defineStore } from 'pinia'
import { recordStudyApi } from '@/api/study'
let timer = null

const STORAGE_KEY = 'focus-session'

export const useFocusStore = defineStore('focus', {
  state: () => ({
    /**
     * 当前任务
     */
    focusTask: '预习高数第3章',

    /**
     * 名言
     */
    quote: '“书山有路勤为径，学海无涯苦作舟”',

    /**
     * 初始时间
     */
    initialSeconds: 25 * 60,

    /**
     * 剩余时间
     */
    totalSeconds: 25 * 60,

    /**
     * 是否暂停
     */
    isPaused: true,

    /**
     * 是否结束
     */
    isFinished: false,
  }),

  getters: {
    /**
     * 分钟
     */
    minutes(state) {
      return String(Math.floor(state.totalSeconds / 60)).padStart(2, '0')
    },

    /**
     * 秒
     */
    seconds(state) {
      return String(state.totalSeconds % 60).padStart(2, '0')
    },

    /**
     * 百分比进度
     */
    progress(state) {
      return (
        (state.totalSeconds / state.initialSeconds) * 100
      )
    },
  },

  actions: {
    /**
     * 启动计时器
     */
    startTimer() {
      /**
       * 已经存在 timer
       */
      if (timer) return

      this.isPaused = false

      timer = setInterval(() => {
        if (this.totalSeconds > 0) {
          this.totalSeconds--

          /**
           * 自动缓存
           */
          this.saveSession()
        } else {
          this.finishTimer()
        }
      }, 1000)
    },

    /**
     * 暂停
     */
    pauseTimer() {
      this.isPaused = true

      clearInterval(timer)

      timer = null

      this.saveSession()
    },

    /**
     * 继续
     */
    resumeTimer() {
      if (!this.isPaused) return

      this.startTimer()
    },

    /**
     * 完成
     */
  async finishTimer() {
  clearInterval(timer)

  timer = null

  this.isFinished = true

  this.isPaused = true

  /**
   * 提交学习记录
   */
  try {
    await recordStudyApi({
      task: this.focusTask,
      duration: this.initialSeconds / 60,
    })

    console.log('学习记录提交成功')
  } catch (error) {
    console.error('学习记录提交失败', error)
  }

  localStorage.removeItem(STORAGE_KEY)
},

    /**
     * 重置
     */
    resetTimer() {
      clearInterval(timer)

      timer = null

      this.totalSeconds = this.initialSeconds

      this.isPaused = true

      this.isFinished = false

      localStorage.removeItem(STORAGE_KEY)
    },

    /**
     * 设置专注任务
     */
    setFocusTask(task) {
      this.focusTask = task
    },

    /**
     * 保存 session
     */
    saveSession() {
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({
          focusTask: this.focusTask,
          quote: this.quote,
          initialSeconds: this.initialSeconds,
          totalSeconds: this.totalSeconds,
          isPaused: this.isPaused,
          isFinished: this.isFinished,
        })
      )
    },

    /**
     * 恢复 session
     */
    restoreSession() {
      const saved = localStorage.getItem(STORAGE_KEY)

      if (!saved) return

      const data = JSON.parse(saved)

      this.focusTask = data.focusTask
      this.quote = data.quote
      this.initialSeconds = data.initialSeconds
      this.totalSeconds = data.totalSeconds
      this.isPaused = data.isPaused
      this.isFinished = data.isFinished
    },
  },
})