<script setup>
/** 修改已有任务 / 课程的提案：修改前 → 修改后对比，逐条勾选后应用，逐条显示结果。 */
import { computed, reactive, ref } from 'vue'
import { Icon } from '@iconify/vue'
import { useAiStore } from '@/stores/ai'
import { useUiStore } from '@/stores/ui'

const props = defineProps({
  message: { type: Object, required: true },
  proposal: { type: Object, required: true },
})
const ai = useAiStore()
const ui = useUiStore()
const busy = ref(false)

const items = computed(() => props.proposal.items || [])
const result = (c) => props.proposal.results?.[c.key]
const done = (c) => Boolean(result(c)?.ok)
const picked = reactive(new Set(items.value.filter((c) => !done(c)).map((c) => c.key)))
const toggle = (c) => (picked.has(c.key) ? picked.delete(c.key) : picked.add(c.key))
const chosen = computed(() => items.value.filter((c) => !done(c) && picked.has(c.key)))
const allDone = computed(() => items.value.length > 0 && items.value.every(done))
const deletes = computed(() => chosen.value.filter((c) => c.action === 'delete').length)

const apply = async () => {
  if (deletes.value) {
    const ok = await ui.confirm({ title: '确认删除', message: `将删除 ${deletes.value} 项，删除后不能恢复。`, confirmText: '确认应用', danger: true })
    if (!ok) return
  }
  busy.value = true
  try {
    const payload = chosen.value.map((c) => ({ key: c.key, target: c.target, id: c.id, action: c.action, changes: c.changes || {}, title: c.title }))
    await ai.applyProposal(props.message, props.proposal, payload)
    items.value.forEach((c) => done(c) && picked.delete(c.key))
  } catch (error) {
    ui.fail(error)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="overflow-hidden rounded-3xl border border-ink-line/70 bg-surface shadow-soft">
    <div class="flex items-center gap-2 border-b border-ink-line/60 bg-flame-light/60 px-4 py-3">
      <Icon icon="lucide:git-compare" width="18" class="text-flame" />
      <div class="min-w-0">
        <p class="text-sm font-black text-ink">修改已有内容 · {{ items.length }} 项</p>
        <p class="truncate text-[11px] text-ink-mute">{{ proposal.summary || '确认后才会修改，可以逐条取消' }}</p>
      </div>
    </div>

    <div class="space-y-2 px-4 py-3">
      <div v-for="c in items" :key="c.key" class="rounded-2xl px-3 py-2.5" :class="[done(c) ? 'bg-success-light/60' : result(c) && !result(c).ok ? 'bg-danger-light/60' : 'bg-background', !done(c) && !picked.has(c.key) && 'opacity-50']">
        <div class="flex items-center gap-2">
          <input v-if="!done(c)" type="checkbox" class="accent-primary" :checked="picked.has(c.key)" :aria-label="`选择 ${c.title}`" @change="toggle(c)" />
          <Icon v-else icon="lucide:circle-check" width="16" class="shrink-0 text-success" />
          <Icon :icon="c.target === 'course' ? 'lucide:book-open' : 'lucide:list-todo'" width="14" class="shrink-0 text-ink-mute" />
          <span class="min-w-0 flex-1 truncate text-xs font-bold text-ink">{{ c.title }}</span>
          <span class="shrink-0 rounded-full px-2 py-0.5 text-[10px] font-bold" :class="c.action === 'delete' ? 'bg-danger-light text-danger' : 'bg-primary-light text-primary'">{{ c.action === 'delete' ? '删除' : '修改' }}</span>
        </div>
        <div class="mt-1.5 space-y-1 pl-6">
          <p v-if="c.action === 'delete'" class="text-[11px] text-danger line-through decoration-danger/50">{{ c.summary }}</p>
          <div v-for="d in c.diff || []" :key="d.field" class="flex flex-wrap items-center gap-1 text-[11px]">
            <span class="w-10 shrink-0 font-bold text-ink-mute">{{ d.field }}</span>
            <span class="text-ink-mute line-through">{{ d.before }}</span>
            <Icon icon="lucide:arrow-right" width="12" class="text-ink-mute" />
            <span class="font-bold text-ink">{{ d.after }}</span>
          </div>
          <p v-if="c.reason" class="text-[10px] text-ink-mute">原因：{{ c.reason }}</p>
          <template v-if="!done(c)">
            <p v-for="w in c.warnings || []" :key="w" class="flex gap-1 text-[11px] font-semibold text-flame"><Icon icon="lucide:triangle-alert" width="12" class="mt-0.5 shrink-0" />{{ w }}</p>
          </template>
          <p v-if="done(c)" class="text-[11px] font-semibold text-success">已应用</p>
          <p v-else-if="result(c)" class="flex gap-1 text-[11px] font-bold text-danger"><Icon icon="lucide:circle-x" width="12" class="mt-0.5 shrink-0" />未应用：{{ result(c).reason }}</p>
        </div>
      </div>
    </div>

    <div class="border-t border-ink-line/60 p-3">
      <p v-if="allDone" class="btn w-full bg-success-light text-success"><Icon icon="lucide:circle-check" width="16" />全部已应用</p>
      <button v-else class="btn-primary w-full" type="button" :disabled="busy || !chosen.length || ai.streaming" @click="apply">
        <Icon :icon="busy ? 'lucide:loader-circle' : 'lucide:check'" width="16" :class="busy && 'animate-spin'" />
        {{ busy ? '正在应用…' : chosen.length ? `应用 ${chosen.length} 项修改` : '请勾选要应用的修改' }}
      </button>
    </div>
  </div>
</template>
