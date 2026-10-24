<script setup>
import { computed, defineAsyncComponent, onActivated, onMounted, ref } from 'vue'
import { Icon } from '@iconify/vue'
import dayjs from 'dayjs'
import Heatmap from '@/components/stats/Heatmap.vue'
import Leaderboard from '@/components/stats/Leaderboard.vue'
import ProgressRing from '@/components/common/ProgressRing.vue'
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
  tooltip: { trigger: 'axis', formatter: (p) => `${p[0].name}<br/>专注 ${p[0].value} 分钟` },
  xAxis: { type: 'category', data: d.value.week.map((w) => w.label.replace('周', '')), axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: '#94A3B8', fontSize: 11 } },
  yAxis: { type: 'value', splitLine: { lineStyle: { color: '#F1F5F9' } }, axisLabel: { color: '#CBD5E1', fontSize: 10 } },
  series: [
    {
      type: 'bar',
      barWidth: 16,
      data: d.value.week.map((w, i) => ({
        value: w.minutes,
        itemStyle: { borderRadius: [8, 8, 2, 2], color: i === 6 ? '#4F6EF7' : '#C7D2FE' },
      })),
      label: { show: true, position: 'top', fontSize: 10, color: '#64748B', formatter: (p) => (p.value ? p.value : '') },
    },
  ],
}))

const PIE = ['#4F6EF7', '#8B5CF6', '#10B981', '#FF8A00', '#06B6D4', '#94A3B8']
const subjectOption = computed(() => ({
  tooltip: { trigger: 'item', formatter: (p) => `${p.name}<br/>${p.value} 分钟（${p.percent}%）` },
  series: [
    {
      type: 'pie',
      radius: ['55%', '82%'],
      center: ['50%', '50%'],
      itemStyle: { borderColor: '#fff', borderWidth: 3, borderRadius: 6 },
      label: { show: false },
      data: d.value.subjects.map((s, i) => ({ name: s.subject, value: s.minutes, itemStyle: { color: PIE[i % PIE.length] } })),
    },
  ],
}))

const load = async () => {
  try {
    const data = await stats.load()
    game.apply(data)
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
      <section class="mt-4 rounded-[28px] bg-gradient-to-br from-xp to-primary p-5 text-white shadow-lift lg:mt-0 lg:order-1">
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
        <div class="mt-4 h-2.5 overflow-hidden rounded-full bg-white/20">
          <div class="h-full rounded-full bg-white transition-all duration-700" :style="{ width: `${d.level.progress}%` }" />
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
          <ProgressRing :value="d.daily_goal.progress" :size="42" :stroke="5" color="#10B981" track="#E2E8F0">
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
            <span class="flex h-9 w-9 items-center justify-center rounded-full" :class="day.active ? 'bg-flame text-white' : day.is_today ? 'border-2 border-dashed border-flame/50 text-flame' : 'bg-background text-ink-mute'">
              <Icon :icon="day.active ? 'lucide:flame' : 'lucide:circle-dashed'" width="16" />
            </span>
            <span class="text-[10px] font-bold" :class="day.is_today ? 'text-flame' : 'text-ink-mute'">{{ day.label }}</span>
          </div>
        </div>
        <p v-if="d.streak.at_risk" class="mt-3 rounded-2xl bg-flame-light px-3 py-2 text-xs font-semibold text-flame">今天还没打卡，完成一次专注或任务就能保住 {{ d.streak.current }} 天的连续记录</p>
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
      <section v-if="d.subjects.length" class="card mt-3 p-4 lg:mt-0 lg:order-6">
        <h2 class="section-title">近 30 天科目分布</h2>
        <div class="mt-2 flex items-center gap-3">
          <EChart :option="subjectOption" :height="130" class="!w-[130px] shrink-0" />
          <ul class="min-w-0 flex-1 space-y-1.5">
            <li v-for="(s, i) in d.subjects" :key="s.subject" class="flex items-center gap-2 text-xs">
              <i class="h-2.5 w-2.5 shrink-0 rounded-full" :style="{ background: PIE[i % PIE.length] }" />
              <span class="min-w-0 flex-1 truncate font-semibold text-ink">{{ s.subject }}</span>
              <span class="num text-ink-mute">{{ formatMinutes(s.minutes) }}</span>
            </li>
          </ul>
        </div>
      </section>

      <!-- 排行榜 -->
      <section class="card mt-3 p-4 lg:mt-0 lg:order-7">
        <div class="mb-3 flex items-center justify-between">
          <h2 class="section-title">本周 XP 排行</h2>
          <button class="text-xs font-bold text-primary" type="button" @click="openBoard">查看全部</button>
        </div>
        <Leaderboard :board="d.leaderboard" />
      </section>

      <!-- 成就 -->
      <section class="card mt-3 p-4 lg:mt-0 lg:order-8 lg:col-span-2">
        <div class="mb-3 flex items-center justify-between">
          <h2 class="section-title">成就</h2>
          <span class="num text-xs font-bold text-ink-mute">{{ unlocked }}/{{ d.achievements.length }}</span>
        </div>
        <div class="grid grid-cols-4 gap-3 lg:grid-cols-8">
          <button v-for="a in d.achievements" :key="a.code" class="flex flex-col items-center gap-1.5" type="button" @click="badge = a">
            <span class="relative flex h-14 w-14 items-center justify-center rounded-2xl" :class="a.unlocked ? 'bg-gradient-to-br from-amber-300 to-flame text-white shadow-soft' : 'bg-background text-ink-mute'">
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

    <BottomSheet :open="Boolean(badge)" @close="badge = null">
      <div v-if="badge" class="flex flex-col items-center pb-2 pt-4 text-center">
        <span class="flex h-20 w-20 items-center justify-center rounded-3xl" :class="badge.unlocked ? 'bg-gradient-to-br from-amber-300 to-flame text-white shadow-lift' : 'bg-background text-ink-mute'">
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
