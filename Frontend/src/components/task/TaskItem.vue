<script setup>
import { computed, ref } from 'vue'
import { Icon } from '@iconify/vue'
import { priorityMeta } from '@/utils/task'
import { relativeDay } from '@/utils/dates'
import { useTasksStore } from '@/stores/tasks'
import { isBilibili, linkHost, remindLabel, taskLinks } from './extras'

const props = defineProps({
  task: { type: Object, required: true },
  showDate: { type: Boolean, default: false },
  hidePlan: { type: Boolean, default: false },
  // 多选模式：左侧变成勾选框，点整行即选中 / 取消
  selectable: { type: Boolean, default: false },
  selected: { type: Boolean, default: false },
})
const emit = defineEmits(['toggle', 'open', 'focus', 'select'])

const tasks = useTasksStore()
const priority = computed(() => priorityMeta(props.task.priority))
const timeText = computed(() => {
  const { start_time: start, end_time: end } = props.task
  return start ? `${start}${end ? `-${end}` : ''}` : ''
})

// 展开的面板：子任务快速勾选 / 学习资源链接
const panel = ref(null)
const togglePanel = (name) => (panel.value = panel.value === name ? null : name)
const checklist = computed(() => props.task.checklist || [])
// 学习资源：链接字段 + 备注里写的网址（AI 推荐的资源写在备注里）
const links = computed(() => taskLinks(props.task))
const tags = computed(() => props.task.tags || [])
const stepsDone = computed(() => props.task.checklist_done ?? checklist.value.filter((item) => item.done).length)
const hasBili = computed(() => links.value.some(isBilibili))
const showRemind = computed(() => props.task.remind_at && !props.task.completed)
</script>

