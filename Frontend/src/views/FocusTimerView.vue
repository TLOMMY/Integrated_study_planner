<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import { taskApi } from '@/api'
import { useFocusStore } from '@/stores/focus'
import { useTasksStore } from '@/stores/tasks'
import { useUiStore } from '@/stores/ui'
import { FOCUS_MAX, FOCUS_MIN } from '@/utils/task'

const route = useRoute()
const router = useRouter()
const focus = useFocusStore()
const tasks = useTasksStore()
const ui = useUiStore()

const PRESETS = [5, 15, 25, 45, 60]
const QUOTES = [
  '把手机放远一点，世界会等你 25 分钟。',
  '慢慢来，比较快。',
  '先完成，再完美。',
  '专注当下这一小步。',
  '今天的你，比昨天多懂一点。',
]
const quote = QUOTES[new Date().getDate() % QUOTES.length]
const minutes = ref(25)
const customOpen = ref(false)
const customValue = ref('')
const isCustom = computed(() => !PRESETS.includes(minutes.value))
const openCustom = () => {
  customValue.value = String(minutes.value)
  customOpen.value = true
}
const applyCustom = () => {
  const value = Math.round(Number(customValue.value))
  if (!value || value < FOCUS_MIN || value > FOCUS_MAX) {
    ui.toast(`请输入 ${FOCUS_MIN}-${FOCUS_MAX} 之间的分钟数`, 'warning')
    return
  }
  minutes.value = value
  customOpen.value = false
}

const ring = computed(() => {
  const r = 118
  const c = 2 * Math.PI * r
  return { r, c, offset: c * (1 - focus.progress) }
})

const label = computed(() => ({ idle: '准备开始', running: '专注中', paused: '已暂停', finished: '本次完成' })[focus.status])

onMounted(async () => {
  focus.restore()
  if (focus.active) {
    minutes.value = focus.plannedMinutes
    if (route.query.taskId && Number(route.query.taskId) !== focus.task?.id) ui.toast('已有进行中的专注，先完成当前这一轮', 'warning')
    return
  }
  const fromQuery = Math.round(Number(route.query.minutes))
  minutes.value = fromQuery >= FOCUS_MIN && fromQuery <= FOCUS_MAX ? fromQuery : 25
  let task = null
  if (route.query.taskId) {
    task = await taskApi.detail(route.query.taskId).catch(() => null)
  }
  focus.setup({ task: task && { id: task.id, title: task.title, subject: task.subject }, minutes: minutes.value })
})

watch(minutes, (value) => {
  if (focus.status === 'idle') focus.plannedMinutes = value
})

const finishEarly = async () => {
  const done = Math.floor(focus.elapsedMs / 60000)
  const ok = await ui.confirm({
    title: '提前结束？',
    message: done >= 1 ? `将按实际专注的 ${done} 分钟记录，不计完整番茄奖励。` : '专注不足 1 分钟，本次不会记录。',
    confirmText: '结束并记录',
  })
  if (ok) await focus.finish(false)
}

const giveUp = async () => {
  if (focus.status === 'idle' || focus.status === 'finished') return leave()
  const ok = await ui.confirm({ title: '放弃本次专注？', message: '已专注的时间不会被记录。', confirmText: '放弃', danger: true })
  if (ok) {
    focus.abandon()
    leave()
  }
}

const markTaskDone = async () => {
  const task = focus.lastResult?.task
  if (!task || task.completed) return
  const copy = { ...task }
  if (await tasks.toggle(copy)) focus.lastResult.task = copy
}

const again = () => {
  const task = focus.task
  focus.setup({ task, minutes: minutes.value })
}

const leave = () => (window.history.length > 1 ? router.back() : router.replace('/today-task'))
</script>

