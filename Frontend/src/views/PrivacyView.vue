<script setup>
import LegalPage from '@/components/common/LegalPage.vue'
import { PRIVACY } from '@/utils/legal'
</script>

<template>
  <LegalPage :doc="PRIVACY" icon="lucide:shield-check" :other="{ to: { name: 'terms' }, label: '用户协议' }" />
</template>
