<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import dayjs from 'dayjs'
import { Icon } from '@iconify/vue'
import DayTimeline from '@/components/day/DayTimeline.vue'
import WeekView from '@/components/day/WeekView.vue'
import MonthView from '@/components/day/MonthView.vue'
import TaskItem from '@/components/task/TaskItem.vue'
import TaskEditor from '@/components/task/TaskEditor.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import { dayApi } from '@/api'
import { useTasksStore } from '@/stores/tasks'
import { useTimetableStore } from '@/stores/timetable'
import { useUiStore } from '@/stores/ui'
import { focusRoute } from '@/utils/task'
import { mondayOf, relativeDay, shortMinutes, todayStr, weekdayLabel } from '@/utils/dates'

const router = useRouter()
const tasks = useTasksStore()
const timetable = useTimetableStore()
const ui = useUiStore()

const MODES = [{ k: 'day', l: '日' }, { k: 'week', l: '周' }, { k: 'month', l: '月' }]
const mode = ref('day')
const selected = ref(todayStr())
const month = ref(todayStr())
const day = ref(null)
const rangeTasks = ref([])
const loading = ref(false)
const editor = ref({ open: false, task: null, defaults: {} })

const strip = computed(() => {
  const monday = mondayOf(selected.value)
  return Array.from({ length: 7 }, (_, i) => {
    const d = monday.add(i, 'day')
    return { key: d.format('YYYY-MM-DD'), label: '一二三四五六日'[i], day: d.date(), today: d.isSame(dayjs(), 'day') }
  })
})

const title = computed(() => `${dayjs(selected.value).format('M月D日')} ${weekdayLabel(selected.value)}`)
const weekLabel = computed(() => {
  const monday = mondayOf(selected.value)
  return `${monday.format('M月D日')} – ${monday.add(6, 'day').format('M月D日')}`
})
const isToday = computed(() =>
  mode.value === 'month' ? dayjs(month.value).isSame(dayjs(), 'month') : mode.value === 'week' ? mondayOf(selected.value).isSame(mondayOf(todayStr()), 'day') : selected.value === todayStr(),
)

/** 每种视图真正依赖的数据范围；只有它变化时才请求，避免点选同一周内的日期也重复加载。 */
const range = computed(() => {
  if (mode.value === 'day') return { kind: 'day', key: selected.value }
  const start = mode.value === 'week' ? mondayOf(selected.value) : mondayOf(dayjs(month.value).startOf('month'))
  const end = start.add(mode.value === 'week' ? 6 : 41, 'day')
  return { kind: 'range', key: `${start.format('YYYY-MM-DD')}~${end.format('YYYY-MM-DD')}`, start, end }
})

// 快速切换视图或翻页时，只采用最后一次请求的结果，慢请求晚到也不会覆盖新数据
let ticket = 0
const refresh = async () => {
  const current = ++ticket
  const r = range.value
  if (r.kind === 'day') {
    loading.value = !day.value || day.value.date !== r.key
    try {
      const data = await dayApi.timeline(r.key)
      if (current === ticket) day.value = data
    } catch (error) {
      if (current === ticket) ui.fail(error)
    } finally {
      if (current === ticket) loading.value = false
    }
    return
  }
  try {
    await timetable.ensure()
    const list = await tasks.range(r.start.format('YYYY-MM-DD'), r.end.format('YYYY-MM-DD'))
    if (current === ticket) rangeTasks.value = list
  } catch (error) {
    if (current === ticket) ui.fail(error)
  }
}

watch(() => range.value.key, refresh)
onMounted(refresh)

const setMode = (key) => {
  // 进入月视图时显示所选日期所在的月份
  if (key === 'month') month.value = selected.value
  mode.value = key
}
const pick = (key) => {
  selected.value = key
  month.value = key
  mode.value = 'day'
}
const goToday = () => {
  selected.value = todayStr()
  month.value = todayStr()
}
const shiftDay = (n) => (selected.value = dayjs(selected.value).add(n, 'day').format('YYYY-MM-DD'))
const shiftWeek = (n) => shiftDay(n * 7)

