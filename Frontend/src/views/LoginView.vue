<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import { authApi } from '@/api'
import { useAuthStore } from '@/stores/auth'
import { useUiStore } from '@/stores/ui'
import { DEFAULT_SERVER, getServer, isNativeApp, probeServer, setServer } from '@/api/server'

const auth = useAuthStore()
const ui = useUiStore()
const route = useRoute()
const router = useRouter()

const mode = ref('login')
const busy = ref(false)
const showPwd = ref(false)
const error = ref('')
const form = reactive({ name: '', account: '', password: '', code: '' })
const isLogin = computed(() => mode.value === 'login')

// 服务器开启「注册必须验证邮箱」时，注册表单显示验证码
const requireCode = ref(false)
const codeHint = ref('')
const cooldown = ref(0)
let codeTimer = null
onMounted(async () => {
  try {
    requireCode.value = Boolean((await authApi.options()).require_email_verify)
  } catch {
    /* 旧版服务器没有该接口时按不需要验证处理 */
  }
})
onBeforeUnmount(() => clearInterval(codeTimer))
const sendCode = async () => {
  error.value = ''
  const email = form.account.trim()
  if (!/^\S+@\S+\.\S+$/.test(email)) return (error.value = '请先输入正确的邮箱')
  try {
    const data = await authApi.sendEmailCode(email, 'register')
    codeHint.value = data.mail_enabled ? `验证码已发送到 ${email}` : '服务器未配置邮件发送，验证码已写入后端日志'
    cooldown.value = data.cooldown || 60
  } catch (e) {
    error.value = e.message
    cooldown.value = e.data?.retry_after || 0
  }
  clearInterval(codeTimer)
  if (cooldown.value > 0) codeTimer = setInterval(() => (--cooldown.value <= 0 ? clearInterval(codeTimer) : null), 1000)
}

// 只在手机 App 里显示：切换要连接的服务器（正式服务器 / 局域网里的电脑）
const native = isNativeApp()
const server = reactive({ open: false, value: getServer(), testing: false, result: '' })
const testServer = async () => {
  server.testing = true
  server.result = ''
  try {
    server.result = `✓ 连接成功（${await probeServer(server.value)} ms）`
  } catch (err) {
    server.result = `✗ ${err?.message?.includes('timeout') ? '连接超时' : err?.message || '无法连接'}`
  } finally {
    server.testing = false
  }
}
const saveServer = () => {
  server.value = setServer(server.value)
  server.open = false
  ui.success('已切换服务器')
}
const resetServer = () => (server.value = setServer(''))

const FEATURES = [
  { icon: 'lucide:calendar-days', text: '课表', sub: '单双周' },
  { icon: 'lucide:circle-check-big', text: '任务', sub: '番茄钟' },
  { icon: 'lucide:sparkles', text: 'AI', sub: '避开课程' },
  { icon: 'lucide:flame', text: '打卡', sub: '等级成就' },
]

const done = () => {
  ui.success(`欢迎，${auth.displayName}`)
  const target = typeof route.query.redirect === 'string' && route.query.redirect.startsWith('/') ? route.query.redirect : '/today-task'
  router.replace(target)
}

