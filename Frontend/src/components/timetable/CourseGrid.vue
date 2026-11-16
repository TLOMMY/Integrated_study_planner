<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import { useDesktop } from '@/composables/useDesktop'
import { subjectBg, subjectInk, subjectOf } from '@/utils/subjects'

const props = defineProps({
  data: { type: Object, required: true },
  showOff: { type: Boolean, default: false },
})
// empty：确认新建课程的位置，{ day_of_week, start_period, end_period }
const emit = defineEmits(['select', 'empty'])

const isDesktop = useDesktop()
// 桌面端屏幕更高，格子加高，课程名和教室能完整显示
const ROW = computed(() => (isDesktop.value ? 64 : 56))
const periods = computed(() => props.data.period_times.map((p, i) => ({ index: i + 1, ...p })))
// 固定显示周一到周日（周末没课也留着，方便点空格加课）
const days = computed(() => props.data.days.slice(0, 7))

/** 每天的课程块：同一时段多门课时并排分栏（如单双周交替的两门课）。 */
const blocksByDay = computed(() => {
  const result = {}
  for (const day of days.value) {
    const list = props.data.courses
      .filter((c) => c.day_of_week === day.day_of_week && (c.in_week || props.showOff))
      .sort((a, b) => a.start_period - b.start_period || Number(b.in_week) - Number(a.in_week))
    const lanes = []
    const placed = list.map((course) => {
      let lane = lanes.findIndex((end) => end < course.start_period)
      if (lane === -1) lane = lanes.push(0) - 1
      lanes[lane] = course.end_period
      return { course, lane }
    })
    result[day.day_of_week] = placed.map((item) => {
      const overlapping = placed.filter(
        (other) => other.course.start_period <= item.course.end_period && other.course.end_period >= item.course.start_period,
      )
      const width = Math.max(...overlapping.map((o) => o.lane)) + 1
      return { ...item, width }
    })
  }
  return result
})

// 分科色只在课表页用：浅色做块、深色做教室文字，课名一律墨色
const blockStyle = ({ course, lane, width }) => ({
  top: `${(course.start_period - 1) * ROW.value + 2}px`,
  height: `${(course.end_period - course.start_period + 1) * ROW.value - 4}px`,
  left: `calc(${(lane / width) * 100}% + 2px)`,
  width: `calc(${100 / width}% - 4px)`,
  background: course.in_week ? subjectBg(subjectOf(course)) : undefined,
})
const roomStyle = (course) => (course.in_week ? { color: subjectInk(subjectOf(course)) } : undefined)

// ---------------------------------------------------------------- 点空白处新建：先放一个草稿块，拖上下把手调节数，再点草稿进入编辑
// 草稿：{ day, start, end }。点别的空白处：先取消草稿（再点一次才新建）；点草稿本身：打开课程编辑器。
const MIN_SPAN = 2 // 默认占两节（多数课两节连上）；放不下时缩到能放下
const draft = ref(null)
const resizing = ref(null) // { edge: 'top' | 'bottom', originY, start, end }

const clampSpan = (day, start, end) => {
  const total = periods.value.length
  return { day, start: Math.max(1, Math.min(start, total)), end: Math.max(1, Math.min(end, total)) }
}
const onEmpty = (day, period) => {
  if (draft.value) {
    // 已经有草稿：这一下只是取消
    draft.value = null
    return
  }
  const total = periods.value.length
  const end = Math.min(period + MIN_SPAN - 1, total)
  draft.value = clampSpan(day.day_of_week, period, end)
}
const openDraft = () => {
  const d = draft.value
  if (!d || resizing.value?.moved) return
  draft.value = null
  emit('empty', { day_of_week: d.day, start_period: d.start, end_period: d.end })
}
const draftStyle = computed(() => {
  const d = draft.value
  if (!d) return {}
  return { top: `${(d.start - 1) * ROW.value + 2}px`, height: `${(d.end - d.start + 1) * ROW.value - 4}px` }
})
const draftTime = computed(() => {
  const d = draft.value
  if (!d) return ''
  const list = props.data.period_times
  return `${d.start === d.end ? `第 ${d.start} 节` : `第 ${d.start}-${d.end} 节`} · ${list[d.start - 1]?.start || ''}-${list[d.end - 1]?.end || ''}`
})

/** 拖动上 / 下把手：按格子高度换算成节数，至少 1 节。触摸和鼠标都走 pointer 事件。 */
const startResize = (event, edge) => {
  const d = draft.value
  if (!d) return
  event.preventDefault()
  event.stopPropagation()
  resizing.value = { edge, originY: event.clientY, start: d.start, end: d.end, moved: false }
  window.addEventListener('pointermove', onResize, { passive: false })
  window.addEventListener('pointerup', endResize)
  window.addEventListener('pointercancel', endResize)
}
const onResize = (event) => {
  const r = resizing.value
  const d = draft.value
  if (!r || !d) return
  event.preventDefault()
  const steps = Math.round((event.clientY - r.originY) / ROW.value)
  if (steps) r.moved = true
  const total = periods.value.length
  if (r.edge === 'top') d.start = Math.max(1, Math.min(r.start + steps, d.end))
  else d.end = Math.min(total, Math.max(r.end + steps, d.start))
}
const endResize = () => {
  window.removeEventListener('pointermove', onResize)
  window.removeEventListener('pointerup', endResize)
  window.removeEventListener('pointercancel', endResize)
  // 让紧跟着的 click 知道这是拖动结束，不要打开编辑器
  setTimeout(() => (resizing.value = null), 0)
}
onBeforeUnmount(endResize)
// 换周 / 换课表时收起草稿
watch(() => [props.data.week, props.data.courses.length], () => (draft.value = null))
const onKey = (event) => event.key === 'Escape' && (draft.value = null)
watch(draft, (value) => (value ? window.addEventListener('keydown', onKey) : window.removeEventListener('keydown', onKey)))
onBeforeUnmount(() => window.removeEventListener('keydown', onKey))
defineExpose({ clearDraft: () => (draft.value = null) })
</script>

