<script setup>
/**
 * 日程时间轴（珠点轴）：按时间比例排布，1 分钟 = 0.8px。
 *   · 轴是一串珠点，颜色跟着上面紧挨着的块走：课程段沙色、任务段珊瑚、空闲段浅蓝；没有刻度横线，也没有"现在"横线，
 *     现在的位置是轴上的一个珊瑚点，时刻列里用珊瑚色写出来。
 *   · 课程块是实心沙色，课名前加 6px 分科色点；任务块是珊瑚；短于 40 分钟的事件用 32px 圆徽章。
 *   · 完成的任务：块变淡、标题划线、右侧是带勾的空心圈（不用浅绿）。
 *   · 空闲段不画框，只有一行"空闲 · 点按安排"。
 *   · ghosts：一键排今天的建议块（浅珊瑚底 + 描边），点 × / 圈切换是否加入；picking：空闲段快建时的预览块。
 * 块之间至少留 8px：短事件的圆徽章比按比例算出来的高时，后面的内容整体顺延，时刻跟着一起移动，顺序不会乱。
 */
import { computed, onBeforeUnmount, ref } from 'vue'
import dayjs from 'dayjs'
import { Icon } from '@iconify/vue'
import { compactMinutes } from '@/utils/dates'
import { subjectInk, subjectOf } from '@/utils/subjects'
import { useDesktop } from '@/composables/useDesktop'

const props = defineProps({
  day: { type: Object, required: true },
  // 一键排今天的建议：[{ key, kind, title, start_time, end_time, minutes, reason, optional, picked }]
  ghosts: { type: Array, default: () => [] },
  // 空闲段快建的预览：{ start_time, end_time, title }
  picking: { type: Object, default: null },
})
// reschedule：电脑端拖动任务块改开始时间，{ task, start_time, conflict }
const emit = defineEmits(['toggle', 'open', 'plan-free', 'reschedule', 'ghost'])
const isDesktop = useDesktop()

const PX = 0.8
const SHORT = 40 // 分钟：短于它用圆徽章
const DOT = 32 // 圆徽章直径
const GAP = 8 // 块之间的最小间隔
const AXIS = 68 // 轴中心离左边的距离
const SNAP = 15
const KIND_ICON = { exam: 'lucide:alarm-clock', review: 'lucide:notebook-pen', task: 'lucide:book-open' }

const toMin = (hm) => {
  const [h, m] = String(hm || '0:0').split(':').map(Number)
  return h * 60 + (m || 0)
}
const toHm = (minutes) => `${String(Math.floor(minutes / 60)).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`

// 现在（分钟）：每 30 秒更新一次，正在上的课、现在的位置跟着变
const nowMin = ref(dayjs().hour() * 60 + dayjs().minute())
const clock = setInterval(() => (nowMin.value = dayjs().hour() * 60 + dayjs().minute()), 30000)
onBeforeUnmount(() => clearInterval(clock))
const isToday = computed(() => props.day.date === dayjs().format('YYYY-MM-DD'))
const isPast = computed(() => props.day.date < dayjs().format('YYYY-MM-DD'))
/** 显示范围：默认 07:00–21:00，有更早 / 更晚的块时向外扩到整点。 */
const range = computed(() => {
  const all = [...props.day.items, ...props.ghosts, ...(props.picking ? [props.picking] : [])]
  let lo = 7 * 60
  let hi = 21 * 60
  for (const item of all) {
    lo = Math.min(lo, Math.floor(toMin(item.start_time) / 60) * 60)
    hi = Math.max(hi, Math.ceil(toMin(item.end_time) / 60) * 60)
  }
  return { start: lo - 15, end: Math.min(hi + 10, 24 * 60) }
})
const natural = (minutes) => (minutes - range.value.start) * PX

