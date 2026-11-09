<script setup>
/**
 * 任务完成圈：未完成时是空心圈（边框颜色表示优先级）；完成时圈填满、勾描出来。
 * 只在"刚刚完成"时播放（done 从 false 变 true），列表初次加载的已完成任务直接显示最后一帧。
 */
import { ref, watch } from 'vue'

const props = defineProps({
  done: { type: Boolean, default: false },
  // 未完成时的边框颜色类（来自 priorityMeta().ring）
  ringClass: { type: [String, Array], default: 'border-ink-line' },
})
const playing = ref(false)
let timer = null
watch(() => props.done, (now, before) => {
  if (!now || before) return
  playing.value = true
  clearTimeout(timer)
  timer = setTimeout(() => (playing.value = false), 700)
})
</script>

<template>
  <span class="task-check" :class="[done ? 'is-done' : ringClass, playing && 'is-playing']" aria-hidden="true">
    <svg v-if="done" viewBox="0 0 22 22">
      <circle class="fill" cx="11" cy="11" r="11" />
      <path class="tick" d="M6.5 11.4l3 3 6-6.4" />
    </svg>
  </span>
</template>

<style scoped>
.task-check { display: flex; width: 22px; height: 22px; border-radius: 9999px; border-width: 2px; }
.task-check.is-done { border-color: transparent; }
.task-check svg { width: 22px; height: 22px; margin: -2px; overflow: visible; }
.fill { fill: rgb(var(--c-success)); transform-box: fill-box; transform-origin: center; }
.tick { fill: none; stroke: rgb(var(--c-on-success)); stroke-width: 2.2; stroke-linecap: round; stroke-linejoin: round; stroke-dasharray: 16; stroke-dashoffset: 0; }
.is-playing .fill { animation: tc-fill .32s cubic-bezier(.3, 1.5, .5, 1) both; }
.is-playing .tick { animation: tc-draw .26s .2s ease-out both; }
@keyframes tc-fill { from { transform: scale(0); } }
@keyframes tc-draw { from { stroke-dashoffset: 16; } }
@media (prefers-reduced-motion: reduce) {
  .is-playing .fill, .is-playing .tick { animation: none; }
}
</style>
