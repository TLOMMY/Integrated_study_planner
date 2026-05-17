<script setup>
import { computed, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import { useFocusStore } from '@/stores/focusStore'

const router = useRouter()
const focusStore = useFocusStore()

/**
 * computed
 */
const focusTask = computed(() => focusStore.focusTask)

const quote = computed(() => focusStore.quote)

const minutes = computed(() => focusStore.minutes)

const seconds = computed(() => focusStore.seconds)

const isPaused = computed(() => focusStore.isPaused)

const progress = computed(() => focusStore.progress)

/**
 * 暂停 / 继续
 */
const togglePause = () => {
  if (focusStore.isPaused) {
    focusStore.resumeTimer()
  } else {
    focusStore.pauseTimer()
  }
}

/**
 * 完成专注
 */
const finishFocus = async () => {
  await focusStore.finishTimer()

  alert('专注完成！')

  router.push('/')
}

/**
 * 返回
 */
const goBack = () => {
  focusStore.resetTimer()

  router.push('/')
}

/**
 * 页面挂载
 */
onMounted(() => {
  /**
   * 恢复 session
   */
  focusStore.restoreSession()

  /**
   * 自动继续
   */
  if (!focusStore.isPaused) {
    focusStore.startTimer()
  }
})

/**
 * 页面卸载
 */
onBeforeUnmount(() => {
  /**
   * 不需要 clearInterval
   * store 自己管理 timer
   */
})
</script>

<template>
  <div
    class="relative w-full h-full overflow-hidden bg-gradient-to-b from-slate-900 to-slate-950 text-white"
  >
    <div class="h-full flex flex-col px-8 pt-10 pb-24">
      <!-- 顶部 -->
      <div class="flex justify-between items-center">
        <button
          class="w-10 h-10 rounded-full bg-white/5 flex items-center justify-center"
          @click="goBack"
        >
          <Icon icon="lucide:chevron-left" width="24" />
        </button>

        <div class="flex flex-col items-center">
          <span
            class="text-[10px] font-bold text-gray-500 uppercase tracking-widest"
          >
            正在专注
          </span>

          <span class="text-sm font-bold text-blue-400 mt-1">
            {{ focusTask }}
          </span>
        </div>

        <div
          class="w-10 h-10 rounded-full bg-white/5 flex items-center justify-center"
        >
          <Icon icon="lucide:bell-off" width="20" />
        </div>
      </div>

      <!-- 中间 -->
      <div class="flex-1 flex flex-col items-center justify-center">
        <div
          class="timer-circle glow"
          :style="{
            background: `conic-gradient(
              #3b82f6 ${progress * 3.6}deg,
              rgba(255,255,255,0.05) 0deg
            )`,
          }"
        >
          <div class="timer-inner">
           <h2 class="timer-display text-6xl font-black tracking-tighter text-slate-900">
                <span>{{ minutes }}</span>

               <span class="text-blue-600 mx-0.5">:</span>

               <span>{{ seconds }}</span>
          </h2>

            <p
             class="timer-label text-[10px] text-slate-500 font-bold uppercase"
             >
              剩余时间
            </p>
          </div>
        </div>

        <div class="mt-12 text-center">
          <div
            class="inline-flex items-center gap-2 bg-blue-500/10 px-4 py-2 rounded-full border border-blue-500/20 mb-4"
          >
            <span
              class="w-1.5 h-1.5 bg-blue-500 rounded-full animate-pulse"
            ></span>

           <span class="text-[10px] font-bold text-blue-400">
           深度模式已开启
           </span>
          </div>

          <p class="text-sm text-gray-400 px-10 italic leading-relaxed">
            {{ quote }}
          </p>
        </div>
      </div>

      <!-- 底部 -->
      <div class="space-y-4">
        <button
          class="w-full py-5 bg-white text-slate-900 rounded-3xl font-bold flex items-center justify-center gap-2 shadow-xl shadow-white/10"
          @click="togglePause"
        >
          <Icon
            :icon="isPaused ? 'lucide:play' : 'lucide:pause'"
            width="20"
          />

          {{ isPaused ? '继续专注' : '暂停专注' }}
        </button>

        <div class="flex gap-4">
          <button
            class="flex-1 py-4 bg-white/5 text-white/40 rounded-3xl font-bold text-sm border border-white/5"
            @click="goBack"
          >
            放弃
          </button>

          <button
            class="flex-1 py-4 bg-blue-600/20 text-blue-400 rounded-3xl font-bold text-sm border border-blue-500/20"
            @click="finishFocus"
          >
            完成
          </button>
        </div>

        <!-- 底部装饰 -->
        <div class="pt-2 flex gap-2 justify-center">
          <div class="w-1 h-1 bg-white/20 rounded-full"></div>
          <div class="w-1 h-1 bg-white/60 rounded-full"></div>
          <div class="w-1 h-1 bg-white/20 rounded-full"></div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.timer-circle {
  width: 240px;
  height: 240px;
  border-radius: 9999px;
  padding: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.3s ease;
}

.timer-inner {
  width: 100%;
  height: 100%;
  border-radius: 9999px;
  background: white;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.timer-display {
  display: flex;
  align-items: center;
  justify-content: center;
  font-variant-numeric: tabular-nums;
  line-height: 1.1;
  margin-bottom: 4px;
}

.timer-label {
  line-height: 1;
  letter-spacing: 4px;
  margin-top: 4px;
}

.glow {
  box-shadow: 0 0 40px rgba(59, 130, 246, 0.25);
}
</style>