<template>
  <div
    class="group rounded-2xl border border-ink-line/60 bg-surface transition"
    :class="[task.completed && !selectable ? 'opacity-60' : 'shadow-soft', selected && 'border-primary bg-primary-light/50 ring-2 ring-primary/30']"
  >
    <div class="flex items-start gap-3 px-3.5 py-3 active:scale-[.99]">
      <button
        v-if="selectable"
        class="mt-0.5 flex h-[22px] w-[22px] shrink-0 items-center justify-center rounded-md border-2 transition"
        :class="selected ? 'border-primary bg-primary text-on-primary' : 'border-ink-line hover:border-primary/60'"
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
        :class="task.completed ? 'border-success bg-success text-on-success' : [priority.ring, 'hover:bg-background']"
        type="button"
        :aria-label="task.completed ? '标记为未完成' : '完成任务'"
        @click="emit('toggle', task)"
      >
        <Icon v-if="task.completed" icon="lucide:check" width="14" class="animate-check" />
      </button>

      <div class="min-w-0 flex-1">
        <button class="block w-full min-w-0 text-left" type="button" @click="selectable ? emit('select', task) : emit('open', task)">
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
            <span v-if="showRemind" class="inline-flex items-center gap-0.5 text-flame" :title="`提醒：${task.remind_at.replace('T', ' ')}`"><Icon icon="lucide:bell" width="12" />{{ remindLabel(task.remind_at) }}</span>
            <span v-if="task.subject" class="rounded-md bg-primary-light px-1.5 py-0.5 font-bold text-primary">{{ task.subject }}</span>
            <span v-if="task.list_name" class="inline-flex min-w-0 max-w-[120px] items-center gap-0.5 font-semibold text-ink-soft">
              <Icon icon="lucide:folder" width="12" class="shrink-0" /><span class="truncate">{{ task.list_name }}</span>
            </span>
            <span v-for="tag in tags" :key="tag" class="font-semibold text-xp">#{{ tag }}</span>
            <span v-if="task.repeat_rule !== 'none'" class="inline-flex items-center gap-0.5"><Icon icon="lucide:repeat" width="12" />{{ task.repeat_label }}</span>
            <span v-if="task.pomodoros" class="inline-flex items-center gap-0.5 text-flame"><Icon icon="lucide:timer" width="12" />×{{ task.pomodoros }}</span>
            <span v-if="task.plan_title && !hidePlan" class="inline-flex min-w-0 max-w-[150px] items-center gap-0.5">
              <Icon icon="lucide:map" width="12" class="shrink-0" /><span class="truncate">{{ task.plan_title }}</span>
            </span>
          </div>
        </button>

        <!-- 子任务进度 / 链接数量：点开就地展开 -->
        <div v-if="!selectable && (checklist.length || links.length)" class="mt-1.5 flex flex-wrap gap-1.5">
          <button
            v-if="checklist.length"
            type="button"
            class="inline-flex items-center gap-1 rounded-lg px-2 py-0.5 text-[11px] font-bold transition"
            :class="panel === 'steps' ? 'bg-primary text-on-primary' : stepsDone === checklist.length ? 'bg-success-light text-success' : 'bg-background text-ink-soft hover:bg-ink-line/60'"
            :aria-expanded="panel === 'steps'"
            :aria-label="`子任务 ${stepsDone}/${checklist.length}，点击${panel === 'steps' ? '收起' : '展开'}`"
            @click="togglePanel('steps')"
          >
            <Icon icon="lucide:list-todo" width="12" /><span class="num">{{ stepsDone }}/{{ checklist.length }}</span>
          </button>
          <button
            v-if="links.length"
            type="button"
            class="inline-flex items-center gap-1 rounded-lg px-2 py-0.5 text-[11px] font-bold transition"
            :class="panel === 'links' ? 'bg-primary text-on-primary' : 'bg-background text-ink-soft hover:bg-ink-line/60'"
            :aria-expanded="panel === 'links'"
            :aria-label="`${links.length} 个学习资源，点击${panel === 'links' ? '收起' : '展开'}`"
            @click="togglePanel('links')"
          >
            <Icon icon="lucide:link" width="12" /><span class="num">{{ links.length }}</span>
            <span v-if="hasBili" class="rounded px-1 text-[9px] font-black" :class="panel === 'links' ? 'bg-on-primary/25' : 'bg-primary text-on-primary'">B站</span>
          </button>
        </div>
      </div>

      <div class="flex shrink-0 items-center gap-1">
        <Icon v-if="task.priority && !task.completed" icon="lucide:flag" width="14" :class="priority.color" />
        <button
          v-if="!task.completed && !selectable"
          class="flex h-8 w-8 items-center justify-center rounded-full bg-primary-light text-primary transition hover:bg-primary hover:text-on-primary"
          type="button"
          :aria-label="`专注：${task.title}`"
          @click="emit('focus', task)"
        >
          <Icon icon="lucide:play" width="14" />
        </button>
      </div>
    </div>

    <ul v-if="panel === 'steps' && !selectable" class="space-y-0.5 border-t border-ink-line/60 px-3.5 py-2 pl-[50px]">
      <li v-for="item in checklist" :key="item.id">
        <button type="button" class="flex w-full items-center gap-2 rounded-xl px-1.5 py-1.5 text-left hover:bg-background" role="checkbox" :aria-checked="item.done" @click="tasks.toggleChecklistItem(task, item.id)">
          <span class="flex h-4 w-4 shrink-0 items-center justify-center rounded border-2 transition" :class="item.done ? 'border-success bg-success text-on-success' : 'border-ink-line'">
            <Icon v-if="item.done" icon="lucide:check" width="10" />
          </span>
          <span class="min-w-0 flex-1 truncate text-[13px]" :class="item.done ? 'text-ink-mute line-through' : 'text-ink-soft'">{{ item.title }}</span>
        </button>
      </li>
    </ul>

    <ul v-if="panel === 'links' && !selectable" class="space-y-1 border-t border-ink-line/60 px-3.5 py-2 pl-[50px]">
      <li v-for="link in links" :key="link.url">
        <a :href="link.url" target="_blank" rel="noopener noreferrer" class="flex items-center gap-2 rounded-xl px-1.5 py-1.5 hover:bg-background">
          <span v-if="isBilibili(link)" class="shrink-0 rounded-md bg-primary px-1.5 py-0.5 text-[10px] font-black text-on-primary">B站</span>
          <Icon v-else icon="lucide:globe" width="14" class="shrink-0 text-ink-mute" />
          <span class="min-w-0 flex-1">
            <span class="block truncate text-[13px] font-semibold text-ink">{{ link.title || linkHost(link.url) }}</span>
            <span class="block truncate text-[10px] text-ink-mute">{{ linkHost(link.url) }}</span>
          </span>
          <Icon icon="lucide:external-link" width="13" class="shrink-0 text-ink-mute" />
        </a>
      </li>
    </ul>
  </div>
</template>
