<script setup>
/** 设置页 · 我的反馈：处理状态、管理员回复（未读红点）。提交新反馈后监听 feedback:submitted 事件刷新。 */
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { Icon } from '@iconify/vue'
import { feedbackApi } from '@/api'
import FeedbackImage from '@/components/admin/FeedbackImage.vue'
import { statusMeta, timeAgo } from '@/components/admin/meta'

const items = ref([])
const unread = ref(0)
const loaded = ref(false)
const expanded = ref(null)
const showAll = ref(false)

const load = async () => {
  try {
    const data = await feedbackApi.mine()
    items.value = data.items
    unread.value = data.unread
  } catch {
    /* 列表加载失败不打扰用户，下次进入设置页再试 */
  } finally {
    loaded.value = true
  }
}

const toggle = async (item) => {
  expanded.value = expanded.value === item.id ? null : item.id
  if (item.unread) {
    item.unread = false
    unread.value = Math.max(0, unread.value - 1)
    feedbackApi.markRead(item.id).catch(() => {})
  }
}

onMounted(() => {
  load()
  window.addEventListener('feedback:submitted', load)
})
onBeforeUnmount(() => window.removeEventListener('feedback:submitted', load))
</script>

<template>
  <div v-if="loaded && items.length">
    <h2 class="mb-2 mt-5 flex items-center gap-1.5 px-1 text-xs font-black text-ink-mute">
      我的反馈
      <span v-if="unread" class="num rounded-full bg-danger px-1.5 text-[10px] leading-4 text-on-danger" :aria-label="`${unread} 条未读回复`">{{ unread }}</span>
    </h2>
    <div class="card divide-y divide-ink-line/60 overflow-hidden">
      <div v-for="item in showAll ? items : items.slice(0, 3)" :key="item.id">
        <button class="flex w-full items-start gap-3 px-4 py-3 text-left" type="button" :aria-expanded="expanded === item.id" @click="toggle(item)">
          <span class="relative mt-0.5 shrink-0">
            <Icon :icon="item.reply ? 'lucide:message-square-text' : 'lucide:message-square-warning'" width="18" :class="item.reply ? 'text-primary' : 'text-ink-mute'" />
            <span v-if="item.unread" class="absolute -right-0.5 -top-0.5 h-2 w-2 rounded-full bg-danger ring-2 ring-surface" />
          </span>
          <span class="min-w-0 flex-1">
            <span class="flex items-center gap-2 text-[11px]">
              <span class="font-bold text-ink-soft">{{ item.category_label }}</span>
              <span class="rounded-full px-1.5 py-px font-bold" :class="statusMeta(item.status).cls">{{ item.status_label }}</span>
              <span class="ml-auto text-ink-mute">{{ timeAgo(item.created_at) }}</span>
            </span>
            <span class="mt-1 block text-sm text-ink" :class="expanded !== item.id && 'line-clamp-2'">{{ item.content }}</span>
            <span v-if="item.reply && expanded !== item.id" class="mt-1 block truncate text-xs font-semibold text-primary">技术同学回复：{{ item.reply }}</span>
          </span>
        </button>
        <div v-if="expanded === item.id" class="space-y-2 px-4 pb-3 pl-[46px]">
          <div v-if="item.images.length" class="flex gap-2">
            <FeedbackImage v-for="name in item.images" :key="name" :name="name" size="h-16 w-16" />
          </div>
          <div v-if="item.reply" class="rounded-2xl bg-primary-light px-3 py-2">
            <p class="text-[11px] font-bold text-primary">技术同学回复 · {{ timeAgo(item.replied_at) }}</p>
            <p class="mt-0.5 whitespace-pre-wrap text-xs leading-5 text-ink">{{ item.reply }}</p>
          </div>
          <p v-else class="text-[11px] text-ink-mute">已收到，技术同学处理后会在这里回复你</p>
        </div>
      </div>
      <button v-if="items.length > 3" class="w-full py-2.5 text-xs font-bold text-primary" type="button" @click="showAll = !showAll">
        {{ showAll ? '收起' : `查看全部 ${items.length} 条` }}
      </button>
    </div>
  </div>
</template>
