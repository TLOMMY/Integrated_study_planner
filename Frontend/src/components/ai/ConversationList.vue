<script setup>
/** 会话列表：新建、切换、重命名（行内编辑）、删除。电脑端放左栏，手机端放抽屉。 */
import { nextTick, ref } from 'vue'
import dayjs from 'dayjs'
import { Icon } from '@iconify/vue'
import { useAiStore } from '@/stores/ai'
import { useUiStore } from '@/stores/ui'

const emit = defineEmits(['picked'])
const ai = useAiStore()
const ui = useUiStore()
const editingId = ref(null)
const draft = ref('')
const input = ref(null)

const when = (iso) => {
  if (!iso) return ''
  const d = dayjs(iso)
  return d.isSame(dayjs(), 'day') ? d.format('HH:mm') : d.isSame(dayjs(), 'year') ? d.format('M/D') : d.format('YYYY/M/D')
}

const pick = async (c) => {
  if (editingId.value) return
  await ai.select(c.id)
  emit('picked')
}
const create = () => {
  ai.newConversation()
  emit('picked')
}
const startRename = async (c) => {
  editingId.value = c.id
  draft.value = c.title
  await nextTick()
  input.value?.[0]?.focus()
}
const saveRename = async (c) => {
  const title = draft.value.trim()
  editingId.value = null
  if (!title || title === c.title) return
  try {
    await ai.rename(c.id, title.slice(0, 100))
  } catch (error) {
    ui.fail(error)
  }
}
const remove = (c) => ai.remove(c).catch((error) => ui.fail(error))
</script>

<template>
  <div class="flex h-full flex-col">
    <div class="p-3">
      <button class="btn-primary w-full py-2.5" type="button" :disabled="ai.streaming" @click="create"><Icon icon="lucide:plus" width="16" />新对话</button>
    </div>
    <div class="scrollbar-hide flex-1 space-y-1 overflow-y-auto px-2 pb-3">
      <p v-if="!ai.conversations.length" class="px-3 py-6 text-center text-xs text-ink-mute">还没有对话</p>
      <div
        v-for="c in ai.conversations"
        :key="c.id"
        class="group flex items-center gap-2 rounded-2xl px-3 py-2.5 transition"
        :class="c.id === ai.currentId ? 'bg-primary-light' : 'hover:bg-background'"
      >
        <Icon icon="lucide:message-square" width="15" class="shrink-0" :class="c.id === ai.currentId ? 'text-primary' : 'text-ink-mute'" />
        <input
          v-if="editingId === c.id"
          ref="input"
          v-model="draft"
          maxlength="100"
          class="min-w-0 flex-1 rounded-lg border border-primary/40 bg-surface px-2 py-1 text-xs text-ink outline-none"
          aria-label="对话名称"
          @keydown.enter.prevent="saveRename(c)"
          @keydown.esc="editingId = null"
          @blur="saveRename(c)"
        />
        <button v-else type="button" class="min-w-0 flex-1 text-left" :disabled="ai.streaming" @click="pick(c)">
          <span class="block truncate text-xs font-bold" :class="c.id === ai.currentId ? 'text-primary' : 'text-ink'">{{ c.title }}</span>
          <span class="block truncate text-[10px] text-ink-mute">{{ when(c.updated_at) }}<template v-if="c.preview"> · {{ c.preview }}</template></span>
        </button>
        <template v-if="editingId !== c.id">
          <button type="button" class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-ink-mute hover:bg-surface hover:text-ink lg:opacity-0 lg:group-hover:opacity-100" :aria-label="`重命名 ${c.title}`" @click="startRename(c)"><Icon icon="lucide:pencil" width="13" /></button>
          <button type="button" class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-ink-mute hover:bg-danger-light hover:text-danger lg:opacity-0 lg:group-hover:opacity-100" :aria-label="`删除 ${c.title}`" @click="remove(c)"><Icon icon="lucide:trash-2" width="13" /></button>
        </template>
      </div>
    </div>
  </div>
</template>
