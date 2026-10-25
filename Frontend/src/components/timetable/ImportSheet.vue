<script setup>
import { computed, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import BottomSheet from '@/components/common/BottomSheet.vue'
import { aiApi, timetableApi } from '@/api'
import { useTimetableStore } from '@/stores/timetable'
import { useUiStore } from '@/stores/ui'

const props = defineProps({ open: { type: Boolean, default: false } })
const emit = defineEmits(['close'])

const timetable = useTimetableStore()
const ui = useUiStore()
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
const pasted = ref('')
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
    pasted.value = ''
    if (tab.value === 'ai') loadProviders()
  },
)

const subtitle = computed(() => {
  if (preview.value) return preview.value.file_name || '粘贴的内容'
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

const parsePasted = () => {
  const text = pasted.value.trim()
  if (!text) return ui.toast('请先粘贴课表页面的源代码', 'warning')
  const json = text.startsWith('{') || text.startsWith('[')
  const file = new File([text], json ? 'pasted.json' : 'pasted.html', { type: json ? 'application/json' : 'text/html' })
  runPreview(() => timetableApi.importWeb(file, 'preview'), 'web', file)
}

const pickAi = (event) => {
  const file = takeFile(event)
  if (file) runPreview(() => timetableApi.recognize(file, providerId.value || null), 'ai', file)
}

// ---------------------------------------------------------------- 教务系统地址与书签小工具
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

const openJwxt = () => {
  if (!normalizedUrl.value) return ui.toast('请先填写学校教务系统网址', 'warning')
  saveUrl()
  window.open(normalizedUrl.value, '_blank', 'noopener')
}

// 在教务系统的课表页运行：收集顶层页面与同源 iframe/frame 的 HTML，用标记（与后端 FRAME_MARKER 一致）拼接后复制；
// 复制失败则下载成文件。只用 ES5 语法、不含 // 注释（会被压成一行），兼容老旧教务系统常见的旧浏览器内核。
const BOOKMARKLET_SOURCE = `(function(){
var M='<'+'!--STUDY-PLANNER-FRAME-->',out=[],docs=[];
function walk(w,d){if(d>4)return;try{var doc=w.document;out.push(doc.documentElement.outerHTML);docs.push(doc);}catch(e){return;}
for(var i=0;i<w.frames.length;i++){walk(w.frames[i],d+1);}}
walk(window,0);var text=out.join(M);
function body(){for(var i=0;i<docs.length;i++){var b=docs[i].body;if(b&&b.tagName==='BODY')return docs[i];}return null;}
function copy(){var doc=body();if(!doc)return false;var t=doc.createElement('textarea');t.value=text;
t.style.position='fixed';t.style.top='0';t.style.opacity='0';doc.body.appendChild(t);t.focus();t.select();
var ok=false;try{ok=doc.execCommand('copy');}catch(e){}doc.body.removeChild(t);return ok;}
function save(){var a=document.createElement('a');a.href=URL.createObjectURL(new Blob([text],{type:'text/html'}));
a.download='timetable.html';(document.body||document.documentElement).appendChild(a);a.click();}
if(copy()){alert('已复制课表页面（'+text.length+' 字符），回到学习规划粘贴即可');}
else{save();alert('无法写入剪贴板，已下载 timetable.html，请在学习规划里上传该文件');}
})()`
const bookmarklet = `javascript:${encodeURIComponent(BOOKMARKLET_SOURCE.replace(/\n/g, ''))}`
const bookmarkletHint = () => ui.toast('请把按钮拖到浏览器书签栏，在教务系统的课表页点击它', 'info', 3200)

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
  const options = [{ value: '', label: `当前启用：${s.resolved?.label || '未选择'}` }]
  if (s.env?.configured) options.push({ value: 'env', label: `${s.env.name} · ${s.env.model}（仅文字版 PDF）${s.active === 'auto' ? ' · 使用中' : ''}` })
  s.providers.forEach((p) => options.push({ value: String(p.id), label: `${p.name} · ${p.model}${p.active ? ' · 使用中' : ''}` }))
  return options
})
const usingRule = computed(() => aiSettings.value && !providerId.value && aiSettings.value.resolved?.provider === 'rule')

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

