<script setup>
/** 用户概况与操作：停用/启用、重置密码（临时密码只显示一次）、设为/取消管理员。 */
import { computed, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import { adminApi } from '@/api/admin'
import { useAuthStore } from '@/stores/auth'
import { useUiStore } from '@/stores/ui'
import { formatMinutes } from '@/utils/dates'
import { fullTime, timeAgo } from './meta'

const props = defineProps({ id: { type: Number, required: true } })
const emit = defineEmits(['changed'])
const ui = useUiStore()
const auth = useAuthStore()
const user = ref(null)
const busy = ref(false)
const temp = ref('')
const isSelf = computed(() => user.value?.id === auth.user?.id)

const load = async () => {
  user.value = null
  temp.value = ''
  try {
    user.value = await adminApi.user(props.id)
  } catch (error) {
    ui.fail(error)
  }
}
watch(() => props.id, load, { immediate: true })

const update = async (payload, message) => {
  busy.value = true
  try {
    user.value = await adminApi.updateUser(props.id, payload)
    ui.success(message)
    emit('changed', user.value)
  } catch (error) {
    ui.fail(error)
  } finally {
    busy.value = false
  }
}
const toggleActive = async () => {
  const off = user.value.is_active
  if (off && !(await ui.confirm({ title: '停用该账号？', message: `${user.value.email} 将立即退出登录且无法再登录，数据保留，可随时启用。`, confirmText: '停用', danger: true }))) return
  update({ is_active: !off }, off ? '账号已停用' : '账号已启用')
}
const toggleAdmin = async () => {
  const on = !user.value.is_admin
  if (!(await ui.confirm({ title: on ? '设为管理员？' : '取消管理员？', message: on ? '管理员可以查看所有反馈、管理用户和修改系统设置。' : '该用户将无法再进入管理后台。', confirmText: '确定', danger: !on }))) return
  update({ is_admin: on }, on ? '已设为管理员' : '已取消管理员')
}
const resetPassword = async () => {
  if (!(await ui.confirm({ title: '重置密码？', message: '将生成一个临时密码，该用户所有设备上的登录会立即失效。临时密码只显示这一次。', confirmText: '重置', danger: true }))) return
  busy.value = true
  try {
    temp.value = (await adminApi.resetPassword(props.id)).temp_password
  } catch (error) {
    ui.fail(error)
  } finally {
    busy.value = false
  }
}
const copy = async () => {
  try {
    await navigator.clipboard.writeText(temp.value)
    ui.success('已复制临时密码')
  } catch {
    ui.toast('复制失败，请手动选择', 'warning')
  }
}

const stats = computed(() => {
  const u = user.value
  return u ? [
    { label: '任务', value: `${u.completed_tasks}/${u.task_count}` },
    { label: '专注', value: formatMinutes(u.focus_minutes) },
    { label: '专注次数', value: u.focus_sessions },
    { label: '计划', value: u.plan_count },
    { label: '课程', value: u.course_count },
    { label: '经验', value: u.xp_total },
    { label: 'AI 提问', value: u.ai_messages },
    { label: '30 天活跃', value: `${u.active_days_30} 天` },
  ] : []
})
</script>

<template>
  <div v-if="!user" class="space-y-3"><div class="skeleton h-20" /><div class="skeleton h-32" /></div>
  <div v-else class="space-y-4">
    <div class="flex items-center gap-3">
      <span class="flex h-12 w-12 items-center justify-center rounded-2xl bg-background text-2xl">{{ user.avatar }}</span>
      <div class="min-w-0 flex-1">
        <p class="truncate font-black text-ink">{{ user.name }} <span class="num text-xs font-bold text-ink-mute">#{{ user.id }}</span></p>
        <p class="truncate text-xs text-ink-soft">{{ user.email }}</p>
        <div class="mt-1 flex flex-wrap gap-1 text-[10px] font-bold">
          <span v-if="!user.is_active" class="rounded-full bg-danger-light px-2 py-0.5 text-danger">已停用</span>
          <span v-if="user.is_admin" class="rounded-full bg-xp-light px-2 py-0.5 text-xp">管理员{{ user.admin_by_env ? '（服务器配置）' : '' }}</span>
          <span v-if="user.is_demo" class="rounded-full bg-flame-light px-2 py-0.5 text-flame">演示</span>
          <span class="rounded-full px-2 py-0.5" :class="user.email_verified ? 'bg-success-light text-success' : 'bg-background text-ink-mute'">{{ user.email_verified ? '邮箱已验证' : '邮箱未验证' }}</span>
        </div>
      </div>
    </div>

    <dl class="grid grid-cols-[72px_1fr] gap-y-1.5 text-xs">
      <dt class="text-ink-mute">注册时间</dt><dd class="text-ink-soft">{{ fullTime(user.created_at) }}</dd>
      <dt class="text-ink-mute">最近活跃</dt><dd class="text-ink-soft">{{ timeAgo(user.last_seen_at) }}</dd>
      <dt class="text-ink-mute">学期</dt><dd class="text-ink-soft">{{ user.semester || '—' }}</dd>
      <dt class="text-ink-mute">手机</dt><dd class="text-ink-soft">{{ user.phone_masked || '未绑定' }}</dd>
      <dt class="text-ink-mute">反馈</dt><dd class="text-ink-soft">{{ user.feedback_count }} 条</dd>
    </dl>

    <div class="grid grid-cols-4 gap-2">
      <div v-for="s in stats" :key="s.label" class="rounded-2xl bg-background px-2 py-2 text-center">
        <p class="num truncate text-sm font-black text-ink">{{ s.value }}</p>
        <p class="text-[10px] font-bold text-ink-mute">{{ s.label }}</p>
      </div>
    </div>

    <div v-if="temp" class="rounded-2xl border border-flame/40 bg-flame-light p-3">
      <p class="text-xs font-bold text-flame">临时密码（只显示这一次，请转告用户登录后尽快修改）</p>
      <div class="mt-2 flex items-center gap-2">
        <code class="num flex-1 select-all rounded-xl bg-surface px-3 py-2 text-base font-black tracking-wider text-ink">{{ temp }}</code>
        <button class="btn-ghost px-3 py-2" type="button" @click="copy"><Icon icon="lucide:copy" width="15" />复制</button>
      </div>
    </div>

    <div v-if="isSelf" class="rounded-2xl bg-background px-3 py-2 text-xs text-ink-mute">这是你自己的账号：不能停用、取消管理员或在这里重置密码</div>
    <div v-else class="grid grid-cols-1 gap-2 sm:grid-cols-3">
      <button class="btn py-2.5" :class="user.is_active ? 'btn-danger' : 'btn-ghost text-success'" type="button" :disabled="busy" @click="toggleActive">
        <Icon :icon="user.is_active ? 'lucide:user-x' : 'lucide:user-check'" width="15" />{{ user.is_active ? '停用账号' : '启用账号' }}
      </button>
      <button class="btn-ghost py-2.5" type="button" :disabled="busy || user.is_demo" @click="resetPassword"><Icon icon="lucide:key-round" width="15" />重置密码</button>
      <button class="btn-ghost py-2.5" type="button" :disabled="busy || (user.is_admin && user.admin_by_env) || (!user.is_admin && user.is_demo)" @click="toggleAdmin">
        <Icon :icon="user.is_admin ? 'lucide:shield-off' : 'lucide:shield-check'" width="15" />{{ user.is_admin ? '取消管理员' : '设为管理员' }}
      </button>
    </div>
  </div>
</template>
