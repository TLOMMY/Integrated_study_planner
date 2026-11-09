<script setup>
/**
 * 导入考试安排：粘贴文字，或上传表格 / 网页 / PDF / 截图 → 预览（每条可改、可取消勾选）→ 导入。
 * 表格、网页、复制的文字在服务器本地解析，不占 AI 次数；截图和扫描件才交给模型。
 * 已有的同名同日考试、日期已过、没认出日期的默认不勾。
 */
import { computed, onBeforeUnmount, ref } from 'vue'
import dayjs from 'dayjs'
import { Icon } from '@iconify/vue'
import { examApi } from '@/api/growth'
import { useTimetableStore } from '@/stores/timetable'
import { useUiStore } from '@/stores/ui'

const emit = defineEmits(['done'])
const timetable = useTimetableStore()
const ui = useUiStore()

const ACCEPT = '.xlsx,.xls,.csv,.html,.htm,.mhtml,.txt,.pdf,application/pdf,image/png,image/jpeg,image/webp'
const WEEK = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
const FIELDS = ['title', 'subject', 'exam_date', 'start_time', 'end_time', 'location', 'note']

const text = ref('')
const fileInput = ref(null)
const busy = ref(false)
const slow = ref(false)
const failure = ref(null)
const result = ref(null) // 预览：{ items, skipped, source, model, ... }
const rows = ref([])
const editing = ref(-1)
let slowTimer = null
onBeforeUnmount(() => clearTimeout(slowTimer))

const describe = (error) => {
  const reason = error?.data?.reason
  if (reason === 'no_vision') return { title: '当前模型不能识别图片', message: error.message, tips: ['把考试安排复制成文字粘贴进来，不需要模型', '或在「AI 设置」里添加能看图的模型'] }
  if (reason === 'no_model') return { title: '这份内容需要 AI 识别', message: '没能直接读出考试安排，而当前没有可用的大模型。', tips: ['复制成文字粘贴（每场考试一行，含课程名和日期）', '或在「AI 设置」里添加一个模型'] }
  if (reason === 'no_exams') return { title: '没有找到考试安排', message: error.message, tips: ['每场考试要有课程名和日期', '截图要包含完整的表格'] }
  if (reason === 'timeout' || error?.status === 504) return { title: '识别超时', message: error.message, tips: ['稍后重试，或把图片裁剪到只剩考试表'] }
  return { title: '没能读取', message: error?.message || '请重试', tips: [] }
}

const run = async (payload) => {
  busy.value = true
  failure.value = null
  slowTimer = setTimeout(() => (slow.value = true), 2500)
  try {
    const data = await examApi.importPreview(payload)
    result.value = data
    rows.value = data.items.map((item) => ({ ...item, picked: item.selected }))
    editing.value = -1
  } catch (error) {
    failure.value = describe(error)
  } finally {
    clearTimeout(slowTimer)
    busy.value = false
    slow.value = false
  }
}
const parseText = () => (text.value.trim() ? run({ text: text.value }) : ui.toast('先粘贴考试安排', 'warning'))
const pickFile = (event) => {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (file) run({ file })
}

const picked = computed(() => rows.value.filter((r) => r.picked))
const ready = (row) => row.title.trim() && /^\d{4}-\d{2}-\d{2}$/.test(row.exam_date)
const toggle = (row, index) => {
  row.picked = !row.picked
  // 勾上一条没有日期的：直接展开让同学补日期
  if (row.picked && !ready(row)) editing.value = index
}
const saving = ref(false)
const submit = async () => {
  const list = picked.value
  if (!list.length) return ui.toast('至少勾选一场考试', 'warning')
  const missing = list.findIndex((r) => !ready(r))
  if (missing !== -1) {
    editing.value = rows.value.indexOf(list[missing])
    return ui.toast(`「${list[missing].title || '未命名'}」还没有日期`, 'warning')
  }
  saving.value = true
  try {
    const items = list.map((r) => Object.fromEntries(FIELDS.map((k) => [k, k === 'title' ? r.title.trim() : r[k] || ''])))
    const data = await examApi.importCommit(items)
    ui.success(data.skipped_count ? `已添加 ${data.created_count} 场，${data.skipped_count} 场已存在` : `已添加 ${data.created_count} 场考试`)
    await timetable.loadExams()
    emit('done')
  } catch (error) {
    ui.fail(error)
  } finally {
    saving.value = false
  }
}
const restart = () => {
  result.value = null
  rows.value = []
  failure.value = null
}

