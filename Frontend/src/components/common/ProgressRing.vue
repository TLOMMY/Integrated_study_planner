<script setup>
import { computed } from 'vue'

const props = defineProps({
  value: { type: Number, default: 0 },
  size: { type: Number, default: 64 },
  stroke: { type: Number, default: 7 },
  // 颜色可传任意 CSS 颜色，包括主题变量 rgb(var(--c-success))；默认跟随文字颜色
  color: { type: String, default: 'currentColor' },
  // 不传时轨道为当前文字颜色的 25% 透明度（放在白字渐变卡片上与原来的 rgba(255,255,255,.25) 一致）
  track: { type: String, default: '' },
})

const radius = computed(() => (props.size - props.stroke) / 2)
const circumference = computed(() => 2 * Math.PI * radius.value)
const offset = computed(() => circumference.value * (1 - Math.min(100, Math.max(0, props.value)) / 100))
</script>

<template>
  <div class="relative inline-flex items-center justify-center" :style="{ width: `${size}px`, height: `${size}px` }">
    <svg :width="size" :height="size" class="-rotate-90">
      <circle :cx="size / 2" :cy="size / 2" :r="radius" fill="none" :style="track ? { stroke: track } : { stroke: 'currentColor', strokeOpacity: 0.25 }" :stroke-width="stroke" />
      <circle
        :cx="size / 2"
        :cy="size / 2"
        :r="radius"
        fill="none"
        :style="{ stroke: color, transition: 'stroke-dashoffset 0.6s ease' }"
        :stroke-width="stroke"
        stroke-linecap="round"
        :stroke-dasharray="circumference"
        :stroke-dashoffset="offset"
      />
    </svg>
    <div class="absolute inset-0 flex items-center justify-center"><slot /></div>
  </div>
</template>
