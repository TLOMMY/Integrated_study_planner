import { defineStore } from 'pinia'
import { getPlanListApi } from '@/api/plan'
import { mapPlanItem } from '@/utils/mapper/planMapper'

export const usePlanStore = defineStore('plan', {
  state: () => ({
    /**
     * 加载状态
     */
    loading: false,

    /**
     * 错误信息
     */
    error: null,

    /**
     * 统计信息
     */
    stats: {
      activeCount: 0,
      weeklyProgress: 0
    },

    /**
     * 计划列表
     */
    plans: []
  }),

  actions: {
    /**
     * 获取计划列表
     */
    async fetchPlans() {
      this.loading = true
      this.error = null

      try {
        const res = await getPlanListApi()

        /**
         * 后端统一返回:
         * {
         *   code,
         *   message,
         *   data
         * }
         */
        const data = res?.data

        /**
         * 防止后端返回 null
         */
        if (!Array.isArray(data)) {
          this.plans = []

          this.stats.activeCount = 0
          this.stats.weeklyProgress = 0

          return
        }

        /**
         * 数据映射
         */
        this.plans = data.map(mapPlanItem)

        /**
         * 统计：
         * 当前进行中的计划数量
         */
        this.stats.activeCount = this.plans.filter(
          (plan) => plan.type !== 'finished'
        ).length

        /**
         * 平均进度
         */
        const totalProgress = this.plans.reduce(
          (sum, plan) => sum + Number(plan.progress || 0),
          0
        )

        this.stats.weeklyProgress =
          this.plans.length > 0
            ? Math.round(totalProgress / this.plans.length)
            : 0
      } catch (error) {
        console.error('获取计划失败:', error)

        this.error =
          error.response?.data?.message ||
          error.message ||
          '获取计划失败'

        this.plans = [
  {
    id: 1,
    title: '高等数学强化',
    subject: '数学',
    progress: 75,
    type: 'ongoing'
  },
  {
    id: 2,
    title: '英语六级',
    subject: '英语',
    progress: 40,
    type: 'ongoing'
  },
  {
    id: 3,
    title: '数据结构复习',
    subject: '计算机',
    progress: 100,
    type: 'finished'
  }
]

this.stats.activeCount = this.plans.filter(
  (plan) => plan.type !== 'finished'
).length

const totalProgress = this.plans.reduce(
  (sum, plan) => sum + Number(plan.progress || 0),
  0
)

this.stats.weeklyProgress =
  this.plans.length > 0
    ? Math.round(totalProgress / this.plans.length)
    : 0
      } finally {
        this.loading = false
      }
    },

    /**
     * 创建计划
     */
    createPlan() {
      console.log('创建学习计划')
    },

    /**
     * 查看计划详情
     */
    viewPlanDetail(plan) {
      console.log('查看计划详情', plan)
    },

    /**
     * 打开筛选器
     */
    openFilter() {
      console.log('打开筛选器')
    }
  }
})