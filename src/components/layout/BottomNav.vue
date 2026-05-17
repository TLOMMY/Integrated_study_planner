<script setup>
import { Icon } from '@iconify/vue'
import { useRoute } from 'vue-router'

const route = useRoute()

const tabs = [
  {
    label: '首页',
    icon: 'lucide:home',
    path: '/today-task',
  },
  {
    label: '课表',
    icon: 'lucide:calendar-range',
    path: '/timetable',
  },
  {
    label: 'AI',
    icon: 'lucide:sparkles',
    path: '/ai',
  },
  {
    label: '统计',
    icon: 'lucide:bar-chart-3',
    path: '/statistics',
  },
  {
    label: '我的',
    icon: 'lucide:user',
    path: '/profile',
  },
]
</script>

<template>
  <div
    class="h-[80px] bg-white border-t border-slate-200 flex items-center justify-around shrink-0"
  >
    <router-link
      v-for="tab in tabs"
      :key="tab.path"
      :to="tab.path"
      class="flex flex-col items-center justify-center gap-1 text-xs flex-1 h-full transition-all"
      :class="route.path === tab.path ? 'text-blue-500' : 'text-slate-400'"
    >
      <Icon :icon="tab.icon" class="text-[22px]" />

      <span>{{ tab.label }}</span>
    </router-link>
  </div>
</template>