<script setup>
import { Icon } from '@iconify/vue'
</script>

<template>
  <div
    class="absolute bottom-0 w-full h-20 bg-white border-t border-gray-100 flex items-center justify-around px-2 pb-2"
  >
    <RouterLink
      to="/"
      class="flex flex-col items-center text-gray-400"
    >
      <Icon
        icon="mdi:home"
        class="text-2xl"
      />

      <span class="text-[10px] mt-1">首页</span>
    </RouterLink>

    <RouterLink
      to="/timetable"
      class="flex flex-col items-center text-blue-500"
    >
      <Icon
        icon="mdi:calendar-month"
        class="text-2xl"
      />

      <span class="text-[10px] mt-1">课表</span>
    </RouterLink>

    <div class="relative -top-4">
      <div
        class="w-14 h-14 bg-blue-500 rounded-full flex items-center justify-center text-white shadow-lg border-4 border-white"
      >
        <Icon
          icon="mdi:bullseye-arrow"
          class="text-3xl"
        />
      </div>

      <span
        class="text-[10px] mt-1 text-center block text-gray-400"
      >
        今日视图
      </span>
    </div>

    <RouterLink
      to="/ai"
      class="flex flex-col items-center text-gray-400"
    >
      <Icon
        icon="mdi:robot"
        class="text-2xl"
      />

      <span class="text-[10px] mt-1">AI</span>
    </RouterLink>

    <RouterLink
      to="/statistics"
      class="flex flex-col items-center text-gray-400"
    >
      <Icon
        icon="mdi:chart-bar"
        class="text-2xl"
      />

      <span class="text-[10px] mt-1">统计</span>
    </RouterLink>
  </div>
</template>