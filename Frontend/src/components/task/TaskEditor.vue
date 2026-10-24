<script setup>
import { computed, reactive, ref, watch } from 'vue'
import dayjs from 'dayjs'
import { Icon } from '@iconify/vue'
import BottomSheet from '@/components/common/BottomSheet.vue'
import { planApi } from '@/api'
import { useTasksStore } from '@/stores/tasks'
import { useTimetableStore } from '@/stores/timetable'
import { useUiStore } from '@/stores/ui'
import { DURATIONS, PRIORITIES, REPEATS, focusRoute } from '@/utils/task'
import { todayStr } from '@/utils/dates'
import { useRouter } from 'vue-router'

const props = defineProps({
  open: { type: Boolean, default: false },
  task: { type: Object, default: null },
  defaults: { type: Object, default: () => ({}) },
})
const emit = defineEmits(['close', 'saved'])

const tasks = useTasksStore()
const timetable = useTimetableStore()
const ui = useUiStore()
const router = useRouter()

const form = reactive({})
const plans = ref([])
const saving = ref(false)
const isEdit = computed(() => Boolean(props.task?.id))
// AI 排出的任务可能是 50、40 分钟这类非预设时长，也要能显示与保留
const durationOptions = computed(() => [...new Set([...DURATIONS, Number(form.duration_minutes) || 30])].sort((a, b) => a - b))

const dateChips = computed(() => {
  const today = dayjs()
  const nextMonday = today.add(((8 - (today.day() || 7)) % 7) || 7, 'day')
  return [
    { label: '今天', value: todayStr() },
    { label: '明天', value: today.add(1, 'day').format('YYYY-MM-DD') },
    { label: '下周一', value: nextMonday.format('YYYY-MM-DD') },
    { label: '无日期', value: null },
  ]
})

const reset = () => {
  const source = { due_date: todayStr(), duration_minutes: 30, priority: 0, repeat_rule: 'none', ...props.defaults, ...(props.task || {}) }
  Object.assign(form, {
    title: source.title || '',
    note: source.note || '',
    due_date: source.due_date ?? null,
    start_time: source.start_time || '',
    duration_minutes: source.duration_minutes || 30,
    priority: source.priority || 0,
    repeat_rule: source.repeat_rule || 'none',
    subject: source.subject || '',
    plan_id: source.plan_id ?? null,
  })
}

watch(
  () => props.open,
  async (open) => {
    if (!open) return
    reset()
    timetable.ensure().catch(() => {})
    planApi.list('active').then((data) => (plans.value = data.items)).catch(() => {})
  },
)

const submit = async () => {
  if (!form.title.trim()) return ui.toast('请输入任务名称', 'warning')
  if (form.repeat_rule !== 'none' && !form.due_date) return ui.toast('重复任务需要设置日期', 'warning')
  const dueDate = form.due_date || null
  const payload = {
    title: form.title.trim(),
    note: form.note.trim() || null,
    due_date: dueDate,
    start_time: dueDate && form.start_time ? form.start_time : null,
    duration_minutes: Number(form.duration_minutes),
    priority: form.priority,
    repeat_rule: form.repeat_rule,
    subject: form.subject.trim() || null,
    plan_id: form.plan_id,
  }
  saving.value = true
  try {
    const saved = isEdit.value ? await tasks.update(props.task.id, payload) : await tasks.create(payload)
    emit('saved', saved)
    emit('close')
  } catch (error) {
    ui.fail(error)
  } finally {
    saving.value = false
  }
}

const remove = async () => {
  if (await tasks.remove(props.task)) {
    emit('saved', null)
    emit('close')
  }
}

const startFocus = () => {
  emit('close')
  router.push(focusRoute(props.task))
}
</script>

