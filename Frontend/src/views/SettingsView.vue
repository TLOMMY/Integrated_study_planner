<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import BottomSheet from '@/components/common/BottomSheet.vue'
import { feedbackApi, userApi } from '@/api'
import { useAuthStore } from '@/stores/auth'
import { useUiStore } from '@/stores/ui'
import { reminderEnabled, setReminderEnabled } from '@/composables/useClassReminder'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const ui = useUiStore()

const SEGMENTS = [
  { key: 'morning', label: '上午', hint: '8:00-12:00', icon: 'lucide:sunrise' },
  { key: 'afternoon', label: '下午', hint: '13:30-17:30', icon: 'lucide:sun' },
  { key: 'evening', label: '晚上', hint: '18:30-22:00', icon: 'lucide:moon' },
]
const BLOCKS = [25, 30, 45, 60, 90]
const RESTS = [5, 10, 15]
const CATEGORIES = [
  { key: 'bug', label: '功能异常' },
  { key: 'ui', label: '界面问题' },
  { key: 'suggestion', label: '功能建议' },
  { key: 'other', label: '其他' },
]

const sheet = ref('')
const busy = ref(false)
const form = reactive({ email: '', phone: '', password: '', old_password: '', new_password: '', confirm: '' })
const feedback = reactive({ category: 'bug', content: '', contact: '' })
const study = ref(null)
const prefs = reactive({ mode: 'auto', segments: [], avoid: [], earliest: '08:00', latest: '22:00', block_minutes: 45, rest_minutes: 10, daily_minutes: null })
const prefsDirty = ref(false)

const user = computed(() => auth.user || {})
const maxHour = computed(() => Math.max(1, ...(study.value?.profile.by_hour || [0])))
// 只画 6:00-23:00，凌晨基本没有数据
const hours = computed(() => (study.value?.profile.by_hour || []).map((m, h) => ({ h, m })).slice(6, 24))

watch(sheet, (value) => {
  Object.assign(form, { email: '', phone: user.value.phone || '', password: '', old_password: '', new_password: '', confirm: '' })
  if (value === 'feedback') feedback.content = feedback.content || ''
})

const loadPrefs = async () => {
  try {
    study.value = await userApi.studyPrefs()
    Object.assign(prefs, study.value.prefs)
    prefsDirty.value = false
  } catch (error) {
    ui.fail(error)
  }
}

onMounted(() => {
  loadPrefs()
  if (route.query.open === 'feedback') sheet.value = 'feedback'
})

const run = async (fn, message) => {
  busy.value = true
  try {
    await fn()
    if (message) ui.success(message)
    sheet.value = ''
  } catch (error) {
    ui.fail(error)
  } finally {
    busy.value = false
  }
}

const saveEmail = () => run(() => auth.changeEmail({ email: form.email, password: form.password }), '邮箱已更新')
const savePhone = (unbind = false) =>
  run(() => auth.changePhone({ phone: unbind ? '' : form.phone, password: form.password }), unbind ? '已解绑手机号' : '手机号已绑定')
const savePassword = () => {
  if (form.new_password.length < 6) return ui.toast('新密码至少 6 位', 'warning')
  if (form.new_password !== form.confirm) return ui.toast('两次输入的新密码不一致', 'warning')
  return run(() => auth.changePassword({ old_password: form.old_password, new_password: form.new_password }), '密码已修改，其他设备需要重新登录')
}
const logoutOthers = async () => {
  if (!(await ui.confirm({ title: '退出其他所有设备？', message: '其他手机和电脑上的登录会立即失效，本机保持登录。', confirmText: '退出其他设备' }))) return
  run(() => auth.logoutOthers(), '已退出其他设备')
}

// ---------------------------------------------------------------- 学习时段偏好
const toggleIn = (list, key, other) => {
  const i = list.indexOf(key)
  if (i >= 0) list.splice(i, 1)
  else {
    list.push(key)
    const j = other.indexOf(key)
    if (j >= 0) other.splice(j, 1)
  }
  prefsDirty.value = true
}
const setPref = (key, value) => {
  prefs[key] = value
  prefsDirty.value = true
}
const savePrefs = async () => {
  if (prefs.latest <= prefs.earliest) return ui.toast('最晚时间必须晚于最早时间', 'warning')
  busy.value = true
  try {
    study.value = await userApi.saveStudyPrefs({ ...prefs })
    Object.assign(prefs, study.value.prefs)
    prefsDirty.value = false
    ui.success('学习偏好已保存，AI 排程会按此安排')
  } catch (error) {
    ui.fail(error)
  } finally {
    busy.value = false
  }
}

