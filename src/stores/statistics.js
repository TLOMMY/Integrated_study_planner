import { defineStore } from 'pinia'
import { getStatisticsApi } from '@/api/statistics'

export const useStatisticsStore = defineStore('statistics', {
  state: () => ({
    user: {
      name: '',
      level: 0,
      exp: 0,
      progress: 0,
      nextLevelNeed: 0,
    },

    stats: [],

    badges: [],

    chartData: [],

    loading: false,
  }),

  actions: {
    async fetchStatistics() {
      try {
        this.loading = true

        const res = await getStatisticsApi()

        const data = res.data

        this.user = data.user

        this.stats = data.stats

        this.badges = data.badges

        this.chartData = data.chartData
      } catch (error) {
        console.error('获取统计数据失败', error)

        // fallback mock 数据
        this.user = {
          name: '测试用户',
          level: 6,
          exp: 820,
          progress: 70,
          nextLevelNeed: 1200,
        }

        this.stats = [
          {
            label: '学习时长',
            value: '128h',
          },
          {
            label: '完成任务',
            value: '64',
          },
          {
            label: '连续学习',
            value: '12天',
          },
        ]

        this.badges = [
          {
            id: 1,
            name: '学习达人',
          },
          {
            id: 2,
            name: '专注大师',
          },
        ]

        this.chartData = [12, 18, 9, 22, 30, 16, 28]
      } finally {
        this.loading = false
      }
    },
  },
})