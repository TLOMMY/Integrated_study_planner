import { defineStore } from 'pinia'
import { helpForError, toastDuration } from '@/utils/toast'
import { useGameStore } from './game'

let seq = 0
const timers = new Map()

export const useUiStore = defineStore('ui', {
  state: () => ({
    toasts: [],
    dialog: null,
    celebrations: [],
    // 今天第一次打卡：不打断操作的小卡片（火苗动画），2.4 秒后自动消失
    checkin: null,
  }),

  actions: {
    /**
     * 弹出提示。第三个参数可以是停留毫秒数，或 { duration, help }；
     * help = { label, hash } 时显示"查看说明"，跳到使用手册对应位置。长文字自动延长停留时间。
     */
    toast(message, type = 'info', options = 2400) {
      const { duration = 2400, help = null } = typeof options === 'number' ? { duration: options } : options || {}
      const id = ++seq
      this.toasts.push({ id, message, type, help, expanded: false })
      const timer = setTimeout(() => this.dismiss(id), toastDuration(message, duration))
      timers.set(id, timer)
    },
    success(message) {
      this.toast(message, 'success')
    },
    fail(error, fallback = '操作失败，请重试') {
      this.toast(error?.message || fallback, 'error', { duration: 3200, help: helpForError(error) })
    },
    /** 点开被截断的提示：展开全文，并停留到再次点击或 8 秒后。 */
    expand(id) {
      const toast = this.toasts.find((t) => t.id === id)
      if (!toast) return
      toast.expanded = true
      clearTimeout(timers.get(id))
      timers.set(id, setTimeout(() => this.dismiss(id), 8000))
    },
    dismiss(id) {
      clearTimeout(timers.get(id))
      timers.delete(id)
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
        // 大庆祝层里同时播放打卡火苗（如果这次也是今天第一次打卡）
        this.celebrations.push({ id: ++seq, ...reward })
      } else if (reward.checked_in_now) {
        const id = ++seq
        this.checkin = { id, days: reward.streak?.current || 1, xp: reward.xp_gained || 0 }
        setTimeout(() => this.checkin?.id === id && (this.checkin = null), 2400)
      } else if (reward.xp_gained > 0) {
        this.toast(`+${reward.xp_gained} XP`, 'xp', 1600)
      }
    },
    nextCelebration() {
      this.celebrations.shift()
    },
  },
})
