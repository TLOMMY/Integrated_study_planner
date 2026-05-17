<script setup>
import { Icon } from '@iconify/vue'
import * as echarts from 'echarts'
import { onMounted, ref } from 'vue'

import StatsCard from '@/components/statistics/StatsCard.vue'
import AchievementBadge from '@/components/statistics/AchievementBadge.vue'

import { useStatisticsStore } from '@/stores/statistics'

const store = useStatisticsStore()

const chartRef = ref(null)

onMounted(async () => {
  await store.fetchStatistics()
  const chart = echarts.init(chartRef.value)

  chart.setOption({
    tooltip: {
      trigger: 'axis',
    },

    grid: {
      top: 20,
      left: 20,
      right: 20,
      bottom: 20,
    },

    xAxis: {
      type: 'category',

      data: ['一', '二', '三', '四', '五', '六', '日'],

      axisLine: {
        show: false,
      },

      axisTick: {
        show: false,
      },

      axisLabel: {
        color: '#94a3b8',
        fontSize: 11,
      },
    },

    yAxis: {
      type: 'value',

      splitLine: {
        lineStyle: {
          color: '#f1f5f9',
        },
      },

      axisLabel: {
        show: false,
      },
    },

    series: [
      {
        data: store.chartData,

        type: 'bar',

        barWidth: 18,

        itemStyle: {
          borderRadius: [10, 10, 0, 0],

          color: new echarts.graphic.LinearGradient(
            0,
            0,
            0,
            1,
            [
              {
                offset: 0,
                color: '#6366f1',
              },
              {
                offset: 1,
                color: '#818cf8',
              },
            ]
          ),
        },
      },
    ],
  })

  window.addEventListener('resize', () => {
    chart.resize()
  })
})
</script>

<template>
  <div class="relative w-full h-full bg-slate-50 overflow-hidden">
    <!-- 顶部 -->
    <div
      class="h-[88px] px-6 pt-10 pb-4 flex items-center justify-between border-b border-slate-100 bg-slate-50"
    >
      <div>
        <h1 class="text-[22px] font-bold text-slate-900">
          数据统计
        </h1>

        <p class="text-xs text-slate-400 mt-1">
          查看你的学习成长轨迹
        </p>
      </div>
    </div>

    <!-- 内容区域 -->
    <div
      class="h-[calc(812px-88px-80px)] overflow-y-auto scrollbar-hide pb-8"
    >
      <!-- 等级卡片 -->
      <div class="px-6 pt-6">
        <div
          class="bg-gradient-to-br from-slate-900 to-slate-700 rounded-[28px] p-6 text-white"
        >
          <div class="flex items-center justify-between mb-5">
            <div class="flex items-center gap-3">
              <div
                class="w-12 h-12 rounded-2xl bg-yellow-400 flex items-center justify-center text-slate-900"
              >
                <Icon icon="lucide:trophy" width="24" />
              </div>

              <div>
                <h2 class="text-lg font-bold">
                  {{ store.user.name }}
                </h2>

                <p class="text-xs text-slate-300">
                  Lv.{{ store.user.level }}
                </p>
              </div>
            </div>

            <div class="text-right">
              <div class="text-3xl font-black">
                {{ store.user.exp }}
              </div>

              <div class="text-[10px] text-slate-300">
                EXP
              </div>
            </div>
          </div>

          <!-- 经验条 -->
          <div>
            <div
              class="h-2 bg-white/10 rounded-full overflow-hidden"
            >
              <div
                class="h-full bg-yellow-400 rounded-full"
                :style="{
                  width: store.user.progress + '%',
                }"
              ></div>
            </div>

            <div
              class="flex justify-between mt-2 text-[10px] text-slate-400"
            >
              <span>当前进度</span>

              <span>
                还差 {{ store.user.nextLevelNeed }} EXP
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- 数据卡片 -->
      <div
        class="px-6 mt-6 grid grid-cols-2 gap-4 mb-8 auto-rows-[110px]"
      >
        <StatsCard
          v-for="item in store.stats"
          :key="item.title"
          v-bind="item"
        />
      </div>

      <!-- 图表 -->
      <div class="px-6 mb-8">
        <div class="flex items-center gap-2 mb-4">
          <Icon
            icon="lucide:bar-chart-3"
            width="18"
            class="text-blue-500"
          />

          <h3 class="text-sm font-bold text-slate-800">
            本周学习趋势
          </h3>
        </div>

        <div
          ref="chartRef"
          class="w-full h-[180px] bg-white rounded-[24px] border border-slate-100"
        ></div>
      </div>

      <!-- 成就 -->
      <div class="px-6 mb-8">
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-sm font-bold text-slate-800">
            成就勋章
          </h3>

          <button
            class="text-xs font-medium text-blue-500"
          >
            查看全部
          </button>
        </div>

        <div class="grid grid-cols-4 gap-4">
          <AchievementBadge
            v-for="badge in store.badges"
            :key="badge.title"
            v-bind="badge"
          />
        </div>
      </div>

      <!-- AI 总结 -->
      <div class="px-6 pb-10">
        <div
          class="bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-100 rounded-[28px] p-5"
        >
          <div class="flex items-center gap-2 mb-3">
            <div
              class="w-8 h-8 rounded-xl bg-blue-500 text-white flex items-center justify-center"
            >
              <Icon icon="lucide:sparkles" width="16" />
            </div>

            <h3 class="text-sm font-bold text-slate-800">
              AI 学习分析
            </h3>
          </div>

          <p class="text-xs leading-6 text-slate-600">
            本周学习时长较上周提升 18%，专注状态明显改善。
            数学与英语进步速度最快，建议继续保持当前节奏。
            你的学习习惯已经逐渐进入稳定阶段。
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.scrollbar-hide::-webkit-scrollbar {
  display: none;
}

.scrollbar-hide {
  scrollbar-width: none;
}
</style>