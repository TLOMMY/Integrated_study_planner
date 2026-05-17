<script setup>
defineProps({
  text: {
    type: String,
    required: true,
  },
})

const emit = defineEmits(['click'])
</script>

<template>
  <button
    class="px-4 py-2 rounded-full bg-slate-100 text-sm text-gray-700 hover:bg-blue-100 hover:text-blue-600 transition-all duration-200"
    @click="emit('click', text)"
  >
    {{ text }}
  </button>
</template>