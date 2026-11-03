<script setup>
/**
 * 备案号（ICP 备案 → 工信部，公安备案 → 公安部）。号码为空时整块不显示。
 * 传入 info（/site/info 的结果）；不传时自己读取。
 */
import { computed, onMounted, ref } from 'vue'
import { siteApi } from '@/api/site'
import { beianLinks, loadSiteInfo } from '@/utils/site'

const props = defineProps({ info: { type: Object, default: null } })
const loaded = ref(null)
onMounted(async () => {
  if (!props.info) loaded.value = await loadSiteInfo(siteApi.info)
})
const links = computed(() => beianLinks(props.info || loaded.value))
</script>

<template>
  <p v-if="links.length" class="flex flex-wrap items-center justify-center gap-x-3 gap-y-1 text-[11px] text-ink-mute">
    <a v-for="l in links" :key="l.key" class="hover:text-primary hover:underline" :href="l.url" target="_blank" rel="noopener noreferrer">{{ l.text }}</a>
  </p>
</template>
