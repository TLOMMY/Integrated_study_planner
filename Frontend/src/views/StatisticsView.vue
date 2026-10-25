<script setup>
import { computed, defineAsyncComponent, onActivated, onMounted, ref } from 'vue'
import { Icon } from '@iconify/vue'
import dayjs from 'dayjs'
import Heatmap from '@/components/stats/Heatmap.vue'
import Leaderboard from '@/components/stats/Leaderboard.vue'
import ProgressRing from '@/components/common/ProgressRing.vue'
import { themeColor } from '@/composables/useTheme'
import BottomSheet from '@/components/common/BottomSheet.vue'
import { useStatsStore } from '@/stores/plans'
import { useGameStore } from '@/stores/game'
import { useAuthStore } from '@/stores/auth'
import { useUiStore } from '@/stores/ui'
import { formatMinutes } from '@/utils/dates'

defineOptions({ name: 'StatisticsView' })

// ECharts 体积较大，单独拆包，先渲染数字卡片再加载图表
const EChart = defineAsyncComponent(() => import('@/components/stats/EChart.vue'))

const stats = useStatsStore()
const game = useGameStore()
const auth = useAuthStore()
const ui = useUiStore()
const sheet = ref('')
const badge = ref(null)

const d = computed(() => stats.data)
const unlocked = computed(() => d.value?.achievements.filter((a) => a.unlocked).length || 0)

const trendOption = computed(() => ({
  grid: { top: 20, left: 4, right: 4, bottom: 4, containLabel: true },
  tooltip: { trigger: 'axis', formatter: (p) => `${p[0].name}<br/>专注 ${p[0].value} 分钟`, ...chartTooltip() },
  xAxis: { type: 'category', data: d.value.week.map((w) => w.label.replace('周', '')), axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: themeColor('chart-axis'), fontSize: 11 } },
  yAxis: { type: 'value', splitLine: { lineStyle: { color: themeColor('chart-grid') } }, axisLabel: { color: themeColor('chart-faint'), fontSize: 10 } },
  series: [
    {
      type: 'bar',
      barWidth: 16,
      data: d.value.week.map((w, i) => ({
        value: w.minutes,
        itemStyle: { borderRadius: [8, 8, 2, 2], color: i === 6 ? themeColor('primary') : themeColor('primary-soft') },
      })),
      label: { show: true, position: 'top', fontSize: 10, color: themeColor('chart-label'), formatter: (p) => (p.value ? p.value : '') },
    },
  ],
}))

// 图表配色取当前主题（themeColor 是响应式的，切换主题后 option 重算、图表重绘）
const PIE = ['chart-1', 'chart-2', 'chart-3', 'chart-4', 'chart-5', 'chart-6', 'chart-7']
const chartTooltip = () => ({ backgroundColor: themeColor('surface'), borderColor: themeColor('ink-line'), textStyle: { color: themeColor('ink') } })
const subjectOption = computed(() => ({
  tooltip: { trigger: 'item', formatter: (p) => `${p.name}<br/>${p.value} 分钟（${p.percent}%）`, ...chartTooltip() },
  series: [
    {
      type: 'pie',
      radius: ['55%', '82%'],
      center: ['50%', '50%'],
      itemStyle: { borderColor: themeColor('surface'), borderWidth: 3, borderRadius: 6 },
      label: { show: false },
      data: subjectItems.value.map((s, i) => ({ name: s.subject, value: s.minutes, itemStyle: { color: themeColor(PIE[i % PIE.length]) } })),
    },
  ],
}))

// ---------------------------------------------------------------- 科目统计（7 / 30 / 90 天）
const subjectDays = ref(30)
const subjectItems = computed(() => stats.subjects?.items || d.value?.subjects || [])
const subjectTotal = computed(() => subjectItems.value.reduce((sum, s) => sum + s.minutes, 0))
const loadSubjects = (days = subjectDays.value) => {
  subjectDays.value = days
  return stats.loadSubjects(days).catch(() => {})
}

