<script setup>
import { computed, onActivated, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import dayjs from 'dayjs'
import ProgressRing from '@/components/common/ProgressRing.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import TaskItem from '@/components/task/TaskItem.vue'
import TaskEditor from '@/components/task/TaskEditor.vue'
import TaskSearch from '@/components/task/TaskSearch.vue'
import BottomSheet from '@/components/common/BottomSheet.vue'
import { useHomeStore } from '@/stores/home'
import { useTasksStore } from '@/stores/tasks'
import { useUiStore } from '@/stores/ui'
import { focusRoute } from '@/utils/task'
import { relativeDay, todayStr, weekdayLabel } from '@/utils/dates'

defineOptions({ name: 'HomeView' })

const router = useRouter()
const home = useHomeStore()
const tasks = useTasksStore()
const ui = useUiStore()

const tab = ref('today')
const showDone = ref(true)
const showOverdue = ref(true)
const editor = ref({ open: false, task: null, defaults: {} })
const searchBox = ref(null)
const searching = ref(false)

// ---------------------------------------------------------------- 多选：批量删除 / 改日期
const selecting = ref(false)
const picked = ref(new Set())
const moveSheet = ref(false)
const moveDate = ref('')
const visibleTasks = computed(() => {
  if (tab.value === 'today') return [...(showOverdue.value ? tasks.overdue : []), ...tasks.todayOpen, ...(showDone.value ? tasks.todayDone : [])]
  if (tab.value === 'upcoming') return tasks.upcoming
  return tasks.completed
})
const allPicked = computed(() => visibleTasks.value.length > 0 && visibleTasks.value.every((t) => picked.value.has(t.id)))
const startSelect = () => {
  selecting.value = true
  picked.value = new Set()
}
const stopSelect = () => {
  selecting.value = false
  picked.value = new Set()
}
const pick = (task) => {
  const next = new Set(picked.value)
  next.has(task.id) ? next.delete(task.id) : next.add(task.id)
  picked.value = next
}
const pickAll = () => (picked.value = allPicked.value ? new Set() : new Set(visibleTasks.value.map((t) => t.id)))
const afterBatch = async () => {
  stopSelect()
  moveSheet.value = false
  if (tab.value !== 'today') await tasks.loadView(tab.value).catch(() => {})
}
const removePicked = async () => {
  const ids = [...picked.value]
  const ok = await ui.confirm({ title: `删除 ${ids.length} 个任务？`, message: '删除后无法恢复，相关的专注记录会保留。', confirmText: '删除', danger: true })
  if (!ok) return
  await tasks.batch({ ids, action: 'delete' }, `已删除 ${ids.length} 个任务`).then(afterBatch).catch(ui.fail)
}
const movePicked = async (payload, label) => {
  const ids = [...picked.value]
  await tasks.batch({ ids, action: 'move', ...payload }, `已把 ${ids.length} 个任务移到${label}`).then(afterBatch).catch(ui.fail)
}
const openMove = () => {
  moveDate.value = dayjs().add(1, 'day').format('YYYY-MM-DD')
  moveSheet.value = true
}
const moveOptions = computed(() => [
  { label: '今天', date: todayStr() },
  { label: '明天', date: dayjs().add(1, 'day').format('YYYY-MM-DD') },
  { label: '后天', date: dayjs().add(2, 'day').format('YYYY-MM-DD') },
  { label: '下周一', date: dayjs().add(((8 - dayjs().day()) % 7) || 7, 'day').format('YYYY-MM-DD') },
])

const tabs = computed(() => [
  { key: 'today', label: '今天', count: tasks.counts.today - tasks.counts.today_done },
  { key: 'upcoming', label: '即将', count: tasks.counts.upcoming },
  { key: 'completed', label: '已完成', count: null },
])

const s = computed(() => home.summary)
const goal = computed(() => s.value?.daily_goal)
const streak = computed(() => s.value?.streak)
const dateLine = computed(() => {
  const d = dayjs()
  const week = s.value?.teaching_week ? ` · 第 ${s.value.teaching_week} 教学周` : ''
  return `${d.format('M月D日')} ${weekdayLabel(d)}${week}`
})

const nextCourseText = computed(() => {
  const c = s.value?.next_course
  if (!c) return s.value?.courses?.length ? '今天的课都上完啦' : '今天没有课'
  if (c.status === 'ongoing') return `正在上：${c.title}`
  const mins = s.value.minutes_until_next
  const when = mins != null && mins <= 90 ? `${mins} 分钟后` : c.start_time
  return `${when} · ${c.title}`
})

const upcomingGroups = computed(() => {
  const groups = new Map()
  for (const task of tasks.upcoming) {
    const key = task.due_date || 'none'
    if (!groups.has(key)) groups.set(key, { key, label: task.due_date ? relativeDay(task.due_date) : '无日期', items: [] })
    groups.get(key).items.push(task)
  }
  return [...groups.values()]
})

const load = async () => {
  try {
    await Promise.all([home.load({ silent: Boolean(home.summary) }), tasks.loadToday()])
  } catch (error) {
    ui.fail(error, '加载失败')
  }
}

const switchTab = async (key) => {
  tab.value = key
  picked.value = new Set()
  if (key !== 'today') await tasks.loadView(key).catch((error) => ui.fail(error))
}

const openEditor = (task = null, defaults = {}) => {
  editor.value = { open: true, task, defaults }
}
const onSaved = () => {
  if (tab.value !== 'today') tasks.loadView(tab.value).catch(() => {})
  searchBox.value?.refresh()
}
const toggle = async (task) => {
  await tasks.toggle(task)
  if (tab.value !== 'today') tasks.loadView(tab.value).catch(() => {})
  searchBox.value?.refresh()
}
const focus = (task) => router.push(focusRoute(task))
const askAi = () => router.push({ name: 'ai', query: { q: '帮我把今天的空闲时间安排成复习计划' } })

onMounted(load)
onActivated(() => tasks.loaded && load())
</script>

<template>
  <div class="flex h-full flex-col">
    <div class="scrollbar-hide flex-1 overflow-y-auto px-5 pb-24 pt-[calc(var(--safe-top)+20px)] lg:px-10 lg:pb-10 lg:pt-8">
     <!-- 手机：单列；桌面：左栏任务（快速添加 + 列表），右栏概览 / 今日课程 / 计划入口 -->
     <div class="desk-page flex flex-col lg:grid lg:grid-cols-[minmax(0,1fr)_340px] lg:items-start lg:gap-x-8">
      <!-- 头部 -->
      <header class="flex items-start justify-between lg:col-span-2 lg:mb-6">
        <div>
          <p class="text-xs font-semibold text-ink-mute">{{ dateLine }}</p>
          <h1 class="mt-1 text-[22px] font-black text-ink">
            {{ s?.greeting || '你好' }}，{{ s?.user?.display_name || '同学' }}
          </h1>
        </div>
        <RouterLink to="/statistics" class="flex items-center gap-1 rounded-2xl px-3 py-2" :class="streak?.active_today ? 'bg-flame-light text-flame' : 'bg-surface text-ink-mute shadow-soft'" aria-label="连续打卡">
          <Icon icon="lucide:flame" width="20" :class="streak?.active_today && 'animate-flicker'" />
          <span class="num text-lg font-black">{{ streak?.current ?? 0 }}</span>
        </RouterLink>
      </header>

      <!-- 右栏（桌面） -->
      <aside class="lg:sticky lg:top-0 lg:col-start-2 lg:row-span-2 lg:row-start-2 lg:space-y-3">
      <!-- 今日概览 -->
      <section v-if="home.loading && !s" class="skeleton mt-5 h-[148px] lg:mt-0" />
      <section v-else-if="s" class="mt-5 overflow-hidden rounded-[28px] bg-gradient-to-br from-primary via-[#5B6CF9] to-xp p-5 text-white shadow-lift lg:mt-0">
        <div class="flex items-center gap-4">
          <ProgressRing :value="goal?.progress || 0" :size="76" :stroke="8" color="#fff">
            <div class="text-center leading-none">
              <div class="num text-xl font-black">{{ goal?.done_minutes || 0 }}</div>
              <div class="mt-0.5 text-[9px] opacity-80">/{{ goal?.goal_minutes }} 分</div>
            </div>
          </ProgressRing>
          <div class="min-w-0 flex-1">
            <p class="text-xs opacity-80">{{ goal?.reached ? '今日目标已达成 🎉' : `还差 ${goal.goal_minutes - goal.done_minutes} 分钟达成今日目标` }}</p>
            <div class="mt-2 flex items-center gap-2">
              <span class="rounded-lg bg-white/20 px-2 py-0.5 text-xs font-black">Lv.{{ s.level.level }}</span>
              <div class="h-1.5 flex-1 overflow-hidden rounded-full bg-white/20">
                <div class="h-full rounded-full bg-white transition-all duration-700" :style="{ width: `${s.level.progress}%` }" />
              </div>
              <span class="num text-[10px] opacity-80">{{ s.level.xp_in_level }}/{{ s.level.xp_for_next }}</span>
            </div>
          </div>
        </div>
        <RouterLink to="/view" class="mt-4 flex items-center gap-2 rounded-2xl bg-white/15 px-3 py-2.5 text-sm">
          <Icon icon="lucide:graduation-cap" width="18" class="shrink-0" />
          <span class="min-w-0 flex-1 truncate font-semibold">{{ nextCourseText }}</span>
          <span v-if="s.next_course?.location" class="shrink-0 text-xs opacity-80">{{ s.next_course.location }}</span>
          <Icon icon="lucide:chevron-right" width="16" class="shrink-0 opacity-70" />
        </RouterLink>
      </section>

      <!-- 断火提醒 -->
      <RouterLink v-if="streak?.at_risk" :to="{ name: 'focus' }" class="mt-3 flex items-center gap-3 rounded-2xl border border-flame/30 bg-flame-light px-4 py-3">
        <Icon icon="lucide:flame" width="22" class="shrink-0 text-flame animate-flicker" />
        <p class="flex-1 text-xs font-semibold text-ink-soft">已连续学习 <b class="text-flame">{{ streak.current }}</b> 天，今天还没打卡，专注一会儿保住火苗吧</p>
        <Icon icon="lucide:chevron-right" width="16" class="text-flame" />
      </RouterLink>

      <!-- 今日课程（桌面右栏；手机上由概览卡片里的"下一节课"代替） -->
      <section v-if="s?.courses?.length" class="card hidden p-4 lg:block">
        <div class="mb-3 flex items-center justify-between">
          <h2 class="section-title">今日课程</h2>
          <RouterLink to="/timetable" class="text-xs font-bold text-primary">课表</RouterLink>
        </div>
        <ul class="space-y-2">
          <li v-for="c in s.courses" :key="c.id" class="flex items-center gap-3 rounded-2xl bg-background px-3 py-2.5" :class="c.status === 'done' && 'opacity-50'">
            <i class="h-9 w-1 shrink-0 rounded-full" :style="{ background: c.color }" />
            <div class="min-w-0 flex-1">
              <p class="truncate text-sm font-bold text-ink">{{ c.title }}</p>
              <p class="num truncate text-[11px] text-ink-mute">{{ c.start_time }}-{{ c.end_time }}<template v-if="c.location"> · {{ c.location }}</template></p>
            </div>
            <span v-if="c.status === 'ongoing'" class="shrink-0 rounded-full bg-success-light px-2 py-0.5 text-[10px] font-black text-success">上课中</span>
          </li>
        </ul>
      </section>

      <RouterLink to="/plans" class="hidden items-center justify-between rounded-3xl bg-surface px-4 py-3.5 shadow-soft lg:flex">
        <span class="flex items-center gap-2 text-sm font-bold text-ink"><Icon icon="lucide:map" width="18" class="text-primary" />学习计划</span>
        <Icon icon="lucide:chevron-right" width="18" class="text-ink-mute" />
      </RouterLink>
      </aside>

      <!-- 左栏（桌面）：任务 -->
      <div class="min-w-0 lg:col-start-1 lg:row-start-2">
      <!-- 搜索任务 + 添加任务 -->
      <div class="mt-5 lg:mt-0">
        <TaskSearch ref="searchBox" @add="openEditor(null, { due_date: tab === 'today' ? todayStr() : null })" @open="openEditor" @toggle="toggle" @focus="focus" @searching="(v) => (searching = v)" />
      </div>
      <template v-if="!searching">

      <!-- 视图切换 + 多选 -->
      <div class="mt-5 flex items-center gap-2">
      <nav class="flex flex-1 items-center gap-1 rounded-2xl bg-ink-line/40 p-1" aria-label="任务视图">
        <button
          v-for="item in tabs"
          :key="item.key"
          type="button"
          class="flex flex-1 items-center justify-center gap-1 rounded-xl py-2 text-xs font-bold transition"
          :class="tab === item.key ? 'bg-surface text-ink shadow-soft' : 'text-ink-mute'"
          @click="switchTab(item.key)"
        >
          {{ item.label }}
          <span v-if="item.count" class="num rounded-full px-1.5 text-[10px]" :class="tab === item.key ? 'bg-primary text-white' : 'bg-ink-line text-ink-soft'">{{ item.count }}</span>
        </button>
      </nav>
      <button class="chip shrink-0 py-2" :class="selecting && 'chip-active'" type="button" :aria-pressed="selecting" @click="selecting ? stopSelect() : startSelect()">
        <Icon :icon="selecting ? 'lucide:x' : 'lucide:list-checks'" width="14" />{{ selecting ? '取消' : '多选' }}
      </button>
      </div>

      <!-- 今天 -->
      <section v-if="tab === 'today'" class="mt-4 space-y-2.5">
        <div v-if="tasks.loading && !tasks.loaded" class="space-y-2.5">
          <div v-for="i in 3" :key="i" class="skeleton h-[62px]" />
        </div>
        <template v-else>
          <div v-if="tasks.overdue.length" class="rounded-3xl bg-danger-light/70 p-2.5">
            <div class="flex items-center justify-between px-1.5 pb-2">
              <button class="flex items-center gap-1 text-xs font-black text-danger" type="button" @click="showOverdue = !showOverdue">
                <Icon :icon="showOverdue ? 'lucide:chevron-down' : 'lucide:chevron-right'" width="14" />已逾期 {{ tasks.overdue.length }}
              </button>
              <button class="text-xs font-bold text-danger" type="button" @click="tasks.moveOverdueToToday().catch(ui.fail)">全部移到今天</button>
            </div>
            <div v-if="showOverdue" class="space-y-2">
              <TaskItem v-for="task in tasks.overdue" :key="task.id" :task="task" :selectable="selecting" :selected="picked.has(task.id)" @select="pick" @toggle="toggle" @open="openEditor" @focus="focus" />
            </div>
          </div>

          <TaskItem v-for="task in tasks.todayOpen" :key="task.id" :task="task" :selectable="selecting" :selected="picked.has(task.id)" @select="pick" @toggle="toggle" @open="openEditor" @focus="focus" />

          <EmptyState
            v-if="!tasks.todayOpen.length && !tasks.overdue.length"
            compact
            :icon="tasks.todayDone.length ? 'lucide:party-popper' : 'lucide:sun'"
            :title="tasks.todayDone.length ? '今天的任务全部完成！' : '今天还没有任务'"
            :text="tasks.todayDone.length ? '去专注一会儿冲击每日目标，或让 AI 帮你安排复习' : '在上方输入框快速添加，或让 AI 根据课表空闲帮你排'"
          >
            <button class="chip chip-active" type="button" @click="askAi"><Icon icon="lucide:sparkles" width="13" />AI 安排今天</button>
          </EmptyState>

          <div v-if="tasks.todayDone.length" class="pt-2">
            <button class="flex items-center gap-1 px-1 pb-2 text-xs font-bold text-ink-mute" type="button" @click="showDone = !showDone">
              <Icon :icon="showDone ? 'lucide:chevron-down' : 'lucide:chevron-right'" width="14" />已完成 {{ tasks.todayDone.length }}
            </button>
            <div v-if="showDone" class="space-y-2">
              <TaskItem v-for="task in tasks.todayDone" :key="task.id" :task="task" :selectable="selecting" :selected="picked.has(task.id)" @select="pick" @toggle="toggle" @open="openEditor" />
            </div>
          </div>

          <button
            v-if="s && s.free_minutes >= 60 && tasks.todayOpen.length < 3"
            class="mt-2 flex w-full items-center gap-3 rounded-3xl border border-primary/15 bg-primary-light p-4 text-left"
            type="button"
            @click="askAi"
          >
            <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-primary text-white"><Icon icon="lucide:sparkles" width="20" /></div>
            <div class="min-w-0 flex-1">
              <p class="text-sm font-black text-ink">今天还有 {{ Math.floor(s.free_minutes / 60) }} 小时空闲</p>
              <p class="mt-0.5 text-xs text-ink-soft">让 AI 避开课程，帮你排一份复习计划</p>
            </div>
            <Icon icon="lucide:chevron-right" width="18" class="text-primary" />
          </button>
        </template>
      </section>

      <!-- 即将 -->
      <section v-else-if="tab === 'upcoming'" class="mt-4 space-y-4">
        <div v-for="group in upcomingGroups" :key="group.key">
          <h3 class="mb-2 px-1 text-xs font-black text-ink-soft">{{ group.label }} <span class="text-ink-mute">· {{ group.items.length }}</span></h3>
          <div class="space-y-2">
            <TaskItem v-for="task in group.items" :key="task.id" :task="task" :selectable="selecting" :selected="picked.has(task.id)" @select="pick" @toggle="toggle" @open="openEditor" @focus="focus" />
          </div>
        </div>
        <EmptyState v-if="!upcomingGroups.length" compact icon="lucide:calendar-check" title="没有待办的未来任务" text="可以在快速添加里写“明天”“周五”来安排" />
      </section>

      <!-- 已完成 -->
      <section v-else class="mt-4 space-y-2">
        <TaskItem v-for="task in tasks.completed" :key="task.id" :task="task" :selectable="selecting" :selected="picked.has(task.id)" @select="pick" show-date @toggle="toggle" @open="openEditor" />
        <EmptyState v-if="!tasks.completed.length" compact icon="lucide:list-checks" title="还没有完成的任务" />
      </section>
      </template>

      <RouterLink to="/plans" class="mt-6 flex items-center justify-between rounded-3xl bg-surface px-4 py-3.5 shadow-soft lg:hidden">
        <span class="flex items-center gap-2 text-sm font-bold text-ink"><Icon icon="lucide:map" width="18" class="text-primary" />学习计划</span>
        <Icon icon="lucide:chevron-right" width="18" class="text-ink-mute" />
      </RouterLink>
      </div>
     </div>
    </div>

    <Transition enter-active-class="transition duration-200" enter-from-class="translate-y-4 opacity-0" leave-active-class="transition duration-150" leave-to-class="translate-y-4 opacity-0">
      <div v-if="selecting" class="absolute inset-x-3 bottom-3 z-30 flex items-center gap-2 rounded-3xl bg-ink px-3 py-2.5 text-white shadow-2xl lg:inset-x-auto lg:left-1/2 lg:w-[560px] lg:-translate-x-1/2" role="toolbar" aria-label="批量操作">
        <button class="flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-2xl px-2 py-1.5 text-xs font-bold hover:bg-white/10" type="button" @click="pickAll">
          <Icon :icon="allPicked ? 'lucide:square-check' : 'lucide:square'" width="16" />全选
        </button>
        <span class="num min-w-0 flex-1 whitespace-nowrap text-xs text-white/70"><span class="hidden sm:inline">已选 </span>{{ picked.size }} 项</span>
        <button class="flex shrink-0 items-center gap-1 whitespace-nowrap rounded-2xl bg-white/15 px-2.5 py-2 text-xs font-bold hover:bg-white/25 disabled:opacity-40 sm:px-3" type="button" :disabled="!picked.size" @click="movePicked({ shift_days: 1 }, '后一天')">
          <Icon icon="lucide:arrow-right" width="14" />顺延
        </button>
        <button class="flex shrink-0 items-center gap-1 whitespace-nowrap rounded-2xl bg-white/15 px-2.5 py-2 text-xs font-bold hover:bg-white/25 disabled:opacity-40 sm:px-3" type="button" :disabled="!picked.size" @click="openMove">
          <Icon icon="lucide:calendar" width="14" />改日期
        </button>
        <button class="flex shrink-0 items-center gap-1 whitespace-nowrap rounded-2xl bg-danger px-2.5 py-2 text-xs font-bold disabled:opacity-40 sm:px-3" type="button" :disabled="!picked.size" @click="removePicked">
          <Icon icon="lucide:trash-2" width="14" />删除
        </button>
      </div>
    </Transition>

    <BottomSheet :open="moveSheet" :title="`移动 ${picked.size} 个任务`" subtitle="保留原来的时刻和时长，只改日期" @close="moveSheet = false">
      <div class="space-y-4 pb-2">
        <div class="grid grid-cols-4 gap-2">
          <button v-for="o in moveOptions" :key="o.label" type="button" class="chip justify-center" @click="movePicked({ due_date: o.date }, o.label)">{{ o.label }}</button>
        </div>
        <label class="block"><span class="label">选择任意日期</span><input v-model="moveDate" class="field" type="date" /></label>
      </div>
      <template #footer>
        <button class="btn-primary w-full" type="button" :disabled="!moveDate" @click="movePicked({ due_date: moveDate }, dayjs(moveDate).format('M月D日'))">移到 {{ moveDate ? dayjs(moveDate).format('M月D日') : '…' }}</button>
      </template>
    </BottomSheet>

    <TaskEditor :open="editor.open" :task="editor.task" :defaults="editor.defaults" @close="editor.open = false" @saved="onSaved" />
  </div>
</template>
