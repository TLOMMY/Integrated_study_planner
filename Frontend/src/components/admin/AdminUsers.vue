<script setup>
import { onMounted, reactive, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import BottomSheet from '@/components/common/BottomSheet.vue'
import { adminApi } from '@/api/admin'
import { useDesktop } from '@/composables/useDesktop'
import { useUiStore } from '@/stores/ui'
import { formatMinutes } from '@/utils/dates'
import Pager from './Pager.vue'
import UserDetail from './UserDetail.vue'
import { timeAgo } from './meta'

const props = defineProps({ focusId: { type: Number, default: null } })
const STATUS = [
  { key: '', label: '全部' },
  { key: 'active', label: '正常' },
  { key: 'disabled', label: '已停用' },
  { key: 'admin', label: '管理员' },
]
const ui = useUiStore()
const desktop = useDesktop()
const filter = reactive({ q: '', status: '', page: 1 })
const result = ref({ items: [], total: 0, size: 20 })
const loading = ref(false)
const current = ref(props.focusId)
watch(() => props.focusId, (id) => id && (current.value = id))

const load = async () => {
  loading.value = true
  try {
    result.value = await adminApi.users({ ...filter, size: 20 })
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
const onChanged = (u) => {
  const i = result.value.items.findIndex((r) => r.id === u.id)
  if (i >= 0) result.value.items[i] = { ...result.value.items[i], ...u }
}
onMounted(load)
defineExpose({ load })

const badges = (u) => [
  !u.is_active && { text: '停用', cls: 'bg-danger-light text-danger' },
  u.is_admin && { text: '管理员', cls: 'bg-xp-light text-xp' },
  u.is_demo && { text: '演示', cls: 'bg-flame-light text-flame' },
].filter(Boolean)
</script>

<template>
  <div class="lg:grid lg:grid-cols-[minmax(0,1fr)_400px] lg:items-start lg:gap-4">
    <div class="min-w-0 space-y-3">
      <div class="flex gap-2">
        <button v-for="s in STATUS" :key="s.key" type="button" class="chip" :class="filter.status === s.key && 'chip-active'" @click="filter.status = s.key; search()">{{ s.label }}</button>
      </div>
      <form class="flex gap-2" @submit.prevent="search">
        <input v-model="filter.q" class="field py-2.5" type="search" placeholder="搜索邮箱 / 昵称 / #编号" aria-label="搜索用户" />
        <button class="btn-ghost shrink-0 px-3 py-2.5" type="submit" aria-label="搜索"><Icon icon="lucide:search" width="16" /></button>
      </form>

      <div v-if="loading && !result.items.length" class="space-y-2"><div v-for="i in 4" :key="i" class="skeleton h-14" /></div>
      <p v-else-if="!result.items.length" class="card py-10 text-center text-sm text-ink-mute">没有找到用户</p>

      <div v-else-if="desktop" class="card overflow-hidden">
        <table class="w-full table-fixed text-left text-xs">
          <colgroup><col /><col class="w-24" /><col class="w-24" /><col class="w-14" /><col class="w-24" /></colgroup>
          <thead class="bg-background text-[11px] text-ink-mute">
            <tr><th class="px-3 py-2 font-bold">用户</th><th class="px-3 py-2 font-bold">注册</th><th class="px-3 py-2 font-bold">最近活跃</th><th class="px-3 py-2 text-right font-bold">任务</th><th class="px-3 py-2 text-right font-bold">专注</th></tr>
          </thead>
          <tbody class="divide-y divide-ink-line/60">
            <tr v-for="u in result.items" :key="u.id" class="cursor-pointer transition hover:bg-background" :class="[current === u.id && 'bg-primary-light/60', !u.is_active && 'opacity-60']" @click="current = u.id">
              <td class="max-w-0 px-3 py-2.5">
                <p class="flex items-center gap-1.5 truncate font-semibold text-ink">{{ u.avatar }} {{ u.name }}
                  <span v-for="b in badges(u)" :key="b.text" class="rounded-full px-1.5 py-px text-[10px] font-bold" :class="b.cls">{{ b.text }}</span>
                </p>
                <p class="truncate text-[11px] text-ink-mute">#{{ u.id }} · {{ u.email }}</p>
              </td>
              <td class="whitespace-nowrap px-3 py-2.5 text-ink-mute">{{ u.created_at?.slice(0, 10) }}</td>
              <td class="whitespace-nowrap px-3 py-2.5 text-ink-soft">{{ timeAgo(u.last_seen_at) }}</td>
              <td class="num px-3 py-2.5 text-right text-ink-soft">{{ u.task_count }}</td>
              <td class="whitespace-nowrap px-3 py-2.5 text-right text-ink-soft">{{ formatMinutes(u.focus_minutes) }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-else class="space-y-2">
        <button v-for="u in result.items" :key="u.id" type="button" class="card flex w-full items-center gap-3 p-3 text-left" :class="!u.is_active && 'opacity-60'" @click="current = u.id">
          <span class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-background text-xl">{{ u.avatar }}</span>
          <span class="min-w-0 flex-1">
            <span class="flex items-center gap-1.5 truncate text-sm font-bold text-ink">{{ u.name }}
              <span v-for="b in badges(u)" :key="b.text" class="rounded-full px-1.5 py-px text-[10px] font-bold" :class="b.cls">{{ b.text }}</span>
            </span>
            <span class="block truncate text-[11px] text-ink-mute">{{ u.email }}</span>
            <span class="block text-[11px] text-ink-mute">活跃 {{ timeAgo(u.last_seen_at) }} · 任务 {{ u.task_count }} · 专注 {{ formatMinutes(u.focus_minutes) }}</span>
          </span>
          <Icon icon="lucide:chevron-right" width="16" class="text-ink-mute" />
        </button>
      </div>

      <Pager v-model="filter.page" :total="result.total" :size="result.size" @update:model-value="load" />
    </div>

    <aside v-if="desktop" class="card sticky top-4 hidden p-4 lg:block">
      <UserDetail v-if="current" :id="current" @changed="onChanged" />
      <p v-else class="py-16 text-center text-sm text-ink-mute"><Icon icon="lucide:users" width="28" class="mx-auto mb-2" />选择左侧的用户查看概况</p>
    </aside>
    <BottomSheet v-if="!desktop" :open="Boolean(current)" title="用户概况" @close="current = null">
      <UserDetail v-if="current" :id="current" @changed="onChanged" />
    </BottomSheet>
  </div>
</template>
