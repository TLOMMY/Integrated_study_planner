<script setup>
import { computed, defineAsyncComponent, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import dayjs from 'dayjs'
import { Icon } from '@iconify/vue'
import MarkdownText from '@/components/ai/MarkdownText.vue'
import { growthApi } from '@/api/growth'
import { themeColor } from '@/composables/useTheme'
import { formatMinutes, mondayOf } from '@/utils/dates'

/** 每周学习报告：统计（/study/weekly-report）+ AI 复盘（/ai/review/weekly，代理 F） */
const EChart = defineAsyncComponent(() => import('@/components/stats/EChart.vue'))
const route = useRoute()
const router = useRouter()

const thisMonday = mondayOf(dayjs())
const week = ref(mondayOf(route.query.week || dayjs()))
const report = ref(null)
const loading = ref(false)
const error = ref('')
const ai = ref(null)
const aiState = ref('idle') // idle | loading | ready | unavailable
const aiError = ref('')

const isCurrent = computed(() => week.value.isSame(thisMonday, 'day'))
const title = computed(() => {
  if (isCurrent.value) return '本周'
  if (week.value.isSame(thisMonday.subtract(7, 'day'), 'day')) return '上周'
  return `${week.value.format('M月D日')}这周`
})
const range = computed(() => `${week.value.format('M/D')} – ${week.value.add(6, 'day').format('M/D')}`)

const load = async () => {
  loading.value = true
  error.value = ''
  try {
    report.value = await growthApi.weeklyReport(week.value.format('YYYY-MM-DD'))
  } catch (e) {
    error.value = e.message
    report.value = null
  } finally {
    loading.value = false
  }
  loadAi(false)
}

const loadAi = async (refresh = false) => {
  ai.value = null
  aiError.value = ''
  if (!report.value?.has_data) {
    aiState.value = 'idle'
    return
  }
  aiState.value = 'loading'
  const asked = week.value.format('YYYY-MM-DD')
  try {
    const data = await growthApi.aiReview(asked, refresh)
    if (asked !== week.value.format('YYYY-MM-DD')) return
    ai.value = data
    aiState.value = data?.review_markdown ? 'ready' : 'unavailable'
  } catch (e) {
    if (asked !== week.value.format('YYYY-MM-DD')) return
    aiState.value = 'unavailable'
    aiError.value = e.status === 404 || e.status === 405 ? '' : e.message
  }
}

watch(
  week,
  (value) => {
    router.replace({ query: { week: value.format('YYYY-MM-DD') } })
    load()
  },
  { immediate: true },
)
const go = (offset) => {
  const next = week.value.add(offset * 7, 'day')
  if (next.isAfter(thisMonday, 'day')) return
  week.value = next
}

const change = (value, suffix = '%') => {
  if (value === null || value === undefined) return null
  return { up: value >= 0, text: `${value >= 0 ? '+' : ''}${value}${suffix}` }
}
const cards = computed(() => {
  const r = report.value
  if (!r) return []
  return [
    { key: 'focus', label: '专注时长', value: formatMinutes(r.focus.total_minutes), icon: 'lucide:hourglass', tone: 'text-primary', change: change(r.compare.focus_minutes) },
    { key: 'tasks', label: '完成任务', value: `${r.tasks.completed} 个`, icon: 'lucide:list-checks', tone: 'text-success', change: change(r.compare.tasks_completed) },
    { key: 'days', label: '学习天数', value: `${r.streak.active_days} 天`, icon: 'lucide:flame', tone: 'text-flame', change: change(r.compare.active_days, ' 天') },
    { key: 'xp', label: '获得 XP', value: r.xp.total, icon: 'lucide:sparkles', tone: 'text-xp', change: change(r.compare.xp) },
  ]
})

const PIE = ['chart-1', 'chart-2', 'chart-3', 'chart-4', 'chart-5', 'chart-6', 'chart-7']
// Tailwind 需要完整类名才会生成
const DOTS = ['bg-chart-1', 'bg-chart-2', 'bg-chart-3', 'bg-chart-4', 'bg-chart-5', 'bg-chart-6', 'bg-chart-7']
const tooltip = () => ({ backgroundColor: themeColor('surface'), borderColor: themeColor('ink-line'), textStyle: { color: themeColor('ink') } })
const dailyOption = computed(() => ({
  grid: { top: 22, left: 4, right: 4, bottom: 4, containLabel: true },
  tooltip: { trigger: 'axis', formatter: (p) => `${p[0].name}<br/>专注 ${p[0].value} 分钟<br/>完成任务 ${report.value.daily[p[0].dataIndex].tasks} 个`, ...tooltip() },
  xAxis: { type: 'category', data: report.value.daily.map((d) => d.label.replace('周', '')), axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: themeColor('chart-axis'), fontSize: 11 } },
  yAxis: { type: 'value', splitLine: { lineStyle: { color: themeColor('chart-grid') } }, axisLabel: { color: themeColor('chart-faint'), fontSize: 10 } },
  series: [
    {
      type: 'bar',
      barWidth: 18,
      data: report.value.daily.map((d) => ({
        value: d.minutes,
        itemStyle: { borderRadius: [8, 8, 2, 2], color: d.future ? themeColor('ink-line') : d.active ? themeColor('primary') : themeColor('primary-soft') },
      })),
      label: { show: true, position: 'top', fontSize: 10, color: themeColor('chart-label'), formatter: (p) => (p.value ? p.value : '') },
    },
  ],
}))
const subjectOption = computed(() => ({
  tooltip: { trigger: 'item', formatter: (p) => `${p.name}<br/>${p.value} 分钟（${p.percent}%）`, ...tooltip() },
  series: [
    {
      type: 'pie',
      radius: ['55%', '82%'],
      itemStyle: { borderColor: themeColor('surface'), borderWidth: 3, borderRadius: 6 },
      label: { show: false },
      data: report.value.subjects.map((s, i) => ({ name: s.subject, value: s.minutes, itemStyle: { color: themeColor(PIE[i % PIE.length]) } })),
    },
  ],
}))
</script>

