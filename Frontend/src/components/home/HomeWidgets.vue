<script setup>
/** 首页右栏 / 手机端概览下方的小组件：考试倒计时、断签保护提示、周报入口 */
import { computed, onActivated, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import dayjs from 'dayjs'
import { Icon } from '@iconify/vue'
import { aiRoute, examDaysText } from '@/components/timetable/examAi'
import { useGameStore } from '@/stores/game'
import { useTimetableStore } from '@/stores/timetable'
import { mondayOf } from '@/utils/dates'

const router = useRouter()
const timetable = useTimetableStore()
const game = useGameStore()

const exams = computed(() => timetable.exams.slice(0, 3))
const isMonday = dayjs().day() === 1
const lastWeek = mondayOf(dayjs()).subtract(7, 'day').format('YYYY-MM-DD')
const thisWeek = mondayOf(dayjs()).format('YYYY-MM-DD')
// 最近两天内用过保护卡（昨天或前天被补上）时提示一次
const protectedRecently = computed(() => {
  const day = game.streak?.last_protected
  return Boolean(day) && dayjs().diff(dayjs(day), 'day') <= 2
})

const load = () => timetable.loadExams().catch(() => {})
onMounted(load)
onActivated(load)
</script>

<template>
  <div class="space-y-3">
    <!-- 断签保护 -->
    <RouterLink v-if="protectedRecently" to="/statistics" class="mt-3 flex items-center gap-3 rounded-2xl border border-primary/20 bg-primary-light px-4 py-3">
      <Icon icon="lucide:shield-check" width="22" class="shrink-0 text-primary" />
      <p class="flex-1 text-xs font-semibold text-ink-soft">
        已用保护卡保住 <b class="text-primary">{{ game.streak.current }}</b> 天的连续记录<template v-if="game.streak.at_risk">，今天学一会儿就能续上</template>
        <span class="text-ink-mute">（剩 {{ game.streak.freezes }} 张）</span>
      </p>
      <Icon icon="lucide:chevron-right" width="16" class="text-primary" />
    </RouterLink>

    <!-- 考试倒计时 -->
    <section class="card mt-3 p-4">
      <div class="mb-3 flex items-center justify-between">
        <h2 class="section-title flex items-center gap-1.5"><Icon icon="lucide:alarm-clock" width="16" class="text-danger" />考试倒计时</h2>
        <RouterLink :to="{ name: 'timetable', query: { exams: exams.length ? '1' : 'new' } }" class="text-xs font-bold text-primary">{{ exams.length ? '全部' : '添加' }}</RouterLink>
      </div>
      <p v-if="!exams.length" class="rounded-2xl bg-background px-3 py-3 text-xs text-ink-mute">记下考试日期，临近时提醒你，并可让 AI 排复习计划</p>
      <ul v-else class="space-y-2">
        <li v-for="exam in exams" :key="exam.id" class="flex items-center gap-3 rounded-2xl px-3 py-2.5" :class="exam.urgent ? 'bg-danger-light' : 'bg-background'">
          <div class="flex h-11 w-11 shrink-0 flex-col items-center justify-center rounded-xl" :class="exam.urgent ? 'bg-danger text-on-danger' : 'bg-surface text-primary'">
            <template v-if="exam.days_left > 1">
              <span class="num text-base font-black leading-none">{{ exam.days_left }}</span>
              <span class="text-[9px] font-bold">天</span>
            </template>
            <span v-else class="text-xs font-black">{{ examDaysText(exam) }}</span>
          </div>
          <div class="min-w-0 flex-1">
            <p class="truncate text-sm font-bold" :class="exam.urgent ? 'text-danger' : 'text-ink'">{{ exam.title }}</p>
            <p class="num truncate text-[11px] text-ink-mute">{{ dayjs(exam.exam_date).format('M月D日') }} {{ exam.weekday }}<template v-if="exam.start_time"> {{ exam.start_time }}</template><template v-if="exam.location"> · {{ exam.location }}</template></p>
          </div>
          <button class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-xp-light text-xp" type="button" :aria-label="`让 AI 为《${exam.title}》排复习计划`" title="让 AI 排复习计划" @click="router.push(aiRoute(exam))">
            <Icon icon="lucide:sparkles" width="16" />
          </button>
        </li>
      </ul>
    </section>

    <!-- 周报入口：周一突出显示上周报告 -->
    <RouterLink
      v-if="isMonday"
      :to="{ name: 'report', query: { week: lastWeek } }"
      class="flex items-center gap-3 rounded-3xl bg-gradient-to-r from-primary to-xp px-4 py-3.5 text-on-primary shadow-lift"
    >
      <Icon icon="lucide:file-chart-column" width="22" class="shrink-0" />
      <span class="flex-1">
        <span class="block text-sm font-black">上周报告已生成</span>
        <span class="block text-[11px] opacity-80">看看上周的专注、完成任务与 AI 复盘</span>
      </span>
      <Icon icon="lucide:chevron-right" width="18" />
    </RouterLink>
    <RouterLink v-else :to="{ name: 'report', query: { week: thisWeek } }" class="flex items-center justify-between rounded-3xl bg-surface px-4 py-3.5 shadow-soft">
      <span class="flex items-center gap-2 text-sm font-bold text-ink"><Icon icon="lucide:file-chart-column" width="18" class="text-primary" />本周学习报告</span>
      <Icon icon="lucide:chevron-right" width="18" class="text-ink-mute" />
    </RouterLink>
  </div>
</template>
