<script setup>
/**
 * 麦克风按钮：点一下开始听写（zh-CN），识别中的文字实时写进绑定的输入框，再点一下停止。
 * 当前环境不支持语音识别时整个按钮不渲染。用法：<MicButton v-model="text" />
 */
import { Icon } from '@iconify/vue'
import { speechSupport, useSpeech } from '@/composables/useSpeech'
import { mergeTranscript } from '@/utils/speech'

const props = defineProps({
  modelValue: { type: String, default: '' },
  // 输入框的最大长度，识别结果超出时截断
  maxlength: { type: Number, default: 2000 },
  disabled: { type: Boolean, default: false },
  size: { type: String, default: 'md' }, // md：44px，sm：36px
})
const emit = defineEmits(['update:modelValue', 'end'])

const { listening, toggle } = useSpeech({
  onText: (base, spoken) => emit('update:modelValue', mergeTranscript(base, spoken).slice(0, props.maxlength)),
  onEnd: () => emit('end'),
})
</script>

<template>
  <button
    v-if="speechSupport"
    type="button"
    class="relative flex shrink-0 items-center justify-center rounded-2xl transition active:scale-95 disabled:opacity-40"
    :class="[size === 'sm' ? 'h-9 w-9' : 'h-11 w-11', listening ? 'bg-danger text-on-danger shadow-lift' : 'bg-background text-ink-soft hover:bg-ink-line/60']"
    :aria-label="listening ? '停止语音输入' : '语音输入'"
    :title="listening ? '正在听…再点一次停止' : '语音输入（普通话）'"
    :aria-pressed="listening"
    :disabled="disabled"
    @click="toggle(modelValue)"
  >
    <span v-if="listening" class="absolute inset-0 animate-ping rounded-2xl bg-danger/30" aria-hidden="true" />
    <Icon :icon="listening ? 'lucide:mic-off' : 'lucide:mic'" :width="size === 'sm' ? 16 : 18" class="relative" />
  </button>
</template>
