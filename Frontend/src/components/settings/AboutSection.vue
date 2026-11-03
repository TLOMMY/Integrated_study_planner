<script setup>
/** 设置 →「关于」：版本、用户协议 / 隐私政策、联系邮箱、备案号（为空不显示）。 */
import { computed, onMounted, ref } from 'vue'
import { Icon } from '@iconify/vue'
import BeianFooter from '@/components/common/BeianFooter.vue'
import { siteApi } from '@/api/site'
import { DEFAULT_SITE, beianLinks, loadSiteInfo } from '@/utils/site'

const info = ref({ ...DEFAULT_SITE })
onMounted(async () => {
  info.value = await loadSiteInfo(siteApi.info)
})
const hasBeian = computed(() => beianLinks(info.value).length > 0)
</script>

<template>
  <h2 class="mb-2 mt-5 px-1 text-xs font-black text-ink-mute">关于</h2>
  <div class="card divide-y divide-ink-line/60 overflow-hidden">
    <div class="flex items-center gap-3 px-4 py-3.5">
      <Icon icon="lucide:info" width="20" class="text-primary" />
      <span class="flex-1 text-sm font-semibold text-ink">{{ info.app_name }}</span>
      <span class="num text-xs font-bold text-ink-mute">{{ info.version ? `v${info.version}` : '' }}</span>
    </div>
    <RouterLink class="flex items-center gap-3 px-4 py-3.5" :to="{ name: 'terms' }">
      <Icon icon="lucide:scale" width="20" class="text-ink-soft" />
      <span class="flex-1 text-sm font-semibold text-ink">用户协议</span>
      <Icon icon="lucide:chevron-right" width="16" class="text-ink-mute" />
    </RouterLink>
    <RouterLink class="flex items-center gap-3 px-4 py-3.5" :to="{ name: 'privacy' }">
      <Icon icon="lucide:shield-check" width="20" class="text-success" />
      <span class="flex-1">
        <span class="block text-sm font-semibold text-ink">隐私政策</span>
        <span class="block text-[11px] text-ink-mute">收集哪些数据、AI 内容发给谁、如何导出与注销</span>
      </span>
      <Icon icon="lucide:chevron-right" width="16" class="text-ink-mute" />
    </RouterLink>
    <a v-if="info.contact_email" class="flex items-center gap-3 px-4 py-3.5" :href="`mailto:${info.contact_email}`">
      <Icon icon="lucide:mail" width="20" class="text-xp" />
      <span class="flex-1 text-sm font-semibold text-ink">联系我们</span>
      <span class="max-w-[55%] truncate text-xs font-bold text-ink-mute">{{ info.contact_email }}</span>
    </a>
    <div v-if="hasBeian" class="px-4 py-3">
      <BeianFooter :info="info" />
    </div>
  </div>
</template>
