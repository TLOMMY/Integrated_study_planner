<script setup>
import { Icon } from '@iconify/vue'

defineProps({
  task: {
    type: Object,
    required: true,
  },
})
</script>

<template>
  <div
    class="flex items-start gap-3 p-3 rounded-2xl bg-slate-50 border border-slate-100"
  >
    <!-- icon -->
    <div
      class="w-9 h-9 rounded-xl bg-blue-100 text-blue-600 flex items-center justify-center shrink-0"
    >
      <Icon
        :icon="task.icon || 'lucide:book-open'"
        width="18"
      />
    </div>

    <!-- content -->
    <div class="flex-1">
      <div class="text-sm font-semibold text-gray-800">
        {{ task.title }}
      </div>

      <div class="text-xs text-gray-500 mt-1">
        {{ task.time }}
      </div>
    </div>

    <!-- status -->
    <div
      v-if="task.completed"
      class="text-green-500"
    >
      <Icon icon="lucide:check-circle-2" width="18" />
    </div>
  </div>
</template>