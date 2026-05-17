<script setup>
import { computed, ref } from 'vue'
import { Icon } from '@iconify/vue'
import { useAiStore } from '@/stores/aiStore'

const aiStore = useAiStore()

const text = ref('')

const disabled = computed(() => {
  return !text.value.trim() || aiStore.thinking
})

const handleSend = async () => {
  const content = text.value.trim()

  if (!content) return

  await aiStore.sendMessage(content)

  text.value = ''
}
</script>

<template>
  <div
    class="border-t border-gray-100 bg-white px-4 py-3 flex items-end gap-3"
  >
    <!-- mic -->
    <button
      class="text-gray-400 mb-2"
    >
      <Icon icon="lucide:mic" width="22" />
    </button>

    <!-- input -->
    <div
      class="flex-1 bg-gray-50 rounded-2xl px-4 py-3"
    >
      <textarea
        v-model="text"
        rows="1"
        placeholder="输入你想做的事..."
        class="w-full bg-transparent resize-none outline-none text-sm"
        @keydown.enter.exact.prevent="handleSend"
      />
    </div>

    <!-- send -->
    <button
      :disabled="disabled"
      @click="handleSend"
      class="w-11 h-11 rounded-2xl flex items-center justify-center transition-all duration-200"
      :class="
        disabled
          ? 'bg-gray-200 text-gray-400'
          : 'bg-blue-600 text-white shadow-lg shadow-blue-100'
      "
    >
      <Icon
        :icon="
          aiStore.thinking
            ? 'lucide:loader-circle'
            : 'lucide:send'
        "
        width="18"
        :class="{
          'animate-spin': aiStore.thinking,
        }"
      />
    </button>
  </div>
</template>