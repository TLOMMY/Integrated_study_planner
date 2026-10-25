<script setup>
/** 管理员查看与处理一条反馈：用户信息、截图、改状态、回复（可同时发邮件）。 */
import { ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import { adminApi } from '@/api/admin'
import { useUiStore } from '@/stores/ui'
import FeedbackImage from './FeedbackImage.vue'
import { FEEDBACK_STATUS, fullTime, statusMeta, timeAgo } from './meta'

const props = defineProps({ id: { type: Number, required: true } })
const emit = defineEmits(['changed', 'user'])
const ui = useUiStore()
const item = ref(null)
const busy = ref(false)
const reply = ref('')
const sendEmail = ref(false)

const load = async () => {
  item.value = null
  try {
    item.value = await adminApi.feedbackDetail(props.id)
    reply.value = ''
    sendEmail.value = false
  } catch (error) {
    ui.fail(error)
  }
}
watch(() => props.id, load, { immediate: true })

const act = async (fn) => {
  busy.value = true
  try {
    const result = await fn()
    item.value = result.data
    ui.success(result.message)
    emit('changed', result.data)
  } catch (error) {
    ui.fail(error)
  } finally {
    busy.value = false
  }
}
// http 只返回 data；提示文字在本地拼
const setStatus = (status) =>
  act(async () => ({ data: await adminApi.feedbackStatus(props.id, status), message: `已标记为「${statusMeta(status).label}」` }))
const submitReply = () => {
  if (!reply.value.trim()) return ui.toast('请输入回复内容', 'warning')
  return act(async () => {
    const data = await adminApi.feedbackReply(props.id, { reply: reply.value.trim(), send_email: sendEmail.value })
    return { data, message: data.emailed ? '已回复，并已发送邮件' : '已回复，用户会在「我的反馈」看到' }
  })
}
</script>

<template>
  <div v-if="!item" class="space-y-3"><div class="skeleton h-24" /><div class="skeleton h-40" /></div>
  <div v-else class="space-y-4">
    <div class="flex flex-wrap items-center gap-2">
      <span class="num text-sm font-black text-ink">#{{ item.id }}</span>
      <span class="rounded-full bg-background px-2 py-0.5 text-[11px] font-bold text-ink-soft">{{ item.category_label }}</span>
      <span class="rounded-full px-2 py-0.5 text-[11px] font-bold" :class="statusMeta(item.status).cls">{{ item.status_label }}</span>
      <span class="ml-auto text-[11px] text-ink-mute" :title="fullTime(item.created_at)">{{ timeAgo(item.created_at) }}</span>
    </div>

    <p class="whitespace-pre-wrap break-words rounded-2xl bg-background p-3 text-sm leading-6 text-ink">{{ item.content }}</p>
    <div v-if="item.images.length" class="flex flex-wrap gap-2">
      <FeedbackImage v-for="name in item.images" :key="name" :name="name" size="h-24 w-24" />
    </div>

    <dl class="grid grid-cols-[72px_1fr] gap-x-2 gap-y-1.5 text-xs">
      <dt class="text-ink-mute">用户</dt>
      <dd class="min-w-0">
        <button v-if="item.user" class="truncate text-left font-bold text-primary" type="button" @click="emit('user', item.user.id)">
          {{ item.user.avatar }} {{ item.user.name }} · {{ item.user.email }}
        </button>
        <span v-else class="text-ink-mute">账号已注销</span>
        <span v-if="item.user?.is_demo" class="ml-1 text-flame">演示账号</span>
      </dd>
      <template v-if="item.user">
        <dt class="text-ink-mute">注册 / 活跃</dt>
        <dd class="text-ink-soft">{{ fullTime(item.user.created_at) }} · {{ timeAgo(item.user.last_seen_at) }}（共 {{ item.user.feedback_count }} 条反馈）</dd>
      </template>
      <dt class="text-ink-mute">联系方式</dt><dd class="break-all text-ink-soft">{{ item.contact || '未填写' }}</dd>
      <dt class="text-ink-mute">页面</dt><dd class="break-all text-ink-soft">{{ item.page || '未知' }}</dd>
      <dt class="text-ink-mute">客户端</dt><dd class="break-all text-[11px] text-ink-mute">{{ item.client || '—' }}</dd>
      <dt class="text-ink-mute">原文</dt><dd class="break-all text-[11px] text-ink-mute">feedback/{{ item.txt_name }}</dd>
    </dl>

    <div>
      <p class="label">状态</p>
      <div class="flex flex-wrap gap-2">
        <button v-for="s in FEEDBACK_STATUS" :key="s.key" type="button" class="chip" :class="item.status === s.key && 'chip-active'" :disabled="busy" @click="item.status !== s.key && setStatus(s.key)">{{ s.label }}</button>
      </div>
    </div>

    <div v-if="item.reply" class="rounded-2xl bg-primary-light p-3 text-xs">
      <p class="font-bold text-primary">已回复 · {{ item.replied_by_name || '管理员' }} · {{ timeAgo(item.replied_at) }}{{ item.unread ? ' · 用户未读' : ' · 用户已读' }}</p>
      <p class="mt-1 whitespace-pre-wrap leading-5 text-ink">{{ item.reply }}</p>
    </div>

    <div>
      <p class="label">{{ item.reply ? '更新回复' : '回复用户' }}</p>
      <textarea v-model="reply" class="field min-h-[96px] resize-none" maxlength="2000" placeholder="用户会在「设置 → 我的反馈」看到回复，并显示未读红点" />
      <div class="mt-2 flex items-center gap-3">
        <label class="flex flex-1 items-center gap-2 text-xs text-ink-soft" :class="(!item.user || item.user.is_demo) && 'opacity-50'">
          <input v-model="sendEmail" type="checkbox" class="h-4 w-4 accent-primary" :disabled="!item.user || item.user.is_demo" />同时发邮件给用户
        </label>
        <button class="btn-primary py-2" type="button" :disabled="busy" @click="submitReply"><Icon icon="lucide:reply" width="15" />发送回复</button>
      </div>
    </div>
  </div>
</template>
