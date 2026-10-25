<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import { useAuthStore } from '@/stores/auth'
import { useGameStore } from '@/stores/game'
import { useFocusStore } from '@/stores/focus'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const game = useGameStore()
const focus = useFocusStore()

/** 桌面端侧边导航：移动端底部 5 个入口 + 计划 / 我的 直达。 */
const GROUPS = [
  {
    title: '学习',
    items: [
      { name: 'home', label: '今日待办', icon: 'lucide:circle-check-big', to: '/today-task' },
      { name: 'view', label: '日程', icon: 'lucide:calendar-clock', to: '/view' },
      { name: 'timetable', label: '课表', icon: 'lucide:calendar-days', to: '/timetable' },
      { name: 'plans', label: '学习计划', icon: 'lucide:map', to: '/plans' },
    ],
  },
  {
    title: '智能与成长',
    items: [
      { name: 'ai', label: 'AI 规划', icon: 'lucide:sparkles', to: '/ai', accent: true },
      { name: 'statistics', label: '成长', icon: 'lucide:trophy', to: '/statistics' },
      { name: 'profile', label: '我的', icon: 'lucide:user-round', to: '/profile' },
      { name: 'settings', label: '设置', icon: 'lucide:settings', to: '/settings' },
    ],
  },
]

// 管理员额外显示「管理后台」入口
const groups = computed(() =>
  auth.user?.is_admin
    ? [...GROUPS, { title: '管理', items: [{ name: 'admin', label: '管理后台', icon: 'lucide:shield-check', to: '/admin' }] }]
    : GROUPS,
)
const level = computed(() => game.level)
const streak = computed(() => game.streak)
const startFocus = () => router.push({ name: 'focus' })
</script>

<template>
  <aside class="glass-bar flex h-full w-60 shrink-0 flex-col border-r border-ink-line/70 bg-surface px-3 py-5" aria-label="主导航">
    <RouterLink to="/today-task" class="flex items-center gap-2.5 px-3">
      <img src="/app-icon.svg" alt="" class="h-9 w-9 rounded-xl shadow-lift" />
      <div class="leading-tight">
        <p class="text-base font-black text-ink">学业管家</p>
        <p class="text-[10px] font-semibold text-ink-mute">课表 · 待办 · 专注 · 成长</p>
      </div>
    </RouterLink>

    <button class="btn-primary mx-1 mt-5 py-2.5" type="button" @click="startFocus">
      <Icon :icon="focus.active ? 'lucide:timer' : 'lucide:play'" width="16" />
      {{ focus.active ? `专注中 ${focus.clock}` : '开始专注' }}
    </button>

    <nav class="scrollbar-hide mt-5 flex-1 space-y-5 overflow-y-auto">
      <div v-for="group in groups" :key="group.title">
        <p class="mb-1.5 px-3 text-[10px] font-black tracking-wider text-ink-mute">{{ group.title }}</p>
        <RouterLink
          v-for="item in group.items"
          :key="item.name"
          :to="item.to"
          class="group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-bold transition"
          :class="route.name === item.name ? 'bg-primary-light text-primary' : 'text-ink-soft hover:bg-background hover:text-ink'"
          :aria-current="route.name === item.name ? 'page' : undefined"
        >
          <Icon :icon="item.icon" width="18" :class="item.accent && route.name !== item.name && 'text-xp'" />
          <span class="flex-1">{{ item.label }}</span>
          <span v-if="item.name === 'statistics' && streak?.at_risk" class="h-2 w-2 rounded-full bg-flame" title="今天还没打卡" />
        </RouterLink>
      </div>
    </nav>

    <RouterLink to="/profile" class="mt-3 rounded-2xl bg-background p-3 transition hover:bg-ink-line/40">
      <div class="flex items-center gap-2.5">
        <span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-surface text-xl shadow-soft">{{ auth.user?.avatar }}</span>
        <div class="min-w-0 flex-1">
          <p class="truncate text-sm font-black text-ink">{{ auth.displayName }}</p>
          <p class="text-[11px] font-semibold text-ink-mute">
            Lv.{{ level?.level ?? 1 }}<span class="mx-1">·</span><span class="text-flame">🔥 {{ streak?.current ?? 0 }} 天</span>
          </p>
        </div>
      </div>
      <div class="mt-2.5 h-1.5 overflow-hidden rounded-full bg-ink-line">
        <div class="h-full rounded-full bg-gradient-to-r from-primary to-xp transition-all duration-700" :style="{ width: `${level?.progress ?? 0}%` }" />
      </div>
    </RouterLink>
  </aside>
</template>
