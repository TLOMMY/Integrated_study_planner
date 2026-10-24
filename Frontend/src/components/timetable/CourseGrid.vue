<script setup>
import { computed } from 'vue'
import { useDesktop } from '@/composables/useDesktop'

const props = defineProps({
  data: { type: Object, required: true },
  showOff: { type: Boolean, default: false },
})
const emit = defineEmits(['select', 'empty'])

const isDesktop = useDesktop()
// 桌面端屏幕更高，格子加高，课程名和教室能完整显示
const ROW = computed(() => (isDesktop.value ? 64 : 56))
const periods = computed(() => props.data.period_times.map((p, i) => ({ index: i + 1, ...p })))
const hasWeekend = computed(() => props.data.courses.some((c) => c.day_of_week >= 6))
const days = computed(() => props.data.days.slice(0, hasWeekend.value ? 7 : 5))

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

const blockStyle = ({ course, lane, width }) => ({
  top: `${(course.start_period - 1) * ROW.value + 2}px`,
  height: `${(course.end_period - course.start_period + 1) * ROW.value - 4}px`,
  left: `calc(${(lane / width) * 100}% + 2px)`,
  width: `calc(${100 / width}% - 4px)`,
  background: course.in_week ? course.color : undefined,
})
</script>

<template>
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
        <div class="flex h-11 flex-col items-center justify-center rounded-xl" :class="day.is_today && 'bg-primary text-white'">
          <span class="text-[11px] font-black lg:text-sm">{{ day.label }}</span>
          <span class="num text-[9px] lg:text-[11px]" :class="day.is_today ? 'text-white/80' : 'text-ink-mute'">{{ day.short }}</span>
        </div>
        <div class="relative" :style="{ height: `${periods.length * ROW}px` }">
          <button
            v-for="p in periods"
            :key="p.index"
            type="button"
            class="absolute inset-x-0.5 rounded-lg transition hover:bg-primary-light/70"
            :class="day.is_today && 'bg-primary-light/30'"
            :style="{ top: `${(p.index - 1) * ROW}px`, height: `${ROW}px` }"
            :aria-label="`${day.label}第${p.index}节 添加课程`"
            @click="emit('empty', { day_of_week: day.day_of_week, start_period: p.index })"
          />
          <button
            v-for="block in blocksByDay[day.day_of_week]"
            :key="block.course.id"
            type="button"
            class="absolute overflow-hidden rounded-xl p-1.5 text-left shadow-sm transition active:scale-95 lg:p-2.5 lg:hover:brightness-105"
            :class="block.course.in_week ? 'text-white' : 'border border-dashed border-ink-line bg-background text-ink-mute'"
            :style="blockStyle(block)"
            @click="emit('select', block.course)"
          >
            <p class="line-clamp-3 text-[11px] font-bold leading-tight lg:text-[13px]">{{ block.course.course_name }}</p>
            <p v-if="block.course.classroom" class="mt-0.5 truncate text-[9px] opacity-90 lg:mt-1 lg:text-[11px]">@{{ block.course.classroom }}</p>
            <p v-if="block.course.teacher" class="hidden truncate text-[11px] opacity-80 lg:block">{{ block.course.teacher }}</p>
            <p v-if="!block.course.in_week" class="mt-0.5 text-[8px]">非本周</p>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
