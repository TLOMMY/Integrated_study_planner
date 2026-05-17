import { computed } from 'vue'

/**
 * 学习计划统计 composable
 */
export const usePlanStats = (plans) => {
  /**
   * 进行中的计划数量
   */
  const activeCount = computed(() => {
    return plans.value.filter(
      (plan) => plan.type !== 'finished'
    ).length
  })

  /**
   * 已完成计划数量
   */
  const finishedCount = computed(() => {
    return plans.value.filter(
      (plan) => plan.type === 'finished'
    ).length
  })

  /**
   * 平均进度
   */
  const averageProgress = computed(() => {
    if (!plans.value.length) return 0

    const total = plans.value.reduce(
      (sum, plan) =>
        sum + Number(plan.progress || 0),
      0
    )

    return Math.round(total / plans.value.length)
  })

  /**
   * 总任务数量
   */
  const totalPlans = computed(() => {
    return plans.value.length
  })

  /**
   * 加急计划数量
   */
  const urgentPlans = computed(() => {
    return plans.value.filter(
      (plan) => plan.status === '加急'
    ).length
  })

  /**
   * 已结束计划数量
   */
  const endedPlans = computed(() => {
    return plans.value.filter(
      (plan) => plan.status === '已结束'
    ).length
  })

  /**
   * 平均剩余天数
   */
  const averageRemainingDays = computed(() => {
    const validPlans = plans.value.filter(
      (plan) => typeof plan.remainingDays === 'number'
    )

    if (!validPlans.length) return 0

    const total = validPlans.reduce(
      (sum, plan) => sum + plan.remainingDays,
      0
    )

    return Math.round(total / validPlans.length)
  })

  /**
   * 完成率
   */
  const completionRate = computed(() => {
    if (!plans.value.length) return 0

    return Math.round(
      (finishedCount.value / plans.value.length) *
        100
    )
  })

  return {
    activeCount,
    finishedCount,
    averageProgress,
    totalPlans,
    urgentPlans,
    endedPlans,
    averageRemainingDays,
    completionRate
  }
}