<template>
  <div class="relative flex h-full flex-col overflow-hidden bg-gradient-to-b from-[#1E2A5E] via-[#26357A] to-[#3B2C7A] text-white">
    <div class="pointer-events-none absolute -left-24 -top-24 h-72 w-72 rounded-full bg-primary/30 blur-3xl" />
    <div class="pointer-events-none absolute -bottom-24 -right-24 h-72 w-72 rounded-full bg-xp/30 blur-3xl" />

    <header class="relative flex items-center justify-between px-5 pt-[calc(var(--safe-top)+18px)]">
      <button class="flex h-10 w-10 items-center justify-center rounded-full bg-white/10" type="button" aria-label="返回" @click="leave">
        <Icon icon="lucide:chevron-down" width="22" />
      </button>
      <div class="text-center">
        <p class="text-[10px] font-bold tracking-[0.3em] text-white/50">FOCUS</p>
        <p class="max-w-[200px] truncate text-sm font-bold">{{ focus.task?.title || '自由专注' }}</p>
      </div>
      <span class="w-10" />
    </header>

    <main class="relative flex flex-1 flex-col items-center justify-center px-8">
      <div class="relative">
        <svg width="260" height="260" class="-rotate-90">
          <circle cx="130" cy="130" :r="ring.r" fill="none" stroke="rgba(255,255,255,.12)" stroke-width="10" />
          <circle
            cx="130"
            cy="130"
            :r="ring.r"
            fill="none"
            stroke="url(#focus-gradient)"
            stroke-width="10"
            stroke-linecap="round"
            :stroke-dasharray="ring.c"
            :stroke-dashoffset="ring.offset"
            style="transition: stroke-dashoffset 0.5s linear"
          />
          <defs>
            <linearGradient id="focus-gradient" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stop-color="#9DB0FF" />
              <stop offset="100%" stop-color="#FFB86B" />
            </linearGradient>
          </defs>
        </svg>
        <div class="absolute inset-0 flex flex-col items-center justify-center">
          <span class="num text-[64px] font-black leading-none tracking-tight">{{ focus.status === 'idle' ? `${String(focus.plannedMinutes).padStart(2, '0')}:00` : focus.clock }}</span>
          <span class="mt-2 flex items-center gap-1.5 text-xs font-bold text-white/60">
            <span v-if="focus.status === 'running'" class="h-1.5 w-1.5 animate-pulse rounded-full bg-flame" />{{ label }}
          </span>
        </div>
      </div>

      <!-- 选择时长 -->
      <div v-if="focus.status === 'idle'" class="mt-10 flex flex-col items-center gap-3">
        <div class="flex flex-wrap justify-center gap-2">
          <button
            v-for="m in PRESETS"
            :key="m"
            type="button"
            class="num rounded-2xl px-3.5 py-2 text-sm font-black transition"
            :class="minutes === m ? 'bg-white text-[#26357A]' : 'bg-white/10 text-white/80 hover:bg-white/20'"
            @click="minutes = m; customOpen = false"
          >
            {{ m }}'
          </button>
          <button
            type="button"
            class="flex items-center gap-1 rounded-2xl px-3.5 py-2 text-sm font-black transition"
            :class="isCustom ? 'bg-white text-[#26357A]' : 'bg-white/10 text-white/80 hover:bg-white/20'"
            :aria-expanded="customOpen"
            @click="openCustom"
          >
            <Icon icon="lucide:pencil" width="13" />{{ isCustom ? `${minutes}'` : '自定义' }}
          </button>
        </div>
        <form v-if="customOpen" class="flex items-center gap-2" @submit.prevent="applyCustom">
          <input
            v-model="customValue"
            type="number"
            inputmode="numeric"
            :min="FOCUS_MIN"
            :max="FOCUS_MAX"
            class="num w-24 rounded-2xl bg-white/15 px-3 py-2 text-center text-base font-black text-white outline-none ring-white/40 placeholder:text-white/40 focus:ring-2"
            placeholder="分钟"
            aria-label="自定义专注分钟数"
            autofocus
          />
          <span class="text-sm text-white/70">分钟</span>
          <button class="rounded-2xl bg-white px-3.5 py-2 text-sm font-black text-[#26357A]" type="submit">确定</button>
        </form>
      </div>

      <!-- 完成结果 -->
      <div v-else-if="focus.status === 'finished'" class="mt-8 w-full animate-rise rounded-3xl bg-white/10 p-4 text-center backdrop-blur">
        <p class="text-lg font-black">
          {{ focus.lastResult?.minutes ? `专注了 ${focus.lastResult.minutes} 分钟` : '本次未计入' }}
        </p>
        <p v-if="focus.lastResult?.task?.focus_minutes" class="mt-1 text-xs text-white/60">「{{ focus.lastResult.task.title }}」累计专注 {{ focus.lastResult.task.focus_minutes }} 分钟</p>
        <button v-if="focus.lastResult?.pending" class="btn mt-3 bg-white/20 text-white" type="button" :disabled="focus.saving" @click="focus.retrySave()">
          <Icon icon="lucide:refresh-cw" width="16" />{{ focus.saving ? '保存中…' : '网络异常，重试保存' }}
        </button>
        <button
          v-else-if="focus.lastResult?.task && !focus.lastResult.task.completed"
          class="btn mt-3 bg-success text-white"
          type="button"
          @click="markTaskDone"
        >
          <Icon icon="lucide:check" width="16" />这个任务已经完成了
        </button>
      </div>

      <p v-else class="mt-10 max-w-[260px] text-center text-sm italic leading-6 text-white/60">{{ quote }}</p>
    </main>

    <footer class="relative space-y-3 px-6 pb-[calc(var(--safe-bottom)+28px)]">
      <template v-if="focus.status === 'idle'">
        <button class="btn w-full bg-white py-4 text-base text-[#26357A] shadow-xl" type="button" @click="focus.start()">
          <Icon icon="lucide:play" width="20" />开始专注 {{ focus.plannedMinutes }} 分钟
        </button>
      </template>
      <template v-else-if="focus.active">
        <button class="btn w-full bg-white py-4 text-base text-[#26357A] shadow-xl" type="button" @click="focus.status === 'running' ? focus.pause() : focus.resume()">
          <Icon :icon="focus.status === 'running' ? 'lucide:pause' : 'lucide:play'" width="20" />{{ focus.status === 'running' ? '暂停' : '继续' }}
        </button>
        <div class="grid grid-cols-2 gap-3">
          <button class="btn bg-white/10 text-white/80" type="button" @click="giveUp">放弃</button>
          <button class="btn bg-white/10 text-white" type="button" @click="finishEarly">提前完成</button>
        </div>
      </template>
      <template v-else>
        <div class="grid grid-cols-2 gap-3">
          <button class="btn bg-white/10 text-white" type="button" @click="again"><Icon icon="lucide:rotate-ccw" width="16" />再来一轮</button>
          <button class="btn bg-white text-[#26357A]" type="button" @click="focus.abandon(); leave()">完成</button>
        </div>
      </template>
    </footer>
  </div>
</template>
