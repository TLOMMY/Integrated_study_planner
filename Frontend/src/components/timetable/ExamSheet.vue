<script setup>
import { reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import dayjs from 'dayjs'
import { Icon } from '@iconify/vue'
import BottomSheet from '@/components/common/BottomSheet.vue'
import { useTimetableStore } from '@/stores/timetable'
import { useUiStore } from '@/stores/ui'
import { aiRoute, examDaysText } from './examAi'

const props = defineProps({
  open: { type: Boolean, default: false },
  // 打开时直接编辑某场考试（或传 'new' 新建）
  initial: { type: [Object, String], default: null },
})
const emit = defineEmits(['close'])
const router = useRouter()
const timetable = useTimetableStore()
const ui = useUiStore()

const view = ref('list') // list | edit
const editingId = ref(null)
const saving = ref(false)
const showPast = ref(false)
const form = reactive({ title: '', subject: '', exam_date: '', start_time: '', location: '', note: '' })

const startEdit = (exam = null) => {
  editingId.value = exam?.id || null
  Object.assign(form, {
    title: exam?.title || '',
    subject: exam?.subject || '',
    exam_date: exam?.exam_date || dayjs().add(7, 'day').format('YYYY-MM-DD'),
    start_time: exam?.start_time || '',
    location: exam?.location || '',
    note: exam?.note || '',
  })
  view.value = 'edit'
}

watch(
  () => props.open,
  (open) => {
    if (!open) return
    view.value = 'list'
    timetable.loadExams().catch((e) => ui.fail(e, '考试加载失败'))
    if (props.initial === 'new') startEdit()
    else if (props.initial && typeof props.initial === 'object') startEdit(props.initial)
  },
)

const submit = async () => {
  if (!form.title.trim()) return ui.toast('请填写考试名称', 'warning')
  if (!form.exam_date) return ui.toast('请选择考试日期', 'warning')
  saving.value = true
  try {
    await timetable.saveExam({ ...form, title: form.title.trim() }, editingId.value)
    view.value = 'list'
  } catch (e) {
    ui.fail(e)
  } finally {
    saving.value = false
  }
}

const remove = async (exam) => {
  if (await timetable.removeExam(exam).catch(ui.fail)) view.value = 'list'
}

const askAi = (exam) => {
  emit('close')
  router.push(aiRoute(exam))
}
</script>

<template>
  <BottomSheet :open="open" :title="view === 'edit' ? (editingId ? '编辑考试' : '添加考试') : '考试倒计时'" :subtitle="view === 'list' ? '3 天内的考试会标红提醒' : ''" @close="emit('close')">
    <!-- 列表 -->
    <div v-if="view === 'list'" class="space-y-2">
      <p v-if="!timetable.exams.length" class="rounded-3xl bg-background px-4 py-6 text-center text-sm text-ink-mute">还没有即将到来的考试</p>
      <article
        v-for="exam in timetable.exams"
        :key="exam.id"
        class="rounded-3xl border p-3.5"
        :class="exam.urgent ? 'border-danger/30 bg-danger-light' : 'border-ink-line/70 bg-surface'"
      >
        <div class="flex items-start gap-3">
          <div class="flex h-14 w-14 shrink-0 flex-col items-center justify-center rounded-2xl" :class="exam.urgent ? 'bg-danger text-on-danger' : 'bg-primary-light text-primary'">
            <template v-if="exam.days_left > 1">
              <span class="num text-xl font-black leading-none">{{ exam.days_left }}</span>
              <span class="mt-0.5 text-[10px] font-bold">天</span>
            </template>
            <span v-else class="text-sm font-black">{{ examDaysText(exam) }}</span>
          </div>
          <button class="min-w-0 flex-1 text-left" type="button" @click="startEdit(exam)">
            <p class="truncate text-sm font-black text-ink">{{ exam.title }}</p>
            <p class="num mt-0.5 text-xs text-ink-soft">{{ dayjs(exam.exam_date).format('M月D日') }} {{ exam.weekday }}<template v-if="exam.start_time"> · {{ exam.start_time }}</template></p>
            <p v-if="exam.location || exam.subject" class="mt-0.5 truncate text-[11px] text-ink-mute">{{ [exam.subject, exam.location].filter(Boolean).join(' · ') }}</p>
          </button>
        </div>
        <button class="mt-2.5 flex w-full items-center justify-center gap-1.5 rounded-2xl bg-xp-light py-2 text-xs font-bold text-xp" type="button" @click="askAi(exam)">
          <Icon icon="lucide:sparkles" width="14" />让 AI 排复习计划
        </button>
      </article>

      <div v-if="timetable.pastExams.length" class="pt-2">
        <button class="flex items-center gap-1 text-xs font-bold text-ink-mute" type="button" :aria-expanded="showPast" @click="showPast = !showPast">
          <Icon :icon="showPast ? 'lucide:chevron-down' : 'lucide:chevron-right'" width="14" />已结束（{{ timetable.pastExams.length }}）
        </button>
        <ul v-if="showPast" class="mt-2 space-y-1.5">
          <li v-for="exam in timetable.pastExams" :key="exam.id" class="flex items-center gap-2 rounded-2xl bg-background px-3 py-2 text-xs">
            <span class="min-w-0 flex-1 truncate font-semibold text-ink-soft">{{ exam.title }}</span>
            <span class="num text-ink-mute">{{ dayjs(exam.exam_date).format('M/D') }}</span>
            <button class="text-ink-mute" type="button" :aria-label="`删除${exam.title}`" @click="remove(exam)"><Icon icon="lucide:trash-2" width="14" /></button>
          </li>
        </ul>
      </div>
    </div>

    <!-- 编辑 -->
    <form v-else class="space-y-3" @submit.prevent="submit">
      <label class="block">
        <span class="label">考试名称</span>
        <input v-model="form.title" class="field" maxlength="100" placeholder="如 高等数学期末" />
      </label>
      <div class="grid grid-cols-2 gap-3">
        <label class="block">
          <span class="label">日期</span>
          <input v-model="form.exam_date" type="date" class="field" />
        </label>
        <label class="block">
          <span class="label">开始时间（可选）</span>
          <input v-model="form.start_time" type="time" class="field" />
        </label>
      </div>
      <div class="grid grid-cols-2 gap-3">
        <label class="block">
          <span class="label">科目（可选）</span>
          <input v-model="form.subject" class="field" maxlength="80" list="exam-subjects" placeholder="科目" />
          <datalist id="exam-subjects"><option v-for="n in timetable.courseNames" :key="n" :value="n" /></datalist>
        </label>
        <label class="block">
          <span class="label">地点（可选）</span>
          <input v-model="form.location" class="field" maxlength="100" placeholder="考场" />
        </label>
      </div>
      <label class="block">
        <span class="label">备注（可选）</span>
        <textarea v-model="form.note" class="field min-h-[72px]" maxlength="500" placeholder="考试范围、需带的东西…" />
      </label>
    </form>

    <template #footer>
      <button v-if="view === 'list'" class="btn-primary w-full" type="button" @click="startEdit()"><Icon icon="lucide:plus" width="16" />添加考试</button>
      <div v-else class="grid gap-3" :class="editingId ? 'grid-cols-3' : 'grid-cols-2'">
        <button v-if="editingId" class="btn-danger" type="button" @click="remove({ id: editingId, title: form.title })"><Icon icon="lucide:trash-2" width="16" />删除</button>
        <button class="btn-ghost" type="button" @click="view = 'list'">返回</button>
        <button class="btn-primary" type="button" :disabled="saving" @click="submit">{{ saving ? '保存中…' : '保存' }}</button>
      </div>
    </template>
  </BottomSheet>
</template>