/** 课程、任务、建议块、快建预览：按时间排好，算出每块的 top / height，挤在一起时整体顺延。 */
const layout = computed(() => {
  const list = []
  for (const item of props.day.items) {
    if (item.type === 'course' || item.type === 'task') list.push({ kind: item.type, key: item.id, item })
  }
  for (const g of props.ghosts) list.push({ kind: 'ghost', key: `g-${g.key}`, item: g })
  if (props.picking) list.push({ kind: 'picking', key: 'picking', item: props.picking })
  list.sort((a, b) => toMin(a.item.start_time) - toMin(b.item.start_time) || (a.kind === 'course' ? -1 : 1))

  let shift = 0
  let lastBottom = -Infinity
  const shifts = [] // [起始分钟, 从这里开始的累计顺延]
  const blocks = list.map((entry) => {
    const s = toMin(entry.item.start_time)
    const e = Math.max(s + 5, toMin(entry.item.end_time))
    const short = e - s < SHORT
    const height = short ? DOT : (e - s) * PX
    let top = natural(s) + shift
    if (top < lastBottom + GAP) {
      shift += lastBottom + GAP - top
      top = lastBottom + GAP
      shifts.push([s, shift])
    }
    const bottom = top + height
    lastBottom = bottom
    // 圆徽章比按比例算出来的长：它下面的时刻也要顺延
    const overflow = bottom - (natural(e) + shift)
    if (overflow > 0) {
      shift += overflow
      shifts.push([e, shift])
    }
    return { ...entry, s, e, short, top, height, center: top + height / 2 }
  })
  const y = (minutes) => {
    let d = 0
    for (const [m, value] of shifts) if (m <= minutes) d = value
    return natural(minutes) + d
  }
  const height = Math.max(y(range.value.end), lastBottom) + 12
  return { blocks, y, height }
})

/** 空闲段：被建议块 / 快建预览占用时不再显示"点按安排"；已经过去的空闲不显示。 */
const frees = computed(() => {
  if (isPast.value) return []
  const taken = [...props.ghosts, ...(props.picking ? [props.picking] : [])]
  return props.day.items
    .filter((item) => item.type === 'free' && !(isToday.value && toMin(item.end_time) <= nowMin.value))
    .map((item) => {
      const s = toMin(item.start_time)
      const e = toMin(item.end_time)
      const covered = taken.some((g) => toMin(g.start_time) < e && toMin(g.end_time) > s)
      const top = layout.value.y(s)
      const bottom = layout.value.y(e)
      return { item, s, e, top, bottom, center: (top + bottom) / 2, covered }
    })
})

// ---------------------------------------------------------------- 珠点轴
const BEAD = {
  course: 'rgb(var(--c-course-line))',
  task: 'rgb(var(--c-primary-mid))',
  done: 'rgb(var(--c-primary-soft))',
  ghost: 'rgb(var(--c-primary-soft))',
  idle: 'rgb(var(--c-idle-bead))',
  none: 'rgb(var(--c-bead))',
}
const beadOf = (block) => (block.kind === 'course' ? BEAD.course : block.kind === 'task' ? (block.item.task.completed ? BEAD.done : BEAD.task) : BEAD.ghost)

/** 块与块之间的间隙按"上面那块"的颜色画珠点；落在空闲段里的部分改成空闲蓝。 */
const beads = computed(() => {
  const { blocks, y, height } = layout.value
  const gaps = []
  let cursor = 0
  let color = BEAD.none
  for (const block of blocks) {
    if (block.top > cursor) gaps.push([cursor, block.top, color])
    cursor = Math.max(cursor, block.top + block.height)
    color = beadOf(block)
  }
  gaps.push([cursor, height - 6, color])
  const zones = frees.value.map((f) => [y(f.s), y(f.e)])
  const out = []
  for (const [a, b, c] of gaps) {
    const marks = [...new Set([a, b, ...zones.flat().filter((p) => p > a && p < b)])].sort((p, q) => p - q)
    for (let i = 0; i < marks.length - 1; i++) {
      const mid = (marks[i] + marks[i + 1]) / 2
      const idle = zones.some(([p, q]) => p <= mid && mid < q)
      out.push({ y1: marks[i] + 4, y2: marks[i + 1] - 4, color: idle ? BEAD.idle : c })
    }
  }
  return out.filter((seg) => seg.y2 - seg.y1 >= 2)
})

