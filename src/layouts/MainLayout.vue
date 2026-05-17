<script setup>
import BottomNav from '@/components/layout/BottomNav.vue'
</script>

<template>
  <div class="w-full h-full bg-slate-100 flex items-center justify-center">
    <!-- 手机容器 -->
    <div
      class="w-[375px] h-[812px] bg-white rounded-[32px] shadow-2xl overflow-hidden flex flex-col"
    >
      <!-- 页面内容 -->
      <div class="flex-1 overflow-hidden">
        <router-view />
      </div>

      <!-- 底部导航 -->
      <BottomNav />
    </div>
  </div>
</template>