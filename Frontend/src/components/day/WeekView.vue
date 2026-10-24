<script setup>
import { computed } from 'vue'
import dayjs from 'dayjs'
import { coursesOnDate, mondayOf } from '@/utils/dates'

const props = defineProps({
  selected: { type: String, required: true },
  courses: { type: Array, default: () => [] },
  meta: { type: Object, default: null },
  tasks: { type: Array, default: () => [] },
})
const emit = defineEmits(['pick'])

/** 课程与任务合并成一条时间线，按开始时间排序；没有时刻的任务排在最后。 */
const merge = (courses, tasks) =>
  [
    ...courses.map((c) => ({ key: `c${c.id}`, type: 'course', time: c.start_time, title: c.course_name, color: c.color })),
    ...tasks.map((t) => ({ key: `t${t.id}`, type: 'task', time: t.start_time || '', title: t.title, done: t.completed })),
  ].sort((a, b) => (a.time || '99:99').localeCompare(b.time || '99:99') || (a.type === 'course' ? -1 : 1))

const days = computed(() => {
  const monday = mondayOf(props.selected)
  const today = dayjs().format('YYYY-MM-DD')
  return Array.from({ length: 7 }, (_, i) => {
    const date = monday.add(i, 'day')
    const key = date.format('YYYY-MM-DD')
    const items = merge(coursesOnDate(props.courses, props.meta, key), props.tasks.filter((t) => t.due_date === key))
    return { key, label: `周${'一二三四五六日'[i]}`, short: date.format('M/D'), today: key === today, items }
  })
})
</script>

<template>
  <!-- 手机：按天纵向排列；桌面：7 列周视图，内容多时每列单独上下滚动 -->
  <div class="space-y-2.5 lg:grid lg:grid-cols-7 lg:gap-3 lg:space-y-0">
    <button
      v-for="day in days"
      :key="day.key"
      type="button"
      class="w-full rounded-3xl border bg-surface p-3.5 text-left transition active:scale-[.99] lg:flex lg:h-[calc(100vh-230px)] lg:min-h-[360px] lg:flex-col lg:p-3 lg:hover:border-primary/40 lg:hover:shadow-soft"
      :class="day.key === selected ? 'border-primary/40 shadow-soft' : 'border-ink-line/60'"
      @click="emit('pick', day.key)"
    >
      <div class="mb-2 flex shrink-0 items-center justify-between lg:mb-3">
        <span class="text-sm font-black text-ink">{{ day.label }} <span class="num ml-1 text-xs font-semibold text-ink-mute">{{ day.short }}</span></span>
        <span v-if="day.today" class="rounded-full bg-primary px-2 py-0.5 text-[10px] font-bold text-white">今天</span>
      </div>
      <div v-if="day.items.length" class="scrollbar-hide flex flex-wrap gap-1.5 lg:-mr-1.5 lg:min-h-0 lg:flex-1 lg:flex-col lg:flex-nowrap lg:overflow-y-auto lg:pr-1.5">
        <span
          v-for="item in day.items"
          :key="item.key"
          class="rounded-lg px-2 py-1 text-[11px] lg:shrink-0 lg:py-1.5"
          :class="item.type === 'course' ? 'font-bold text-white' : item.done ? 'bg-background font-semibold text-ink-mute line-through' : 'bg-background font-semibold text-ink-soft'"
          :style="item.type === 'course' ? { background: item.color } : undefined"
        >
          <span v-if="item.time" class="num mr-1" :class="item.type === 'course' ? '' : 'text-ink-mute'">{{ item.time }}</span>{{ item.title }}
        </span>
      </div>
      <p v-else class="text-xs text-ink-mute">没有安排</p>
    </button>
  </div>
</template>
