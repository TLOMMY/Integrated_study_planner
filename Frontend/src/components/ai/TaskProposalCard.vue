<script setup>
/**
 * 新建任务提案：按天分组；全选 / 按天 / 单条勾选；日期、开始时间、时长可直接修改；可删单条；显示学习资源链接。
 * 导入后逐条显示成功 / 失败原因，失败的条目修改后可以重试（追加到同一个学习计划）。
 */
import { computed, reactive, ref, watch } from 'vue'
import dayjs from 'dayjs'
import { Icon } from '@iconify/vue'
import { useAiStore } from '@/stores/ai'
import { useUiStore } from '@/stores/ui'
import { formatMinutes, relativeDay, todayStr } from '@/utils/dates'

const props = defineProps({
  message: { type: Object, required: true },
  proposal: { type: Object, required: true },
})
const ai = useAiStore()
const ui = useUiStore()
const busy = ref(false)
const expanded = ref(false)

const copy = (items) => items.map((t) => ({ ...t, links: t.links || [], edited: false }))
const items = ref(copy(props.proposal.items || []))
const picked = reactive(new Set(items.value.filter((t) => !props.proposal.results?.[t.key]?.ok).map((t) => t.key)))
watch(() => props.proposal.id, () => {
  items.value = copy(props.proposal.items || [])
  picked.clear()
  items.value.forEach((t) => picked.add(t.key))
})

const result = (t) => props.proposal.results?.[t.key]
const done = (t) => Boolean(result(t)?.ok)

const toMin = (hm) => (hm ? Number(hm.slice(0, 2)) * 60 + Number(hm.slice(3, 5)) : null)
const endOf = (t) => {
  const start = toMin(t.start_time)
  if (start === null) return ''
  const end = start + Number(t.duration_minutes || 0)
  return end >= 1440 ? '次日' : `${String(Math.floor(end / 60)).padStart(2, '0')}:${String(end % 60).padStart(2, '0')}`
}

/** 本地即时校验（最终以导入时服务器校验为准）。 */
const localIssues = computed(() => {
  const map = {}
  const today = todayStr()
  const chosen = items.value.filter((t) => picked.has(t.key) && !done(t))
  for (const t of chosen) {
    const list = []
    const start = toMin(t.start_time)
    const minutes = Number(t.duration_minutes || 0)
    if (!t.date) list.push('请选择日期')
    else if (t.date < today) list.push('日期已经过去')
    if (!(minutes >= 5 && minutes <= 480)) list.push('时长需在 5-480 分钟')
    if (start !== null && start + minutes > 1440) list.push('跨越午夜')
    for (const o of chosen) {
      if (o === t || o.date !== t.date || o.start_time == null || start === null) continue
      const os = toMin(o.start_time)
      if (start < os + Number(o.duration_minutes || 0) && os < start + minutes) list.push(`与「${o.title}」重叠`)
    }
    if (list.length) map[t.key] = list
  }
  return map
})
const warningsOf = (t) => (t.edited ? [] : (t.warnings || []).filter(() => !done(t)))

const groups = computed(() => {
  // 只按日期分组；组内保持原来的顺序，改时间时条目不会跳动
  const map = new Map()
  const order = new Map(items.value.map((t, i) => [t.key, i]))
  for (const t of [...items.value].sort((a, b) => String(a.date).localeCompare(String(b.date)) || order.get(a.key) - order.get(b.key))) {
    if (!map.has(t.date)) map.set(t.date, [])
    map.get(t.date).push(t)
  }
  return [...map.entries()].map(([date, list]) => ({ date, items: list, minutes: list.reduce((s, t) => s + Number(t.duration_minutes || 0), 0) }))
})
const shown = computed(() => (expanded.value ? groups.value : groups.value.slice(0, 3)))

const selectable = computed(() => items.value.filter((t) => !done(t)))
const chosen = computed(() => selectable.value.filter((t) => picked.has(t.key)))
const allPicked = computed(() => selectable.value.length > 0 && chosen.value.length === selectable.value.length)
const somePicked = computed(() => chosen.value.length > 0 && !allPicked.value)
const toggleAll = () => {
  const on = !allPicked.value
  selectable.value.forEach((t) => (on ? picked.add(t.key) : picked.delete(t.key)))
}
const dayState = (g) => {
  const list = g.items.filter((t) => !done(t))
  const n = list.filter((t) => picked.has(t.key)).length
  return { all: list.length > 0 && n === list.length, some: n > 0 && n < list.length, empty: !list.length }
}
const toggleDay = (g) => {
  const on = !dayState(g).all
  g.items.filter((t) => !done(t)).forEach((t) => (on ? picked.add(t.key) : picked.delete(t.key)))
}
const toggle = (t) => (picked.has(t.key) ? picked.delete(t.key) : picked.add(t.key))
const edit = (t) => {
  t.edited = true
  picked.add(t.key)
}
const removeItem = (t) => {
  items.value = items.value.filter((x) => x !== t)
  picked.delete(t.key)
}

