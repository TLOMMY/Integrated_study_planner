<script setup>
/** 设置页 · 外观主题（主题切换、跟随系统、无障碍显示开关、快捷键说明） */
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { useTheme } from '@/composables/useTheme'
import { openShortcutsHelp } from '@/composables/useShortcuts'
import { useDesktop } from '@/composables/useDesktop'
import { resolveVars } from '@/themes'

const { themes, system, choice, setTheme, a11y, setA11y } = useTheme()
const isDesktop = useDesktop()

// 卡片预览：玻璃主题显示它的壁纸，普通主题显示底色；"跟随系统"为浅 / 深对半
const darkTheme = themes.find((t) => t.id === 'dark')
const lightTheme = themes.find((t) => t.id === 'default')
const options = computed(() => [
  ...themes.map((t) => ({ ...t, split: false, wallpaper: t.glass ? resolveVars(t).wallpaper : null })),
  { ...system, preview: [lightTheme.preview[1], darkTheme.preview[1], lightTheme.preview[0]], split: true },
])

const SWITCHES = [
  { key: 'transparency', icon: 'lucide:layers', title: '降低透明度', text: '玻璃效果换成不透明底色，去掉模糊' },
  { key: 'contrast', icon: 'lucide:contrast', title: '增强对比度', text: '次要文字与分隔线加深，玻璃描边更清楚' },
  { key: 'borders', icon: 'lucide:square-dashed', title: '显示边框', text: '按钮、卡片、输入框加一圈实线边框' },
]
</script>

<template>
  <section>
    <h2 class="mb-2 mt-5 px-1 text-xs font-black text-ink-mute">外观</h2>
    <div class="card p-4">
      <div role="radiogroup" aria-label="界面主题" class="grid grid-cols-3 gap-2.5">
        <button
          v-for="t in options"
          :key="t.id"
          type="button"
          role="radio"
          :aria-checked="choice === t.id"
          :title="t.description"
          class="relative rounded-2xl border-2 p-2 text-left transition active:scale-[.97]"
          :class="choice === t.id ? 'border-primary bg-primary-light' : 'border-ink-line/70 hover:border-primary/40'"
          :data-theme-option="t.id"
          @click="setTheme(t.id)"
        >
          <!-- 预览色块：底色（玻璃主题为壁纸）+ 主色 + 强调色；跟随系统为浅 / 深对半 -->
          <span class="flex h-12 overflow-hidden rounded-xl ring-1 ring-ink-line/60">
            <template v-if="t.split">
              <span class="flex flex-1 items-end p-1.5" :style="{ background: t.preview[0] }"><span class="h-2 w-6 rounded-full" :style="{ background: t.preview[2] }" /></span>
              <span class="flex flex-1 items-end p-1.5" :style="{ background: t.preview[1] }"><span class="h-2 w-6 rounded-full" :style="{ background: darkTheme.preview[0] }" /></span>
            </template>
            <span v-else class="flex flex-1 items-end gap-1 p-1.5" :style="{ background: t.wallpaper || t.preview[1] }">
              <span class="h-5 w-5 rounded-lg" :style="{ background: t.preview[0] }" />
              <span class="h-3 w-3 rounded-md" :style="{ background: t.preview[2] }" />
            </span>
          </span>
          <span class="mt-1.5 flex items-center gap-1">
            <span class="min-w-0 flex-1 truncate text-xs font-black" :class="choice === t.id ? 'text-primary' : 'text-ink'">{{ t.name }}</span>
            <Icon v-if="choice === t.id" icon="lucide:circle-check" width="14" class="shrink-0 text-primary" />
          </span>
          <span class="block truncate text-[10px] text-ink-mute">{{ t.description }}</span>
        </button>
      </div>
      <p class="mt-3 text-[11px] text-ink-mute">主题会保存到账号，换设备登录后自动使用同一主题</p>
    </div>

    <!-- 无障碍：系统设置之外的兜底开关（只存本机） -->
    <div class="card mt-3 divide-y divide-ink-line/60 overflow-hidden">
      <button
        v-for="s in SWITCHES"
        :key="s.key"
        class="flex w-full items-center gap-3 px-4 py-3.5 text-left"
        type="button"
        role="switch"
        :aria-checked="a11y[s.key]"
        :data-a11y="s.key"
        @click="setA11y(s.key, !a11y[s.key])"
      >
        <Icon :icon="s.icon" width="20" class="shrink-0 text-ink-soft" />
        <span class="min-w-0 flex-1">
          <span class="block text-sm font-semibold text-ink">{{ s.title }}</span>
          <span class="block text-[11px] text-ink-mute">{{ s.text }}</span>
        </span>
        <span class="relative h-6 w-11 shrink-0 rounded-full transition" :class="a11y[s.key] ? 'bg-primary' : 'bg-ink-line'">
          <span class="absolute top-0.5 h-5 w-5 rounded-full shadow transition-all" :class="[a11y[s.key] ? 'left-[22px] bg-on-primary' : 'left-0.5 bg-surface']" />
        </span>
      </button>
    </div>

    <button v-if="isDesktop" class="card mt-3 flex w-full items-center gap-3 px-4 py-3.5 text-left" type="button" @click="openShortcutsHelp">
      <Icon icon="lucide:keyboard" width="20" class="text-primary" />
      <span class="flex-1">
        <span class="block text-sm font-semibold text-ink">键盘快捷键</span>
        <span class="block text-[11px] text-ink-mute">按 ? 随时查看</span>
      </span>
      <Icon icon="lucide:chevron-right" width="16" class="text-ink-mute" />
    </button>
  </section>
</template>
