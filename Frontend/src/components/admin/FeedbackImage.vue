<script setup>
/** 反馈截图缩略图：截图需要登录才能看，用接口取回 Blob 再显示；点击放大。 */
import { onBeforeUnmount, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import { feedbackApi } from '@/api'

const props = defineProps({ name: { type: String, required: true }, size: { type: String, default: 'h-20 w-20' } })
const url = ref('')
const failed = ref(false)
const zoom = ref(false)

const load = async () => {
  if (url.value) URL.revokeObjectURL(url.value)
  url.value = ''
  failed.value = false
  try {
    const blob = await feedbackApi.image(props.name)
    url.value = URL.createObjectURL(blob)
  } catch {
    failed.value = true
  }
}
watch(() => props.name, load, { immediate: true })
onBeforeUnmount(() => url.value && URL.revokeObjectURL(url.value))
</script>

<template>
  <button type="button" class="relative shrink-0 overflow-hidden rounded-xl border border-ink-line bg-background" :class="size" :aria-label="`查看截图 ${name}`" @click="url && (zoom = true)">
    <img v-if="url" :src="url" alt="反馈截图" class="h-full w-full object-cover" />
    <span v-else class="flex h-full w-full items-center justify-center text-ink-mute">
      <Icon :icon="failed ? 'lucide:image-off' : 'lucide:loader-circle'" width="18" :class="!failed && 'animate-spin'" />
    </span>
  </button>
  <Teleport to="#overlay-root" defer>
    <div v-if="zoom" class="absolute inset-0 z-[90] flex items-center justify-center bg-scrim/80 p-4" role="dialog" aria-label="截图预览" @click="zoom = false">
      <img :src="url" alt="反馈截图" class="max-h-full max-w-full rounded-2xl object-contain shadow-2xl" />
      <button class="absolute right-4 top-[calc(var(--safe-top)+16px)] icon-btn" type="button" aria-label="关闭"><Icon icon="lucide:x" width="18" /></button>
    </div>
  </Teleport>
</template>