const toggle = async (task) => {
  await tasks.toggle(task)
  refresh()
}
const openTask = (task) => (editor.value = { open: true, task, defaults: {} })
const planFree = (slot) => {
  editor.value = { open: true, task: null, defaults: { due_date: selected.value, start_time: slot.start_time, duration_minutes: Math.min(slot.minutes, 60) } }
}
const askAi = () => router.push({ name: 'ai', query: { q: `帮我安排${relativeDay(selected.value)}的学习，避开课程` } })

// ---------------------------------------------------------------- 拖拽改期 + 撤销
const undo = ref(null)
let undoTimer = null
const showUndo = (message, revert) => {
  clearTimeout(undoTimer)
  undo.value = { message, revert, busy: false }
  undoTimer = setTimeout(() => (undo.value = null), 6000)
}
const runUndo = async () => {
  const current = undo.value
  if (!current || current.busy) return
  current.busy = true
  try {
    await current.revert()
    ui.toast('已撤销', 'info')
    undo.value = null
    refresh()
  } catch (error) {
    current.busy = false
    ui.fail(error)
  }
}
onBeforeUnmount(() => clearTimeout(undoTimer))

/** 周 / 月视图：拖到另一天，只改日期（时刻、时长保留，提醒随之平移）。 */
const moveToDate = async ({ task, date }) => {
  const pending = tasks.reschedule(task, { due_date: date })
  // 先在界面上挪过去，请求失败再刷新回来
  task.due_date = date
  try {
    const revert = await pending
    if (revert) showUndo(`已移到 ${dayjs(date).format('M月D日')} ${weekdayLabel(date)}`, revert)
  } catch (error) {
    ui.fail(error)
  }
  refresh()
}

/** 日视图时间轴：上下拖动改开始时间（冲突时提示，但仍然保存）。 */
const moveToTime = async ({ task, start_time: startTime, conflict }) => {
  try {
    const revert = await tasks.reschedule(task, { due_date: task.due_date, start_time: startTime })
    if (revert) showUndo(`已改到 ${startTime} 开始${conflict.length ? `，与「${conflict[0]}」时间重叠` : ''}`, revert)
  } catch (error) {
    ui.fail(error)
  }
  refresh()
}
</script>

