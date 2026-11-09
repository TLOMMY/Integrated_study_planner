<script setup>
/**
 * 一个对话附件。mode：tray（输入框上方，待发送：进度、失败重试、删除）/ message（已发送的消息里）。
 * 图片是方形缩略图，点开放大；文件是卡片：类型色块 + 文件名 + 类型 · 页数 · 大小。
 * 已发送的图片需要登录才能看：以 Blob 取回再显示；待发送的直接用本地地址。
 */
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import { agentApi } from '@/api/agent'

const props = defineProps({
  item: { type: Object, required: true },
  mode: { type: String, default: 'message' },
})
const emit = defineEmits(['remove', 'retry'])

const TYPES = [
  { test: /\.pdf$/i, label: 'PDF', icon: 'lucide:file-text', tile: 'bg-danger-light text-danger' },
  { test: /\.docx$/i, label: 'Word', icon: 'lucide:file-type', tile: 'bg-idle text-idle-ink' },
  { test: /\.pptx$/i, label: 'PPT', icon: 'lucide:presentation', tile: 'bg-primary-light text-primary' },
  { test: /\.(xlsx|xls|csv)$/i, label: '表格', icon: 'lucide:sheet', tile: 'bg-success-light text-success' },
  { test: /\.(md|markdown)$/i, label: 'Markdown', icon: 'lucide:file-code', tile: 'bg-course text-course-icon' },
]
const type = computed(() => TYPES.find((t) => t.test.test(props.item.name || '')) || { label: '文本', icon: 'lucide:file', tile: 'bg-course text-course-icon' })
const isImage = computed(() => props.item.kind === 'image')
const tray = computed(() => props.mode === 'tray')
const status = computed(() => props.item.status || 'ready')

const sizeText = (bytes) => {
  if (!bytes) return ''
  return bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`
}
const subtitle = computed(() => {
  if (status.value === 'uploading') return `上传中 ${props.item.progress || 0}%`
  if (status.value === 'error') return props.item.error || '上传失败'
  const parts = [type.value.label, props.item.pages ? `${props.item.pages} ${type.value.label === 'PPT' ? '张' : '页'}` : '', sizeText(props.item.size)]
  if (props.item.scanned) parts.push('扫描件，发送后识别')
  return parts.filter(Boolean).join(' · ')
})

// ---------------------------------------------------------------- 图片
const remote = ref('')
const failed = ref(false)
const zoom = ref(false)
const src = computed(() => props.item.localUrl || remote.value)
const load = async () => {
  if (!isImage.value || props.item.localUrl || !props.item.id) return
  failed.value = false
  try {
    const blob = await agentApi.attachmentContent(props.item.id)
    if (remote.value) URL.revokeObjectURL(remote.value)
    remote.value = URL.createObjectURL(blob)
  } catch {
    failed.value = true
  }
}
watch(() => [props.item.id, props.item.localUrl], load, { immediate: true })
onBeforeUnmount(() => remote.value && URL.revokeObjectURL(remote.value))
</script>

<template>
  <!-- 图片 -->
  <div v-if="isImage" class="relative shrink-0">
    <button
      type="button"
      class="block overflow-hidden rounded-2xl border border-ink-line/70 bg-background"
      :class="tray ? 'h-16 w-16' : 'h-28 w-28 lg:h-32 lg:w-32'"
      :aria-label="`查看图片 ${item.name}`"
      @click="src && (zoom = true)"
    >
      <img v-if="src" :src="src" :alt="item.name" class="h-full w-full object-cover" />
      <span v-else class="flex h-full w-full items-center justify-center text-ink-mute">
        <Icon :icon="failed ? 'lucide:image-off' : 'lucide:loader-circle'" width="18" :class="!failed && 'animate-spin'" />
      </span>
    </button>
    <span v-if="tray && status === 'uploading'" class="num pointer-events-none absolute inset-0 flex items-center justify-center rounded-2xl bg-scrim/45 text-xs font-black text-on-primary">
      {{ item.progress || 0 }}%
    </span>
    <button
      v-if="tray && status === 'error'"
      type="button"
      class="absolute inset-0 flex flex-col items-center justify-center gap-0.5 rounded-2xl bg-danger-light/90 text-[10px] font-bold text-danger"
      :title="item.error"
      @click="emit('retry')"
    >
      <Icon icon="lucide:rotate-cw" width="15" />重试
    </button>
    <button
      v-if="tray"
      type="button"
      class="absolute -right-1.5 -top-1.5 flex h-6 w-6 items-center justify-center rounded-full bg-inverse text-inverse-ink shadow-soft"
      :aria-label="`移除 ${item.name}`"
      @click="emit('remove')"
    >
      <Icon icon="lucide:x" width="13" />
    </button>
  </div>

  <!-- 文件 -->
  <div
    v-else
    class="relative flex shrink-0 items-center gap-2.5 rounded-2xl border bg-surface p-2 pr-3"
    :class="[tray ? 'h-16 w-[208px]' : 'w-[240px] max-w-full', status === 'error' ? 'border-danger/40' : 'border-ink-line/70']"
  >
    <span class="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl" :class="type.tile">
      <Icon v-if="status === 'uploading'" icon="lucide:loader-circle" width="18" class="animate-spin" />
      <Icon v-else :icon="type.icon" width="19" />
    </span>
    <span class="grid min-w-0 flex-1 gap-0.5 text-left">
      <b class="truncate text-[13px] font-bold text-ink" :title="item.name">{{ item.name }}</b>
      <small class="num truncate text-[11px]" :class="status === 'error' ? 'font-semibold text-danger' : 'text-ink-mute'">{{ subtitle }}</small>
    </span>
    <button v-if="tray && status === 'error'" type="button" class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-danger hover:bg-danger-light" aria-label="重试上传" @click="emit('retry')">
      <Icon icon="lucide:rotate-cw" width="14" />
    </button>
    <button
      v-if="tray"
      type="button"
      class="absolute -right-1.5 -top-1.5 flex h-6 w-6 items-center justify-center rounded-full bg-inverse text-inverse-ink shadow-soft"
      :aria-label="`移除 ${item.name}`"
      @click="emit('remove')"
    >
      <Icon icon="lucide:x" width="13" />
    </button>
    <span v-if="tray && status === 'uploading'" class="absolute inset-x-3 bottom-1 h-0.5 overflow-hidden rounded-full bg-ink-line">
      <span class="block h-full rounded-full bg-primary transition-all" :style="{ width: `${item.progress || 0}%` }" />
    </span>
  </div>

  <Teleport v-if="zoom" to="#overlay-root" defer>
    <div class="absolute inset-0 z-[90] flex items-center justify-center bg-scrim/80 p-4" role="dialog" :aria-label="`图片预览 ${item.name}`" @click="zoom = false">
      <img :src="src" :alt="item.name" class="max-h-full max-w-full rounded-2xl object-contain shadow-2xl" />
      <button class="icon-btn absolute right-4 top-[calc(var(--safe-top)+16px)]" type="button" aria-label="关闭"><Icon icon="lucide:x" width="18" /></button>
    </div>
  </Teleport>
</template>
