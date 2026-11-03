<script setup>
import LegalPage from '@/components/common/LegalPage.vue'
import { TERMS } from '@/utils/legal'
</script>

<template>
  <LegalPage :doc="TERMS" icon="lucide:scale" :other="{ to: { name: 'privacy' }, label: '隐私政策' }" />
</template>
