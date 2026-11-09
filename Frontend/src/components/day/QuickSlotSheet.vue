<script setup>
/**
 * 点空闲段的半屏快建：只填名字；时长按空闲长度给建议，写出结束时间。科目只列当天的课，其余放进"更多选项"（完整编辑器）。
 * 编辑时把标题、时长同步给日程（update），轴上的"正在安排"块跟着变。
 */
import { computed, nextTick, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import BottomSheet from '@/components/common/BottomSheet.vue'
import { useTasksStore } from '@/stores/tasks'
import { useUiStore } from '@/stores/ui'
import { compactMinutes } from '@/utils/dates'
import { subjectInk, subjectOf } from '@/utils/subjects'

const props = defineProps({
  open: { type: Boolean, default: false },
  // 空闲段：{ start_time, end_time, minutes }
  slotInfo: { type: Object, default: null },
  date: { type: String, required: true },
  courses: { type: Array, default: () => [] },
})
const emit = defineEmits(['update', 'more', 'close'])
const tasks = useTasksStore()
const ui = useUiStore()

const title = ref('')
const minutes = ref(45)
const subject = ref('')
const saving = ref(false)
const input = ref(null)

const OPTIONS = [20, 30, 45, 60, 90]
const choices = computed(() => {
  const max = props.slotInfo?.minutes || 60
  const list = OPTIONS.filter((m) => m <= max)
  return list.length ? list : [max]
})
const subjects = computed(() => [...new Set(props.courses.map((c) => c.title))].slice(0, 4))

const toMin = (hm) => {
  const [h, m] = String(hm).split(':').map(Number)
  return h * 60 + m
}
const toHm = (v) => `${String(Math.floor(v / 60)).padStart(2, '0')}:${String(v % 60).padStart(2, '0')}`
const endTime = computed(() => (props.slotInfo ? toHm(toMin(props.slotInfo.start_time) + minutes.value) : ''))
const hint = computed(() => {
  if (!props.slotInfo) return ''
  const rest = props.slotInfo.minutes - minutes.value
  return `${props.slotInfo.start_time} - ${endTime.value}${rest >= 15 ? `，之后这段还空 ${compactMinutes(rest)}` : ''}`
})

watch(
  () => props.open,
  async (open) => {
    if (!open) return
    title.value = ''
    subject.value = ''
    minutes.value = choices.value.includes(45) ? 45 : choices.value[choices.value.length - 1]
    await nextTick()
    input.value?.focus()
  },
)
watch([title, minutes], () => props.open && emit('update', { title: title.value, minutes: minutes.value }))

const payload = () => ({
  title: title.value.trim(),
  subject: subject.value || null,
  due_date: props.date,
  start_time: props.slotInfo.start_time,
  duration_minutes: minutes.value,
})
const save = async () => {
  if (!title.value.trim()) {
    ui.toast('先写个名字', 'warning')
    input.value?.focus()
    return
  }
  saving.value = true
  try {
    await tasks.create({ ...payload(), source: 'quick' })
    emit('close')
  } catch (error) {
    ui.fail(error)
  } finally {
    saving.value = false
  }
}
const more = () => emit('more', { ...payload(), title: title.value.trim() || undefined })
</script>

<template>
  <BottomSheet :open="open" :title="slotInfo ? `在 ${slotInfo.start_time} 安排` : ''" :subtitle="slotInfo ? `空闲 ${compactMinutes(slotInfo.minutes)}` : ''" @close="emit('close')">
    <div v-if="slotInfo" class="space-y-3.5 pb-1">
      <input
        ref="input"
        v-model="title"
        class="field border-[1.5px] border-primary py-3.5 text-base font-bold"
        placeholder="准备做什么？"
        maxlength="200"
        enterkeyhint="done"
        aria-label="任务名称"
        @keydown.enter.prevent="save"
      />
      <div>
        <span class="label">时长</span>
        <div class="flex flex-wrap gap-1.5">
          <button v-for="m in choices" :key="m" type="button" class="chip num" :class="minutes === m && 'chip-active'" :aria-pressed="minutes === m" @click="minutes = m">
            {{ minutes === m ? `${m} 分钟` : m }}
          </button>
        </div>
        <p class="num mt-1.5 text-xs text-ink-mute">{{ hint }}</p>
      </div>
      <div v-if="subjects.length">
        <span class="label">科目</span>
        <div class="flex flex-wrap gap-1.5">
          <button
            v-for="s in subjects"
            :key="s"
            type="button"
            class="chip"
            :class="subject === s && 'chip-active'"
            :aria-pressed="subject === s"
            @click="subject = subject === s ? '' : s"
          >
            <i class="h-1.5 w-1.5 rounded-full" :style="{ background: subjectInk(subjectOf(s)) }" />{{ s }}
          </button>
        </div>
      </div>
    </div>
    <template #footer>
      <div class="grid grid-cols-[auto_1fr] gap-2.5">
        <button class="btn-ghost rounded-full" type="button" @click="more"><Icon icon="lucide:sliders-horizontal" width="15" />更多选项</button>
        <button class="btn-primary rounded-full" type="button" :disabled="saving" @click="save">
          <Icon v-if="saving" icon="lucide:loader-circle" width="16" class="animate-spin" />加入日程
        </button>
      </div>
    </template>
  </BottomSheet>
</template>