// ---------------------------------------------------------------- 反馈 / 数据
const submitFeedback = () => {
  if (feedback.content.trim().length < 5) return ui.toast('请至少写 5 个字描述问题', 'warning')
  return run(async () => {
    await feedbackApi.submit({
      ...feedback,
      page: String(route.query.from || document.referrer || location.pathname).slice(0, 200),
      client: navigator.userAgent.slice(0, 300),
    })
    Object.assign(feedback, { category: 'bug', content: '', contact: '' })
  }, '感谢反馈！技术同学会尽快处理')
}

const exportData = () =>
  run(async () => {
    const data = await userApi.exportData()
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = `学业管家-数据导出-${new Date().toISOString().slice(0, 10)}.json`
    link.click()
    URL.revokeObjectURL(link.href)
  }, '已导出，文件已下载')

const deleteAccount = async () => {
  if (!form.password) return ui.toast('请输入密码确认', 'warning')
  const ok = await ui.confirm({ title: '确定注销账号？', message: '课表、任务、专注记录、等级与成就会被全部删除，无法恢复。', confirmText: '永久注销', danger: true })
  if (!ok) return
  run(async () => {
    await userApi.deleteAccount(form.password)
    auth.logout()
    router.replace('/login')
  }, '账号已注销')
}

const toggleReminder = () => {
  setReminderEnabled(!reminderEnabled.value)
  ui.toast(reminderEnabled.value ? '已开启课前 10 分钟提醒' : '已关闭课前提醒', 'info')
}
</script>

