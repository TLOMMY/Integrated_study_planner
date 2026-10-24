<script setup>
import { nextTick, onActivated, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import PlanDraftCard from '@/components/ai/PlanDraftCard.vue'
import AiSettings from '@/components/ai/AiSettings.vue'
import MarkdownText from '@/components/ai/MarkdownText.vue'
import { useAiStore } from '@/stores/ai'
import { useAuthStore } from '@/stores/auth'
import { useUiStore } from '@/stores/ui'

defineOptions({ name: 'AiAssistantView' })

const ai = useAiStore()
const auth = useAuthStore()
const ui = useUiStore()
const route = useRoute()
const router = useRouter()

const text = ref('')
const list = ref(null)
const settingsOpen = ref(false)

const SUGGESTIONS = [
  { icon: 'lucide:moon', text: '帮我安排今晚的复习' },
  { icon: 'lucide:graduation-cap', text: '两周内准备期末考试，每天两小时' },
  { icon: 'lucide:calendar-range', text: '这周每天一个半小时复习高数和英语，晚上学' },
  { icon: 'lucide:feather', text: '明天轻松一点，复习一下物理' },
]

const scrollBottom = async () => {
  await nextTick()
  list.value?.scrollTo({ top: list.value.scrollHeight, behavior: 'smooth' })
}

const send = async (value = text.value) => {
  if (!value.trim() || ai.thinking) return
  text.value = ''
  await ai.ask(value)
}

const clear = async () => {
  if (await ui.confirm({ title: '清空对话', message: '已采纳的计划不受影响。', confirmText: '清空' })) ai.clear()
}

const consumeQuery = () => {
  const q = route.query.q
  if (typeof q === 'string' && q) {
    router.replace({ query: {} })
    send(q)
  }
}

watch(() => [ai.messages.length, ai.thinking], scrollBottom)
onMounted(() => {
  ai.init(auth.user?.id)
  scrollBottom()
})
// KeepAlive 下 onActivated 在首次挂载时也会触发，只在这里处理 ?q=，避免重复发送
onActivated(consumeQuery)
</script>

<template>
  <div class="flex h-full flex-col">
    <header class="flex shrink-0 items-center justify-between bg-surface px-5 pb-3 pt-[calc(var(--safe-top)+16px)] lg:border-b lg:border-ink-line/70 lg:px-10 lg:pt-5">
      <div class="flex items-center gap-3">
        <div class="flex h-10 w-10 items-center justify-center rounded-2xl bg-gradient-to-br from-primary to-xp text-white shadow-lift">
          <Icon icon="lucide:sparkles" width="20" />
        </div>
        <button class="min-w-0 text-left" type="button" @click="settingsOpen = true">
          <h1 class="text-base font-black text-ink">AI 学习规划</h1>
          <p class="flex max-w-[200px] items-center gap-1 lg:max-w-[420px] text-[11px] font-semibold text-ink-mute">
            <span class="h-1.5 w-1.5 shrink-0 rounded-full" :class="ai.engine.provider === 'llm' ? 'bg-success' : 'bg-ink-mute'" />
            <span class="truncate">{{ ai.engine.label }}</span>
            <Icon icon="lucide:chevron-down" width="12" class="shrink-0" />
          </p>
        </button>
      </div>
      <div class="flex gap-2">
        <button v-if="ai.messages.length" class="icon-btn" type="button" aria-label="清空对话" @click="clear"><Icon icon="lucide:eraser" width="18" /></button>
        <button class="icon-btn" type="button" aria-label="模型设置" @click="settingsOpen = true"><Icon icon="lucide:settings-2" width="18" /></button>
      </div>
    </header>

    <div ref="list" class="scrollbar-hide flex-1 overflow-y-auto px-4 py-4 lg:px-10 lg:py-8">
     <div class="space-y-4 lg:mx-auto lg:max-w-3xl">
      <div v-if="!ai.messages.length" class="animate-rise pt-6 text-center">
        <div class="mx-auto flex h-16 w-16 items-center justify-center rounded-3xl bg-primary-light text-primary"><Icon icon="lucide:calendar-heart" width="30" /></div>
        <h2 class="mt-4 text-lg font-black text-ink">说出你的学习目标</h2>
        <p class="mx-auto mt-1 max-w-[280px] text-xs leading-5 text-ink-mute">我会读取你的课表和已有任务，只在空闲时段里按番茄节奏排程。满意后一键加入日程。</p>
        <div class="mt-6 space-y-2 text-left lg:mx-auto lg:grid lg:max-w-2xl lg:grid-cols-2 lg:gap-3 lg:space-y-0">
          <button v-for="s in SUGGESTIONS" :key="s.text" class="flex w-full items-center gap-3 rounded-2xl bg-surface px-4 py-3 shadow-soft transition hover:ring-2 hover:ring-primary/20 active:scale-[.98]" type="button" @click="send(s.text)">
            <Icon :icon="s.icon" width="18" class="shrink-0 text-primary" />
            <span class="text-sm font-semibold text-ink">{{ s.text }}</span>
          </button>
        </div>
      </div>

      <template v-for="msg in ai.messages" :key="msg.id">
        <div v-if="msg.role === 'user'" class="flex justify-end">
          <p class="max-w-[80%] rounded-3xl rounded-br-md bg-primary px-4 py-2.5 text-sm text-white shadow-lift">{{ msg.text }}</p>
        </div>
        <div v-else class="space-y-2">
          <div class="flex gap-2">
            <div class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary-light text-primary"><Icon icon="lucide:bot" width="16" /></div>
            <p v-if="msg.error || !msg.draft" class="max-w-[85%] rounded-3xl rounded-tl-md px-4 py-2.5 text-sm leading-6" :class="msg.error ? 'bg-danger-light text-danger' : 'bg-surface text-ink shadow-soft'">{{ msg.text }}</p>
            <!-- 第一部分：写给学生的学习建议 -->
            <div v-else class="max-w-[85%] rounded-3xl rounded-tl-md bg-surface px-4 py-3 shadow-soft">
              <p class="mb-1.5 flex items-center gap-1 text-[10px] font-bold text-primary"><Icon icon="lucide:lightbulb" width="12" />学习建议 · {{ msg.draft.model }}</p>
              <MarkdownText :text="msg.draft.advice" />
              <p v-if="msg.draft.fallback_reason" class="mt-2 rounded-xl bg-flame-light px-3 py-1.5 text-[11px] font-semibold text-flame">
                模型未能生成（{{ msg.draft.fallback_reason }}），本次由规则引擎完成
              </p>
            </div>
          </div>
          <!-- 第二部分：结构化计划，可直接导入日程与课表 -->
          <PlanDraftCard v-if="msg.draft" :message="msg" class="ml-9" />
        </div>
      </template>

      <div v-if="ai.thinking" class="flex gap-2">
        <div class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary-light text-primary"><Icon icon="lucide:bot" width="16" /></div>
        <div class="flex items-center gap-1 rounded-3xl rounded-tl-md bg-surface px-4 py-3 shadow-soft">
          <span v-for="i in 3" :key="i" class="h-1.5 w-1.5 animate-bounce rounded-full bg-primary" :style="{ animationDelay: `${i * 0.15}s` }" />
          <span class="ml-2 text-xs text-ink-mute">正在读取课表与空闲时段…</span>
        </div>
      </div>
     </div>
    </div>

    <form class="shrink-0 border-t border-ink-line/70 bg-surface px-3 py-2.5 lg:px-10 lg:py-4" @submit.prevent="send()">
      <div class="flex items-end gap-2 lg:mx-auto lg:max-w-3xl">
        <textarea
          v-model="text"
          rows="1"
          class="field max-h-28 min-h-[44px] flex-1 resize-none py-2.5"
          placeholder="例如：这周每天2小时复习高数，晚上学"
          maxlength="500"
          aria-label="输入学习需求"
          @keydown.enter.exact.prevent="send()"
        />
        <button class="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-primary text-white shadow-lift transition active:scale-95 disabled:opacity-40" type="submit" :disabled="!text.trim() || ai.thinking" aria-label="发送">
          <Icon :icon="ai.thinking ? 'lucide:loader-circle' : 'lucide:send'" width="18" :class="ai.thinking && 'animate-spin'" />
        </button>
      </div>
    </form>

    <AiSettings :open="settingsOpen" @close="settingsOpen = false" />
  </div>
</template>
