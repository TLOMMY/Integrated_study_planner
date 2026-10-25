<script setup>
/**
 * PDF 讲义提取章节：上传 PDF → 显示章节树（页码、字数、预计复习时长）→ 勾选章节 →
 * 点「让 AI 按这些章节排复习计划」时 emit('plan', text)，text 是整理好的一段中文需求，由父组件发给 AI。
 *
 * 用法：<MaterialOutline @plan="(text) => sendToAgent(text)" />
 * 可选 props：compact（隐藏标题栏，嵌进对话气泡时用）
 */
import { computed, reactive, ref } from 'vue'
import { Icon } from '@iconify/vue'
import { insightApi } from '@/api/insight'
import { useUiStore } from '@/stores/ui'
import { formatMinutes } from '@/utils/dates'

defineProps({ compact: { type: Boolean, default: false } })
const emit = defineEmits(['plan'])
const ui = useUiStore()

const MAX_BYTES = 5 * 1024 * 1024
const input = ref(null)
const busy = ref(false)
const error = ref('')
const outline = ref(null)
const picked = reactive(new Set())
const open = reactive(new Set())

const SOURCE_LABELS = { outline: '来自 PDF 书签', headings: '识别正文标题', pages: '按页数分段' }

const chapters = computed(() => outline.value?.chapters || [])
const keyOf = (i, j = null) => (j === null ? `${i}` : `${i}-${j}`)
const childKeys = (chapter, i) => (chapter.children || []).map((_, j) => keyOf(i, j))

/** 有子节的章节，选中状态由子节决定；没有子节的直接看自己。 */
const chapterState = (chapter, i) => {
  const kids = childKeys(chapter, i)
  if (!kids.length) return picked.has(keyOf(i)) ? 'all' : 'none'
  const count = kids.filter((k) => picked.has(k)).length
  return count === 0 ? 'none' : count === kids.length ? 'all' : 'some'
}

const toggleChapter = (chapter, i) => {
  const kids = childKeys(chapter, i)
  const next = chapterState(chapter, i) !== 'all'
  for (const k of kids.length ? kids : [keyOf(i)]) next ? picked.add(k) : picked.delete(k)
}
const toggleChild = (i, j) => {
  const k = keyOf(i, j)
  picked.has(k) ? picked.delete(k) : picked.add(k)
}
const toggleOpen = (i) => (open.has(i) ? open.delete(i) : open.add(i))

const selectAll = (value) => {
  picked.clear()
  if (!value) return
  chapters.value.forEach((c, i) => {
    const kids = childKeys(c, i)
    ;(kids.length ? kids : [keyOf(i)]).forEach((k) => picked.add(k))
  })
}

/** 选中的复习单元：整章全选时按整章，部分选中时按选中的小节。 */
const selection = computed(() => {
  const units = []
  chapters.value.forEach((c, i) => {
    const state = chapterState(c, i)
    if (state === 'all') units.push({ ...c, sections: (c.children || []).map((s) => s.title) })
    else if (state === 'some')
      c.children.forEach((s, j) => picked.has(keyOf(i, j)) && units.push({ ...s, parent: c.title }))
  })
  return units
})
const selectedMinutes = computed(() => selection.value.reduce((sum, u) => sum + Number(u.est_minutes || 0), 0))
const allSelected = computed(() => chapters.value.length > 0 && chapters.value.every((c, i) => chapterState(c, i) === 'all'))

const pages = (range) => (range[0] === range[1] ? `第 ${range[0]} 页` : `第 ${range[0]}-${range[1]} 页`)
const words = (n) => (n >= 10000 ? `${(n / 10000).toFixed(1)} 万字` : `${n} 字`)

const choose = () => input.value?.click()

