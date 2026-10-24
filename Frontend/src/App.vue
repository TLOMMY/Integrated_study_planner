<script setup>
import { RouterView } from 'vue-router'
import ToastHost from '@/components/common/ToastHost.vue'
import ConfirmHost from '@/components/common/ConfirmHost.vue'
import RewardOverlay from '@/components/common/RewardOverlay.vue'
</script>

<template>
  <div class="phone">
    <!--
      顶层页面（登录 / 主框架 / 专注）之间不再用 <Transition mode="out-in">：
      离开的页面里含 KeepAlive 缓存页和 Teleport 弹层时，out-in 会卡在"等待离场"，
      新页面永远不挂载，表现为白屏、刷新才恢复。改为进入时的纯 CSS 动画。
    -->
    <RouterView v-slot="{ Component, route }">
      <component :is="Component" :key="route.matched[0]?.path" class="page-enter" />
    </RouterView>
    <!-- 底部弹层统一挂到这里，保证平板"手机框"演示时也只覆盖手机区域 -->
    <div id="overlay-root"></div>
    <ConfirmHost />
    <RewardOverlay />
    <ToastHost />
  </div>
</template>