const whenText = (row) => {
  if (!row.exam_date) return '日期未知'
  const d = dayjs(row.exam_date)
  const time = row.start_time ? ` ${row.start_time}${row.end_time ? `-${row.end_time}` : ''}` : ''
  return `${d.format('M月D日')} ${WEEK[d.day()]}${time}`
}
const sourceText = computed(() => (result.value?.source === 'ai' ? `AI 识别 · ${result.value.model}` : '直接读取，未使用 AI'))
</script>
<template>
  <div class="pb-1">
    <input ref="fileInput" type="file" :accept="ACCEPT" class="hidden" @change="pickFile" />

    <!-- 第一步：粘贴或上传 -->
    <div v-if="!result" class="space-y-3">
      <label class="block">
        <span class="label">粘贴考试安排</span>
        <textarea
          v-model="text"
          class="field min-h-[132px] text-sm leading-6"
          maxlength="20000"
          :disabled="busy"
          placeholder="从教务系统或通知里复制过来，每场一行即可，例如：&#10;高等数学A  1月8日 09:00-11:00  教一 201  座位号 15&#10;大学英语  2027-01-10 14:00-16:00  B2203"
        />
      </label>
      <button class="btn-primary w-full rounded-full" type="button" :disabled="busy || !text.trim()" @click="parseText">
        <Icon v-if="busy" icon="lucide:loader-circle" width="16" class="animate-spin" />
        {{ busy ? (slow ? 'AI 正在识别，通常 10-30 秒…' : '正在读取…') : '识别' }}
      </button>

      <div class="flex items-center gap-3 text-[11px] font-semibold text-ink-mute">
        <span class="h-px flex-1 bg-ink-line" />或<span class="h-px flex-1 bg-ink-line" />
      </div>
      <button
        class="flex w-full items-center gap-3 rounded-[20px] border border-dashed border-ink-line bg-background px-4 py-3.5 text-left transition hover:border-primary-mid disabled:opacity-50"
        type="button"
        :disabled="busy"
        @click="fileInput.click()"
      >
        <span class="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary-light text-primary"><Icon icon="lucide:file-up" width="19" /></span>
        <span class="min-w-0 flex-1">
          <b class="block text-sm font-black text-ink">上传文件</b>
          <small class="block text-xs text-ink-mute">Excel / CSV、保存的网页、PDF 或截图</small>
        </span>
        <Icon icon="lucide:chevron-right" width="18" class="text-ink-mute" />
      </button>
      <p class="px-1 text-[11px] leading-5 text-ink-mute">表格、网页和复制的文字直接读取，不用 AI 次数；截图和扫描版 PDF 交给 AI 识别。</p>

      <div v-if="failure" class="rounded-[20px] bg-danger-light px-4 py-3" role="alert">
        <p class="flex items-center gap-1.5 text-sm font-black text-danger"><Icon icon="lucide:circle-alert" width="16" />{{ failure.title }}</p>
        <p class="mt-1 text-xs leading-5 text-ink-soft">{{ failure.message }}</p>
        <ul v-if="failure.tips.length" class="mt-1.5 space-y-0.5 text-xs leading-5 text-ink-soft">
          <li v-for="tip in failure.tips" :key="tip">· {{ tip }}</li>
        </ul>
      </div>
    </div>

    <!-- 第二步：核对 -->
    <div v-else class="space-y-2">
      <p class="flex flex-wrap items-center gap-x-2 gap-y-1 px-1 text-xs text-ink-mute">
        <span>找到 <b class="num text-ink">{{ rows.length }}</b> 场<template v-if="result.duplicate_count">，{{ result.duplicate_count }} 场已添加过</template></span>
        <span class="rounded-full bg-background px-2 py-0.5 text-[10px] font-bold">{{ sourceText }}</span>
      </p>
      <article
        v-for="(row, index) in rows"
        :key="index"
        class="rounded-[20px] border bg-surface transition"
        :class="row.picked ? 'border-primary-mid' : 'border-ink-line/70'"
      >
        <div class="flex items-start gap-3 p-3">
          <button
            type="button"
            role="checkbox"
            :aria-checked="row.picked"
            :aria-label="`${row.picked ? '不导入' : '导入'}：${row.title}`"
            class="mt-0.5 flex h-[22px] w-[22px] shrink-0 items-center justify-center rounded-full border-[1.5px] transition"
            :class="row.picked ? 'border-primary bg-primary text-on-primary' : 'border-bead'"
            @click="toggle(row, index)"
          >
            <Icon v-if="row.picked" icon="lucide:check" width="13" />
          </button>
          <button class="min-w-0 flex-1 text-left" type="button" :aria-expanded="editing === index" @click="editing = editing === index ? -1 : index">
            <p class="truncate text-sm font-black" :class="row.picked ? 'text-ink' : 'text-ink-mute'">{{ row.title || '未命名' }}</p>
            <p class="num mt-0.5 text-xs" :class="row.exam_date ? 'text-ink-soft' : 'font-bold text-primary'">{{ whenText(row) }}</p>
            <p v-if="row.location || row.note" class="mt-0.5 truncate text-[11px] text-ink-mute">{{ [row.location, row.note].filter(Boolean).join(' · ') }}</p>
            <p v-if="row.duplicate" class="mt-1 text-[11px] font-bold text-ink-mute">已经添加过</p>
            <p v-else-if="row.problem" class="mt-1 text-[11px] font-bold text-primary">{{ row.problem }}</p>
          </button>
          <Icon :icon="editing === index ? 'lucide:chevron-up' : 'lucide:pencil'" width="15" class="mt-1 shrink-0 text-ink-mute" />
        </div>

        <div v-if="editing === index" class="space-y-2.5 border-t border-ink-line/70 px-3 pb-3 pt-2.5">
          <input v-model="row.title" class="field py-2.5 text-sm font-bold" maxlength="100" placeholder="考试名称" aria-label="考试名称" />
          <div class="grid grid-cols-[1.4fr_1fr_1fr] gap-2">
            <input v-model="row.exam_date" class="field px-2.5 py-2.5 text-sm" type="date" aria-label="日期" />
            <input v-model="row.start_time" class="field px-2.5 py-2.5 text-sm" type="time" aria-label="开始时间" />
            <input v-model="row.end_time" class="field px-2.5 py-2.5 text-sm" type="time" aria-label="结束时间" />
          </div>
          <input v-model="row.location" class="field py-2.5 text-sm" maxlength="100" placeholder="考场（可选）" aria-label="考场" />
          <input v-model="row.note" class="field py-2.5 text-sm" maxlength="500" placeholder="备注，如座位号、开卷闭卷（可选）" aria-label="备注" />
        </div>
      </article>

      <details v-if="result.skipped.length" class="rounded-[18px] bg-background px-3.5 py-2.5 text-xs text-ink-mute">
        <summary class="cursor-pointer font-bold">{{ result.skipped.length }} 行没有读出来</summary>
        <p v-for="(item, i) in result.skipped" :key="i" class="mt-1">· {{ item.name }}：{{ item.reason }}</p>
      </details>

      <div class="sticky bottom-0 -mx-5 grid grid-cols-[auto_1fr] gap-2.5 border-t border-ink-line/70 bg-surface px-5 pb-1 pt-3">
        <button class="btn-ghost rounded-full" type="button" :disabled="saving" @click="restart"><Icon icon="lucide:rotate-ccw" width="15" />重新导入</button>
        <button class="btn-primary rounded-full" type="button" :disabled="saving || !picked.length" @click="submit">
          <Icon v-if="saving" icon="lucide:loader-circle" width="16" class="animate-spin" />导入 {{ picked.length }} 场
        </button>
      </div>
    </div>
  </div>
</template>
