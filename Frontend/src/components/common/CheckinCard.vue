<script setup>
/** 今天第一次打卡成功：顶部下方弹出的小卡片，播放火苗动画，不挡操作，2.4 秒后自动消失。 */
import { useUiStore } from '@/stores/ui'
import StreakFlame from '@/components/motion/StreakFlame.vue'

const ui = useUiStore()
</script>

<template>
  <Transition enter-active-class="transition duration-200" enter-from-class="-translate-y-3 opacity-0" leave-active-class="transition duration-200" leave-to-class="opacity-0">
    <div
      v-if="ui.checkin"
      :key="ui.checkin.id"
      class="pointer-events-auto absolute left-1/2 top-[calc(var(--safe-top)+64px)] z-[95] flex -translate-x-1/2 items-center gap-3 rounded-3xl border border-ink-line/70 bg-surface py-2 pl-2 pr-5 shadow-2xl"
      role="status"
      @click="ui.checkin = null"
    >
      <StreakFlame :days="ui.checkin.days" :size="64" :show-days="false" />
      <div>
        <p class="text-[15px] font-black text-ink">今天已打卡</p>
        <p class="whitespace-nowrap text-xs text-ink-soft">连续 <b class="num text-flame">{{ ui.checkin.days }}</b> 天<template v-if="ui.checkin.xp"> · +{{ ui.checkin.xp }} XP</template></p>
      </div>
    </div>
  </Transition>
</template>
