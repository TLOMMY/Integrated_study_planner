<script setup>
import { computed } from 'vue'
import { Icon } from '@iconify/vue'

const props = defineProps({
  item: {
    type: Object,
    required: true,
  },
})

/**
 * 时间显示
 * 例如：
 * 08:00 - 09:30
 */
const duration = computed(() => {
  if (!props.item.startTime || !props.item.endTime) {
    return ''
  }

  return `${props.item.startTime} - ${props.item.endTime}`
})

/**
 * 默认图标
 */
const defaultIcon = 'mdi:book-open-page-variant'
</script>

<template>
  <!-- 课程 -->
  <div
    v-if="item.type === 'course'"
    class="flex min-h-[100px] relative"
  >
    <div class="w-16 text-right pr-4 pt-1 text-xs text-gray-400 font-medium">
      {{ item.startTime }}
    </div>

    <div class="flex-1 pl-4 pr-4">
      <div class="bg-blue-50 border border-blue-100 rounded-2xl p-3 relative">
        <div class="flex items-center justify-between">
          <span class="font-bold text-blue-800 text-sm">
            {{ item.title }}
          </span>

          <Icon
            icon="mdi:checkbox-marked-circle"
            class="text-blue-500"
          />
        </div>

        <div class="text-[11px] text-blue-600 mt-1 flex items-center gap-2">
          <Icon icon="mdi:map-marker" />

          <span>
            {{ item.location }}
          </span>
        </div>

        <div
          class="mt-2 text-[10px] text-blue-400 border-t border-blue-100 pt-2 flex justify-between items-center"
        >
          <span>
            {{ duration }}
          </span>

          <span
            class="flex items-center gap-1"
            :class="
              item.reviewDone
                ? 'text-blue-500'
                : 'text-gray-300'
            "
          >
            <Icon
              :icon="
                item.reviewDone
                  ? 'mdi:check-circle'
                  : 'mdi:checkbox-blank-circle-outline'
              "
            />

            复习
          </span>
        </div>
      </div>
    </div>
  </div>

  <!-- 普通任务 -->
  <div
    v-else-if="item.type === 'task'"
    class="flex min-h-[80px] relative"
  >
    <div class="w-16 text-right pr-4 pt-1 text-xs text-gray-400">
      {{ item.startTime }}
    </div>

    <div class="flex-1 pl-4 pr-4">
      <div
        class="bg-white border border-gray-100 rounded-full py-2 px-4 shadow-sm flex items-center justify-between"
      >
        <div class="flex items-center gap-3">
          <div
            class="w-8 h-8 bg-purple-100 rounded-full flex items-center justify-center text-purple-600"
          >
            <Icon :icon="item.icon || defaultIcon" />
          </div>

          <span class="text-xs font-semibold">
            {{ item.title }}
          </span>
        </div>

        <div class="flex items-center gap-3">
          <span class="text-[10px] text-gray-400">
            {{ duration }}
          </span>

          <RouterLink
            v-if="item.link"
            :to="item.link"
            class="text-blue-500 flex items-center"
          >
            <Icon
              icon="mdi:play-circle"
              class="text-2xl"
            />
          </RouterLink>
        </div>
      </div>
    </div>
  </div>

  <!-- 已完成课程 -->
  <div
    v-else-if="item.type === 'finished-course'"
    class="flex min-h-[100px] relative"
  >
    <div class="w-16 text-right pr-4 pt-1 text-xs text-gray-400 font-medium">
      {{ item.startTime }}
    </div>

    <div class="flex-1 pl-4 pr-4">
      <div
        class="bg-gray-50 border border-gray-100 rounded-2xl p-3 opacity-60"
      >
        <div class="flex items-center justify-between">
          <span class="font-bold text-gray-600 text-sm">
            {{ item.title }}
          </span>

          <span class="text-[10px] text-green-500 font-bold">
            已完成 √
          </span>
        </div>

        <div class="text-[11px] text-gray-400 mt-1">
          {{ duration }}
        </div>
      </div>
    </div>
  </div>

  <!-- 进行中任务 -->
  <div
    v-else-if="item.type === 'active-task'"
    class="flex min-h-[80px] relative"
  >
    <div class="w-16 text-right pr-4 pt-1 text-xs text-gray-400 font-medium">
      {{ item.startTime }}
    </div>

    <div class="flex-1 pl-4 pr-4">
      <div
        class="bg-white border border-blue-400 rounded-full py-2 px-4 shadow-md flex items-center justify-between ring-2 ring-blue-50 ring-offset-1"
      >
        <div class="flex items-center gap-3">
          <div
            class="w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center text-blue-600"
          >
            <Icon :icon="item.icon || defaultIcon" />
          </div>

          <span class="text-xs font-semibold">
            {{ item.title }}
          </span>
        </div>

        <span class="text-[10px] text-blue-500 font-bold">
          进行中
        </span>
      </div>
    </div>
  </div>
</template>