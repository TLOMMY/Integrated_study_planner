<script setup>
/** 管理后台（仅管理员）：看板 / 反馈 / 用户 / 错误 / 设置。?tab=feedback&id=12 可直接打开某条反馈（通知消息里的链接）。 */
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import AdminDashboard from '@/components/admin/AdminDashboard.vue'
import AdminFeedback from '@/components/admin/AdminFeedback.vue'
import AdminUsers from '@/components/admin/AdminUsers.vue'
import AdminErrors from '@/components/admin/AdminErrors.vue'
import AdminSettings from '@/components/admin/AdminSettings.vue'

const router = useRouter()
const route = useRoute()

const TABS = [
  { key: 'dashboard', label: '看板', icon: 'lucide:layout-dashboard' },
  { key: 'feedback', label: '反馈', icon: 'lucide:message-square-text' },
  { key: 'users', label: '用户', icon: 'lucide:users' },
  { key: 'errors', label: '错误', icon: 'lucide:bug' },
  { key: 'settings', label: '设置', icon: 'lucide:settings-2' },
]
const tab = computed(() => (TABS.some((t) => t.key === route.query.tab) ? route.query.tab : 'dashboard'))
const feedbackId = computed(() => (tab.value === 'feedback' && /^\d+$/.test(route.query.id || '') ? Number(route.query.id) : null))
const userFocus = ref(null)
const panel = ref(null)

const go = (key) => router.replace({ query: { tab: key } })
const openUser = (id) => {
  userFocus.value = id
  go('users')
}
watch(tab, (t) => t !== 'users' && (userFocus.value = null))
const refresh = () => panel.value?.load?.()
</script>

<template>
  <div class="flex h-full flex-col">
    <header class="glass-bar shrink-0 bg-surface px-4 pt-[calc(var(--safe-top)+16px)] lg:border-b lg:border-ink-line/70 lg:px-10 lg:pt-6">
      <div class="flex items-center gap-3">
        <button class="icon-btn lg:hidden" type="button" aria-label="返回" @click="router.back()"><Icon icon="lucide:chevron-left" width="20" /></button>
        <h1 class="flex-1 text-lg font-black text-ink lg:text-[22px]">管理后台</h1>
        <button v-if="tab !== 'settings'" class="icon-btn" type="button" aria-label="刷新" @click="refresh"><Icon icon="lucide:refresh-cw" width="17" /></button>
      </div>
      <nav class="scrollbar-hide -mx-1 mt-3 flex gap-1 overflow-x-auto pb-2" role="tablist">
        <button v-for="t in TABS" :key="t.key" type="button" role="tab" :aria-selected="tab === t.key" class="flex shrink-0 items-center gap-1.5 rounded-xl px-3 py-2 text-sm font-bold transition" :class="tab === t.key ? 'bg-primary-light text-primary' : 'text-ink-mute hover:bg-background'" @click="go(t.key)">
          <Icon :icon="t.icon" width="16" />{{ t.label }}
        </button>
      </nav>
    </header>

    <div class="scrollbar-hide flex-1 overflow-y-auto px-4 pb-24 pt-4 lg:px-10 lg:pb-10 lg:pt-6">
      <div class="desk-page">
        <AdminDashboard v-if="tab === 'dashboard'" ref="panel" @go="go" />
        <AdminFeedback v-else-if="tab === 'feedback'" ref="panel" :initial-id="feedbackId" @user="openUser" />
        <AdminUsers v-else-if="tab === 'users'" ref="panel" :focus-id="userFocus" />
        <AdminErrors v-else-if="tab === 'errors'" ref="panel" />
        <AdminSettings v-else ref="panel" />
      </div>
    </div>
  </div>
</template>
