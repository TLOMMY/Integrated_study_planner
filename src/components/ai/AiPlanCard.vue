<script setup>
import { Icon } from '@iconify/vue'

defineProps({
  plan: {
    type: Object,
    required: true,
  },

  quickActions: {
    type: Array,
    default: () => [],
  },
})

const emit = defineEmits(['action'])
</script>

<template>
  <div class="animate-fade-in mb-10">

    <!-- card -->
    <div
      class="bg-gradient-to-br from-indigo-900 to-slate-800 rounded-3xl p-6 text-white shadow-xl shadow-indigo-100 relative overflow-hidden"
    >
      <!-- bg icon -->
      <div class="absolute top-0 right-0 p-4 opacity-10">
        <Icon
          icon="lucide:calendar-check"
          width="100"
        />
      </div>

      <!-- header -->
      <div class="flex justify-between items-center relative z-10">
        <h3 class="font-bold">
          {{ plan.title }}
        </h3>

        <span
          class="text-[10px] bg-white/20 px-2 py-0.5 rounded-full"
        >
          {{ plan.period }}
        </span>
      </div>

      <!-- stages -->
      <div class="mt-6 space-y-4 relative z-10">
        <div
          v-for="(item, index) in plan.stages"
          :key="index"
          class="flex items-center gap-4"
        >
          <div
            class="w-1.5 h-10 rounded-full"
            :class="item.color"
          />

          <div>
            <p class="text-[10px] opacity-60">
              {{ item.title }}
            </p>

            <p class="text-xs font-bold mt-0.5">
              {{ item.desc }}
            </p>
          </div>
        </div>
      </div>

      <!-- footer -->
      <div
        class="mt-6 pt-4 border-t border-white/10 flex justify-between items-center relative z-10"
      >
        <p class="text-[10px] opacity-60">
          {{ plan.total }}
        </p>

        <RouterLink
          to="/plans"
          class="bg-white text-indigo-900 text-[10px] font-bold px-4 py-2 rounded-xl"
        >
          确认使用
        </RouterLink>
      </div>
    </div>

    <!-- quick actions -->
    <div
      class="flex gap-2 mt-4 overflow-x-auto pb-2 scrollbar-hide"
    >
      <button
        v-for="(action, index) in quickActions"
        :key="index"
        @click="emit('action', action)"
        class="shrink-0 bg-white border border-gray-200 px-4 py-2 rounded-full text-xs text-gray-600 font-bold hover:bg-blue-50 hover:border-blue-200 transition-colors"
      >
        {{ action }}
      </button>
    </div>
  </div>
</template>