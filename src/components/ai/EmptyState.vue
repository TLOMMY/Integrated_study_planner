<script setup>
import { Icon } from '@iconify/vue'
</script>

<template>
  <div
    class="flex flex-col items-center justify-center text-center py-20 px-6"
  >
    <!-- icon -->
    <div
      class="w-20 h-20 rounded-3xl bg-blue-100 text-blue-600 flex items-center justify-center mb-6"
    >
      <Icon icon="lucide:sparkles" width="36" />
    </div>

    <!-- title -->
    <h2 class="text-xl font-bold text-gray-800 mb-3">
      AI 学习助手
    </h2>

    <!-- desc -->
    <p class="text-sm text-gray-500 leading-6 max-w-[280px]">
      你可以让我帮你生成学习计划、调整复习安排、分析课程压力。
    </p>

    <!-- tips -->
    <div class="flex flex-wrap justify-center gap-2 mt-8">
      <div class="chip">
        帮我安排今晚复习
      </div>

      <div class="chip">
        生成考试周计划
      </div>

      <div class="chip">
        调整我的作息
      </div>
    </div>
  </div>
</template>

<style scoped>
.chip {
  padding: 8px 14px;
  border-radius: 9999px;
  background: #f1f5f9;
  font-size: 13px;
  color: #475569;
}
</style>