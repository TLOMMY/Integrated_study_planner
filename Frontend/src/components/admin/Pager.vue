<script setup>
import { computed } from 'vue'
import { Icon } from '@iconify/vue'

const props = defineProps({ total: { type: Number, default: 0 }, size: { type: Number, default: 20 } })
const page = defineModel({ type: Number, default: 1 })
const pages = computed(() => Math.max(1, Math.ceil(props.total / props.size)))
const go = (p) => (page.value = Math.min(pages.value, Math.max(1, p)))
</script>

<template>
  <div v-if="total > size" class="flex items-center justify-center gap-3 py-1 text-xs text-ink-soft">
    <button class="icon-btn h-8 w-8" type="button" aria-label="上一页" :disabled="page <= 1" :class="page <= 1 && 'opacity-40'" @click="go(page - 1)"><Icon icon="lucide:chevron-left" width="16" /></button>
    <span class="num">{{ page }} / {{ pages }} · 共 {{ total }} 条</span>
    <button class="icon-btn h-8 w-8" type="button" aria-label="下一页" :disabled="page >= pages" :class="page >= pages && 'opacity-40'" @click="go(page + 1)"><Icon icon="lucide:chevron-right" width="16" /></button>
  </div>
  <p v-else-if="total" class="text-center text-[11px] text-ink-mute">共 {{ total }} 条</p>
</template>
