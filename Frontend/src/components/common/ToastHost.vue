<script setup>
/**
 * 顶部提示条。文字最多显示 3 行；被截断时点一下展开全文，再点一下关闭。
 * 带帮助链接的提示（如 AI 额度用完、识别失败）显示"查看说明"，跳到使用手册对应位置。
 */
import { nextTick, onBeforeUpdate, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import { useUiStore } from '@/stores/ui'

const ui = useUiStore()
const router = useRouter()

const STYLE = {
  success: { icon: 'lucide:circle-check', cls: 'bg-inverse text-inverse-ink', iconCls: 'text-success' },
  error: { icon: 'lucide:circle-x', cls: 'bg-danger text-on-danger', iconCls: 'text-on-danger' },
  warning: { icon: 'lucide:triangle-alert', cls: 'bg-inverse text-inverse-ink', iconCls: 'text-flame' },
  info: { icon: 'lucide:info', cls: 'bg-inverse text-inverse-ink', iconCls: 'text-inverse-accent' },
  xp: { icon: 'lucide:sparkles', cls: 'bg-xp text-on-xp', iconCls: 'text-on-xp' },
}

// 记录每条提示的文字元素，判断是否被截断
const textEls = new Map()
onBeforeUpdate(() => textEls.clear())
const setText = (id) => (el) => el && textEls.set(id, el)
const clipped = ref(new Set())
const measure = async () => {
  await nextTick()
  const next = new Set()
  for (const [id, el] of textEls) if (el.scrollHeight > el.clientHeight + 1) next.add(id)
  clipped.value = next
}

const onClick = (toast) => {
  if (!toast.expanded && clipped.value.has(toast.id)) ui.expand(toast.id)
  else ui.dismiss(toast.id)
}
const openHelp = (toast) => {
  ui.dismiss(toast.id)
  router.push({ name: 'manual', hash: toast.help.hash }).catch(() => {})
}
</script>

<template>
  <div class="pointer-events-none absolute inset-x-0 top-0 z-[100] flex flex-col items-center gap-2 px-6 pt-[calc(var(--safe-top)+14px)]" aria-live="polite">
    <TransitionGroup enter-active-class="transition duration-200" enter-from-class="-translate-y-3 opacity-0" leave-active-class="transition duration-150" leave-to-class="opacity-0" @after-enter="measure">
      <div
        v-for="toast in ui.toasts"
        :key="toast.id"
        class="pointer-events-auto flex max-w-full items-start gap-2 rounded-2xl px-4 py-2.5 text-sm font-semibold shadow-xl lg:max-w-[560px]"
        :class="STYLE[toast.type]?.cls"
        role="status"
        @click="onClick(toast)"
      >
        <Icon :icon="STYLE[toast.type]?.icon" width="18" :class="STYLE[toast.type]?.iconCls" class="mt-px shrink-0" />
        <span class="min-w-0 flex-1">
          <span :ref="setText(toast.id)" class="block break-words leading-5" :class="!toast.expanded && 'line-clamp-3'">{{ toast.message }}</span>
          <span v-if="(clipped.has(toast.id) && !toast.expanded) || toast.help" class="mt-1 flex items-center gap-3 text-xs font-bold opacity-80">
            <span v-if="clipped.has(toast.id) && !toast.expanded">点击查看全文</span>
            <button v-if="toast.help" type="button" class="inline-flex items-center gap-0.5 underline underline-offset-2" @click.stop="openHelp(toast)">
              {{ toast.help.label }}<Icon icon="lucide:chevron-right" width="12" />
            </button>
          </span>
        </span>
      </div>
    </TransitionGroup>
  </div>
</template>
