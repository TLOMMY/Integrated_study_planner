<script setup>
import { computed, onActivated, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import dayjs from 'dayjs'
import EmptyState from '@/components/common/EmptyState.vue'
import TaskItem from '@/components/task/TaskItem.vue'
import TaskEditor from '@/components/task/TaskEditor.vue'
import TaskSearch from '@/components/task/TaskSearch.vue'
import BottomSheet from '@/components/common/BottomSheet.vue'
import HomeWidgets from '@/components/home/HomeWidgets.vue'
import CheckinRule from '@/components/stats/CheckinRule.vue'
import { useHomeStore } from '@/stores/home'
import { useTasksStore } from '@/stores/tasks'
import { useUiStore } from '@/stores/ui'
import { plannerApi } from '@/api/planner'
import { focusRoute } from '@/utils/task'
import { relativeDay, todayStr, weekdayLabel } from '@/utils/dates'
import { subjectInk, subjectOf } from '@/utils/subjects'

defineOptions({ name: 'HomeView' })

const router = useRouter()
const home = useHomeStore()
const tasks = useTasksStore()
const ui = useUiStore()

const tab = ref('today')
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
  if (tab.value === 'today') return [...(showOverdue.value ? tasks.overdue : []), ...tasks.todayOpen]
  return tasks[tab.value]
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

// 筛选清单 / 标签时，计数按筛选后的列表算（服务器返回的 counts 是全部任务的）
const tabs = computed(() => [
  { key: 'today', label: '今天', count: tasks.filter ? tasks.todayOpen.length : tasks.counts.today - tasks.counts.today_done },
  { key: 'future', label: '即将', count: tasks.filter ? null : tasks.counts.future },
  { key: 'inbox', label: '收集箱', count: tasks.filter ? null : tasks.counts.inbox },
  { key: 'completed', label: '已完成', count: null },
])

const s = computed(() => home.summary)
const streak = computed(() => s.value?.streak)
const dateLine = computed(() => {
  const d = dayjs()
  const week = s.value?.teaching_week ? ` · 第 ${s.value.teaching_week} 教学周` : ''
  return `${d.format('M月D日')} ${weekdayLabel(d)}${week}`
})

// "即将"按日期分组（服务器已按日期排好）
const futureGroups = computed(() => {
  const groups = new Map()
  for (const task of tasks.future) {
    const key = task.due_date
    if (!groups.has(key)) groups.set(key, { key, label: relativeDay(task.due_date), items: [] })
    groups.get(key).items.push(task)
  }
  return [...groups.values()]
})

const load = async () => {
  try {
    await Promise.all([home.load({ silent: Boolean(home.summary) }), tasks.loadToday(), tasks.loadGroups().catch(() => {})])
  } catch (error) {
    ui.fail(error, '加载失败')
  }
}

// ---------------------------------------------------------------- 按清单 / 标签筛选
const hasGroups = computed(() => tasks.groups.lists.length > 0 || tasks.groups.tags.length > 0 || Boolean(tasks.filter))
const isFilter = (kind, name) => tasks.filter?.kind === kind && tasks.filter?.name === name
const applyFilter = async (filter) => {
  picked.value = new Set()
  try {
    await tasks.setFilter(isFilter(filter?.kind, filter?.name) ? null : filter)
    if (tab.value !== 'today') await tasks.loadView(tab.value)
  } catch (error) {
    ui.fail(error)
  }
}

const groupSheet = ref(false)
const renaming = ref(null)
const groupSections = computed(() => [
  { kind: 'list', title: '清单', items: tasks.groups.lists },
  { kind: 'tag', title: '标签', items: tasks.groups.tags },
])
const closeGroupSheet = () => {
  groupSheet.value = false
  renaming.value = null
}
const refreshAfterGroups = async () => {
  await tasks.loadGroups()
  await tasks.loadToday()
  if (tab.value !== 'today') await tasks.loadView(tab.value)
  searchBox.value?.refresh()
}
const saveRename = async () => {
  const { kind, old, value } = renaming.value || {}
  const name = (value || '').trim().replace(/^#+/, '')
  if (!name) return ui.toast('名称不能为空', 'warning')
  if (name === old) return (renaming.value = null)
  try {
    const exists = (kind === 'tag' ? tasks.groups.tags : tasks.groups.lists).some((g) => g.name === name)
    if (exists && !(await ui.confirm({ title: '合并？', message: `「${name}」已存在，改名后两者会合并为一个。`, confirmText: '合并' }))) return
    await plannerApi.renameGroup(kind, old, name)
    if (isFilter(kind, old)) tasks.filter = { kind, name }
    ui.success('已改名')
    renaming.value = null
    await refreshAfterGroups()
  } catch (error) {
    ui.fail(error)
  }
}
const removeGroup = async (kind, name) => {
  const label = kind === 'tag' ? '标签' : '清单'
  const ok = await ui.confirm({ title: `删除${label}「${name}」？`, message: `只会去掉任务上的${label}名，任务本身不会被删除。`, confirmText: '删除', danger: true })
  if (!ok) return
  try {
    const result = await plannerApi.removeGroup(kind, name)
    if (isFilter(kind, name)) tasks.filter = null
    ui.success(`已删除，${result.count} 个任务保留`)
    await refreshAfterGroups()
  } catch (error) {
    ui.fail(error)
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
const autoPlan = () => router.push({ path: '/view', query: { autoplan: '1' } })

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
          <h1 class="text-[26px] font-black leading-tight text-ink">任务</h1>
          <p class="mt-0.5 text-xs font-semibold text-ink-mute">{{ dateLine }}</p>
        </div>
        <div class="flex flex-col items-end gap-1">
          <RouterLink to="/statistics" class="flex items-center gap-1 rounded-full px-3 py-1.5" :class="streak?.active_today ? 'bg-flame-light text-flame' : 'bg-surface text-ink-mute shadow-soft'" :aria-label="`连续打卡 ${streak?.current ?? 0} 天，${streak?.active_today ? '今天已打卡' : '今天还没打卡'}`">
            <Icon icon="lucide:flame" width="18" :class="streak?.active_today && 'animate-flicker'" />
            <span class="num text-base font-black">{{ streak?.current ?? 0 }}</span>
          </RouterLink>
          <span class="flex items-center text-[10px] font-bold" :class="streak?.active_today ? 'text-flame' : 'text-ink-mute'">
            {{ streak?.active_today ? '今日已打卡' : '今日未打卡' }}<CheckinRule :streak="streak" />
          </span>
        </div>
      </header>

      <!-- 右栏（桌面） -->
      <aside class="lg:sticky lg:top-0 lg:col-start-2 lg:row-span-2 lg:row-start-2 lg:space-y-3">
      <!-- 断火提醒 -->
      <RouterLink v-if="streak?.at_risk" :to="{ name: 'focus' }" class="mt-4 flex lg:mt-0 items-center gap-3 rounded-2xl border border-flame/30 bg-flame-light px-4 py-3">
        <Icon icon="lucide:flame" width="22" class="shrink-0 text-flame animate-flicker" />
        <p class="flex-1 text-xs font-semibold text-ink-soft">已连续学习 <b class="text-flame">{{ streak.current }}</b> 天，今天还没打卡：专注满 {{ streak.rule?.min_focus_minutes ?? 5 }} 分钟或完成 1 个任务就能保住火苗</p>
        <Icon icon="lucide:chevron-right" width="16" class="text-flame" />
      </RouterLink>

      <!-- 今日课程（只在桌面右栏；手机上日程页有上课通知） -->
      <section v-if="s?.courses?.length" class="card hidden p-4 lg:block">
        <div class="mb-3 flex items-center justify-between">
          <h2 class="section-title">今日课程</h2>
          <RouterLink to="/timetable" class="text-xs font-bold text-primary">课表</RouterLink>
        </div>
        <ul class="space-y-2">
          <li v-for="c in s.courses" :key="c.id" class="flex items-center gap-3 rounded-2xl bg-background px-3 py-2.5" :class="c.status === 'done' && 'opacity-50'">
            <i class="h-1.5 w-1.5 shrink-0 rounded-full" :style="{ background: subjectInk(subjectOf(c)) }" />
            <div class="min-w-0 flex-1">
              <p class="truncate text-sm font-bold text-ink">{{ c.title }}</p>
              <p class="num truncate text-[11px] text-ink-mute">{{ c.start_time }}-{{ c.end_time }}<template v-if="c.location"> · {{ c.location }}</template></p>
            </div>
            <span v-if="c.status === 'ongoing'" class="shrink-0 rounded-full bg-primary-light px-2 py-0.5 text-[10px] font-bold text-primary">正在上</span>
          </li>
        </ul>
      </section>

      <HomeWidgets />

      <RouterLink to="/plans" class="hidden items-center justify-between rounded-3xl bg-surface px-4 py-3.5 shadow-soft lg:flex">
        <span class="flex items-center gap-2 text-sm font-bold text-ink"><Icon icon="lucide:map" width="18" class="text-primary" />学习计划</span>
        <Icon icon="lucide:chevron-right" width="18" class="text-ink-mute" />
      </RouterLink>
      </aside>

      <!-- 左栏（桌面）：任务 -->
      <div class="min-w-0 lg:col-start-1 lg:row-start-2">
      <!-- 搜索任务 + 添加任务 -->
      <div class="mt-5 lg:mt-0">
        <TaskSearch ref="searchBox" @add="openEditor(null, { due_date: tab === 'inbox' ? null : todayStr() })" @open="openEditor" @toggle="toggle" @focus="focus" @searching="(v) => (searching = v)" />
      </div>
      <template v-if="!searching">

      <!-- 视图切换 + 多选 -->
      <div class="mt-5 flex items-center gap-2">
      <nav class="flex flex-1 items-center gap-1 rounded-2xl bg-ink-line/40 p-1" aria-label="任务视图">
        <button
          v-for="item in tabs"
          :key="item.key"
          type="button"
          class="flex flex-1 items-center justify-center gap-1 whitespace-nowrap rounded-xl py-2 text-xs font-bold transition"
          :class="tab === item.key ? 'bg-surface text-ink shadow-soft' : 'text-ink-mute'"
          @click="switchTab(item.key)"
        >
          {{ item.label }}
          <span v-if="item.count" class="num rounded-full px-1.5 text-[10px]" :class="tab === item.key ? 'bg-primary text-on-primary' : 'bg-ink-line text-ink-soft'">{{ item.count }}</span>
        </button>
      </nav>
      <button class="chip shrink-0 py-2" :class="selecting && 'chip-active'" type="button" :aria-pressed="selecting" @click="selecting ? stopSelect() : startSelect()">
        <Icon :icon="selecting ? 'lucide:x' : 'lucide:list-checks'" width="14" />{{ selecting ? '取消' : '多选' }}
      </button>
      </div>

      <!-- 按清单 / 标签筛选：手机上横向滚动 -->
      <div v-if="hasGroups" class="scrollbar-hide -mx-5 mt-3 flex items-center gap-2 overflow-x-auto px-5 lg:mx-0 lg:flex-wrap lg:px-0" role="toolbar" aria-label="按清单或标签筛选">
        <button class="chip shrink-0" :class="!tasks.filter && 'chip-active'" type="button" :aria-pressed="!tasks.filter" @click="applyFilter(null)">全部</button>
        <button
          v-for="g in tasks.groups.lists"
          :key="`l-${g.name}`"
          class="chip shrink-0"
          :class="isFilter('list', g.name) && 'chip-active'"
          type="button"
          :aria-pressed="isFilter('list', g.name)"
          @click="applyFilter({ kind: 'list', name: g.name })"
        >
          <Icon icon="lucide:folder" width="12" />{{ g.name }}<span v-if="g.open" class="num text-[10px] opacity-70">{{ g.open }}</span>
        </button>
        <button
          v-for="g in tasks.groups.tags"
          :key="`t-${g.name}`"
          class="chip shrink-0"
          :class="isFilter('tag', g.name) && 'chip-active'"
          type="button"
          :aria-pressed="isFilter('tag', g.name)"
          @click="applyFilter({ kind: 'tag', name: g.name })"
        >
          #{{ g.name }}<span v-if="g.open" class="num text-[10px] opacity-70">{{ g.open }}</span>
        </button>
        <button class="chip shrink-0 border-dashed" type="button" aria-label="管理清单与标签" @click="groupSheet = true">
          <Icon icon="lucide:settings-2" width="12" />管理
        </button>
      </div>
      <p v-if="tasks.filter" class="mt-2 flex items-center gap-1 px-1 text-[11px] font-semibold text-ink-mute">
        <Icon icon="lucide:list-filter" width="12" />只看{{ tasks.filter.kind === 'tag' ? '标签' : '清单' }}「{{ tasks.filter.name }}」的任务
        <button class="ml-1 font-bold text-primary" type="button" @click="applyFilter(null)">清除</button>
      </p>

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
            :title="tasks.todayDone.length ? '今天的任务全部完成！' : tasks.filter ? `「${tasks.filter.name}」今天没有任务` : '今天还没有任务'"
            :text="tasks.todayDone.length ? `已完成 ${tasks.todayDone.length} 项，可以在「已完成」里查看` : '点「添加任务」写下要做的事，或在日程里点空闲时间安排'"
          >
            <button class="chip chip-active" type="button" @click="autoPlan"><Icon icon="lucide:wand-sparkles" width="13" />一键排今天</button>
          </EmptyState>

        </template>
      </section>

      <!-- 即将：今天以后有日期的 -->
      <section v-else-if="tab === 'future'" class="mt-4 space-y-4">
        <div v-for="group in futureGroups" :key="group.key">
          <h3 class="mb-2 px-1 text-xs font-black text-ink-soft">{{ group.label }} <span class="text-ink-mute">· {{ group.items.length }}</span></h3>
          <div class="space-y-2">
            <TaskItem v-for="task in group.items" :key="task.id" :task="task" :selectable="selecting" :selected="picked.has(task.id)" @select="pick" @toggle="toggle" @open="openEditor" @focus="focus" />
          </div>
        </div>
        <EmptyState v-if="!futureGroups.length" compact icon="lucide:calendar-check" title="没有安排在以后的任务" text="添加任务时写“明天”“周五”就会出现在这里" />
      </section>

      <!-- 收集箱：没有日期的 -->
      <section v-else-if="tab === 'inbox'" class="mt-4 space-y-2">
        <TaskItem v-for="task in tasks.inbox" :key="task.id" :task="task" :selectable="selecting" :selected="picked.has(task.id)" @select="pick" @toggle="toggle" @open="openEditor" @focus="focus" />
        <EmptyState v-if="!tasks.inbox.length" compact icon="lucide:inbox" title="收集箱是空的" text="想到但还没定日期的事放这里，之后再排进日程" />
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
      <div v-if="selecting" class="absolute inset-x-3 bottom-3 z-30 flex items-center gap-2 rounded-3xl bg-inverse px-3 py-2.5 text-inverse-ink shadow-2xl lg:inset-x-auto lg:left-1/2 lg:w-[560px] lg:-translate-x-1/2" role="toolbar" aria-label="批量操作">
        <button class="flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-2xl px-2 py-1.5 text-xs font-bold hover:bg-inverse-ink/10" type="button" @click="pickAll">
          <Icon :icon="allPicked ? 'lucide:square-check' : 'lucide:square'" width="16" />全选
        </button>
        <span class="num min-w-0 flex-1 whitespace-nowrap text-xs text-inverse-ink/70"><span class="hidden sm:inline">已选 </span>{{ picked.size }} 项</span>
        <button class="flex shrink-0 items-center gap-1 whitespace-nowrap rounded-2xl bg-inverse-ink/15 px-2.5 py-2 text-xs font-bold hover:bg-inverse-ink/25 disabled:opacity-40 sm:px-3" type="button" :disabled="!picked.size" @click="movePicked({ shift_days: 1 }, '后一天')">
          <Icon icon="lucide:arrow-right" width="14" />顺延
        </button>
        <button class="flex shrink-0 items-center gap-1 whitespace-nowrap rounded-2xl bg-inverse-ink/15 px-2.5 py-2 text-xs font-bold hover:bg-inverse-ink/25 disabled:opacity-40 sm:px-3" type="button" :disabled="!picked.size" @click="openMove">
          <Icon icon="lucide:calendar" width="14" />改日期
        </button>
        <button class="flex shrink-0 items-center gap-1 whitespace-nowrap rounded-2xl bg-danger px-2.5 py-2 text-xs font-bold text-on-danger disabled:opacity-40 sm:px-3" type="button" :disabled="!picked.size" @click="removePicked">
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

    <!-- 管理清单与标签：改名（同名时合并）/ 删除（任务保留） -->
    <BottomSheet :open="groupSheet" title="清单与标签" subtitle="改名时与已有名称相同会自动合并；删除只去掉名字，任务保留" @close="closeGroupSheet">
      <div class="space-y-4 pb-2">
        <div v-for="section in groupSections" :key="section.kind">
          <h3 class="mb-2 px-1 text-xs font-black text-ink-soft">{{ section.title }}</h3>
          <p v-if="!section.items.length" class="rounded-2xl bg-background px-4 py-3 text-xs text-ink-mute">还没有{{ section.title }}，在任务编辑里填写即可创建</p>
          <ul v-else class="space-y-1.5">
            <li v-for="g in section.items" :key="g.name" class="flex items-center gap-2 rounded-2xl bg-background px-3 py-2">
              <Icon :icon="section.kind === 'list' ? 'lucide:folder' : 'lucide:tag'" width="15" class="shrink-0" :class="section.kind === 'list' ? 'text-ink-soft' : 'text-primary'" />
              <template v-if="renaming && renaming.kind === section.kind && renaming.old === g.name">
                <input v-model="renaming.value" class="field min-w-0 flex-1 py-1.5" :maxlength="section.kind === 'tag' ? 12 : 20" aria-label="新名称" @keydown.enter.prevent="saveRename" @keydown.esc="renaming = null" />
                <button class="chip chip-active shrink-0" type="button" @click="saveRename">保存</button>
              </template>
              <template v-else>
                <span class="min-w-0 flex-1 truncate text-sm font-semibold text-ink">{{ g.name }}</span>
                <span class="num shrink-0 text-[11px] text-ink-mute">{{ g.open }} 未完成 / {{ g.total }}</span>
                <button class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-ink-mute hover:bg-surface hover:text-primary" type="button" :aria-label="`改名：${g.name}`" @click="renaming = { kind: section.kind, old: g.name, value: g.name }">
                  <Icon icon="lucide:pencil" width="14" />
                </button>
                <button class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-ink-mute hover:bg-surface hover:text-danger" type="button" :aria-label="`删除：${g.name}`" @click="removeGroup(section.kind, g.name)">
                  <Icon icon="lucide:trash-2" width="14" />
                </button>
              </template>
            </li>
          </ul>
        </div>
      </div>
    </BottomSheet>

    <TaskEditor :open="editor.open" :task="editor.task" :defaults="editor.defaults" @close="editor.open = false" @saved="onSaved" />
  </div>
</template>
