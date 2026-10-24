import { defineStore } from 'pinia'
import { planApi, studyApi } from '@/api'
import { useUiStore } from './ui'
import { useTasksStore } from './tasks'

export const usePlansStore = defineStore('plans', {
  state: () => ({
    items: [],
    counts: { active: 0, completed: 0, archived: 0, trash: 0 },
    filter: 'active',
    loading: false,
  }),

  actions: {
    async load(filter = this.filter) {
      this.filter = filter
      this.loading = !this.items.length
      try {
        const data = await planApi.list(filter)
        this.items = data.items
        this.counts = data.counts
      } finally {
        this.loading = false
      }
    },

    detail(id) {
      return planApi.detail(id)
    },

    async create(payload) {
      const result = await planApi.create(payload)
      useUiStore().reward(result.reward)
      useUiStore().success('计划已创建')
      await this.load()
      return result.plan
    },

    async update(id, payload, message = '计划已更新') {
      const plan = await planApi.update(id, payload)
      useUiStore().success(message)
      await this.load()
      return plan
    },

    async remove(plan) {
      const ui = useUiStore()
      const ok = await ui.confirm({
        title: '移入回收站？',
        message: `${plan.task_total ? `计划中的 ${plan.task_total} 个任务会一起隐藏。` : ''}30 天内可以在回收站恢复，之后自动彻底删除。`,
        confirmText: '移入回收站',
        danger: true,
      })
      if (!ok) return false
      await planApi.remove(plan.id)
      ui.success('已移入回收站')
      await this.load()
      useTasksStore().afterChange()
      return true
    },

    async restore(ids) {
      const result = await planApi.restore(ids)
      useUiStore().success(`已恢复 ${result.count} 个计划`)
      await this.load()
      useTasksStore().afterChange()
    },

    async purge(ids) {
      const ok = await useUiStore().confirm({ title: `彻底删除 ${ids.length} 个计划？`, message: '计划和其中的任务会被永久删除，无法恢复。已获得的 XP 不受影响。', confirmText: '彻底删除', danger: true })
      if (!ok) return false
      await planApi.purge(ids)
      useUiStore().success('已彻底删除')
      await this.load()
      return true
    },

    async emptyTrash() {
      const ok = await useUiStore().confirm({ title: '清空回收站？', message: `回收站里的 ${this.counts.trash} 个计划会被永久删除，无法恢复。`, confirmText: '清空', danger: true })
      if (!ok) return false
      await planApi.emptyTrash()
      useUiStore().success('回收站已清空')
      await this.load()
      return true
    },
  },
})

export const useStatsStore = defineStore('stats', {
  state: () => ({
    data: null,
    leaderboard: null,
    loading: false,
  }),

  actions: {
    async load() {
      this.loading = !this.data
      try {
        this.data = await studyApi.stats()
      } finally {
        this.loading = false
      }
      return this.data
    },
    async loadLeaderboard() {
      this.leaderboard = await studyApi.leaderboard()
      return this.leaderboard
    },
  },
})