<template>
  <BottomSheet :open="open" :title="isEdit ? '编辑任务' : '新建任务'" @close="emit('close')">
    <form class="space-y-4" @submit.prevent="submit">
      <input v-model="form.title" class="field text-base font-semibold" placeholder="准备做什么？" maxlength="200" autofocus />

      <div>
        <span class="label">日期</span>
        <div class="flex flex-wrap items-center gap-2">
          <button
            v-for="chip in dateChips"
            :key="chip.label"
            type="button"
            class="chip"
            :class="form.due_date === chip.value && 'chip-active'"
            @click="form.due_date = chip.value"
          >
            {{ chip.label }}
          </button>
          <input v-model="form.due_date" type="date" class="chip h-[30px] py-0" aria-label="选择日期" />
        </div>
      </div>

      <div class="grid grid-cols-2 gap-3">
        <label class="block">
          <span class="label">开始时间（可选）</span>
          <input v-model="form.start_time" type="time" class="field" :disabled="!form.due_date" />
        </label>
        <label class="block">
          <span class="label">预计时长</span>
          <select v-model.number="form.duration_minutes" class="field">
            <option v-for="m in durationOptions" :key="m" :value="m">{{ m }} 分钟</option>
          </select>
        </label>
      </div>

      <div>
        <span class="label">优先级</span>
        <div class="grid grid-cols-4 gap-2">
          <button
            v-for="p in PRIORITIES"
            :key="p.value"
            type="button"
            class="flex items-center justify-center gap-1 rounded-2xl border py-2 text-xs font-bold transition"
            :class="form.priority === p.value ? [p.ring, 'bg-background', p.color] : 'border-ink-line text-ink-mute'"
            @click="form.priority = p.value"
          >
            <Icon icon="lucide:flag" width="13" />{{ p.label }}
          </button>
        </div>
      </div>

      <div>
        <span class="label">重复</span>
        <div class="flex flex-wrap gap-2">
          <button v-for="r in REPEATS" :key="r.value" type="button" class="chip" :class="form.repeat_rule === r.value && 'chip-active'" @click="form.repeat_rule = r.value">
            {{ r.label }}
          </button>
        </div>
      </div>

      <div class="grid grid-cols-2 gap-3">
        <label class="block">
          <span class="label">科目</span>
          <input v-model="form.subject" class="field" list="subject-options" placeholder="如 高等数学" maxlength="80" />
          <datalist id="subject-options">
            <option v-for="name in timetable.courseNames" :key="name" :value="name" />
          </datalist>
        </label>
        <label class="block">
          <span class="label">所属计划</span>
          <select v-model="form.plan_id" class="field">
            <option :value="null">不关联</option>
            <option v-for="p in plans" :key="p.id" :value="p.id">{{ p.title }}</option>
          </select>
        </label>
      </div>

      <label class="block">
        <span class="label">备注</span>
        <textarea v-model="form.note" rows="2" class="field resize-none" placeholder="章节、页码、注意事项…" maxlength="1000" />
      </label>

      <div v-if="isEdit && task.focus_minutes" class="flex items-center gap-2 rounded-2xl bg-flame-light px-4 py-3 text-xs font-bold text-flame">
        <Icon icon="lucide:timer" width="16" /> 已专注 {{ task.focus_minutes }} 分钟 · {{ task.pomodoros }} 个完整番茄
      </div>
    </form>

    <template #footer>
      <div class="flex gap-2">
        <button v-if="isEdit" class="btn-danger px-3" type="button" aria-label="删除任务" @click="remove">
          <Icon icon="lucide:trash-2" width="18" />
        </button>
        <button v-if="isEdit && !task.completed" class="btn-ghost" type="button" @click="startFocus">
          <Icon icon="lucide:play" width="16" />专注
        </button>
        <button class="btn-primary flex-1" type="button" :disabled="saving" @click="submit">
          {{ saving ? '保存中…' : isEdit ? '保存修改' : '添加任务' }}
        </button>
      </div>
    </template>
  </BottomSheet>
</template>
