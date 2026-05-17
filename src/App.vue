<template>
  <div class="w-screen h-screen bg-slate-100 flex items-center justify-center">
    <div
      class="w-[375px] h-[812px] bg-white overflow-hidden relative rounded-[40px] shadow-2xl"
    >
      <RouterView />

      <BottomNav />
    </div>
  </div>
</template>

<script setup>
import { RouterView } from 'vue-router'
import BottomNav from '@/components/layout/BottomNav.vue'
</script>