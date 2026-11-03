<script setup>
/**
 * 删除已有任务 / 课程的提案（可批量）：列出待删项，勾选后二次确认、逐条删除并显示结果；
 * 删除的内容可以在卡片上逐条或全部撤销（服务器按删除前的快照恢复）。
 */
import { computed, reactive, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import AiBadge from './AiBadge.vue'
import { useAiStore } from '@/stores/ai'
import { useUiStore } from '@/stores/ui'

const props = defineProps({
  message: { type: Object, required: true },
  proposal: { type: Object, required: true },
})
const ai = useAiStore()
const ui = useUiStore()
const busy = ref('')

const items = computed(() => props.proposal.items || [])
const result = (c) => props.proposal.results?.[c.key]
const deleted = (c) => Boolean(result(c)?.ok && !result(c)?.undone)
const undone = (c) => Boolean(result(c)?.undone)
const canUndo = (c) => deleted(c) && result(c)?.can_undo && typeof props.message.id === 'number'

const picked = reactive(new Set(items.value.filter((c) => !result(c)?.ok).map((c) => c.key)))
watch(() => props.proposal.id, () => {
  picked.clear()
  items.value.forEach((c) => picked.add(c.key))
})
const selectable = computed(() => items.value.filter((c) => !deleted(c)))
const chosen = computed(() => selectable.value.filter((c) => picked.has(c.key)))
const allPicked = computed(() => selectable.value.length > 0 && chosen.value.length === selectable.value.length)
const toggle = (c) => (picked.has(c.key) ? picked.delete(c.key) : picked.add(c.key))
const toggleAll = () => {
  const on = !allPicked.value
  selectable.value.forEach((c) => (on ? picked.add(c.key) : picked.delete(c.key)))
}
const taskItems = computed(() => items.value.filter((c) => c.target !== 'course'))
const courseItems = computed(() => items.value.filter((c) => c.target === 'course'))
const sections = computed(() => [
  { key: 'task', label: '任务', icon: 'lucide:list-todo', list: taskItems.value },
  { key: 'course', label: '课程', icon: 'lucide:book-open', list: courseItems.value },
].filter((s) => s.list.length))
const undoable = computed(() => items.value.filter(canUndo))
const allDeleted = computed(() => items.value.length > 0 && items.value.every((c) => deleted(c)))

const apply = async () => {
  const tasks = chosen.value.filter((c) => c.target !== 'course').length
  const courses = chosen.value.filter((c) => c.target === 'course')
  const parts = [tasks && `${tasks} 个任务`, courses.length && `${courses.length} 门课程`].filter(Boolean).join('、')
  const courseNote = courses.length ? `课程「${[...new Set(courses.map((c) => c.title))].join('、')}」会从课表的每一周移除。` : ''
  const ok = await ui.confirm({
    title: '确认删除',
    message: `将删除 ${parts}。${courseNote}删除后可以在卡片上撤销。`,
    confirmText: `删除 ${chosen.value.length} 项`,
    danger: true,
  })
  if (!ok) return
  busy.value = 'apply'
  try {
    const payload = chosen.value.map((c) => ({ key: c.key, target: c.target, id: c.id, title: c.title }))
    await ai.applyProposal(props.message, props.proposal, payload)
    items.value.forEach((c) => deleted(c) && picked.delete(c.key))
  } catch (error) {
    ui.fail(error)
  } finally {
    busy.value = ''
  }
}

const undo = async (keys = null) => {
  busy.value = keys ? keys[0] : 'all'
  try {
    await ai.undoProposal(props.message, props.proposal, keys)
  } catch (error) {
    ui.fail(error)
  } finally {
    busy.value = ''
  }
}
</script>

<template>
  <div class="overflow-hidden rounded-3xl border border-ink-line/70 bg-surface shadow-soft">
    <div class="flex items-center gap-2 border-b border-ink-line/60 bg-danger-light/60 px-4 py-3">
      <Icon icon="lucide:trash-2" width="18" class="text-danger" />
      <div class="min-w-0 flex-1">
        <p class="flex items-center gap-1.5 text-sm font-black text-ink">删除已有内容 · {{ items.length }} 项<AiBadge label="AI 建议" /></p>
        <p class="truncate text-[11px] text-ink-mute">{{ proposal.summary || '确认后才会删除，可以逐条取消；删除后可撤销' }}</p>
      </div>
    </div>

    <div class="px-4 py-3">
      <label v-if="selectable.length > 1" class="mb-2 flex cursor-pointer items-center gap-2 text-xs font-black text-ink">
        <input type="checkbox" class="accent-danger" :checked="allPicked" :indeterminate.prop="chosen.length > 0 && !allPicked" aria-label="全选要删除的内容" @change="toggleAll" />
        全选
        <span class="ml-auto font-semibold text-ink-mute">已选 {{ chosen.length }}/{{ selectable.length }}</span>
      </label>

      <div class="space-y-3">
        <div v-for="s in sections" :key="s.key">
          <p class="mb-1.5 flex items-center gap-1 text-[11px] font-black text-ink-soft"><Icon :icon="s.icon" width="13" />{{ s.label }} · {{ s.list.length }}</p>
          <div class="space-y-1.5">
            <div
              v-for="c in s.list"
              :key="c.key"
              class="rounded-2xl px-3 py-2"
              :class="[deleted(c) ? 'bg-background' : result(c) && !result(c).ok ? 'bg-danger-light/60' : undone(c) ? 'bg-success-light/50' : 'bg-background', !deleted(c) && !picked.has(c.key) && 'opacity-50']"
            >
              <div class="flex items-center gap-2">
                <input v-if="!deleted(c)" type="checkbox" class="accent-danger" :checked="picked.has(c.key)" :aria-label="`选择删除 ${c.title}`" @change="toggle(c)" />
                <Icon v-else icon="lucide:trash-2" width="15" class="shrink-0 text-ink-mute" />
                <span class="min-w-0 flex-1 truncate text-xs font-bold" :class="deleted(c) ? 'text-ink-mute line-through' : 'text-ink'">{{ c.title }}</span>
                <button v-if="canUndo(c)" type="button" class="flex shrink-0 items-center gap-0.5 rounded-full bg-surface px-2 py-0.5 text-[10px] font-bold text-primary" :disabled="Boolean(busy)" @click="undo([c.key])">
                  <Icon :icon="busy === c.key ? 'lucide:loader-circle' : 'lucide:undo-2'" width="11" :class="busy === c.key && 'animate-spin'" />撤销
                </button>
              </div>
              <p class="num mt-0.5 pl-6 text-[11px] text-ink-mute">{{ c.summary }}</p>
              <p v-if="c.reason && !deleted(c)" class="pl-6 text-[10px] text-ink-mute">原因：{{ c.reason }}</p>
              <template v-if="!result(c)?.ok">
                <p v-for="w in c.warnings || []" :key="w" class="mt-0.5 flex gap-1 pl-6 text-[11px] font-semibold text-flame"><Icon icon="lucide:triangle-alert" width="12" class="mt-0.5 shrink-0" />{{ w }}</p>
              </template>
              <p v-if="deleted(c)" class="mt-0.5 pl-6 text-[11px] font-semibold text-danger">已删除</p>
              <p v-else-if="undone(c)" class="mt-0.5 pl-6 text-[11px] font-semibold text-success">已撤销删除，已恢复</p>
              <p v-else-if="result(c)" class="mt-0.5 flex gap-1 pl-6 text-[11px] font-bold text-danger"><Icon icon="lucide:circle-x" width="12" class="mt-0.5 shrink-0" />未删除：{{ result(c).reason }}</p>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="space-y-2 border-t border-ink-line/60 p-3">
      <button v-if="!allDeleted" class="btn-danger w-full" type="button" :disabled="Boolean(busy) || !chosen.length || ai.streaming" @click="apply">
        <Icon :icon="busy === 'apply' ? 'lucide:loader-circle' : 'lucide:trash-2'" width="16" :class="busy === 'apply' && 'animate-spin'" />
        {{ busy === 'apply' ? '正在删除…' : chosen.length ? `确认删除 ${chosen.length} 项` : '请勾选要删除的内容' }}
      </button>
      <button v-if="undoable.length" class="btn-ghost w-full" type="button" :disabled="Boolean(busy)" @click="undo()">
        <Icon :icon="busy === 'all' ? 'lucide:loader-circle' : 'lucide:undo-2'" width="16" :class="busy === 'all' && 'animate-spin'" />
        撤销删除（{{ undoable.length }} 项）
      </button>
    </div>
  </div>
</template>
