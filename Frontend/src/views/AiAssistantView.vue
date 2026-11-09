<script setup>
import { computed, nextTick, onActivated, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import AiSettings from '@/components/ai/AiSettings.vue'
import AiQuotaNote from '@/components/ai/AiQuotaNote.vue'
import MaterialOutline from '@/components/ai/MaterialOutline.vue'
import BottomSheet from '@/components/common/BottomSheet.vue'
import AgentMessage from '@/components/ai/AgentMessage.vue'
import ChatAttachment from '@/components/ai/ChatAttachment.vue'
import ConversationList from '@/components/ai/ConversationList.vue'
import MicButton from '@/components/common/MicButton.vue'
import { FILE_ACCEPT, IMAGE_ACCEPT, useChatAttachments } from '@/composables/useChatAttachments'
import { useAiStore } from '@/stores/ai'
import { useAuthStore } from '@/stores/auth'
import { useUiStore } from '@/stores/ui'
import { friendlyLabel } from '@/utils/aiModels'

defineOptions({ name: 'AiAssistantView' })

const ai = useAiStore()
const auth = useAuthStore()
const ui = useUiStore()
const route = useRoute()
const router = useRouter()

const text = ref('')
const list = ref(null)
const box = ref(null)
const settingsOpen = ref(false)
// 上传讲义（PDF / PPT / Word / 文本） → 勾选章节 → 作为一条消息交给智能体排复习计划
const materialOpen = ref(false)
const planFromMaterial = (value) => {
  materialOpen.value = false
  send(value)
}
const drawer = ref(false)
const ready = ref(false)

// ---------------------------------------------------------------- 附件：+ 菜单选图片 / 文件，拖进对话区，或在输入框里粘贴截图
const tray = useChatAttachments(() => ai.currentId)
const imageInput = ref(null)
const fileInput = ref(null)
const menu = ref(false)
const menuBox = ref(null)
const pick = (input) => {
  menu.value = false
  input.value?.click()
}
const onPicked = (event) => {
  tray.add(event.target.files)
  event.target.value = ''
}
const openMaterial = () => {
  menu.value = false
  materialOpen.value = true
}
const closeMenu = (event) => {
  if (menu.value && !menuBox.value?.contains(event.target)) menu.value = false
}
const menuKey = (event) => event.key === 'Escape' && (menu.value = false)
onMounted(() => {
  document.addEventListener('pointerdown', closeMenu)
  document.addEventListener('keydown', menuKey)
})
onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', closeMenu)
  document.removeEventListener('keydown', menuKey)
})
const onPaste = (event) => {
  const files = [...(event.clipboardData?.items || [])].filter((i) => i.kind === 'file').map((i) => i.getAsFile()).filter(Boolean)
  if (!files.length) return
  event.preventDefault()
  tray.add(files)
}
// 拖文件进对话区：子元素之间移动也会触发 dragleave，按进出次数判断
const dragDepth = ref(0)
const hasFiles = (event) => [...(event.dataTransfer?.types || [])].includes('Files')
const onDragEnter = (event) => hasFiles(event) && !ai.streaming && dragDepth.value++
const onDragLeave = (event) => hasFiles(event) && (dragDepth.value = Math.max(0, dragDepth.value - 1))
const onDrop = (event) => {
  dragDepth.value = 0
  if (!ai.streaming) tray.add(event.dataTransfer?.files)
}
const canSend = computed(() => !ai.streaming && !tray.uploading.value && (text.value.trim() || tray.ready.value.length))

const SUGGESTIONS = [
  { icon: 'lucide:calendar-range', text: '帮我把这周的线代复习排一下' },
  { icon: 'lucide:book-open', text: '我周四晚上 11-12 节有一门数据库选修，1-16 周' },
  { icon: 'lucide:calendar-clock', text: '把明天的任务都往后挪一天' },
  { icon: 'lucide:lightbulb', text: '线性代数怎么复习比较高效？' },
  { icon: 'lucide:graduation-cap', text: '两周内准备期末考试，每天两小时' },
  { icon: 'lucide:play', text: '推荐几个 B 站的高数课程，放进这周的复习里' },
]

const lastAssistantId = computed(() => [...ai.messages].reverse().find((m) => m.role === 'assistant')?.id)
const title = computed(() => ai.current?.title || '新对话')