<template>
  <div class="flex h-full flex-col">
    <header class="glass-bar shrink-0 bg-surface px-5 pb-3 pt-[calc(var(--safe-top)+16px)] lg:border-b lg:border-ink-line/70 lg:px-10 lg:pt-6">
      <div class="desk-page">
        <div class="flex items-center justify-between gap-3">
          <div>
            <h1 class="text-[22px] font-black text-ink">日程</h1>
            <p class="text-xs font-semibold text-ink-mute">
              <template v-if="mode === 'week'">{{ weekLabel }}</template>
              <template v-else-if="mode === 'month'">{{ dayjs(month).format('YYYY 年 M 月') }}</template>
              <template v-else>{{ title }}<template v-if="day?.teaching_week"> · 第 {{ day.teaching_week }} 周</template></template>
            </p>
          </div>
          <div class="flex items-center gap-2">
            <button v-if="!isToday" class="chip" type="button" @click="goToday">回到{{ mode === 'month' ? '本月' : mode === 'week' ? '本周' : '今天' }}</button>
            <!-- 桌面端：视图切换放在标题行右侧 -->
            <div class="hidden w-56 rounded-2xl bg-ink-line/40 p-1 lg:flex">
              <button
                v-for="m in MODES"
                :key="m.k"
                type="button"
                class="flex-1 rounded-xl py-1.5 text-xs font-bold transition"
                :class="mode === m.k ? 'bg-surface text-ink shadow-soft' : 'text-ink-mute hover:text-ink-soft'"
                :aria-pressed="mode === m.k"
                @click="setMode(m.k)"
              >
                {{ m.l }}
              </button>
            </div>
          </div>
        </div>

        <div class="mt-3 flex rounded-2xl bg-ink-line/40 p-1 lg:hidden">
          <button
            v-for="m in MODES"
            :key="m.k"
            type="button"
            class="flex-1 rounded-xl py-1.5 text-xs font-bold transition"
            :class="mode === m.k ? 'bg-surface text-ink shadow-soft' : 'text-ink-mute'"
            :aria-pressed="mode === m.k"
            @click="setMode(m.k)"
          >
            {{ m.l }}
          </button>
        </div>

        <div v-if="mode === 'day'" class="mt-3 flex items-center gap-1">
          <button class="flex h-8 w-6 items-center justify-center text-ink-mute hover:text-ink" type="button" aria-label="前一天" @click="shiftDay(-1)"><Icon icon="lucide:chevron-left" width="16" /></button>
          <div class="grid flex-1 grid-cols-7 gap-1">
            <button
              v-for="d in strip"
              :key="d.key"
              type="button"
              class="flex flex-col items-center rounded-xl py-1.5 transition lg:flex-row lg:justify-center lg:gap-2"
              :class="d.key === selected ? 'bg-primary text-on-primary' : d.today ? 'text-primary hover:bg-primary-light' : 'text-ink-soft hover:bg-background'"
              @click="selected = d.key"
            >
              <span class="text-[10px] font-bold opacity-80 lg:text-xs">{{ d.label }}</span>
              <span class="num text-sm font-black">{{ d.day }}</span>
            </button>
          </div>
          <button class="flex h-8 w-6 items-center justify-center text-ink-mute hover:text-ink" type="button" aria-label="后一天" @click="shiftDay(1)"><Icon icon="lucide:chevron-right" width="16" /></button>
        </div>

        <div v-else-if="mode === 'week'" class="mt-3 flex items-center justify-between">
          <button class="chip" type="button" aria-label="上一周" @click="shiftWeek(-1)"><Icon icon="lucide:chevron-left" width="14" />上一周</button>
          <span class="num text-sm font-black text-ink">{{ weekLabel }}</span>
          <button class="chip" type="button" aria-label="下一周" @click="shiftWeek(1)">下一周<Icon icon="lucide:chevron-right" width="14" /></button>
        </div>
      </div>
    </header>

    <div class="scrollbar-hide flex-1 overflow-y-auto px-4 pb-24 pt-4 lg:px-10 lg:pb-10 lg:pt-6">
      <div class="desk-page">
        <template v-if="mode === 'day'">
          <div v-if="loading" class="space-y-2"><div v-for="i in 4" :key="i" class="skeleton h-14" /></div>
          <!-- 手机：单列；桌面：左侧时间轴，右侧当日概况 + 未定时任务 -->
          <div v-else-if="day" class="lg:grid lg:grid-cols-[minmax(0,1fr)_320px] lg:items-start lg:gap-8">
            <div class="lg:col-start-2 lg:row-start-1 lg:space-y-4">
              <div class="mb-4 grid grid-cols-3 gap-2 text-center lg:mb-0">
                <div class="rounded-2xl bg-surface p-2.5 shadow-soft"><p class="num text-lg font-black text-primary">{{ day.summary.courses }}</p><p class="text-[10px] font-bold text-ink-mute">节课</p></div>
                <div class="rounded-2xl bg-surface p-2.5 shadow-soft"><p class="num text-lg font-black text-ink">{{ day.summary.tasks_done }}/{{ day.summary.tasks }}</p><p class="text-[10px] font-bold text-ink-mute">任务</p></div>
                <div class="rounded-2xl bg-surface p-2.5 shadow-soft"><p class="num text-lg font-black text-success">{{ shortMinutes(day.summary.free_minutes) }}</p><p class="text-[10px] font-bold text-ink-mute">可支配</p></div>
              </div>
              <button class="hidden w-full items-center gap-3 rounded-3xl bg-gradient-to-r from-primary to-xp p-4 text-left text-on-primary shadow-lift transition hover:brightness-105 lg:flex" type="button" @click="askAi">
                <Icon icon="lucide:sparkles" width="22" />
                <span class="flex-1 text-sm font-bold">让 AI 按空闲时段安排{{ relativeDay(selected) }}的学习</span>
                <Icon icon="lucide:chevron-right" width="18" />
              </button>
            </div>

            <div class="min-w-0 lg:col-start-1 lg:row-start-1 lg:row-end-3">
              <!-- 当天没有具体时刻的任务：放在时间轴最上方（类似日历的"全天"栏） -->
              <section v-if="day.unscheduled.length" class="mb-4 rounded-3xl border border-dashed border-primary/30 bg-primary-light/40 p-3">
                <h3 class="mb-2 flex items-center gap-1.5 px-1 text-xs font-black text-primary">
                  <Icon icon="lucide:sun" width="14" />全天 · 未定时间 <span class="num text-ink-mute">{{ day.unscheduled.length }}</span>
                </h3>
                <div class="space-y-2">
                  <TaskItem v-for="t in day.unscheduled" :key="t.id" :task="t" @toggle="toggle" @open="openTask" @focus="(x) => router.push(focusRoute(x))" />
                </div>
              </section>
              <DayTimeline v-if="day.items.length" :day="day" @toggle="toggle" @focus="(t) => router.push(focusRoute(t))" @open="openTask" @plan-free="planFree" @reschedule="moveToTime" />
              <EmptyState v-else-if="!day.unscheduled.length" compact icon="lucide:calendar-heart" title="这一天没有课程和定时任务" />
            </div>

            <section v-if="day.undated?.length" class="mt-5 lg:col-start-2 lg:row-start-2 lg:mt-4">
              <h3 class="mb-2 flex items-center gap-1.5 px-1 text-xs font-black text-ink-soft">
                <Icon icon="lucide:inbox" width="14" />没有日期的待办 <span class="num text-ink-mute">{{ day.undated.length }}</span>
              </h3>
              <div class="space-y-2">
                <TaskItem v-for="t in day.undated" :key="t.id" :task="t" @toggle="toggle" @open="openTask" @focus="(x) => router.push(focusRoute(x))" />
              </div>
            </section>

            <button class="mt-5 flex w-full items-center gap-3 rounded-3xl bg-gradient-to-r from-primary to-xp p-4 text-left text-on-primary shadow-lift lg:hidden" type="button" @click="askAi">
              <Icon icon="lucide:sparkles" width="22" />
              <span class="flex-1 text-sm font-bold">让 AI 按空闲时段安排{{ relativeDay(selected) }}的学习</span>
              <Icon icon="lucide:chevron-right" width="18" />
            </button>
          </div>
        </template>

        <WeekView v-else-if="mode === 'week'" :selected="selected" :courses="timetable.courses" :meta="timetable.meta" :tasks="rangeTasks" @pick="pick" @move="moveToDate" />
        <MonthView v-else :selected="selected" :month="month" :courses="timetable.courses" :meta="timetable.meta" :tasks="rangeTasks" @pick="pick" @month="(m) => (month = m)" @move="moveToDate" />
      </div>
    </div>

    <!-- 拖拽改期后的撤销条 -->
    <Transition enter-active-class="transition duration-200" enter-from-class="translate-y-4 opacity-0" leave-active-class="transition duration-150" leave-to-class="translate-y-4 opacity-0">
      <div v-if="undo" class="absolute inset-x-3 bottom-3 z-30 flex items-center gap-3 rounded-2xl bg-inverse px-4 py-3 text-inverse-ink shadow-2xl lg:inset-x-auto lg:left-1/2 lg:w-[460px] lg:-translate-x-1/2" role="status">
        <Icon icon="lucide:circle-check" width="18" class="shrink-0 text-success" />
        <span class="min-w-0 flex-1 text-sm font-semibold">{{ undo.message }}</span>
        <button class="flex shrink-0 items-center gap-1 rounded-xl bg-inverse-ink/15 px-3 py-1.5 text-xs font-bold hover:bg-inverse-ink/25 disabled:opacity-50" type="button" :disabled="undo.busy" @click="runUndo">
          <Icon icon="lucide:undo-2" width="14" />撤销
        </button>
      </div>
    </Transition>

    <TaskEditor :open="editor.open" :task="editor.task" :defaults="editor.defaults" @close="editor.open = false" @saved="refresh" />
  </div>
</template>
