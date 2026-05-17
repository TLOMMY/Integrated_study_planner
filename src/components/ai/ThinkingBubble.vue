<script setup>
import { Icon } from '@iconify/vue'
</script>

<template>
  <div class="flex gap-3 mb-6 animate-fade-in">
    <!-- avatar -->
    <div
      class="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center text-blue-600 shrink-0"
    >
      <Icon icon="lucide:bot" width="18" />
    </div>

    <!-- bubble -->
    <div
      class="bg-slate-100 rounded-[20px] rounded-bl-[4px] px-4 py-3 text-sm text-gray-500 flex items-center gap-1"
    >
      <span class="animate-bounce">.</span>

      <span
        class="animate-bounce"
        style="animation-delay: 0.2s"
      >
        .
      </span>

      <span
        class="animate-bounce"
        style="animation-delay: 0.4s"
      >
        .
      </span>

      <span class="ml-2">
        正在分析你的学习计划...
      </span>
    </div>
  </div>
</template>

<style scoped>
.animate-fade-in {
  animation: fadeIn 0.35s ease-out forwards;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }

  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>