<template>
  <div class="bottom-nav">
    <RouterLink to="/">首页</RouterLink>

    <RouterLink to="/timetable">
      课表
    </RouterLink>

    <RouterLink to="/plans">
      计划
    </RouterLink>

    <RouterLink to="/statistics">
      统计
    </RouterLink>

    <RouterLink to="/profile">
      我的
    </RouterLink>
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
  color: #666;
}

.router-link-active {
  color: #3b82f6;
  font-weight: bold;
}
</style>