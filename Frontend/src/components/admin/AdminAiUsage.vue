<script setup>
/** 管理后台看板：服务器 DeepSeek Key 的 AI 用量（今日 / 7 天调用与 token、近 7 天趋势、前 10 用户）。 */
import { computed, defineAsyncComponent } from 'vue'
import { themeColor } from '@/composables/useTheme'
import { formatTokens } from '@/utils/site'

const EChart = defineAsyncComponent(() => import('@/components/stats/EChart.vue'))
const props = defineProps({ usage: { type: Object, required: true } })

const limitText = computed(() => {
  const l = props.usage.limits || {}
  const parts = [l.calls ? `${l.calls} 次` : '次数不限', l.tokens ? `${formatTokens(l.tokens)} tokens` : 'token 不限']
  return `每人每天 ${parts.join(' · ')}`
})

const option = computed(() => {
  const t = props.usage.trend || []
  const axis = { axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: themeColor('ink-mute'), fontSize: 10 } }
  return {
    grid: { top: 24, left: 4, right: 4, bottom: 4, containLabel: true },
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: t.map((d) => d.label), ...axis },
    yAxis: [
      { type: 'value', minInterval: 1, splitLine: { lineStyle: { color: themeColor('ink-line') } }, ...axis },
      { type: 'value', splitLine: { show: false }, ...axis, axisLabel: { ...axis.axisLabel, formatter: (v) => formatTokens(v) } },
    ],
    series: [
      { name: '调用次数', type: 'bar', barMaxWidth: 16, data: t.map((d) => d.calls), itemStyle: { borderRadius: [6, 6, 2, 2], color: themeColor('xp') } },
      // EChart.vue 只注册了柱状图 / 饼图：tokens 也用柱状图（右轴）
      { name: 'tokens', type: 'bar', yAxisIndex: 1, barMaxWidth: 10, data: t.map((d) => d.tokens), itemStyle: { borderRadius: [6, 6, 2, 2], color: themeColor('primary') } },
    ],
  }
})
</script>

<template>
  <section class="card p-4 lg:col-span-3">
    <div class="flex flex-wrap items-center justify-between gap-2">
      <h3 class="section-title">AI 用量（服务器 DeepSeek Key）</h3>
      <span class="text-[11px] text-ink-mute">{{ limitText }} · 用户自己的 Key 与管理员不计入</span>
    </div>
    <div class="mt-3 grid grid-cols-2 gap-3 lg:grid-cols-4">
      <div class="rounded-2xl bg-background p-3">
        <p class="text-[11px] font-bold text-ink-mute">今日调用</p>
        <p class="num mt-1 text-xl font-black text-ink">{{ usage.today.calls }}</p>
        <p class="text-[11px] text-ink-mute">{{ usage.today.users }} 人</p>
      </div>
      <div class="rounded-2xl bg-background p-3">
        <p class="text-[11px] font-bold text-ink-mute">今日 tokens</p>
        <p class="num mt-1 text-xl font-black text-ink">{{ formatTokens(usage.today.tokens) }}</p>
      </div>
      <div class="rounded-2xl bg-background p-3">
        <p class="text-[11px] font-bold text-ink-mute">近 7 天调用</p>
        <p class="num mt-1 text-xl font-black text-ink">{{ usage.last_7d.calls }}</p>
        <p class="text-[11px] text-ink-mute">{{ usage.last_7d.users }} 人</p>
      </div>
      <div class="rounded-2xl bg-background p-3">
        <p class="text-[11px] font-bold text-ink-mute">近 7 天 tokens</p>
        <p class="num mt-1 text-xl font-black text-ink">{{ formatTokens(usage.last_7d.tokens) }}</p>
      </div>
    </div>

    <div class="mt-4 grid gap-4 lg:grid-cols-2">
      <div>
        <p class="text-xs font-bold text-ink-soft">近 7 天趋势</p>
        <EChart :option="option" :height="180" class="mt-1" />
      </div>
      <div class="min-w-0">
        <p class="text-xs font-bold text-ink-soft">近 7 天用量前 10</p>
        <p v-if="!usage.top_users.length" class="mt-6 text-center text-xs text-ink-mute">还没有人使用服务器 Key</p>
        <div v-else class="mt-1 overflow-x-auto">
          <table class="w-full text-left text-xs">
            <thead class="text-[11px] text-ink-mute">
              <tr><th class="py-1.5 font-bold">用户</th><th class="py-1.5 text-right font-bold">今日</th><th class="py-1.5 text-right font-bold">7 天次数</th><th class="py-1.5 text-right font-bold">7 天 tokens</th></tr>
            </thead>
            <tbody class="divide-y divide-ink-line/60">
              <tr v-for="(u, i) in usage.top_users" :key="u.user_id">
                <td class="max-w-[180px] py-1.5">
                  <span class="num mr-1 text-ink-mute">{{ i + 1 }}.</span>
                  <span class="font-semibold text-ink">{{ u.name }}</span>
                  <span v-if="u.is_demo" class="ml-1 rounded bg-flame-light px-1 text-[10px] font-bold text-flame">演示</span>
                  <span class="block truncate text-[10px] text-ink-mute">{{ u.email }}</span>
                </td>
                <td class="num py-1.5 text-right text-ink-soft">{{ u.calls_today }}</td>
                <td class="num py-1.5 text-right text-ink-soft">{{ u.calls_7d }}</td>
                <td class="num py-1.5 text-right font-bold text-ink">{{ formatTokens(u.tokens_7d) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </section>
</template>
