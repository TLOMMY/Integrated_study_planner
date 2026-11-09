<script setup>
import { computed, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import BottomSheet from '@/components/common/BottomSheet.vue'
import { aiApi, timetableApi } from '@/api'
import { useTimetableStore } from '@/stores/timetable'
import { useUiStore } from '@/stores/ui'
import AiBadge from '@/components/ai/AiBadge.vue'
import { friendlyLabel, modelLabel } from '@/utils/aiModels'
import { useJwxtBrowser } from '@/composables/useJwxtBrowser'

// target：'new' 时预览后默认"新建一套课表"（从课表管理的"导入为新课表"进入）
const props = defineProps({ open: { type: Boolean, default: false }, target: { type: String, default: 'current' } })
const emit = defineEmits(['close'])

const timetable = useTimetableStore()
const ui = useUiStore()
const jwxtBrowser = useJwxtBrowser()
const WEEK = ['', '一', '二', '三', '四', '五', '六', '日']
const SOURCES = [
  { key: 'web', label: '教务网页', icon: 'lucide:globe' },
  { key: 'file', label: 'Excel 文件', icon: 'lucide:file-spreadsheet' },
  { key: 'ai', label: '图片/PDF', icon: 'lucide:scan-text' },
]
const TAB_KEY = 'import-source'
const URL_KEY = 'jwxt-url'

const tab = ref(localStorage.getItem(TAB_KEY) || 'web')
const excelInput = ref(null)
const webInput = ref(null)
const aiInput = ref(null)
const preview = ref(null)
const origin = ref(null) // { kind: 'file' | 'web' | 'ai', file }
const selected = ref(new Set())
const busy = ref(false)

const jwxtUrl = ref(localStorage.getItem(URL_KEY) || '')
const aiSettings = ref(null)
const providerId = ref('')

watch(tab, (value) => {
  localStorage.setItem(TAB_KEY, value)
  if (value === 'ai' && props.open && !aiSettings.value) loadProviders()
})

watch(
  () => props.open,
  (open) => {
    if (!open) return
    preview.value = null
    origin.value = null
    aiError.value = null
    if (tab.value === 'ai') loadProviders()
  },
)

const subtitle = computed(() => {
  if (preview.value) return preview.value.file_name || '导入的课表'
  if (tab.value === 'web') return '把教务系统的课表页面交给我，自动识别课程'
  if (tab.value === 'ai') return '截图、照片或 PDF，由大模型识别课程'
  return '支持教务系统导出的 Excel（.xls / .xlsx）与 CSV'
})

/** 同名课程分组，选修方向较多的班级课表可以整组勾选/取消。 */
const groups = computed(() => {
  const map = new Map()
  ;(preview.value?.courses || []).forEach((course, index) => {
    if (!map.has(course.course_name)) map.set(course.course_name, { name: course.course_name, color: course.color, items: [] })
    map.get(course.course_name).items.push({ ...course, index })
  })
  return [...map.values()]
})

// ---------------------------------------------------------------- 解析
const runPreview = async (request, kind, file) => {
  busy.value = true
  try {
    preview.value = await request()
    origin.value = { kind, file }
    selected.value = new Set(preview.value.courses.map((_, i) => i))
  } catch (error) {
    ui.fail(error, '解析失败')
  } finally {
    busy.value = false
  }
}

const takeFile = (event) => {
  const chosen = event.target.files?.[0]
  event.target.value = ''
  return chosen || null
}

const pickExcel = (event) => {
  const file = takeFile(event)
  if (file) runPreview(() => timetableApi.importFile(file, 'preview'), 'file', file)
}

const pickWeb = (event) => {
  const file = takeFile(event)
  if (file) runPreview(() => timetableApi.importWeb(file, 'preview'), 'web', file)
}

// ---------------------------------------------------------------- AI 识别：阶段提示与失败原因
const aiStage = ref('') // upload | read | model | slow
const aiElapsed = ref(0)
const aiError = ref(null) // { title, message, tips[] }
let aiTimer = null
const AI_STAGES = {
  upload: '正在上传文件…',
  read: '正在读取文件（PDF 先提取文字）…',
  model: 'AI 正在识别课程，通常 5-30 秒…',
  slow: '仍在识别，图片或复杂课表可能需要 1 分钟左右…',
}
const RECOGNIZE_TIMEOUT_S = 150

const describeAiError = (error, file, elapsed) => {
  const reason = error?.data?.reason
  const isPdf = /\.pdf$/i.test(file?.name || '') || file?.type === 'application/pdf'
  if (reason === 'no_vision') {
    return {
      title: '当前模型不能识别图片',
      message: error.message,
      tips: error.data?.source === 'pdf-image'
        ? ['这个 PDF 提取不到文字（扫描件 / 截图转的 PDF），只能按图片识别', '从教务系统直接导出或"打印为 PDF"的文字版 PDF 可以用 DeepSeek 识别']
        : ['DeepSeek 只能读文字，图片需要支持视觉的模型', '也可以改用「教务网页」或「Excel 文件」导入'],
    }
  }
  if (reason === 'timeout' || error?.status === 504 || (error?.status === 0 && elapsed >= RECOGNIZE_TIMEOUT_S - 5)) {
    return {
      title: '识别超时',
      message: reason === 'timeout' ? error.message : `等了 ${elapsed} 秒仍没有结果，模型服务可能繁忙。`,
      tips: ['稍后重试一次', '图片裁剪到只剩课表区域会快很多', '文字版 PDF 比图片快且更准'],
    }
  }
  if (reason === 'no_courses') {
    return {
      title: '没有识别出课程',
      message: error.message,
      tips: isPdf ? ['确认 PDF 是课表本身（含星期和节次）', '可以换成课表截图，或改用「教务网页」导入'] : ['截图要包含完整的星期表头和节次列', '避免反光、倾斜，或改用文字版 PDF'],
    }
  }
  if (reason === 'no_model') return { title: '还没有可用的大模型', message: error.message, tips: ['在「AI 设置」中添加一个模型后再试'] }
  if (error?.status === 0) return { title: '连接中断', message: error.message || '无法连接服务器', tips: ['检查网络后重试'] }
  return { title: '识别失败', message: error?.message || '识别失败，请重试', tips: reason === 'bad_output' ? ['换一张更清晰的图片，或重试一次'] : [] }
}

const pickAi = async (event) => {
  const file = takeFile(event)
  if (!file) return
  aiError.value = null
  aiStage.value = 'upload'
  aiElapsed.value = 0
  const started = Date.now()
  aiTimer = setInterval(() => {
    aiElapsed.value = Math.round((Date.now() - started) / 1000)
    // 上传进度事件不一定触发（部分 WebView）：3 秒后按"识别中"显示
    if (['upload', 'read'].includes(aiStage.value) && aiElapsed.value >= 3) aiStage.value = 'model'
    if (aiStage.value === 'model' && aiElapsed.value >= 35) aiStage.value = 'slow'
  }, 1000)
  const onUpload = (e) => {
    if (e.total && e.loaded >= e.total && aiStage.value === 'upload') {
      aiStage.value = 'read'
      setTimeout(() => aiStage.value === 'read' && (aiStage.value = 'model'), 1200)
    }
  }
  busy.value = true
  try {
    preview.value = await timetableApi.recognize(file, providerId.value || null, onUpload)
    origin.value = { kind: 'ai', file }
    selected.value = new Set(preview.value.courses.map((_, i) => i))
  } catch (error) {
    aiError.value = describeAiError(error, file, Math.round((Date.now() - started) / 1000))
  } finally {
    clearInterval(aiTimer)
    aiStage.value = ''
    busy.value = false
  }
}

// ---------------------------------------------------------------- 教务系统地址
const normalizedUrl = computed(() => {
  const raw = jwxtUrl.value.trim()
  if (!raw) return ''
  const value = /^https?:\/\//i.test(raw) ? raw : `http://${raw}`
  try {
    const url = new URL(value)
    return ['http:', 'https:'].includes(url.protocol) ? url.href : ''
  } catch {
    return ''
  }
})

const saveUrl = () => {
  if (jwxtUrl.value.trim() && !normalizedUrl.value) return ui.toast('网址格式不正确', 'warning')
  jwxtUrl.value = normalizedUrl.value
  localStorage.setItem(URL_KEY, normalizedUrl.value)
}

const openJwxt = async () => {
  if (!normalizedUrl.value) return ui.toast('请先填写学校教务系统网址', 'warning')
  saveUrl()
  // 安卓 App：在内置浏览器里打开，同学点页面上的"导入此页课表"后直接解析，不用再保存文件
  if (jwxtBrowser.supported) {
    try {
      const capture = await jwxtBrowser.open(normalizedUrl.value, { accent: themeAccent() })
      if (capture) runPreview(() => timetableApi.importWeb(capture.file, 'preview'), 'web', capture.file)
    } catch (error) {
      ui.fail(error, '打开教务系统失败')
    }
    return
  }
  window.open(normalizedUrl.value, '_blank', 'noopener')
}

/** 当前主题的主色（#RRGGBB），给注入页面的按钮用。 */
const themeAccent = () => {
  const channels = getComputedStyle(document.documentElement).getPropertyValue('--c-primary').trim().split(/\s+/).map(Number)
  return channels.length === 3 && channels.every(Number.isFinite) ? `#${channels.map((c) => c.toString(16).padStart(2, '0')).join('')}` : undefined
}

// ---------------------------------------------------------------- AI 模型选择
const loadProviders = async () => {
  try {
    aiSettings.value = await aiApi.settings()
  } catch (error) {
    ui.fail(error)
  }
}

const providerOptions = computed(() => {
  const s = aiSettings.value
  if (!s) return []
  const options = [{ value: '', label: `跟随 AI 助手：${friendlyLabel(s.resolved?.label) || '未选择'}` }]
  if (s.env?.configured) options.push({ value: 'env', label: `${s.env.name}（仅文字版 PDF）${s.active === 'auto' ? ' · 使用中' : ''}` })
  s.providers.forEach((p) => options.push({ value: String(p.id), label: `${p.name} · ${modelLabel(p.model)}${p.active ? ' · 使用中' : ''}` }))
  return options
})
const usingRule = computed(() => aiSettings.value && !providerId.value && aiSettings.value.resolved?.provider === 'rule')
// 识别实际使用的模型（与 AI 对话是同一套配置；服务器 DeepSeek 默认换 Flash 并关闭思考，见后端 import_label）
const recognizeModel = computed(() => {
  const s = aiSettings.value
  if (!s) return ''
  if (!providerId.value) return s.import_label || ''
  if (providerId.value === 'env') return s.env_import_label || ''
  const p = s.providers.find((x) => String(x.id) === providerId.value)
  return p ? `${p.name} · ${modelLabel(p.model)}` : ''
})
const textOnlyModel = computed(() => /deepseek/i.test(recognizeModel.value))

// ---------------------------------------------------------------- 识别出的节次时间
const usePeriodTimes = ref(true)
watch(preview, () => (usePeriodTimes.value = true))
/** 列出前几处不同："第1节 08:00→08:10"。 */
const periodDiff = computed(() => {
  const next = preview.value?.period_times || []
  const now = timetable.meta?.period_times || []
  const changes = next
    .map((p, i) => ({ i, p, o: now[i] }))
    .filter(({ p, o }) => !o || o.start !== p.start || o.end !== p.end)
    .map(({ i, p, o }) => `第${i + 1}节 ${o ? `${o.start}-${o.end} → ` : ''}${p.start}-${p.end}`)
  const extra = next.length !== now.length ? `共 ${now.length} 节 → ${next.length} 节；` : ''
  return extra + changes.slice(0, 3).join('，') + (changes.length > 3 ? ` 等 ${changes.length} 处` : '')
})

// ---------------------------------------------------------------- 勾选与导入
const groupState = (group) => {
  const count = group.items.filter((item) => selected.value.has(item.index)).length
  return count === 0 ? 'none' : count === group.items.length ? 'all' : 'some'
}
const toggleGroup = (group) => {
  const next = new Set(selected.value)
  const select = groupState(group) !== 'all'
  group.items.forEach((item) => (select ? next.add(item.index) : next.delete(item.index)))
  selected.value = next
}
const toggleItem = (index) => {
  const next = new Set(selected.value)
  next.has(index) ? next.delete(index) : next.add(index)
  selected.value = next
}

// ---------------------------------------------------------------- 导入到哪套课表
const importTarget = ref('current') // current 替换当前课表 / new 新建一套
const newSetName = ref('')
const activeSetName = computed(() => timetable.sets.active_name || '我的课表')
const defaultSetName = computed(() => (preview.value?.file_name || '').replace(/\.[^.]+$/, '').slice(0, 40) || preview.value?.semester || '')
watch(preview, (value) => {
  if (!value) return
  importTarget.value = props.target === 'new' ? 'new' : 'current'
  newSetName.value = defaultSetName.value
})
const targetPayload = () => (importTarget.value === 'new'
  ? { target: 'new', setName: newSetName.value.trim() || defaultSetName.value }
  : { target: 'current' })

const submit = () => {
  const indexes = [...selected.value].sort((a, b) => a - b)
  const { kind, file } = origin.value
  const target = targetPayload()
  if (kind === 'file') return timetableApi.importFile(file, 'commit', indexes, target)
  if (kind === 'web') return timetableApi.importWeb(file, 'commit', indexes, target)
  // AI 识别结果：直接提交预览里勾选的课程，不再调用模型
  const p = preview.value
  return timetableApi.commitCourses({
    courses: indexes.map((i) => p.courses[i]),
    semester: p.semester,
    semester_start: p.semester_start,
    total_weeks: p.total_weeks,
    file_name: p.file_name,
    fail_count: p.skipped.length,
    target: target.target,
    set_name: target.setName,
    period_times: usePeriodTimes.value && p.period_times?.length ? p.period_times : null,
  })
}

const commit = async () => {
  if (!selected.value.size) return ui.toast('请至少勾选一门课程', 'warning')
  const toNew = importTarget.value === 'new'
  const ok = await ui.confirm({
    title: '导入课表',
    message: toNew
      ? `将新建课表「${newSetName.value.trim() || defaultSetName.value || '导入的课表'}」，导入 ${selected.value.size} 门课程并切换过去。原来的课表会保留，可随时切回。`
      : `将导入 ${selected.value.size} 门课程，并替换当前课表「${activeSetName.value}」里已有的课程。`,
    confirmText: '导入',
  })
  if (!ok) return
  busy.value = true
  try {
    const result = await submit()
    ui.reward(result.reward)
    ui.success(`已导入 ${result.success_count} 门课程`)
    timetable.week = null
    await timetable.load()
    emit('close')
  } catch (error) {
    ui.fail(error)
  } finally {
    busy.value = false
  }
}

const back = () => {
  preview.value = null
  origin.value = null
}
</script>

<template>
  <BottomSheet :open="open" title="导入课表" :subtitle="subtitle" @close="emit('close')">
    <input ref="excelInput" type="file" accept=".xls,.xlsx,.csv" class="hidden" @change="pickExcel" />
    <input ref="webInput" type="file" accept=".html,.htm,.mhtml,.mht,.json,.txt" class="hidden" @change="pickWeb" />
    <input ref="aiInput" type="file" accept="image/png,image/jpeg,image/webp,.pdf,application/pdf" class="hidden" @change="pickAi" />

    <div v-if="!preview" class="space-y-3 pb-2">
      <div class="grid grid-cols-3 gap-1 rounded-2xl bg-background p-1" role="tablist" aria-label="导入方式">
        <button
          v-for="source in SOURCES"
          :key="source.key"
          type="button"
          role="tab"
          :aria-selected="tab === source.key"
          class="flex items-center justify-center gap-1 rounded-xl px-2 py-2 text-xs font-bold transition"
          :class="tab === source.key ? 'bg-surface text-primary shadow-soft' : 'text-ink-soft'"
          :disabled="busy"
          @click="tab = source.key"
        >
          <Icon :icon="source.icon" width="14" />{{ source.label }}
        </button>
      </div>

      <!-- 教务网页 -->
      <template v-if="tab === 'web'">
        <div>
          <label class="label" for="jwxt-url">学校教务系统网址</label>
          <div class="flex gap-2">
            <input id="jwxt-url" v-model="jwxtUrl" class="field" type="url" inputmode="url" placeholder="如 http://jwxt.xxx.edu.cn" autocomplete="url" @change="saveUrl" />
            <button class="btn-ghost shrink-0" type="button" @click="openJwxt">
              <Icon icon="lucide:external-link" width="16" />打开
            </button>
          </div>
        </div>

        <!-- 安卓 App：内置浏览器里直接导入 -->
        <ol v-if="jwxtBrowser.supported" class="space-y-1.5 rounded-3xl bg-background p-4 text-xs leading-5 text-ink-soft">
          <li><b class="text-ink">1.</b> 点"打开"，在 App 里登录教务系统</li>
          <li><b class="text-ink">2.</b> 进入"我的课表 / 学生课表 / 个人课表"，选好学年学期并点"查询"</li>
          <li><b class="text-ink">3.</b> 点页面右下角的<b class="text-ink">"导入此页课表"</b>，回到这里核对后导入</li>
        </ol>
        <ol v-else class="space-y-1.5 rounded-3xl bg-background p-4 text-xs leading-5 text-ink-soft">
          <li><b class="text-ink">1.</b> 在新打开的页面登录教务系统</li>
          <li><b class="text-ink">2.</b> 进入"我的课表 / 学生课表 / 个人课表"，选好学年学期并点"查询"</li>
          <li><b class="text-ink">3.</b> 电脑：按 <kbd class="rounded bg-surface px-1">Ctrl+S</kbd> 保存为"网页，单个文件（.mhtml）"，再点下面上传</li>
          <li class="pl-4">手机：在浏览器菜单里选"分享 → 打印 → 存储为 PDF"，再到 <button type="button" class="font-bold text-primary underline underline-offset-2" @click="tab = 'ai'">图片/PDF</button> 上传</li>
        </ol>

        <button class="flex w-full items-center justify-center gap-2 rounded-3xl border-2 border-dashed border-primary/30 bg-primary-light/50 px-4 py-5 text-primary transition hover:bg-primary-light" type="button" :disabled="busy" @click="webInput.click()">
          <Icon :icon="busy ? 'lucide:loader-circle' : 'lucide:file-code'" width="22" :class="busy && 'animate-spin'" />
          <span class="text-sm font-black">{{ busy ? '正在解析…' : '上传保存的网页（.html / .mhtml）' }}</span>
        </button>

        <p class="px-1 text-[11px] leading-5 text-ink-mute">支持正方（新版/旧版）、强智、青果等教务系统的课表页面。只在本地解析页面内容，不会登录或访问你的教务账号。</p>
      </template>

      <!-- Excel 文件 -->
      <template v-else-if="tab === 'file'">
        <button class="flex w-full flex-col items-center gap-2 rounded-3xl border-2 border-dashed border-primary/30 bg-primary-light/50 px-4 py-8 text-primary transition hover:bg-primary-light" type="button" :disabled="busy" @click="excelInput.click()">
          <Icon :icon="busy ? 'lucide:loader-circle' : 'lucide:file-spreadsheet'" width="36" :class="busy && 'animate-spin'" />
          <span class="text-sm font-black">{{ busy ? '正在解析…' : '选择课表文件' }}</span>
          <span class="text-xs text-ink-soft">先预览，确认无误后再导入</span>
        </button>
        <div class="rounded-3xl bg-background p-4 text-xs leading-6 text-ink-soft">
          <p class="font-bold text-ink">能识别的格式</p>
          <p>· 正方教务"班级/个人课表"导出：自动识别周次（含单双周）、节次、教室、教师，以及开学日期与总周数</p>
          <p>· 普通表格：包含"课程、星期、节次、周次、教师、教室"列即可</p>
        </div>
      </template>

      <!-- 图片 / PDF（AI 识别） -->
      <template v-else>
        <div>
          <label class="label" for="ai-model">识别使用的模型</label>
          <select id="ai-model" v-model="providerId" class="field" :disabled="busy || !aiSettings">
            <option v-if="!aiSettings" value="">正在读取模型设置…</option>
            <option v-for="option in providerOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
          </select>
          <p v-if="usingRule" class="mt-1.5 flex items-start gap-1 text-[11px] text-flame">
            <span class="flex-1">当前是本地规则引擎，无法识别图片，请先在 AI 设置中添加大模型。</span>
            <!-- 手册里说明哪些模型能识别图片 / PDF，以及规则引擎能做什么 -->
            <RouterLink :to="{ name: 'manual', hash: '#import-ai' }" class="-my-1 flex h-6 w-6 shrink-0 items-center justify-center rounded-full hover:bg-flame-light" aria-label="哪些模型能识别图片和 PDF" title="哪些模型能识别图片和 PDF" @click="emit('close')"><Icon icon="lucide:circle-help" width="14" /></RouterLink>
          </p>
          <p v-else-if="recognizeModel" class="mt-1.5 flex flex-wrap items-center gap-1 text-[11px] text-ink-soft">
            <Icon icon="lucide:cpu" width="12" class="shrink-0 text-primary" />使用：<b class="text-ink">{{ recognizeModel }}</b>
            <span class="text-ink-mute">· 与 AI 助手同一套模型配置，识别时关闭思考以加快速度</span>
          </p>
          <p v-if="textOnlyModel" class="mt-1 text-[11px] text-flame">DeepSeek 不支持图片：能识别文字版 PDF；截图、照片和扫描版 PDF 需要支持视觉的模型。</p>
        </div>

        <button class="flex w-full flex-col items-center gap-2 rounded-3xl border-2 border-dashed border-primary/30 bg-primary-light/50 px-4 py-8 text-primary transition hover:bg-primary-light" type="button" :disabled="busy" :aria-busy="busy" @click="aiInput.click()">
          <Icon :icon="busy ? 'lucide:loader-circle' : 'lucide:scan-text'" width="36" :class="busy && 'animate-spin'" />
          <span class="text-sm font-black" aria-live="polite">{{ busy ? AI_STAGES[aiStage] || 'AI 正在识别…' : '选择课表截图 / 照片 / PDF' }}</span>
          <span class="num text-xs text-ink-soft">{{ busy ? `已用 ${aiElapsed} 秒 · 最长等待 ${RECOGNIZE_TIMEOUT_S} 秒` : '识别结果会先给你核对，确认后才导入' }}</span>
        </button>

        <div v-if="aiError && !busy" class="rounded-3xl border border-danger/30 bg-danger-light/60 p-4 text-xs leading-5" role="alert">
          <p class="flex items-center gap-1.5 text-sm font-black text-danger"><Icon icon="lucide:circle-x" width="16" class="shrink-0" />{{ aiError.title }}</p>
          <p class="mt-1 text-ink-soft">{{ aiError.message }}</p>
          <ul v-if="aiError.tips.length" class="mt-1.5 space-y-0.5 text-ink-soft">
            <li v-for="tip in aiError.tips" :key="tip">· {{ tip }}</li>
          </ul>
          <div class="mt-2 flex gap-2">
            <button class="btn-ghost px-3 py-1.5 text-xs" type="button" @click="aiInput.click()"><Icon icon="lucide:refresh-cw" width="14" />重新选择文件</button>
            <button class="btn-ghost px-3 py-1.5 text-xs" type="button" @click="aiError = null">知道了</button>
          </div>
        </div>

        <div class="rounded-3xl bg-background p-4 text-xs leading-6 text-ink-soft">
          <p class="font-bold text-ink">识别小贴士</p>
          <p>· 图片需要支持视觉的模型，如 通义千问 qwen-vl、智谱 GLM-4V、GPT-4o；DeepSeek 只能识别文字版 PDF</p>
          <p>· 截图请包含完整的星期表头和节次列，避免反光、倾斜</p>
          <p>· 文字版 PDF 会先提取文字再识别，更准确也更省额度</p>
        </div>
      </template>
    </div>

    <div v-else class="space-y-3 pb-2">
      <div v-if="preview.format === 'ai'" class="flex items-start gap-2 rounded-2xl bg-xp-light p-3 text-xs leading-5 text-ink-soft">
        <Icon icon="lucide:sparkles" width="16" class="mt-0.5 shrink-0 text-xp" />
        <p><AiBadge class="mr-1" />由 <b class="text-ink">{{ friendlyLabel(preview.model) }}</b> 识别{{ preview.source === 'pdf-text' ? '（PDF 文字）' : '' }}，可能有误差，请逐门核对后再导入。</p>
      </div>

      <div class="grid grid-cols-3 gap-2 text-center">
        <div class="rounded-2xl bg-primary-light p-3">
          <p class="num text-xl font-black text-primary">{{ preview.success_count }}</p>
          <p class="text-[10px] font-bold text-ink-soft">识别课程</p>
        </div>
        <div class="rounded-2xl bg-background p-3">
          <p class="num text-xl font-black text-ink">{{ preview.total_weeks }}</p>
          <p class="text-[10px] font-bold text-ink-soft">学期周数</p>
        </div>
        <div class="rounded-2xl bg-background p-3">
          <p class="num text-sm font-black leading-7 text-ink">{{ preview.semester_start?.slice(5) || '未识别' }}</p>
          <p class="text-[10px] font-bold text-ink-soft">开学日期</p>
        </div>
      </div>

      <!-- 课表上印了每节课的时间、且和设置里不一样：默认一并更新，课程时间按新的节次表计算 -->
      <label v-if="preview.period_times?.length" class="flex cursor-pointer items-start gap-2 rounded-2xl border border-primary/25 bg-primary-light/60 p-3 text-xs leading-5 text-ink-soft">
        <input v-model="usePeriodTimes" type="checkbox" class="mt-0.5 accent-primary" />
        <span class="min-w-0">
          <b class="text-ink">同时更新节次时间</b>（课表上印的和你现在的设置不一样）
          <span class="num mt-1 block text-[11px] text-ink-mute">{{ periodDiff }}</span>
        </span>
      </label>

      <p class="text-xs text-ink-soft">班级课表会列出所有选修方向，<b>取消勾选你没选的课</b>即可。已选 {{ selected.size }} 门。</p>

      <div class="space-y-2">
        <div v-for="group in groups" :key="group.name" class="rounded-2xl border border-ink-line/70">
          <button class="flex w-full items-center gap-3 px-3 py-2.5 text-left" type="button" @click="toggleGroup(group)">
            <span class="flex h-5 w-5 shrink-0 items-center justify-center rounded-md border-2" :class="groupState(group) === 'none' ? 'border-ink-line' : 'border-primary bg-primary text-on-primary'">
              <Icon v-if="groupState(group) !== 'none'" :icon="groupState(group) === 'all' ? 'lucide:check' : 'lucide:minus'" width="12" />
            </span>
            <span class="h-3 w-3 shrink-0 rounded-full" :style="{ background: group.color }" />
            <span class="min-w-0 flex-1 truncate text-sm font-bold text-ink">{{ group.name }}</span>
            <span class="text-xs text-ink-mute">{{ group.items.length }} 个时段</span>
          </button>
          <div class="space-y-1 border-t border-ink-line/60 px-3 py-2">
            <label v-for="item in group.items" :key="item.index" class="flex cursor-pointer items-center gap-2 text-xs text-ink-soft">
              <input type="checkbox" class="accent-primary" :checked="selected.has(item.index)" @change="toggleItem(item.index)" />
              周{{ WEEK[item.day_of_week] }} {{ item.start_period }}-{{ item.end_period }}节 · {{ item.week_text }}
              <span class="truncate text-ink-mute">{{ item.classroom }} {{ item.teacher }}</span>
            </label>
          </div>
        </div>
      </div>

      <div v-if="preview.skipped.length" class="rounded-2xl bg-flame-light p-3 text-xs text-ink-soft">
        <p class="mb-1 font-bold text-flame">以下 {{ preview.skipped.length }} 项未导入</p>
        <p v-for="(item, i) in preview.skipped" :key="i">· {{ item.name }}：{{ item.reason }}</p>
      </div>

      <!-- 导入到当前课表 / 新建一套 -->
      <div class="space-y-2">
        <p class="label">导入到</p>
        <div class="grid grid-cols-2 gap-2" role="radiogroup" aria-label="导入到哪套课表">
          <button type="button" role="radio" :aria-checked="importTarget === 'current'" class="rounded-2xl border p-3 text-left" :class="importTarget === 'current' ? 'border-primary bg-primary-light' : 'border-ink-line'" @click="importTarget = 'current'">
            <p class="text-sm font-bold text-ink">当前课表</p>
            <p class="mt-0.5 truncate text-[11px] text-ink-mute">替换「{{ activeSetName }}」的课程</p>
          </button>
          <button type="button" role="radio" :aria-checked="importTarget === 'new'" class="rounded-2xl border p-3 text-left" :class="importTarget === 'new' ? 'border-primary bg-primary-light' : 'border-ink-line'" @click="importTarget = 'new'">
            <p class="text-sm font-bold text-ink">新建一套</p>
            <p class="mt-0.5 text-[11px] text-ink-mute">原课表保留，可随时切回</p>
          </button>
        </div>
        <input v-if="importTarget === 'new'" v-model="newSetName" class="field" maxlength="40" placeholder="新课表名称，如 大二下" aria-label="新课表名称" />
      </div>
    </div>

    <template v-if="preview" #footer>
      <div class="grid grid-cols-[auto_1fr] gap-3">
        <button class="btn-ghost" type="button" :disabled="busy" @click="back">
          <Icon icon="lucide:arrow-left" width="16" />重选
        </button>
        <button class="btn-primary" type="button" :disabled="busy" @click="commit">{{ busy ? '导入中…' : `导入 ${selected.size} 门课程` }}</button>
      </div>
    </template>
  </BottomSheet>
</template>
