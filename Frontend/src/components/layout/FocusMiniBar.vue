<script setup>
/**
 * 专注进行中、离开专注页时的悬浮条。
 * 展开：底部居中的胶囊（时间 + 任务名），点击回到专注页。
 * 收起：屏幕右侧的小圆点（进度环 + 分钟数），点击展开。不挡输入框和按钮：
 * - 展开 5 秒后自动收起；
 * - 有底部输入框的页面（AI 对话）进入时直接收起；
 * - 任何输入框获得焦点时收起。
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import { useFocusStore } from '@/stores/focus'

const AUTO_COLLAPSE_MS = 5000
const INPUT_ROUTES = new Set(['ai'])

const focus = useFocusStore()
const route = useRoute()
const router = useRouter()
const visible = computed(() => focus.active && route.name !== 'focus')
const collapsed = ref(false)
let timer = null

const minutesLeft = computed(() => Math.ceil(focus.remainingMs / 60000))
const ring = computed(() => {
  const c = 2 * Math.PI * 17
  return { c, offset: c * (1 - focus.progress) }
})

const collapse = () => {
  clearTimeout(timer)
  collapsed.value = true
}
const expand = () => {
  collapsed.value = false
  clearTimeout(timer)
  timer = setTimeout(collapse, AUTO_COLLAPSE_MS)
}
const sync = () => (visible.value && INPUT_ROUTES.has(route.name) ? collapse() : visible.value && expand())

watch(visible, sync)
watch(() => route.name, sync)

const isField = (el) => el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.tagName === 'SELECT' || el.isContentEditable)
const onFocusIn = (event) => visible.value && isField(event.target) && collapse()

onMounted(() => {
  document.addEventListener('focusin', onFocusIn)
  sync()
})
onBeforeUnmount(() => {
  document.removeEventListener('focusin', onFocusIn)
  clearTimeout(timer)
})

const open = () => router.push({ name: 'focus' })
</script>

<template>
  <Transition enter-active-class="transition duration-200" enter-from-class="translate-y-4 opacity-0" leave-active-class="transition duration-150" leave-to-class="translate-y-4 opacity-0" mode="out-in">
    <button
      v-if="visible && !collapsed"
      key="bar"
      class="absolute bottom-3 left-1/2 z-30 flex -translate-x-1/2 items-center gap-2.5 glass glass-ink rounded-full bg-inverse py-2 pl-2 pr-4 text-inverse-ink shadow-xl active:scale-95"
      type="button"
      aria-label="回到专注页"
      @click="open"
    >
      <span class="flex h-8 w-8 items-center justify-center rounded-full" :class="focus.status === 'running' ? 'bg-primary text-on-primary' : 'bg-inverse-ink/20'">
        <Icon :icon="focus.status === 'running' ? 'lucide:timer' : 'lucide:pause'" width="16" />
      </span>
      <span class="num text-base font-black">{{ focus.clock }}</span>
      <span class="max-w-[120px] truncate text-xs opacity-70">{{ focus.task?.title || '自由专注' }}</span>
    </button>
    <button
      v-else-if="visible"
      key="dot"
      class="absolute right-2 top-[42%] z-30 flex h-11 w-11 items-center justify-center rounded-full bg-inverse text-inverse-ink shadow-xl glass glass-ink active:scale-95"
      type="button"
      :aria-label="`专注${focus.status === 'running' ? '中' : '已暂停'}，还剩 ${focus.clock}，点击展开`"
      @click="expand"
    >
      <svg class="absolute inset-0 -rotate-90" viewBox="0 0 44 44" aria-hidden="true">
        <circle cx="22" cy="22" r="17" fill="none" stroke="currentColor" stroke-opacity="0.2" stroke-width="3" />
        <circle cx="22" cy="22" r="17" fill="none" class="text-primary" stroke="currentColor" stroke-width="3" stroke-linecap="round" :stroke-dasharray="ring.c" :stroke-dashoffset="ring.offset" />
      </svg>
      <Icon v-if="focus.status !== 'running'" icon="lucide:pause" width="14" class="relative" />
      <span v-else class="num relative text-[11px] font-black">{{ minutesLeft }}'</span>
    </button>
  </Transition>
</template>
