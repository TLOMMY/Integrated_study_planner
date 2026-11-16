<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'

/**
 * 打卡规则 ⓘ：点一下展开说明（专注满 5 分钟或完成 1 个任务即算打卡）与今天的打卡进度。
 * 说明气泡挂到 #overlay-root（最上层），按按钮位置定位，不会被后面的卡片盖住；底色不透明。
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
const bubble = ref(null)
const pos = ref({ top: 0, left: 0 })
const WIDTH = 240
const MARGIN = 12

/** 相对 .phone（手机框演示时它不贴着窗口）计算位置：默认在按钮下方，放不下翻到上方，左右夹在屏幕内。 */
const place = () => {
  const button = root.value?.querySelector('button')
  const frame = document.querySelector('.phone')
  if (!button || !frame) return
  const b = button.getBoundingClientRect()
  const f = frame.getBoundingClientRect()
  const height = bubble.value?.offsetHeight || 160
  let left = props.align === 'left' ? b.left - f.left : b.right - f.left - WIDTH
  left = Math.max(MARGIN, Math.min(left, f.width - WIDTH - MARGIN))
  let top = b.bottom - f.top + 6
  if (top + height > f.height - MARGIN) top = Math.max(MARGIN, b.top - f.top - 6 - height)
  pos.value = { top, left }
}
const onDoc = (event) => {
  if (root.value?.contains(event.target) || bubble.value?.contains(event.target)) return
  open.value = false
}
const close = () => (open.value = false)
const listen = (on) => {
  const method = on ? 'addEventListener' : 'removeEventListener'
  document[method]('click', onDoc, true)
  // 页面滚动或窗口变化时直接收起，避免气泡和按钮错位
  window[method]('scroll', close, true)
  window[method]('resize', close)
}
watch(open, async (value) => {
  listen(value)
  if (!value) return
  place()
  await nextTick()
  place()
})
onBeforeUnmount(() => listen(false))
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
    <Teleport to="#overlay-root" defer>
    <span
      v-if="open"
      ref="bubble"
      role="tooltip"
      class="solid-pop absolute z-[95] block w-60 rounded-2xl border border-ink-line p-3 text-left text-xs font-normal leading-5 text-ink-soft shadow-lift"
      :style="{ top: `${pos.top}px`, left: `${pos.left}px` }"
      @click.stop.prevent
    >
      <span class="flex items-center gap-1.5 font-black text-ink"><Icon icon="lucide:flame" width="14" class="text-flame" />打卡规则</span>
      <span class="mt-1 block">{{ rule.text }}，连续打卡的天数就是火苗数字。</span>
      <span class="mt-1 block text-ink-mute">连续天数、断签保护卡、成就、学习足迹和周报都按这个标准统计。</span>
      <span v-if="progress" class="mt-2 block rounded-xl px-2 py-1.5 font-semibold" :class="done ? 'bg-flame-light text-flame' : 'bg-background text-ink-soft'">{{ progress }}</span>
    </span>
    </Teleport>
  </span>
</template>
