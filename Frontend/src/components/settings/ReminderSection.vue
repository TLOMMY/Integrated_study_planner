<script setup>
/** 设置页 · 提醒设置（任务提醒、默认提前时间、系统通知权限、测试提醒） */
import { computed, onMounted, ref } from 'vue'
import { Icon } from '@iconify/vue'
import { isNativeApp } from '@/api/server'
import { useUiStore } from '@/stores/ui'
import {
  notificationPermission,
  reminderSettings,
  requestNotificationPermission,
  setDefaultLead,
  setTaskReminderEnabled,
  testReminder,
} from '@/composables/useReminders'

const ui = useUiStore()
const permission = ref('prompt')
const asking = ref(false)

const LEADS = [
  { value: null, label: '不自动' },
  { value: 0, label: '准时' },
  { value: 5, label: '5 分钟' },
  { value: 15, label: '15 分钟' },
  { value: 30, label: '30 分钟' },
]

const PERMISSION_TEXT = {
  granted: { text: '已开启', cls: 'bg-success-light text-success' },
  denied: { text: '已拒绝', cls: 'bg-danger-light text-danger' },
  prompt: { text: '未开启', cls: 'bg-flame-light text-flame' },
  unsupported: { text: '不支持', cls: 'bg-background text-ink-mute' },
}
const permissionMeta = computed(() => PERMISSION_TEXT[permission.value] || PERMISSION_TEXT.prompt)
const permissionHint = computed(() => {
  if (permission.value === 'denied') return isNativeApp() ? '请到 手机设置 → 应用 → 学业管家 → 通知 中打开' : '请在浏览器地址栏左侧的站点设置里允许通知'
  if (permission.value === 'unsupported') return '当前浏览器不支持系统通知，页面打开时仍会弹出提醒'
  return isNativeApp() ? 'App 关闭后也能按时收到任务与课前提醒' : '页面打开时到点弹出提醒，开启后同时发系统通知'
})

const refresh = async () => {
  permission.value = await notificationPermission().catch(() => 'unsupported')
}
onMounted(refresh)

const toggle = () => {
  setTaskReminderEnabled(!reminderSettings.enabled)
  ui.toast(reminderSettings.enabled ? '已开启任务提醒' : '已关闭任务提醒', 'info')
}

const enable = async () => {
  asking.value = true
  try {
    permission.value = await requestNotificationPermission()
    if (permission.value === 'granted') ui.success('系统通知已开启')
    else if (permission.value === 'denied') ui.toast('通知权限被拒绝，可在系统设置里重新打开', 'warning', 3600)
  } finally {
    asking.value = false
  }
}

const pickLead = (value) => {
  setDefaultLead(value)
  ui.toast(value === null ? '新建任务时不自动设置提醒' : `新建定时任务默认${value ? `提前 ${value} 分钟` : '准时'}提醒`, 'info')
}
</script>

<template>
  <section>
    <h2 class="mb-2 mt-5 px-1 text-xs font-black text-ink-mute">任务提醒</h2>
    <div class="card divide-y divide-ink-line/60 overflow-hidden">
      <button class="flex w-full items-center gap-3 px-4 py-3.5 text-left" type="button" role="switch" :aria-checked="reminderSettings.enabled" @click="toggle">
        <Icon icon="lucide:bell" width="20" class="text-primary" />
        <span class="flex-1">
          <span class="block text-sm font-semibold text-ink">任务到点提醒</span>
          <span class="block text-[11px] text-ink-mute">在任务编辑里设置提醒时间，到点弹出提醒</span>
        </span>
        <span class="relative h-6 w-11 shrink-0 rounded-full transition" :class="reminderSettings.enabled ? 'bg-primary' : 'bg-ink-line'">
          <span class="absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-all" :class="reminderSettings.enabled ? 'left-[22px]' : 'left-0.5'" />
        </span>
      </button>

      <div class="px-4 py-3.5">
        <p class="text-sm font-semibold text-ink">默认提前</p>
        <p class="mb-2 text-[11px] text-ink-mute">新建有具体时刻的任务时自动带上的提醒，编辑时可改</p>
        <div class="scrollbar-hide -mx-1 flex gap-2 overflow-x-auto px-1" role="radiogroup" aria-label="默认提前时间">
          <button
            v-for="lead in LEADS"
            :key="String(lead.value)"
            type="button"
            role="radio"
            class="chip shrink-0"
            :class="reminderSettings.lead === lead.value && 'chip-active'"
            :aria-checked="reminderSettings.lead === lead.value"
            @click="pickLead(lead.value)"
          >
            {{ lead.label }}
          </button>
        </div>
      </div>

      <div class="flex items-center gap-3 px-4 py-3.5">
        <Icon icon="lucide:bell-ring" width="20" class="shrink-0 text-flame" />
        <span class="min-w-0 flex-1">
          <span class="flex items-center gap-2 text-sm font-semibold text-ink">
            系统通知
            <span class="rounded-full px-2 py-0.5 text-[10px] font-black" :class="permissionMeta.cls">{{ permissionMeta.text }}</span>
          </span>
          <span class="block text-[11px] text-ink-mute">{{ permissionHint }}</span>
        </span>
        <button v-if="permission === 'prompt'" class="chip chip-active shrink-0" type="button" :disabled="asking" @click="enable">
          <Icon icon="lucide:bell-plus" width="13" />开启通知
        </button>
        <button v-else-if="permission === 'denied'" class="chip shrink-0" type="button" @click="refresh">
          <Icon icon="lucide:refresh-cw" width="13" />重新检测
        </button>
      </div>

      <button class="flex w-full items-center gap-3 px-4 py-3.5 text-left" type="button" @click="testReminder">
        <Icon icon="lucide:send" width="20" class="text-xp" />
        <span class="flex-1 text-sm font-semibold text-ink">发送测试提醒</span>
        <Icon icon="lucide:chevron-right" width="16" class="text-ink-mute" />
      </button>
    </div>
  </section>
</template>
