<script setup>
import { computed, onBeforeUnmount, ref } from 'vue'
import dayjs from 'dayjs'
import { Icon } from '@iconify/vue'
import { formatMinutes } from '@/utils/dates'
import { useDesktop } from '@/composables/useDesktop'

const props = defineProps({
  day: { type: Object, required: true },
})
// reschedule：电脑端拖动任务块改开始时间，{ task, start_time, conflict }
const emit = defineEmits(['toggle', 'focus', 'open', 'plan-free', 'reschedule'])
const isDesktop = useDesktop()

const STATUS = { done: '已结束', ongoing: '进行中', upcoming: '' }
const SNAP = 15
// 时间轴不是按比例绘制的，拖动距离按"每 15 分钟 12 像素"换算，上下拖都能精确到刻
const PX_PER_STEP = 12

/** 今天的时间轴里插入一条"现在"指示线。 */
const items = computed(() => {
  const list = [...props.day.items]
  if (props.day.date !== dayjs().format('YYYY-MM-DD')) return list
  const now = dayjs().format('HH:mm')
  const index = list.findIndex((item) => item.start_time > now)
  list.splice(index === -1 ? list.length : index, 0, { type: 'now', id: 'now', start_time: now })
  return list
})

const toMinutes = (hm) => {
  const [h, m] = String(hm).split(':').map(Number)
  return h * 60 + m
}
const toHm = (minutes) => `${String(Math.floor(minutes / 60)).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`

// ---------------------------------------------------------------- 拖动改时间（仅电脑端）
const drag = ref(null)
let suppressClick = false

const canDrag = (item) => isDesktop.value && item.type === 'task' && !item.task.completed

const conflictsWith = (item, start, end) =>
  props.day.items.filter(
    (other) => other.id !== item.id && (other.type === 'course' || other.type === 'task') && toMinutes(other.start_time) < end && start < toMinutes(other.end_time),
  )

const onPointerDown = (event, item) => {
  if (!canDrag(item) || event.button !== 0) return
  // 点在勾选 / 专注按钮上时不拖动
  if (event.target.closest('[data-no-drag]')) return
  // 阻止拖动时选中文字（不影响随后的点击）
  event.preventDefault()
  const start = toMinutes(item.start_time)
  const duration = Math.max(SNAP, toMinutes(item.end_time) - start)
  drag.value = { item, startY: event.clientY, origin: start, duration, start, moved: false }
  window.addEventListener('pointermove', onPointerMove)
  window.addEventListener('pointerup', onPointerUp)
  window.addEventListener('keydown', onKey)
}

const onPointerMove = (event) => {
  const d = drag.value
  if (!d) return
  const dy = event.clientY - d.startY
  if (!d.moved && Math.abs(dy) < 6) return
  d.moved = true
  const steps = Math.round(dy / PX_PER_STEP)
  // 按步数移动后吸附到整 15 分钟；没移动时保持原时间；限制在当天内（不跨午夜）
  const target = steps === 0 ? d.origin : Math.round((d.origin + steps * SNAP) / SNAP) * SNAP
  d.start = Math.min(Math.max(0, target), 24 * 60 - d.duration)
}

const preview = computed(() => {
  const d = drag.value
  if (!d?.moved) return null
  const end = d.start + d.duration
  const clashes = conflictsWith(d.item, d.start, end)
  return { start: toHm(d.start), end: toHm(end), changed: d.start !== d.origin, clashes }
})

const cleanup = () => {
  window.removeEventListener('pointermove', onPointerMove)
  window.removeEventListener('pointerup', onPointerUp)
  window.removeEventListener('keydown', onKey)
}

const onPointerUp = () => {
  const d = drag.value
  const p = preview.value
  cleanup()
  drag.value = null
  if (!d?.moved) return
  suppressClick = true
  setTimeout(() => (suppressClick = false), 0)
  if (p?.changed) emit('reschedule', { task: d.item.task, start_time: p.start, conflict: p.clashes.map((c) => c.title) })
}

const onKey = (event) => {
  if (event.key !== 'Escape') return
  cleanup()
  drag.value = null
}

const openTask = (task) => !suppressClick && emit('open', task)
onBeforeUnmount(cleanup)
</script>

