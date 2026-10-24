<script setup>
import { Icon } from '@iconify/vue'
import BottomSheet from '@/components/common/BottomSheet.vue'

defineProps({
  open: { type: Boolean, default: false },
  course: { type: Object, default: null },
})
const emit = defineEmits(['close', 'edit', 'delete', 'review'])
const WEEK = ['', '一', '二', '三', '四', '五', '六', '日']
</script>

<template>
  <BottomSheet :open="open" @close="emit('close')">
    <template v-if="course">
      <div class="flex items-start gap-3 pt-3">
        <div class="h-12 w-1.5 shrink-0 rounded-full" :style="{ background: course.color }" />
        <div class="min-w-0 flex-1">
          <h2 class="text-lg font-black text-ink">{{ course.course_name }}</h2>
          <p class="mt-0.5 text-xs text-ink-mute">{{ course.semester }}</p>
        </div>
      </div>

      <dl class="mt-4 space-y-3 rounded-3xl bg-background p-4 text-sm">
        <div class="flex items-center gap-3">
          <Icon icon="lucide:clock" width="18" class="text-primary" />
          <dt class="sr-only">时间</dt>
          <dd class="font-semibold text-ink">周{{ WEEK[course.day_of_week] }} 第 {{ course.start_period }}-{{ course.end_period }} 节 · {{ course.start_time }}-{{ course.end_time }}</dd>
        </div>
        <div class="flex items-center gap-3">
          <Icon icon="lucide:calendar-range" width="18" class="text-primary" />
          <dt class="sr-only">周次</dt>
          <dd class="font-semibold text-ink">{{ course.week_text }}</dd>
        </div>
        <div v-if="course.classroom" class="flex items-center gap-3">
          <Icon icon="lucide:map-pin" width="18" class="text-primary" />
          <dt class="sr-only">教室</dt>
          <dd class="font-semibold text-ink">{{ course.classroom }}</dd>
        </div>
        <div v-if="course.teacher" class="flex items-center gap-3">
          <Icon icon="lucide:user-round" width="18" class="text-primary" />
          <dt class="sr-only">教师</dt>
          <dd class="font-semibold text-ink">{{ course.teacher }}</dd>
        </div>
        <div v-if="course.note" class="flex items-start gap-3">
          <Icon icon="lucide:sticky-note" width="18" class="mt-0.5 text-primary" />
          <dt class="sr-only">备注</dt>
          <dd class="text-ink-soft">{{ course.note }}</dd>
        </div>
      </dl>

      <button class="mt-3 flex w-full items-center gap-3 rounded-3xl border border-primary/15 bg-primary-light p-4 text-left" type="button" @click="emit('review', course)">
        <Icon icon="lucide:notebook-pen" width="20" class="text-primary" />
        <span class="flex-1 text-sm font-bold text-ink">课后复习：添加到这节课当天的任务</span>
        <Icon icon="lucide:plus" width="18" class="text-primary" />
      </button>
    </template>

    <template #footer>
      <div class="grid grid-cols-2 gap-3">
        <button class="btn-danger" type="button" @click="emit('delete', course)"><Icon icon="lucide:trash-2" width="16" />删除</button>
        <button class="btn-primary" type="button" @click="emit('edit', course)"><Icon icon="lucide:pencil" width="16" />编辑</button>
      </div>
    </template>
  </BottomSheet>
</template>