const submit = async () => {
  error.value = ''
  if (!isLogin.value && !form.name.trim()) return (error.value = '请输入昵称')
  if (!form.account.trim()) return (error.value = isLogin.value ? '请输入邮箱或用户名' : '请输入邮箱')
  if (!isLogin.value && !/^\S+@\S+\.\S+$/.test(form.account.trim())) return (error.value = '邮箱格式不正确')
  if (form.password.length < (isLogin.value ? 1 : 6)) return (error.value = isLogin.value ? '请输入密码' : '密码至少 6 位')
  if (!isLogin.value && requireCode.value && !/^\d{6}$/.test(form.code.trim())) return (error.value = '请输入邮箱收到的 6 位验证码')
  busy.value = true
  try {
    if (isLogin.value) await auth.login(form.account.trim(), form.password)
    else await auth.register({ email: form.account.trim(), password: form.password, full_name: form.name.trim(), ...(form.code.trim() ? { code: form.code.trim() } : {}) })
    done()
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

const demo = async () => {
  busy.value = true
  error.value = ''
  try {
    await auth.loginDemo()
    done()
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="scrollbar-hide flex h-full flex-col overflow-y-auto bg-gradient-to-b from-primary via-hero to-xp lg:flex-row lg:items-center lg:justify-center lg:gap-20 lg:bg-gradient-to-br lg:px-16">
    <div class="shrink-0 px-6 pb-8 pt-[calc(var(--safe-top)+40px)] text-on-primary lg:max-w-md lg:p-0">
      <div class="flex h-14 w-14 items-center justify-center rounded-2xl bg-on-primary/20 text-3xl backdrop-blur">🦉</div>
      <h1 class="mt-4 text-3xl font-black lg:text-5xl">学业管家</h1>
      <p class="mt-1 text-sm opacity-85 lg:mt-3 lg:text-base">课表、待办、专注与成长，一个 App 管好大学学习</p>
      <div class="mt-5 grid grid-cols-4 gap-2 lg:mt-8 lg:gap-3">
        <div v-for="f in FEATURES" :key="f.text" class="rounded-2xl bg-on-primary/15 py-2.5 text-center backdrop-blur">
          <Icon :icon="f.icon" width="20" class="mx-auto" />
          <p class="mt-1 text-xs font-black">{{ f.text }}</p>
          <p class="text-[9px] opacity-75">{{ f.sub }}</p>
        </div>
      </div>
    </div>

    <section class="material flex-1 rounded-t-[32px] bg-surface px-6 pb-[calc(var(--safe-bottom)+24px)] pt-6 lg:w-[420px] lg:flex-none lg:rounded-[32px] lg:p-8 lg:shadow-2xl">
      <div class="grid grid-cols-2 rounded-2xl bg-background p-1">
        <button v-for="m in ['login', 'register']" :key="m" type="button" class="rounded-xl py-2.5 text-sm font-black transition" :class="mode === m ? 'bg-surface text-primary shadow-soft' : 'text-ink-mute'" @click="mode = m; error = ''">
          {{ m === 'login' ? '登录' : '注册' }}
        </button>
      </div>

      <form class="mt-5 space-y-3" novalidate @submit.prevent="submit">
        <input v-if="!isLogin" v-model="form.name" class="field" placeholder="昵称" maxlength="40" autocomplete="nickname" />
        <input v-model="form.account" class="field" :placeholder="isLogin ? '邮箱或用户名' : '邮箱'" :type="isLogin ? 'text' : 'email'" autocomplete="username" />
        <div class="relative">
          <input v-model="form.password" class="field pr-12" :type="showPwd ? 'text' : 'password'" :placeholder="isLogin ? '密码' : '密码（至少 6 位）'" :autocomplete="isLogin ? 'current-password' : 'new-password'" />
          <button class="absolute right-3 top-1/2 -translate-y-1/2 p-1 text-ink-mute" type="button" :aria-label="showPwd ? '隐藏密码' : '显示密码'" @click="showPwd = !showPwd">
            <Icon :icon="showPwd ? 'lucide:eye-off' : 'lucide:eye'" width="18" />
          </button>
        </div>
        <template v-if="!isLogin && requireCode">
          <div class="flex gap-2">
            <input v-model="form.code" class="field num tracking-[0.3em]" inputmode="numeric" maxlength="6" placeholder="邮箱验证码" autocomplete="one-time-code" aria-label="邮箱验证码" />
            <button class="btn-ghost shrink-0 px-3" type="button" :disabled="cooldown > 0" @click="sendCode">{{ cooldown > 0 ? `${cooldown} 秒` : '发送验证码' }}</button>
          </div>
          <p v-if="codeHint" class="px-1 text-[11px] text-ink-mute">{{ codeHint }}</p>
        </template>
        <div v-if="isLogin" class="-mt-1 flex justify-end">
          <RouterLink class="px-1 text-xs font-bold text-primary" :to="{ name: 'forgot', query: form.account.includes('@') ? { email: form.account.trim() } : {} }">忘记密码？</RouterLink>
        </div>
        <p v-if="error" class="flex items-center gap-1.5 rounded-2xl bg-danger-light px-4 py-2.5 text-xs font-bold text-danger" role="alert">
          <Icon icon="lucide:circle-alert" width="14" />{{ error }}
        </p>
        <button class="btn-primary w-full py-3.5 text-base" type="submit" :disabled="busy">
          <Icon v-if="busy" icon="lucide:loader-circle" width="18" class="animate-spin" />{{ isLogin ? '登录' : '注册并登录' }}
        </button>
      </form>

      <div class="my-5 flex items-center gap-3 text-[11px] text-ink-mute"><span class="h-px flex-1 bg-ink-line" />或<span class="h-px flex-1 bg-ink-line" /></div>

      <button class="btn w-full border-2 border-dashed border-primary/30 bg-primary-light py-3.5 text-primary" type="button" :disabled="busy" @click="demo">
        <Icon icon="lucide:play-circle" width="18" />一键体验演示账号
      </button>
      <p class="mt-2 text-center text-[11px] text-ink-mute">已预置课表、计划、45 天学习记录与排行榜</p>

      <div v-if="native" class="mt-5 rounded-2xl bg-background p-3 text-xs">
        <button class="flex w-full items-center gap-2 text-left font-bold text-ink-soft" type="button" :aria-expanded="server.open" @click="server.open = !server.open">
          <Icon icon="lucide:server" width="15" />
          <span class="min-w-0 flex-1 truncate">服务器：{{ getServer() }}</span>
          <Icon :icon="server.open ? 'lucide:chevron-up' : 'lucide:chevron-down'" width="15" />
        </button>
        <div v-if="server.open" class="mt-3 space-y-2">
          <input v-model="server.value" class="field" type="url" inputmode="url" placeholder="https://app.xueyeguanjia.com" aria-label="服务器地址" />
          <p class="text-[11px] leading-5 text-ink-mute">局域网演示：填电脑的地址，如 http://192.168.1.5:5173（手机和电脑连同一个 Wi-Fi）。默认 {{ DEFAULT_SERVER }}</p>
          <p v-if="server.result" class="font-bold" :class="server.result.startsWith('✓') ? 'text-success' : 'text-danger'">{{ server.result }}</p>
          <div class="grid grid-cols-3 gap-2">
            <button class="btn-ghost py-2" type="button" @click="resetServer">恢复默认</button>
            <button class="btn-ghost py-2" type="button" :disabled="server.testing" @click="testServer">{{ server.testing ? '测试中…' : '测试连接' }}</button>
            <button class="btn-primary py-2" type="button" @click="saveServer">保存</button>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>