const scrollBottom = async (smooth = true) => {
  await nextTick()
  list.value?.scrollTo({ top: list.value.scrollHeight, behavior: smooth ? 'smooth' : 'auto' })
}
// 流式输出时只在用户本来就在底部附近时跟随，避免打断向上翻看
const nearBottom = () => !list.value || list.value.scrollHeight - list.value.scrollTop - list.value.clientHeight < 160
const streamSignature = computed(() => {
  const last = ai.messages[ai.messages.length - 1]
  return last ? `${ai.messages.length}:${last.content?.length || 0}:${last.meta?.reasoning?.length || 0}:${last.meta?.proposals?.length || 0}` : ''
})
watch(streamSignature, () => nearBottom() && scrollBottom(false))
watch(() => ai.currentId, () => scrollBottom(false))

const autosize = () => {
  const el = box.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = `${Math.min(el.scrollHeight, 144)}px`
}

const send = async (value = text.value) => {
  if (ai.streaming) return
  if (tray.uploading.value) return ui.toast('附件还在上传，稍等一下', 'info')
  const files = tray.snapshot()
  if (!value.trim() && !files.length) return
  const keep = value
  text.value = ''
  await nextTick()
  autosize()
  scrollBottom()
  const sent = await ai.send(value, files, () => tray.clearSent(files))
  // 没发出去（建对话失败）：把字放回输入框
  if (sent === false && !text.value) text.value = keep
}

const consumeQuery = async () => {
  const q = route.query.q
  if (typeof q === 'string' && q) {
    router.replace({ query: {} })
    await load()
    ai.newConversation()
    send(q)
  }
}

const load = async () => {
  if (ready.value) return
  ai.init(auth.user?.id)
  try {
    await ai.ensureLoaded()
  } catch (error) {
    ui.fail(error)
  } finally {
    ready.value = true
    scrollBottom(false)
  }
}

onMounted(load)
// KeepAlive 下 onActivated 在首次挂载时也会触发，只在这里处理 ?q=，避免重复发送
onActivated(consumeQuery)
</script>

