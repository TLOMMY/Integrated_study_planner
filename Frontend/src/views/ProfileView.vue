<script setup>
import { reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import BottomSheet from '@/components/common/BottomSheet.vue'
import { useAuthStore } from '@/stores/auth'
import { useGameStore } from '@/stores/game'
import { useHomeStore } from '@/stores/home'
import { useUiStore } from '@/stores/ui'
import { reminderEnabled, setReminderEnabled } from '@/composables/useClassReminder'

const router = useRouter()
const auth = useAuthStore()
const game = useGameStore()
const ui = useUiStore()

const AVATARS = ['🦉', '🐼', '🦊', '🐱', '🐯', '🐧', '🐨', '🐸', '🦄', '🐳', '🐝', '🌱']
const GOALS = [15, 30, 60, 90, 120, 180]

const sheet = ref('')
const name = ref('')
const pwd = reactive({ old_password: '', new_password: '' })
const saving = ref(false)

watch(sheet, (value) => {
  if (value === 'name') name.value = auth.user?.full_name || ''
  if (value === 'password') Object.assign(pwd, { old_password: '', new_password: '' })
})

const save = async (payload, message = '已保存') => {
  saving.value = true
  try {
    await auth.updateProfile(payload)
    useHomeStore().refresh()
    ui.success(message)
    sheet.value = ''
  } catch (error) {
    ui.fail(error)
  } finally {
    saving.value = false
  }
}

const changePassword = async () => {
  if (pwd.new_password.length < 6) return ui.toast('新密码至少 6 位', 'warning')
  saving.value = true
  try {
    await auth.changePassword({ ...pwd })
    ui.success('密码已修改，其他设备需要重新登录')
    sheet.value = ''
  } catch (error) {
    ui.fail(error)
  } finally {
    saving.value = false
  }
}

const toggleReminder = () => {
  setReminderEnabled(!reminderEnabled.value)
  ui.toast(reminderEnabled.value ? '已开启课前 10 分钟提醒' : '已关闭课前提醒', 'info')
}

const logout = async () => {
  if (!(await ui.confirm({ title: '退出登录', message: '本机保存的 AI 对话记录会保留。', confirmText: '退出' }))) return
  auth.logout()
  router.replace('/login')
}
</script>

<template>
  <div class="scrollbar-hide h-full overflow-y-auto pb-24 lg:pb-10">
    <section class="bg-gradient-to-b from-primary-light to-background px-5 pb-6 pt-[calc(var(--safe-top)+16px)]">
      <button class="icon-btn lg:invisible" type="button" aria-label="返回" @click="router.back()"><Icon icon="lucide:chevron-left" width="20" /></button>
      <div class="mt-2 flex flex-col items-center text-center">
        <button class="relative flex h-24 w-24 items-center justify-center rounded-full bg-surface text-5xl shadow-soft" type="button" aria-label="更换头像" @click="sheet = 'avatar'">
          {{ auth.user?.avatar }}
          <span class="absolute bottom-0 right-0 flex h-7 w-7 items-center justify-center rounded-full bg-primary text-on-primary ring-4 ring-primary-light"><Icon icon="lucide:pencil" width="13" /></span>
        </button>
        <button class="mt-3 flex items-center gap-1 text-xl font-black text-ink" type="button" @click="sheet = 'name'">
          {{ auth.displayName }}<Icon icon="lucide:pencil" width="14" class="text-ink-mute" />
        </button>
        <p class="mt-0.5 text-xs text-ink-mute">{{ auth.user?.email }}<span v-if="auth.isDemo" class="ml-1 rounded bg-flame-light px-1.5 text-flame">演示账号</span></p>
        <div v-if="game.level" class="mt-3 flex gap-2">
          <span class="rounded-full bg-xp-light px-3 py-1 text-xs font-black text-xp">Lv.{{ game.level.level }}</span>
          <span class="rounded-full bg-flame-light px-3 py-1 text-xs font-black text-flame">🔥 {{ game.streak?.current ?? 0 }} 天</span>
        </div>
      </div>
    </section>

    <div class="space-y-4 px-5 lg:mx-auto lg:max-w-2xl">
      <section class="card divide-y divide-ink-line/60 overflow-hidden">
        <button class="flex w-full items-center gap-3 px-4 py-3.5 text-left" type="button" @click="sheet = 'goal'">
          <Icon icon="lucide:target" width="20" class="text-success" />
          <span class="flex-1 text-sm font-semibold text-ink">每日专注目标</span>
          <span class="text-xs font-bold text-ink-mute">{{ auth.user?.daily_goal_minutes }} 分钟</span>
          <Icon icon="lucide:chevron-right" width="16" class="text-ink-mute" />
        </button>
        <RouterLink to="/timetable" class="flex items-center gap-3 px-4 py-3.5">
          <Icon icon="lucide:calendar-cog" width="20" class="text-primary" />
          <span class="flex-1 text-sm font-semibold text-ink">学期与节次设置</span>
          <span class="text-xs font-bold text-ink-mute">{{ auth.user?.semester }}</span>
          <Icon icon="lucide:chevron-right" width="16" class="text-ink-mute" />
        </RouterLink>
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
        <RouterLink to="/plans" class="flex items-center gap-3 px-4 py-3.5">
          <Icon icon="lucide:map" width="20" class="text-xp" />
          <span class="flex-1 text-sm font-semibold text-ink">学习计划</span>
          <Icon icon="lucide:chevron-right" width="16" class="text-ink-mute" />
        </RouterLink>
      </section>

      <section class="card divide-y divide-ink-line/60 overflow-hidden">
        <RouterLink to="/settings" class="flex items-center gap-3 px-4 py-3.5">
          <Icon icon="lucide:settings" width="20" class="text-ink-soft" />
          <span class="flex-1">
            <span class="block text-sm font-semibold text-ink">设置</span>
            <span class="block text-[11px] text-ink-mute">账号安全 · 学习时段偏好 · 问题反馈 · 数据导出</span>
          </span>
          <Icon icon="lucide:chevron-right" width="16" class="text-ink-mute" />
        </RouterLink>
        <button class="flex w-full items-center gap-3 px-4 py-3.5 text-left" type="button" @click="logout">
          <Icon icon="lucide:log-out" width="20" class="text-danger" />
          <span class="flex-1 text-sm font-semibold text-danger">退出登录</span>
        </button>
      </section>

      <p class="pb-2 text-center text-[10px] text-ink-mute">学业管家 v3.0 · 课表 × 任务 × 番茄钟 × 成长激励</p>
    </div>

    <BottomSheet :open="sheet === 'avatar'" title="选择头像" @close="sheet = ''">
      <div class="grid grid-cols-6 gap-2 pb-2">
        <button v-for="a in AVATARS" :key="a" type="button" class="flex aspect-square items-center justify-center rounded-2xl text-3xl transition" :class="auth.user?.avatar === a ? 'bg-primary-light ring-2 ring-primary' : 'bg-background'" @click="save({ avatar: a }, '头像已更新')">
          {{ a }}
        </button>
      </div>
    </BottomSheet>

    <BottomSheet :open="sheet === 'name'" title="修改昵称" @close="sheet = ''">
      <input v-model="name" class="field" maxlength="40" placeholder="昵称" @keydown.enter="name.trim() && save({ full_name: name.trim() })" />
      <template #footer><button class="btn-primary w-full" type="button" :disabled="saving || !name.trim()" @click="save({ full_name: name.trim() })">保存</button></template>
    </BottomSheet>

    <BottomSheet :open="sheet === 'goal'" title="每日专注目标" subtitle="达成后获得额外 XP，并计入连续打卡" @close="sheet = ''">
      <div class="grid grid-cols-3 gap-2 pb-2">
        <button
          v-for="g in GOALS"
          :key="g"
          type="button"
          class="rounded-2xl border-2 py-4 text-center transition"
          :class="auth.user?.daily_goal_minutes === g ? 'border-primary bg-primary-light text-primary' : 'border-ink-line text-ink'"
          @click="save({ daily_goal_minutes: g }, `每日目标改为 ${g} 分钟`)"
        >
          <p class="num text-xl font-black">{{ g }}</p>
          <p class="text-[10px] font-bold opacity-70">{{ g <= 30 ? '轻松' : g <= 90 ? '认真' : '硬核' }}</p>
        </button>
      </div>
    </BottomSheet>

    <BottomSheet :open="sheet === 'password'" title="修改密码" @close="sheet = ''">
      <div class="space-y-3">
        <input v-model="pwd.old_password" type="password" class="field" placeholder="原密码" autocomplete="current-password" />
        <input v-model="pwd.new_password" type="password" class="field" placeholder="新密码（至少 6 位）" autocomplete="new-password" />
      </div>
      <template #footer><button class="btn-primary w-full" type="button" :disabled="saving" @click="changePassword">确认修改</button></template>
    </BottomSheet>
  </div>
</template>