<template>
  <div>
    <p v-if="isDesktop && day.items.some((i) => i.type === 'task' && !i.task.completed)" class="mb-3 flex items-center gap-1.5 text-xs font-semibold text-ink-mute">
      <Icon icon="lucide:move-vertical" width="13" />上下拖动任务块可调整开始时间（按 15 分钟对齐，Esc 取消）
    </p>
    <ol class="relative space-y-2 pl-14" :class="drag?.moved && 'cursor-grabbing select-none'">
      <span class="absolute bottom-2 left-[46px] top-2 w-px bg-ink-line" aria-hidden="true" />
      <li v-for="item in items" :key="item.id" class="relative">
        <span class="num absolute -left-14 top-2.5 w-10 text-right text-[11px] font-bold" :class="item.type === 'now' ? 'text-danger' : 'text-ink-mute'">
          {{ item.start_time }}
        </span>

        <div v-if="item.type === 'now'" class="flex items-center gap-2 py-1">
          <span class="-ml-[11px] h-2.5 w-2.5 rounded-full bg-danger ring-4 ring-danger/15" />
          <span class="h-px flex-1 bg-danger/40" />
          <span class="text-[10px] font-bold text-danger">现在</span>
        </div>

        <div
          v-else-if="item.type === 'course'"
          class="rounded-2xl p-3 text-white shadow-soft transition"
          :class="[item.status === 'done' && 'opacity-55', preview?.clashes.some((c) => c.id === item.id) && 'ring-4 ring-danger/40']"
          :style="{ background: item.color }"
        >
          <div class="flex items-center justify-between gap-2">
            <p class="truncate text-sm font-black">{{ item.title }}</p>
            <span v-if="STATUS[item.status]" class="shrink-0 rounded-full bg-white/25 px-2 py-0.5 text-[10px] font-bold">{{ STATUS[item.status] }}</span>
          </div>
          <p class="mt-1 text-[11px] opacity-90">
            {{ item.start_time }}-{{ item.end_time }} · {{ item.periods }}<template v-if="item.location"> · {{ item.location }}</template>
          </p>
        </div>

        <div
          v-else-if="item.type === 'task'"
          class="relative flex items-center gap-3 rounded-2xl border bg-surface px-3 py-2.5 shadow-soft transition"
          :class="[
            drag?.moved && drag.item.id === item.id ? 'z-10 border-primary shadow-lift ring-4 ring-primary/20' : 'border-ink-line/70',
            preview?.clashes.some((c) => c.id === item.id) && 'ring-4 ring-danger/40',
            canDrag(item) && 'cursor-grab',
          ]"
          :style="drag?.moved && drag.item.id === item.id ? { transform: `translateY(${((drag.start - drag.origin) / 15) * 12}px)` } : undefined"
          @pointerdown="onPointerDown($event, item)"
        >
          <span v-if="canDrag(item)" class="-ml-1 shrink-0 text-ink-mute" aria-hidden="true"><Icon icon="lucide:grip-vertical" width="14" /></span>
          <button
            data-no-drag
            class="flex h-5 w-5 shrink-0 items-center justify-center rounded-full border-2"
            :class="item.task.completed ? 'border-success bg-success text-on-success' : 'border-primary'"
            type="button"
            :aria-label="item.task.completed ? '标记未完成' : '完成'"
            @click="emit('toggle', item.task)"
          >
            <Icon v-if="item.task.completed" icon="lucide:check" width="12" />
          </button>
          <button class="min-w-0 flex-1 text-left" type="button" @click="openTask(item.task)">
            <p class="truncate text-sm font-semibold" :class="item.task.completed ? 'text-ink-mute line-through' : 'text-ink'">{{ item.title }}</p>
            <p class="num text-[11px] text-ink-mute">
              {{ item.start_time }}-{{ item.end_time }}
              <template v-if="item.task.checklist_total"> · 子任务 {{ item.task.checklist_done }}/{{ item.task.checklist_total }}</template>
            </p>
          </button>
          <button v-if="!item.task.completed" data-no-drag class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary-light text-primary" type="button" aria-label="开始专注" @click="emit('focus', item.task)">
            <Icon icon="lucide:play" width="14" />
          </button>

          <!-- 拖动时显示目标时间与冲突提示 -->
          <div
            v-if="drag?.moved && drag.item.id === item.id && preview"
            class="pointer-events-none absolute -top-9 left-2 flex items-center gap-1.5 whitespace-nowrap rounded-xl px-2.5 py-1.5 text-xs font-black shadow-xl"
            :class="preview.clashes.length ? 'bg-danger text-on-danger' : 'bg-inverse text-inverse-ink'"
            role="status"
          >
            <Icon :icon="preview.clashes.length ? 'lucide:triangle-alert' : 'lucide:clock'" width="13" />
            <span class="num">{{ preview.start }}-{{ preview.end }}</span>
            <span v-if="preview.clashes.length" class="font-semibold">与「{{ preview.clashes[0].title }}」冲突，仍可放下</span>
            <span v-else-if="!preview.changed" class="font-semibold opacity-70">未改动</span>
          </div>
        </div>

        <button
          v-else
          class="flex w-full items-center gap-2 rounded-2xl border border-dashed border-primary/30 bg-primary-light/40 px-3 py-2.5 text-left transition hover:bg-primary-light"
          type="button"
          @click="emit('plan-free', item)"
        >
          <Icon icon="lucide:coffee" width="16" class="text-primary" />
          <span class="flex-1 text-xs font-semibold text-ink-soft">空闲 {{ formatMinutes(item.minutes) }}（至 {{ item.end_time }}）</span>
          <span class="text-xs font-bold text-primary">安排</span>
        </button>
      </li>
    </ol>
  </div>
</template>
