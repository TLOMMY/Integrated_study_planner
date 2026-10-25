<script setup>
import { computed, nextTick, reactive, ref, watch } from 'vue'
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
import { reminderSettings } from '@/composables/useReminders'
import {
  CHECKLIST_MAX,
  LINKS_MAX,
  LIST_LEN,
  TAG_LEN,
  TAG_MAX,
  computeRemindAt,
  inferRemindMode,
  isBilibili,
  isHttpUrl,
  linkHost,
  newItemId,
  remindOptions,
} from './extras'

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
    list_name: source.list_name || '',
    tags: [...(source.tags || [])],
    checklist: (source.checklist || []).map((item) => ({ id: item.id || newItemId(), title: item.title, done: Boolean(item.done) })),
    links: (source.links || []).map((link) => ({ ...link })),
    remind_custom: source.remind_at || '',
  })
  form.remind_mode = inferRemindMode(source.remind_at, form.due_date, form.start_time)
  // 新建定时任务时按设置里的"默认提前"自动带上提醒
  remindTouched.value = Boolean(source.remind_at)
  if (!isEdit.value && !remindTouched.value) applyDefaultRemind()
  tagInput.value = ''
  stepInput.value = ''
  linkDraft.url = ''
  linkDraft.title = ''
}

// ---------------------------------------------------------------- 提醒
const remindTouched = ref(false)
const reminderChoices = computed(() => remindOptions(form.due_date, form.start_time))
const remindPreview = computed(() =>
  computeRemindAt(form.remind_mode, { dueDate: form.due_date, startTime: form.start_time, custom: form.remind_custom }),
)
const applyDefaultRemind = () => {
  const lead = reminderSettings.lead
  form.remind_mode = form.due_date && form.start_time && reminderSettings.enabled && lead !== null && lead !== undefined ? `m${lead}` : 'none'
  if (!reminderChoices.value.some((o) => o.key === form.remind_mode)) form.remind_mode = 'none'
}
const pickRemind = (key) => {
  remindTouched.value = true
  form.remind_mode = key
  if (key === 'custom' && !form.remind_custom) {
    form.remind_custom = remindPreview.value || dayjs(`${form.due_date || todayStr()} ${form.start_time || '09:00'}`).format('YYYY-MM-DDTHH:mm')
  }
}
// 改了日期 / 时刻后，当前提醒方式不再可选时回到默认
watch(
  () => [form.due_date, form.start_time],
  () => {
    if (!props.open) return
    if (!remindTouched.value && !isEdit.value) return applyDefaultRemind()
    if (!reminderChoices.value.some((o) => o.key === form.remind_mode)) form.remind_mode = 'none'
  },
)

