<script setup>
/**
 * 头像：有自定义图片（avatar_url）时显示图片，否则显示 emoji。图片加载失败时退回 emoji。
 * user 可以是当前用户，也可以是排行榜条目（都带 avatar / avatar_url）。尺寸、底色由外层 class 决定。
 */
import { computed, ref, watch } from 'vue'
import { apiBase } from '@/api/server'

const props = defineProps({ user: { type: Object, default: null } })
const broken = ref(false)
const src = computed(() => (props.user?.avatar_url && !broken.value ? `${apiBase()}${props.user.avatar_url}` : ''))
watch(() => props.user?.avatar_url, () => (broken.value = false))
</script>

<template>
  <span class="inline-flex items-center justify-center overflow-hidden">
    <img v-if="src" :src="src" alt="" class="h-full w-full object-cover" loading="lazy" @error="broken = true" />
    <template v-else>{{ user?.avatar || '🦉' }}</template>
  </span>
</template>
