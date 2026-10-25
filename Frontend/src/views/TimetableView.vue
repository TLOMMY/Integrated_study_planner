<script setup>
import { computed, nextTick, onActivated, onMounted, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import dayjs from 'dayjs'
import CourseGrid from '@/components/timetable/CourseGrid.vue'
import CourseEditor from '@/components/timetable/CourseEditor.vue'
import CourseDetail from '@/components/timetable/CourseDetail.vue'
import ImportSheet from '@/components/timetable/ImportSheet.vue'
import SemesterSettings from '@/components/timetable/SemesterSettings.vue'
import ExportSheet from '@/components/timetable/ExportSheet.vue'
import ShareSheet from '@/components/timetable/ShareSheet.vue'
import ShareImportSheet from '@/components/timetable/ShareImportSheet.vue'
import ExamSheet from '@/components/timetable/ExamSheet.vue'
import { aiRoute, examDaysText } from '@/components/timetable/examAi'
import BottomSheet from '@/components/common/BottomSheet.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import { useRoute, useRouter } from 'vue-router'
import { useTimetableStore } from '@/stores/timetable'
import { useTasksStore } from '@/stores/tasks'
import { useUiStore } from '@/stores/ui'

defineOptions({ name: 'TimetableView' })

const timetable = useTimetableStore()
const tasks = useTasksStore()
const ui = useUiStore()
const route = useRoute()
const router = useRouter()
const examInitial = ref(null)

const MORE = [
  { key: 'export', label: '导出图片', hint: '把本周课表存成 PNG', icon: 'lucide:image-down' },
  { key: 'share', label: '分享课表', hint: '生成 8 位分享码给同学', icon: 'lucide:share-2' },
  { key: 'share-import', label: '用分享码导入', hint: '导入同学分享的课表', icon: 'lucide:clipboard-paste' },
  { key: 'exams', label: '考试倒计时', hint: '记录考试，AI 帮你排复习', icon: 'lucide:alarm-clock' },
]
const pickMore = (key) => {
  if (key === 'exams') examInitial.value = null
  sheet.value = key
}
const openExams = (initial = null) => {
  examInitial.value = initial
  sheet.value = 'exams'
}
const loadExams = () => timetable.loadExams().catch(() => {})
/** 首页考试卡片跳过来时：/timetable?exams=1 或 ?exams=new */
const handleQuery = () => {
  if (!route.query.exams) return
  openExams(route.query.exams === 'new' ? 'new' : null)
  router.replace({ query: {} })
}

const showOff = ref(localStorage.getItem('timetable-show-off') === '1')
const sheet = ref('')
const editing = ref(null)
const preset = ref({})
const detail = ref(null)
const strip = ref(null)

const data = computed(() => timetable.data)
const weeks = computed(() => Array.from({ length: data.value?.total_weeks || 0 }, (_, i) => i + 1))
const isCurrent = computed(() => data.value && data.value.week === data.value.current_week)
const headerLine = computed(() => {
  const d = data.value
  if (!d) return ''
  if (!d.settings_ready) return `${d.semester} · 未设置开学日期`
  if (d.current_week === 0) return `${d.semester} · 不在学期内`
  return `${d.semester} · 本周第 ${d.current_week} 周`
})
const monthLabel = computed(() => (data.value ? `${dayjs(data.value.days[0].date).month() + 1}月` : ''))

watch(showOff, (value) => localStorage.setItem('timetable-show-off', value ? '1' : '0'))

const scrollToWeek = async () => {
  await nextTick()
  strip.value?.querySelector('[data-active="true"]')?.scrollIntoView({ inline: 'center', block: 'nearest', behavior: 'smooth' })
}

const load = async (week) => {
  try {
    await timetable.load(week)
    scrollToWeek()
  } catch (error) {
    ui.fail(error, '课表加载失败')
  }
}

const open = (name) => (sheet.value = name)
const openEditor = (course = null, at = {}) => {
  editing.value = course
  preset.value = at
  detail.value = null
  sheet.value = 'editor'
}
const openDetail = (course) => {
  detail.value = course
  sheet.value = 'detail'
}
const removeCourse = async (course) => {
  if (await timetable.removeCourse(course).catch(ui.fail)) sheet.value = ''
}

/** 课后复习：在这节课当天生成一个复习任务（对标"课程 + 待办"联动）。 */
const addReview = async (course) => {
  const date = data.value.days.find((d) => d.day_of_week === course.day_of_week)?.date
  try {
    await tasks.create({ title: `复习：${course.course_name}`, subject: course.course_name, due_date: date, duration_minutes: 30, priority: 2, note: `课后复习 · ${course.week_text}` })
    sheet.value = ''
  } catch (error) {
    ui.fail(error)
  }
}

onMounted(() => {
  load()
  loadExams()
  handleQuery()
})
onActivated(() => {
  if (data.value) load(timetable.week)
  loadExams()
  handleQuery()
})
</script>

<template>
  <div class="flex h-full flex-col">
    <header class="glass-bar shrink-0 bg-surface px-4 pb-2 pt-[calc(var(--safe-top)+16px)] lg:border-b lg:border-ink-line/70 lg:px-10 lg:pb-3 lg:pt-6">
     <div class="desk-page">
      <div class="flex items-center justify-between">
        <div class="min-w-0">
          <h1 class="flex items-baseline gap-2 text-[22px] font-black text-ink">
            课表 <span class="text-sm font-bold text-ink-mute">{{ monthLabel }}</span>
          </h1>
          <p class="truncate text-xs font-semibold text-ink-mute">{{ headerLine }}</p>
        </div>
        <div class="flex gap-2">
          <!-- 电脑端直接平铺；手机端收进"更多" -->
          <button class="icon-btn hidden lg:inline-flex" type="button" aria-label="导出图片" title="导出图片" :disabled="!data?.courses.length" @click="open('export')"><Icon icon="lucide:image-down" width="18" /></button>
          <button class="icon-btn hidden lg:inline-flex" type="button" aria-label="分享课表" title="分享课表" @click="open('share')"><Icon icon="lucide:share-2" width="18" /></button>
          <button class="icon-btn hidden lg:inline-flex" type="button" aria-label="用分享码导入" title="用分享码导入" @click="open('share-import')"><Icon icon="lucide:clipboard-paste" width="18" /></button>
          <button class="icon-btn" type="button" aria-label="导入课表" title="导入课表" @click="open('import')"><Icon icon="lucide:file-up" width="18" /></button>
          <button class="icon-btn" type="button" aria-label="学期设置" title="学期设置" @click="open('settings')"><Icon icon="lucide:settings-2" width="18" /></button>
          <button class="icon-btn lg:hidden" type="button" aria-label="更多" @click="open('more')"><Icon icon="lucide:ellipsis" width="18" /></button>
          <button class="icon-btn bg-primary text-on-primary" type="button" aria-label="添加课程" title="添加课程" @click="openEditor()"><Icon icon="lucide:plus" width="20" /></button>
        </div>
      </div>

      <!-- 考试条 -->
      <div class="scrollbar-hide mt-3 flex gap-2 overflow-x-auto">
        <button
          v-for="exam in timetable.exams.slice(0, 6)"
          :key="exam.id"
          type="button"
          class="flex shrink-0 items-center gap-2 rounded-2xl px-3 py-1.5 text-left"
          :class="exam.urgent ? 'bg-danger-light text-danger' : 'bg-background text-ink-soft'"
          @click="openExams()"
        >
          <Icon icon="lucide:alarm-clock" width="14" class="shrink-0" />
          <span class="max-w-[9rem] truncate text-xs font-bold">{{ exam.title }}</span>
          <span class="num text-xs font-black">{{ examDaysText(exam) }}</span>
        </button>
        <button v-if="timetable.exams.length" class="chip shrink-0 py-1" type="button" aria-label="让 AI 排复习计划" @click="router.push(aiRoute(timetable.exams[0]))">
          <Icon icon="lucide:sparkles" width="13" class="text-xp" />AI 排复习
        </button>
        <button class="chip shrink-0 py-1" type="button" @click="openExams(timetable.exams.length ? null : 'new')">
          <Icon :icon="timetable.exams.length ? 'lucide:calendar-clock' : 'lucide:plus'" width="13" />{{ timetable.exams.length ? '全部考试' : '添加考试倒计时' }}
        </button>
      </div>

      <button
        v-if="data && !data.settings_ready"
        class="mt-3 flex w-full items-center gap-2 rounded-2xl bg-flame-light px-3 py-2.5 text-left text-xs font-semibold text-ink-soft"
        type="button"
        @click="open('settings')"
      >
        <Icon icon="lucide:calendar-cog" width="18" class="shrink-0 text-flame" />
        <span class="flex-1">设置开学日期后，才能按周显示课程（单双周、第几周开课）</span>
        <Icon icon="lucide:chevron-right" width="16" class="text-flame" />
      </button>

      <div v-if="data?.settings_ready" class="mt-3 flex items-center gap-2">
        <div ref="strip" class="scrollbar-hide flex flex-1 gap-1.5 overflow-x-auto">
          <button
            v-for="w in weeks"
            :key="w"
            type="button"
            :data-active="w === data.week"
            class="num relative shrink-0 rounded-xl px-3 py-1.5 text-xs font-black transition"
            :class="w === data.week ? 'bg-inverse text-inverse-ink' : 'bg-background text-ink-soft'"
            @click="load(w)"
          >
            {{ w }}
            <span v-if="w === data.current_week" class="absolute -top-1 right-0.5 h-1.5 w-1.5 rounded-full bg-flame" />
          </button>
        </div>
        <button v-if="!isCurrent && data.current_week" class="chip shrink-0 py-1" type="button" @click="load(data.current_week)">回本周</button>
      </div>
     </div>
    </header>

    <div class="scrollbar-hide flex-1 overflow-y-auto px-2 pb-24 pt-2 lg:px-10 lg:pb-10 lg:pt-5">
     <div class="desk-page lg:rounded-3xl lg:bg-surface lg:p-5 lg:shadow-soft">
      <div v-if="timetable.loading" class="skeleton mx-2 h-[520px]" />
      <template v-else-if="data">
        <div v-if="data.courses.length" class="flex items-center justify-end px-2 pb-1">
          <label class="flex cursor-pointer items-center gap-1.5 text-[11px] font-semibold text-ink-mute">
            <input v-model="showOff" type="checkbox" class="accent-primary" />显示非本周课程
          </label>
        </div>
        <CourseGrid :data="data" :show-off="showOff" @select="openDetail" @empty="(at) => openEditor(null, at)" />
        <EmptyState v-if="!data.courses.length" compact icon="lucide:calendar-plus" title="还没有课程" text="导入教务系统导出的课表，或点击格子手动添加">
          <button class="chip chip-active" type="button" @click="open('import')"><Icon icon="lucide:file-up" width="13" />导入课表</button>
        </EmptyState>
      </template>
     </div>
    </div>

    <CourseDetail :open="sheet === 'detail'" :course="detail" @close="sheet = ''" @edit="openEditor" @delete="removeCourse" @review="addReview" />
    <CourseEditor :open="sheet === 'editor'" :course="editing" :preset="preset" @close="sheet = ''" />
    <ImportSheet :open="sheet === 'import'" @close="sheet = ''" />
    <SemesterSettings :open="sheet === 'settings'" @close="sheet = ''" />
    <ExportSheet :open="sheet === 'export'" :data="data" :show-off="showOff" @close="sheet = ''" />
    <ShareSheet :open="sheet === 'share'" @close="sheet = ''" @import="sheet = 'share-import'" />
    <ShareImportSheet :open="sheet === 'share-import'" @close="sheet = ''" />
    <ExamSheet :open="sheet === 'exams'" :initial="examInitial" @close="sheet = ''" />

    <BottomSheet :open="sheet === 'more'" title="更多" @close="sheet = ''">
      <div class="divide-y divide-ink-line/60 overflow-hidden rounded-3xl bg-background">
        <button
          v-for="item in MORE"
          :key="item.key"
          type="button"
          class="flex w-full items-center gap-3 px-4 py-3.5 text-left disabled:opacity-50"
          :disabled="item.key === 'export' && !data?.courses.length"
          @click="pickMore(item.key)"
        >
          <Icon :icon="item.icon" width="20" class="text-primary" />
          <span class="flex-1">
            <span class="block text-sm font-semibold text-ink">{{ item.label }}</span>
            <span class="block text-[11px] text-ink-mute">{{ item.hint }}</span>
          </span>
          <Icon icon="lucide:chevron-right" width="16" class="text-ink-mute" />
        </button>
      </div>
    </BottomSheet>
  </div>
</template>
