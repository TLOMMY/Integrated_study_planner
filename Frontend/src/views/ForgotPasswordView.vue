<script setup>
/** 找回密码：邮箱 → 验证码 → 新密码。成功后所有设备上的旧登录失效，回到登录页。 */
import { onBeforeUnmount, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import { authApi } from '@/api'
import { useUiStore } from '@/stores/ui'

const router = useRouter()
const route = useRoute()
const ui = useUiStore()

const form = reactive({ email: typeof route.query.email === 'string' ? route.query.email : '', code: '', password: '', confirm: '' })
const step = ref(1)
const busy = ref(false)
const error = ref('')
const hint = ref('')
const showPwd = ref(false)
const cooldown = ref(0)
let timer = null

const tick = (seconds) => {
  clearInterval(timer)
  cooldown.value = seconds
  timer = setInterval(() => {
    cooldown.value -= 1
    if (cooldown.value <= 0) clearInterval(timer)
  }, 1000)
}
onBeforeUnmount(() => clearInterval(timer))

const send = async () => {
  error.value = ''
  if (!/^\S+@\S+\.\S+$/.test(form.email.trim())) return (error.value = '请输入注册时使用的邮箱')
  busy.value = true
  try {
    const data = await authApi.sendEmailCode(form.email.trim(), 'reset')
    hint.value = data.mail_enabled ? '如果该邮箱已注册，验证码已发送，10 分钟内有效（可能在垃圾邮件里）' : '服务器未配置邮件发送，验证码已写入后端日志，请联系管理员'
    step.value = 2
    tick(data.cooldown || 60)
  } catch (e) {
    error.value = e.message
    if (e.data?.retry_after) tick(e.data.retry_after)
  } finally {
    busy.value = false
  }
}

const reset = async () => {
  error.value = ''
  if (!/^\d{6}$/.test(form.code.trim())) return (error.value = '请输入 6 位数字验证码')
  if (form.password.length < 6) return (error.value = '新密码至少 6 位')
  if (form.password !== form.confirm) return (error.value = '两次输入的新密码不一致')
  busy.value = true
  try {
    await authApi.resetPassword({ email: form.email.trim(), code: form.code.trim(), new_password: form.password })
    ui.success('密码已重设，请用新密码登录')
    router.replace({ name: 'login' })
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="scrollbar-hide flex h-full flex-col overflow-y-auto bg-background lg:items-center lg:justify-center">
    <header class="flex items-center gap-3 px-4 pb-2 pt-[calc(var(--safe-top)+16px)] lg:hidden">
      <button class="icon-btn" type="button" aria-label="返回登录" @click="router.replace({ name: 'login' })"><Icon icon="lucide:chevron-left" width="20" /></button>
    </header>
    <section class="mx-4 mt-2 rounded-[28px] bg-surface p-6 shadow-soft lg:mx-0 lg:mt-0 lg:w-[420px] lg:p-8">
      <div class="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary-light text-primary"><Icon icon="lucide:key-round" width="24" /></div>
      <h1 class="mt-4 text-2xl font-black text-ink">找回密码</h1>
      <p class="mt-1 text-sm text-ink-mute">{{ step === 1 ? '输入注册邮箱，我们会发送 6 位验证码' : '填写验证码并设置新密码' }}</p>

      <form class="mt-5 space-y-3" novalidate @submit.prevent="step === 1 ? send() : reset()">
        <input v-model="form.email" class="field" type="email" placeholder="注册邮箱" autocomplete="email" :readonly="step === 2" aria-label="注册邮箱" />
        <template v-if="step === 2">
          <p v-if="hint" class="rounded-2xl bg-primary-light px-3 py-2 text-xs font-semibold leading-5 text-primary">{{ hint }}</p>
          <div class="flex gap-2">
            <input v-model="form.code" class="field num tracking-[0.3em]" inputmode="numeric" maxlength="6" placeholder="验证码" autocomplete="one-time-code" aria-label="验证码" />
            <button class="btn-ghost shrink-0 px-3" type="button" :disabled="busy || cooldown > 0" @click="send">{{ cooldown > 0 ? `${cooldown} 秒` : '重新发送' }}</button>
          </div>
          <div class="relative">
            <input v-model="form.password" class="field pr-12" :type="showPwd ? 'text' : 'password'" placeholder="新密码（至少 6 位）" autocomplete="new-password" aria-label="新密码" />
            <button class="absolute right-3 top-1/2 -translate-y-1/2 p-1 text-ink-mute" type="button" :aria-label="showPwd ? '隐藏密码' : '显示密码'" @click="showPwd = !showPwd">
              <Icon :icon="showPwd ? 'lucide:eye-off' : 'lucide:eye'" width="18" />
            </button>
          </div>
          <input v-model="form.confirm" class="field" :type="showPwd ? 'text' : 'password'" placeholder="再输入一次新密码" autocomplete="new-password" aria-label="确认新密码" />
        </template>
        <p v-if="error" class="flex items-center gap-1.5 rounded-2xl bg-danger-light px-4 py-2.5 text-xs font-bold text-danger" role="alert">
          <Icon icon="lucide:circle-alert" width="14" />{{ error }}
        </p>
        <button class="btn-primary w-full py-3.5 text-base" type="submit" :disabled="busy || (step === 1 && cooldown > 0)">
          <Icon v-if="busy" icon="lucide:loader-circle" width="18" class="animate-spin" />
          {{ step === 1 ? (cooldown > 0 ? `${cooldown} 秒后可重新发送` : '发送验证码') : '重设密码' }}
        </button>
      </form>
      <div class="mt-4 flex items-center justify-between text-xs">
        <button v-if="step === 2" class="font-bold text-ink-mute" type="button" @click="step = 1; error = ''">换个邮箱</button>
        <RouterLink class="ml-auto font-bold text-primary" :to="{ name: 'login' }">返回登录</RouterLink>
      </div>
      <p class="mt-4 text-[11px] leading-5 text-ink-mute">重设成功后，所有设备上的旧登录会失效。收不到邮件？也可以联系管理员在后台为你重置密码。</p>
    </section>
  </div>
</template>