const upload = async (event) => {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return
  error.value = ''
  if (!/\.pdf$/i.test(file.name) && file.type !== 'application/pdf') {
    error.value = '仅支持 PDF 文件'
    return
  }
  if (file.size > MAX_BYTES) {
    error.value = '文件不能超过 5MB'
    return
  }
  busy.value = true
  try {
    outline.value = await insightApi.materialsOutline(file)
    open.clear()
    selectAll(true)
  } catch (err) {
    // 扫描件、加密、损坏等后端给的中文原因直接显示在卡片里
    error.value = err?.message || '提取章节失败，请重试'
  } finally {
    busy.value = false
  }
}

const reset = () => {
  outline.value = null
  error.value = ''
  picked.clear()
}

const buildText = () => {
  const lines = selection.value.map((u, n) => {
    const title = u.parent ? `${u.parent} / ${u.title}` : u.title
    const extra = u.sections?.length ? `（含 ${u.sections.slice(0, 6).join('、')}${u.sections.length > 6 ? ' 等' : ''}）` : ''
    return `${n + 1}. ${title}${extra}：${pages(u.pages)}，预计 ${u.est_minutes} 分钟`
  })
  return [
    `请按以下章节帮我安排复习（讲义《${outline.value.file_name}》，共 ${lines.length} 个单元，预计 ${formatMinutes(selectedMinutes.value)}）：`,
    ...lines,
    '请结合我的课表和空闲时间，把每个单元安排成具体的复习任务，难的章节分开多次复习，最后留出整体回顾的时间。',
  ].join('\n')
}

const plan = () => {
  if (!selection.value.length) {
    ui.toast('请先勾选要复习的章节')
    return
  }
  emit('plan', buildText())
}

defineExpose({ choose, reset })
</script>

