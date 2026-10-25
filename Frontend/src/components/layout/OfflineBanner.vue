<script setup>
import { ref } from 'vue'
import { Icon } from '@iconify/vue'
import { network, retryConnection } from '@/api/request'
import { useUiStore } from '@/stores/ui'

const ui = useUiStore()
const busy = ref(false)

const retry = async () => {
  busy.value = true
  const ok = await retryConnection()
  busy.value = false
  if (ok) ui.success('已重新连上服务器')
  else ui.toast('仍然连不上服务器', 'warning')
}
</script>

<template>
  <!-- 全局离线横幅：连不上服务器时出现，恢复后自动消失 -->
  <Transition enter-active-class="transition duration-200" enter-from-class="-translate-y-full opacity-0" leave-active-class="transition duration-150" leave-to-class="-translate-y-full opacity-0">
    <div
      v-if="network.offline"
      class="relative z-50 flex shrink-0 items-center gap-2 bg-flame-light px-4 pb-2 pt-[calc(var(--safe-top)+8px)] text-xs font-bold text-flame lg:pt-2"
      role="status"
      aria-live="polite"
    >
      <Icon icon="lucide:wifi-off" width="16" class="shrink-0" />
      <span class="min-w-0 flex-1 truncate">{{ network.cached ? '网络已断开，正在显示离线数据' : '网络已断开，部分内容暂时无法加载' }}</span>
      <button class="shrink-0 rounded-full bg-surface px-2.5 py-1 text-[11px] text-flame shadow-soft disabled:opacity-60" type="button" :disabled="busy" @click="retry">
        {{ busy ? '连接中…' : '重试' }}
      </button>
    </div>
  </Transition>
</template>
