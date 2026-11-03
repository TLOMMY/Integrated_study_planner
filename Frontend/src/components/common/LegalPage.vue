<script setup>
/** 隐私政策 / 用户协议的公共版式（公开页面，未登录也能看）。 */
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import BeianFooter from '@/components/common/BeianFooter.vue'
import { siteApi } from '@/api/site'
import { fillLegal } from '@/utils/legal'
import { DEFAULT_SITE, loadSiteInfo } from '@/utils/site'

const props = defineProps({
  doc: { type: Object, required: true },
  icon: { type: String, default: 'lucide:file-text' },
  other: { type: Object, required: true },
})

const router = useRouter()
const info = ref({ ...DEFAULT_SITE })
onMounted(async () => {
  info.value = await loadSiteInfo(siteApi.info)
})
const fill = (text) => fillLegal(text, info.value)
const back = () => (window.history.length > 1 ? router.back() : router.replace({ name: 'login' }))
const version = computed(() => info.value.terms_version || '')
// 页面在内部滚动容器里，锚点用 scrollIntoView（不经过路由）
const jump = (id) => document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
</script>

<template>
  <div class="scrollbar-hide h-full overflow-y-auto bg-background">
    <header class="glass-bar sticky top-0 z-10 flex items-center gap-3 bg-background/90 px-4 pb-3 pt-[calc(var(--safe-top)+16px)] backdrop-blur lg:px-10 lg:pt-6">
      <button class="icon-btn" type="button" aria-label="返回" @click="back"><Icon icon="lucide:chevron-left" width="20" /></button>
      <h1 class="flex-1 text-lg font-black text-ink lg:text-[22px]">{{ doc.title }}</h1>
      <RouterLink class="text-xs font-bold text-primary" :to="other.to">{{ other.label }}</RouterLink>
    </header>

    <article class="mx-4 mb-10 mt-2 rounded-[28px] bg-surface p-5 shadow-soft lg:mx-auto lg:max-w-3xl lg:p-10">
      <div class="flex items-center gap-3">
        <span class="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-primary-light text-primary"><Icon :icon="icon" width="22" /></span>
        <div>
          <p class="text-base font-black text-ink">学业管家 · {{ doc.title }}</p>
          <p class="num text-[11px] text-ink-mute">版本 {{ version || '—' }}<template v-if="version"> · 自该日起生效</template></p>
        </div>
      </div>

      <div class="mt-4 space-y-2 text-sm leading-7 text-ink-soft">
        <p v-for="(p, i) in doc.intro" :key="i">{{ fill(p) }}</p>
      </div>

      <nav class="mt-4 flex flex-wrap gap-2" aria-label="目录">
        <a v-for="s in doc.sections" :key="s.id" class="chip" :href="`#${s.id}`" @click.prevent="jump(s.id)">{{ s.title.replace(/^[一二三四五六七八九十]+、/, '') }}</a>
      </nav>

      <section v-for="s in doc.sections" :id="s.id" :key="s.id" class="mt-6 scroll-mt-24">
        <h2 class="text-[15px] font-black text-ink">{{ s.title }}</h2>
        <ul class="mt-2 list-disc space-y-1.5 pl-5 text-sm leading-7 text-ink-soft marker:text-primary">
          <li v-for="(item, i) in s.items" :key="i">{{ fill(item) }}</li>
        </ul>
      </section>

      <p class="mt-8 rounded-2xl bg-background px-4 py-3 text-xs leading-6 text-ink-mute">
        联系邮箱：<a v-if="info.contact_email" class="font-bold text-primary" :href="`mailto:${info.contact_email}`">{{ info.contact_email }}</a><span v-else>待公布</span>
        · 也可以在登录后通过「设置 → 问题反馈」联系我们。
      </p>
      <BeianFooter class="mt-4" :info="info" />
    </article>
  </div>
</template>
