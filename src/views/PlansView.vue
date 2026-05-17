<script setup>
import { onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import { Icon } from '@iconify/vue'

import { usePlanStore } from '@/stores/plan'
import { usePlanStats } from '@/composables/usePlanStats'

import PlanCard from '@/components/plan/PlanCard.vue'

const planStore = usePlanStore()

/**
 * store refs
 */
const { plans, loading, error } =
  storeToRefs(planStore)

/**
 * 统计
 */
const {
  activeCount,
  averageProgress
} = usePlanStats(plans)

/**
 * 初始化获取数据
 */
onMounted(() => {
  planStore.fetchPlans()
})
</script>

<template>
  <div class="relative w-full h-full overflow-hidden bg-white">
    <!-- 顶部导航栏 -->
    <div
      class="h-[88px] px-6 pt-10 pb-4 flex justify-between items-center bg-white border-b border-gray-50"
    >
      <h1 class="text-xl font-bold text-gray-900">
        我的计划
      </h1>

      <button
        class="w-10 h-10 bg-gray-50 rounded-full flex items-center justify-center text-gray-600 hover:bg-gray-100 transition"
        @click="planStore.openFilter"
      >
        <Icon icon="lucide:list-filter" width="20" />
      </button>
    </div>

    <!-- 内容 -->
    <div class="h-[644px] overflow-y-auto pb-24 scrollbar-hide">
      <!-- 统计卡片 -->
      <div class="px-6 py-4">
        <div
          class="bg-blue-600 rounded-3xl p-5 text-white flex justify-between items-center"
        >
          <div>
            <p class="text-xs opacity-70">
              进行中的计划
            </p>

            <p class="text-2xl font-bold mt-1">
              {{ activeCount }} 个计划
            </p>
          </div>

          <div class="text-right">
            <p class="text-xs opacity-70">
              平均进度
            </p>

            <p class="text-2xl font-bold mt-1">
              {{ averageProgress }}%
            </p>
          </div>
        </div>
      </div>

      <!-- loading -->
      <div
        v-if="loading"
        class="flex flex-col items-center justify-center py-20 text-gray-400"
      >
        <Icon
          icon="lucide:loader-circle"
          width="32"
          class="animate-spin"
        />

        <p class="text-sm mt-3">
          正在加载计划...
        </p>
      </div>

      <!-- error -->
      <div
        v-else-if="error"
        class="px-6 py-10"
      >
        <div
          class="bg-red-50 border border-red-100 rounded-2xl p-5 text-center"
        >
          <Icon
            icon="lucide:triangle-alert"
            width="28"
            class="mx-auto text-red-400"
          />

          <p class="text-sm text-red-500 mt-3">
            {{ error }}
          </p>

          <button
            class="mt-4 px-4 py-2 bg-red-500 text-white text-xs rounded-xl"
            @click="planStore.fetchPlans"
          >
            重新加载
          </button>
        </div>
      </div>

      <!-- 空状态 -->
      <div
        v-else-if="plans.length === 0"
        class="flex flex-col items-center justify-center py-20 text-gray-400"
      >
        <Icon
          icon="lucide:notebook-pen"
          width="40"
        />

        <p class="text-sm mt-4">
          还没有学习计划
        </p>

        <button
          class="mt-4 px-4 py-2 bg-blue-500 text-white text-xs rounded-xl"
          @click="planStore.createPlan"
        >
          创建第一个计划
        </button>
      </div>

      <!-- 列表 -->
      <div
        v-else
        class="px-6 space-y-4"
      >
        <PlanCard
          v-for="plan in plans"
          :key="plan.id"
          :plan="plan"
        />

        <!-- 创建计划 -->
        <div class="py-6 flex flex-col items-center">
          <button
            class="bg-gray-50 border-2 border-dashed border-gray-200 rounded-2xl p-6 w-full flex flex-col items-center gap-2 group hover:border-blue-200 hover:bg-blue-50/30 transition"
            @click="planStore.createPlan"
          >
            <Icon
              class="text-gray-300 group-hover:text-blue-500 transition-colors"
              icon="lucide:plus"
              width="32"
            />

            <span
              class="text-xs text-gray-400 group-hover:text-blue-500 font-medium transition"
            >
              创建新的长期学习计划
            </span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.scrollbar-hide::-webkit-scrollbar {
  display: none;
}

.scrollbar-hide {
  scrollbar-width: none;
}
</style>