<script setup>
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { priorityMeta } from '@/utils/task'
import { relativeDay } from '@/utils/dates'

const props = defineProps({
  task: { type: Object, required: true },
  showDate: { type: Boolean, default: false },
  hidePlan: { type: Boolean, default: false },
  // 多选模式：左侧变成勾选框，点整行即选中 / 取消
  selectable: { type: Boolean, default: false },
  selected: { type: Boolean, default: false },
})
const emit = defineEmits(['toggle', 'open', 'focus', 'select'])

const priority = computed(() => priorityMeta(props.task.priority))
const timeText = computed(() => {
  const { start_time: start, end_time: end } = props.task
  return start ? `${start}${end ? `-${end}` : ''}` : ''
})
</script>

<template>
  <div
    class="group flex items-start gap-3 rounded-2xl border border-ink-line/60 bg-surface px-3.5 py-3 transition active:scale-[.99]"
    :class="[task.completed && !selectable ? 'opacity-60' : 'shadow-soft', selected && 'border-primary bg-primary-light/50 ring-2 ring-primary/30']"
  >
    <button
      v-if="selectable"
      class="mt-0.5 flex h-[22px] w-[22px] shrink-0 items-center justify-center rounded-md border-2 transition"
      :class="selected ? 'border-primary bg-primary text-white' : 'border-ink-line hover:border-primary/60'"
      type="button"
      role="checkbox"
      :aria-checked="selected"
      :aria-label="`选择：${task.title}`"
      @click="emit('select', task)"
    >
      <Icon v-if="selected" icon="lucide:check" width="14" />
    </button>
    <button
      v-else
      class="mt-0.5 flex h-[22px] w-[22px] shrink-0 items-center justify-center rounded-full border-2 transition"
      :class="task.completed ? 'border-success bg-success text-white' : [priority.ring, 'hover:bg-background']"
      type="button"
      :aria-label="task.completed ? '标记为未完成' : '完成任务'"
      @click="emit('toggle', task)"
    >
      <Icon v-if="task.completed" icon="lucide:check" width="14" class="animate-check" />
    </button>

    <button class="min-w-0 flex-1 text-left" type="button" @click="selectable ? emit('select', task) : emit('open', task)">
      <p class="text-[15px] font-semibold leading-snug" :class="task.completed ? 'text-ink-mute line-through' : 'text-ink'">
        {{ task.title }}
      </p>
      <div class="mt-1 flex flex-wrap items-center gap-x-2.5 gap-y-1 text-[11px] font-medium text-ink-mute">
        <span v-if="showDate && task.due_date" :class="task.overdue ? 'text-danger' : ''" class="inline-flex items-center gap-0.5">
          <Icon icon="lucide:calendar" width="12" />{{ relativeDay(task.due_date) }}
        </span>
        <span v-else-if="task.overdue" class="inline-flex items-center gap-0.5 text-danger">
          <Icon icon="lucide:calendar-x" width="12" />{{ relativeDay(task.due_date) }}
        </span>
        <span v-if="timeText" class="inline-flex items-center gap-0.5"><Icon icon="lucide:clock" width="12" />{{ timeText }}</span>
        <span v-else class="inline-flex items-center gap-0.5"><Icon icon="lucide:hourglass" width="12" />{{ task.duration_minutes }} 分钟</span>
        <span v-if="task.subject" class="rounded-md bg-primary-light px-1.5 py-0.5 font-bold text-primary">{{ task.subject }}</span>
        <span v-if="task.repeat_rule !== 'none'" class="inline-flex items-center gap-0.5"><Icon icon="lucide:repeat" width="12" />{{ task.repeat_label }}</span>
        <span v-if="task.pomodoros" class="inline-flex items-center gap-0.5 text-flame"><Icon icon="lucide:timer" width="12" />×{{ task.pomodoros }}</span>
        <span v-if="task.plan_title && !hidePlan" class="inline-flex min-w-0 max-w-[150px] items-center gap-0.5">
          <Icon icon="lucide:map" width="12" class="shrink-0" /><span class="truncate">{{ task.plan_title }}</span>
        </span>
      </div>
    </button>

    <div class="flex shrink-0 items-center gap-1">
      <Icon v-if="task.priority && !task.completed" icon="lucide:flag" width="14" :class="priority.color" />
      <button
        v-if="!task.completed && !selectable"
        class="flex h-8 w-8 items-center justify-center rounded-full bg-primary-light text-primary transition hover:bg-primary hover:text-white"
        type="button"
        :aria-label="`专注：${task.title}`"
        @click="emit('focus', task)"
      >
        <Icon icon="lucide:play" width="14" />
      </button>
    </div>
  </div>
</template>
