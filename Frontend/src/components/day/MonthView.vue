<script setup>
import { computed } from 'vue'
import dayjs from 'dayjs'
import { Icon } from '@iconify/vue'
import { coursesOnDate, mondayOf } from '@/utils/dates'

const props = defineProps({
  selected: { type: String, required: true },
  month: { type: String, required: true },
  courses: { type: Array, default: () => [] },
  meta: { type: Object, default: null },
  tasks: { type: Array, default: () => [] },
})
const emit = defineEmits(['pick', 'month'])

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
      // 桌面端格子里直接列出待办标题
      preview: open.slice(0, 3).map((t) => t.title),
      more: Math.max(open.length - 3, 0),
    }
  })
})

const shift = (n) => emit('month', dayjs(props.month).add(n, 'month').format('YYYY-MM-DD'))
</script>

<template>
  <div class="card p-3 lg:p-5">
    <div class="mb-2 flex items-center justify-between px-1 lg:mb-4">
      <button class="flex h-8 w-8 items-center justify-center rounded-full bg-background hover:bg-ink-line/60" type="button" aria-label="上个月" @click="shift(-1)"><Icon icon="lucide:chevron-left" width="16" /></button>
      <span class="text-sm font-black text-ink lg:text-base">{{ dayjs(month).format('YYYY 年 M 月') }}</span>
      <button class="flex h-8 w-8 items-center justify-center rounded-full bg-background hover:bg-ink-line/60" type="button" aria-label="下个月" @click="shift(1)"><Icon icon="lucide:chevron-right" width="16" /></button>
    </div>
    <div class="grid grid-cols-7 text-center text-[10px] font-bold text-ink-mute lg:text-xs">
      <span v-for="w in '一二三四五六日'" :key="w" class="py-1">{{ w }}</span>
    </div>
    <div class="grid grid-cols-7 gap-1 lg:gap-2">
      <button
        v-for="cell in cells"
        :key="cell.key"
        type="button"
        class="flex aspect-square flex-col items-center justify-center rounded-xl transition lg:aspect-auto lg:h-[104px] lg:items-stretch lg:justify-start lg:border lg:p-2 lg:text-left"
        :class="[
          cell.key === selected ? 'bg-primary text-white lg:border-primary' : cell.today ? 'bg-primary-light text-primary lg:border-primary/30' : 'text-ink lg:border-ink-line/60 lg:hover:border-primary/40 lg:hover:bg-background',
          !cell.inMonth && 'opacity-35',
        ]"
        :aria-label="`${cell.key}，${cell.courses} 节课，${cell.open} 项待办`"
        @click="emit('pick', cell.key)"
      >
        <span class="flex items-center justify-between">
          <span class="num text-sm font-black">{{ cell.day }}</span>
          <span v-if="cell.courses" class="hidden text-[10px] font-bold lg:inline" :class="cell.key === selected ? 'text-white/80' : 'text-primary'">{{ cell.courses }} 节课</span>
        </span>
        <span class="mt-0.5 flex h-1.5 gap-0.5 lg:hidden">
          <span v-if="cell.courses" class="h-1.5 w-1.5 rounded-full" :class="cell.key === selected ? 'bg-white' : 'bg-primary'" />
          <span v-if="cell.open" class="h-1.5 w-1.5 rounded-full bg-flame" />
          <span v-if="cell.done && !cell.open" class="h-1.5 w-1.5 rounded-full bg-success" />
        </span>
        <span class="mt-1.5 hidden min-w-0 space-y-0.5 lg:block">
          <span
            v-for="(title, i) in cell.preview"
            :key="i"
            class="block truncate rounded-md px-1.5 py-0.5 text-[11px] font-semibold"
            :class="cell.key === selected ? 'bg-white/20 text-white' : 'bg-flame-light text-ink-soft'"
          >{{ title }}</span>
          <span v-if="cell.more" class="block px-1.5 text-[10px] font-bold" :class="cell.key === selected ? 'text-white/80' : 'text-ink-mute'">还有 {{ cell.more }} 项</span>
          <span v-if="!cell.open && cell.done" class="block px-1.5 text-[10px] font-bold" :class="cell.key === selected ? 'text-white/80' : 'text-success'">✓ 已完成 {{ cell.done }} 项</span>
        </span>
      </button>
    </div>
    <div class="mt-3 flex justify-center gap-4 text-[10px] font-semibold text-ink-mute lg:hidden">
      <span class="flex items-center gap-1"><span class="h-1.5 w-1.5 rounded-full bg-primary" />有课</span>
      <span class="flex items-center gap-1"><span class="h-1.5 w-1.5 rounded-full bg-flame" />待办</span>
      <span class="flex items-center gap-1"><span class="h-1.5 w-1.5 rounded-full bg-success" />已完成</span>
    </div>
  </div>
</template>
