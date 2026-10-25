<script setup>
import { computed, ref } from 'vue'
import dayjs from 'dayjs'
import { Icon } from '@iconify/vue'
import { coursesOnDate, mondayOf } from '@/utils/dates'
import { useDesktop } from '@/composables/useDesktop'

const props = defineProps({
  selected: { type: String, required: true },
  month: { type: String, required: true },
  courses: { type: Array, default: () => [] },
  meta: { type: Object, default: null },
  tasks: { type: Array, default: () => [] },
})
// move：电脑端把格子里的任务拖到另一天，{ task, date }
const emit = defineEmits(['pick', 'month', 'move'])
const isDesktop = useDesktop()

const cells = computed(() => {
  const first = dayjs(props.month).startOf('month')
  const start = mondayOf(first)
  const end = dayjs(props.month).endOf('month')
  const count = Math.ceil((end.diff(start, 'day') + 1) / 7) * 7
  const today = dayjs().format('YYYY-MM-DD')
  return Array.from({ length: count }, (_, i) => {
    const date = start.add(i, 'day')
    const key = date.format('YYYY-MM-DD')
    const dayTasks = props.tasks.filter((t) => t.due_date === key)
    const open = dayTasks.filter((t) => !t.completed)
    return {
      key,
      day: date.date(),
      inMonth: date.month() === first.month(),
      today: key === today,
      courses: coursesOnDate(props.courses, props.meta, key).length,
      open: open.length,
      done: dayTasks.length - open.length,
      // 桌面端格子里直接列出待办（可拖动）
      preview: open.slice(0, 3),
      more: Math.max(open.length - 3, 0),
    }
  })
})

const shift = (n) => emit('month', dayjs(props.month).add(n, 'month').format('YYYY-MM-DD'))

// ---------------------------------------------------------------- 拖拽改期（仅电脑端）
const dragTask = ref(null)
const overKey = ref(null)
const onDragStart = (event, task) => {
  dragTask.value = task
  event.dataTransfer.effectAllowed = 'move'
  event.dataTransfer.setData('text/plain', String(task.id))
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
const isTarget = (key) => overKey.value === key && dragTask.value && dragTask.value.due_date !== key
</script>

<template>
  <div class="card p-3 lg:p-5">
    <div class="mb-2 flex items-center justify-between px-1 lg:mb-4">
      <button class="flex h-8 w-8 items-center justify-center rounded-full bg-background hover:bg-ink-line/60" type="button" aria-label="上个月" @click="shift(-1)"><Icon icon="lucide:chevron-left" width="16" /></button>
      <span class="text-sm font-black text-ink lg:text-base">{{ dayjs(month).format('YYYY 年 M 月') }}</span>
      <button class="flex h-8 w-8 items-center justify-center rounded-full bg-background hover:bg-ink-line/60" type="button" aria-label="下个月" @click="shift(1)"><Icon icon="lucide:chevron-right" width="16" /></button>
    </div>
    <p class="-mt-2 mb-3 hidden items-center justify-center gap-1.5 text-[11px] font-semibold text-ink-mute lg:flex">
      <Icon icon="lucide:move" width="12" />把格子里的待办拖到另一天即可改期
    </p>
    <div class="grid grid-cols-7 text-center text-[10px] font-bold text-ink-mute lg:text-xs">
      <span v-for="w in '一二三四五六日'" :key="w" class="py-1">{{ w }}</span>
    </div>
    <div class="grid grid-cols-7 gap-1 lg:gap-2">
      <div
        v-for="cell in cells"
        :key="cell.key"
        role="button"
        tabindex="0"
        class="flex aspect-square cursor-pointer flex-col items-center justify-center rounded-xl outline-none transition focus-visible:ring-4 focus-visible:ring-primary/20 lg:aspect-auto lg:h-[104px] lg:items-stretch lg:justify-start lg:border lg:p-2 lg:text-left"
        :class="[
          isTarget(cell.key)
            ? 'bg-primary-light text-primary ring-4 ring-primary/25 lg:border-primary'
            : cell.key === selected ? 'bg-primary text-on-primary lg:border-primary' : cell.today ? 'bg-primary-light text-primary lg:border-primary/30' : 'text-ink lg:border-ink-line/60 lg:hover:border-primary/40 lg:hover:bg-background',
          !cell.inMonth && !isTarget(cell.key) && 'opacity-35',
        ]"
        :aria-label="`${cell.key}，${cell.courses} 节课，${cell.open} 项待办`"
        @click="pick(cell.key)"
        @keydown.enter.prevent="pick(cell.key)"
        @keydown.space.prevent="pick(cell.key)"
        @dragover="onDragOver($event, cell.key)"
        @dragleave="onDragLeave($event, cell.key)"
        @drop.prevent="onDrop(cell.key)"
      >
        <span class="flex items-center justify-between">
          <span class="num text-sm font-black">{{ cell.day }}</span>
          <span v-if="isTarget(cell.key)" class="hidden text-[10px] font-black lg:inline">放到这天</span>
          <span v-else-if="cell.courses" class="hidden text-[10px] font-bold lg:inline" :class="cell.key === selected ? 'text-on-primary/80' : 'text-primary'">{{ cell.courses }} 节课</span>
        </span>
        <span class="mt-0.5 flex h-1.5 gap-0.5 lg:hidden">
          <span v-if="cell.courses" class="h-1.5 w-1.5 rounded-full" :class="cell.key === selected ? 'bg-on-primary' : 'bg-primary'" />
          <span v-if="cell.open" class="h-1.5 w-1.5 rounded-full bg-flame" />
          <span v-if="cell.done && !cell.open" class="h-1.5 w-1.5 rounded-full bg-success" />
        </span>
        <span class="mt-1.5 hidden min-w-0 space-y-0.5 lg:block">
          <span
            v-for="task in cell.preview"
            :key="task.id"
            class="block truncate rounded-md px-1.5 py-0.5 text-[11px] font-semibold"
            :class="[
              cell.key === selected && !isTarget(cell.key) ? 'bg-on-primary/20 text-on-primary' : 'bg-flame-light text-ink-soft',
              isDesktop && 'cursor-grab hover:ring-2 hover:ring-primary/40 active:cursor-grabbing',
              dragTask === task && 'opacity-40',
            ]"
            :draggable="isDesktop"
            :title="isDesktop ? '拖到另一天改期' : undefined"
            @dragstart.stop="onDragStart($event, task)"
            @dragend="onDragEnd"
          >{{ task.title }}</span>
          <span v-if="cell.more" class="block px-1.5 text-[10px] font-bold" :class="cell.key === selected ? 'text-on-primary/80' : 'text-ink-mute'">还有 {{ cell.more }} 项</span>
          <span v-if="!cell.open && cell.done" class="block px-1.5 text-[10px] font-bold" :class="cell.key === selected ? 'text-on-primary/80' : 'text-success'">✓ 已完成 {{ cell.done }} 项</span>
        </span>
      </div>
    </div>
    <div class="mt-3 flex justify-center gap-4 text-[10px] font-semibold text-ink-mute lg:hidden">
      <span class="flex items-center gap-1"><span class="h-1.5 w-1.5 rounded-full bg-primary" />有课</span>
      <span class="flex items-center gap-1"><span class="h-1.5 w-1.5 rounded-full bg-flame" />待办</span>
      <span class="flex items-center gap-1"><span class="h-1.5 w-1.5 rounded-full bg-success" />已完成</span>
    </div>
  </div>
</template>
