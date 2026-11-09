<script setup>
/** 设置页 · 专注设置（默认声音：白噪音或我的歌单、音量、防切出提醒、我的音乐） */
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { Icon } from '@iconify/vue'
import MusicLibrary from './MusicLibrary.vue'
import { NOISES, guardEnabled, setGuardEnabled, setStrictEnabled, strictEnabled } from '@/utils/noise'
import { playlistKey } from '@/utils/music'
import { library, playlistForKey, reloadLibrary } from '@/composables/useMusicLibrary'
import { useFocusStore } from '@/stores/focus'
import { useUiStore } from '@/stores/ui'

const focus = useFocusStore()
const ui = useUiStore()
const guard = ref(guardEnabled())
const strict = ref(strictEnabled())
const previewing = ref(false)
let previewTimer = null

onMounted(async () => {
  await reloadLibrary()
  // 默认声音指向的歌单已被删除：退回关闭
  if (focus.noiseKind.startsWith('playlist:') && !playlistForKey(focus.noiseKind) && !library.error) focus.setNoise('off')
})

const toggleGuard = () => {
  guard.value = !guard.value
  setGuardEnabled(guard.value)
  ui.success(guard.value ? '已开启防切出提醒' : '已关闭防切出提醒')
  strict.value = strictEnabled()
}
const toggleStrict = () => {
  setStrictEnabled(!strict.value)
  strict.value = strictEnabled()
  ui.success(strict.value ? '已开启严格模式' : '已关闭严格模式')
}

const pick = (key) => {
  // 设置页里只记住选择并短暂试听，不影响进行中的专注
  focus.setNoise(key)
  clearTimeout(previewTimer)
  if (key === 'off' || focus.status === 'running') return (previewing.value = false)
  previewing.value = true
  previewTimer = setTimeout(() => {
    if (focus.status !== 'running') focus.stopPreview()
    previewing.value = false
  }, 3000)
}
onBeforeUnmount(() => {
  clearTimeout(previewTimer)
  if (previewing.value) focus.stopPreview()
})
</script>

<template>
  <h2 class="mb-2 mt-5 px-1 text-xs font-black text-ink-mute">专注</h2>
  <div class="card divide-y divide-ink-line/60 overflow-hidden">
    <div class="px-4 py-3.5">
      <div class="flex items-center gap-3">
        <Icon icon="lucide:headphones" width="20" class="text-primary" />
        <span class="flex-1">
          <span class="block text-sm font-semibold text-ink">默认声音</span>
          <span class="block text-[11px] text-ink-mute">开始专注时自动播放，暂停 / 结束时跟着停；白噪音本机实时生成，不消耗流量{{ previewing ? ' · 试听中' : '' }}</span>
        </span>
      </div>
      <div class="mt-3 grid grid-cols-5 gap-1.5" role="radiogroup" aria-label="默认白噪音">
        <button
          v-for="n in NOISES"
          :key="n.key"
          type="button"
          role="radio"
          :aria-checked="focus.noiseKind === n.key"
          class="flex flex-col items-center gap-1 rounded-2xl py-2 text-[11px] font-bold transition"
          :class="focus.noiseKind === n.key ? 'bg-primary-light text-primary ring-1 ring-primary/30' : 'bg-background text-ink-soft'"
          @click="pick(n.key)"
        >
          <Icon :icon="n.icon" width="18" />{{ n.label }}
        </button>
      </div>
      <div v-if="library.playlists.length" class="mt-2 flex flex-wrap gap-1.5" role="radiogroup" aria-label="或播放我的歌单">
        <button
          v-for="p in library.playlists"
          :key="p.id"
          type="button"
          role="radio"
          :aria-checked="focus.noiseKind === playlistKey(p.id)"
          class="chip max-w-full"
          :class="focus.noiseKind === playlistKey(p.id) && 'chip-active'"
          @click="pick(playlistKey(p.id))"
        >
          <Icon icon="lucide:list-music" width="13" class="shrink-0" /><span class="truncate">{{ p.name }}</span><span class="num opacity-70">· {{ p.trackIds.length }}</span>
        </button>
      </div>
      <label v-if="focus.noiseKind !== 'off'" class="mt-3 flex items-center gap-3">
        <Icon icon="lucide:volume-2" width="16" class="shrink-0 text-ink-mute" />
        <input
          type="range"
          min="0"
          max="1"
          step="0.05"
          :value="focus.noiseVolume"
          class="h-1.5 flex-1 accent-primary"
          aria-label="专注声音音量"
          @input="focus.setNoiseVolume(Number($event.target.value))"
        />
        <span class="num w-8 text-right text-[11px] text-ink-mute">{{ Math.round(focus.noiseVolume * 100) }}</span>
      </label>
    </div>

    <button class="flex w-full items-center gap-3 px-4 py-3.5 text-left" type="button" role="switch" :aria-checked="guard" @click="toggleGuard">
      <Icon icon="lucide:eye-off" width="20" class="text-flame" />
      <span class="flex-1">
        <span class="block text-sm font-semibold text-ink">防切出提醒</span>
        <span class="block text-[11px] text-ink-mute">专注中切到其他页面或应用超过 3 秒，回来时温和提示并记录次数；整轮没切出的完整番茄额外 +3 XP</span>
      </span>
      <span class="relative h-6 w-11 shrink-0 rounded-full transition" :class="guard ? 'bg-primary' : 'bg-ink-line'">
        <span class="absolute top-0.5 h-5 w-5 rounded-full bg-surface shadow transition-all" :class="guard ? 'left-[22px]' : 'left-0.5'" />
      </span>
    </button>
    <!-- 严格模式：依赖防切出，关掉防切出时一起失效 -->
    <button v-if="guard" class="flex w-full items-center gap-3 border-t border-ink-line/60 px-4 py-3.5 text-left" type="button" role="switch" :aria-checked="strict" @click="toggleStrict">
      <Icon icon="lucide:shield-check" width="20" class="text-flame" />
      <span class="flex-1">
        <span class="block text-sm font-semibold text-ink">严格模式</span>
        <span class="block text-[11px] text-ink-mute">切出超过 10 秒自动暂停，离开的时间不计入专注；已专注的时间不会扣</span>
      </span>
      <span class="relative h-6 w-11 shrink-0 rounded-full transition" :class="strict ? 'bg-primary' : 'bg-ink-line'">
        <span class="absolute top-0.5 h-5 w-5 rounded-full bg-surface shadow transition-all" :class="strict ? 'left-[22px]' : 'left-0.5'" />
      </span>
    </button>
  </div>
  <MusicLibrary />
</template>
