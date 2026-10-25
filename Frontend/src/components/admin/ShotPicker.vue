<script setup>
/**
 * 反馈截图选择（最多 3 张）。v-model 是 File 数组；大图在本地先压缩（最长边 1600、JPEG），
 * 提交时由父组件调用 feedbackApi.uploadImage 上传。服务器还会再校验与重新编码。
 */
import { onBeforeUnmount, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import { useUiStore } from '@/stores/ui'

const MAX = 3
const MAX_BYTES = 3 * 1024 * 1024
const MAX_SIDE = 1600

const files = defineModel({ type: Array, default: () => [] })
const ui = useUiStore()
const input = ref(null)
const previews = ref([])

watch(files, (list) => {
  previews.value.forEach((p) => URL.revokeObjectURL(p))
  previews.value = list.map((f) => URL.createObjectURL(f))
}, { immediate: true })
onBeforeUnmount(() => previews.value.forEach((p) => URL.revokeObjectURL(p)))

/** 超过 3MB 或尺寸过大时用 canvas 缩小并转成 JPEG。 */
const shrink = async (file) => {
  const bitmap = await createImageBitmap(file).catch(() => null)
  if (!bitmap) return null
  if (file.size <= MAX_BYTES && Math.max(bitmap.width, bitmap.height) <= MAX_SIDE) return file
  const scale = Math.min(1, MAX_SIDE / Math.max(bitmap.width, bitmap.height))
  const canvas = document.createElement('canvas')
  canvas.width = Math.round(bitmap.width * scale)
  canvas.height = Math.round(bitmap.height * scale)
  canvas.getContext('2d').drawImage(bitmap, 0, 0, canvas.width, canvas.height)
  const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.85))
  return blob ? new File([blob], file.name.replace(/\.\w+$/, '') + '.jpg', { type: 'image/jpeg' }) : null
}

const pick = async (event) => {
  const chosen = [...(event.target.files || [])]
  event.target.value = ''
  const room = MAX - files.value.length
  if (chosen.length > room) ui.toast(`最多 ${MAX} 张截图`, 'warning')
  const next = [...files.value]
  for (const file of chosen.slice(0, room)) {
    if (!/^image\/(png|jpe?g|webp)$/.test(file.type)) {
      ui.toast('只支持 png / jpg / webp 图片', 'warning')
      continue
    }
    const ready = await shrink(file)
    if (!ready || ready.size > MAX_BYTES) ui.toast('图片无法读取或过大', 'warning')
    else next.push(ready)
  }
  files.value = next
}
const remove = (i) => (files.value = files.value.filter((_, j) => j !== i))
</script>

<template>
  <div>
    <p class="label">截图（选填，最多 {{ MAX }} 张）</p>
    <div class="flex flex-wrap gap-2">
      <div v-for="(src, i) in previews" :key="src" class="relative h-20 w-20 overflow-hidden rounded-xl border border-ink-line">
        <img :src="src" alt="待上传的截图" class="h-full w-full object-cover" />
        <button class="absolute right-1 top-1 flex h-6 w-6 items-center justify-center rounded-full bg-scrim/60 text-white" type="button" aria-label="移除截图" @click="remove(i)">
          <Icon icon="lucide:x" width="13" />
        </button>
      </div>
      <button v-if="files.length < MAX" class="flex h-20 w-20 flex-col items-center justify-center gap-1 rounded-xl border-2 border-dashed border-ink-line text-ink-mute" type="button" @click="input?.click()">
        <Icon icon="lucide:image-plus" width="20" />
        <span class="text-[10px] font-bold">添加截图</span>
      </button>
    </div>
    <input ref="input" class="hidden" type="file" accept="image/png,image/jpeg,image/webp" multiple @change="pick" />
  </div>
</template>
