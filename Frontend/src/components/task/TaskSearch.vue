<script setup>
import { onBeforeUnmount, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import TaskItem from '@/components/task/TaskItem.vue'
import { taskApi } from '@/api'
import { useUiStore } from '@/stores/ui'

/** 首页顶部：左侧按关键词搜索全部任务（标题 / 科目 / 备注），右侧"添加任务"按钮打开完整编辑器。 */
const emit = defineEmits(['add', 'open', 'toggle', 'focus', 'searching'])
const ui = useUiStore()

const q = ref('')
const results = ref([])
const loading = ref(false)
let timer = null
let ticket = 0

const search = async (keyword) => {
  const current = ++ticket
  loading.value = true
  try {
    const data = await taskApi.search(keyword)
    if (current === ticket) results.value = data.items
  } catch (error) {
    if (current === ticket) ui.fail(error)
  } finally {
    if (current === ticket) loading.value = false
  }
}

watch(q, (value) => {
  clearTimeout(timer)
  const keyword = value.trim()
  emit('searching', Boolean(keyword))
  if (!keyword) {
    ticket++
    results.value = []
    loading.value = false
    return
  }
  timer = setTimeout(() => search(keyword), 250)
})
onBeforeUnmount(() => clearTimeout(timer))

const clear = () => (q.value = '')
/** 列表里的任务被修改后重新搜索一次，保证结果是最新的。 */
const refresh = () => q.value.trim() && search(q.value.trim())
defineExpose({ refresh, clear })
</script>

<template>
  <div>
    <div class="flex items-stretch gap-2">
      <label class="flex min-w-0 flex-1 items-center gap-2 rounded-2xl border border-ink-line/70 bg-surface px-3 shadow-soft focus-within:border-primary/40 focus-within:ring-4 focus-within:ring-primary/10">
        <Icon icon="lucide:search" width="18" class="shrink-0 text-ink-mute" />
        <input
          v-model="q"
          class="min-w-0 flex-1 bg-transparent py-3 text-sm outline-none placeholder:text-ink-mute"
          placeholder="搜索任务：标题、科目、备注"
          maxlength="50"
          enterkeyhint="search"
          aria-label="搜索任务"
          @keydown.esc="clear"
        />
        <Icon v-if="loading" icon="lucide:loader-circle" width="16" class="shrink-0 animate-spin text-ink-mute" />
        <button v-else-if="q" class="shrink-0 rounded-full p-1 text-ink-mute hover:bg-background" type="button" aria-label="清空搜索" @click="clear">
          <Icon icon="lucide:x" width="14" />
        </button>
      </label>
      <button class="btn-primary shrink-0 px-4 py-3 text-sm lg:px-5" type="button" aria-label="添加任务" @click="emit('add')">
        <Icon icon="lucide:plus" width="18" />添加任务
      </button>
    </div>

    <section v-if="q.trim()" class="mt-4 space-y-2" aria-live="polite">
      <p class="px-1 text-xs font-black text-ink-soft">
        搜索「{{ q.trim() }}」<span class="text-ink-mute"> · {{ loading && !results.length ? '搜索中…' : `${results.length} 个结果` }}</span>
      </p>
      <TaskItem v-for="task in results" :key="task.id" :task="task" show-date @toggle="(t) => emit('toggle', t)" @open="(t) => emit('open', t)" @focus="(t) => emit('focus', t)" />
      <p v-if="!loading && !results.length" class="rounded-2xl bg-surface px-4 py-6 text-center text-xs text-ink-mute">没有找到相关任务，换个关键词试试</p>
    </section>
  </div>
</template>
