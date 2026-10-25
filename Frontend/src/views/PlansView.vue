<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import EmptyState from '@/components/common/EmptyState.vue'
import PlanDetail from '@/components/plan/PlanDetail.vue'
import PlanEditor from '@/components/plan/PlanEditor.vue'
import { usePlansStore } from '@/stores/plans'
import { useUiStore } from '@/stores/ui'

const router = useRouter()
const plans = usePlansStore()
const ui = useUiStore()

const detailId = ref(null)
const editor = ref({ open: false, plan: null })
const FILTERS = [
  { key: 'active', label: '进行中', hint: '' },
  { key: 'completed', label: '已完成', hint: '任务全部做完（或手动标记完成）的计划，保留进度与专注记录，可随时恢复为进行中。' },
  { key: 'archived', label: '已归档', hint: '暂时搁置、不想出现在进行中的计划：任务和记录都保留，不要求做完。在计划详情里点「归档」图标即可。' },
  { key: 'all', label: '全部', hint: '' },
  { key: 'trash', label: '回收站', hint: '删除的计划先放在这里，其中的任务也会一起隐藏；30 天后自动彻底删除。' },
]
const hint = computed(() => FILTERS.find((f) => f.key === plans.filter)?.hint)
const inTrash = computed(() => plans.filter === 'trash')

// 回收站多选
const picked = ref(new Set())
const allPicked = computed(() => plans.items.length > 0 && plans.items.every((p) => picked.value.has(p.id)))
const pick = (plan) => {
  const next = new Set(picked.value)
  next.has(plan.id) ? next.delete(plan.id) : next.add(plan.id)
  picked.value = next
}
const pickAll = () => (picked.value = allPicked.value ? new Set() : new Set(plans.items.map((p) => p.id)))
const act = async (fn) => {
  try {
    if ((await fn()) !== false) picked.value = new Set()
  } catch (error) {
    ui.fail(error)
  }
}
const restore = () => act(() => plans.restore([...picked.value]))
const purge = () => act(() => plans.purge([...picked.value]))
const emptyTrash = () => act(() => plans.emptyTrash())

const load = (filter) => {
  picked.value = new Set()
  return plans.load(filter).catch((error) => ui.fail(error))
}
const openPlan = (plan) => (inTrash.value ? pick(plan) : (detailId.value = plan.id))
const editPlan = (plan) => {
  detailId.value = null
  editor.value = { open: true, plan }
}
onMounted(() => load())
</script>