<template>
  <div>
  <div class="flex select-none">
    <!-- 节次列 -->
    <div class="w-9 shrink-0 lg:w-14">
      <div class="h-11" />
      <div v-for="p in periods" :key="p.index" class="flex flex-col items-center justify-center" :style="{ height: `${ROW}px` }">
        <span class="num text-xs font-black text-ink-soft">{{ p.index }}</span>
        <span class="num text-[8px] leading-tight text-ink-mute lg:text-[10px]">{{ p.start }}</span>
      </div>
    </div>

    <div class="grid flex-1" :style="{ gridTemplateColumns: `repeat(${days.length}, minmax(0, 1fr))` }">
      <div v-for="day in days" :key="day.day_of_week" class="min-w-0">
        <div class="flex h-11 flex-col items-center justify-center rounded-xl" :class="day.is_today ? 'bg-primary text-on-primary' : 'text-ink'">
          <span class="text-[11px] font-bold lg:text-sm">{{ day.label }}</span>
          <span class="num text-[9px] lg:text-[11px]" :class="day.is_today ? 'text-on-primary/80' : 'text-ink-mute'">{{ day.short }}</span>
        </div>
        <div class="relative" :style="{ height: `${periods.length * ROW}px` }">
          <button
            v-for="p in periods"
            :key="p.index"
            type="button"
            class="absolute inset-x-0.5 rounded-lg transition hover:bg-primary-light/70"
            :class="day.is_today && 'bg-primary-light/30'"
            :style="{ top: `${(p.index - 1) * ROW}px`, height: `${ROW}px` }"
            :aria-label="draft ? '取消新建' : `${day.label}第${p.index}节 添加课程`"
            @click="onEmpty(day, p.index)"
          />
          <button
            v-for="block in blocksByDay[day.day_of_week]"
            :key="block.course.id"
            type="button"
            class="absolute overflow-hidden rounded-[10px] px-[3px] py-1 text-left transition active:scale-95 lg:p-2.5 lg:hover:brightness-[1.03]"
            :class="block.course.in_week ? 'text-ink' : 'border border-dashed border-ink-line bg-background text-ink-mute'"
            :style="blockStyle(block)"
            @click="draft ? (draft = null) : emit('select', block.course)"
          >
            <p class="line-clamp-3 break-all text-[11px] font-bold leading-tight lg:text-[13px]">{{ block.course.course_name }}</p>
            <p v-if="block.course.classroom" class="mt-0.5 truncate text-[9px] font-medium lg:mt-1 lg:text-[11px]" :style="roomStyle(block.course)">@{{ block.course.classroom }}</p>
            <p v-if="block.course.teacher" class="hidden truncate text-[11px] text-ink-mute lg:block">{{ block.course.teacher }}</p>
            <p v-if="!block.course.in_week" class="mt-0.5 text-[8px]">非本周</p>
          </button>

          <!-- 新建草稿：点它进入编辑，拖上下把手改节数 -->
          <div
            v-if="draft && draft.day === day.day_of_week"
            class="absolute inset-x-0.5 z-10 rounded-[10px] border-[1.5px] border-primary bg-primary-light shadow-lift"
            :class="!resizing && 'transition-[top,height] duration-150'"
            :style="draftStyle"
          >
            <button class="flex h-full w-full flex-col items-center justify-center gap-0.5 px-1 text-primary" type="button" :aria-label="`新建课程：${draftTime}，点击填写`" @click.stop="openDraft">
              <Icon icon="lucide:plus" width="18" />
              <span class="num text-center text-[9px] font-bold leading-tight lg:text-[11px]">{{ draft.end - draft.start + 1 }} 节</span>
            </button>
            <span
              class="absolute -top-2 left-1/2 flex h-4 w-8 -translate-x-1/2 cursor-ns-resize touch-none items-center justify-center rounded-full bg-primary"
              role="slider"
              aria-label="拖动调整开始节次"
              :aria-valuenow="draft.start"
              @pointerdown="startResize($event, 'top')"
              @click.stop
            ><i class="h-0.5 w-3 rounded-full bg-on-primary" /></span>
            <span
              class="absolute -bottom-2 left-1/2 flex h-4 w-8 -translate-x-1/2 cursor-ns-resize touch-none items-center justify-center rounded-full bg-primary"
              role="slider"
              aria-label="拖动调整结束节次"
              :aria-valuenow="draft.end"
              @pointerdown="startResize($event, 'bottom')"
              @click.stop
            ><i class="h-0.5 w-3 rounded-full bg-on-primary" /></span>
          </div>
        </div>
      </div>
    </div>
  </div>
  <!-- 草稿的时间提示 -->
  <p v-if="draft" class="mt-2 text-center text-xs text-ink-mute" role="status">
    <b class="num text-primary">{{ draftTime }}</b> · 拖上下把手调整，点它填写课程；点别处取消
  </p>
  </div>
</template>
