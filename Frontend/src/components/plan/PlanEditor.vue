<script setup>
import { reactive, ref, watch } from 'vue'
import dayjs from 'dayjs'
import BottomSheet from '@/components/common/BottomSheet.vue'
import { usePlansStore } from '@/stores/plans'
import { useUiStore } from '@/stores/ui'
import { todayStr } from '@/utils/dates'

const props = defineProps({ open: { type: Boolean, default: false }, plan: { type: Object, default: null } })
const emit = defineEmits(['close', 'saved'])

const plans = usePlansStore()
const ui = useUiStore()
const saving = ref(false)
// undated：不设日期范围（长期的学习路线、以后再排的待办）
const form = reactive({ title: '', goal: '', start_date: '', end_date: '', undated: false })

watch(
  () => props.open,
  (open) => {
    if (!open) return
    Object.assign(form, {
      title: props.plan?.title || '',
      goal: props.plan?.goal || '',
      start_date: props.plan?.start_date || todayStr(),
      end_date: props.plan?.end_date || dayjs().add(13, 'day').format('YYYY-MM-DD'),
      undated: Boolean(props.plan?.undated),
    })
  },
)

const submit = async () => {
  if (!form.title.trim()) return ui.toast('请输入计划名称', 'warning')
  if (!form.undated && (!form.start_date || !form.end_date)) return ui.toast('请选择开始和结束日期，或勾选"不设日期"', 'warning')
  if (!form.undated && form.end_date < form.start_date) return ui.toast('结束日期不能早于开始日期', 'warning')
  saving.value = true
  try {
    const dates = form.undated ? { undated: true } : { start_date: form.start_date, end_date: form.end_date }
    const payload = { title: form.title.trim(), goal: form.goal.trim() || null, ...dates }
    const saved = props.plan ? await plans.update(props.plan.id, payload) : await plans.create(payload)
    emit('saved', saved)
    emit('close')
  } catch (error) {
    ui.fail(error)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <BottomSheet :open="open" :title="plan ? '编辑计划' : '新建学习计划'" @close="emit('close')">
    <form class="space-y-4" @submit.prevent="submit">
      <input v-model="form.title" class="field text-base font-semibold" placeholder="如：高数期末冲刺" maxlength="200" />
      <textarea v-model="form.goal" rows="2" class="field resize-none" placeholder="想达成的目标（可选）" maxlength="500" />
      <div v-if="!form.undated" class="grid grid-cols-2 gap-3">
        <label class="block"><span class="label">开始</span><input v-model="form.start_date" type="date" class="field" /></label>
        <label class="block"><span class="label">结束</span><input v-model="form.end_date" type="date" class="field" /></label>
      </div>
      <label class="flex cursor-pointer items-center gap-2 text-xs font-semibold text-ink-soft">
        <input v-model="form.undated" type="checkbox" class="accent-primary" />
        不设日期（长期路线或以后再排；里面的任务也可以不定日期）
      </label>
    </form>
    <template #footer>
      <button class="btn-primary w-full" type="button" :disabled="saving" @click="submit">{{ saving ? '保存中…' : plan ? '保存' : '创建计划' }}</button>
    </template>
  </BottomSheet>
</template>
