<script setup>
/**
 * 极简 Markdown 渲染：标题、无序/有序列表、加粗、行内代码。
 * 全部走文本插值而不是 v-html，模型输出里即使有 <script> 也只会被当作文字显示。
 */
import { computed } from 'vue'

const props = defineProps({ text: { type: String, default: '' } })

const inline = (line) =>
  line
    .split(/(\*\*[^*]+\*\*|`[^`]+`)/g)
    .filter(Boolean)
    .map((part) => {
      if (part.startsWith('**') && part.endsWith('**')) return { type: 'bold', text: part.slice(2, -2) }
      if (part.startsWith('`') && part.endsWith('`')) return { type: 'code', text: part.slice(1, -1) }
      return { type: 'text', text: part }
    })

const blocks = computed(() =>
  props.text
    .replace(/\r/g, '')
    .split('\n')
    .map((raw) => raw.trim())
    .filter(Boolean)
    .map((line) => {
      let match = line.match(/^#{1,4}\s+(.*)$/)
      if (match) return { type: 'heading', parts: inline(match[1]) }
      match = line.match(/^(?:[-*•]|\d+[.)、])\s+(.*)$/)
      if (match) return { type: 'item', parts: inline(match[1]) }
      return { type: 'para', parts: inline(line) }
    }),
)
</script>

<template>
  <div class="space-y-1.5 text-sm leading-6 text-ink">
    <template v-for="(block, i) in blocks" :key="i">
      <p v-if="block.type === 'heading'" class="pt-1 font-black">
        <template v-for="(p, j) in block.parts" :key="j">{{ p.text }}</template>
      </p>
      <p v-else :class="block.type === 'item' && 'relative pl-4'">
        <span v-if="block.type === 'item'" class="absolute left-0 top-[10px] h-1.5 w-1.5 rounded-full bg-primary" />
        <template v-for="(p, j) in block.parts" :key="j">
          <b v-if="p.type === 'bold'" class="font-black">{{ p.text }}</b>
          <code v-else-if="p.type === 'code'" class="rounded bg-background px-1 text-[12px] text-primary">{{ p.text }}</code>
          <template v-else>{{ p.text }}</template>
        </template>
      </p>
    </template>
  </div>
</template>
