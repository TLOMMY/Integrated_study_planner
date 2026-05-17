<script setup>
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import dayjs from 'dayjs'

import { useDayViewStore } from '@/stores/dayView'

import DayTimelineItem from '@/components/day/DayTimelineItem.vue'
import DayFreeBlock from '@/components/day/DayFreeBlock.vue'

const router = useRouter()

const store = useDayViewStore()

onMounted(() => {
  store.fetchTimeline(dayjs().format('YYYY-MM-DD'))
})

const goWeekView = () => {
  router.push('/timetable')
}
</script>

<template>
  <div class="relative w-full h-full bg-white overflow-hidden">
    <!-- Header -->
    <div
      class="h-[88px] px-6 pt-10 pb-4 bg-white border-b border-slate-100 z-20"
    >
      <div class="flex justify-between items-center mb-4">
        <div class="bg-gray-100 rounded-full p-1 flex gap-1">
          <button
            class="px-4 py-1.5 text-xs text-gray-500 font-medium"
            @click="goWeekView"
          >
            周视图
          </button>

          <button
            class="px-4 py-1.5 text-xs bg-white text-blue-500 font-bold rounded-full shadow-sm"
          >
            日视图
          </button>
        </div>

        <div class="text-sm font-bold text-gray-800">
          {{ store.currentDate }}
        </div>
      </div>
    </div>

    <!-- Title -->
    <div class="px-6 py-4 bg-white">
      <h1 class="text-xl font-bold">
        {{ store.currentTitle }}
      </h1>
    </div>

    <!-- Loading -->
    <div
      v-if="store.loading"
      class="flex justify-center items-center h-[500px]"
    >
      <span class="text-gray-400 text-sm">
        加载中...
      </span>
    </div>

    <!-- Error -->
    <div
      v-else-if="store.error"
      class="flex justify-center items-center h-[500px]"
    >
      <span class="text-red-500 text-sm">
        {{ store.error }}
      </span>
    </div>

    <!-- Empty -->
    <div
      v-else-if="store.timeline.length === 0"
      class="flex justify-center items-center h-[500px]"
    >
      <span class="text-gray-400 text-sm">
        今日暂无安排
      </span>
    </div>

    <!-- Timeline -->
    <div
      v-else
      class="h-[640px] overflow-y-auto scrollbar-hide pb-24"
    >
      <div class="relative">
        <!-- 时间线 -->
        <div
          class="absolute left-16 top-0 bottom-0 w-[1px] bg-gray-200"
        ></div>

        <div class="space-y-0">
          <template
            v-for="item in store.timeline"
            :key="item.id"
          >
            <DayFreeBlock
              v-if="item.type === 'free'"
              :item="item"
            />

            <DayTimelineItem
              v-else
              :item="item"
            />
          </template>

          <!-- End -->
          <div class="flex items-center py-6">
            <div class="w-16 text-right pr-4 text-xs text-gray-300">
              17:00
            </div>

            <div
              class="flex-1 border-t border-dashed border-gray-200 mx-4 flex justify-center"
            >
              <span
                class="bg-white px-4 -mt-2.5 text-[10px] text-gray-300 font-bold tracking-widest"
              >
                [ 今日结束 ]
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.scrollbar-hide::-webkit-scrollbar {
  display: none;
}

.scrollbar-hide {
  scrollbar-width: none;
}
</style>