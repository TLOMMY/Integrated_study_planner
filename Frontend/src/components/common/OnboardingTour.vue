<script setup>
/**
 * 新手教程：分步高亮页面上的入口（data-tour="..."），可上一步 / 下一步 / 跳过。
 * 电脑与手机的入口位置不同，见 utils/tour.js 的 desktop / mobile；找不到目标时气泡居中。
 * 首次登录（含注册后）进入主界面时自动弹出；演示账号不自动弹出。
 */
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import { useAuthStore } from '@/stores/auth'
import { useDesktop } from '@/composables/useDesktop'
import { finishTour, locallyDone, startTour, tour } from '@/composables/useOnboarding'
import { TOUR_STEPS, placeCard, shouldAutoStart, spotlight, targetFor } from '@/utils/tour'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const desktop = useDesktop()

const card = ref(null)
const nextBtn = ref(null)
const rect = ref(null)
const box = ref({ width: 390, height: 844 })
const cardSize = ref({ width: 320, height: 200 })
const locating = ref(false)
let poll = null
let token = 0

const step = computed(() => TOUR_STEPS[tour.step] || TOUR_STEPS[0])
const isLast = computed(() => tour.step === TOUR_STEPS.length - 1)
const hole = computed(() => spotlight(rect.value, box.value))
const position = computed(() => placeCard(rect.value, box.value, cardSize.value))

// ---------------------------------------------------------------- 自动弹出
const MAIN_ROUTES = new Set(['home', 'timetable', 'ai', 'view', 'statistics', 'profile', 'plans', 'settings'])
watch(
  () => [auth.user?.id, auth.user?.onboarded, route.name],
  () => {
    const user = auth.user
    if (!user || tour.open || tour.startedFor === user.id || !MAIN_ROUTES.has(route.name)) return
    if (!shouldAutoStart(user, locallyDone(user.id))) return
    tour.startedFor = user.id
    // 等首页数据和奖励弹层先出来
    setTimeout(() => auth.user?.id === user.id && !tour.open && startTour(), 700)
  },
  { immediate: true },
)
// 退出登录时关掉
watch(() => auth.isLoggedIn, (on) => !on && (tour.open = false))

// ---------------------------------------------------------------- 定位
const container = () => document.querySelector('.phone') || document.body

const measure = () => {
  const root = container().getBoundingClientRect()
  box.value = { width: root.width, height: root.height }
  if (card.value) cardSize.value = { width: card.value.offsetWidth, height: card.value.offsetHeight }
  const name = targetFor(step.value, desktop.value)
  const el = name && [...document.querySelectorAll(`[data-tour="${name}"]`)].find((node) => node.getClientRects().length && node.offsetWidth)
  if (!el) return (rect.value = null)
  const r = el.getBoundingClientRect()
  rect.value = { top: r.top - root.top, left: r.left - root.left, width: r.width, height: r.height }
  return el
}

const locate = async () => {
  const current = ++token
  rect.value = null
  const routeTo = (desktop.value ? step.value.desktopRoute : step.value.mobileRoute) || step.value.route
  if (routeTo && route.path !== routeTo) await router.push(routeTo).catch(() => {})
  await nextTick()
  const name = targetFor(step.value, desktop.value)
  if (!name) return measure()
  locating.value = true
  // 页面切换、数据加载需要一点时间：最多等 2 秒
  const started = Date.now()
  while (current === token && Date.now() - started < 2000) {
    const el = measure()
    if (el) {
      el.scrollIntoView({ block: 'nearest', inline: 'nearest' })
      await new Promise((r) => setTimeout(r, 60))
      measure()
      break
    }
    await new Promise((r) => setTimeout(r, 80))
  }
  if (current === token) locating.value = false
}

watch(
  () => [tour.open, tour.step, desktop.value],
  async ([open]) => {
    clearInterval(poll)
    if (!open) return
    await locate()
    await nextTick()
    measure()
    nextBtn.value?.focus({ preventScroll: true })
    // 布局变化（侧栏收起、数据加载、滚动）时跟着走
    poll = setInterval(measure, 400)
  },
)
const onResize = () => tour.open && measure()
window.addEventListener('resize', onResize)
onBeforeUnmount(() => {
  clearInterval(poll)
  window.removeEventListener('resize', onResize)
})

