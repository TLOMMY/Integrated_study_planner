<script setup>
import { computed, ref } from 'vue'
import dayjs from 'dayjs'
import { Icon } from '@iconify/vue'
import { ADJUSTMENTS, useAiStore } from '@/stores/ai'
import { useUiStore } from '@/stores/ui'
import { formatMinutes, relativeDay } from '@/utils/dates'

/** 回复的第二部分：结构化计划（日程任务 + 课程），可选择导入哪些内容。 */
const props = defineProps({ message: { type: Object, required: true } })
const ai = useAiStore()
const ui = useUiStore()
const adopting = ref(false)
const expanded = ref(false)
const WEEK = ['', '一', '二', '三', '四', '五', '六', '日']

const draft = computed(() => props.message.draft)
const courses = computed(() => draft.value.courses || [])
const importCourses = ref((draft.value.courses || []).length > 0)

const allGroups = computed(() => {
  const map = new Map()
  for (const task of draft.value.tasks) {
    if (!map.has(task.date)) map.set(task.date, [])
    map.get(task.date).push(task)
  }
  return [...map.entries()].map(([date, items]) => ({ date, items, minutes: items.reduce((s, t) => s + t.duration_minutes, 0) }))
})
const groups = computed(() => (expanded.value ? allGroups.value : allGroups.value.slice(0, 3)))
const dayCount = computed(() => allGroups.value.length)

// 按天选择要导入的日程：默认全选，可以只导入其中几天
const pickedDays = ref(new Set(allGroups.value.map((g) => g.date)))
const allDays = computed(() => dayCount.value > 0 && pickedDays.value.size === dayCount.value)
const someDays = computed(() => pickedDays.value.size > 0 && !allDays.value)
const toggleAllDays = () => (pickedDays.value = allDays.value ? new Set() : new Set(allGroups.value.map((g) => g.date)))
const toggleDay = (date) => {
  const next = new Set(pickedDays.value)
  next.has(date) ? next.delete(date) : next.add(date)
  pickedDays.value = next
}
const pickedTasks = computed(() => draft.value.tasks.filter((t) => pickedDays.value.has(t.date)))

const canAdopt = computed(() => pickedTasks.value.length || (importCourses.value && courses.value.length))
const adoptLabel = computed(() => {
  const parts = []
  if (pickedTasks.value.length) parts.push(`${pickedTasks.value.length} 个任务${allDays.value ? '' : `（${pickedDays.value.size} 天）`}`)
  if (importCourses.value && courses.value.length) parts.push(`${courses.value.length} 门课程`)
  return parts.length ? `导入 ${parts.join(' + ')}` : '请选择要导入的内容'
})

const adopt = async () => {
  adopting.value = true
  try {
    await ai.adopt(props.message, { tasks: pickedTasks.value, importCourses: importCourses.value })
  } catch (error) {
    ui.fail(error)
  } finally {
    adopting.value = false
  }
}
</script>

