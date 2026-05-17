<script setup>
import { computed } from 'vue'
import { Icon } from '@iconify/vue'

const props = defineProps({
  plan: {
    type: Object,
    required: true
  }
})

/**
 * 状态样式
 */
const statusClass = computed(() => {
  switch (props.plan.status) {
    case '已结束':
      return 'bg-gray-200 text-gray-500'

    case '加急':
      return 'bg-orange-100 text-orange-600'

    default:
      return 'bg-green-100 text-green-600'
  }
})

/**
 * 进度条颜色
 */
const progressColor = computed(() => {
  const progress = Number(props.plan.progress || 0)

  if (progress >= 80) {
    return 'bg-green-500'
  }

  if (progress >= 50) {
    return 'bg-blue-500'
  }

  return 'bg-orange-500'
})

/**
 * 进度文字颜色
 */
const progressTextColor = computed(() => {
  const progress = Number(props.plan.progress || 0)

  if (progress >= 80) {
    return 'text-green-600'
  }

  if (progress >= 50) {
    return 'text-blue-600'
  }

  return 'text-orange-600'
})

/**
 * 图标背景颜色
 */
const iconBg = computed(() => {
  switch (props.plan.type) {
    case 'urgent':
      return 'bg-orange-100'

    case 'finished':
      return 'bg-gray-200'

    default:
      return 'bg-blue-100'
  }
})

/**
 * 图标颜色
 */
const iconColor = computed(() => {
  switch (props.plan.type) {
    case 'urgent':
      return 'text-orange-600'

    case 'finished':
      return 'text-gray-500'

    default:
      return 'text-blue-600'
  }
})
</script>

<template>
  <!-- 进行中 -->
  <div
    v-if="plan.type === 'running'"
    class="bg-white border border-gray-100 rounded-2xl p-5 shadow-sm"
  >
    <div class="flex justify-between items-start mb-4">
      <div class="flex gap-3">
        <div
          class="w-12 h-12 rounded-2xl flex items-center justify-center"
          :class="[iconBg, iconColor]"
        >
          <Icon :icon="plan.icon" width="24" />
        </div>

        <div>
          <h4 class="font-bold text-gray-800">
            {{ plan.title }}
          </h4>

          <p class="text-[10px] text-gray-400 mt-0.5">
            {{ plan.remainText }}
          </p>
        </div>
      </div>

      <span
        class="text-[10px] px-2 py-1 rounded-full font-bold"
        :class="statusClass"
      >
        {{ plan.status }}
      </span>
    </div>

    <div class="space-y-3">
      <div class="flex justify-between items-end text-[10px] font-bold">
        <span class="text-gray-400">总体进度</span>

        <span :class="progressTextColor">
          {{ plan.progress }}%
        </span>
      </div>

      <div class="h-2 bg-gray-100 rounded-full overflow-hidden">
        <div
          class="h-full rounded-full transition-all duration-300"
          :class="progressColor"
          :style="{ width: `${plan.progress}%` }"
        ></div>
      </div>
    </div>

    <div
      class="mt-4 pt-4 border-t border-gray-50 flex justify-between items-center"
    >
      <div class="flex -space-x-2">
        <div
          v-for="tag in plan.tags"
          :key="tag.text"
          class="w-6 h-6 rounded-full border-2 border-white flex items-center justify-center text-[8px] font-bold"
          :class="[tag.bg, tag.color]"
        >
          {{ tag.text }}
        </div>
      </div>

      <button
        class="text-xs font-bold text-gray-400 flex items-center gap-1 hover:text-gray-600 transition"
      >
        查看详情

        <Icon icon="lucide:chevron-right" width="14" />
      </button>
    </div>
  </div>

  <!-- 加急 -->
  <div
    v-else-if="plan.type === 'urgent'"
    class="bg-white border border-gray-100 rounded-2xl p-5 shadow-sm"
  >
    <div class="flex justify-between items-start mb-4">
      <div class="flex gap-3">
        <div
          class="w-12 h-12 rounded-2xl flex items-center justify-center"
          :class="[iconBg, iconColor]"
        >
          <Icon :icon="plan.icon" width="24" />
        </div>

        <div>
          <h4 class="font-bold text-gray-800">
            {{ plan.title }}
          </h4>

          <p class="text-[10px] text-gray-400 mt-0.5">
            {{ plan.remainText }}
          </p>
        </div>
      </div>

      <span
        class="text-[10px] px-2 py-1 rounded-full font-bold"
        :class="statusClass"
      >
        {{ plan.status }}
      </span>
    </div>

    <div class="space-y-3">
      <div class="flex justify-between items-end text-[10px] font-bold">
        <span class="text-gray-400">总体进度</span>

        <span :class="progressTextColor">
          {{ plan.progress }}%
        </span>
      </div>

      <div class="h-2 bg-gray-100 rounded-full overflow-hidden">
        <div
          class="h-full rounded-full transition-all duration-300"
          :class="progressColor"
          :style="{ width: `${plan.progress}%` }"
        ></div>
      </div>
    </div>

    <div
      class="mt-4 pt-4 border-t border-gray-50 flex justify-between items-center text-xs font-bold text-gray-400"
    >
      <span>今日待办: {{ plan.todo }}</span>

      <Icon icon="lucide:chevron-right" width="14" />
    </div>
  </div>

  <!-- 已结束 -->
  <div
    v-else
    class="bg-gray-50/50 border border-gray-100 rounded-2xl p-5 opacity-60"
  >
    <div class="flex justify-between items-start mb-4">
      <div class="flex gap-3">
        <div
          class="w-12 h-12 rounded-2xl flex items-center justify-center"
          :class="[iconBg, iconColor]"
        >
          <Icon :icon="plan.icon" width="24" />
        </div>

        <div>
          <h4 class="font-bold text-gray-400">
            {{ plan.title }}
          </h4>

          <p class="text-[10px] text-gray-400 mt-0.5">
            {{ plan.remainText }}
          </p>
        </div>
      </div>

      <span
        class="text-[10px] px-2 py-1 rounded-full font-bold"
        :class="statusClass"
      >
        {{ plan.status }}
      </span>
    </div>

    <div
      class="text-[10px] font-bold text-green-600 flex items-center gap-1"
    >
      <Icon icon="lucide:award" width="14" />

      {{ plan.finalResult }}
    </div>
  </div>
</template>