<script setup>
/** 设置页 · 专注设置（白噪音默认、音量、防切出提醒） */
import { ref } from 'vue'
import { Icon } from '@iconify/vue'
import { NOISES, guardEnabled, setGuardEnabled } from '@/utils/noise'
import { useFocusStore } from '@/stores/focus'
import { useUiStore } from '@/stores/ui'

const focus = useFocusStore()
const ui = useUiStore()
const guard = ref(guardEnabled())
const previewing = ref(false)

const toggleGuard = () => {
  guard.value = !guard.value
  setGuardEnabled(guard.value)
  ui.success(guard.value ? '已开启防切出提醒' : '已关闭防切出提醒')
}

const pick = (key) => {
  // 设置页里只记住选择并短暂试听，不影响进行中的专注
  focus.setNoise(key)
  if (key === 'off' || focus.status === 'running') return
  previewing.value = true
  setTimeout(() => {
    if (focus.status !== 'running') focus.stopPreview()
    previewing.value = false
  }, 2500)
}
</script>

<template>
  <h2 class="mb-2 mt-5 px-1 text-xs font-black text-ink-mute">专注</h2>
  <div class="card divide-y divide-ink-line/60 overflow-hidden">
    <div class="px-4 py-3.5">
      <div class="flex items-center gap-3">
        <Icon icon="lucide:headphones" width="20" class="text-primary" />
        <span class="flex-1">
          <span class="block text-sm font-semibold text-ink">默认白噪音</span>
          <span class="block text-[11px] text-ink-mute">开始专注时自动播放；本机实时生成，不消耗流量{{ previewing ? ' · 试听中' : '' }}</span>
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
      <label v-if="focus.noiseKind !== 'off'" class="mt-3 flex items-center gap-3">
        <Icon icon="lucide:volume-2" width="16" class="shrink-0 text-ink-mute" />
        <input
          type="range"
          min="0"
          max="1"
          step="0.05"
          :value="focus.noiseVolume"
          class="h-1.5 flex-1 accent-primary"
          aria-label="白噪音音量"
          @input="focus.setNoiseVolume(Number($event.target.value))"
        />
        <span class="num w-8 text-right text-[11px] text-ink-mute">{{ Math.round(focus.noiseVolume * 100) }}</span>
      </label>
    </div>

    <button class="flex w-full items-center gap-3 px-4 py-3.5 text-left" type="button" role="switch" :aria-checked="guard" @click="toggleGuard">
      <Icon icon="lucide:eye-off" width="20" class="text-flame" />
      <span class="flex-1">
        <span class="block text-sm font-semibold text-ink">防切出提醒</span>
        <span class="block text-[11px] text-ink-mute">专注中切到其他页面或应用超过 3 秒，回来时温和提示并记录次数</span>
      </span>
      <span class="relative h-6 w-11 shrink-0 rounded-full transition" :class="guard ? 'bg-primary' : 'bg-ink-line'">
        <span class="absolute top-0.5 h-5 w-5 rounded-full bg-surface shadow transition-all" :class="guard ? 'left-[22px]' : 'left-0.5'" />
      </span>
    </button>
  </div>
</template>
