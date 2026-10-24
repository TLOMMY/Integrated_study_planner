<script setup>
import { Icon } from '@iconify/vue'

defineProps({
  icon: { type: String, default: 'lucide:inbox' },
  title: { type: String, required: true },
  text: { type: String, default: '' },
  compact: { type: Boolean, default: false },
})
</script>

<template>
  <div class="flex flex-col items-center text-center" :class="compact ? 'py-6' : 'py-12'">
    <div class="mb-3 flex h-14 w-14 items-center justify-center rounded-3xl bg-primary-light text-primary">
      <Icon :icon="icon" width="26" />
    </div>
    <p class="text-sm font-bold text-ink">{{ title }}</p>
    <p v-if="text" class="mt-1 max-w-[260px] text-xs leading-5 text-ink-mute">{{ text }}</p>
    <div v-if="$slots.default" class="mt-4 flex flex-wrap justify-center gap-2"><slot /></div>
  </div>
</template>
