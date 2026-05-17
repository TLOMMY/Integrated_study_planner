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
 * 时间范围
 * 例如：
 * 10:00 - 12:00
 */
const duration = computed(() => {
  if (!props.item.startTime || !props.item.endTime) {
    return ''
  }

  return `${props.item.startTime} - ${props.item.endTime}`
})

/**
 * 是否长时间空闲
 * 超过 90 分钟视为长空闲
 */
const isLongFree = computed(() => {
  return props.item.duration >= 90
})

/**
 * 空闲提示文案
 */
const freeText = computed(() => {
  if (props.item.text) {
    return props.item.text
  }

  return isLongFree.value
    ? '长时间空闲，可安排学习计划'
    : '短暂休息时间'
})
</script>

<template>
  <!-- 短空闲 -->
  <div
    v-if="!isLongFree"
    class="flex min-h-[40px] items-center"
  >
    <div class="w-16 text-right pr-4 text-xs text-gray-400">
      {{ item.startTime }}
    </div>

    <div
      class="flex-1 pl-8 flex items-center gap-2 text-[11px] text-gray-400 italic"
    >
      <Icon icon="mdi:arrow-down" />

      <span>
        {{ freeText }}
      </span>
    </div>
  </div>

  <!-- 长空闲 -->
  <div
    v-else
    class="flex min-h-[120px] items-center"
  >
    <div class="w-16 text-right pr-4 text-xs text-gray-400">
      {{ item.startTime }}
    </div>

    <div
      class="flex-1 pl-8 flex flex-col items-start gap-1 text-[11px] text-gray-400 italic"
    >
      <Icon
        icon="mdi:arrow-down"
        class="ml-2"
      />

      <span class="bg-gray-50 px-3 py-1 rounded-full">
        {{ freeText }}
      </span>

      <span class="text-[10px] text-gray-300 ml-2">
        {{ duration }}
      </span>

      <Icon
        icon="mdi:arrow-down"
        class="ml-2"
      />
    </div>
  </div>
</template>