<template>
  <div class="overflow-hidden rounded-3xl border border-ink-line/70 bg-surface shadow-soft">
    <div class="bg-gradient-to-br from-primary to-xp p-4 text-white">
      <p class="flex items-center gap-1 text-[10px] font-bold opacity-80"><Icon icon="lucide:calendar-check" width="12" />结构化计划 · 可直接导入</p>
      <div class="mt-1 flex items-center justify-between gap-2">
        <h3 class="truncate text-base font-black">{{ draft.title }}</h3>
        <span class="shrink-0 rounded-full bg-white/20 px-2 py-0.5 text-[10px] font-bold">{{ draft.provider === 'llm' ? 'AI 模型' : '规则引擎' }}</span>
      </div>
      <p class="num mt-1 text-xs opacity-85">{{ dayjs(draft.start_date).format('M/D') }} - {{ dayjs(draft.end_date).format('M/D') }} · {{ draft.subjects.join('、') }}</p>
      <div class="mt-3 grid grid-cols-3 gap-2 text-center">
        <div class="rounded-2xl bg-white/15 py-2"><p class="num text-lg font-black">{{ draft.stats.task_count }}</p><p class="text-[10px] opacity-80">学习块</p></div>
        <div class="rounded-2xl bg-white/15 py-2"><p class="num text-lg font-black">{{ (draft.stats.total_minutes / 60).toFixed(1) }}</p><p class="text-[10px] opacity-80">总小时</p></div>
        <div class="rounded-2xl bg-white/15 py-2"><p class="num text-lg font-black">{{ draft.stats.course_count }}</p><p class="text-[10px] opacity-80">避开课程</p></div>
      </div>
    </div>

    <div v-if="draft.warnings?.length" class="space-y-1 border-b border-ink-line/60 bg-flame-light/60 px-4 py-2.5">
      <p v-for="w in draft.warnings" :key="w" class="flex gap-1.5 text-[11px] font-semibold text-flame"><Icon icon="lucide:triangle-alert" width="13" class="mt-0.5 shrink-0" />{{ w }}</p>
    </div>

    <!-- 日程任务 -->
    <section v-if="draft.tasks.length" class="border-b border-ink-line/60 px-4 py-3">
      <label class="mb-2 flex cursor-pointer items-center gap-2 text-xs font-black text-ink">
        <input type="checkbox" class="accent-primary" :checked="allDays" :indeterminate.prop="someDays" :disabled="message.saved" aria-label="全选日程" @change="toggleAllDays" />
        日程安排 · {{ draft.tasks.length }} 个学习块
        <span class="ml-auto font-semibold text-ink-mute">{{ allDays ? '全选' : `已选 ${pickedDays.size}/${dayCount} 天` }}</span>
      </label>
      <div class="space-y-3">
        <div v-for="group in groups" :key="group.date" :class="!pickedDays.has(group.date) && 'opacity-40'">
          <label class="mb-1.5 flex cursor-pointer items-center gap-2 text-[11px] font-black text-ink-soft">
            <input type="checkbox" class="accent-primary" :checked="pickedDays.has(group.date)" :disabled="message.saved" :aria-label="`导入 ${group.date}`" @change="toggleDay(group.date)" />
            {{ relativeDay(group.date) }}<span class="num font-semibold text-ink-mute">{{ dayjs(group.date).format('M/D') }}</span>
            <span class="ml-auto font-semibold text-ink-mute">{{ group.items.length }} 块 · {{ formatMinutes(group.minutes) }}</span>
          </label>
          <div class="space-y-1.5">
            <div v-for="(task, i) in group.items" :key="i" class="flex items-center gap-2.5 rounded-xl bg-background px-3 py-2">
              <span class="num w-11 shrink-0 text-[11px] font-black text-primary">{{ task.start_time }}</span>
              <span class="min-w-0 flex-1 truncate text-xs font-semibold text-ink">{{ task.title }}</span>
              <span class="num shrink-0 text-[10px] text-ink-mute">{{ task.duration_minutes }}'</span>
            </div>
          </div>
        </div>
        <button v-if="dayCount > 3" class="w-full text-center text-xs font-bold text-primary" type="button" @click="expanded = !expanded">
          {{ expanded ? '收起' : `查看全部 ${dayCount} 天` }}
        </button>
      </div>
    </section>

    <!-- 课程 -->
    <section v-if="courses.length" class="border-b border-ink-line/60 px-4 py-3">
      <label class="mb-2 flex cursor-pointer items-center gap-2 text-xs font-black text-ink">
        <input v-model="importCourses" type="checkbox" class="accent-primary" :disabled="message.saved" />课程安排 · {{ courses.length }} 门新课程
      </label>
      <div class="space-y-1.5" :class="!importCourses && 'opacity-40'">
        <div v-for="(c, i) in courses" :key="i" class="flex items-center gap-2.5 rounded-xl bg-background px-3 py-2">
          <span class="h-8 w-1 shrink-0 rounded-full" :style="{ background: c.color }" />
          <div class="min-w-0 flex-1">
            <p class="truncate text-xs font-bold text-ink">{{ c.course_name }}</p>
            <p class="text-[10px] text-ink-mute">周{{ WEEK[c.day_of_week] }} {{ c.start_period }}-{{ c.end_period }}节 · {{ c.start_time }}-{{ c.end_time }} · {{ c.week_text }}<template v-if="c.classroom"> · {{ c.classroom }}</template></p>
          </div>
        </div>
      </div>
    </section>

    <ul class="space-y-1 border-b border-ink-line/60 px-4 py-2.5">
      <li v-for="tip in draft.insights" :key="tip" class="flex gap-2 text-[11px] leading-5 text-ink-mute">
        <Icon icon="lucide:check" width="13" class="mt-1 shrink-0 text-success" />{{ tip }}
      </li>
    </ul>

    <p v-if="!draft.tasks.length && !courses.length" class="px-4 py-3 text-center text-xs text-ink-mute">这段时间没有足够的空闲时段</p>

    <div class="p-3">
      <div v-if="message.saved" class="space-y-2">
        <button class="btn w-full bg-success-light text-success" type="button" @click="$router.push('/today-task')">
          <Icon icon="lucide:circle-check" width="16" />已导入<template v-if="message.result"> {{ message.result.tasks }} 个任务<template v-if="message.result.courses"> · {{ message.result.courses }} 门课程</template></template>
        </button>
        <p v-for="s in message.result?.skipped || []" :key="s.course_name" class="text-[11px] text-flame">「{{ s.course_name }}」未导入：{{ s.reason }}</p>
      </div>
      <template v-else>
        <button class="btn-primary w-full" type="button" :disabled="adopting || !canAdopt || ai.thinking" @click="adopt">
          <Icon icon="lucide:calendar-check" width="16" />{{ adopting ? '正在导入…' : adoptLabel }}
        </button>
        <div class="scrollbar-hide mt-2 flex gap-1.5 overflow-x-auto">
          <button v-for="a in ADJUSTMENTS" :key="a.key" class="chip shrink-0" type="button" :disabled="ai.thinking" @click="ai.adjust(message, a.key)">
            <Icon :icon="a.icon" width="13" />{{ a.label }}
          </button>
        </div>
      </template>
    </div>
  </div>
</template>
