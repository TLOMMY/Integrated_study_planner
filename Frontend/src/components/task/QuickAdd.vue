<script setup>
import { computed, ref } from 'vue'
import { Icon } from '@iconify/vue'
import { parseQuickAdd } from '@/utils/quickAdd'
import { useTasksStore } from '@/stores/tasks'
import { useUiStore } from '@/stores/ui'

const emit = defineEmits(['expand'])
const tasks = useTasksStore()
const ui = useUiStore()

const text = ref('')
const busy = ref(false)
const parsed = computed(() => (text.value.trim() ? parseQuickAdd(text.value) : null))

const submit = async () => {
  const result = parsed.value
  if (!result || busy.value) return
  if (!result.title) return ui.toast('请写上要做的事', 'warning')
  busy.value = true
  try {
    const { tokens, ...payload } = result
    await tasks.create({ ...payload, source: 'quick' })
    text.value = ''
  } catch (error) {
    ui.fail(error)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="rounded-3xl border border-ink-line/70 bg-surface p-2 shadow-soft">
    <div class="flex items-center gap-2">
      <Icon icon="lucide:plus" width="20" class="ml-2 shrink-0 text-primary" />
      <input
        v-model="text"
        class="min-w-0 flex-1 bg-transparent py-2 text-sm outline-none placeholder:text-ink-mute"
        placeholder="明天下午3点 复习高数 !高"
        maxlength="200"
        enterkeyhint="done"
        aria-label="快速添加任务"
        @keydown.enter.prevent="submit"
      />
      <button
        v-if="text.trim()"
        class="flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl bg-primary text-white active:scale-95"
        type="button"
        aria-label="添加"
        :disabled="busy"
        @click="submit"
      >
        <Icon :icon="busy ? 'lucide:loader-circle' : 'lucide:arrow-up'" width="18" :class="busy && 'animate-spin'" />
      </button>
      <button v-else class="flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl bg-background text-ink-soft" type="button" aria-label="详细添加" @click="emit('expand')">
        <Icon icon="lucide:sliders-horizontal" width="16" />
      </button>
    </div>
    <div v-if="parsed?.tokens.length" class="flex flex-wrap gap-1.5 px-2 pb-1 pt-1">
      <span v-for="token in parsed.tokens" :key="token.text" class="inline-flex items-center gap-1 rounded-lg bg-primary-light px-2 py-0.5 text-[11px] font-bold text-primary">
        <Icon :icon="token.icon" width="11" />{{ token.text }}
      </span>
    </div>
  </div>
</template>
