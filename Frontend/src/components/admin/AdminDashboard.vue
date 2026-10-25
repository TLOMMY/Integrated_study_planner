<script setup>
import { computed, defineAsyncComponent, onMounted, ref } from 'vue'
import { Icon } from '@iconify/vue'
import { adminApi } from '@/api/admin'
import { themeColor } from '@/composables/useTheme'
import { useUiStore } from '@/stores/ui'

const EChart = defineAsyncComponent(() => import('@/components/stats/EChart.vue'))
const emit = defineEmits(['go'])
const ui = useUiStore()
const data = ref(null)

const load = async () => {
  try {
    data.value = await adminApi.dashboard()
  } catch (error) {
    ui.fail(error)
  }
}
onMounted(load)
defineExpose({ load })

const cards = computed(() => {
  const d = data.value
  if (!d) return []
  return [
    { label: '注册用户', value: d.users.total, sub: `今日 +${d.users.new_today} · 7 天 +${d.users.new_7d}`, icon: 'lucide:users', cls: 'text-primary bg-primary-light' },
    { label: '日活 / 周活', value: `${d.users.dau} / ${d.users.wau}`, sub: `月活 ${d.users.mau}`, icon: 'lucide:flame', cls: 'text-flame bg-flame-light' },
    { label: 'AI 对话', value: d.ai.messages_total, sub: `今日 ${d.ai.messages_today} · ${d.ai.conversations} 个会话`, icon: 'lucide:sparkles', cls: 'text-xp bg-xp-light' },
    { label: '待处理反馈', value: d.feedback.by_status.open, sub: `处理中 ${d.feedback.by_status.processing} · 共 ${d.feedback.total}`, icon: 'lucide:inbox', cls: 'text-success bg-success-light', tab: 'feedback' },
    { label: '前端错误（7 天）', value: d.errors.occurrences_7d, sub: `${d.errors.groups_7d} 类`, icon: 'lucide:bug', cls: 'text-danger bg-danger-light', tab: 'errors' },
  ]
})

const axis = () => ({
  axisLine: { show: false }, axisTick: { show: false },
  axisLabel: { color: themeColor('ink-mute'), fontSize: 10 },
})
const trendOption = computed(() => {
  const t = data.value?.trend || []
  return {
    grid: { top: 28, left: 4, right: 4, bottom: 4, containLabel: true },
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: t.map((d) => d.label), ...axis() },
    yAxis: { type: 'value', minInterval: 1, splitLine: { lineStyle: { color: themeColor('ink-line') } }, ...axis() },
    series: [
      { name: '活跃用户', type: 'bar', barGap: '10%', barMaxWidth: 14, data: t.map((d) => d.active_users), itemStyle: { borderRadius: [6, 6, 2, 2], color: themeColor('primary') } },
      { name: '新增注册', type: 'bar', barMaxWidth: 14, data: t.map((d) => d.new_users), itemStyle: { borderRadius: [6, 6, 2, 2], color: themeColor('flame') } },
    ],
  }
})
const aiOption = computed(() => {
  const t = data.value?.trend || []
  return {
    grid: { top: 16, left: 4, right: 4, bottom: 4, containLabel: true },
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: t.map((d) => d.label), ...axis() },
    yAxis: { type: 'value', minInterval: 1, splitLine: { lineStyle: { color: themeColor('ink-line') } }, ...axis() },
    series: [{ name: 'AI 提问', type: 'bar', barMaxWidth: 16, data: t.map((d) => d.ai_messages), itemStyle: { borderRadius: [6, 6, 2, 2], color: themeColor('xp') } }],
  }
})
const feedbackOption = computed(() => {
  const s = data.value?.feedback.by_status || {}
  const colors = { open: 'flame', processing: 'primary', resolved: 'success', closed: 'ink-mute' }
  const labels = { open: '待处理', processing: '处理中', resolved: '已解决', closed: '已关闭' }
  return {
    tooltip: { trigger: 'item', formatter: '{b}：{c}（{d}%）' },
    series: [{
      type: 'pie', radius: ['55%', '82%'], label: { show: false },
      itemStyle: { borderColor: themeColor('surface'), borderWidth: 3, borderRadius: 6 },
      data: Object.keys(labels).map((k) => ({ name: labels[k], value: s[k] || 0, itemStyle: { color: themeColor(colors[k]) } })),
    }],
  }
})
</script>

<template>
  <div v-if="!data" class="grid grid-cols-2 gap-3 lg:grid-cols-5"><div v-for="i in 5" :key="i" class="skeleton h-24" /></div>
  <div v-else class="space-y-4">
    <div class="grid grid-cols-2 gap-3 lg:grid-cols-5">
      <component :is="c.tab ? 'button' : 'div'" v-for="c in cards" :key="c.label" type="button" class="card p-4 text-left" :class="c.tab && 'transition hover:border-primary/40'" @click="c.tab && emit('go', c.tab)">
        <div class="flex items-center gap-2">
          <span class="flex h-8 w-8 items-center justify-center rounded-xl" :class="c.cls"><Icon :icon="c.icon" width="16" /></span>
          <span class="text-xs font-bold text-ink-soft">{{ c.label }}</span>
        </div>
        <p class="num mt-2 text-2xl font-black text-ink">{{ c.value }}</p>
        <p class="mt-0.5 truncate text-[11px] text-ink-mute">{{ c.sub }}</p>
      </component>
    </div>

    <div class="grid gap-4 lg:grid-cols-3">
      <section class="card p-4 lg:col-span-2">
        <div class="flex items-center justify-between">
          <h3 class="section-title">近 14 天新增与活跃</h3>
          <span class="flex items-center gap-3 text-[11px] text-ink-mute">
            <span class="flex items-center gap-1"><i class="h-2 w-2 rounded-full bg-primary" />活跃</span>
            <span class="flex items-center gap-1"><i class="h-2 w-2 rounded-full bg-flame" />新增</span>
          </span>
        </div>
        <EChart :option="trendOption" :height="200" class="mt-2" />
        <p class="mt-1 text-[11px] text-ink-mute">活跃：当天打开过 App 或有学习记录（任务、专注等）的用户；不含演示数据</p>
      </section>
      <section class="card p-4">
        <h3 class="section-title">反馈状态</h3>
        <div class="mt-2 flex items-center gap-4">
          <EChart :option="feedbackOption" :height="140" class="!w-[140px] shrink-0" />
          <ul class="space-y-1.5 text-xs">
            <li v-for="(v, k) in data.feedback.by_status" :key="k" class="flex items-center justify-between gap-4">
              <span class="text-ink-soft">{{ { open: '待处理', processing: '处理中', resolved: '已解决', closed: '已关闭' }[k] }}</span>
              <span class="num font-black text-ink">{{ v }}</span>
            </li>
            <li class="pt-1 text-[11px] text-ink-mute">近 7 天新增 {{ data.feedback.new_7d }}</li>
          </ul>
        </div>
      </section>
      <section class="card p-4 lg:col-span-3">
        <h3 class="section-title">近 14 天 AI 提问次数</h3>
        <EChart :option="aiOption" :height="160" class="mt-2" />
      </section>
    </div>
  </div>
</template>