<template>
  <div class="scrollbar-hide h-full overflow-y-auto px-5 pb-24 pt-[calc(var(--safe-top)+16px)] lg:px-10 lg:pb-10 lg:pt-8">
    <div class="desk-page">
      <header class="flex items-center gap-3">
        <button class="icon-btn lg:hidden" type="button" aria-label="返回" @click="router.back()"><Icon icon="lucide:chevron-left" width="20" /></button>
        <div class="min-w-0 flex-1">
          <h1 class="text-[22px] font-black text-ink">{{ title }}学习报告</h1>
          <p class="num text-xs font-semibold text-ink-mute">{{ range }}{{ report && !report.is_complete ? ' · 本周进行中，数据随学随更新' : '' }}</p>
        </div>
        <div class="flex gap-1.5">
          <button class="icon-btn" type="button" aria-label="上一周" @click="go(-1)"><Icon icon="lucide:chevron-left" width="18" /></button>
          <button class="icon-btn" type="button" aria-label="下一周" :disabled="isCurrent" :class="isCurrent && 'opacity-40'" @click="go(1)"><Icon icon="lucide:chevron-right" width="18" /></button>
        </div>
      </header>

      <div v-if="loading && !report" class="mt-4 space-y-3"><div class="skeleton h-28" /><div class="skeleton h-52" /><div class="skeleton h-40" /></div>
      <div v-else-if="error" class="mt-4 rounded-3xl bg-danger-light p-4 text-sm font-semibold text-danger">{{ error }}</div>

      <div v-else-if="report" class="mt-4 lg:grid lg:grid-cols-2 lg:gap-4">
        <!-- 核心数字 -->
        <section class="grid grid-cols-2 gap-2.5 lg:col-span-2 lg:grid-cols-4">
          <div v-for="c in cards" :key="c.key" class="card p-3.5">
            <p class="flex items-center gap-1.5 text-[11px] font-bold text-ink-mute"><Icon :icon="c.icon" width="14" :class="c.tone" />{{ c.label }}</p>
            <p class="num mt-1.5 text-xl font-black text-ink">{{ c.value }}</p>
            <p v-if="c.change" class="mt-0.5 flex items-center gap-0.5 text-[11px] font-bold" :class="c.change.up ? 'text-success' : 'text-danger'">
              <Icon :icon="c.change.up ? 'lucide:trending-up' : 'lucide:trending-down'" width="12" />较上周 {{ c.change.text }}
            </p>
            <p v-else class="mt-0.5 text-[11px] text-ink-mute">上周无数据</p>
          </div>
        </section>

        <!-- AI 复盘 -->
        <section class="card mt-3 p-4 lg:col-span-2 lg:mt-0">
          <div class="mb-2 flex items-center justify-between">
            <h2 class="section-title flex items-center gap-1.5"><Icon icon="lucide:sparkles" width="16" class="text-xp" />AI 复盘</h2>
            <button v-if="aiState === 'unavailable' || aiState === 'ready'" class="text-xs font-bold text-primary" type="button" @click="loadAi(aiState === 'ready')">{{ aiState === 'ready' ? '重新生成' : '重试' }}</button>
          </div>
          <div v-if="aiState === 'loading'" class="space-y-2"><div class="skeleton h-4 w-3/4" /><div class="skeleton h-4" /><div class="skeleton h-4 w-5/6" /></div>
          <template v-else-if="aiState === 'ready'">
            <MarkdownText :text="ai.review_markdown" />
            <ul v-if="ai.suggestions?.length" class="mt-3 space-y-1.5">
              <li v-for="(s, i) in ai.suggestions" :key="i" class="flex items-start gap-2 rounded-2xl bg-xp-light px-3 py-2 text-xs font-semibold text-ink">
                <Icon icon="lucide:lightbulb" width="14" class="mt-0.5 shrink-0 text-xp" />{{ typeof s === 'string' ? s : s.text || s.title }}
              </li>
            </ul>
            <p v-if="ai.model || ai.provider" class="mt-2 text-[10px] text-ink-mute">由 {{ ai.model || ai.provider }} 生成{{ ai.generated_at ? ` · ${dayjs(ai.generated_at).format('M/D HH:mm')}` : '' }}</p>
          </template>
          <p v-else-if="aiState === 'unavailable'" class="rounded-2xl bg-background px-3 py-3 text-xs text-ink-mute">AI 复盘暂不可用{{ aiError ? `：${aiError}` : '' }}，下方的统计不受影响。</p>
          <p v-else class="rounded-2xl bg-background px-3 py-3 text-xs text-ink-mute">这周还没有学习记录，学一会儿再来看 AI 复盘吧。</p>
        </section>

        <!-- 每日分布 -->
        <section class="card mt-3 p-4 lg:mt-0">
          <div class="flex items-center justify-between">
            <h2 class="section-title">每日专注</h2>
            <span class="text-xs text-ink-mute">日均 {{ formatMinutes(report.focus.daily_average) }}</span>
          </div>
          <p v-if="report.focus.best_day" class="mt-0.5 text-xs text-ink-mute">最拼的一天：{{ report.focus.best_day.label }} {{ formatMinutes(report.focus.best_day.minutes) }}</p>
          <EChart :option="dailyOption" :height="180" class="mt-2" />
          <div class="mt-2 grid grid-cols-3 gap-2 text-center text-[11px]">
            <div class="rounded-2xl bg-background py-2"><p class="num text-base font-black text-ink">{{ report.focus.sessions }}</p><p class="text-ink-mute">专注次数</p></div>
            <div class="rounded-2xl bg-background py-2"><p class="num text-base font-black text-ink">{{ report.focus.pomodoros }}</p><p class="text-ink-mute">完整番茄</p></div>
            <div class="rounded-2xl bg-background py-2">
              <p class="num text-base font-black text-ink">{{ report.tasks.completion_rate === null ? '—' : `${report.tasks.completion_rate}%` }}</p>
              <p class="text-ink-mute">计划完成率</p>
            </div>
          </div>
        </section>

        <!-- 科目分布 -->
        <section class="card mt-3 p-4 lg:mt-0">
          <h2 class="section-title">科目分布</h2>
          <p v-if="!report.subjects.length" class="mt-3 rounded-2xl bg-background px-3 py-6 text-center text-xs text-ink-mute">这周还没有专注记录</p>
          <div v-else class="mt-2 flex items-center gap-3">
            <EChart :option="subjectOption" :height="140" class="!w-[140px] shrink-0" />
            <ul class="min-w-0 flex-1 space-y-1.5">
              <li v-for="(s, i) in report.subjects" :key="s.subject" class="flex items-center gap-2 text-xs">
                <i class="h-2.5 w-2.5 shrink-0 rounded-full" :class="DOTS[i % DOTS.length]" />
                <span class="min-w-0 flex-1 truncate font-semibold text-ink">{{ s.subject }}</span>
                <span class="num text-ink-mute">{{ s.percent }}%</span>
              </li>
            </ul>
          </div>
        </section>

        <!-- 连续与 XP -->
        <section class="card mt-3 p-4 lg:mt-0">
          <h2 class="section-title">连续与 XP</h2>
          <div class="mt-3 flex items-center gap-3 rounded-2xl bg-flame-light px-3 py-2.5">
            <Icon icon="lucide:flame" width="22" class="text-flame" />
            <p class="flex-1 text-xs font-semibold text-ink-soft">{{ report.is_complete ? '周末时' : '目前' }}连续学习 <b class="num text-flame">{{ report.streak.current }}</b> 天 · 最长 {{ report.streak.longest }} 天</p>
          </div>
          <p v-if="report.streak.protected_days.length" class="mt-2 flex items-center gap-1.5 text-xs text-primary">
            <Icon icon="lucide:shield-check" width="14" />这周用了 {{ report.streak.protected_days.length }} 张保护卡保住连续记录
          </p>
          <ul v-if="report.xp.breakdown.length" class="mt-3 space-y-1.5">
            <li v-for="x in report.xp.breakdown" :key="x.reason" class="flex items-center gap-2 text-xs">
              <span class="w-16 shrink-0 font-semibold text-ink-soft">{{ x.label }}</span>
              <span class="h-2 flex-1 overflow-hidden rounded-full bg-background"><span class="block h-full rounded-full bg-xp" :style="{ width: `${Math.max(4, (x.xp / report.xp.total) * 100)}%` }" /></span>
              <span class="num w-12 text-right font-black text-xp">+{{ x.xp }}</span>
            </li>
          </ul>
        </section>

        <!-- 成就 -->
        <section class="card mt-3 p-4 lg:mt-0">
          <h2 class="section-title">本周解锁成就</h2>
          <p v-if="!report.achievements.length" class="mt-3 rounded-2xl bg-background px-3 py-6 text-center text-xs text-ink-mute">这周没有新成就，继续加油</p>
          <ul v-else class="mt-3 grid grid-cols-2 gap-2">
            <li v-for="a in report.achievements" :key="a.code" class="flex items-center gap-2 rounded-2xl bg-background px-3 py-2">
              <span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-flame-light to-flame text-on-flame"><Icon :icon="a.icon" width="18" /></span>
              <span class="min-w-0">
                <span class="block truncate text-xs font-bold text-ink">{{ a.title }}</span>
                <span class="block text-[10px] text-xp">+{{ a.xp }} XP</span>
              </span>
            </li>
          </ul>
        </section>
      </div>
    </div>
  </div>
</template>
