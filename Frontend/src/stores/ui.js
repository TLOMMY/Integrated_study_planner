import { defineStore } from 'pinia'
import { useGameStore } from './game'

let seq = 0

export const useUiStore = defineStore('ui', {
  state: () => ({
    toasts: [],
    dialog: null,
    celebrations: [],
  }),

  actions: {
    toast(message, type = 'info', duration = 2400) {
      const id = ++seq
      this.toasts.push({ id, message, type })
      setTimeout(() => this.dismiss(id), duration)
    },
    success(message) {
      this.toast(message, 'success')
    },
    fail(error, fallback = '操作失败，请重试') {
      this.toast(error?.message || fallback, 'error', 3200)
    },
    dismiss(id) {
      this.toasts = this.toasts.filter((toast) => toast.id !== id)
    },

    /** Promise 风格的确认框：await ui.confirm({...}) 返回 true/false。 */
    confirm({ title, message = '', confirmText = '确定', cancelText = '取消', danger = false }) {
      return new Promise((resolve) => {
        this.dialog?.resolve(false)
        this.dialog = { title, message, confirmText, cancelText, danger, resolve }
      })
    },
    closeDialog(result) {
      this.dialog?.resolve(result)
      this.dialog = null
    },

    /**
     * 处理后端返回的奖励回执：小奖励用 Toast，升级 / 新成就 / 达成每日目标弹出庆祝层。
     */
    reward(reward) {
      if (!reward) return
      useGameStore().apply(reward)
      const big = reward.level_up || reward.goal_just_reached || reward.new_achievements?.length
      if (big) {
        this.celebrations.push({ id: ++seq, ...reward })
      } else if (reward.xp_gained > 0) {
        this.toast(`+${reward.xp_gained} XP`, 'xp', 1600)
      }
    },
    nextCelebration() {
      this.celebrations.shift()
    },
  },
})
