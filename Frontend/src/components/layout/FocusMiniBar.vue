<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import { useFocusStore } from '@/stores/focus'

const focus = useFocusStore()
const route = useRoute()
const router = useRouter()
const visible = computed(() => focus.active && route.name !== 'focus')
</script>

<template>
  <Transition enter-active-class="transition duration-200" enter-from-class="translate-y-4 opacity-0" leave-active-class="transition duration-150" leave-to-class="translate-y-4 opacity-0">
    <button
      v-if="visible"
      class="absolute bottom-3 left-1/2 z-30 flex -translate-x-1/2 items-center gap-2.5 glass glass-ink rounded-full bg-inverse py-2 pl-2 pr-4 text-inverse-ink shadow-xl active:scale-95"
      type="button"
      @click="router.push({ name: 'focus' })"
    >
      <span class="flex h-8 w-8 items-center justify-center rounded-full" :class="focus.status === 'running' ? 'bg-primary text-on-primary' : 'bg-inverse-ink/20'">
        <Icon :icon="focus.status === 'running' ? 'lucide:timer' : 'lucide:pause'" width="16" />
      </span>
      <span class="num text-base font-black">{{ focus.clock }}</span>
      <span class="max-w-[120px] truncate text-xs opacity-70">{{ focus.task?.title || '自由专注' }}</span>
    </button>
  </Transition>
</template>
