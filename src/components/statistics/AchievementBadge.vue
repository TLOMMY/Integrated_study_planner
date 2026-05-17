<template>
  <div
    :class="[
      locked ? 'grayscale opacity-30' : 'grayscale-0',
      'flex flex-col items-center gap-1.5',
    ]"
  >
    <div
      :class="[
        bg,
        text,
        border,
        'w-12 h-12 rounded-full flex items-center justify-center shadow-sm border',
      ]"
    >
      <Icon :icon="icon" width="24" />
    </div>

    <span class="text-[8px] font-bold text-gray-600">
      {{ name }}
    </span>
  </div>
</template>

<script setup>
import { Icon } from '@iconify/vue'

defineProps({
  name: String,
  icon: String,
  bg: String,
  text: String,
  border: String,
  locked: Boolean,
})
</script>