<template>
  <div class="flex h-full flex-col">
    <header class="glass-bar flex shrink-0 items-center gap-3 bg-surface px-4 pb-3 pt-[calc(var(--safe-top)+16px)] lg:px-10 lg:pt-6">
      <button class="icon-btn lg:hidden" type="button" aria-label="返回" @click="router.back()"><Icon icon="lucide:chevron-left" width="20" /></button>
      <h1 class="flex-1 text-lg font-black text-ink lg:text-[22px]">学习计划</h1>
      <button class="icon-btn bg-primary text-on-primary" type="button" aria-label="新建计划" @click="editor = { open: true, plan: null }"><Icon icon="lucide:plus" width="20" /></button>
    </header>

    <nav class="scrollbar-hide flex shrink-0 gap-2 overflow-x-auto bg-surface px-4 pb-3 lg:border-b lg:border-ink-line/70 lg:px-10">
      <button v-for="f in FILTERS" :key="f.key" class="chip shrink-0" :class="plans.filter === f.key && 'chip-active'" type="button" @click="load(f.key)">
        <Icon v-if="f.key === 'trash'" icon="lucide:trash-2" width="13" />{{ f.label }}<span v-if="f.key !== 'all' && plans.counts[f.key]" class="num">{{ plans.counts[f.key] }}</span>
      </button>
    </nav>
    <div v-if="hint || inTrash" class="shrink-0 bg-surface px-4 pb-3 lg:px-10">
      <p v-if="hint" class="flex items-start gap-1.5 rounded-2xl bg-background px-3 py-2 text-[11px] leading-5 text-ink-soft"><Icon icon="lucide:info" width="13" class="mt-0.5 shrink-0 text-primary" />{{ hint }}</p>
      <div v-if="inTrash && plans.items.length" class="mt-2 flex items-center gap-2">
        <button class="chip" type="button" @click="pickAll"><Icon :icon="allPicked ? 'lucide:square-check' : 'lucide:square'" width="14" />全选</button>
        <span class="num flex-1 text-xs text-ink-mute">已选 {{ picked.size }} 项</span>
        <button class="chip" type="button" :disabled="!picked.size" :class="!picked.size && 'opacity-40'" @click="restore"><Icon icon="lucide:rotate-ccw" width="14" />恢复</button>
        <button class="chip border-danger/40 text-danger" type="button" :disabled="!picked.size" :class="!picked.size && 'opacity-40'" @click="purge"><Icon icon="lucide:trash-2" width="14" />彻底删除</button>
        <button class="chip border-danger bg-danger text-on-danger" type="button" @click="emptyTrash">清空</button>
      </div>
    </div>

    <div class="scrollbar-hide flex-1 space-y-3 overflow-y-auto px-4 pb-24 pt-4 lg:grid lg:grid-cols-2 lg:content-start lg:gap-4 lg:space-y-0 lg:px-10 lg:pb-10 lg:pt-6 xl:grid-cols-3">
      <div v-if="plans.loading" class="space-y-3 lg:col-span-full"><div v-for="i in 3" :key="i" class="skeleton h-28" /></div>
      <template v-else>
        <button
          v-for="plan in plans.items"
          :key="plan.id"
          class="card w-full p-4 text-left transition hover:border-primary/30 active:scale-[.99]"
          :class="picked.has(plan.id) && 'border-primary ring-2 ring-primary/30'"
          type="button"
          :role="inTrash ? 'checkbox' : undefined"
          :aria-checked="inTrash ? picked.has(plan.id) : undefined"
          @click="openPlan(plan)"
        >
          <div class="flex items-start gap-3">
            <span v-if="inTrash" class="mt-2.5 flex h-[22px] w-[22px] shrink-0 items-center justify-center rounded-md border-2" :class="picked.has(plan.id) ? 'border-primary bg-primary text-on-primary' : 'border-ink-line'">
              <Icon v-if="picked.has(plan.id)" icon="lucide:check" width="14" />
            </span>
            <span class="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl" :class="plan.source === 'ai' ? 'bg-xp-light text-xp' : 'bg-primary-light text-primary'">
              <Icon :icon="plan.source === 'ai' ? 'lucide:sparkles' : 'lucide:map'" width="22" />
            </span>
            <div class="min-w-0 flex-1">
              <p class="truncate text-[15px] font-black text-ink">{{ plan.title }}</p>
              <p class="mt-0.5 truncate text-xs text-ink-mute">{{ plan.goal || `${plan.start_date} ~ ${plan.end_date}` }}</p>
            </div>
            <span
              class="shrink-0 rounded-full px-2 py-0.5 text-[10px] font-bold"
              :class="plan.status === 'completed' ? 'bg-success-light text-success' : plan.expired ? 'bg-danger-light text-danger' : 'bg-primary-light text-primary'"
            >
              {{ inTrash ? `${plan.purge_in_days} 天后删除` : plan.status === 'active' ? (plan.expired ? '已过期' : `剩 ${plan.remaining_days} 天`) : plan.status_label }}
            </span>
          </div>
          <div class="mt-3 flex items-center gap-3">
            <div class="h-2 flex-1 overflow-hidden rounded-full bg-ink-line"><div class="h-full rounded-full bg-gradient-to-r from-primary to-xp" :style="{ width: `${plan.progress}%` }" /></div>
            <span class="num text-xs font-black text-ink">{{ plan.progress }}%</span>
          </div>
          <p class="mt-2 flex gap-3 text-[11px] font-semibold text-ink-mute">
            <span>{{ plan.task_done }}/{{ plan.task_total }} 个任务</span>
            <span v-if="plan.focus_minutes">已专注 {{ plan.focus_minutes }} 分钟</span>
          </p>
        </button>

        <EmptyState v-if="!plans.items.length && inTrash" class="lg:col-span-full" icon="lucide:trash-2" title="回收站是空的" text="删除的计划会在这里保留 30 天" />
        <EmptyState v-else-if="!plans.items.length" class="lg:col-span-full" icon="lucide:map" title="这里还没有计划" text="手动创建一个长期目标，或让 AI 根据课表空闲自动生成">
          <button class="chip chip-active" type="button" @click="router.push('/ai')"><Icon icon="lucide:sparkles" width="13" />AI 生成计划</button>
          <button class="chip" type="button" @click="editor = { open: true, plan: null }"><Icon icon="lucide:plus" width="13" />手动创建</button>
        </EmptyState>
      </template>
    </div>

    <PlanDetail :plan-id="detailId" @close="detailId = null" @edit="editPlan" />
    <PlanEditor :open="editor.open" :plan="editor.plan" @close="editor.open = false" />
  </div>
</template>
