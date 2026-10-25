<script setup>
/** 反馈列表：电脑左表右详情，手机卡片 + 底部抽屉详情。 */
import { onMounted, reactive, ref } from 'vue'
import { Icon } from '@iconify/vue'
import BottomSheet from '@/components/common/BottomSheet.vue'
import { adminApi } from '@/api/admin'
import { useDesktop } from '@/composables/useDesktop'
import { useUiStore } from '@/stores/ui'
import FeedbackDetail from './FeedbackDetail.vue'
import Pager from './Pager.vue'
import { FEEDBACK_CATEGORY, FEEDBACK_STATUS, statusMeta, timeAgo } from './meta'

const props = defineProps({ initialId: { type: Number, default: null } })
const emit = defineEmits(['user'])
const ui = useUiStore()
const desktop = useDesktop()
const filter = reactive({ status: '', category: '', q: '', page: 1 })
const result = ref({ items: [], total: 0, size: 20, counts: {} })
const loading = ref(false)
const current = ref(props.initialId)

const load = async () => {
  loading.value = true
  try {
    result.value = await adminApi.feedbackList({ ...filter, size: 20 })
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
const setStatus = (s) => {
  filter.status = s
  search()
}
const onChanged = (item) => {
  const i = result.value.items.findIndex((r) => r.id === item.id)
  if (i >= 0) result.value.items[i] = { ...result.value.items[i], status: item.status, status_label: item.status_label, reply: item.reply }
}
onMounted(load)
defineExpose({ load })
</script>

<template>
  <div class="lg:grid lg:grid-cols-[minmax(0,1fr)_420px] lg:items-start lg:gap-4">
    <div class="min-w-0 space-y-3">
      <div class="scrollbar-hide flex gap-2 overflow-x-auto">
        <button type="button" class="chip shrink-0" :class="!filter.status && 'chip-active'" @click="setStatus('')">全部</button>
        <button v-for="s in FEEDBACK_STATUS" :key="s.key" type="button" class="chip shrink-0" :class="filter.status === s.key && 'chip-active'" @click="setStatus(s.key)">
          {{ s.label }}<span class="num">{{ result.counts[s.key] ?? '' }}</span>
        </button>
      </div>
      <form class="flex gap-2" @submit.prevent="search">
        <select v-model="filter.category" class="field w-28 shrink-0 py-2.5" aria-label="类型" @change="search">
          <option value="">全部类型</option>
          <option v-for="c in FEEDBACK_CATEGORY" :key="c.key" :value="c.key">{{ c.label }}</option>
        </select>
        <input v-model="filter.q" class="field py-2.5" type="search" placeholder="搜索内容 / 页面 / 用户邮箱 / #编号" aria-label="搜索反馈" />
        <button class="btn-ghost shrink-0 px-3 py-2.5" type="submit" aria-label="搜索"><Icon icon="lucide:search" width="16" /></button>
      </form>

      <div v-if="loading && !result.items.length" class="space-y-2"><div v-for="i in 4" :key="i" class="skeleton h-16" /></div>
      <p v-else-if="!result.items.length" class="card py-10 text-center text-sm text-ink-mute">没有符合条件的反馈</p>

      <!-- 电脑：表格 -->
      <div v-else-if="desktop" class="card overflow-hidden">
        <table class="w-full table-fixed text-left text-xs">
          <colgroup><col class="w-12" /><col /><col class="w-28" /><col class="w-20" /><col class="w-24" /></colgroup>
          <thead class="bg-background text-[11px] text-ink-mute">
            <tr><th class="px-3 py-2 font-bold">#</th><th class="px-3 py-2 font-bold">内容</th><th class="px-3 py-2 font-bold">用户</th><th class="px-3 py-2 font-bold">状态</th><th class="px-3 py-2 font-bold">时间</th></tr>
          </thead>
          <tbody class="divide-y divide-ink-line/60">
            <tr v-for="r in result.items" :key="r.id" class="cursor-pointer transition hover:bg-background" :class="current === r.id && 'bg-primary-light/60'" @click="current = r.id">
              <td class="num px-3 py-2.5 text-ink-mute">{{ r.id }}</td>
              <td class="max-w-0 px-3 py-2.5">
                <p class="truncate font-semibold text-ink"><span class="mr-1 text-ink-mute">[{{ r.category_label }}]</span>{{ r.content }}</p>
                <p class="truncate text-[11px] text-ink-mute">{{ r.page || '—' }}<template v-if="r.images.length"> · <Icon icon="lucide:image" width="11" class="inline" /> {{ r.images.length }}</template><template v-if="r.reply"> · 已回复</template></p>
              </td>
              <td class="truncate px-3 py-2.5 text-ink-soft">{{ r.user ? r.user.name : '已注销' }}</td>
              <td class="px-3 py-2.5"><span class="whitespace-nowrap rounded-full px-2 py-0.5 text-[11px] font-bold" :class="statusMeta(r.status).cls">{{ r.status_label }}</span></td>
              <td class="whitespace-nowrap px-3 py-2.5 text-ink-mute">{{ timeAgo(r.created_at) }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- 手机：卡片 -->
      <div v-else class="space-y-2">
        <button v-for="r in result.items" :key="r.id" type="button" class="card block w-full p-3 text-left" @click="current = r.id">
          <div class="flex items-center gap-2 text-[11px]">
            <span class="num font-black text-ink-mute">#{{ r.id }}</span>
            <span class="font-bold text-ink-soft">{{ r.category_label }}</span>
            <span class="rounded-full px-2 py-0.5 font-bold" :class="statusMeta(r.status).cls">{{ r.status_label }}</span>
            <span class="ml-auto text-ink-mute">{{ timeAgo(r.created_at) }}</span>
          </div>
          <p class="mt-1.5 line-clamp-2 text-sm text-ink">{{ r.content }}</p>
          <p class="mt-1 truncate text-[11px] text-ink-mute">{{ r.user ? `${r.user.name} · ${r.user.email}` : '已注销' }}<template v-if="r.images.length"> · {{ r.images.length }} 张截图</template></p>
        </button>
      </div>

      <Pager v-model="filter.page" :total="result.total" :size="result.size" @update:model-value="load" />
    </div>

    <aside v-if="desktop" class="card sticky top-4 hidden max-h-[calc(100vh-140px)] overflow-y-auto p-4 lg:block">
      <FeedbackDetail v-if="current" :id="current" @changed="onChanged" @user="emit('user', $event)" />
      <p v-else class="py-16 text-center text-sm text-ink-mute"><Icon icon="lucide:inbox" width="28" class="mx-auto mb-2" />选择左侧的一条反馈查看详情</p>
    </aside>
    <BottomSheet v-if="!desktop" :open="Boolean(current)" title="反馈详情" @close="current = null">
      <FeedbackDetail v-if="current" :id="current" @changed="onChanged" @user="current = null; emit('user', $event)" />
    </BottomSheet>
  </div>
</template>