// ---------------------------------------------------------------- 时刻列
const nowY = computed(() => (isToday.value && nowMin.value >= range.value.start && nowMin.value <= range.value.end ? layout.value.y(nowMin.value) : null))
const hours = computed(() => {
  const list = []
  let last = -Infinity
  for (let m = Math.ceil(range.value.start / 60) * 60; m <= range.value.end; m += 60) {
    const top = layout.value.y(m)
    if (nowY.value !== null && Math.abs(top - nowY.value) < 14) continue
    if (top - last < 16) continue
    list.push({ label: toHm(m), top })
    last = top
  }
  return list
})

// ---------------------------------------------------------------- 文字
const courseStatus = (item) => {
  if (isPast.value) return 'done'
  if (!isToday.value) return 'upcoming'
  if (nowMin.value >= toMin(item.end_time)) return 'done'
  return nowMin.value >= toMin(item.start_time) ? 'ongoing' : 'upcoming'
}
const periodText = (item) => String(item.periods || '').replace(/^第\s*/, '').replace(/\s*节$/, '')
const courseSub = (item) => [`${item.start_time}-${item.end_time}`, periodText(item) && `${periodText(item)} 节`, item.location].filter(Boolean).join(' · ')
const taskSub = (block) => {
  const t = block.item.task
  const steps = t.checklist_total ? ` · 子任务 ${t.checklist_done}/${t.checklist_total}` : ''
  return `${block.item.start_time}-${block.item.end_time} · ${compactMinutes(block.e - block.s)}${steps}`
}

const blockClass = (block) => {
  if (block.kind === 'course') return 'border-[1.5px] border-course-line bg-course text-course-icon'
  if (block.kind === 'task') {
    return block.item.task.completed
      ? 'bg-primary-soft text-primary-dark opacity-75'
      : 'bg-primary text-on-primary shadow-lift'
  }
  const off = block.kind === 'ghost' && !block.item.picked
  return off ? 'border-[1.5px] border-dashed border-bead bg-surface/60 text-ink-mute' : 'border-[1.5px] border-primary-mid bg-primary-light text-primary'
}
const blockIcon = (block) => {
  if (block.kind === 'course') return 'lucide:graduation-cap'
  if (block.kind === 'task') return block.item.task.completed ? 'lucide:check' : 'lucide:book-open'
  if (block.kind === 'picking') return 'lucide:pencil'
  return KIND_ICON[block.item.kind] || KIND_ICON.task
}
// ---------------------------------------------------------------- 拖动改时间（仅电脑端）
const drag = ref(null)
let suppressClick = false

const canDrag = (block) => isDesktop.value && block.kind === 'task' && !block.item.task.completed

const conflictsWith = (item, start, end) =>
  props.day.items.filter((other) => other.id !== item.id && (other.type === 'course' || other.type === 'task') && toMin(other.start_time) < end && start < toMin(other.end_time))

const onPointerDown = (event, block) => {
  if (!canDrag(block) || event.button !== 0) return
  if (event.target.closest('[data-no-drag]')) return
  event.preventDefault()
  drag.value = { item: block.item, startY: event.clientY, origin: block.s, duration: Math.max(SNAP, block.e - block.s), start: block.s, moved: false }
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
  // 按比例换算成分钟，吸附到整 15 分钟；限制在当天内（不跨午夜）
  const target = Math.round((d.origin + dy / PX) / SNAP) * SNAP
  d.start = Math.min(Math.max(0, target), 24 * 60 - d.duration)
}
const preview = computed(() => {
  const d = drag.value
  if (!d?.moved) return null
  const end = d.start + d.duration
  return { start: toHm(d.start), end: toHm(end), changed: d.start !== d.origin, clashes: conflictsWith(d.item, d.start, end) }
})
const clashIds = computed(() => new Set((preview.value?.clashes || []).map((c) => c.id)))
const dragging = (block) => drag.value?.moved && drag.value.item.id === block.item.id
const dragDy = computed(() => (drag.value?.moved ? (drag.value.start - drag.value.origin) * PX : 0))
const dragStyle = (block) => (dragging(block) ? { transform: `translateY(${dragDy.value}px)` } : {})
// 文字、完成圈跟着块一起移动（它们本身用 -50% 垂直居中，内联 transform 会覆盖掉，所以写在一起）
const rowStyle = (block) => ({ top: `${block.center}px`, ...(dragging(block) ? { transform: `translateY(calc(-50% + ${dragDy.value}px))` } : {}) })

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
onBeforeUnmount(cleanup)

