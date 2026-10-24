<script setup>
import { Icon } from '@iconify/vue'

defineProps({
  board: { type: Object, required: true },
  limit: { type: Number, default: 5 },
})
const MEDALS = ['bg-amber-400', 'bg-slate-400', 'bg-orange-400']
</script>

<template>
  <div>
    <ol class="space-y-1.5">
      <li
        v-for="entry in board.entries.slice(0, limit)"
        :key="entry.user_id"
        class="flex items-center gap-3 rounded-2xl px-3 py-2"
        :class="entry.is_me ? 'bg-primary-light ring-1 ring-primary/30' : 'bg-background'"
      >
        <span class="num flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[11px] font-black" :class="entry.rank <= 3 ? [MEDALS[entry.rank - 1], 'text-white'] : 'text-ink-mute'">
          {{ entry.rank }}
        </span>
        <span class="text-xl">{{ entry.avatar }}</span>
        <span class="min-w-0 flex-1 truncate text-sm font-bold" :class="entry.is_me ? 'text-primary' : 'text-ink'">
          {{ entry.is_me ? '我' : entry.name }}
          <span v-if="entry.is_demo" class="ml-1 rounded bg-ink-line px-1 text-[9px] font-semibold text-ink-mute">演示</span>
        </span>
        <span class="num flex items-center gap-0.5 text-sm font-black text-xp"><Icon icon="lucide:sparkles" width="12" />{{ entry.xp }}</span>
      </li>
    </ol>
    <!-- 排名在展示范围之外时，单独补一行"我" -->
    <div v-if="board.me?.xp && board.me.rank > limit" class="mt-1.5 flex items-center gap-3 rounded-2xl bg-primary-light px-3 py-2 ring-1 ring-primary/30">
      <span class="num flex h-6 w-6 shrink-0 items-center justify-center text-[11px] font-black text-ink-mute">{{ board.me.rank }}</span>
      <span class="text-xl">{{ board.me.avatar }}</span>
      <span class="min-w-0 flex-1 truncate text-sm font-bold text-primary">我</span>
      <span class="num flex items-center gap-0.5 text-sm font-black text-xp"><Icon icon="lucide:sparkles" width="12" />{{ board.me.xp }}</span>
    </div>
    <p v-if="!board.me?.xp" class="mt-2 rounded-2xl bg-background px-3 py-2 text-xs text-ink-soft">
      本周你还没有获得 XP，完成任务或专注一次就能上榜
    </p>
  </div>
</template>