// ---------------------------------------------------------------- 排行榜：全站 / 小组
const boardScope = ref(localStorage.getItem('board-scope') || 'all')
const activeGroupId = ref(Number(localStorage.getItem('board-group')) || null)
const activeGroup = computed(() => stats.groups.find((g) => g.id === activeGroupId.value) || stats.groups[0] || null)
const switchScope = async (scope) => {
  boardScope.value = scope
  localStorage.setItem('board-scope', scope)
  if (scope === 'group') await loadGroupBoard()
}
const loadGroupBoard = async (id = null) => {
  await stats.loadGroups().catch(() => {})
  if (id) activeGroupId.value = id
  const group = activeGroup.value
  if (!group) return
  activeGroupId.value = group.id
  localStorage.setItem('board-group', String(group.id))
  await stats.loadGroupBoard(group.id).catch(ui.fail)
}

// ---------------------------------------------------------------- 断签保护卡
const protectedRecently = computed(() => {
  const day = d.value?.streak?.last_protected
  return Boolean(day) && dayjs().diff(dayjs(day), 'day') <= 2
})
const openFreezes = async () => {
  sheet.value = 'freezes'
  await stats.loadFreezes().catch(ui.fail)
}

const load = async () => {
  try {
    const data = await stats.load()
    game.apply(data)
    loadSubjects()
    if (boardScope.value === 'group') loadGroupBoard()
  } catch (error) {
    ui.fail(error, '统计加载失败')
  }
}
const openBoard = async () => {
  sheet.value = 'board'
  await stats.loadLeaderboard().catch(ui.fail)
}

onMounted(load)
onActivated(() => stats.data && load())
</script>

