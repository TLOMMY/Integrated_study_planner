<script setup>
defineProps({
  item: {
    type: Object,
    required: true,
  },
})
</script>

<template>
  <div
    class="flex-1 bg-white rounded-2xl p-3 shadow-sm border border-gray-100 flex flex-col items-center"
  >
    <span class="text-lg font-bold" :class="item.color">
      {{ item.value }}
    </span>

    <span
      class="text-[8px] text-gray-400 font-bold uppercase tracking-widest"
    >
      {{ item.label }}
    </span>
  </div>
</template>