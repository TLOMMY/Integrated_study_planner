<script setup>
/** 设置页 · 账号与安全的补充项：邮箱验证状态（发码验证、换绑并验证新邮箱）、管理员的「管理后台」入口。 */
import { computed, onBeforeUnmount, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import BottomSheet from '@/components/common/BottomSheet.vue'
import { authApi } from '@/api'
import { useAuthStore } from '@/stores/auth'
import { useUiStore } from '@/stores/ui'

const router = useRouter()
const auth = useAuthStore()
const ui = useUiStore()
const user = computed(() => auth.user || {})

// mode：verify 验证当前邮箱；change 换绑并验证新邮箱
const sheet = reactive({ open: false, mode: 'verify', email: '', code: '', password: '', hint: '' })
const busy = ref(false)
const cooldown = ref(0)
let timer = null
const tick = (seconds) => {
  clearInterval(timer)
  cooldown.value = seconds
  timer = setInterval(() => (--cooldown.value <= 0 ? clearInterval(timer) : null), 1000)
}
onBeforeUnmount(() => clearInterval(timer))

const open = (mode) => {
  Object.assign(sheet, { open: true, mode, email: '', code: '', password: '', hint: '' })
}
// 设置页「绑定邮箱」入口统一走这里的换绑流程（带新邮箱验证码）
defineExpose({ openChange: () => open('change') })
const target = computed(() => (sheet.mode === 'verify' ? user.value.email : sheet.email.trim()))

const sendCode = async () => {
  if (!/^\S+@\S+\.\S+$/.test(target.value || '')) return ui.toast('请输入正确的新邮箱', 'warning')
  busy.value = true
  try {
    const data = await authApi.sendEmailCode(target.value, 'bind')
    sheet.hint = data.mail_enabled ? `验证码已发送到 ${target.value}，10 分钟内有效` : '服务器未配置邮件发送，验证码已写入后端日志'
    tick(data.cooldown || 60)
  } catch (error) {
    ui.fail(error)
    if (error.data?.retry_after) tick(error.data.retry_after)
  } finally {
    busy.value = false
  }
}

const confirm = async () => {
  if (!/^\d{6}$/.test(sheet.code.trim())) return ui.toast('请输入 6 位数字验证码', 'warning')
  if (sheet.mode === 'change' && !sheet.password) return ui.toast('请输入当前密码', 'warning')
  busy.value = true
  try {
    if (sheet.mode === 'verify') await auth.verifyEmail(sheet.code.trim())
    else await auth.changeEmail({ email: target.value, password: sheet.password, code: sheet.code.trim() })
    ui.success(sheet.mode === 'verify' ? '邮箱验证成功' : '邮箱已换绑并验证')
    sheet.open = false
  } catch (error) {
    ui.fail(error)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div v-if="!auth.isDemo || user.is_admin">
    <h2 class="mb-2 mt-5 px-1 text-xs font-black text-ink-mute">邮箱验证{{ user.is_admin ? ' · 管理' : '' }}</h2>
    <div class="card divide-y divide-ink-line/60 overflow-hidden">
      <template v-if="!auth.isDemo">
        <button class="flex w-full items-center gap-3 px-4 py-3.5 text-left" type="button" :disabled="user.email_verified" @click="open('verify')">
          <Icon :icon="user.email_verified ? 'lucide:mail-check' : 'lucide:mail-warning'" width="20" :class="user.email_verified ? 'text-success' : 'text-flame'" />
          <span class="min-w-0 flex-1">
            <span class="block text-sm font-semibold text-ink">{{ user.email_verified ? '邮箱已验证' : '验证邮箱' }}</span>
            <span class="block truncate text-[11px] text-ink-mute">{{ user.email_verified ? `${user.email} · 可用于找回密码` : '验证后可通过邮箱验证码找回密码' }}</span>
          </span>
          <span v-if="!user.email_verified" class="rounded-full bg-flame-light px-2 py-0.5 text-[11px] font-bold text-flame">未验证</span>
          <Icon v-else icon="lucide:badge-check" width="18" class="text-success" />
        </button>
      </template>
      <button v-if="user.is_admin" class="flex w-full items-center gap-3 px-4 py-3.5 text-left" type="button" @click="router.push({ name: 'admin' })">
        <Icon icon="lucide:shield-check" width="20" class="text-xp" />
        <span class="min-w-0 flex-1">
          <span class="block text-sm font-semibold text-ink">管理后台</span>
          <span class="block text-[11px] text-ink-mute">处理用户反馈、管理账号、查看数据看板</span>
        </span>
        <Icon icon="lucide:chevron-right" width="16" class="text-ink-mute" />
      </button>
    </div>

    <BottomSheet :open="sheet.open" :title="sheet.mode === 'verify' ? '验证邮箱' : '换绑并验证新邮箱'" :subtitle="sheet.mode === 'verify' ? user.email : `当前：${user.email}`" @close="sheet.open = false">
      <div class="space-y-3 pb-2">
        <input v-if="sheet.mode === 'change'" v-model="sheet.email" class="field" type="email" placeholder="新邮箱" autocomplete="email" aria-label="新邮箱" />
        <div class="flex gap-2">
          <input v-model="sheet.code" class="field num tracking-[0.3em]" inputmode="numeric" maxlength="6" placeholder="6 位验证码" autocomplete="one-time-code" aria-label="验证码" />
          <button class="btn-ghost shrink-0 px-3" type="button" :disabled="busy || cooldown > 0" @click="sendCode">{{ cooldown > 0 ? `${cooldown} 秒` : '发送验证码' }}</button>
        </div>
        <p v-if="sheet.hint" class="rounded-2xl bg-primary-light px-3 py-2 text-xs font-semibold text-primary">{{ sheet.hint }}</p>
        <input v-if="sheet.mode === 'change'" v-model="sheet.password" class="field" type="password" placeholder="当前密码（验证身份）" autocomplete="current-password" aria-label="当前密码" />
      </div>
      <template #footer><button class="btn-primary w-full" type="button" :disabled="busy || !sheet.code" @click="confirm">{{ sheet.mode === 'verify' ? '完成验证' : '确认换绑' }}</button></template>
    </BottomSheet>
  </div>
</template>