<template>
  <div class="scrollbar-hide h-full overflow-y-auto pb-24 lg:pb-10">
    <header class="sticky top-0 z-10 flex items-center gap-3 bg-background/90 px-4 pb-3 pt-[calc(var(--safe-top)+16px)] backdrop-blur lg:px-10 lg:pt-8">
      <button class="icon-btn lg:hidden" type="button" aria-label="返回" @click="router.back()"><Icon icon="lucide:chevron-left" width="20" /></button>
      <h1 class="text-lg font-black text-ink lg:text-[22px]">设置</h1>
    </header>

    <div class="space-y-5 px-4 lg:mx-auto lg:grid lg:max-w-5xl lg:grid-cols-2 lg:items-start lg:gap-5 lg:space-y-0 lg:px-10">
      <!-- 账号与安全 -->
      <section>
        <h2 class="mb-2 px-1 text-xs font-black text-ink-mute">账号与安全</h2>
        <p v-if="auth.isDemo" class="mb-2 rounded-2xl bg-flame-light px-3 py-2 text-xs font-semibold text-flame">演示账号不能修改邮箱、手机和密码，注册自己的账号后即可使用</p>
        <div class="card divide-y divide-ink-line/60 overflow-hidden">
          <button class="flex w-full items-center gap-3 px-4 py-3.5 text-left disabled:opacity-60" type="button" :disabled="auth.isDemo" @click="sheet = 'email'">
            <Icon icon="lucide:mail" width="20" class="text-primary" />
            <span class="flex-1 text-sm font-semibold text-ink">绑定邮箱</span>
            <span class="max-w-[50%] truncate text-xs font-bold text-ink-mute">{{ user.email }}</span>
            <Icon icon="lucide:chevron-right" width="16" class="text-ink-mute" />
          </button>
          <button class="flex w-full items-center gap-3 px-4 py-3.5 text-left disabled:opacity-60" type="button" :disabled="auth.isDemo" @click="sheet = 'phone'">
            <Icon icon="lucide:smartphone" width="20" class="text-success" />
            <span class="flex-1 text-sm font-semibold text-ink">绑定手机号</span>
            <span class="text-xs font-bold" :class="user.phone ? 'text-ink-mute' : 'text-flame'">{{ user.phone_masked || '未绑定' }}</span>
            <Icon icon="lucide:chevron-right" width="16" class="text-ink-mute" />
          </button>
          <button class="flex w-full items-center gap-3 px-4 py-3.5 text-left disabled:opacity-60" type="button" :disabled="auth.isDemo" @click="sheet = 'password'">
            <Icon icon="lucide:key-round" width="20" class="text-xp" />
            <span class="flex-1 text-sm font-semibold text-ink">修改密码</span>
            <Icon icon="lucide:chevron-right" width="16" class="text-ink-mute" />
          </button>
          <button class="flex w-full items-center gap-3 px-4 py-3.5 text-left" type="button" @click="logoutOthers">
            <Icon icon="lucide:monitor-smartphone" width="20" class="text-ink-soft" />
            <span class="flex-1">
              <span class="block text-sm font-semibold text-ink">退出其他设备</span>
              <span class="block text-[11px] text-ink-mute">手机丢了或在公共电脑登录过时使用</span>
            </span>
            <Icon icon="lucide:chevron-right" width="16" class="text-ink-mute" />
          </button>
        </div>

        <h2 class="mb-2 mt-5 px-1 text-xs font-black text-ink-mute">通知</h2>
        <div class="card overflow-hidden">
          <button class="flex w-full items-center gap-3 px-4 py-3.5 text-left" type="button" role="switch" :aria-checked="reminderEnabled" @click="toggleReminder">
            <Icon icon="lucide:bell-ring" width="20" class="text-flame" />
            <span class="flex-1">
              <span class="block text-sm font-semibold text-ink">课前提醒</span>
              <span class="block text-[11px] text-ink-mute">页面打开时，上课前 10 分钟提醒</span>
            </span>
            <span class="relative h-6 w-11 rounded-full transition" :class="reminderEnabled ? 'bg-primary' : 'bg-ink-line'">
              <span class="absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-all" :class="reminderEnabled ? 'left-[22px]' : 'left-0.5'" />
            </span>
          </button>
        </div>

        <h2 class="mb-2 mt-5 px-1 text-xs font-black text-ink-mute">帮助与数据</h2>
        <div class="card divide-y divide-ink-line/60 overflow-hidden">
          <button class="flex w-full items-center gap-3 px-4 py-3.5 text-left" type="button" @click="sheet = 'feedback'">
            <Icon icon="lucide:message-square-warning" width="20" class="text-primary" />
            <span class="flex-1">
              <span class="block text-sm font-semibold text-ink">问题反馈</span>
              <span class="block text-[11px] text-ink-mute">遇到问题或有建议，告诉技术同学</span>
            </span>
            <Icon icon="lucide:chevron-right" width="16" class="text-ink-mute" />
          </button>
          <button class="flex w-full items-center gap-3 px-4 py-3.5 text-left" type="button" :disabled="busy" @click="exportData">
            <Icon icon="lucide:download" width="20" class="text-success" />
            <span class="flex-1 text-sm font-semibold text-ink">导出我的数据</span>
            <span class="text-xs text-ink-mute">JSON</span>
          </button>
          <button v-if="!auth.isDemo" class="flex w-full items-center gap-3 px-4 py-3.5 text-left" type="button" @click="sheet = 'delete'">
            <Icon icon="lucide:user-x" width="20" class="text-danger" />
            <span class="flex-1 text-sm font-semibold text-danger">注销账号</span>
            <Icon icon="lucide:chevron-right" width="16" class="text-ink-mute" />
          </button>
        </div>
      </section>

      <!-- 学习时段偏好 -->
      <section>
        <h2 class="mb-2 px-1 text-xs font-black text-ink-mute">学习时段偏好 · AI 排程会读取</h2>
        <div class="card p-4">
          <div v-if="!study" class="skeleton h-40" />
          <template v-else>
            <div class="flex items-center justify-between">
              <h3 class="section-title">我的专注习惯</h3>
              <span class="text-[11px] text-ink-mute">近 {{ study.profile.days }} 天 · {{ study.profile.sessions }} 次 · {{ Math.round(study.profile.total_minutes / 60) }} 小时</span>
            </div>
            <div class="mt-3 flex h-20 items-end gap-[3px]" role="img" :aria-label="`专注最多的时段：${study.profile.peak_hour ?? '暂无'} 点`">
              <div v-for="b in hours" :key="b.h" class="flex flex-1 flex-col items-center gap-1">
                <div class="w-full rounded-t-md" :class="b.h === study.profile.peak_hour ? 'bg-primary' : 'bg-primary-soft'" :style="{ height: `${Math.max(3, (b.m / maxHour) * 64)}px` }" />
                <span class="num text-[8px] text-ink-mute">{{ b.h % 3 === 0 ? b.h : '' }}</span>
              </div>
            </div>
            <div class="mt-3 grid grid-cols-3 gap-2 text-center">
              <div v-for="seg in study.profile.segments" :key="seg.key" class="rounded-2xl bg-background py-2">
                <p class="num text-base font-black text-ink">{{ seg.share }}%</p>
                <p class="text-[10px] font-bold text-ink-mute">{{ seg.label }}</p>
              </div>
            </div>
            <p v-if="!study.profile.enough" class="mt-2 text-[11px] text-ink-mute">专注满 5 小时后，自动模式会按你最常学习的时段优先安排</p>

            <div class="mt-4 grid grid-cols-2 rounded-2xl bg-background p-1">
              <button v-for="m in [{ k: 'auto', l: '按专注习惯自动' }, { k: 'custom', l: '自定义' }]" :key="m.k" type="button" class="rounded-xl py-2 text-xs font-black transition" :class="prefs.mode === m.k ? 'bg-surface text-primary shadow-soft' : 'text-ink-mute'" @click="setPref('mode', m.k)">
                {{ m.l }}
              </button>
            </div>

            <div v-if="prefs.mode === 'custom'" class="mt-4 space-y-4">
              <div>
                <p class="label">优先安排（可多选，按点选顺序）</p>
                <div class="grid grid-cols-3 gap-2">
                  <button v-for="seg in SEGMENTS" :key="seg.key" type="button" class="flex flex-col items-center rounded-2xl border py-2 transition" :class="prefs.segments.includes(seg.key) ? 'border-primary bg-primary-light text-primary' : 'border-ink-line text-ink-soft'" @click="toggleIn(prefs.segments, seg.key, prefs.avoid)">
                    <Icon :icon="seg.icon" width="18" />
                    <span class="mt-0.5 text-xs font-black">{{ seg.label }}<span v-if="prefs.segments.includes(seg.key)" class="num ml-0.5">{{ prefs.segments.indexOf(seg.key) + 1 }}</span></span>
                    <span class="num text-[9px] opacity-70">{{ seg.hint }}</span>
                  </button>
                </div>
              </div>
              <div>
                <p class="label">尽量不排</p>
                <div class="flex gap-2">
                  <button v-for="seg in SEGMENTS" :key="seg.key" type="button" class="chip" :class="prefs.avoid.includes(seg.key) && 'border-danger bg-danger-light text-danger'" @click="toggleIn(prefs.avoid, seg.key, prefs.segments)">{{ seg.label }}</button>
                </div>
              </div>
              <div class="grid grid-cols-2 gap-3">
                <label><span class="label">最早开始</span><input class="field" type="time" :value="prefs.earliest" @change="setPref('earliest', $event.target.value)" /></label>
                <label><span class="label">最晚结束</span><input class="field" type="time" :value="prefs.latest" @change="setPref('latest', $event.target.value)" /></label>
              </div>
              <div>
                <p class="label">每段学习时长</p>
                <div class="flex flex-wrap gap-2">
                  <button v-for="b in BLOCKS" :key="b" type="button" class="chip num" :class="prefs.block_minutes === b && 'chip-active'" @click="setPref('block_minutes', b)">{{ b }} 分钟</button>
                </div>
              </div>
              <div>
                <p class="label">段间休息</p>
                <div class="flex gap-2">
                  <button v-for="r in RESTS" :key="r" type="button" class="chip num" :class="prefs.rest_minutes === r && 'chip-active'" @click="setPref('rest_minutes', r)">{{ r }} 分钟</button>
                </div>
              </div>
            </div>

            <p class="mt-4 rounded-2xl bg-primary-light px-3 py-2 text-xs font-semibold text-primary">
              <Icon icon="lucide:sparkles" width="13" class="mr-1 inline" />当前生效：{{ study.effective.text }}
            </p>
            <button class="btn-primary mt-3 w-full" type="button" :disabled="busy || !prefsDirty" @click="savePrefs">{{ prefsDirty ? '保存偏好' : '已保存' }}</button>
          </template>
        </div>
      </section>
    </div>

    <!-- 弹窗 -->
    <BottomSheet :open="sheet === 'email'" title="绑定邮箱" subtitle="换绑后用新邮箱登录" @close="sheet = ''">
      <div class="space-y-3 pb-2">
        <p class="text-xs text-ink-mute">当前：{{ user.email }}</p>
        <input v-model="form.email" class="field" type="email" placeholder="新邮箱" autocomplete="email" />
        <input v-model="form.password" class="field" type="password" placeholder="当前密码（验证身份）" autocomplete="current-password" />
      </div>
      <template #footer><button class="btn-primary w-full" type="button" :disabled="busy || !form.email || !form.password" @click="saveEmail">确认换绑</button></template>
    </BottomSheet>

    <BottomSheet :open="sheet === 'phone'" title="绑定手机号" subtitle="用于找回账号；短信验证将在接入短信服务后开启" @close="sheet = ''">
      <div class="space-y-3 pb-2">
        <input v-model="form.phone" class="field" type="tel" inputmode="numeric" maxlength="16" placeholder="11 位手机号" autocomplete="tel" />
        <input v-model="form.password" class="field" type="password" placeholder="当前密码（验证身份）" autocomplete="current-password" />
      </div>
      <template #footer>
        <div class="grid gap-2" :class="user.phone ? 'grid-cols-2' : ''">
          <button v-if="user.phone" class="btn-ghost" type="button" :disabled="busy || !form.password" @click="savePhone(true)">解绑</button>
          <button class="btn-primary" type="button" :disabled="busy || !form.phone || !form.password" @click="savePhone()">保存</button>
        </div>
      </template>
    </BottomSheet>

    <BottomSheet :open="sheet === 'password'" title="修改密码" subtitle="修改后其他设备需要重新登录" @close="sheet = ''">
      <div class="space-y-3 pb-2">
        <input v-model="form.old_password" class="field" type="password" placeholder="原密码" autocomplete="current-password" />
        <input v-model="form.new_password" class="field" type="password" placeholder="新密码（至少 6 位）" autocomplete="new-password" />
        <input v-model="form.confirm" class="field" type="password" placeholder="再输入一次新密码" autocomplete="new-password" />
      </div>
      <template #footer><button class="btn-primary w-full" type="button" :disabled="busy" @click="savePassword">确认修改</button></template>
    </BottomSheet>

    <BottomSheet :open="sheet === 'feedback'" title="问题反馈" subtitle="会连同页面与设备信息一起保存，方便定位问题" @close="sheet = ''">
      <div class="space-y-3 pb-2">
        <div class="flex flex-wrap gap-2">
          <button v-for="c in CATEGORIES" :key="c.key" type="button" class="chip" :class="feedback.category === c.key && 'chip-active'" @click="feedback.category = c.key">{{ c.label }}</button>
        </div>
        <textarea v-model="feedback.content" class="field min-h-[140px] resize-none" maxlength="2000" placeholder="请描述遇到的问题：在哪个页面、做了什么操作、看到了什么结果…" />
        <p class="num text-right text-[11px] text-ink-mute">{{ feedback.content.length }}/2000</p>
        <input v-model="feedback.contact" class="field" maxlength="100" placeholder="联系方式（选填，微信 / QQ / 邮箱）" />
      </div>
      <template #footer><button class="btn-primary w-full" type="button" :disabled="busy" @click="submitFeedback"><Icon icon="lucide:send" width="16" />提交反馈</button></template>
    </BottomSheet>

    <BottomSheet :open="sheet === 'delete'" title="注销账号" @close="sheet = ''">
      <div class="space-y-3 pb-2">
        <p class="rounded-2xl bg-danger-light px-3 py-2.5 text-xs font-semibold leading-5 text-danger">注销后，课表、任务、学习计划、专注记录、等级与成就会被永久删除。建议先「导出我的数据」备份。</p>
        <input v-model="form.password" class="field" type="password" placeholder="输入密码确认" autocomplete="current-password" />
      </div>
      <template #footer><button class="btn w-full bg-danger text-white" type="button" :disabled="busy || !form.password" @click="deleteAccount">永久注销</button></template>
    </BottomSheet>
  </div>
</template>
