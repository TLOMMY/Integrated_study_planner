<script setup>
import { computed, ref, watch } from 'vue'
import dayjs from 'dayjs'
import { Icon } from '@iconify/vue'
import BottomSheet from '@/components/common/BottomSheet.vue'
import { shareApi } from '@/api/growth'
import { useUiStore } from '@/stores/ui'

const props = defineProps({ open: { type: Boolean, default: false } })
const emit = defineEmits(['close', 'import'])
const ui = useUiStore()

const share = ref(null)
const busy = ref(false)
const error = ref('')
const pretty = computed(() => (share.value ? `${share.value.code.slice(0, 4)} ${share.value.code.slice(4)}` : ''))

const generate = async () => {
  busy.value = true
  error.value = ''
  try {
    share.value = await shareApi.create()
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

watch(
  () => props.open,
  (open) => open && !share.value && generate(),
)

const copy = async (text, message) => {
  try {
    await navigator.clipboard.writeText(text)
  } catch {
    // 旧浏览器 / 非安全上下文的回退
    const area = document.createElement('textarea')
    area.value = text
    document.body.appendChild(area)
    area.select()
    document.execCommand('copy')
    area.remove()
  }
  ui.success(message)
}
const copyText = () =>
  copy(`我在「学业管家」分享了课表（${share.value.semester}，${share.value.course_count} 门课），打开课表页 → 用分享码导入，输入：${share.value.code}（${dayjs(share.value.expires_at).format('M月D日')}前有效）`, '分享文字已复制')
</script>

<template>
  <BottomSheet :open="open" title="分享课表" subtitle="同学输入分享码即可导入你本学期的课程" @close="emit('close')">
    <div v-if="busy" class="skeleton h-44" />
    <div v-else-if="error" class="rounded-3xl bg-danger-light p-4 text-sm font-semibold text-danger">{{ error }}</div>
    <div v-else-if="share" class="space-y-3">
      <div class="rounded-3xl bg-primary-light p-5 text-center">
        <p class="text-xs font-bold text-primary">分享码</p>
        <p class="num mt-2 select-all text-[40px] font-black tracking-[0.18em] text-ink" aria-live="polite">{{ pretty }}</p>
        <p class="mt-2 text-xs text-ink-soft">{{ share.semester }} · {{ share.course_count }} 门课 · {{ dayjs(share.expires_at).format('M月D日 HH:mm') }} 前有效</p>
      </div>
      <div class="grid grid-cols-2 gap-3">
        <button class="btn-primary" type="button" @click="copy(share.code, '分享码已复制')"><Icon icon="lucide:copy" width="16" />复制分享码</button>
        <button class="btn-ghost" type="button" @click="copyText"><Icon icon="lucide:share-2" width="16" />复制分享文字</button>
      </div>
      <p class="text-[11px] leading-5 text-ink-mute">分享的是生成这一刻的课表快照，之后改课不会同步；需要时可重新生成。分享码不含你的任务、专注等其他数据。</p>
      <button class="w-full text-center text-xs font-bold text-primary" type="button" @click="generate"><Icon icon="lucide:refresh-cw" width="12" class="mr-1 inline" />重新生成</button>
    </div>
    <template #footer>
      <button class="btn-ghost w-full" type="button" @click="emit('import')"><Icon icon="lucide:clipboard-paste" width="16" />我有同学的分享码，去导入</button>
    </template>
  </BottomSheet>
</template>
