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
const form = reactive({ title: '', goal: '', start_date: '', end_date: '' })

watch(
  () => props.open,
  (open) => {
    if (!open) return
    Object.assign(form, {
      title: props.plan?.title || '',
      goal: props.plan?.goal || '',
      start_date: props.plan?.start_date || todayStr(),
      end_date: props.plan?.end_date || dayjs().add(13, 'day').format('YYYY-MM-DD'),
    })
  },
)

const submit = async () => {
  if (!form.title.trim()) return ui.toast('请输入计划名称', 'warning')
  if (form.end_date < form.start_date) return ui.toast('结束日期不能早于开始日期', 'warning')
  saving.value = true
  try {
    const payload = { title: form.title.trim(), goal: form.goal.trim() || null, start_date: form.start_date, end_date: form.end_date }
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
      <div class="grid grid-cols-2 gap-3">
        <label class="block"><span class="label">开始</span><input v-model="form.start_date" type="date" class="field" /></label>
        <label class="block"><span class="label">结束</span><input v-model="form.end_date" type="date" class="field" /></label>
      </div>
    </form>
    <template #footer>
      <button class="btn-primary w-full" type="button" :disabled="saving" @click="submit">{{ saving ? '保存中…' : plan ? '保存' : '创建计划' }}</button>
    </template>
  </BottomSheet>
</template>
