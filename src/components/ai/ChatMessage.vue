<script setup>
import { computed } from 'vue'
import { Icon } from '@iconify/vue'

const props = defineProps({
  message: {
    type: Object,
    required: true,
  },
})

const isUser = computed(() => {
  return props.message.role === 'user'
})

const iconName = computed(() => {
  return isUser.value
    ? 'lucide:user'
    : 'lucide:bot'
})
</script>

<template>
  <!-- assistant -->
  <div
    v-if="!isUser"
    class="flex gap-3 mb-6 animate-fade-in"
  >
    <!-- avatar -->
    <div
      class="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center text-blue-600 shrink-0"
    >
      <Icon :icon="iconName" width="18" />
    </div>

    <!-- bubble -->
    <div
      class="bubble-ai p-4 text-sm text-gray-700 leading-relaxed max-w-[85%]"
    >
      {{ message.content }}
    </div>
  </div>

  <!-- user -->
  <div
    v-else
    class="flex justify-end mb-6 animate-fade-in"
  >
    <div
      class="bubble-user p-4 text-sm leading-relaxed max-w-[85%] shadow-md shadow-blue-100"
    >
      {{ message.content }}
    </div>
  </div>
</template>