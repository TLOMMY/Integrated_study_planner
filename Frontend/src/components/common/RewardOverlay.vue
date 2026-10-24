<script setup>
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { useUiStore } from '@/stores/ui'

const ui = useUiStore()
const current = computed(() => ui.celebrations[0])

const pieces = Array.from({ length: 28 }, (_, i) => ({
  left: `${(i * 37) % 100}%`,
  delay: `${(i % 7) * 0.12}s`,
  color: ['#4F6EF7', '#FF8A00', '#10B981', '#8B5CF6', '#F43F5E'][i % 5],
  size: 6 + (i % 3) * 3,
}))

const headline = computed(() => {
  const r = current.value
  if (!r) return ''
  if (r.level_up) return `升到 Lv.${r.level.level}！`
  if (r.goal_just_reached) return '今日目标达成！'
  return '解锁新成就！'
})
</script>

<template>
  <Transition enter-active-class="transition duration-200" enter-from-class="opacity-0" leave-active-class="transition duration-150" leave-to-class="opacity-0">
    <div v-if="current" class="absolute inset-0 z-[90] flex items-center justify-center overflow-hidden bg-ink/55 px-8 backdrop-blur-sm" role="dialog" aria-modal="true">
      <span
        v-for="(p, i) in pieces"
        :key="`${current.id}-${i}`"
        class="pointer-events-none absolute top-0 animate-confetti rounded-sm"
        :style="{ left: p.left, animationDelay: p.delay, background: p.color, width: `${p.size}px`, height: `${p.size * 1.6}px` }"
      />

      <div :key="current.id" class="relative w-full max-w-sm animate-pop rounded-[32px] bg-surface p-6 text-center shadow-2xl">
        <div class="mx-auto -mt-14 mb-3 flex h-20 w-20 items-center justify-center rounded-full border-4 border-surface shadow-lift"
             :class="current.level_up ? 'bg-xp text-white' : current.goal_just_reached ? 'bg-flame text-white' : 'bg-success text-white'">
          <Icon :icon="current.level_up ? 'lucide:crown' : current.goal_just_reached ? 'lucide:flame' : 'lucide:award'" width="38" />
        </div>
        <h2 class="text-2xl font-black text-ink">{{ headline }}</h2>

        <p v-if="current.goal_just_reached" class="mt-2 text-sm text-ink-soft">
          今天已专注 <b class="num text-flame">{{ current.daily_goal.done_minutes }}</b> 分钟 ·
          连续 <b class="num text-flame">{{ current.streak.current }}</b> 天
        </p>
        <p v-else-if="current.level_up" class="mt-2 text-sm text-ink-soft">累计 {{ current.level.total_xp }} XP，继续保持！</p>

        <div v-if="current.new_achievements?.length" class="mt-4 space-y-2 text-left">
          <div v-for="item in current.new_achievements" :key="item.code" class="flex items-center gap-3 rounded-2xl bg-success-light p-3">
            <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-success text-white">
              <Icon :icon="item.icon" width="20" />
            </div>
            <div class="min-w-0 flex-1">
              <p class="text-sm font-black text-ink">{{ item.title }}</p>
              <p class="text-xs text-ink-soft">{{ item.description }}</p>
            </div>
            <span class="num text-xs font-black text-xp">+{{ item.xp }}</span>
          </div>
        </div>

        <div class="mt-5 inline-flex items-center gap-1.5 rounded-full bg-xp-light px-4 py-1.5 text-sm font-black text-xp">
          <Icon icon="lucide:sparkles" width="16" /> +{{ current.xp_gained }} XP
        </div>

        <button class="btn-primary mt-5 w-full" type="button" @click="ui.nextCelebration()">太棒了</button>
      </div>
    </div>
  </Transition>
</template>
