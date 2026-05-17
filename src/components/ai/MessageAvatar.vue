<script setup>
import { Icon } from '@iconify/vue'

defineProps({
  role: {
    type: String,
    default: 'ai',
  },
})
</script>

<template>
  <!-- AI -->
  <div
    v-if="role === 'ai'"
    class="w-8 h-8 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center shrink-0"
  >
    <Icon icon="lucide:bot" width="18" />
  </div>

  <!-- User -->
  <div
    v-else
    class="w-8 h-8 rounded-full bg-blue-500 text-white flex items-center justify-center text-sm font-semibold shrink-0"
  >
    U
  </div>
</template>