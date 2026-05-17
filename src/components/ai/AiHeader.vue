<script setup>
import { computed } from 'vue'
import { Icon } from '@iconify/vue'

const props = defineProps({
  title: {
    type: String,
    default: 'AI 学习助手',
  },

  status: {
    type: String,
    default: '在线',
  },

  subtitle: {
    type: String,
    default: '随时为你规划',
  },
})

const statusColor = computed(() => {
  switch (props.status) {
    case '在线':
      return 'bg-green-500'

    case '思考中':
      return 'bg-yellow-500'

    case '错误':
      return 'bg-red-500'

    default:
      return 'bg-gray-400'
  }
})
</script>

<template>
  <div
    class="px-6 pt-10 pb-4 flex items-center justify-between bg-white border-b border-gray-100 sticky top-0 z-20 backdrop-blur-md"
  >
    <div class="flex items-center gap-3">
      
      <!-- avatar -->
      <div
        class="w-10 h-10 bg-blue-600 rounded-2xl flex items-center justify-center text-white shadow-lg shadow-blue-100"
      >
        <Icon icon="lucide:bot" width="22" />
      </div>

      <!-- info -->
      <div>
        <h1 class="text-sm font-bold text-gray-900">
          {{ title }}
        </h1>

        <div class="flex items-center gap-1.5 mt-0.5">
          <span
            class="w-2 h-2 rounded-full"
            :class="statusColor"
          />

          <span class="text-[11px] text-gray-400 font-medium">
            {{ status }} · {{ subtitle }}
          </span>
        </div>
      </div>
    </div>

    <!-- action -->
    <button
      class="w-9 h-9 rounded-xl flex items-center justify-center text-gray-400 hover:bg-gray-100 transition"
    >
      <Icon icon="lucide:more-horizontal" width="20" />
    </button>
  </div>
</template>