<script setup>
import { computed, ref, watch } from 'vue'
import dayjs from 'dayjs'
import { Icon } from '@iconify/vue'
import BottomSheet from '@/components/common/BottomSheet.vue'
import TaskItem from '@/components/task/TaskItem.vue'
import TaskEditor from '@/components/task/TaskEditor.vue'
import { usePlansStore } from '@/stores/plans'
import { useTasksStore } from '@/stores/tasks'
import { useUiStore } from '@/stores/ui'
import { useRouter } from 'vue-router'
import { focusRoute } from '@/utils/task'
import { relativeDay, todayStr } from '@/utils/dates'

const props = defineProps({ planId: { type: Number, default: null } })
const emit = defineEmits(['close', 'edit'])

const plans = usePlansStore()
const tasks = useTasksStore()
const ui = useUiStore()
const router = useRouter()
const plan = ref(null)
const editor = ref({ open: false, task: null })

const load = async () => {
  if (!props.planId) return
  try {
    plan.value = await plans.detail(props.planId)
  } catch (error) {
    ui.fail(error)
    emit('close')
  }
}
watch(() => props.planId, (id) => (id ? load() : (plan.value = null)), { immediate: true })

const groups = computed(() => {
  const map = new Map()
  for (const task of plan.value?.tasks || []) {
    const key = task.due_date || 'none'
    if (!map.has(key)) map.set(key, { key, label: task.due_date ? relativeDay(task.due_date) : '无日期', items: [] })
    map.get(key).items.push(task)
  }
  return [...map.values()]
})

const toggle = async (task) => {
  await tasks.toggle(task)
  await load()
  plans.load()
}
const setStatus = async (status) => {
  const wasArchived = plan.value.status === 'archived'
  plan.value = await plans.update(plan.value.id, { status }, status === 'archived' ? '已归档，未完成的任务暂时不出现在今天和即将里' : status === 'completed' ? '已标记完成' : '已恢复')
  if (status === 'active' && wasArchived) await offerShift()
  tasks.afterChange()
}

/**
 * 从归档恢复时，如果未完成的任务日期已经过了，问一句要不要整体顺延：
 * 以最早的那天对齐到今天，任务之间的间隔、时刻和时长保持不变。
 */
const offerShift = async () => {
  const open = (plan.value.tasks || []).filter((t) => !t.completed && t.due_date)
  const earliest = open.map((t) => t.due_date).sort()[0]
  const today = todayStr()
  if (!earliest || earliest >= today) return
  const days = dayjs(today).diff(dayjs(earliest), 'day')
  const ok = await ui.confirm({
    title: '未完成的任务日期已过',
    message: `有 ${open.length} 个未完成的任务最早排在 ${dayjs(earliest).format('M月D日')}。整体顺延 ${days} 天，从今天开始？任务之间的间隔和时刻保持不变。`,
    confirmText: `顺延 ${days} 天`,
    cancelText: '保持原日期',
  })
  if (!ok) return
  await tasks.batch({ ids: open.map((t) => t.id), action: 'move', shift_days: days }, `已顺延 ${open.length} 个任务`).catch(ui.fail)
  await load()
}
const remove = async () => {
  if (await plans.remove(plan.value)) emit('close')
}
</script>

<template>
  <BottomSheet :open="Boolean(planId)" :title="plan?.title || ''" :subtitle="plan ? `${plan.undated ? '不设日期' : `${plan.start_date} ~ ${plan.end_date}`} · ${plan.status_label}` : ''" @close="emit('close')">
    <div v-if="!plan" class="space-y-2 pb-4"><div v-for="i in 3" :key="i" class="skeleton h-14" /></div>
    <template v-else>
      <p v-if="plan.goal" class="rounded-2xl bg-background px-4 py-3 text-sm text-ink-soft">🎯 {{ plan.goal }}</p>
      <div class="mt-3 flex items-center gap-3">
        <div class="h-2 flex-1 overflow-hidden rounded-full bg-ink-line"><div class="h-full rounded-full bg-success transition-all" :style="{ width: `${plan.progress}%` }" /></div>
        <span class="num text-xs font-black text-ink">{{ plan.task_done }}/{{ plan.task_total }}</span>
      </div>

      <div class="mt-4 space-y-4">
        <div v-for="group in groups" :key="group.key">
          <h4 class="mb-2 text-xs font-black text-ink-soft">{{ group.label }}</h4>
          <div class="space-y-2">
            <TaskItem v-for="t in group.items" :key="t.id" :task="t" hide-plan @toggle="toggle" @open="(x) => (editor = { open: true, task: x })" @focus="(x) => router.push(focusRoute(x))" />
          </div>
        </div>
        <button class="btn-ghost w-full" type="button" @click="editor = { open: true, task: null }"><Icon icon="lucide:plus" width="16" />添加任务到此计划</button>
      </div>
    </template>

    <template v-if="plan" #footer>
      <div class="grid grid-cols-[auto_auto_auto_1fr] gap-2">
        <button class="btn-danger px-3" type="button" aria-label="移入回收站" title="移入回收站" @click="remove"><Icon icon="lucide:trash-2" width="16" /></button>
        <button class="btn-ghost px-3" type="button" aria-label="编辑计划" title="编辑" @click="emit('edit', plan)"><Icon icon="lucide:pencil" width="16" /></button>
        <!-- 归档：暂时搁置、不想再看到，但保留全部记录；和"已完成"不同，不要求任务做完 -->
        <button v-if="plan.status !== 'archived'" class="btn-ghost px-3" type="button" aria-label="归档计划" title="归档：暂时搁置，不删除" @click="setStatus('archived')"><Icon icon="lucide:archive" width="16" /></button>
        <span v-else />
        <button v-if="plan.status === 'active'" class="btn-primary" type="button" @click="setStatus('completed')"><Icon icon="lucide:flag" width="16" />标记完成</button>
        <button v-else class="btn-ghost" type="button" @click="setStatus('active')"><Icon icon="lucide:rotate-ccw" width="16" />恢复为进行中</button>
      </div>
    </template>
  </BottomSheet>
  <!-- 放在详情弹层之后挂载，保证叠在它上面 -->
  <TaskEditor :open="editor.open" :task="editor.task" :defaults="{ plan_id: plan?.id, due_date: plan?.undated ? null : todayStr() }" @close="editor.open = false" @saved="load" />
</template>