<template>
  <div class="scrollbar-hide h-full overflow-y-auto px-5 pb-24 pt-[calc(var(--safe-top)+16px)] lg:px-10 lg:pb-10 lg:pt-8">
   <div class="desk-page">
    <header class="flex items-center justify-between">
      <h1 class="text-[22px] font-black text-ink">成长</h1>
      <RouterLink to="/profile" class="flex items-center gap-2 rounded-full bg-surface py-1 pl-1 pr-3 shadow-soft">
        <span class="flex h-8 w-8 items-center justify-center rounded-full bg-primary-light text-lg">{{ auth.user?.avatar }}</span>
        <span class="text-xs font-bold text-ink">{{ auth.displayName }}</span>
      </RouterLink>
    </header>

    <div v-if="stats.loading" class="mt-4 space-y-3"><div class="skeleton h-40" /><div class="skeleton h-28" /><div class="skeleton h-48" /></div>

    <div v-else-if="d" class="lg:mt-5 lg:grid lg:grid-cols-2 lg:gap-4">
      <!-- 等级 -->
      <section class="mt-4 rounded-[28px] bg-gradient-to-br from-xp to-primary p-5 text-on-primary shadow-lift lg:mt-0 lg:order-1">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-xs opacity-80">当前等级</p>
            <p class="num mt-0.5 text-4xl font-black">Lv.{{ d.level.level }}</p>
          </div>
          <div class="text-right">
            <p class="num text-2xl font-black">{{ d.level.total_xp }}</p>
            <p class="text-[10px] opacity-80">累计 XP</p>
          </div>
        </div>
        <div class="mt-4 h-2.5 overflow-hidden rounded-full bg-on-primary/20">
          <div class="h-full rounded-full bg-on-primary transition-all duration-700" :style="{ width: `${d.level.progress}%` }" />
        </div>
        <p class="num mt-1.5 text-right text-[11px] opacity-80">再获得 {{ d.level.xp_for_next - d.level.xp_in_level }} XP 升到 Lv.{{ d.level.level + 1 }}</p>
      </section>

      <!-- 三项核心指标 -->
      <section class="mt-3 grid grid-cols-3 gap-2.5 lg:mt-0 lg:order-2">
        <div class="card flex flex-col items-center justify-center p-3 text-center">
          <Icon icon="lucide:flame" width="26" class="text-flame" :class="d.streak.active_today && 'animate-flicker'" />
          <p class="num mt-1 text-xl font-black text-ink">{{ d.streak.current }}</p>
          <p class="text-[10px] font-bold text-ink-mute">连续天数</p>
        </div>
        <div class="card flex flex-col items-center justify-center p-3 text-center">
          <ProgressRing :value="d.daily_goal.progress" :size="42" :stroke="5" color="rgb(var(--c-success))" track="rgb(var(--c-ink-line))">
            <span class="num text-[10px] font-black text-success">{{ d.daily_goal.progress }}%</span>
          </ProgressRing>
          <p class="mt-1 text-[10px] font-bold text-ink-mute">今日目标</p>
        </div>
        <div class="card flex flex-col items-center justify-center p-3 text-center">
          <Icon icon="lucide:hourglass" width="26" class="text-primary" />
          <p class="num mt-1 text-xl font-black text-ink">{{ (d.totals.focus_minutes / 60).toFixed(0) }}</p>
          <p class="text-[10px] font-bold text-ink-mute">累计小时</p>
        </div>
      </section>

      <!-- 本周打卡 -->
      <section class="card mt-3 p-4 lg:mt-0 lg:order-3">
        <div class="flex items-center justify-between">
          <h2 class="section-title">本周打卡</h2>
          <span class="text-xs font-semibold text-ink-mute">最长连续 {{ d.streak.longest }} 天</span>
        </div>
        <div class="mt-3 grid grid-cols-7 gap-1.5">
          <div v-for="day in d.streak.week" :key="day.date" class="flex flex-col items-center gap-1">
            <span
              class="flex h-9 w-9 items-center justify-center rounded-full"
              :class="day.active ? 'bg-flame text-on-flame' : day.frozen ? 'bg-primary-light text-primary' : day.is_today ? 'border-2 border-dashed border-flame/50 text-flame' : 'bg-background text-ink-mute'"
              :title="day.frozen ? '保护卡补上的一天' : undefined"
            >
              <Icon :icon="day.active ? 'lucide:flame' : day.frozen ? 'lucide:shield-check' : 'lucide:circle-dashed'" width="16" />
            </span>
            <span class="text-[10px] font-bold" :class="day.is_today ? 'text-flame' : 'text-ink-mute'">{{ day.label }}</span>
          </div>
        </div>
        <p v-if="d.streak.at_risk" class="mt-3 rounded-2xl bg-flame-light px-3 py-2 text-xs font-semibold text-flame">
          <template v-if="protectedRecently">已用保护卡保住连续记录，</template>今天还没打卡，完成一次专注或任务就能保住 {{ d.streak.current }} 天的连续记录
        </p>
        <p v-else-if="protectedRecently" class="mt-3 rounded-2xl bg-primary-light px-3 py-2 text-xs font-semibold text-primary">已用保护卡保住连续记录，继续保持</p>

        <!-- 断签保护卡 -->
        <button class="mt-3 flex w-full items-center gap-3 rounded-2xl bg-background px-3 py-2.5 text-left" type="button" @click="openFreezes">
          <span class="flex gap-1" :aria-label="`持有 ${d.streak.freezes ?? 0} 张保护卡`">
            <Icon v-for="i in d.streak.freeze_max || 3" :key="i" icon="lucide:shield" width="18" :class="i <= (d.streak.freezes || 0) ? 'text-primary' : 'text-ink-line'" />
          </span>
          <span class="min-w-0 flex-1 text-xs">
            <span class="block font-bold text-ink">断签保护卡 {{ d.streak.freezes ?? 0 }}/{{ d.streak.freeze_max || 3 }}</span>
            <span class="block text-ink-mute">再连续学习 {{ d.streak.next_freeze_in ?? 7 }} 天获得 1 张，漏学一天自动补上</span>
          </span>
          <Icon icon="lucide:chevron-right" width="16" class="text-ink-mute" />
        </button>
      </section>

      <!-- 热力图 -->
      <section class="card mt-3 p-4 lg:mt-0 lg:order-5 lg:col-span-2">
        <h2 class="section-title mb-3">学习足迹</h2>
        <Heatmap :heatmap="d.heatmap" />
      </section>

      <!-- 趋势 -->
      <section class="card mt-3 p-4 lg:mt-0 lg:order-4">
        <div class="flex items-center justify-between">
          <h2 class="section-title">近 7 天专注</h2>
          <span v-if="d.week_change !== null" class="flex items-center gap-0.5 rounded-full px-2 py-0.5 text-[11px] font-black" :class="d.week_change >= 0 ? 'bg-success-light text-success' : 'bg-danger-light text-danger'">
            <Icon :icon="d.week_change >= 0 ? 'lucide:trending-up' : 'lucide:trending-down'" width="13" />{{ Math.abs(d.week_change) }}%
          </span>
        </div>
        <p class="mt-0.5 text-xs text-ink-mute">合计 {{ formatMinutes(d.week_minutes) }}</p>
        <EChart :option="trendOption" :height="170" class="mt-2" />
      </section>

      <!-- 科目分布 -->
      <section class="card mt-3 p-4 lg:mt-0 lg:order-6">
        <div class="flex items-center justify-between gap-2">
          <h2 class="section-title">科目分布</h2>
          <div class="flex gap-1 rounded-xl bg-background p-0.5" role="tablist" aria-label="统计范围">
            <button
              v-for="n in [7, 30, 90]"
              :key="n"
              type="button"
              role="tab"
              :aria-selected="subjectDays === n"
              class="num rounded-lg px-2 py-1 text-[11px] font-black"
              :class="subjectDays === n ? 'bg-surface text-ink shadow-soft' : 'text-ink-mute'"
              @click="loadSubjects(n)"
            >
              {{ n }} 天
            </button>
          </div>
        </div>
        <p v-if="subjectItems.length" class="mt-0.5 text-xs text-ink-mute">合计 {{ formatMinutes(subjectTotal) }}</p>
        <p v-if="!subjectItems.length" class="mt-3 rounded-2xl bg-background px-3 py-6 text-center text-xs text-ink-mute">近 {{ subjectDays }} 天还没有专注记录</p>
        <div v-else class="mt-2 flex items-center gap-3">
          <EChart :option="subjectOption" :height="130" class="!w-[130px] shrink-0" />
          <ul class="min-w-0 flex-1 space-y-1.5">
            <li v-for="(s, i) in subjectItems" :key="s.subject" class="flex items-center gap-2 text-xs">
              <i class="h-2.5 w-2.5 shrink-0 rounded-full" :style="{ background: `rgb(var(--c-${PIE[i % PIE.length]}))` }" />
              <span class="min-w-0 flex-1 truncate font-semibold text-ink">{{ s.subject }}</span>
              <span class="num text-ink-mute" :class="s.percent !== undefined && 'hidden sm:inline lg:hidden xl:inline'">{{ formatMinutes(s.minutes) }}</span>
              <span v-if="s.percent !== undefined" class="num w-10 shrink-0 text-right font-bold text-ink-soft" :title="formatMinutes(s.minutes)">{{ Math.round(s.percent) }}%</span>
            </li>
          </ul>
        </div>
      </section>

      <!-- 排行榜 -->
      <section class="card mt-3 p-4 lg:mt-0 lg:order-7">
        <div class="mb-3 flex items-center justify-between gap-2">
          <h2 class="section-title">本周 XP 排行</h2>
          <div class="flex gap-1 rounded-xl bg-background p-0.5" role="tablist" aria-label="排行范围">
            <button type="button" role="tab" :aria-selected="boardScope === 'all'" class="rounded-lg px-2.5 py-1 text-[11px] font-black" :class="boardScope === 'all' ? 'bg-surface text-ink shadow-soft' : 'text-ink-mute'" @click="switchScope('all')">全站</button>
            <button type="button" role="tab" :aria-selected="boardScope === 'group'" class="rounded-lg px-2.5 py-1 text-[11px] font-black" :class="boardScope === 'group' ? 'bg-surface text-ink shadow-soft' : 'text-ink-mute'" @click="switchScope('group')">小组</button>
          </div>
        </div>
        <template v-if="boardScope === 'all'">
          <Leaderboard :board="d.leaderboard" />
          <button class="mt-2 w-full text-center text-xs font-bold text-primary" type="button" @click="openBoard">查看全部</button>
        </template>
        <template v-else>
          <div v-if="!stats.groupsLoaded" class="skeleton h-32" />
          <div v-else-if="!stats.groups.length" class="rounded-2xl bg-background px-3 py-5 text-center">
            <p class="text-xs text-ink-soft">和同学组个学习小组，只看组内排名</p>
            <RouterLink to="/groups" class="chip chip-active mt-3"><Icon icon="lucide:users" width="13" />创建或加入小组</RouterLink>
          </div>
          <template v-else>
            <div v-if="stats.groups.length > 1" class="scrollbar-hide -mx-1 mb-2 flex gap-1.5 overflow-x-auto px-1">
              <button v-for="g in stats.groups" :key="g.id" type="button" class="chip shrink-0 py-1" :class="g.id === activeGroup?.id && 'chip-active'" @click="loadGroupBoard(g.id)">{{ g.name }}</button>
            </div>
            <Leaderboard v-if="stats.groupBoard?.group_id === activeGroup?.id" :board="stats.groupBoard.leaderboard" />
            <div v-else class="skeleton h-32" />
            <RouterLink :to="{ name: 'groups', query: { id: activeGroup?.id } }" class="mt-2 block text-center text-xs font-bold text-primary">{{ activeGroup?.name }} · 管理小组</RouterLink>
          </template>
        </template>
      </section>

      <!-- 每周报告入口 -->
      <RouterLink to="/report" class="mt-3 flex items-center gap-3 rounded-3xl bg-surface px-4 py-3.5 shadow-soft lg:order-7 lg:mt-0 lg:col-span-2">
        <span class="flex h-10 w-10 items-center justify-center rounded-2xl bg-primary-light text-primary"><Icon icon="lucide:file-chart-column" width="20" /></span>
        <span class="flex-1">
          <span class="block text-sm font-black text-ink">每周学习报告</span>
          <span class="block text-[11px] text-ink-mute">专注、任务、科目与上周对比，附 AI 复盘</span>
        </span>
        <Icon icon="lucide:chevron-right" width="18" class="text-ink-mute" />
      </RouterLink>

      <!-- 成就 -->
      <section class="card mt-3 p-4 lg:mt-0 lg:order-8 lg:col-span-2">
        <div class="mb-3 flex items-center justify-between">
          <h2 class="section-title">成就</h2>
          <span class="num text-xs font-bold text-ink-mute">{{ unlocked }}/{{ d.achievements.length }}</span>
        </div>
        <div class="grid grid-cols-4 gap-3 lg:grid-cols-8">
          <button v-for="a in d.achievements" :key="a.code" class="flex flex-col items-center gap-1.5" type="button" @click="badge = a">
            <span class="relative flex h-14 w-14 items-center justify-center rounded-2xl" :class="a.unlocked ? 'bg-gradient-to-br from-flame-glow to-flame text-on-flame shadow-soft' : 'bg-background text-ink-mute'">
              <Icon :icon="a.icon" width="24" />
              <Icon v-if="!a.unlocked" icon="lucide:lock" width="12" class="absolute bottom-1 right-1" />
            </span>
            <span class="w-full truncate text-center text-[10px] font-bold" :class="a.unlocked ? 'text-ink' : 'text-ink-mute'">{{ a.title }}</span>
            <span v-if="!a.unlocked" class="h-1 w-10 overflow-hidden rounded-full bg-ink-line"><span class="block h-full bg-primary" :style="{ width: `${a.progress}%` }" /></span>
          </button>
        </div>
      </section>
    </div>
   </div>

    <BottomSheet :open="sheet === 'board'" title="本周 XP 排行" :subtitle="stats.leaderboard ? `${dayjs(stats.leaderboard.week_start).format('M/D')} 起 · 每周一重置` : ''" @close="sheet = ''">
      <Leaderboard v-if="stats.leaderboard" :board="stats.leaderboard" :limit="20" />
      <div v-else class="skeleton h-40" />
    </BottomSheet>

    <BottomSheet :open="sheet === 'freezes'" title="断签保护卡" subtitle="连续学习每满 7 天获得 1 张，最多持有 3 张" @close="sheet = ''">
      <div v-if="!stats.freezes" class="skeleton h-40" />
      <template v-else>
        <div class="flex items-center gap-4 rounded-3xl bg-primary-light p-4">
          <div class="flex gap-1.5">
            <Icon v-for="i in stats.freezes.max" :key="i" icon="lucide:shield" width="30" :class="i <= stats.freezes.held ? 'text-primary' : 'text-ink-line'" />
          </div>
          <div class="text-xs text-ink-soft">
            <p class="text-sm font-black text-ink">持有 {{ stats.freezes.held }} 张</p>
            <p>{{ stats.freezes.held >= stats.freezes.max ? '已达上限' : `再连续学习 ${stats.freezes.next_freeze_in} 天获得下一张` }}</p>
          </div>
        </div>
        <p class="mt-3 text-[11px] leading-5 text-ink-mute">某天忘了学习时，会自动消耗保护卡补上那一天，连续天数不中断。缺的天数比持有的卡多时不会消耗（补不上也就不浪费）。</p>
        <h3 class="label mt-4">使用记录</h3>
        <p v-if="!stats.freezes.history.length" class="rounded-2xl bg-background px-3 py-4 text-center text-xs text-ink-mute">还没有记录</p>
        <ul v-else class="space-y-1.5">
          <li v-for="h in stats.freezes.history" :key="h.day + h.kind" class="flex items-center gap-3 rounded-2xl bg-background px-3 py-2 text-xs">
            <Icon :icon="h.kind === 'used' ? 'lucide:shield-check' : 'lucide:plus-circle'" width="16" :class="h.kind === 'used' ? 'text-primary' : 'text-success'" />
            <span class="flex-1 font-semibold text-ink">{{ h.label }}</span>
            <span class="num text-ink-mute">{{ dayjs(h.day).format('M月D日') }} {{ h.weekday }}</span>
          </li>
        </ul>
      </template>
    </BottomSheet>

    <BottomSheet :open="Boolean(badge)" @close="badge = null">
      <div v-if="badge" class="flex flex-col items-center pb-2 pt-4 text-center">
        <span class="flex h-20 w-20 items-center justify-center rounded-3xl" :class="badge.unlocked ? 'bg-gradient-to-br from-flame-glow to-flame text-on-flame shadow-lift' : 'bg-background text-ink-mute'">
          <Icon :icon="badge.icon" width="36" />
        </span>
        <h3 class="mt-4 text-lg font-black text-ink">{{ badge.title }}</h3>
        <p class="mt-1 text-sm text-ink-soft">{{ badge.description }}</p>
        <p v-if="badge.unlocked" class="mt-3 text-xs font-semibold text-success">已于 {{ dayjs(badge.unlocked_at).format('YYYY年M月D日') }} 解锁 · +{{ badge.xp }} XP</p>
        <div v-else class="mt-4 w-full">
          <div class="h-2 overflow-hidden rounded-full bg-ink-line"><div class="h-full rounded-full bg-primary" :style="{ width: `${badge.progress}%` }" /></div>
          <p class="num mt-1.5 text-xs text-ink-mute">{{ badge.value }} / {{ badge.target }} · 解锁奖励 {{ badge.xp }} XP</p>
        </div>
      </div>
    </BottomSheet>
  </div>
</template>
