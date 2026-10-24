<script setup>
import { computed } from 'vue'
import dayjs from 'dayjs'
import { Icon } from '@iconify/vue'
import { formatMinutes } from '@/utils/dates'

const props = defineProps({
  day: { type: Object, required: true },
})
const emit = defineEmits(['toggle', 'focus', 'open', 'plan-free'])

const STATUS = { done: '已结束', ongoing: '进行中', upcoming: '' }

/** 今天的时间轴里插入一条"现在"指示线。 */
const items = computed(() => {
  const list = [...props.day.items]
  if (props.day.date !== dayjs().format('YYYY-MM-DD')) return list
  const now = dayjs().format('HH:mm')
  const index = list.findIndex((item) => item.start_time > now)
  list.splice(index === -1 ? list.length : index, 0, { type: 'now', id: 'now', start_time: now })
  return list
})
</script>

<template>
  <ol class="relative space-y-2 pl-14">
    <span class="absolute bottom-2 left-[46px] top-2 w-px bg-ink-line" aria-hidden="true" />
    <li v-for="item in items" :key="item.id" class="relative">
      <span class="num absolute -left-14 top-2.5 w-10 text-right text-[11px] font-bold" :class="item.type === 'now' ? 'text-danger' : 'text-ink-mute'">
        {{ item.start_time }}
      </span>

      <div v-if="item.type === 'now'" class="flex items-center gap-2 py-1">
        <span class="-ml-[11px] h-2.5 w-2.5 rounded-full bg-danger ring-4 ring-danger/15" />
        <span class="h-px flex-1 bg-danger/40" />
        <span class="text-[10px] font-bold text-danger">现在</span>
      </div>

      <div
        v-else-if="item.type === 'course'"
        class="rounded-2xl p-3 text-white shadow-soft"
        :class="item.status === 'done' && 'opacity-55'"
        :style="{ background: item.color }"
      >
        <div class="flex items-center justify-between gap-2">
          <p class="truncate text-sm font-black">{{ item.title }}</p>
          <span v-if="STATUS[item.status]" class="shrink-0 rounded-full bg-white/25 px-2 py-0.5 text-[10px] font-bold">{{ STATUS[item.status] }}</span>
        </div>
        <p class="mt-1 text-[11px] opacity-90">
          {{ item.start_time }}-{{ item.end_time }} · {{ item.periods }}<template v-if="item.location"> · {{ item.location }}</template>
        </p>
      </div>

      <div v-else-if="item.type === 'task'" class="flex items-center gap-3 rounded-2xl border border-ink-line/70 bg-surface px-3 py-2.5 shadow-soft">
        <button
          class="flex h-5 w-5 shrink-0 items-center justify-center rounded-full border-2"
          :class="item.task.completed ? 'border-success bg-success text-white' : 'border-primary'"
          type="button"
          :aria-label="item.task.completed ? '标记未完成' : '完成'"
          @click="emit('toggle', item.task)"
        >
          <Icon v-if="item.task.completed" icon="lucide:check" width="12" />
        </button>
        <button class="min-w-0 flex-1 text-left" type="button" @click="emit('open', item.task)">
          <p class="truncate text-sm font-semibold" :class="item.task.completed ? 'text-ink-mute line-through' : 'text-ink'">{{ item.title }}</p>
          <p class="num text-[11px] text-ink-mute">{{ item.start_time }}-{{ item.end_time }}</p>
        </button>
        <button v-if="!item.task.completed" class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary-light text-primary" type="button" aria-label="开始专注" @click="emit('focus', item.task)">
          <Icon icon="lucide:play" width="14" />
        </button>
      </div>

      <button
        v-else
        class="flex w-full items-center gap-2 rounded-2xl border border-dashed border-primary/30 bg-primary-light/40 px-3 py-2.5 text-left transition hover:bg-primary-light"
        type="button"
        @click="emit('plan-free', item)"
      >
        <Icon icon="lucide:coffee" width="16" class="text-primary" />
        <span class="flex-1 text-xs font-semibold text-ink-soft">空闲 {{ formatMinutes(item.minutes) }}（至 {{ item.end_time }}）</span>
        <span class="text-xs font-bold text-primary">安排</span>
      </button>
    </li>
  </ol>
</template>
