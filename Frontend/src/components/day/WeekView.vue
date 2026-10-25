<script setup>
import { computed, ref } from 'vue'
import dayjs from 'dayjs'
import { Icon } from '@iconify/vue'
import { coursesOnDate, mondayOf } from '@/utils/dates'
import { useDesktop } from '@/composables/useDesktop'

const props = defineProps({
  selected: { type: String, required: true },
  courses: { type: Array, default: () => [] },
  meta: { type: Object, default: null },
  tasks: { type: Array, default: () => [] },
})
// move：电脑端把任务拖到另一天，{ task, date }
const emit = defineEmits(['pick', 'move'])
const isDesktop = useDesktop()

/** 课程与任务合并成一条时间线，按开始时间排序；没有时刻的任务排在最后。 */
const merge = (courses, tasks) =>
  [
    ...courses.map((c) => ({ key: `c${c.id}`, type: 'course', time: c.start_time, title: c.course_name, color: c.color })),
    ...tasks.map((t) => ({ key: `t${t.id}`, type: 'task', time: t.start_time || '', title: t.title, done: t.completed, task: t })),
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

// ---------------------------------------------------------------- 拖拽改期（仅电脑端）
const dragTask = ref(null)
const overKey = ref(null)
const canDrag = (item) => isDesktop.value && item.type === 'task' && !item.done
const onDragStart = (event, item) => {
  dragTask.value = item.task
  event.dataTransfer.effectAllowed = 'move'
  event.dataTransfer.setData('text/plain', String(item.task.id))
}
const onDragOver = (event, key) => {
  if (!dragTask.value) return
  event.preventDefault()
  event.dataTransfer.dropEffect = 'move'
  overKey.value = key
}
const onDragLeave = (event, key) => {
  if (overKey.value === key && !event.currentTarget.contains(event.relatedTarget)) overKey.value = null
}
const onDrop = (key) => {
  const task = dragTask.value
  dragTask.value = null
  overKey.value = null
  if (task && task.due_date !== key) emit('move', { task, date: key })
}
const onDragEnd = () => {
  dragTask.value = null
  overKey.value = null
}
const pick = (key) => !dragTask.value && emit('pick', key)
</script>

<template>
  <div>
    <p class="mb-3 hidden items-center gap-1.5 text-xs font-semibold text-ink-mute lg:flex">
      <Icon icon="lucide:move" width="13" />按住任务拖到另一天即可改期，时刻与时长保持不变
    </p>
    <!-- 手机：按天纵向排列；桌面：7 列周视图，内容多时每列单独上下滚动 -->
    <div class="space-y-2.5 lg:grid lg:grid-cols-7 lg:gap-3 lg:space-y-0">
      <div
        v-for="day in days"
        :key="day.key"
        role="button"
        tabindex="0"
        class="w-full cursor-pointer rounded-3xl border bg-surface p-3.5 text-left outline-none transition focus-visible:ring-4 focus-visible:ring-primary/20 active:scale-[.99] lg:flex lg:h-[calc(100vh-250px)] lg:min-h-[360px] lg:flex-col lg:p-3 lg:hover:border-primary/40 lg:hover:shadow-soft"
        :class="[
          overKey === day.key && dragTask?.due_date !== day.key
            ? 'border-primary bg-primary-light/60 ring-4 ring-primary/20'
            : day.key === selected ? 'border-primary/40 shadow-soft' : 'border-ink-line/60',
        ]"
        :aria-label="`${day.label} ${day.short}，${day.items.length} 项安排`"
        @click="pick(day.key)"
        @keydown.enter.prevent="pick(day.key)"
        @keydown.space.prevent="pick(day.key)"
        @dragover="onDragOver($event, day.key)"
        @dragleave="onDragLeave($event, day.key)"
        @drop.prevent="onDrop(day.key)"
      >
        <div class="mb-2 flex shrink-0 items-center justify-between lg:mb-3">
          <span class="text-sm font-black text-ink">{{ day.label }} <span class="num ml-1 text-xs font-semibold text-ink-mute">{{ day.short }}</span></span>
          <span v-if="day.today" class="rounded-full bg-primary px-2 py-0.5 text-[10px] font-bold text-on-primary">今天</span>
        </div>
        <p v-if="overKey === day.key && dragTask && dragTask.due_date !== day.key" class="mb-2 flex shrink-0 items-center gap-1 rounded-xl bg-primary px-2 py-1.5 text-[11px] font-bold text-on-primary">
          <Icon icon="lucide:calendar-check" width="12" />放到{{ day.label }}<template v-if="dragTask.start_time"> {{ dragTask.start_time }}</template>
        </p>
        <div v-if="day.items.length" class="scrollbar-hide flex flex-wrap gap-1.5 lg:-mr-1.5 lg:min-h-0 lg:flex-1 lg:flex-col lg:flex-nowrap lg:overflow-y-auto lg:pr-1.5">
          <span
            v-for="item in day.items"
            :key="item.key"
            class="rounded-lg px-2 py-1 text-[11px] transition lg:shrink-0 lg:py-1.5"
            :class="[
              item.type === 'course' ? 'font-bold text-white' : item.done ? 'bg-background font-semibold text-ink-mute line-through' : 'bg-background font-semibold text-ink-soft',
              canDrag(item) && 'cursor-grab hover:bg-primary-light hover:text-primary active:cursor-grabbing',
              dragTask && item.task === dragTask && 'opacity-40 ring-2 ring-primary',
            ]"
            :style="item.type === 'course' ? { background: item.color } : undefined"
            :draggable="canDrag(item)"
            :title="canDrag(item) ? '拖到另一天改期' : undefined"
            @dragstart="onDragStart($event, item)"
            @dragend="onDragEnd"
          >
            <span v-if="item.time" class="num mr-1" :class="item.type === 'course' ? '' : 'text-ink-mute'">{{ item.time }}</span>{{ item.title }}
          </span>
        </div>
        <p v-else class="text-xs text-ink-mute">没有安排</p>
      </div>
    </div>
  </div>
</template>