<template>
  <section class="card p-4 lg:p-5">
    <header v-if="!compact" class="mb-3 flex items-center gap-2">
      <span class="flex h-9 w-9 items-center justify-center rounded-2xl bg-primary-light text-primary">
        <Icon icon="lucide:book-open" width="18" />
      </span>
      <div class="min-w-0 flex-1">
        <h3 class="section-title">讲义提取章节</h3>
        <p class="text-xs text-ink-mute">上传 PDF 讲义或课件，按章节估算复习时长</p>
      </div>
      <button v-if="outline" type="button" class="chip" @click="choose">
        <Icon icon="lucide:refresh-cw" width="12" />换一份
      </button>
    </header>

    <input ref="input" type="file" accept="application/pdf,.pdf" class="hidden" @change="upload" />

    <!-- 上传 -->
    <button
      v-if="!outline"
      type="button"
      class="flex w-full flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-ink-line bg-background px-4 py-7 text-center transition hover:border-primary/50 hover:bg-primary-light/40 disabled:opacity-60"
      :disabled="busy"
      @click="choose"
    >
      <Icon :icon="busy ? 'lucide:loader-circle' : 'lucide:file-up'" width="28" :class="busy ? 'animate-spin text-primary' : 'text-ink-mute'" />
      <span class="text-sm font-bold text-ink">{{ busy ? '正在读取章节…' : '选择 PDF 讲义' }}</span>
      <span class="text-xs text-ink-mute">{{ busy ? '有模型时会让 AI 整理成复习单元，稍等片刻' : '文字版 PDF，不超过 5MB' }}</span>
    </button>

    <p v-if="error" role="alert" class="mt-3 flex items-start gap-1.5 rounded-2xl bg-danger-light px-3 py-2.5 text-xs font-semibold text-danger">
      <Icon icon="lucide:info" width="14" class="mt-px shrink-0" />{{ error }}
    </p>

    <!-- 结果 -->
    <template v-if="outline">
      <div class="mb-3 flex items-start gap-2 rounded-2xl bg-background px-3 py-2.5">
        <Icon icon="lucide:file-text" width="18" class="mt-0.5 shrink-0 text-primary" />
        <div class="min-w-0 flex-1">
          <p class="truncate text-sm font-bold text-ink" :title="outline.file_name">{{ outline.file_name }}</p>
          <p class="text-xs text-ink-mute">
            {{ outline.pages }} 页 · {{ chapters.length }} 个章节 · 共约 {{ formatMinutes(outline.total_minutes) }}
            · {{ outline.provider === 'llm' ? 'AI 已整理' : SOURCE_LABELS[outline.source] || '规则提取' }}
          </p>
        </div>
        <span v-if="outline.provider === 'llm'" class="flex shrink-0 items-center gap-0.5 rounded-full bg-xp-light px-2 py-0.5 text-[10px] font-bold text-xp">
          <Icon icon="lucide:sparkles" width="10" />AI
        </span>
      </div>
      <p v-if="outline.fallback_reason" class="mb-3 text-[11px] text-ink-mute">{{ outline.fallback_reason }}</p>

      <div class="mb-2 flex items-center justify-between text-xs">
        <label class="flex cursor-pointer items-center gap-2 font-bold text-ink-soft">
          <input type="checkbox" class="h-4 w-4 accent-primary" :checked="allSelected" @change="selectAll(!allSelected)" />
          全选
        </label>
        <span class="text-ink-mute">已选 {{ selection.length }} 个单元 · <span class="num font-bold text-ink">{{ formatMinutes(selectedMinutes) }}</span></span>
      </div>

      <ul class="max-h-[46vh] space-y-1.5 overflow-y-auto pr-1 lg:max-h-[420px]">
        <li v-for="(chapter, i) in chapters" :key="i" class="rounded-2xl border border-ink-line/70">
          <div class="flex items-center gap-2 px-3 py-2.5">
            <input
              type="checkbox"
              class="h-4 w-4 shrink-0 accent-primary"
              :aria-label="`选择 ${chapter.title}`"
              :checked="chapterState(chapter, i) === 'all'"
              :indeterminate.prop="chapterState(chapter, i) === 'some'"
              @change="toggleChapter(chapter, i)"
            />
            <button type="button" class="min-w-0 flex-1 text-left" @click="chapter.children?.length ? toggleOpen(i) : toggleChapter(chapter, i)">
              <p class="truncate text-sm font-bold text-ink">{{ chapter.title }}</p>
              <p class="text-[11px] text-ink-mute">{{ pages(chapter.pages) }}<template v-if="chapter.words"> · {{ words(chapter.words) }}</template></p>
            </button>
            <span class="flex shrink-0 items-center gap-0.5 text-xs font-bold text-primary">
              <Icon icon="lucide:clock" width="12" /><span class="num">{{ chapter.est_minutes }}</span>分
            </span>
            <button
              v-if="chapter.children?.length"
              type="button"
              class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-ink-mute hover:bg-background"
              :aria-label="open.has(i) ? '收起小节' : '展开小节'"
              :aria-expanded="open.has(i)"
              @click="toggleOpen(i)"
            >
              <Icon icon="lucide:chevron-right" width="16" class="transition" :class="open.has(i) && 'rotate-90'" />
            </button>
          </div>
          <ul v-if="chapter.children?.length && open.has(i)" class="space-y-0.5 border-t border-ink-line/60 px-3 py-1.5">
            <li v-for="(section, j) in chapter.children" :key="j">
              <label class="flex cursor-pointer items-center gap-2 rounded-xl py-1.5 pl-5 pr-1 hover:bg-background">
                <input type="checkbox" class="h-3.5 w-3.5 shrink-0 accent-primary" :checked="picked.has(keyOf(i, j))" @change="toggleChild(i, j)" />
                <span class="min-w-0 flex-1 truncate text-xs text-ink-soft">{{ section.title }}</span>
                <span class="shrink-0 text-[11px] text-ink-mute">{{ pages(section.pages) }} · {{ section.est_minutes }} 分</span>
              </label>
            </li>
          </ul>
        </li>
      </ul>

      <button type="button" class="btn-primary mt-3 w-full" :disabled="!selection.length" @click="plan">
        <Icon icon="lucide:sparkles" width="16" />让 AI 按这些章节排复习计划
      </button>
    </template>
  </section>
</template>
