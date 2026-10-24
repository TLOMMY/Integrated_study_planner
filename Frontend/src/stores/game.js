import { defineStore } from 'pinia'

/** 等级 / 连续打卡 / 每日目标的全局快照，任何接口返回奖励回执时都会刷新。 */
export const useGameStore = defineStore('game', {
  state: () => ({
    level: null,
    streak: null,
    dailyGoal: null,
  }),

  actions: {
    apply(source) {
      if (!source) return
      if (source.level) this.level = source.level
      if (source.streak) this.streak = source.streak
      if (source.daily_goal) this.dailyGoal = source.daily_goal
    },
  },
})
