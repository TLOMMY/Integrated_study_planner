<script setup>
/**
 * 使用手册：按功能分节，可搜索、有锚点（/manual#rule-engine 等），跳转时滚动到位并短暂高亮。
 */
import { computed, h, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import { RULE_TEMPLATES, SECTIONS } from '@/manual/content'
import { exampleChips, highlight, safeAnchor, searchManual } from '@/utils/manual'
import { startTour } from '@/composables/useOnboarding'
import { openShortcutsHelp } from '@/composables/useShortcuts'

const route = useRoute()
const router = useRouter()

const scroller = ref(null)
const header = ref(null)
const query = ref('')
const flashId = ref('')
const activeId = ref(SECTIONS[0].id)
let flashTimer = null

const results = computed(() => searchManual(SECTIONS, query.value))
const hitCount = computed(() => results.value.reduce((n, r) => n + r.blocks.length, 0))
const TRY_GROUPS = new Set(['dates', 'minutes', 'segments', 'subjects', 'intensity'])

// 关键词高亮（逐段渲染，不用 v-html）
const Hl = (props) => highlight(props.text, query.value).map((part) => (part.hit ? h('mark', { class: 'rounded bg-flame-light px-0.5 text-ink' }, part.text) : part.text))
Hl.props = ['text']

// ---------------------------------------------------------------- 锚点
const goTo = async (id, flash = true) => {
  await nextTick()
  let el = document.getElementById(id)
  // 被搜索过滤掉了：清空搜索再找
  if (!el && query.value) {
    query.value = ''
    await nextTick()
    el = document.getElementById(id)
  }
  const box = scroller.value
  if (!el || !box) return
  const offset = (header.value?.offsetHeight || 0) + 8
  box.scrollTo({ top: el.getBoundingClientRect().top - box.getBoundingClientRect().top + box.scrollTop - offset, behavior: 'smooth' })
  if (!flash) return
  flashId.value = id
  clearTimeout(flashTimer)
  flashTimer = setTimeout(() => (flashId.value = ''), 2400)
}

const jump = (id) => {
  if (route.hash === `#${id}`) goTo(id)
  else router.replace({ hash: `#${id}` })
}

watch(() => route.hash, (hash) => {
  const id = safeAnchor(hash)
  if (id) goTo(id)
})
onMounted(() => {
  const id = safeAnchor(route.hash)
  // 等页面进入动画和字体排版稳定后再滚动
  if (id) setTimeout(() => goTo(id), 120)
})
onBeforeUnmount(() => clearTimeout(flashTimer))

// 滚动时更新目录里的当前章节
const onScroll = () => {
  const box = scroller.value
  if (!box) return
  const line = box.getBoundingClientRect().top + (header.value?.offsetHeight || 0) + 24
  let current = results.value[0]?.section.id
  for (const { section } of results.value) {
    const el = document.getElementById(section.id)
    if (el && el.getBoundingClientRect().top <= line) current = section.id
  }
  activeId.value = current
}

// ---------------------------------------------------------------- 动作
const runAction = (link) => {
  if (link.action === 'tour') startTour()
  else if (link.action === 'shortcuts') openShortcutsHelp()
  else if (link.to) router.push(link.to)
}
const tryExample = (text) => router.push({ name: 'ai', query: { q: text } })
</script>

<template>
  <div ref="scroller" class="scrollbar-hide h-full overflow-y-auto pb-24 lg:pb-10" @scroll.passive="onScroll">
    <header ref="header" class="glass-bar sticky top-0 z-10 bg-background/90 px-4 pb-3 pt-[calc(var(--safe-top)+16px)] backdrop-blur lg:px-10 lg:pt-8">
      <div class="flex items-center gap-3 lg:mx-auto lg:max-w-5xl">
        <button class="icon-btn lg:hidden" type="button" aria-label="返回" @click="router.back()"><Icon icon="lucide:chevron-left" width="20" /></button>
        <h1 class="text-lg font-black text-ink lg:text-[22px]">使用手册</h1>
        <label class="ml-auto flex min-w-0 flex-1 items-center gap-2 rounded-2xl border border-ink-line/70 bg-surface px-3 shadow-soft focus-within:border-primary/40 lg:max-w-sm">
          <Icon icon="lucide:search" width="16" class="shrink-0 text-ink-mute" />
          <input v-model="query" class="min-w-0 flex-1 bg-transparent py-2.5 text-sm outline-none placeholder:text-ink-mute" type="search" placeholder="搜索：打卡、PDF、规则引擎…" maxlength="40" aria-label="搜索使用手册" />
          <button v-if="query" class="shrink-0 rounded-full p-1 text-ink-mute hover:bg-background" type="button" aria-label="清空搜索" @click="query = ''"><Icon icon="lucide:x" width="14" /></button>
        </label>
      </div>
      <!-- 手机：横向目录 -->
      <nav class="scrollbar-hide -mx-4 mt-3 flex gap-1.5 overflow-x-auto px-4 lg:hidden" aria-label="手册目录">
        <button v-for="r in results" :key="r.section.id" type="button" class="chip shrink-0" :class="activeId === r.section.id && 'chip-active'" @click="jump(r.section.id)">{{ r.section.title }}</button>
      </nav>
    </header>

    <div class="px-4 lg:mx-auto lg:grid lg:max-w-5xl lg:grid-cols-[200px_minmax(0,1fr)] lg:gap-8 lg:px-10">
      <!-- 电脑：左侧目录 -->
      <nav class="sticky top-[104px] hidden self-start lg:block" aria-label="手册目录">
        <a
          v-for="r in results"
          :key="r.section.id"
          :href="`#${r.section.id}`"
          class="flex items-center gap-2 rounded-xl px-3 py-2 text-sm font-bold transition"
          :class="activeId === r.section.id ? 'bg-primary-light text-primary' : 'text-ink-soft hover:bg-surface'"
          :aria-current="activeId === r.section.id ? 'true' : undefined"
          @click.prevent="jump(r.section.id)"
        >
          <Icon :icon="r.section.icon" width="16" class="shrink-0" /><span class="truncate">{{ r.section.title }}</span>
        </a>
      </nav>

      <main class="min-w-0 space-y-4 pt-1">
        <p v-if="query" class="px-1 text-xs font-semibold text-ink-mute" aria-live="polite">「{{ query }}」：{{ hitCount ? `${results.length} 节、${hitCount} 处` : '没有找到，换个关键词试试' }}</p>
        <section v-for="r in results" :id="r.section.id" :key="r.section.id" class="card scroll-mt-28 p-4 lg:p-5" :class="flashId === r.section.id && 'flash'">
          <h2 class="flex items-center gap-2.5">
            <span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl bg-primary-light text-primary"><Icon :icon="r.section.icon" width="18" /></span>
            <span class="min-w-0">
              <span class="block text-base font-black text-ink"><Hl :text="r.section.title" /></span>
              <span class="block text-[11px] text-ink-mute"><Hl :text="r.section.summary" /></span>
            </span>
          </h2>
          <div class="mt-3 space-y-3 text-sm leading-6 text-ink-soft">
            <template v-for="(b, bi) in r.blocks" :key="bi">
              <p v-if="b.type === 'p'"><Hl :text="b.text" /></p>
              <div v-else-if="b.type === 'list' || b.type === 'steps'" :id="b.id" class="scroll-mt-28 rounded-2xl" :class="flashId === b.id && 'flash'">
                <h3 v-if="b.title" class="mb-1 text-sm font-black text-ink"><Hl :text="b.title" /></h3>
                <component :is="b.type === 'steps' ? 'ol' : 'ul'" class="space-y-1 pl-5" :class="b.type === 'steps' ? 'list-decimal' : 'list-disc'">
                  <li v-for="(item, ii) in b.items" :key="ii" class="marker:text-ink-mute"><Hl :text="item" /></li>
                </component>
              </div>
              <div v-else-if="b.type === 'tip'" :id="b.id" class="scroll-mt-28 rounded-2xl bg-primary-light/60 px-3 py-2.5 text-[13px] text-ink" :class="flashId === b.id && 'flash'">
                <p v-if="b.title" class="mb-0.5 flex items-center gap-1 font-black text-primary"><Icon icon="lucide:info" width="14" /><Hl :text="b.title" /></p>
                <Hl :text="b.text" />
              </div>
              <div v-else-if="b.type === 'links'" class="flex flex-wrap gap-2">
                <button v-for="link in b.links" :key="link.label" class="chip" type="button" @click="runAction(link)"><Icon :icon="link.icon" width="13" />{{ link.label }}</button>
              </div>
              <div v-else-if="b.type === 'rules'" id="rule-templates" class="scroll-mt-28 space-y-4 rounded-2xl" :class="flashId === 'rule-templates' && 'flash'">
                <p class="flex items-center gap-1.5 text-[11px] font-semibold text-ink-mute"><Icon icon="lucide:calendar" width="13" />{{ b.refLabel }}；每个例句都有自动化测试保证能被这样解析</p>
                <div v-for="g in b.groups" :id="`rule-${g.id}`" :key="g.id" class="scroll-mt-28 rounded-2xl border border-ink-line/70 p-3" :class="[flashId === `rule-${g.id}` && 'flash', g.id === 'limits' && 'bg-flame-light/40']">
                  <h3 class="flex items-center gap-1.5 text-sm font-black text-ink">
                    <Icon :icon="g.id === 'limits' ? 'lucide:circle-alert' : 'lucide:hash'" width="14" :class="g.id === 'limits' ? 'text-flame' : 'text-primary'" /><Hl :text="g.title" />
                  </h3>
                  <ul class="mt-1.5 space-y-1 pl-5 text-[13px]">
                    <li v-for="(pt, pi) in g.patterns" :key="pi" class="list-disc marker:text-ink-mute"><Hl :text="pt" /></li>
                  </ul>
                  <p class="mt-2.5 text-[11px] font-black text-ink-mute">{{ g.id === 'limits' ? '这样写会怎样' : '例句' }}</p>
                  <ul class="mt-1 space-y-1.5">
                    <li v-for="ex in g.examples" :key="ex.text" class="rounded-xl bg-background px-3 py-2">
                      <div class="flex items-start gap-2">
                        <p class="min-w-0 flex-1 text-[13px] font-bold text-ink">“<Hl :text="ex.text" />”<span v-if="ex.courses" class="ml-1 text-[11px] font-semibold text-ink-mute">（课表里有：{{ ex.courses.join('、') }}）</span></p>
                        <button v-if="TRY_GROUPS.has(g.id)" class="shrink-0 rounded-lg px-2 py-0.5 text-[11px] font-bold text-primary hover:bg-primary-light" type="button" :aria-label="`在 AI 助手里试试：${ex.text}`" @click="tryExample(ex.text)">试一试</button>
                      </div>
                      <div class="mt-1 flex flex-wrap gap-1">
                        <span v-for="c in exampleChips(ex.expect, RULE_TEMPLATES.ref_date)" :key="c" class="rounded-md bg-surface px-1.5 py-0.5 text-[10px] font-semibold text-ink-soft">{{ c }}</span>
                      </div>
                    </li>
                  </ul>
                </div>
              </div>
            </template>
          </div>
        </section>
      </main>
    </div>
  </div>
</template>

<style scoped>
.flash {
  animation: manual-flash 2.4s ease-out;
}
@keyframes manual-flash {
  0%,
  35% {
    box-shadow: 0 0 0 3px rgb(var(--c-primary) / 0.55);
    background-color: rgb(var(--c-primary-light));
  }
  100% {
    box-shadow: 0 0 0 0 rgb(var(--c-primary) / 0);
  }
}
</style>
