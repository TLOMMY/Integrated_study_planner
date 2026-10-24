<script setup>
import { onMounted } from 'vue'
import { RouterView } from 'vue-router'
import BottomNav from '@/components/layout/BottomNav.vue'
import SideNav from '@/components/layout/SideNav.vue'
import FocusMiniBar from '@/components/layout/FocusMiniBar.vue'
import { useClassReminder } from '@/composables/useClassReminder'
import { useFocusStore } from '@/stores/focus'
import { useAiStore } from '@/stores/ai'
import { useAuthStore } from '@/stores/auth'
import { useGameStore } from '@/stores/game'
import { useHomeStore } from '@/stores/home'

const focus = useFocusStore()
useClassReminder()

onMounted(() => {
  focus.restore()
  const auth = useAuthStore()
  if (auth.user) useAiStore().init(auth.user.id)
  // 直接打开非首页时，侧边栏的等级 / 连续天数也要有数据
  if (!useGameStore().level) useHomeStore().refresh()
})
</script>

<template>
  <!-- 手机：内容 + 底部导航；桌面（lg）：左侧边栏 + 内容 -->
  <div class="flex h-full flex-col lg:flex-row">
    <SideNav class="hidden lg:flex" />
    <main class="relative min-h-0 flex-1 overflow-hidden">
      <RouterView v-slot="{ Component }">
        <KeepAlive :max="4" include="HomeView,TimetableView,StatisticsView,AiAssistantView">
          <component :is="Component" />
        </KeepAlive>
      </RouterView>
      <FocusMiniBar />
    </main>
    <BottomNav class="lg:hidden" />
  </div>
</template>