// ---------------------------------------------------------------- 清单与标签
const tagInput = ref('')
const groupLists = computed(() => tasks.groups.lists.map((g) => g.name))
const tagSuggestions = computed(() => tasks.groups.tags.map((g) => g.name).filter((name) => !form.tags.includes(name)).slice(0, 8))
const addTag = (raw = tagInput.value) => {
  const tag = String(raw || '').trim().replace(/^#+/, '').trim()
  if (!tag) return
  if (tag.length > TAG_LEN) return ui.toast(`标签最多 ${TAG_LEN} 个字`, 'warning')
  if (form.tags.includes(tag)) return (tagInput.value = '')
  if (form.tags.length >= TAG_MAX) return ui.toast(`每个任务最多 ${TAG_MAX} 个标签`, 'warning')
  form.tags.push(tag)
  tagInput.value = ''
}
const removeTag = (tag) => (form.tags = form.tags.filter((t) => t !== tag))
const onTagKey = (event) => {
  if (event.key === 'Enter' || event.key === ',' || event.key === '，' || event.key === ' ') {
    event.preventDefault()
    addTag()
  } else if (event.key === 'Backspace' && !tagInput.value && form.tags.length) {
    form.tags.pop()
  }
}

// ---------------------------------------------------------------- 子任务
const stepInput = ref('')
const stepList = ref(null)
const doneSteps = computed(() => form.checklist.filter((item) => item.done).length)
const addStep = () => {
  const title = stepInput.value.trim()
  if (!title) return
  if (form.checklist.length >= CHECKLIST_MAX) return ui.toast(`最多 ${CHECKLIST_MAX} 个子任务`, 'warning')
  form.checklist.push({ id: newItemId(), title: title.slice(0, 100), done: false })
  stepInput.value = ''
}
const removeStep = (index) => form.checklist.splice(index, 1)
const moveStep = (from, to) => {
  if (to < 0 || to >= form.checklist.length || from === to) return
  const [item] = form.checklist.splice(from, 1)
  form.checklist.splice(to, 0, item)
}
const onStepKey = async (event, index) => {
  if (!event.altKey || !['ArrowUp', 'ArrowDown'].includes(event.key)) return
  event.preventDefault()
  const to = index + (event.key === 'ArrowUp' ? -1 : 1)
  moveStep(index, to)
  await nextTick()
  stepList.value?.querySelectorAll('[data-grip]')[Math.max(0, Math.min(to, form.checklist.length - 1))]?.focus()
}
// 拖动排序：用 Pointer 事件，鼠标和手指都能用（HTML5 拖放在手机上不可用）
const dragging = ref(-1)
const startStepDrag = (event, index) => {
  dragging.value = index
  event.currentTarget.setPointerCapture?.(event.pointerId)
}
const onStepDrag = (event) => {
  if (dragging.value < 0 || !stepList.value) return
  const rows = [...stepList.value.querySelectorAll('[data-step]')]
  const target = rows.findIndex((row) => {
    const rect = row.getBoundingClientRect()
    return event.clientY >= rect.top && event.clientY <= rect.bottom
  })
  if (target >= 0 && target !== dragging.value) {
    moveStep(dragging.value, target)
    dragging.value = target
  }
}
const endStepDrag = () => (dragging.value = -1)

// ---------------------------------------------------------------- 学习资源链接
const linkDraft = reactive({ url: '', title: '' })
const addLink = () => {
  const url = linkDraft.url.trim()
  if (!url) return
  if (!isHttpUrl(url)) return ui.toast('链接需以 http:// 或 https:// 开头', 'warning')
  if (form.links.length >= LINKS_MAX) return ui.toast(`最多 ${LINKS_MAX} 条链接`, 'warning')
  if (form.links.some((link) => link.url === url)) return ui.toast('这个链接已经添加过了', 'info')
  form.links.push({ url, title: linkDraft.title.trim().slice(0, 100) || linkHost(url), source: isBilibili({ url }) ? 'bilibili' : 'web' })
  linkDraft.url = ''
  linkDraft.title = ''
}
const removeLink = (index) => form.links.splice(index, 1)

watch(
  () => props.open,
  async (open) => {
    if (!open) return
    reset()
    timetable.ensure().catch(() => {})
    tasks.loadGroups().catch(() => {})
    planApi.list('active').then((data) => (plans.value = data.items)).catch(() => {})
  },
)

const submit = async () => {
  if (!form.title.trim()) return ui.toast('请输入任务名称', 'warning')
  if (form.repeat_rule !== 'none' && !form.due_date) return ui.toast('重复任务需要设置日期', 'warning')
  if (form.remind_mode === 'custom' && !remindPreview.value) return ui.toast('请选择自定义提醒时间', 'warning')
  // 输入框里还没按回车的内容也一并保存
  addTag()
  addStep()
  if (linkDraft.url.trim()) addLink()
  const dueDate = form.due_date || null
  const startTime = dueDate && form.start_time ? form.start_time : null
  const payload = {
    title: form.title.trim(),
    note: form.note.trim() || null,
    due_date: dueDate,
    start_time: startTime,
    duration_minutes: Number(form.duration_minutes),
    priority: form.priority,
    repeat_rule: form.repeat_rule,
    subject: form.subject.trim() || null,
    plan_id: form.plan_id,
    list_name: form.list_name.trim() || null,
    tags: [...form.tags],
    checklist: form.checklist.filter((item) => item.title.trim()).map(({ id, title, done }) => ({ id, title: title.trim(), done })),
    links: form.links.map(({ title, url, source }) => ({ title, url, source })),
    remind_at: computeRemindAt(form.remind_mode, { dueDate, startTime, custom: form.remind_custom }),
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

      <div>
        <span class="label flex items-center gap-1.5">
          <Icon icon="lucide:bell" width="13" />提醒
          <span v-if="remindPreview" class="num font-semibold text-primary">· {{ dayjs(remindPreview).format('M月D日 HH:mm') }}</span>
        </span>
        <div class="scrollbar-hide -mx-1 flex gap-2 overflow-x-auto px-1 lg:flex-wrap">
          <button
            v-for="o in reminderChoices"
            :key="o.key"
            type="button"
            class="chip shrink-0"
            :class="form.remind_mode === o.key && 'chip-active'"
            @click="pickRemind(o.key)"
          >
            {{ o.label }}
          </button>
        </div>
        <input v-if="form.remind_mode === 'custom'" v-model="form.remind_custom" type="datetime-local" class="field mt-2" aria-label="自定义提醒时间" />
        <p v-if="form.remind_mode !== 'none' && !reminderSettings.enabled" class="mt-1.5 text-[11px] text-flame">任务提醒已在设置里关闭，到点不会弹出</p>
      </div>

      <!-- 子任务 -->
      <div>
        <span class="label flex items-center gap-1.5">
          <Icon icon="lucide:list-todo" width="13" />子任务
          <span v-if="form.checklist.length" class="num font-semibold text-ink-mute">{{ doneSteps }}/{{ form.checklist.length }}</span>
        </span>
        <ul v-if="form.checklist.length" ref="stepList" class="mb-2 space-y-1.5" @pointermove="onStepDrag" @pointerup="endStepDrag" @pointercancel="endStepDrag">
          <li
            v-for="(item, index) in form.checklist"
            :key="item.id"
            data-step
            class="flex items-center gap-2 rounded-2xl bg-background px-2 py-1.5 transition"
            :class="dragging === index && 'bg-primary-light shadow-soft ring-2 ring-primary/30'"
          >
            <button
              data-grip
              type="button"
              class="flex h-7 w-5 shrink-0 cursor-grab touch-none items-center justify-center text-ink-mute active:cursor-grabbing"
              :aria-label="`拖动排序：${item.title}（也可按 Alt+上下方向键）`"
              @pointerdown.prevent="startStepDrag($event, index)"
              @keydown="onStepKey($event, index)"
            >
              <Icon icon="lucide:grip-vertical" width="14" />
            </button>
            <button
              type="button"
              class="flex h-[18px] w-[18px] shrink-0 items-center justify-center rounded-md border-2 transition"
              :class="item.done ? 'border-success bg-success text-on-success' : 'border-ink-line hover:border-primary/60'"
              role="checkbox"
              :aria-checked="item.done"
              :aria-label="`完成子任务：${item.title}`"
              @click="item.done = !item.done"
            >
              <Icon v-if="item.done" icon="lucide:check" width="12" />
            </button>
            <input v-model="item.title" class="min-w-0 flex-1 bg-transparent py-1 text-sm outline-none" :class="item.done && 'text-ink-mute line-through'" maxlength="100" aria-label="子任务标题" />
            <button type="button" class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-ink-mute hover:bg-surface hover:text-danger" :aria-label="`删除子任务：${item.title}`" @click="removeStep(index)">
              <Icon icon="lucide:x" width="14" />
            </button>
          </li>
        </ul>
        <div v-if="form.checklist.length < CHECKLIST_MAX" class="flex items-center gap-2 rounded-2xl border border-dashed border-ink-line px-3">
          <Icon icon="lucide:plus" width="14" class="shrink-0 text-ink-mute" />
          <input v-model="stepInput" class="min-w-0 flex-1 bg-transparent py-2.5 text-sm outline-none placeholder:text-ink-mute" placeholder="添加子任务，回车确认" maxlength="100" enterkeyhint="done" @keydown.enter.prevent="addStep" />
          <button v-if="stepInput.trim()" type="button" class="shrink-0 text-xs font-bold text-primary" @click="addStep">添加</button>
        </div>
      </div>

      <!-- 清单与标签 -->
      <div class="grid gap-3 sm:grid-cols-2">
        <label class="block">
          <span class="label flex items-center gap-1.5"><Icon icon="lucide:folder" width="13" />清单</span>
          <input v-model="form.list_name" class="field" list="task-list-options" placeholder="如 考研、社团（可不填）" :maxlength="LIST_LEN" />
          <datalist id="task-list-options">
            <option v-for="name in groupLists" :key="name" :value="name" />
          </datalist>
        </label>
        <div>
          <span class="label flex items-center gap-1.5"><Icon icon="lucide:tag" width="13" />标签 <span class="num font-semibold text-ink-mute">{{ form.tags.length }}/{{ TAG_MAX }}</span></span>
          <div class="field flex flex-wrap items-center gap-1.5 py-2">
            <span v-for="tag in form.tags" :key="tag" class="inline-flex items-center gap-0.5 rounded-lg bg-xp/10 px-2 py-0.5 text-xs font-bold text-xp">
              #{{ tag }}
              <button type="button" class="rounded-full p-0.5 hover:bg-xp/20" :aria-label="`移除标签 ${tag}`" @click="removeTag(tag)"><Icon icon="lucide:x" width="11" /></button>
            </span>
            <input
              v-if="form.tags.length < TAG_MAX"
              v-model="tagInput"
              class="min-w-[80px] flex-1 bg-transparent text-sm outline-none placeholder:text-ink-mute"
              :placeholder="form.tags.length ? '' : '输入后回车'"
              :maxlength="TAG_LEN + 1"
              enterkeyhint="done"
              aria-label="添加标签"
              @keydown="onTagKey"
              @blur="addTag()"
            />
          </div>
          <div v-if="tagSuggestions.length && form.tags.length < TAG_MAX" class="mt-1.5 flex flex-wrap gap-1">
            <button v-for="tag in tagSuggestions" :key="tag" type="button" class="rounded-lg bg-background px-2 py-0.5 text-[11px] font-semibold text-ink-soft hover:bg-xp/10 hover:text-xp" @click="addTag(tag)">#{{ tag }}</button>
          </div>
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

      <!-- 学习资源链接 -->
      <div>
        <span class="label flex items-center gap-1.5"><Icon icon="lucide:link" width="13" />学习资源 <span class="num font-semibold text-ink-mute">{{ form.links.length }}/{{ LINKS_MAX }}</span></span>
        <ul v-if="form.links.length" class="mb-2 space-y-1.5">
          <li v-for="(link, index) in form.links" :key="link.url" class="flex items-center gap-2 rounded-2xl bg-background px-3 py-2">
            <span v-if="isBilibili(link)" class="shrink-0 rounded-md bg-primary px-1.5 py-0.5 text-[10px] font-black text-on-primary">B站</span>
            <Icon v-else icon="lucide:globe" width="14" class="shrink-0 text-ink-mute" />
            <a :href="link.url" target="_blank" rel="noopener noreferrer" class="min-w-0 flex-1">
              <span class="block truncate text-sm font-semibold text-ink">{{ link.title || linkHost(link.url) }}</span>
              <span class="block truncate text-[11px] text-ink-mute">{{ linkHost(link.url) }}</span>
            </a>
            <button type="button" class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-ink-mute hover:bg-surface hover:text-danger" :aria-label="`删除链接：${link.title}`" @click="removeLink(index)">
              <Icon icon="lucide:x" width="14" />
            </button>
          </li>
        </ul>
        <div v-if="form.links.length < LINKS_MAX" class="space-y-2 rounded-2xl border border-dashed border-ink-line p-2">
          <input v-model="linkDraft.url" class="field py-2.5" type="url" inputmode="url" placeholder="粘贴网址，如 B 站课程链接" maxlength="500" aria-label="链接网址" @keydown.enter.prevent="addLink" />
          <div class="flex gap-2">
            <input v-model="linkDraft.title" class="field min-w-0 flex-1 py-2.5" placeholder="标题（可选）" maxlength="100" aria-label="链接标题" @keydown.enter.prevent="addLink" />
            <button type="button" class="btn-ghost shrink-0 px-4 py-2.5" :disabled="!linkDraft.url.trim()" @click="addLink"><Icon icon="lucide:plus" width="14" />添加</button>
          </div>
        </div>
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