<template>
  <div class="flex h-full">
    <!-- 电脑：左侧会话栏 -->
    <aside class="hidden w-64 shrink-0 flex-col border-r border-ink-line/70 bg-surface lg:flex">
      <div class="flex items-center gap-2 px-4 pb-1 pt-5">
        <div class="flex h-8 w-8 items-center justify-center rounded-xl bg-primary text-on-primary"><Icon icon="lucide:sparkles" width="16" /></div>
        <p class="text-sm font-black text-ink">AI 学习助手</p>
      </div>
      <ConversationList class="min-h-0 flex-1" />
    </aside>

    <!-- 手机：抽屉 -->
    <Transition name="fade">
      <div v-if="drawer" class="absolute inset-0 z-[60] lg:hidden" role="dialog" aria-modal="true" aria-label="对话列表">
        <div class="absolute inset-0 bg-scrim/45" @click="drawer = false" />
        <div class="absolute inset-y-0 left-0 flex w-[82%] max-w-[320px] flex-col bg-surface pt-[var(--safe-top)] shadow-2xl">
          <div class="flex items-center justify-between px-4 pt-4">
            <p class="text-base font-black text-ink">对话</p>
            <button class="flex h-8 w-8 items-center justify-center rounded-full bg-background text-ink-soft" type="button" aria-label="关闭" @click="drawer = false"><Icon icon="lucide:x" width="16" /></button>
          </div>
          <ConversationList class="min-h-0 flex-1" @picked="drawer = false" />
        </div>
      </div>
    </Transition>

    <div class="relative flex min-w-0 flex-1 flex-col" @dragenter.prevent="onDragEnter" @dragover.prevent @dragleave="onDragLeave" @drop.prevent="onDrop">
      <header class="glass-bar flex shrink-0 items-center gap-2 bg-surface px-4 pb-3 pt-[calc(var(--safe-top)+16px)] lg:border-b lg:border-ink-line/70 lg:px-8 lg:pt-4">
        <button class="icon-btn lg:hidden" type="button" aria-label="对话列表" @click="drawer = true"><Icon icon="lucide:menu" width="18" /></button>
        <button class="min-w-0 flex-1 text-left" type="button" @click="settingsOpen = true">
          <h1 class="truncate text-base font-black text-ink">{{ title }}</h1>
          <p class="flex items-center gap-1 text-[11px] font-semibold text-ink-mute">
            <span class="h-1.5 w-1.5 shrink-0 rounded-full" :class="ai.engine.provider === 'llm' ? 'bg-success' : 'bg-ink-mute'" />
            <span class="truncate">{{ friendlyLabel(ai.engine.label) }}<template v-if="ai.engine.thinking && ai.engine.thinking !== 'off'"> · 思考{{ ai.engine.thinking === 'max' ? '最高' : '高' }}</template></span>
            <AiQuotaNote :quota="ai.engine.quota" compact />
            <Icon icon="lucide:chevron-down" width="12" class="shrink-0" />
          </p>
        </button>
        <RouterLink v-if="ai.engine.provider === 'rule'" :to="{ name: 'manual', hash: '#rule-engine' }" class="icon-btn text-ink-mute" aria-label="本地规则引擎能听懂哪些写法" title="本地规则引擎能听懂哪些写法"><Icon icon="lucide:circle-help" width="18" /></RouterLink>
        <button class="icon-btn" type="button" aria-label="新对话" :disabled="ai.streaming" @click="ai.newConversation()"><Icon icon="lucide:square-pen" width="18" /></button>
        <button class="icon-btn" type="button" aria-label="模型设置" @click="settingsOpen = true"><Icon icon="lucide:settings-2" width="18" /></button>
      </header>

      <div ref="list" class="scrollbar-hide flex-1 overflow-y-auto px-4 py-4 lg:px-8 lg:py-6">
        <div class="space-y-4 lg:mx-auto lg:max-w-3xl">
          <div v-if="ai.loadingMessages && !ai.messages.length" class="space-y-3 pt-4">
            <div v-for="i in 3" :key="i" class="skeleton h-16" />
          </div>
          <div v-else-if="!ai.messages.length" class="animate-rise pt-6 text-center">
            <div class="mx-auto flex h-16 w-16 items-center justify-center rounded-3xl bg-primary-light text-primary"><Icon icon="lucide:calendar-heart" width="30" /></div>
            <h2 class="mt-4 text-lg font-black text-ink">想学什么、排什么，直接说</h2>
            <p class="mx-auto mt-1 max-w-[320px] text-xs leading-5 text-ink-mute">我会先看你的课表、已有任务和空闲时段，需要时追问你；排任务、加课程、改日程都会先给你一张卡片，确认后才导入。</p>
            <div class="mt-6 space-y-2 text-left lg:mx-auto lg:grid lg:max-w-2xl lg:grid-cols-2 lg:gap-3 lg:space-y-0">
              <button v-for="s in SUGGESTIONS" :key="s.text" class="flex w-full items-center gap-3 rounded-2xl bg-surface px-4 py-3 shadow-soft transition hover:ring-2 hover:ring-primary/20 active:scale-[.98]" type="button" :disabled="ai.streaming" @click="send(s.text)">
                <Icon :icon="s.icon" width="18" class="shrink-0 text-primary" />
                <span class="text-sm font-semibold text-ink">{{ s.text }}</span>
              </button>
            </div>
            <p class="mt-4 flex items-center justify-center gap-1.5 text-[11px] text-ink-mute">
              <Icon icon="lucide:paperclip" width="12" />点左下角 + 发图片或文件，也可以拖进来、直接粘贴截图
            </p>
          </div>

          <template v-for="msg in ai.messages" :key="msg.id">
            <div v-if="msg.role === 'user'" class="flex flex-col items-end gap-1.5">
              <div v-if="msg.attachments?.length" class="flex max-w-[86%] flex-wrap justify-end gap-1.5">
                <ChatAttachment v-for="file in msg.attachments" :key="file.id" :item="file" />
              </div>
              <p v-if="msg.content" class="max-w-[80%] whitespace-pre-wrap rounded-3xl rounded-br-md bg-primary px-4 py-2.5 text-sm text-on-primary shadow-lift">{{ msg.content }}</p>
            </div>
            <AgentMessage v-else :message="msg" :last="msg.id === lastAssistantId" />
          </template>
        </div>
      </div>

      <form class="shrink-0 border-t border-ink-line/70 bg-surface px-3 py-2.5 lg:px-8 lg:py-4" @submit.prevent="send()">
        <input ref="imageInput" type="file" :accept="IMAGE_ACCEPT" multiple class="hidden" @change="onPicked" />
        <input ref="fileInput" type="file" :accept="FILE_ACCEPT" multiple class="hidden" @change="onPicked" />

        <!-- 待发送的附件 -->
        <div v-if="tray.items.length" class="lg:mx-auto lg:max-w-3xl">
          <div class="scrollbar-hide -mx-3 flex gap-2.5 overflow-x-auto px-3 pb-2.5 pt-1.5 lg:mx-0 lg:px-0" aria-label="待发送的附件">
            <ChatAttachment v-for="item in tray.items" :key="item.key" :item="item" mode="tray" @remove="tray.remove(item)" @retry="tray.retry(item)" />
          </div>
          <p v-if="ai.engine.provider === 'rule'" class="-mt-1 mb-2 text-[11px] font-semibold text-primary">本地规则引擎读不了附件，请在右上角的模型设置里选择大模型</p>
        </div>

        <div class="flex items-end gap-2 lg:mx-auto lg:max-w-3xl">
          <div ref="menuBox" class="relative shrink-0">
            <button
              class="flex h-11 w-11 items-center justify-center rounded-2xl transition active:scale-95 disabled:opacity-40"
              :class="menu ? 'bg-primary text-on-primary' : 'bg-background text-ink-soft hover:bg-ink-line/60'"
              type="button"
              aria-label="添加图片或文件"
              aria-haspopup="menu"
              :aria-expanded="menu"
              :disabled="ai.streaming"
              @click="menu = !menu"
            >
              <Icon icon="lucide:plus" width="20" class="transition" :class="menu && 'rotate-45'" />
            </button>
            <Transition enter-active-class="transition duration-150" enter-from-class="translate-y-1 opacity-0" leave-active-class="transition duration-100" leave-to-class="opacity-0">
              <div v-if="menu" class="material absolute bottom-[52px] left-0 z-30 w-64 rounded-[22px] bg-surface p-1.5 shadow-2xl" role="menu">
                <button class="flex w-full items-center gap-3 rounded-2xl px-3 py-2.5 text-left hover:bg-background" type="button" role="menuitem" @click="pick(imageInput)">
                  <span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary-light text-primary"><Icon icon="lucide:image" width="17" /></span>
                  <span class="min-w-0"><b class="block text-sm font-bold text-ink">图片</b><small class="block text-[11px] text-ink-mute">照片、截图、拍的讲义或题目</small></span>
                </button>
                <button class="flex w-full items-center gap-3 rounded-2xl px-3 py-2.5 text-left hover:bg-background" type="button" role="menuitem" @click="pick(fileInput)">
                  <span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-idle text-idle-ink"><Icon icon="lucide:paperclip" width="17" /></span>
                  <span class="min-w-0"><b class="block text-sm font-bold text-ink">文件</b><small class="block text-[11px] text-ink-mute">PDF、Word、PPT、表格、文本</small></span>
                </button>
                <div class="mx-3 my-1 h-px bg-ink-line/70" />
                <button class="flex w-full items-center gap-3 rounded-2xl px-3 py-2.5 text-left hover:bg-background" type="button" role="menuitem" @click="openMaterial">
                  <span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-course text-course-icon"><Icon icon="lucide:list-tree" width="17" /></span>
                  <span class="min-w-0"><b class="block text-sm font-bold text-ink">按讲义章节排复习</b><small class="block text-[11px] text-ink-mute">勾选章节，估算时长后排进日程</small></span>
                </button>
              </div>
            </Transition>
          </div>
          <textarea
            ref="box"
            v-model="text"
            rows="1"
            class="field max-h-36 min-h-[44px] flex-1 resize-none py-2.5"
            :placeholder="tray.items.length ? '说说想让 AI 做什么，例如：讲讲这道题 / 总结重点 / 据此排复习' : '例如：这周每天 2 小时复习高数，晚上学'"
            maxlength="2000"
            aria-label="输入消息"
            @input="autosize"
            @paste="onPaste"
            @keydown.enter.exact.prevent="send()"
          />
          <MicButton v-model="text" :maxlength="2000" :disabled="ai.streaming" @update:model-value="nextTick(autosize)" />
          <button v-if="ai.streaming" class="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-inverse text-inverse-ink shadow-lift transition active:scale-95" type="button" aria-label="停止生成" @click="ai.stop()">
            <Icon icon="lucide:square" width="16" />
          </button>
          <button v-else class="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-primary text-on-primary shadow-lift transition active:scale-95 disabled:opacity-40" type="submit" :disabled="!canSend" :aria-label="tray.uploading.value ? '附件上传中' : '发送'">
            <Icon :icon="tray.uploading.value ? 'lucide:loader-circle' : 'lucide:send'" width="18" :class="tray.uploading.value && 'animate-spin'" />
          </button>
        </div>
      </form>

      <!-- 拖进来：整个对话区都能放 -->
      <div v-if="dragDepth > 0" class="pointer-events-none absolute inset-3 z-40 flex flex-col items-center justify-center gap-2 rounded-[28px] border-2 border-dashed border-primary bg-primary-light/90 text-primary">
        <Icon icon="lucide:upload" width="28" />
        <b class="text-base font-black">松开添加图片或文件</b>
        <small class="text-xs font-semibold opacity-80">图片、PDF、Word、PPT、表格，最多 4 个</small>
      </div>
    </div>

    <AiSettings :open="settingsOpen" @close="settingsOpen = false" />
    <BottomSheet :open="materialOpen" title="按讲义排复习" subtitle="上传 PDF / PPT / Word，勾选要复习的章节，AI 会结合你的空闲时段安排" @close="materialOpen = false">
      <MaterialOutline compact @plan="planFromMaterial" />
    </BottomSheet>
  </div>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