const submit = () => {
  const indexes = [...selected.value].sort((a, b) => a - b)
  const { kind, file } = origin.value
  if (kind === 'file') return timetableApi.importFile(file, 'commit', indexes)
  if (kind === 'web') return timetableApi.importWeb(file, 'commit', indexes)
  // AI 识别结果：直接提交预览里勾选的课程，不再调用模型
  const p = preview.value
  return timetableApi.commitCourses({
    courses: indexes.map((i) => p.courses[i]),
    semester: p.semester,
    semester_start: p.semester_start,
    total_weeks: p.total_weeks,
    file_name: p.file_name,
    fail_count: p.skipped.length,
  })
}

const commit = async () => {
  if (!selected.value.size) return ui.toast('请至少勾选一门课程', 'warning')
  const ok = await ui.confirm({
    title: '导入课表',
    message: `将导入 ${selected.value.size} 门课程，并替换「${preview.value.semester}」学期已有的课程。`,
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

        <ol class="space-y-1.5 rounded-3xl bg-background p-4 text-xs leading-5 text-ink-soft">
          <li><b class="text-ink">1.</b> 在新打开的页面登录教务系统</li>
          <li><b class="text-ink">2.</b> 进入"我的课表 / 学生课表 / 个人课表"，选好学年学期并点"查询"</li>
          <li><b class="text-ink">3.</b> 按 <kbd class="rounded bg-surface px-1">Ctrl+S</kbd> 保存为"网页，单个文件（.mhtml）"后上传；或按 <kbd class="rounded bg-surface px-1">Ctrl+U</kbd> 查看源代码，全选复制后粘贴到下面</li>
        </ol>

        <button class="flex w-full items-center justify-center gap-2 rounded-3xl border-2 border-dashed border-primary/30 bg-primary-light/50 px-4 py-5 text-primary transition hover:bg-primary-light" type="button" :disabled="busy" @click="webInput.click()">
          <Icon :icon="busy ? 'lucide:loader-circle' : 'lucide:file-code'" width="22" :class="busy && 'animate-spin'" />
          <span class="text-sm font-black">{{ busy ? '正在解析…' : '上传保存的网页（.html / .mhtml）' }}</span>
        </button>

        <div>
          <label class="label" for="jwxt-paste">或粘贴页面源代码 / 正方接口 JSON</label>
          <textarea id="jwxt-paste" v-model="pasted" class="field h-28 resize-none font-mono text-xs" placeholder="<html>… 或 {&quot;kbList&quot;: […]}" spellcheck="false" />
          <button class="btn-primary mt-2 w-full" type="button" :disabled="busy || !pasted.trim()" @click="parsePasted">
            <Icon :icon="busy ? 'lucide:loader-circle' : 'lucide:clipboard-paste'" width="16" :class="busy && 'animate-spin'" />
            {{ busy ? '正在解析…' : `解析粘贴的内容${pasted ? `（${pasted.length} 字符）` : ''}` }}
          </button>
        </div>

        <details class="rounded-3xl bg-background p-4 text-xs leading-5 text-ink-soft">
          <summary class="cursor-pointer font-bold text-ink">电脑端更省事：书签小工具</summary>
          <p class="mt-2">把下面的按钮拖到浏览器书签栏，在教务系统的课表页点一下，即可复制课表数据（含内嵌框架），回来粘贴即可。</p>
          <a :href="bookmarklet" class="chip chip-active mt-2" draggable="true" @click.prevent="bookmarkletHint">
            <Icon icon="lucide:bookmark" width="14" />复制课表到学习规划
          </a>
        </details>

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
          <p v-if="usingRule" class="mt-1.5 text-[11px] text-flame">当前是本地规则引擎，无法识别图片，请先在 AI 设置中添加大模型。</p>
        </div>

        <button class="flex w-full flex-col items-center gap-2 rounded-3xl border-2 border-dashed border-primary/30 bg-primary-light/50 px-4 py-8 text-primary transition hover:bg-primary-light" type="button" :disabled="busy" @click="aiInput.click()">
          <Icon :icon="busy ? 'lucide:loader-circle' : 'lucide:scan-text'" width="36" :class="busy && 'animate-spin'" />
          <span class="text-sm font-black">{{ busy ? 'AI 正在识别，约需 10-60 秒…' : '选择课表截图 / 照片 / PDF' }}</span>
          <span class="text-xs text-ink-soft">识别结果会先给你核对，确认后才导入</span>
        </button>

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
        <p>由 <b class="text-ink">{{ preview.model }}</b> 识别{{ preview.source === 'pdf-text' ? '（PDF 文字）' : '' }}，可能有误差，请逐门核对后再导入。</p>
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
