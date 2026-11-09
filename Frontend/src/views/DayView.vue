<script setup>
/**
 * 日程：只按时间看一天（或一周 / 一月）。
 * 课程、定了时刻的任务和空闲段排在一根珠点轴上；没定时刻、没日期的任务只在任务页出现，这里不重复。
 * 头部：日期 + 连续打卡、教学周 · 节数 · 空闲 + 日/周/月、星期条、上课通知、近期考试。
 * 一键排今天（中心按钮面板或 ?autoplan=1 进来）：建议块直接画在轴上，确认后才写入，可撤销。
 * 点空闲段：半屏快建，只填名字和时长。
 */
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import dayjs from 'dayjs'
import { Icon } from '@iconify/vue'
import DayTimeline from '@/components/day/DayTimeline.vue'
import WeekView from '@/components/day/WeekView.vue'
import MonthView from '@/components/day/MonthView.vue'
import TaskEditor from '@/components/task/TaskEditor.vue'
import QuickSlotSheet from '@/components/day/QuickSlotSheet.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import { dayApi, taskApi } from '@/api'
import { useTasksStore } from '@/stores/tasks'
import { useTimetableStore } from '@/stores/timetable'
import { useGameStore } from '@/stores/game'
import { useHomeStore } from '@/stores/home'
import { useUiStore } from '@/stores/ui'
import { compactMinutes, mondayOf, todayStr, weekdayLabel } from '@/utils/dates'

const route = useRoute()
const router = useRouter()
const tasks = useTasksStore()
const timetable = useTimetableStore()
const game = useGameStore()
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

const weekLabel = computed(() => {
  const monday = mondayOf(selected.value)
  return `${monday.format('M月D日')} – ${monday.add(6, 'day').format('M月D日')}`
})
const isToday = computed(() =>
  mode.value === 'month' ? dayjs(month.value).isSame(dayjs(), 'month') : mode.value === 'week' ? mondayOf(selected.value).isSame(mondayOf(todayStr()), 'day') : selected.value === todayStr(),
)
/** 第二行：第 10 周 · 2 节课 · 空闲 2h30m */
const metaLine = computed(() => {
  if (mode.value === 'week') return weekLabel.value
  if (mode.value === 'month') return dayjs(month.value).format('YYYY 年 M 月')
  const d = day.value
  if (!d || d.date !== selected.value) return weekdayLabel(selected.value)
  const parts = []
  if (d.teaching_week) parts.push(`第 ${d.teaching_week} 周`)
  parts.push(d.summary.courses ? `${d.summary.courses} 节课` : '没有课')
  if (d.summary.free_minutes && selected.value >= todayStr()) parts.push(`空闲 ${compactMinutes(d.summary.free_minutes)}`)
  return parts.join(' · ')
})

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
// 换了日期 / 视图：收起建议块和快建
watch([selected, mode], () => {
  if (plan.value && !plan.value.loading && (mode.value !== 'day' || plan.value.items[0]?.date !== selected.value)) plan.value = null
  quick.value = null
})
// 任何地方改了任务（中心按钮新建、任务页勾选、拖拽改期……）都重新拉一次
watch(() => tasks.version, refresh)
onMounted(() => {
  refresh()
  if (!timetable.examsLoaded) timetable.loadExams().catch(() => {})
  if (!game.streak) useHomeStore().refresh()
  handleQuery()
})
watch(() => route.query.autoplan, handleQuery)

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

