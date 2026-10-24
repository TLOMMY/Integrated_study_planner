<script setup>
import { reactive, ref, watch } from 'vue'
import dayjs from 'dayjs'
import { Icon } from '@iconify/vue'
import BottomSheet from '@/components/common/BottomSheet.vue'
import { useTimetableStore } from '@/stores/timetable'
import { useUiStore } from '@/stores/ui'
import { mondayOf } from '@/utils/dates'

const props = defineProps({ open: { type: Boolean, default: false } })
const emit = defineEmits(['close'])

const timetable = useTimetableStore()
const ui = useUiStore()
const saving = ref(false)
const currentWeek = ref(1)
const form = reactive({ semester: '', semester_start: '', total_weeks: 20, periods: [] })

const DEFAULT = [
  ['08:00', '08:45'], ['08:50', '09:35'], ['09:55', '10:40'], ['10:45', '11:30'],
  ['14:00', '14:45'], ['14:50', '15:35'], ['15:55', '16:40'], ['16:45', '17:30'],
  ['19:00', '19:45'], ['19:50', '20:35'], ['20:40', '21:25'], ['21:30', '22:15'],
].map(([start, end]) => ({ start, end }))

watch(
  () => props.open,
  (open) => {
    if (!open || !timetable.meta) return
    const m = timetable.meta
    Object.assign(form, {
      semester: m.semester,
      semester_start: m.semester_start || mondayOf(dayjs()).format('YYYY-MM-DD'),
      total_weeks: m.total_weeks,
      periods: m.period_times.map((p) => ({ ...p })),
    })
    currentWeek.value = m.current_week || 1
  },
)

/** 用"本周是第几周"反推开学日期，比手填日期更直观。 */
const applyCurrentWeek = () => {
  form.semester_start = mondayOf(dayjs()).subtract(currentWeek.value - 1, 'week').format('YYYY-MM-DD')
}

const addPeriod = () => {
  const last = form.periods[form.periods.length - 1]
  const start = dayjs(`2000-01-01 ${last?.end || '07:15'}`).add(5, 'minute')
  form.periods.push({ start: start.format('HH:mm'), end: start.add(45, 'minute').format('HH:mm') })
}

const submit = async () => {
  saving.value = true
  try {
    await timetable.saveSettings({
      semester: form.semester.trim(),
      semester_start: form.semester_start,
      total_weeks: Number(form.total_weeks),
      period_times: form.periods,
    })
    emit('close')
  } catch (error) {
    ui.fail(error)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <BottomSheet :open="open" title="学期设置" subtitle="决定每周显示哪些课，以及每节课的时间" @close="emit('close')">
    <div class="space-y-4">
      <label class="block">
        <span class="label">学期名称</span>
        <input v-model="form.semester" class="field" placeholder="如 2025-2026-2" />
      </label>

      <div class="rounded-3xl bg-primary-light p-4">
        <span class="label text-primary">本周是第几周</span>
        <div class="flex items-center gap-2">
          <select v-model.number="currentWeek" class="field flex-1 bg-surface">
            <option v-for="n in Number(form.total_weeks)" :key="n" :value="n">第 {{ n }} 周</option>
          </select>
          <button class="btn-primary shrink-0 py-2.5" type="button" @click="applyCurrentWeek">按此推算</button>
        </div>
        <p class="mt-2 text-xs text-ink-soft">开学日期：<b class="num">{{ form.semester_start }}</b>（第 1 周周一）</p>
      </div>

      <div class="grid grid-cols-2 gap-3">
        <label class="block">
          <span class="label">开学日期</span>
          <input v-model="form.semester_start" type="date" class="field" />
        </label>
        <label class="block">
          <span class="label">学期总周数</span>
          <input v-model.number="form.total_weeks" type="number" min="1" max="30" class="field" />
        </label>
      </div>

      <div>
        <div class="mb-2 flex items-center justify-between">
          <span class="label mb-0">节次时间（{{ form.periods.length }} 节）</span>
          <button class="text-xs font-bold text-primary" type="button" @click="form.periods = DEFAULT.map((p) => ({ ...p }))">恢复默认</button>
        </div>
        <div class="space-y-1.5">
          <div v-for="(p, i) in form.periods" :key="i" class="flex items-center gap-2">
            <span class="num w-6 text-center text-xs font-black text-ink-soft">{{ i + 1 }}</span>
            <input v-model="p.start" type="time" class="field flex-1 px-3 py-2" :aria-label="`第${i + 1}节开始`" />
            <span class="text-ink-mute">-</span>
            <input v-model="p.end" type="time" class="field flex-1 px-3 py-2" :aria-label="`第${i + 1}节结束`" />
            <button class="flex h-8 w-8 items-center justify-center rounded-full text-ink-mute hover:bg-danger-light hover:text-danger" type="button" :disabled="form.periods.length <= 4" aria-label="删除这一节" @click="form.periods.splice(i, 1)">
              <Icon icon="lucide:minus" width="16" />
            </button>
          </div>
        </div>
        <button v-if="form.periods.length < 16" class="btn-ghost mt-2 w-full py-2" type="button" @click="addPeriod"><Icon icon="lucide:plus" width="16" />增加一节</button>
      </div>
    </div>
    <template #footer>
      <button class="btn-primary w-full" type="button" :disabled="saving" @click="submit">{{ saving ? '保存中…' : '保存设置' }}</button>
    </template>
  </BottomSheet>
</template>
