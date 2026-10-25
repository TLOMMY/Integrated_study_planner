<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { Icon } from '@iconify/vue'
import { useGameStore } from '@/stores/game'

const route = useRoute()
const game = useGameStore()

const tabs = [
  { name: 'home', label: '今日', icon: 'lucide:circle-check-big', to: '/today-task', also: ['plans'] },
  { name: 'timetable', label: '课表', icon: 'lucide:calendar-days', to: '/timetable' },
  { name: 'ai', label: 'AI', icon: 'lucide:sparkles', to: '/ai', primary: true },
  { name: 'view', label: '日程', icon: 'lucide:calendar-clock', to: '/view' },
  { name: 'statistics', label: '成长', icon: 'lucide:trophy', to: '/statistics', also: ['profile', 'settings'] },
]

const isActive = (tab) => route.name === tab.name || tab.also?.includes(route.name)
const streakAtRisk = computed(() => game.streak?.at_risk)
</script>

<template>
  <nav class="glass-bar relative z-40 shrink-0 border-t border-ink-line/70 bg-surface/95 pb-[var(--safe-bottom)] backdrop-blur" aria-label="主导航">
    <div class="grid h-16 grid-cols-5">
      <RouterLink
        v-for="tab in tabs"
        :key="tab.name"
        :to="tab.to"
        class="relative flex flex-col items-center justify-center gap-1 text-[10px] font-bold transition"
        :class="isActive(tab) ? 'text-primary' : 'text-ink-mute'"
        :aria-current="isActive(tab) ? 'page' : undefined"
      >
        <span
          v-if="tab.primary"
          class="-mt-7 flex h-14 w-14 items-center justify-center rounded-[20px] bg-gradient-to-br from-primary to-xp text-on-primary shadow-lift ring-4 ring-surface"
        >
          <Icon :icon="tab.icon" width="26" />
        </span>
        <Icon v-else :icon="tab.icon" width="22" />
        <span>{{ tab.label }}</span>
        <span v-if="tab.name === 'statistics' && streakAtRisk" class="absolute right-[22%] top-2.5 h-2 w-2 rounded-full bg-flame ring-2 ring-surface" />
      </RouterLink>
    </div>
  </nav>
</template>