// 日视图的星期条：左右滑动切换上一周 / 下一周（保留选中的星期几）
let swipe = null
const onStripStart = (event) => {
  const t = event.touches?.[0]
  swipe = t ? { x: t.clientX, y: t.clientY } : null
}
const onStripEnd = (event) => {
  const t = event.changedTouches?.[0]
  if (!swipe || !t) return
  const dx = t.clientX - swipe.x
  const dy = t.clientY - swipe.y
  swipe = null
  if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy) * 1.5) shiftWeek(dx < 0 ? 1 : -1)
}
// ---------------------------------------------------------------- 上课通知（只看今天）：正在上 / 下一节 / 今天没课 / 都上完了
const nowMin = ref(dayjs().hour() * 60 + dayjs().minute())
const clock = setInterval(() => (nowMin.value = dayjs().hour() * 60 + dayjs().minute()), 30000)
const toMin = (hm) => {
  const [h, m] = String(hm).split(':').map(Number)
  return h * 60 + m
}
const where = (c) => (c.location ? ` · ${c.location}` : '')
const classNotice = computed(() => {
  const d = day.value
  if (mode.value !== 'day' || selected.value !== todayStr() || !d || d.date !== selected.value) return null
  const courses = d.items.filter((i) => i.type === 'course')
  if (!courses.length) return { icon: 'lucide:coffee', title: '今天没课', sub: d.summary.free_minutes ? `空闲 ${compactMinutes(d.summary.free_minutes)}，可以安排点什么` : '' }
  const now = nowMin.value
  const index = courses.findIndex((c) => toMin(c.end_time) > now)
  if (index === -1) return { icon: 'lucide:circle-check', title: '今天的课都上完了', sub: `共 ${courses.length} 节` }
  const c = courses[index]
  const next = courses[index + 1]
  if (toMin(c.start_time) <= now) {
    return { icon: 'lucide:graduation-cap', live: true, title: `${c.title}${where(c)}`, sub: `${c.start_time}-${c.end_time}${next ? ` · 下一节 ${next.start_time} ${next.title}${where(next)}` : ' · 今天最后一节'}` }
  }
  const mins = toMin(c.start_time) - now
  return { icon: 'lucide:graduation-cap', title: `下一节：${c.title}${where(c)}`, sub: `${c.start_time}-${c.end_time}${mins <= 90 ? ` · ${mins} 分钟后` : ''}` }
})

// ---------------------------------------------------------------- 近期考试（30 天内，最多两条）
const exams = computed(() => timetable.exams.filter((e) => e.days_left <= 30))
const examText = (e) => `${e.subject || e.title}`
const examDays = (e) => (e.days_left === 0 ? '今天' : e.days_left === 1 ? '明天' : `${e.days_left}`)

// ---------------------------------------------------------------- 连续打卡
const streak = computed(() => game.streak)

// ---------------------------------------------------------------- 任务
const toggle = (task) => tasks.toggle(task)
const openTask = (task) => (editor.value = { open: true, task, defaults: {} })

