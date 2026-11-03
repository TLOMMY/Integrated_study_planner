<script setup>
/** "AI 生成"小标签：AI 回复、提案卡片、复盘、讲义大纲、识别结果等处统一使用。 */
import { Icon } from '@iconify/vue'

defineProps({
  // 鼠标悬停 / 读屏时的补充说明，如模型名
  title: { type: String, default: '' },
  label: { type: String, default: 'AI 生成' },
  // 放在深色 / 渐变背景上时用半透明白底
  inverse: { type: Boolean, default: false },
})
</script>

<template>
  <span
    class="inline-flex shrink-0 items-center gap-0.5 rounded-full px-1.5 py-px align-middle text-[10px] font-bold leading-4"
    :class="inverse ? 'bg-surface/20 text-on-primary' : 'bg-xp-light text-xp'"
    :title="title ? `${label} · ${title}` : `${label}，内容可能有误，请核对`"
  >
    <Icon icon="lucide:sparkles" width="10" aria-hidden="true" />{{ label }}
  </span>
</template>
