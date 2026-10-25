<script setup>
/** 一条助手消息：可折叠的思考过程 + 工具调用、正文（Markdown）、追问选项、提案卡片。 */
import { computed, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import MarkdownText from './MarkdownText.vue'
import TaskProposalCard from './TaskProposalCard.vue'
import CourseProposalCard from './CourseProposalCard.vue'
import ChangeProposalCard from './ChangeProposalCard.vue'
import { useAiStore } from '@/stores/ai'

const props = defineProps({
  message: { type: Object, required: true },
  // 只有最后一条助手消息的追问选项可以点
  last: { type: Boolean, default: false },
})
const ai = useAiStore()

const meta = computed(() => props.message.meta || {})
const tools = computed(() => meta.value.tools || [])
const proposals = computed(() => meta.value.proposals || [])
const asks = computed(() => proposals.value.filter((p) => p.type === 'ask'))
const cards = computed(() => proposals.value.filter((p) => p.type !== 'ask'))
const reasoning = computed(() => meta.value.reasoning || '')
const hasTrace = computed(() => reasoning.value || tools.value.length)
// 生成中默认展开，结束后自动收起
const open = ref(Boolean(props.message.live))
watch(() => props.message.live, (live) => {
  if (!live) open.value = false
})
const traceLabel = computed(() => {
  if (props.message.live && !props.message.content) return props.message.status || '正在思考…'
  const parts = []
  if (reasoning.value) parts.push('思考过程')
  if (tools.value.length) parts.push(`${tools.value.length} 次工具调用`)
  return parts.join(' · ')
})
// 正文与追问问题相同时不重复显示
const content = computed(() => {
  const text = (props.message.content || '').trim()
  return asks.value.some((a) => a.question.trim() === text) ? '' : text
})
const engineNote = computed(() => {
  if (meta.value.engine === 'rule') return '本地规则引擎'
  if (meta.value.engine === 'draft') return '简化规划模式'
  return ''
})
const toolIcon = (t) => (t.status === 'running' ? 'lucide:loader-circle' : t.summary?.startsWith('失败') ? 'lucide:circle-x' : 'lucide:check')
</script>

<template>
  <div class="flex gap-2">
    <div class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary-light text-primary"><Icon icon="lucide:bot" width="16" /></div>
    <div class="min-w-0 max-w-[92%] flex-1 space-y-2 lg:max-w-[85%]">
      <!-- 思考过程 + 工具调用 -->
      <div v-if="hasTrace || message.live" class="rounded-2xl border border-ink-line/70 bg-surface/60">
        <button type="button" class="flex w-full items-center gap-1.5 px-3 py-2 text-left text-[11px] font-bold text-ink-mute" :aria-expanded="open" @click="open = !open">
          <Icon :icon="message.live ? 'lucide:loader-circle' : 'lucide:brain'" width="14" :class="message.live && 'animate-spin text-primary'" />
          <span class="min-w-0 flex-1 truncate">{{ traceLabel || '思考中' }}</span>
          <Icon v-if="hasTrace" :icon="open ? 'lucide:chevron-up' : 'lucide:chevron-down'" width="14" />
        </button>
        <div v-if="open && hasTrace" class="space-y-2 border-t border-ink-line/60 px-3 py-2">
          <ul v-if="tools.length" class="space-y-1">
            <li v-for="(t, i) in tools" :key="t.id || i" class="flex items-center gap-1.5 text-[11px] text-ink-soft">
              <Icon :icon="toolIcon(t)" width="12" :class="t.status === 'running' ? 'animate-spin text-primary' : 'text-success'" />
              <span class="font-semibold">{{ t.label }}</span><span v-if="t.summary" class="truncate text-ink-mute">· {{ t.summary }}</span>
            </li>
          </ul>
          <p v-if="reasoning" class="max-h-48 overflow-y-auto whitespace-pre-wrap text-[11px] leading-5 text-ink-mute">{{ reasoning }}<template v-if="!message.live && meta.reasoning_chars > reasoning.length">…</template></p>
        </div>
      </div>

      <!-- 正文 -->
      <div v-if="content || (message.live && !hasTrace)" class="rounded-3xl rounded-tl-md bg-surface px-4 py-3 shadow-soft">
        <MarkdownText v-if="content" :text="content" />
        <span v-else class="flex items-center gap-1">
          <span v-for="i in 3" :key="i" class="h-1.5 w-1.5 animate-bounce rounded-full bg-primary" :style="{ animationDelay: `${i * 0.15}s` }" />
          <span class="ml-2 text-xs text-ink-mute">{{ message.status || '正在思考…' }}</span>
        </span>
        <span v-if="message.live && content" class="ml-0.5 inline-block h-3.5 w-1.5 animate-pulse rounded-sm bg-primary align-middle" />
        <p v-if="engineNote && !message.live" class="mt-2 text-[10px] font-semibold text-ink-mute">{{ engineNote }}<template v-if="meta.model"> · {{ meta.model }}</template></p>
      </div>
      <p v-if="meta.notice" class="rounded-xl bg-flame-light px-3 py-1.5 text-[11px] font-semibold text-flame">{{ meta.notice }}</p>
      <p v-if="meta.error" class="rounded-xl bg-danger-light px-3 py-1.5 text-[11px] font-semibold text-danger">{{ meta.error }}</p>

      <!-- 追问 -->
      <div v-for="a in asks" :key="a.id" class="rounded-3xl border border-primary/30 bg-primary-light/40 px-4 py-3">
        <p class="flex gap-1.5 text-sm font-bold text-ink"><Icon icon="lucide:message-circle-question" width="16" class="mt-0.5 shrink-0 text-primary" />{{ a.question }}</p>
        <div v-if="a.options?.length" class="mt-2 flex flex-wrap gap-1.5">
          <button
            v-for="o in a.options"
            :key="o"
            type="button"
            class="chip"
            :class="a.answered === o && 'chip-active'"
            :disabled="!last || ai.streaming || Boolean(a.answered)"
            @click="ai.answer(a, o)"
          >{{ o }}</button>
        </div>
        <p v-if="last && !a.answered" class="mt-1.5 text-[10px] text-ink-mute">点选一个，或者直接在下方输入</p>
      </div>

      <!-- 提案卡片 -->
      <template v-for="p in cards" :key="p.id">
        <TaskProposalCard v-if="p.type === 'tasks'" :message="message" :proposal="p" />
        <CourseProposalCard v-else-if="p.type === 'courses'" :message="message" :proposal="p" />
        <ChangeProposalCard v-else-if="p.type === 'changes'" :message="message" :proposal="p" />
      </template>
    </div>
  </div>
</template>
