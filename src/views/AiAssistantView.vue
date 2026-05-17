<script setup>
import { nextTick, ref, watch } from 'vue'

import { useAiStore } from '@/stores/aiStore'

import AiHeader from '@/components/ai/AiHeader.vue'
import ChatMessage from '@/components/ai/ChatMessage.vue'
import AiPlanCard from '@/components/ai/AiPlanCard.vue'
import ChatInput from '@/components/ai/ChatInput.vue'
import ThinkingBubble from '@/components/ai/ThinkingBubble.vue'
import EmptyState from '@/components/ai/EmptyState.vue'

const aiStore = useAiStore()

const chatRef = ref(null)

watch(
  () => aiStore.messages.length,
  async () => {
    await nextTick()

    chatRef.value?.scrollTo({
      top: chatRef.value.scrollHeight,
      behavior: 'smooth',
    })
  }
)
</script>

<template>
  <div class="flex flex-col h-full bg-white">

    <!-- header -->
    <AiHeader />

    <!-- chat -->
    <div
      ref="chatRef"
      class="flex-1 overflow-y-auto px-6 py-4 pb-8 scrollbar-hide"
    >
      <!-- empty -->
      <EmptyState
        v-if="!aiStore.messages.length"
      />

      <!-- messages -->
      <ChatMessage
        v-for="message in aiStore.messages"
        :key="message.id"
        :message="message"
      />

      <!-- thinking -->
      <ThinkingBubble v-if="aiStore.thinking" />

      <!-- plan -->
      <AiPlanCard
        v-if="aiStore.generatedPlan"
        :plan="aiStore.generatedPlan"
        :quick-actions="aiStore.quickActions"
      />
    </div>

    <!-- input -->
    <ChatInput />
  </div>
</template>

<style scoped>
.scrollbar-hide::-webkit-scrollbar {
  display: none;
}

.scrollbar-hide {
  scrollbar-width: none;
}

.bubble-ai {
  background: #f1f5f9;
  border-radius: 20px 20px 20px 4px;
}

.bubble-user {
  background: #3b82f6;
  color: white;
  border-radius: 20px 20px 4px 20px;
}

.animate-fade-in {
  animation: fadeIn 0.4s ease-out forwards;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }

  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>