// ---------------------------------------------------------------- 操作
const next = () => (isLast.value ? done() : tour.step++)
const prev = () => tour.step > 0 && tour.step--
const done = () => {
  token++
  clearInterval(poll)
  finishTour()
}
const openManual = () => {
  done()
  router.push({ name: 'manual' })
}
const onKey = (event) => {
  if (event.key === 'Escape') done()
  else if (event.key === 'ArrowRight') next()
  else if (event.key === 'ArrowLeft') prev()
  else return
  event.preventDefault()
}
</script>

<template>
  <Transition name="tour">
    <div v-if="tour.open" class="absolute inset-0 z-[85]" role="dialog" aria-modal="true" :aria-label="`新手教程：${step.title}`" @keydown="onKey">
      <!-- 遮罩：有目标时用超大阴影挖出高亮框，没有时整屏变暗 -->
      <div v-if="!hole" class="absolute inset-0 bg-scrim/55" />
      <div
        v-else
        class="tour-hole pointer-events-none absolute rounded-2xl ring-2 ring-primary transition-all duration-300"
        :style="{ top: `${hole.top}px`, left: `${hole.left}px`, width: `${hole.width}px`, height: `${hole.height}px` }"
      />
      <!-- 拦住其他点击，避免教程中误操作 -->
      <div class="absolute inset-0" />

      <section
        ref="card"
        class="absolute w-[min(340px,calc(100%-24px))] rounded-3xl bg-surface p-4 shadow-2xl transition-all duration-300"
        :style="{ top: `${position.top}px`, left: `${position.left}px` }"
        aria-live="polite"
      >
        <div class="flex items-center gap-2.5">
          <span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl bg-primary-light text-primary">
            <Icon :icon="locating ? 'lucide:loader-circle' : step.icon" width="18" :class="locating && 'animate-spin'" />
          </span>
          <p class="num flex-1 text-[11px] font-bold text-ink-mute">{{ tour.step + 1 }} / {{ TOUR_STEPS.length }}</p>
          <button class="rounded-full px-2.5 py-1 text-xs font-bold text-ink-mute hover:bg-background" type="button" @click="done">{{ isLast ? '关闭' : '跳过' }}</button>
        </div>
        <h2 class="mt-3 text-base font-black text-ink">{{ step.title }}</h2>
        <p class="mt-1.5 text-[13px] leading-6 text-ink-soft">{{ step.text }}</p>
        <div class="mt-3 flex items-center gap-1" aria-hidden="true">
          <span v-for="(s, i) in TOUR_STEPS" :key="s.key" class="h-1.5 rounded-full transition-all" :class="i === tour.step ? 'w-5 bg-primary' : i < tour.step ? 'w-1.5 bg-primary/50' : 'w-1.5 bg-ink-line'" />
        </div>
        <div class="mt-4 flex items-center gap-2">
          <button v-if="tour.step > 0" class="btn-ghost px-3 py-2.5 text-xs" type="button" @click="prev"><Icon icon="lucide:chevron-left" width="15" />上一步</button>
          <button v-if="isLast" class="btn-ghost px-3 py-2.5 text-xs" type="button" @click="openManual"><Icon icon="lucide:book-open-text" width="15" />使用手册</button>
          <button ref="nextBtn" class="btn-primary ml-auto px-4 py-2.5 text-xs" type="button" @click="next">
            {{ tour.step === 0 ? '开始' : isLast ? '开始使用' : '下一步' }}<Icon v-if="!isLast" icon="lucide:chevron-right" width="15" />
          </button>
        </div>
      </section>
    </div>
  </Transition>
</template>

<style scoped>
.tour-hole {
  box-shadow: 0 0 0 9999px rgb(var(--c-scrim) / 0.55);
}
.tour-enter-active,
.tour-leave-active {
  transition: opacity 0.2s ease;
}
.tour-enter-from,
.tour-leave-to {
  opacity: 0;
}
</style>
