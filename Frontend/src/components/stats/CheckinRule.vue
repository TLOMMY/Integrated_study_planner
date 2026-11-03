<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'

/**
 * 打卡规则 ⓘ：点一下展开说明（专注满 5 分钟或完成 1 个任务即算打卡）与今天的打卡进度。
 * streak 为后端 streak_info：{ active_today, rule: {text, min_focus_minutes, min_tasks}, today: {...} }
 */
const props = defineProps({
  streak: { type: Object, default: null },
  // 是否在按钮旁直接显示"今天已打卡 / 未打卡"
  showStatus: { type: Boolean, default: false },
  align: { type: String, default: 'right' }, // 弹层对齐：left / right
})

const FALLBACK = { text: '当天专注满 5 分钟或完成 1 个任务即算打卡', min_focus_minutes: 5, min_tasks: 1 }
const rule = computed(() => props.streak?.rule || FALLBACK)
const today = computed(() => props.streak?.today || null)
const done = computed(() => Boolean(props.streak?.active_today))
const progress = computed(() => {
  const t = today.value
  if (!t) return ''
  if (done.value) return `今天已打卡：专注 ${t.focus_minutes} 分钟 · 完成 ${t.tasks_done} 个任务`
  return `今天还没打卡：再专注 ${t.focus_needed} 分钟，或完成 1 个任务`
})

const open = ref(false)
const root = ref(null)
const onDoc = (event) => {
  if (root.value && !root.value.contains(event.target)) open.value = false
}
watch(open, (value) => (value ? document.addEventListener('click', onDoc, true) : document.removeEventListener('click', onDoc, true)))
onBeforeUnmount(() => document.removeEventListener('click', onDoc, true))
</script>

<template>
  <span ref="root" class="relative inline-flex items-center gap-1">
    <span v-if="showStatus && streak" class="rounded-full px-1.5 py-0.5 text-[10px] font-bold" :class="done ? 'bg-flame-light text-flame' : 'bg-background text-ink-mute'">
      {{ done ? '今日已打卡' : '今日未打卡' }}
    </span>
    <button
      class="inline-flex h-5 w-5 items-center justify-center rounded-full text-ink-mute hover:bg-background hover:text-primary"
      type="button"
      :aria-expanded="open"
      aria-label="打卡规则"
      title="打卡规则"
      @click.stop.prevent="open = !open"
    >
      <Icon icon="lucide:info" width="14" />
    </button>
    <span
      v-if="open"
      role="tooltip"
      class="absolute top-6 z-30 w-60 rounded-2xl border border-ink-line/70 bg-surface p-3 text-left text-xs font-normal leading-5 text-ink-soft shadow-lift"
      :class="align === 'left' ? 'left-0' : 'right-0'"
      @click.stop.prevent
    >
      <span class="flex items-center gap-1.5 font-black text-ink"><Icon icon="lucide:flame" width="14" class="text-flame" />打卡规则</span>
      <span class="mt-1 block">{{ rule.text }}，连续打卡的天数就是火苗数字。</span>
      <span class="mt-1 block text-ink-mute">连续天数、断签保护卡、成就、学习足迹和周报都按这个标准统计。</span>
      <span v-if="progress" class="mt-2 block rounded-xl px-2 py-1.5 font-semibold" :class="done ? 'bg-flame-light text-flame' : 'bg-background text-ink-soft'">{{ progress }}</span>
    </span>
  </span>
</template>