const totalMinutes = computed(() => chosen.value.reduce((s, t) => s + Number(t.duration_minutes || 0), 0))
const retrying = computed(() => props.proposal.applied && Object.values(props.proposal.results || {}).some((r) => !r.ok))
const allDone = computed(() => items.value.length > 0 && items.value.every(done))
const okCount = computed(() => items.value.filter(done).length)

const apply = async () => {
  if (!chosen.value.length) return
  busy.value = true
  try {
    const payload = chosen.value.map(({ edited, warnings, ...rest }) => ({ ...rest, duration_minutes: Number(rest.duration_minutes) }))
    await ai.applyProposal(props.message, props.proposal, payload)
    // 成功的条目自动取消勾选；失败的保留勾选，修改后可直接重试
    items.value.forEach((t) => {
      if (done(t)) picked.delete(t.key)
      t.edited = false
    })
  } catch (error) {
    ui.fail(error)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="overflow-hidden rounded-3xl border border-ink-line/70 bg-surface shadow-soft">
    <div class="bg-gradient-to-br from-primary to-xp px-4 py-3 text-on-primary">
      <p class="flex items-center gap-1 text-[10px] font-bold opacity-80"><Icon icon="lucide:calendar-plus" width="12" />新建任务 · 可修改后导入</p>
      <h3 class="mt-0.5 truncate text-base font-black">{{ proposal.title }}</h3>
      <p class="num mt-0.5 text-xs opacity-85">{{ items.length }} 个学习块 · {{ groups.length }} 天 · 合计 {{ formatMinutes(items.reduce((s, t) => s + Number(t.duration_minutes || 0), 0)) }}</p>
    </div>

    <div class="px-4 py-3">
      <label v-if="selectable.length" class="mb-2 flex cursor-pointer items-center gap-2 text-xs font-black text-ink">
        <input type="checkbox" class="accent-primary" :checked="allPicked" :indeterminate.prop="somePicked" aria-label="全选任务" @change="toggleAll" />
        全选
        <span class="ml-auto font-semibold text-ink-mute">已选 {{ chosen.length }}/{{ selectable.length }}</span>
      </label>

      <div class="space-y-3">
        <div v-for="g in shown" :key="g.date">
          <label class="mb-1.5 flex cursor-pointer items-center gap-2 text-[11px] font-black text-ink-soft">
            <input v-if="!dayState(g).empty" type="checkbox" class="accent-primary" :checked="dayState(g).all" :indeterminate.prop="dayState(g).some" :aria-label="`选择 ${g.date} 的任务`" @change="toggleDay(g)" />
            <Icon v-else icon="lucide:circle-check" width="14" class="text-success" />
            {{ relativeDay(g.date) }}<span class="num font-semibold text-ink-mute">{{ dayjs(g.date).format('M/D') }}</span>
            <span class="ml-auto font-semibold text-ink-mute">{{ g.items.length }} 块 · {{ formatMinutes(g.minutes) }}</span>
          </label>

          <div class="space-y-1.5">
            <div
              v-for="t in g.items"
              :key="t.key"
              class="rounded-2xl px-3 py-2 transition"
              :class="[
                done(t) ? 'bg-success-light/60' : result(t) && !result(t).ok ? 'bg-danger-light/60' : 'bg-background',
                !done(t) && !picked.has(t.key) && 'opacity-50',
              ]"
            >
              <div class="flex items-center gap-2">
                <input v-if="!done(t)" type="checkbox" class="accent-primary" :checked="picked.has(t.key)" :aria-label="`选择 ${t.title}`" @change="toggle(t)" />
                <Icon v-else icon="lucide:circle-check" width="16" class="shrink-0 text-success" />
                <span class="min-w-0 flex-1 truncate text-xs font-bold text-ink">{{ t.title }}</span>
                <button v-if="!done(t)" type="button" class="flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-ink-mute hover:bg-danger-light hover:text-danger" :aria-label="`删除 ${t.title}`" @click="removeItem(t)">
                  <Icon icon="lucide:x" width="14" />
                </button>
              </div>

              <div v-if="!done(t)" class="mt-1.5 flex flex-wrap items-center gap-1.5 pl-6">
                <input v-model="t.date" type="date" class="num rounded-lg border border-ink-line bg-surface px-1.5 py-1 text-[11px] text-ink" :aria-label="`${t.title} 的日期`" @input="edit(t)" />
                <input v-model="t.start_time" type="time" class="num rounded-lg border border-ink-line bg-surface px-1.5 py-1 text-[11px] text-ink" :aria-label="`${t.title} 的开始时间`" @input="edit(t)" />
                <span class="flex items-center gap-1 rounded-lg border border-ink-line bg-surface px-1.5 py-0.5">
                  <input v-model.number="t.duration_minutes" type="number" min="5" max="480" step="5" class="num w-11 bg-transparent text-[11px] text-ink outline-none" :aria-label="`${t.title} 的时长（分钟）`" @input="edit(t)" />
                  <span class="text-[10px] text-ink-mute">分钟</span>
                </span>
                <span v-if="t.start_time" class="num text-[10px] text-ink-mute">至 {{ endOf(t) }}</span>
              </div>
              <p v-else class="num mt-0.5 pl-6 text-[11px] text-success">{{ result(t).summary || `${t.start_time} · ${t.duration_minutes} 分钟` }} · 已导入</p>

              <p v-if="t.note && !done(t)" class="mt-1 pl-6 text-[11px] leading-4 text-ink-mute">{{ t.note }}</p>
              <div v-if="t.links?.length" class="mt-1 flex flex-wrap gap-1 pl-6">
                <a v-for="l in t.links" :key="l.url" :href="l.url" target="_blank" rel="noopener noreferrer" class="flex max-w-full items-center gap-1 rounded-full bg-primary-light px-2 py-0.5 text-[10px] font-bold text-primary">
                  <Icon icon="lucide:link" width="11" class="shrink-0" /><span class="truncate">{{ l.source ? `${l.source} · ` : '' }}{{ l.title }}</span>
                </a>
              </div>

              <p v-for="w in localIssues[t.key] || []" :key="`l${w}`" class="mt-1 flex gap-1 pl-6 text-[11px] font-semibold text-danger"><Icon icon="lucide:circle-x" width="12" class="mt-0.5 shrink-0" />{{ w }}</p>
              <p v-for="w in warningsOf(t)" :key="w" class="mt-1 flex gap-1 pl-6 text-[11px] font-semibold text-flame"><Icon icon="lucide:triangle-alert" width="12" class="mt-0.5 shrink-0" />{{ w }}</p>
              <p v-if="result(t) && !result(t).ok" class="mt-1 flex gap-1 pl-6 text-[11px] font-bold text-danger"><Icon icon="lucide:circle-x" width="12" class="mt-0.5 shrink-0" />未导入：{{ result(t).reason }}</p>
            </div>
          </div>
        </div>
        <button v-if="groups.length > 3" class="w-full text-center text-xs font-bold text-primary" type="button" @click="expanded = !expanded">
          {{ expanded ? '收起' : `查看全部 ${groups.length} 天` }}
        </button>
      </div>
    </div>

    <div class="border-t border-ink-line/60 p-3">
      <button v-if="allDone" class="btn w-full bg-success-light text-success" type="button" @click="$router.push('/today-task')">
        <Icon icon="lucide:circle-check" width="16" />已导入 {{ okCount }} 个任务 · 去日程查看
      </button>
      <template v-else>
        <button class="btn-primary w-full" type="button" :disabled="busy || !chosen.length || ai.streaming" @click="apply">
          <Icon :icon="busy ? 'lucide:loader-circle' : 'lucide:calendar-check'" width="16" :class="busy && 'animate-spin'" />
          {{ busy ? '正在导入…' : chosen.length ? `${retrying ? '重试' : '导入'} ${chosen.length} 个任务 · ${formatMinutes(totalMinutes)}` : '请勾选要导入的任务' }}
        </button>
        <p v-if="okCount" class="mt-1.5 text-center text-[11px] text-ink-mute">已导入 {{ okCount }} 个；未导入的可以改时间后重试</p>
        <p v-else class="mt-1.5 text-center text-[11px] text-ink-mute">可以直接修改日期、开始时间和时长，导入时会再检查一次冲突</p>
      </template>
    </div>
  </div>
</template>
