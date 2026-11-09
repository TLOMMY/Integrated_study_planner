<script setup>
/**
 * 手机底部导航：日程 / 课表 / AI（中心按钮）/ 任务 / 成长。
 * 中心按钮不直接跳页，而是打开面板：一键排今天 → AI 对话入口 → 任务 · 课程 · 考试 · 专注。
 */
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import BottomSheet from '@/components/common/BottomSheet.vue'
import TaskEditor from '@/components/task/TaskEditor.vue'
import CourseEditor from '@/components/timetable/CourseEditor.vue'
import ExamSheet from '@/components/timetable/ExamSheet.vue'
import { useGameStore } from '@/stores/game'
import { useAiStore } from '@/stores/ai'
import { useTimetableStore } from '@/stores/timetable'
import { todayStr } from '@/utils/dates'

// 根节点不止一个（导航 + 面板），外面传的 class（如 lg:hidden）只给导航
defineOptions({ inheritAttrs: false })

const route = useRoute()
const router = useRouter()
const game = useGameStore()
const ai = useAiStore()
const timetable = useTimetableStore()

const tabs = [
  { name: 'view', label: '日程', icon: 'lucide:calendar-clock', to: '/view' },
  { name: 'timetable', label: '课表', icon: 'lucide:calendar-days', to: '/timetable' },
  { name: 'ai', label: 'AI', icon: 'lucide:sparkles', center: true },
  { name: 'home', label: '任务', icon: 'lucide:circle-check-big', to: '/today-task', also: ['plans'] },
  { name: 'statistics', label: '成长', icon: 'lucide:trophy', to: '/statistics', also: ['profile', 'settings'] },
]

const isActive = (tab) => route.name === tab.name || tab.also?.includes(route.name)
const streakAtRisk = computed(() => game.streak?.at_risk)

// ---------------------------------------------------------------- 中心面板
const panel = ref(false)
const sheet = ref('') // task | course | exam
const lastChat = computed(() => ai.conversations[0]?.title || '')

const openPanel = () => {
  panel.value = true
  // 只取会话列表给"继续上次"用，失败不影响面板
  if (!ai.conversations.length) ai.loadConversations().catch(() => {})
}
const go = (to) => {
  panel.value = false
  router.push(to)
}
const openSheet = async (name) => {
  panel.value = false
  if (name === 'course') await timetable.ensure().catch(() => {})
  sheet.value = name
}
// 从中心面板建的任务：建完回到日程
const onTaskSaved = (task) => {
  if (task && route.name !== 'view') router.push('/view')
}
</script>

<template>
  <nav v-bind="$attrs" class="glass-bar relative z-40 shrink-0 border-t border-ink-line/70 bg-surface/95 pb-[var(--safe-bottom)] backdrop-blur" aria-label="主导航">
    <div class="grid h-16 grid-cols-5">
      <template v-for="tab in tabs" :key="tab.name">
        <button
          v-if="tab.center"
          type="button"
          class="relative flex flex-col items-center justify-center gap-1 text-[10px] font-bold text-ink"
          :aria-expanded="panel"
          aria-haspopup="dialog"
          data-tour="nav-ai"
          @click="openPanel"
        >
          <span class="-mt-7 flex h-14 w-14 items-center justify-center rounded-full bg-primary text-on-primary shadow-lift ring-[5px] ring-surface">
            <Icon :icon="tab.icon" width="24" />
          </span>
          <span>{{ tab.label }}</span>
        </button>
        <RouterLink
          v-else
          :to="tab.to"
          class="relative flex flex-col items-center justify-center gap-1 text-[10px] font-bold transition"
          :class="isActive(tab) ? 'text-primary' : 'text-ink-mute'"
          :aria-current="isActive(tab) ? 'page' : undefined"
          :data-tour="tab.name === 'statistics' ? 'nav-growth' : undefined"
        >
          <Icon :icon="tab.icon" width="22" />
          <span>{{ tab.label }}</span>
          <span v-if="tab.name === 'statistics' && streakAtRisk" class="absolute right-[22%] top-2.5 h-2 w-2 rounded-full bg-flame ring-2 ring-surface" />
        </RouterLink>
      </template>
    </div>
  </nav>

  <BottomSheet :open="panel" title="" @close="panel = false">
    <div class="grid gap-3.5 pb-1 pt-2">
      <button class="grid grid-cols-[1fr_auto] items-center gap-3 rounded-[22px] bg-primary p-4 text-left text-on-primary" type="button" @click="go('/view?autoplan=1')">
        <span>
          <span class="mb-1.5 inline-block whitespace-nowrap rounded-full bg-primary-dark px-2 py-px text-[10px] font-bold">本地计算 · 不用 AI 次数</span>
          <b class="block text-lg font-black leading-snug">一键排今天</b>
          <small class="mt-0.5 block text-xs opacity-90">把待办和考前复习排进今天的空闲时间</small>
        </span>
        <span class="inline-flex h-9 items-center gap-1 rounded-full bg-surface px-4 text-[13px] font-black text-primary">预览<Icon icon="lucide:chevron-right" width="16" /></span>
      </button>

      <button class="flex items-center gap-3 rounded-[20px] border border-ink-line bg-background px-3.5 py-3 text-left" type="button" @click="go('/ai')">
        <span class="flex h-[38px] w-[38px] shrink-0 items-center justify-center rounded-full bg-primary-light text-primary"><Icon icon="lucide:sparkles" width="18" /></span>
        <span class="grid min-w-0 flex-1 gap-px">
          <b class="text-[15px] font-black text-ink">AI 对话</b>
          <small class="truncate text-xs text-ink-mute">{{ lastChat ? `继续上次：${lastChat}` : '说说这周要学什么，帮你排进日程' }}</small>
        </span>
        <Icon icon="lucide:chevron-right" width="18" class="text-ink-mute" />
      </button>

      <div class="grid grid-cols-4 gap-2">
        <button
          v-for="q in [
            { key: 'task', label: '任务', icon: 'lucide:circle-check-big' },
            { key: 'course', label: '课程', icon: 'lucide:book-open' },
            { key: 'exam', label: '考试', icon: 'lucide:alarm-clock' },
          ]"
          :key="q.key"
          class="grid justify-items-center gap-1.5 rounded-[18px] bg-background pb-2.5 pt-3 text-xs font-bold text-ink"
          type="button"
          @click="openSheet(q.key)"
        >
          <Icon :icon="q.icon" width="20" class="text-primary" />{{ q.label }}
        </button>
        <button class="grid justify-items-center gap-1.5 rounded-[18px] bg-background pb-2.5 pt-3 text-xs font-bold text-ink" type="button" @click="go('/focus-timer')">
          <Icon icon="lucide:timer" width="20" class="text-primary" />专注
        </button>
      </div>
    </div>
  </BottomSheet>

  <TaskEditor :open="sheet === 'task'" :task="null" :defaults="{ due_date: todayStr() }" @close="sheet = ''" @saved="onTaskSaved" />
  <CourseEditor :open="sheet === 'course'" :course="null" @close="sheet = ''" />
  <ExamSheet :open="sheet === 'exam'" initial="new" @close="sheet = ''" />
</template>
