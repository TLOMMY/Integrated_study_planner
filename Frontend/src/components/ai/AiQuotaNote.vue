<script setup>
/**
 * 服务器 AI 额度提示（只在使用服务器 DeepSeek Key 且有上限时显示）。
 * compact：AI 页头部的一小段文字；否则为设置里的说明卡片。
 */
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { formatTokens, quotaText } from '@/utils/site'

const props = defineProps({ quota: { type: Object, default: null }, compact: { type: Boolean, default: false } })
const tip = computed(() => quotaText(props.quota))
</script>

<template>
  <template v-if="tip">
    <span v-if="compact" class="shrink-0 font-bold" :class="tip.exceeded ? 'text-danger' : 'text-ink-mute'">· {{ tip.text }}</span>
    <div v-else class="rounded-2xl px-4 py-2.5 text-xs leading-5" :class="tip.exceeded ? 'bg-danger-light text-danger' : 'bg-background text-ink-soft'">
      <p class="flex items-center gap-1.5 font-bold">
        <Icon :icon="tip.exceeded ? 'lucide:circle-alert' : 'lucide:gauge'" width="14" />{{ tip.text }}
        <span v-if="quota.calls_limit" class="num font-semibold opacity-80">（每天 {{ quota.calls_limit }} 次<template v-if="quota.tokens_limit"> · {{ formatTokens(quota.tokens_limit) }} tokens</template>）</span>
      </p>
      <p class="mt-0.5 text-[11px] opacity-80">
        额度只限制服务器提供的 DeepSeek，每天 0 点恢复；添加自己的模型 Key 或使用本地规则引擎不受限制。
        <RouterLink :to="{ name: 'manual', hash: '#rule-templates' }" class="inline-flex translate-y-0.5 items-center text-primary" aria-label="本地规则引擎能听懂哪些写法" title="本地规则引擎能听懂哪些写法"><Icon icon="lucide:circle-help" width="13" /></RouterLink>
      </p>
    </div>
  </template>
</template>
