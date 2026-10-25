<script setup>
import { computed, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import BottomSheet from '@/components/common/BottomSheet.vue'
import { shareApi } from '@/api/growth'
import { useTimetableStore } from '@/stores/timetable'
import { useUiStore } from '@/stores/ui'

const props = defineProps({ open: { type: Boolean, default: false } })
const emit = defineEmits(['close'])
const timetable = useTimetableStore()
const ui = useUiStore()
const WEEK = ['', '一', '二', '三', '四', '五', '六', '日']

const code = ref('')
const preview = ref(null)
const mode = ref('merge')
const usePeriods = ref(false)
const busy = ref(false)
const error = ref('')
const result = ref(null)

const clean = computed(() => code.value.replace(/[\s-]/g, '').toUpperCase())
const periodsDiffer = computed(() => {
  const mine = timetable.meta?.period_times || []
  const theirs = preview.value?.period_times || []
  return theirs.length && JSON.stringify(mine) !== JSON.stringify(theirs)
})
const grouped = computed(() => {
  const map = new Map()
  for (const c of preview.value?.courses || []) {
    if (!map.has(c.course_name)) map.set(c.course_name, { name: c.course_name, color: c.color, slots: [] })
    map.get(c.course_name).slots.push(`周${WEEK[c.day_of_week]} ${c.start_period}-${c.end_period}节${c.classroom ? ` @${c.classroom}` : ''}`)
  }
  return [...map.values()]
})

watch(
  () => props.open,
  (open) => {
    if (!open) return
    code.value = ''
    preview.value = null
    result.value = null
    error.value = ''
    mode.value = 'merge'
    usePeriods.value = false
    timetable.ensure().catch(() => {})
  },
)

const lookup = async () => {
  if (clean.value.length < 6) {
    error.value = '请输入 8 位分享码'
    return
  }
  busy.value = true
  error.value = ''
  try {
    preview.value = await shareApi.preview(clean.value)
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

const doImport = async () => {
  if (mode.value === 'replace') {
    const ok = await ui.confirm({ title: '覆盖本学期课表？', message: '会先清空你本学期的全部课程，再导入同学的课表。此操作无法撤销。', confirmText: '覆盖导入', danger: true })
    if (!ok) return
  }
  busy.value = true
  try {
    const data = await shareApi.importCourses(preview.value.code, { mode: mode.value, use_period_times: usePeriods.value })
    result.value = data
    timetable.applyPayload(data.timetable)
    ui.reward(data.reward)
    if (data.added_count) ui.success(`已导入 ${data.added_count} 门课`)
  } catch (e) {
    ui.fail(e, '导入失败')
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <BottomSheet :open="open" title="用分享码导入" subtitle="导入同学分享的课表到你的当前学期" @close="emit('close')">
    <!-- 导入结果 -->
    <div v-if="result" class="space-y-3">
      <div class="rounded-3xl p-4" :class="result.added_count ? 'bg-success-light' : 'bg-background'">
        <p class="flex items-center gap-2 text-sm font-black" :class="result.added_count ? 'text-success' : 'text-ink'">
          <Icon :icon="result.added_count ? 'lucide:circle-check' : 'lucide:info'" width="18" />已导入 {{ result.added_count }} 门，跳过 {{ result.skipped_count }} 门
        </p>
      </div>
      <div v-if="result.skipped.length">
        <p class="label">跳过的课程</p>
        <ul class="space-y-1.5">
          <li v-for="(s, i) in result.skipped" :key="i" class="rounded-2xl bg-background px-3 py-2 text-xs">
            <p class="font-bold text-ink">{{ s.label }}</p>
            <p class="mt-0.5 text-ink-soft">{{ s.reason }}</p>
          </li>
        </ul>
        <p class="mt-2 text-[11px] text-ink-mute">想完全换成同学的课表，可返回选择“覆盖本学期”。</p>
      </div>
    </div>

    <!-- 输入分享码 -->
    <div v-else-if="!preview" class="space-y-3">
      <form class="flex gap-2" @submit.prevent="lookup">
        <input
          v-model="code"
          class="field num flex-1 text-center text-lg font-black uppercase tracking-[0.2em]"
          maxlength="12"
          placeholder="8 位分享码"
          aria-label="分享码"
          autocomplete="off"
          autocapitalize="characters"
        />
        <button class="btn-primary shrink-0" type="submit" :disabled="busy">查看</button>
      </form>
      <p v-if="error" class="rounded-2xl bg-danger-light px-3 py-2 text-xs font-semibold text-danger" role="alert">{{ error }}</p>
      <p class="text-[11px] leading-5 text-ink-mute">分享码由同学在课表页“分享课表”生成，7 天内有效。导入前可以先预览课程。</p>
    </div>

    <!-- 预览 -->
    <div v-else class="space-y-3">
      <div class="flex items-center gap-3 rounded-3xl bg-primary-light p-4">
        <span class="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-surface text-2xl">{{ preview.owner_avatar }}</span>
        <div class="min-w-0 flex-1">
          <p class="truncate text-sm font-black text-ink">来自 {{ preview.owner_name }}{{ preview.is_mine ? '（我自己）' : '' }}</p>
          <p class="text-xs text-ink-soft">{{ preview.semester }} · {{ preview.course_count }} 门课</p>
        </div>
      </div>
      <ul class="max-h-60 space-y-1.5 overflow-y-auto">
        <li v-for="g in grouped" :key="g.name" class="flex items-start gap-2.5 rounded-2xl bg-background px-3 py-2">
          <i class="mt-1 h-3 w-3 shrink-0 rounded-full" :style="{ background: g.color }" />
          <div class="min-w-0">
            <p class="truncate text-sm font-bold text-ink">{{ g.name }}</p>
            <p class="text-[11px] text-ink-mute">{{ g.slots.join('；') }}</p>
          </div>
        </li>
      </ul>
      <div class="grid grid-cols-2 gap-2" role="radiogroup" aria-label="导入方式">
        <button type="button" role="radio" :aria-checked="mode === 'merge'" class="rounded-2xl border p-3 text-left" :class="mode === 'merge' ? 'border-primary bg-primary-light' : 'border-ink-line'" @click="mode = 'merge'">
          <p class="text-sm font-bold text-ink">合并</p>
          <p class="mt-0.5 text-[11px] text-ink-mute">保留我的课，冲突的跳过</p>
        </button>
        <button type="button" role="radio" :aria-checked="mode === 'replace'" class="rounded-2xl border p-3 text-left" :class="mode === 'replace' ? 'border-danger bg-danger-light' : 'border-ink-line'" @click="mode = 'replace'">
          <p class="text-sm font-bold text-ink">覆盖本学期</p>
          <p class="mt-0.5 text-[11px] text-ink-mute">清空我的课，换成同学的</p>
        </button>
      </div>
      <label v-if="periodsDiffer" class="flex cursor-pointer items-start gap-2 rounded-2xl bg-flame-light px-3 py-2 text-xs text-ink-soft">
        <input v-model="usePeriods" type="checkbox" class="mt-0.5 accent-primary" />
        <span>同学的节次时间和你不同，同时采用同学的节次时间（{{ preview.period_times.length }} 节）</span>
      </label>
    </div>

    <template #footer>
      <button v-if="result" class="btn-primary w-full" type="button" @click="emit('close')">完成</button>
      <div v-else-if="preview" class="grid grid-cols-2 gap-3">
        <button class="btn-ghost" type="button" @click="preview = null">换个分享码</button>
        <button class="btn-primary" type="button" :disabled="busy" @click="doImport"><Icon icon="lucide:import" width="16" />{{ busy ? '导入中…' : '导入' }}</button>
      </div>
    </template>
  </BottomSheet>
</template>