const openTask = (task) => !suppressClick && emit('open', task)
const pick = (block) => {
  if (block.kind === 'task') openTask(block.item.task)
  else if (block.kind === 'ghost') emit('ghost', block.item)
}
</script>

<template>
  <div>
    <p v-if="isDesktop && day.items.some((i) => i.type === 'task' && !i.task.completed)" class="mb-2 flex items-center gap-1.5 text-xs font-semibold text-ink-mute">
      <Icon icon="lucide:move-vertical" width="13" />上下拖动任务块可调整开始时间（按 15 分钟对齐，Esc 取消）
    </p>
    <div class="relative" :class="drag?.moved && 'cursor-grabbing select-none'" :style="{ height: `${layout.height}px` }">
      <!-- 时刻：只留整点文字，没有横线；现在的时刻用珊瑚色写在同一列 -->
      <span v-for="h in hours" :key="h.label" class="num absolute left-0 w-10 -translate-y-1/2 text-[11px] font-semibold leading-none text-ink-mute" :style="{ top: `${h.top}px` }" aria-hidden="true">{{ h.label }}</span>
      <span v-if="nowY !== null" class="num absolute left-0 w-10 -translate-y-1/2 text-[11px] font-bold leading-none text-primary" :style="{ top: `${nowY}px` }">{{ toHm(nowMin) }}</span>

      <svg class="pointer-events-none absolute inset-0 overflow-visible" width="100%" :height="layout.height" aria-hidden="true">
        <line v-for="(seg, i) in beads" :key="i" class="bead" :x1="AXIS" :x2="AXIS" :y1="seg.y1" :y2="seg.y2" :style="{ stroke: seg.color }" />
      </svg>

      <!-- 空闲段：不画框，只有一行字 -->
      <template v-for="f in frees" :key="f.item.id">
        <button
          v-if="!f.covered"
          class="absolute left-[96px] right-0 -translate-y-1/2 text-left text-[13px] text-idle-ink"
          type="button"
          :data-free="f.item.start_time"
          :style="{ top: `${f.center}px` }"
          @click="emit('plan-free', f.item)"
        >
          空闲 {{ compactMinutes(f.item.minutes) }} · <span class="font-bold text-link">点按安排</span>
        </button>
      </template>

      <template v-for="block in layout.blocks" :key="block.key">
        <div
          class="absolute left-[52px] flex w-8 items-center justify-center transition-shadow"
          :class="[blockClass(block), block.short ? 'rounded-full' : 'rounded-full', clashIds.has(block.item.id) && 'ring-4 ring-danger/40', dragging(block) && 'z-10 ring-4 ring-primary/25', canDrag(block) && 'cursor-grab']"
          :style="{ top: `${block.top}px`, height: `${block.height}px`, ...dragStyle(block) }"
          aria-hidden="true"
          @pointerdown="onPointerDown($event, block)"
          @click="pick(block)"
        >
          <Icon :icon="blockIcon(block)" width="16" />
        </div>

        <!-- 课程 -->
        <div v-if="block.kind === 'course'" class="absolute left-[96px] right-2 grid -translate-y-1/2 gap-px leading-snug" :style="{ top: `${block.center}px` }">
          <small class="num truncate text-[11px] font-medium text-ink-mute">{{ courseSub(block.item) }}</small>
          <b class="flex min-w-0 items-center text-[15px] font-bold text-ink">
            <i class="mr-1.5 h-1.5 w-1.5 shrink-0 rounded-full" :style="{ background: subjectInk(subjectOf(block.item)) }" />
            <span v-if="courseStatus(block.item) === 'ongoing'" class="mr-1.5 shrink-0 rounded-full bg-primary-light px-1.5 text-[10px] font-bold text-primary">正在上</span>
            <span class="truncate">{{ block.item.title }}</span>
          </b>
        </div>

        <!-- 任务：点文字打开编辑，右侧圈完成 -->
        <template v-else-if="block.kind === 'task'">
          <button
            class="absolute left-[96px] right-9 grid -translate-y-1/2 gap-px text-left leading-snug"
            type="button"
            :style="rowStyle(block)"
            @pointerdown="onPointerDown($event, block)"
            @click="openTask(block.item.task)"
          >
            <small class="num truncate text-[11px] font-medium text-ink-mute">{{ taskSub(block) }}</small>
            <b class="truncate text-[15px] font-bold" :class="block.item.task.completed ? 'text-ink-mute line-through' : 'text-ink'">{{ block.item.title }}</b>
          </button>
          <button
            data-no-drag
            class="absolute right-0 flex h-[22px] w-[22px] -translate-y-1/2 items-center justify-center rounded-full border-[1.5px]"
            :class="block.item.task.completed ? 'border-bead text-ink-mute' : 'border-primary-mid hover:bg-primary-light'"
            type="button"
            :aria-label="block.item.task.completed ? '标记未完成' : '完成'"
            :style="rowStyle(block)"
            @click="emit('toggle', block.item.task)"
          >
            <Icon v-if="block.item.task.completed" icon="lucide:check" width="13" />
          </button>
          <!-- 拖动时显示目标时间与冲突提示 -->
          <div
            v-if="dragging(block) && preview"
            class="pointer-events-none absolute left-[96px] z-20 flex items-center gap-1.5 whitespace-nowrap rounded-xl px-2.5 py-1.5 text-xs font-black shadow-xl"
            :class="preview.clashes.length ? 'bg-danger text-on-danger' : 'bg-inverse text-inverse-ink'"
            :style="{ top: `${block.top + dragDy - 34}px` }"
            role="status"
          >
            <Icon :icon="preview.clashes.length ? 'lucide:triangle-alert' : 'lucide:clock'" width="13" />
            <span class="num">{{ preview.start }}-{{ preview.end }}</span>
            <span v-if="preview.clashes.length" class="font-semibold">与「{{ preview.clashes[0].title }}」冲突，仍可放下</span>
            <span v-else-if="!preview.changed" class="font-semibold opacity-70">未改动</span>
          </div>
        </template>

        <!-- 一键排今天的建议：点 × 去掉，点空心圈加回来 -->
        <button
          v-else-if="block.kind === 'ghost'"
          class="absolute left-[96px] right-0 flex -translate-y-1/2 items-center gap-1.5 overflow-hidden whitespace-nowrap text-left"
          type="button"
          role="checkbox"
          :aria-checked="block.item.picked"
          :aria-label="`${block.item.picked ? '去掉' : '加入'}：${block.item.title}`"
          :style="{ top: `${block.center}px` }"
          @click="emit('ghost', block.item)"
        >
          <span class="flex h-[18px] w-[18px] shrink-0 items-center justify-center rounded-full" :class="block.item.picked ? 'bg-primary-light text-primary' : 'border-[1.5px] border-bead'">
            <Icon v-if="block.item.picked" icon="lucide:x" width="11" />
          </span>
          <b class="truncate text-sm font-bold" :class="block.item.picked ? 'text-ink' : 'text-ink-mute'">{{ block.item.title }}</b>
          <small class="num shrink-0 text-[11px] text-ink-mute">{{ compactMinutes(block.item.minutes) }} · {{ block.item.reason }}</small>
        </button>

        <!-- 空闲段快建：正在安排 -->
        <div v-else class="absolute left-[96px] right-0 grid -translate-y-1/2 justify-items-start gap-1" :style="{ top: `${block.center}px` }">
          <b class="max-w-full truncate text-sm font-bold text-ink">{{ block.item.title || '新任务' }}</b>
          <span class="num rounded-full bg-idle px-2.5 py-0.5 text-xs font-bold text-idle-ink">{{ block.item.start_time }}-{{ block.item.end_time }} · 正在安排</span>
        </div>
      </template>

      <!-- 现在：轴上一个珊瑚点 -->
      <span v-if="nowY !== null" class="absolute left-[62px] h-3 w-3 -translate-y-1/2 rounded-full bg-primary shadow-[0_0_0_3px_rgb(var(--c-background))]" :style="{ top: `${nowY}px` }" aria-hidden="true" />
    </div>
  </div>
</template>

<style scoped>
.bead {
  stroke-width: 3.5;
  stroke-linecap: round;
  stroke-dasharray: 0.1 8;
}
</style>
