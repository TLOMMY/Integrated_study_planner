<script setup>
import { Icon } from '@iconify/vue'
</script>

<template>
  <div class="bottom-nav">
    <RouterLink to="/">首页</RouterLink>
    <RouterLink to="/timetable">课表</RouterLink>
    <RouterLink to="/ai">AI</RouterLink>
    <RouterLink to="/plans">计划</RouterLink>
    <RouterLink to="/statistics">统计</RouterLink>
  </div>
</template>

<style scoped>
.bottom-nav {
  position: fixed;
  bottom: 0;
  width: 100%;
  height: 70px;
  background: white;
  display: flex;
  justify-content: space-around;
  align-items: center;
  border-top: 1px solid #eee;
}
a {
  text-decoration: none;
  color: #666;
}
.router-link-active {
  color: #3b82f6;
  font-weight: bold;
}
</style>