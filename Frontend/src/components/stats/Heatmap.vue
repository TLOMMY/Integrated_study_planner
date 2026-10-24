<script setup>
import { computed, ref } from 'vue'
import dayjs from 'dayjs'
import { formatMinutes } from '@/utils/dates'

const props = defineProps({ heatmap: { type: Object, required: true } })
const active = ref(null)

const COLORS = ['bg-ink-line/60', 'bg-primary/25', 'bg-primary/50', 'bg-primary/75', 'bg-primary']

const columns = computed(() => {
  const cols = []
  props.heatmap.days.forEach((day, i) => {
    if (i % 7 === 0) cols.push([])
    cols[cols.length - 1].push(day)
  })
  return cols
})
const monthLabels = computed(() =>
  columns.value.map((col, i) => {
    const month = dayjs(col[0].date).month()
    const prev = i ? dayjs(columns.value[i - 1][0].date).month() : -1
    return month !== prev ? `${month + 1}月` : ''
  }),
)
const totalDays = computed(() => props.heatmap.days.filter((d) => d.level > 0).length)
</script>

<template>
  <div>
    <div class="scrollbar-hide overflow-x-auto">
      <div class="inline-flex flex-col gap-1">
        <div class="flex gap-[3px] pl-5">
          <span v-for="(label, i) in monthLabels" :key="i" class="w-[14px] text-[9px] font-semibold text-ink-mute">{{ label }}</span>
        </div>
        <div class="flex gap-[3px]">
          <div class="flex w-4 flex-col gap-[3px] text-[9px] text-ink-mute">
            <span v-for="(w, i) in ['一', '', '三', '', '五', '', '日']" :key="i" class="h-[14px] leading-[14px]">{{ w }}</span>
          </div>
          <div v-for="(col, ci) in columns" :key="ci" class="flex flex-col gap-[3px]">
            <button
              v-for="day in col"
              :key="day.date"
              type="button"
              class="h-[14px] w-[14px] rounded-[4px] transition hover:ring-2 hover:ring-primary/40"
              :class="[COLORS[day.level], active?.date === day.date && 'ring-2 ring-ink']"
              :aria-label="`${day.date} 专注 ${day.minutes} 分钟`"
              @click="active = day"
            />
          </div>
        </div>
      </div>
    </div>
    <div class="mt-3 flex items-center justify-between text-[11px] text-ink-mute">
      <span v-if="active" class="font-semibold text-ink-soft">{{ dayjs(active.date).format('M月D日') }}：{{ formatMinutes(active.minutes) }} · 完成 {{ active.tasks }} 个任务</span>
      <span v-else>近 {{ heatmap.weeks }} 周有 <b class="num text-primary">{{ totalDays }}</b> 天在学习</span>
      <span class="flex items-center gap-1">少<i v-for="(c, i) in COLORS" :key="i" class="h-2.5 w-2.5 rounded-[3px]" :class="c" />多</span>
    </div>
  </div>
</template>