// ---------------------------------------------------------------- 点空闲段：半屏快建
const quick = ref(null) // { slot, title, minutes }
const picking = computed(() => {
  const q = quick.value
  if (!q) return null
  return { start_time: q.slot.start_time, end_time: addMinutes(q.slot.start_time, q.minutes), title: q.title }
})
const addMinutes = (hm, minutes) => {
  const total = toMin(hm) + minutes
  return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`
}
const planFree = async (slot) => {
  if (plan.value) return
  quick.value = { slot, title: '', minutes: Math.min(slot.minutes, 45) }
  // 把这段空闲滚到半屏上方，看得到"正在安排"
  await nextTick()
  const target = scroller.value?.querySelector(`[data-free="${slot.start_time}"]`)
  if (target) scrollToEl(target)
}
const scroller = ref(null)
/** 把元素滚到可视区上方（留出头部和半屏的位置）。 */
const scrollToEl = (el, offset = 140) => {
  const box = scroller.value
  if (!box || !el) return
  const top = box.scrollTop + el.getBoundingClientRect().top - box.getBoundingClientRect().top - offset
  box.scrollTo({ top: Math.max(0, top), behavior: 'smooth' })
}
const quickMore = (payload) => {
  quick.value = null
  editor.value = { open: true, task: null, defaults: payload }
}
// ---------------------------------------------------------------- 一键排今天：本地规则，建议块画在轴上，确认后写入
const plan = ref(null) // { items: [...{ picked }], skipped, loading, saving }
const planDate = computed(() => (selected.value < todayStr() ? todayStr() : selected.value))
const picked = computed(() => (plan.value?.items || []).filter((i) => i.picked))
const pickedMinutes = computed(() => picked.value.reduce((sum, i) => sum + i.minutes, 0))
const ghosts = computed(() => plan.value?.items || [])

const startPlan = async () => {
  quick.value = null
  mode.value = 'day'
  selected.value = planDate.value
  plan.value = { items: [], skipped: [], loading: true, saving: false }
  try {
    const data = await dayApi.autoPlan(selected.value)
    if (!data.items.length) {
      plan.value = null
      const why = data.skipped[0]?.reason
      ui.toast(data.skipped.length ? `排不进去：${why}` : '没有需要安排的待办，今天可以自由安排', 'info', 3200)
      return
    }
    // 课后回顾默认不勾选
    plan.value = { items: data.items.map((i) => ({ ...i, picked: !i.optional })), skipped: data.skipped, loading: false, saving: false }
    await nextTick()
    const first = scroller.value?.querySelector('[role="checkbox"]')
    if (first) scrollToEl(first, 220)
  } catch (error) {
    plan.value = null
    ui.fail(error)
  }
}
const toggleGhost = (item) => (item.picked = !item.picked)
const cancelPlan = () => (plan.value = null)

const commitPlan = async () => {
  if (!plan.value || !picked.value.length || plan.value.saving) return
  plan.value.saving = true
  const items = picked.value.map(({ key, kind, task_id: taskId, title, subject, date, start_time: start, minutes, priority }) => ({
    key, kind, task_id: taskId ?? null, title, subject: subject || null, date, start_time: start, minutes, priority,
  }))
  try {
    const result = await dayApi.commitAutoPlan(items)
    plan.value = null
    const done = result.results.filter((r) => r.ok)
    await tasks.afterChange()
    if (done.length) {
      showUndo(`已加入 ${done.length} 项${result.fail_count ? `，${result.fail_count} 项没排进去` : ''}`, async () => {
        for (const r of done) {
          if (r.created) await taskApi.remove(r.id)
          else await taskApi.update(r.id, r.before)
        }
        await tasks.afterChange()
      })
    } else {
      ui.toast(result.results[0]?.reason || '没有加入任何任务', 'warning', 3200)
    }
  } catch (error) {
    if (plan.value) plan.value.saving = false
    ui.fail(error)
  }
}

// ---------------------------------------------------------------- 撤销条（一键排程、拖拽改期）
const undo = ref(null)
let undoTimer = null
function showUndo(message, revert) {
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
  } catch (error) {
    current.busy = false
    ui.fail(error)
  }
}
onBeforeUnmount(() => {
  clearTimeout(undoTimer)
  clearInterval(clock)
})

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
    refresh()
  }
}

/** 日视图时间轴：上下拖动改开始时间（冲突时提示，但仍然保存）。 */
const moveToTime = async ({ task, start_time: startTime, conflict }) => {
  try {
    const revert = await tasks.reschedule(task, { due_date: task.due_date, start_time: startTime })
    if (revert) showUndo(`已改到 ${startTime} 开始${conflict.length ? `，与「${conflict[0]}」时间重叠` : ''}`, revert)
  } catch (error) {
    ui.fail(error)
  }
}

/** 中心按钮"一键排今天"跳过来时带 ?autoplan=1。 */
function handleQuery() {
  if (!route.query.autoplan) return
  router.replace({ query: {} })
  startPlan()
}
</script>

<template>
  <div class="relative flex h-full flex-col">
    <div ref="scroller" class="scrollbar-hide flex-1 overflow-y-auto pb-28 lg:pb-10" :class="plan && 'pb-48 lg:pb-40'">
      <!-- 状态栏下方的一条玻璃：内容滚上去时从它下面经过 -->
      <div class="glass-bar sticky top-0 z-20 h-[var(--safe-top)] border-0 lg:hidden" aria-hidden="true" />
      <header class="px-5 pt-4 lg:px-10 lg:pt-7">
        <div class="mx-auto grid max-w-[720px] gap-2.5" :class="mode !== 'day' && 'lg:max-w-[1180px]'">
          <div class="flex items-center justify-between gap-3">
            <h1 class="text-[28px] font-black leading-tight text-ink">
              <template v-if="mode === 'day'">{{ dayjs(selected).format('M月D日') }}<small class="ml-1.5 text-lg font-bold">{{ weekdayLabel(selected) }}</small></template>
              <template v-else>日程</template>
            </h1>
            <div class="flex items-center gap-2">
              <button v-if="!isToday" class="chip" type="button" @click="goToday">回到{{ mode === 'month' ? '本月' : mode === 'week' ? '本周' : '今天' }}</button>
              <button v-if="mode === 'day' && selected >= todayStr() && !plan" class="chip hidden lg:inline-flex" type="button" @click="startPlan">
                <Icon icon="lucide:wand-sparkles" width="14" class="text-primary" />一键排{{ selected === todayStr() ? '今天' : '这天' }}
              </button>
              <RouterLink
                to="/statistics"
                class="flex h-[34px] items-center gap-1 rounded-full bg-primary-light pl-2.5 pr-3"
                :aria-label="`连续打卡 ${streak?.current ?? 0} 天，${streak?.active_today ? '今天已打卡' : '今天还没打卡'}`"
              >
                <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" :class="!streak?.active_today && 'opacity-45 grayscale'">
                  <path fill="rgb(var(--c-flame))" d="M12 2c1.6 3.6 6.5 6.3 6.5 12.4A6.5 6.5 0 0 1 5.5 14.4c0-3 1.5-5 3.5-6.4 0 2.5 1.2 4 2.6 4.3C10.9 8.5 11.4 5 12 2z" />
                </svg>
                <span class="num text-[17px] font-bold text-ink">{{ streak?.current ?? 0 }}</span>
                <small class="text-[11px] font-bold text-ink-mute">天</small>
              </RouterLink>
            </div>
          </div>

          <div class="flex items-center justify-between gap-2.5">
            <span class="num min-w-0 truncate text-xs text-ink-mute">{{ metaLine }}</span>
            <div class="flex shrink-0 gap-0.5 rounded-full bg-ink-line p-[3px]">
              <button
                v-for="m in MODES"
                :key="m.k"
                type="button"
                class="rounded-full px-3 py-0.5 text-xs font-bold transition"
                :class="mode === m.k ? 'bg-surface text-ink shadow-soft' : 'text-ink-mute hover:text-ink-soft'"
                :aria-pressed="mode === m.k"
                @click="setMode(m.k)"
              >
                {{ m.l }}
              </button>
            </div>
          </div>

          <!-- 星期条：左右滑动 / 箭头切换上一周、下一周 -->
          <div v-if="mode === 'day'" class="-mx-1.5 grid grid-cols-[24px_repeat(7,1fr)_24px] items-center" @touchstart.passive="onStripStart" @touchend="onStripEnd">
            <button class="flex h-8 items-center justify-center text-ink-mute hover:text-ink" type="button" aria-label="上一周" title="上一周" @click="shiftWeek(-1)"><Icon icon="lucide:chevron-left" width="16" /></button>
            <button
              v-for="d in strip"
              :key="d.key"
              type="button"
              class="grid justify-items-center gap-0.5 rounded-[14px] py-1.5 transition"
              :class="d.key === selected ? 'bg-primary text-on-primary' : 'hover:bg-surface/60'"
              :aria-pressed="d.key === selected"
              :aria-label="`${dayjs(d.key).format('M月D日')} 周${d.label}`"
              @click="selected = d.key"
            >
              <span class="text-[10px] font-medium" :class="d.key === selected ? 'text-on-primary' : 'text-ink-mute'">{{ d.label }}</span>
              <span class="num text-[15px] font-bold" :class="d.key === selected ? 'text-on-primary' : d.today ? 'text-primary' : 'text-ink'">{{ d.day }}</span>
            </button>
            <button class="flex h-8 items-center justify-center text-ink-mute hover:text-ink" type="button" aria-label="下一周" title="下一周" @click="shiftWeek(1)"><Icon icon="lucide:chevron-right" width="16" /></button>
          </div>
          <div v-else-if="mode === 'week'" class="flex items-center justify-between">
            <button class="chip" type="button" aria-label="上一周" @click="shiftWeek(-1)"><Icon icon="lucide:chevron-left" width="14" />上一周</button>
            <button class="chip" type="button" aria-label="下一周" @click="shiftWeek(1)">下一周<Icon icon="lucide:chevron-right" width="14" /></button>
          </div>

          <!-- 上课通知 -->
          <RouterLink v-if="classNotice" to="/timetable" class="card flex items-center gap-2.5 rounded-2xl px-3 py-2.5 shadow-none">
            <span class="flex h-[34px] w-[34px] shrink-0 items-center justify-center rounded-full bg-course text-course-icon"><Icon :icon="classNotice.icon" width="18" /></span>
            <span class="grid min-w-0 flex-1 gap-px">
              <b class="truncate text-sm font-bold text-ink"><span v-if="classNotice.live" class="mr-1.5 rounded-full bg-primary-light px-1.5 align-[1px] text-[10px] font-bold text-primary">正在上</span>{{ classNotice.title }}</b>
              <small v-if="classNotice.sub" class="num truncate text-[11px] text-ink-mute">{{ classNotice.sub }}</small>
            </span>
            <Icon icon="lucide:chevron-right" width="18" class="shrink-0 text-ink-mute" />
          </RouterLink>

          <!-- 近期考试 -->
          <div v-if="mode === 'day' && exams.length" class="flex items-center gap-2">
            <RouterLink
              v-for="e in exams.slice(0, 2)"
              :key="e.id"
              :to="{ name: 'timetable', query: { exams: '1' } }"
              class="inline-flex h-7 max-w-[46%] items-baseline gap-1 rounded-full border px-3 pt-[5px] text-xs"
              :class="e.days_left <= 7 ? 'border-transparent bg-primary-light text-primary-dark' : 'border-ink-line bg-surface text-ink'"
            >
              <span class="truncate">{{ examText(e) }}</span><b class="num shrink-0 text-[13px] font-bold">{{ examDays(e) }}</b><span v-if="e.days_left > 1" class="shrink-0">天</span>
            </RouterLink>
            <RouterLink v-if="exams.length > 2" :to="{ name: 'timetable', query: { exams: '1' } }" class="inline-flex h-7 items-center rounded-full border border-ink-line bg-surface px-2.5 text-xs text-ink-mute">+{{ exams.length - 2 }}</RouterLink>
          </div>
        </div>
      </header>

      <div class="px-5 pt-4 lg:px-10 lg:pt-6">
        <div class="mx-auto max-w-[720px]" :class="mode !== 'day' && 'lg:max-w-[1180px]'">
          <template v-if="mode === 'day'">
            <div v-if="loading" class="space-y-3"><div v-for="i in 4" :key="i" class="skeleton h-14" /></div>
            <template v-else-if="day">
              <DayTimeline
                v-if="day.items.length || ghosts.length"
                :day="day"
                :ghosts="ghosts"
                :picking="picking"
                @toggle="toggle"
                @open="openTask"
                @plan-free="planFree"
                @reschedule="moveToTime"
                @ghost="toggleGhost"
              />
              <EmptyState v-else compact icon="lucide:calendar-heart" title="这一天没有课程和定时任务" text="没定时刻的任务在「任务」页" />
            </template>
          </template>

          <WeekView v-else-if="mode === 'week'" :selected="selected" :courses="timetable.courses" :meta="timetable.meta" :tasks="rangeTasks" @pick="pick" @move="moveToDate" />
          <MonthView v-else :selected="selected" :month="month" :courses="timetable.courses" :meta="timetable.meta" :tasks="rangeTasks" @pick="pick" @month="(m) => (month = m)" @move="moveToDate" />
        </div>
      </div>
    </div>

    <!-- 一键排今天：底部确认条 -->
    <Transition enter-active-class="transition duration-200" enter-from-class="translate-y-4 opacity-0" leave-active-class="transition duration-150" leave-to-class="translate-y-4 opacity-0">
      <div v-if="plan" class="glass material absolute inset-x-3 bottom-3 z-30 grid gap-2.5 rounded-3xl bg-surface p-3.5 shadow-lift lg:inset-x-auto lg:left-1/2 lg:w-[480px] lg:-translate-x-1/2" role="region" aria-label="一键排今天">
        <div v-if="plan.loading" class="flex items-center gap-2 py-2 text-sm font-bold text-ink-soft"><Icon icon="lucide:loader-circle" width="16" class="animate-spin" />正在按空闲时段排…</div>
        <template v-else>
          <div class="grid gap-0.5">
            <b class="text-[15px] font-black text-ink">加入 <span class="num">{{ picked.length }}</span> 项 · <span class="num">{{ compactMinutes(pickedMinutes) }}</span></b>
            <small class="text-xs leading-relaxed text-ink-mute">
              按优先级填进现在以后的空闲：逾期 → 今天要做 → 考前复习 → 收集箱。<template v-if="plan.items.some((i) => i.optional && !i.picked)">课后回顾未勾选。</template>
              <template v-if="plan.skipped.length">另有 {{ plan.skipped.length }} 项排不下（{{ plan.skipped[0].reason }}）。</template>
            </small>
          </div>
          <div class="grid grid-cols-[1fr_2fr] gap-2.5">
            <button class="btn-ghost rounded-full" type="button" :disabled="plan.saving" @click="cancelPlan">取消</button>
            <button class="btn-primary rounded-full" type="button" :disabled="!picked.length || plan.saving" @click="commitPlan">
              <Icon v-if="plan.saving" icon="lucide:loader-circle" width="16" class="animate-spin" />全部加入
            </button>
          </div>
        </template>
      </div>
    </Transition>

    <!-- 撤销条（一键排程、拖拽改期后） -->
    <Transition enter-active-class="transition duration-200" enter-from-class="translate-y-4 opacity-0" leave-active-class="transition duration-150" leave-to-class="translate-y-4 opacity-0">
      <div v-if="undo && !plan" class="absolute inset-x-3 bottom-3 z-30 flex items-center gap-3 rounded-2xl bg-inverse px-4 py-3 text-inverse-ink shadow-2xl lg:inset-x-auto lg:left-1/2 lg:w-[460px] lg:-translate-x-1/2" role="status">
        <Icon icon="lucide:circle-check" width="18" class="shrink-0 text-inverse-accent" />
        <span class="min-w-0 flex-1 text-sm font-semibold">{{ undo.message }}</span>
        <button class="flex shrink-0 items-center gap-1 rounded-xl bg-inverse-ink/15 px-3 py-1.5 text-xs font-bold hover:bg-inverse-ink/25 disabled:opacity-50" type="button" :disabled="undo.busy" @click="runUndo">
          <Icon icon="lucide:undo-2" width="14" />撤销
        </button>
      </div>
    </Transition>

    <QuickSlotSheet
      :open="Boolean(quick)"
      :slot-info="quick?.slot || null"
      :date="selected"
      :courses="day?.items.filter((i) => i.type === 'course') || []"
      @update="(v) => quick && Object.assign(quick, v)"
      @more="quickMore"
      @close="quick = null"
    />
    <TaskEditor :open="editor.open" :task="editor.task" :defaults="editor.defaults" @close="editor.open = false" />
  </div>
</template>
