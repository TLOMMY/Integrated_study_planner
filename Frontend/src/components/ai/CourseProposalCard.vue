<script setup>
/** 新增课程提案：星期 / 节次 / 周次 / 教室可编辑，逐条勾选、逐条导入并显示失败原因（节次冲突、周次越界等）。 */
import { computed, reactive, ref } from 'vue'
import { Icon } from '@iconify/vue'
import { useAiStore } from '@/stores/ai'
import { useUiStore } from '@/stores/ui'

const props = defineProps({
  message: { type: Object, required: true },
  proposal: { type: Object, required: true },
})
const ai = useAiStore()
const ui = useUiStore()
const busy = ref(false)
const WEEK = ['', '周一', '周二', '周三', '周四', '周五', '周六', '周日']
const periodCount = computed(() => props.proposal.period_count || 12)
const totalWeeks = computed(() => props.proposal.total_weeks || 20)

const items = ref((props.proposal.items || []).map((c) => ({ ...c, week_text: c.week_text || '', edited: false })))
const result = (c) => props.proposal.results?.[c.key]
const done = (c) => Boolean(result(c)?.ok)
const picked = reactive(new Set(items.value.filter((c) => !done(c)).map((c) => c.key)))
const toggle = (c) => (picked.has(c.key) ? picked.delete(c.key) : picked.add(c.key))
const edit = (c) => {
  c.edited = true
  picked.add(c.key)
}
const chosen = computed(() => items.value.filter((c) => !done(c) && picked.has(c.key)))
const allDone = computed(() => items.value.length > 0 && items.value.every(done))

const localIssues = (c) => {
  const list = []
  const p1 = Number(c.start_period)
  const p2 = Number(c.end_period)
  if (!(p1 >= 1) || p2 < p1) list.push('结束节次不能早于开始节次')
  else if (p2 > periodCount.value) list.push(`超出节次表：只有 ${periodCount.value} 节`)
  if (!String(c.week_text || '').match(/\d/)) list.push('请填写周次，如 1-16周')
  return list
}

const apply = async () => {
  busy.value = true
  try {
    const payload = chosen.value.map((c) => ({
      key: c.key, course_name: c.course_name, day_of_week: Number(c.day_of_week),
      start_period: Number(c.start_period), end_period: Number(c.end_period),
      // 只传周次文字，由服务器解析（支持 1-16周、2-16周(双)、1-8,10-16周）
      week_text: c.week_text, classroom: c.classroom || '', teacher: c.teacher || '',
    }))
    await ai.applyProposal(props.message, props.proposal, payload)
    items.value.forEach((c) => {
      if (done(c)) picked.delete(c.key)
      c.edited = false
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
    <div class="flex items-center gap-2 border-b border-ink-line/60 bg-success-light/60 px-4 py-3">
      <Icon icon="lucide:book-open" width="18" class="text-success" />
      <div class="min-w-0">
        <p class="text-sm font-black text-ink">新增课程 · {{ items.length }} 门</p>
        <p class="text-[11px] text-ink-mute">每周固定上课，确认后加入课表（共 {{ totalWeeks }} 周、{{ periodCount }} 节）</p>
      </div>
    </div>

    <div class="space-y-2 px-4 py-3">
      <div v-for="c in items" :key="c.key" class="rounded-2xl px-3 py-2.5" :class="[done(c) ? 'bg-success-light/60' : result(c) && !result(c).ok ? 'bg-danger-light/60' : 'bg-background', !done(c) && !picked.has(c.key) && 'opacity-50']">
        <div class="flex items-center gap-2">
          <input v-if="!done(c)" type="checkbox" class="accent-primary" :checked="picked.has(c.key)" :aria-label="`选择 ${c.course_name}`" @change="toggle(c)" />
          <Icon v-else icon="lucide:circle-check" width="16" class="shrink-0 text-success" />
          <span class="min-w-0 flex-1 truncate text-sm font-bold text-ink">{{ c.course_name }}</span>
        </div>
        <p v-if="done(c)" class="mt-1 pl-6 text-[11px] text-success">{{ result(c).summary }} · 已加入课表</p>
        <div v-else class="mt-2 grid grid-cols-2 gap-1.5 pl-6 text-[11px] sm:grid-cols-4">
          <label class="flex flex-col gap-0.5"><span class="text-ink-mute">星期</span>
            <select v-model.number="c.day_of_week" class="rounded-lg border border-ink-line bg-surface px-1.5 py-1 text-ink" @change="edit(c)">
              <option v-for="d in 7" :key="d" :value="d">{{ WEEK[d] }}</option>
            </select>
          </label>
          <label class="flex flex-col gap-0.5"><span class="text-ink-mute">节次</span>
            <span class="flex items-center gap-1">
              <input v-model.number="c.start_period" type="number" min="1" :max="periodCount" class="num w-full rounded-lg border border-ink-line bg-surface px-1.5 py-1 text-ink" aria-label="开始节次" @input="edit(c)" />
              <span class="text-ink-mute">-</span>
              <input v-model.number="c.end_period" type="number" min="1" :max="periodCount" class="num w-full rounded-lg border border-ink-line bg-surface px-1.5 py-1 text-ink" aria-label="结束节次" @input="edit(c)" />
            </span>
          </label>
          <label class="flex flex-col gap-0.5"><span class="text-ink-mute">周次</span>
            <input v-model="c.week_text" class="rounded-lg border border-ink-line bg-surface px-1.5 py-1 text-ink" placeholder="1-16周" @input="edit(c)" />
          </label>
          <label class="flex flex-col gap-0.5"><span class="text-ink-mute">教室</span>
            <input v-model="c.classroom" maxlength="80" class="rounded-lg border border-ink-line bg-surface px-1.5 py-1 text-ink" placeholder="可不填" @input="edit(c)" />
          </label>
        </div>
        <p v-if="!done(c) && c.start_time && !c.edited" class="num mt-1 pl-6 text-[10px] text-ink-mute">{{ c.start_time }}-{{ c.end_time }}</p>
        <template v-if="!done(c)">
          <p v-for="w in localIssues(c)" :key="`l${w}`" class="mt-1 flex gap-1 pl-6 text-[11px] font-semibold text-danger"><Icon icon="lucide:circle-x" width="12" class="mt-0.5 shrink-0" />{{ w }}</p>
          <p v-for="w in c.edited ? [] : c.warnings || []" :key="w" class="mt-1 flex gap-1 pl-6 text-[11px] font-semibold text-flame"><Icon icon="lucide:triangle-alert" width="12" class="mt-0.5 shrink-0" />{{ w }}</p>
          <p v-if="result(c) && !result(c).ok" class="mt-1 flex gap-1 pl-6 text-[11px] font-bold text-danger"><Icon icon="lucide:circle-x" width="12" class="mt-0.5 shrink-0" />未导入：{{ result(c).reason }}</p>
        </template>
      </div>
    </div>

    <div class="border-t border-ink-line/60 p-3">
      <button v-if="allDone" class="btn w-full bg-success-light text-success" type="button" @click="$router.push('/timetable')">
        <Icon icon="lucide:circle-check" width="16" />已加入课表 · 去查看
      </button>
      <button v-else class="btn-primary w-full" type="button" :disabled="busy || !chosen.length || ai.streaming" @click="apply">
        <Icon :icon="busy ? 'lucide:loader-circle' : 'lucide:calendar-plus'" width="16" :class="busy && 'animate-spin'" />
        {{ busy ? '正在导入…' : chosen.length ? `加入课表（${chosen.length} 门）` : '请勾选要导入的课程' }}
      </button>
    </div>
  </div>
</template>
