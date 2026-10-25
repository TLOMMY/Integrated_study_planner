<script setup>
import { onMounted, reactive, ref } from 'vue'
import { Icon } from '@iconify/vue'
import { adminApi } from '@/api/admin'
import { useUiStore } from '@/stores/ui'
import Pager from './Pager.vue'
import { fullTime, timeAgo } from './meta'

const ui = useUiStore()
const filter = reactive({ q: '', days: 30, page: 1 })
const result = ref({ items: [], total: 0, size: 20 })
const loading = ref(false)
const open = ref(new Set())

const load = async () => {
  loading.value = true
  try {
    result.value = await adminApi.errors({ ...filter, size: 20 })
  } catch (error) {
    ui.fail(error)
  } finally {
    loading.value = false
  }
}
const search = () => {
  filter.page = 1
  load()
}
const toggle = (id) => {
  const next = new Set(open.value)
  next.has(id) ? next.delete(id) : next.add(id)
  open.value = next
}
const remove = async (row) => {
  if (!(await ui.confirm({ title: '删除这组错误？', message: '确认已修复后再删除；之后再出现会重新计数。', confirmText: '删除', danger: true }))) return
  try {
    await adminApi.removeError(row.id)
    result.value.items = result.value.items.filter((r) => r.id !== row.id)
    result.value.total -= 1
    ui.success('已删除')
  } catch (error) {
    ui.fail(error)
  }
}
onMounted(load)
defineExpose({ load })
</script>

<template>
  <div class="space-y-3">
    <form class="flex gap-2" @submit.prevent="search">
      <select v-model.number="filter.days" class="field w-28 shrink-0 py-2.5" aria-label="时间范围" @change="search">
        <option :value="1">24 小时</option><option :value="7">7 天</option><option :value="30">30 天</option><option :value="365">一年</option>
      </select>
      <input v-model="filter.q" class="field py-2.5" type="search" placeholder="搜索错误信息 / 页面" aria-label="搜索错误" />
      <button class="btn-ghost shrink-0 px-3 py-2.5" type="submit" aria-label="搜索"><Icon icon="lucide:search" width="16" /></button>
    </form>
    <p class="px-1 text-[11px] text-ink-mute">相同的错误信息 + 堆栈首行合并为一组；前端每个页面每分钟最多上报 5 条</p>

    <div v-if="loading && !result.items.length" class="space-y-2"><div v-for="i in 3" :key="i" class="skeleton h-16" /></div>
    <p v-else-if="!result.items.length" class="card py-10 text-center text-sm text-ink-mute"><Icon icon="lucide:badge-check" width="28" class="mx-auto mb-2 text-success" />这段时间没有前端错误</p>

    <div v-else class="space-y-2 lg:grid lg:grid-cols-2 lg:gap-3 lg:space-y-0">
      <article v-for="r in result.items" :key="r.id" class="card min-w-0 p-3">
        <div class="flex items-start gap-3">
          <span class="num flex h-9 min-w-[36px] shrink-0 items-center justify-center rounded-xl bg-danger-light px-1.5 text-sm font-black text-danger" :title="`共出现 ${r.count} 次`">{{ r.count }}</span>
          <div class="min-w-0 flex-1">
            <p class="break-words text-sm font-bold text-ink">{{ r.message }}</p>
            <p class="mt-0.5 truncate text-[11px] text-ink-mute">{{ r.page || '—' }} · v{{ r.version || '?' }} · 最近 {{ timeAgo(r.last_seen) }}<template v-if="r.user_id"> · 用户 #{{ r.user_id }}</template></p>
          </div>
          <button class="shrink-0 rounded-full p-1.5 text-ink-mute hover:bg-background" type="button" aria-label="删除" @click="remove(r)"><Icon icon="lucide:trash-2" width="15" /></button>
        </div>
        <button v-if="r.stack" class="mt-2 flex items-center gap-1 text-[11px] font-bold text-primary" type="button" :aria-expanded="open.has(r.id)" @click="toggle(r.id)">
          <Icon :icon="open.has(r.id) ? 'lucide:chevron-up' : 'lucide:chevron-down'" width="13" />{{ open.has(r.id) ? '收起堆栈' : '查看堆栈' }}
        </button>
        <div v-if="open.has(r.id)" class="mt-2 space-y-1">
          <pre class="scrollbar-hide max-h-56 overflow-auto whitespace-pre-wrap break-all rounded-xl bg-background p-2 text-[10px] leading-4 text-ink-soft">{{ r.stack }}</pre>
          <p class="break-all text-[10px] text-ink-mute">首次 {{ fullTime(r.first_seen) }} · {{ r.client }}</p>
        </div>
      </article>
    </div>
    <Pager v-model="filter.page" :total="result.total" :size="result.size" @update:model-value="load" />
  </div>
</template>
