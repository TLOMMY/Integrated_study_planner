<script setup>
import BottomSheet from '@/components/common/BottomSheet.vue'
import { SHORTCUTS, shortcutsHelpOpen } from '@/composables/useShortcuts'
</script>

<template>
  <BottomSheet :open="shortcutsHelpOpen" title="键盘快捷键" subtitle="电脑端可用，在输入框里不会触发" @close="shortcutsHelpOpen = false">
    <ul class="divide-y divide-ink-line/70">
      <li v-for="item in SHORTCUTS" :key="item.label" class="flex items-center justify-between gap-3 py-2.5">
        <span class="text-sm font-semibold text-ink-soft">{{ item.label }}</span>
        <span class="flex shrink-0 items-center gap-1 text-xs text-ink-mute">
          <template v-for="(k, i) in item.keys" :key="k">
            <span v-if="i" class="px-0.5">然后</span>
            <kbd class="num min-w-[26px] rounded-lg border border-ink-line bg-background px-1.5 py-0.5 text-center font-bold text-ink">{{ k }}</kbd>
          </template>
          <template v-if="item.alt">
            <span class="px-0.5">或</span>
            <template v-for="(k, i) in item.alt" :key="`alt-${k}`">
              <span v-if="i">+</span>
              <kbd class="num min-w-[26px] rounded-lg border border-ink-line bg-background px-1.5 py-0.5 text-center font-bold text-ink">{{ k }}</kbd>
            </template>
          </template>
        </span>
      </li>
    </ul>
  </BottomSheet>
</template>
