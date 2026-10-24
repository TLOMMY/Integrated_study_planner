<script setup>
import { Icon } from '@iconify/vue'
import { useUiStore } from '@/stores/ui'

const ui = useUiStore()

const STYLE = {
  success: { icon: 'lucide:circle-check', cls: 'bg-ink text-white', iconCls: 'text-success' },
  error: { icon: 'lucide:circle-x', cls: 'bg-danger text-white', iconCls: 'text-white' },
  warning: { icon: 'lucide:triangle-alert', cls: 'bg-ink text-white', iconCls: 'text-flame' },
  info: { icon: 'lucide:info', cls: 'bg-ink text-white', iconCls: 'text-primary-soft' },
  xp: { icon: 'lucide:sparkles', cls: 'bg-xp text-white', iconCls: 'text-white' },
}
</script>

<template>
  <div class="pointer-events-none absolute inset-x-0 top-0 z-[100] flex flex-col items-center gap-2 px-6 pt-[calc(var(--safe-top)+14px)]" aria-live="polite">
    <TransitionGroup enter-active-class="transition duration-200" enter-from-class="-translate-y-3 opacity-0" leave-active-class="transition duration-150" leave-to-class="opacity-0">
      <div
        v-for="toast in ui.toasts"
        :key="toast.id"
        class="pointer-events-auto flex max-w-full items-center gap-2 rounded-2xl px-4 py-2.5 text-sm font-semibold shadow-xl"
        :class="STYLE[toast.type]?.cls"
        @click="ui.dismiss(toast.id)"
      >
        <Icon :icon="STYLE[toast.type]?.icon" width="18" :class="STYLE[toast.type]?.iconCls" class="shrink-0" />
        <span class="truncate">{{ toast.message }}</span>
      </div>
    </TransitionGroup>
  </div>
</template>
