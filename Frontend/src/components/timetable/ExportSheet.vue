<script setup>
import { computed, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import BottomSheet from '@/components/common/BottomSheet.vue'
import { isNativeApp } from '@/api/server'
import { useUiStore } from '@/stores/ui'
import { canvasToBlob, drawTimetable } from './timetableImage'

const props = defineProps({
  open: { type: Boolean, default: false },
  data: { type: Object, default: null },
  showOff: { type: Boolean, default: false },
})
const emit = defineEmits(['close'])
const ui = useUiStore()

const preview = ref('')
const blob = ref(null)
const busy = ref(false)
const withOff = ref(false)
const fileName = computed(() => `课表-${props.data?.semester || ''}-第${props.data?.week || ''}周.png`)
const canShare = computed(() => Boolean(blob.value && navigator.canShare?.({ files: [new File([blob.value], fileName.value, { type: 'image/png' })] })))

const render = async () => {
  if (!props.data) return
  busy.value = true
  try {
    // 等字体就绪再画，避免首帧用回退字体
    await document.fonts?.ready
    const canvas = drawTimetable(props.data, { showOff: withOff.value, title: `第 ${props.data.week} 周课表` })
    blob.value = await canvasToBlob(canvas)
    if (preview.value) URL.revokeObjectURL(preview.value)
    preview.value = URL.createObjectURL(blob.value)
  } catch (error) {
    ui.fail(error, '图片生成失败')
  } finally {
    busy.value = false
  }
}

watch(
  () => props.open,
  (open) => {
    if (open) {
      withOff.value = props.showOff
      render()
    }
  },
)
watch(withOff, () => props.open && render())

const download = () => {
  if (!blob.value) return
  const link = document.createElement('a')
  link.href = preview.value
  link.download = fileName.value
  document.body.appendChild(link)
  link.click()
  link.remove()
  ui.success(isNativeApp() ? '如未弹出保存，请长按图片保存或使用“分享”' : '图片已开始下载')
}

const share = async () => {
  try {
    await navigator.share({ files: [new File([blob.value], fileName.value, { type: 'image/png' })], title: '我的课表' })
  } catch (error) {
    if (error?.name !== 'AbortError') ui.fail(error, '分享失败')
  }
}
</script>

<template>
  <BottomSheet :open="open" title="导出课表图片" :subtitle="data ? `${data.semester} · 第 ${data.week} 周` : ''" @close="emit('close')">
    <label class="mb-3 flex cursor-pointer items-center gap-2 text-xs font-semibold text-ink-soft">
      <input v-model="withOff" type="checkbox" class="accent-primary" />同时画出非本周课程（虚线）
    </label>
    <div class="overflow-hidden rounded-2xl bg-background">
      <div v-if="busy && !preview" class="skeleton h-80" />
      <img v-else-if="preview" :src="preview" alt="课表图片预览" class="block w-full" />
    </div>
    <p class="mt-2 text-[11px] text-ink-mute">图片按当前所选周生成，长按或右键也可直接保存。</p>
    <template #footer>
      <div class="grid gap-3" :class="canShare ? 'grid-cols-2' : 'grid-cols-1'">
        <button v-if="canShare" class="btn-ghost" type="button" @click="share"><Icon icon="lucide:share-2" width="16" />分享</button>
        <button class="btn-primary" type="button" :disabled="!blob || busy" @click="download"><Icon icon="lucide:image-down" width="16" />保存 PNG</button>
      </div>
    </template>
  </BottomSheet>
</template>
