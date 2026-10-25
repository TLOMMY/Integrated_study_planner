<script setup>
import { watch } from 'vue'
import { Icon } from '@iconify/vue'

const props = defineProps({
  open: { type: Boolean, default: false },
  title: { type: String, default: '' },
  subtitle: { type: String, default: '' },
})
const emit = defineEmits(['close'])

const onKey = (event) => {
  if (event.key === 'Escape') emit('close')
}
watch(
  () => props.open,
  (open) => (open ? window.addEventListener('keydown', onKey) : window.removeEventListener('keydown', onKey)),
)
</script>

<template>
  <Teleport to="#overlay-root" defer>
    <Transition name="sheet" :duration="260">
      <!-- 手机：底部抽屉；桌面（lg）：居中对话框 -->
      <div v-if="open" class="sheet absolute inset-0 z-[70] flex flex-col justify-end lg:items-center lg:justify-center lg:p-8" role="dialog" aria-modal="true" :aria-label="title">
        <div class="sheet-mask absolute inset-0 bg-scrim/45" @click="emit('close')" />
        <section class="sheet-panel material relative flex max-h-[88%] flex-col rounded-t-[28px] bg-surface pb-[calc(var(--safe-bottom)+12px)] shadow-2xl lg:max-h-[min(86vh,820px)] lg:w-full lg:max-w-[560px] lg:rounded-[28px] lg:pb-4">
          <div class="mx-auto mt-2.5 h-1.5 w-10 rounded-full bg-ink-line lg:hidden" />
          <header v-if="title" class="flex items-start justify-between gap-3 px-5 pb-2 pt-3">
            <div class="min-w-0">
              <h2 class="text-lg font-black text-ink">{{ title }}</h2>
              <p v-if="subtitle" class="mt-0.5 text-xs text-ink-mute">{{ subtitle }}</p>
            </div>
            <button class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-background text-ink-soft" type="button" aria-label="关闭" @click="emit('close')">
              <Icon icon="lucide:x" width="16" />
            </button>
          </header>
          <div class="scrollbar-hide flex-1 overflow-y-auto px-5 pb-2 pt-1"><slot /></div>
          <footer v-if="$slots.footer" class="px-5 pt-3"><slot name="footer" /></footer>
        </section>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.sheet-enter-active .sheet-mask,
.sheet-leave-active .sheet-mask {
  transition: opacity 0.26s ease;
}
.sheet-enter-active .sheet-panel,
.sheet-leave-active .sheet-panel {
  transition: transform 0.26s cubic-bezier(0.2, 0.9, 0.3, 1);
}
.sheet-enter-from .sheet-mask,
.sheet-leave-to .sheet-mask {
  opacity: 0;
}
.sheet-enter-from .sheet-panel,
.sheet-leave-to .sheet-panel {
  transform: translateY(100%);
}
@media (min-width: 1024px) {
  .sheet-enter-active .sheet-panel,
  .sheet-leave-active .sheet-panel {
    transition: transform 0.2s ease, opacity 0.2s ease;
  }
  .sheet-enter-from .sheet-panel,
  .sheet-leave-to .sheet-panel {
    transform: translateY(12px) scale(0.97);
    opacity: 0;
  }
}
</style>
