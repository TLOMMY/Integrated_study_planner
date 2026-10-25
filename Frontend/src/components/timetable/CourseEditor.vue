<script setup>
import { computed, reactive, ref, watch } from 'vue'
import BottomSheet from '@/components/common/BottomSheet.vue'
import { useTimetableStore } from '@/stores/timetable'
import { useUiStore } from '@/stores/ui'

const props = defineProps({
  open: { type: Boolean, default: false },
  course: { type: Object, default: null },
  preset: { type: Object, default: () => ({}) },
})
const emit = defineEmits(['close'])

const timetable = useTimetableStore()
const ui = useUiStore()
const saving = ref(false)

const COLORS = ['#4F6EF7', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#06B6D4', '#EC4899', '#84CC16', '#F97316', '#14B8A6']
const DAYS = ['一', '二', '三', '四', '五', '六', '日']
const MODES = [
  { key: 'all', label: '每周' },
  { key: 'odd', label: '单周' },
  { key: 'even', label: '双周' },
  { key: 'custom', label: '自定义' },
]

const total = computed(() => timetable.meta?.total_weeks || 20)
const periodCount = computed(() => timetable.meta?.period_times.length || 12)
const form = reactive({})

const detectMode = (weeks) => {
  if (!weeks?.length) return { mode: 'all', from: 1, to: total.value }
  const from = weeks[0]
  const to = weeks[weeks.length - 1]
  if (weeks.length === to - from + 1) return { mode: 'all', from, to }
  if (weeks.every((w, i) => i === 0 || w - weeks[i - 1] === 2)) return { mode: from % 2 ? 'odd' : 'even', from, to }
  return { mode: 'custom', from, to }
}

watch(
  () => props.open,
  (open) => {
    if (!open) return
    const c = props.course
    const p = props.preset
    const range = detectMode(c?.weeks)
    Object.assign(form, {
      course_name: c?.course_name || '',
      classroom: c?.classroom || '',
      teacher: c?.teacher || '',
      day_of_week: c?.day_of_week || p.day_of_week || 1,
      start_period: c?.start_period || p.start_period || 1,
      end_period: c?.end_period || Math.min((p.start_period || 1) + 1, periodCount.value),
      mode: range.mode,
      from: range.from,
      to: range.to,
      custom: new Set(c?.weeks || []),
      color: c?.color || COLORS[Math.floor(Math.random() * COLORS.length)],
      note: c?.note || '',
    })
  },
)

const weeks = computed(() => {
  if (form.mode === 'custom') return [...form.custom].sort((a, b) => a - b)
  const list = []
  for (let w = form.from; w <= form.to; w++) {
    if (form.mode === 'odd' && w % 2 === 0) continue
    if (form.mode === 'even' && w % 2 === 1) continue
    list.push(w)
  }
  return list
})

const toggleWeek = (week) => {
  const next = new Set(form.custom)
  next.has(week) ? next.delete(week) : next.add(week)
  form.custom = next
}

const submit = async () => {
  if (!form.course_name.trim()) return ui.toast('请输入课程名称', 'warning')
  if (form.end_period < form.start_period) return ui.toast('结束节次不能早于开始节次', 'warning')
  if (!weeks.value.length) return ui.toast('请至少选择一个上课周', 'warning')
  saving.value = true
  try {
    const ok = await timetable.saveCourse(
      {
        course_name: form.course_name.trim(),
        classroom: form.classroom.trim(),
        teacher: form.teacher.trim(),
        day_of_week: form.day_of_week,
        start_period: form.start_period,
        end_period: form.end_period,
        weeks: weeks.value,
        color: form.color,
        note: form.note.trim(),
      },
      props.course?.id,
    )
    if (ok) emit('close')
  } catch (error) {
    ui.fail(error)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <BottomSheet :open="open" :title="course ? '编辑课程' : '添加课程'" @close="emit('close')">
    <form class="space-y-4" @submit.prevent="submit">
      <input v-model="form.course_name" class="field text-base font-semibold" placeholder="课程名称" maxlength="160" />
      <div class="grid grid-cols-2 gap-3">
        <input v-model="form.classroom" class="field" placeholder="教室" maxlength="80" />
        <input v-model="form.teacher" class="field" placeholder="教师" maxlength="120" />
      </div>

      <div>
        <span class="label">星期</span>
        <div class="grid grid-cols-7 gap-1.5">
          <button
            v-for="(d, i) in DAYS"
            :key="d"
            type="button"
            class="rounded-xl py-2 text-xs font-bold transition"
            :class="form.day_of_week === i + 1 ? 'bg-primary text-on-primary' : 'bg-background text-ink-soft'"
            @click="form.day_of_week = i + 1"
          >
            {{ d }}
          </button>
        </div>
      </div>

      <div class="grid grid-cols-2 gap-3">
        <label class="block">
          <span class="label">开始节次</span>
          <select v-model.number="form.start_period" class="field">
            <option v-for="n in periodCount" :key="n" :value="n">第 {{ n }} 节 · {{ timetable.meta?.period_times[n - 1]?.start }}</option>
          </select>
        </label>
        <label class="block">
          <span class="label">结束节次</span>
          <select v-model.number="form.end_period" class="field">
            <option v-for="n in periodCount" :key="n" :value="n" :disabled="n < form.start_period">第 {{ n }} 节 · {{ timetable.meta?.period_times[n - 1]?.end }}</option>
          </select>
        </label>
      </div>

      <div>
        <span class="label">上课周次</span>
        <div class="grid grid-cols-4 gap-2">
          <button v-for="m in MODES" :key="m.key" type="button" class="chip justify-center" :class="form.mode === m.key && 'chip-active'" @click="form.mode = m.key">
            {{ m.label }}
          </button>
        </div>
        <div v-if="form.mode !== 'custom'" class="mt-2 flex items-center gap-2 text-sm text-ink-soft">
          第
          <select v-model.number="form.from" class="field w-20 px-3 py-2">
            <option v-for="n in total" :key="n" :value="n">{{ n }}</option>
          </select>
          至
          <select v-model.number="form.to" class="field w-20 px-3 py-2">
            <option v-for="n in total" :key="n" :value="n" :disabled="n < form.from">{{ n }}</option>
          </select>
          周
        </div>
        <div v-else class="mt-2 grid grid-cols-6 gap-1.5">
          <button
            v-for="n in total"
            :key="n"
            type="button"
            class="num rounded-lg py-1.5 text-xs font-bold transition"
            :class="form.custom.has(n) ? 'bg-primary text-on-primary' : 'bg-background text-ink-mute'"
            @click="toggleWeek(n)"
          >
            {{ n }}
          </button>
        </div>
        <p class="mt-2 text-xs text-ink-mute">共 {{ weeks.length }} 周</p>
      </div>

      <div>
        <span class="label">颜色</span>
        <div class="flex flex-wrap gap-2">
          <button
            v-for="c in COLORS"
            :key="c"
            type="button"
            class="h-8 w-8 rounded-full ring-offset-2 transition"
            :class="form.color === c && 'ring-2 ring-ink'"
            :style="{ background: c }"
            :aria-label="`颜色 ${c}`"
            @click="form.color = c"
          />
        </div>
      </div>

      <input v-model="form.note" class="field" placeholder="备注（如：带实验报告）" maxlength="200" />
    </form>
    <template #footer>
      <button class="btn-primary w-full" type="button" :disabled="saving" @click="submit">{{ saving ? '保存中…' : '保存课程' }}</button>
    </template>
  </BottomSheet>
</template>
