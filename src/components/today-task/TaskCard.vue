<script setup>
import { Icon } from '@iconify/vue'
import { useRouter } from 'vue-router'

const router = useRouter()
defineProps({
  task: {
    type: Object,
    required: true
  }
})
</script>

<template>
  <div
    :class="[
      task.completed
        ? 'bg-gray-50/50 border border-gray-100 rounded-2xl p-4 opacity-70'
        : 'bg-white border border-gray-100 rounded-2xl p-4 shadow-sm hover:shadow-md transition-shadow'
    ]"
  >
    <div class="flex justify-between items-start">
      <div class="flex gap-3">
        <div
          :class="[
            task.iconBg,
            'p-2.5 rounded-xl'
          ]"
        >
          <Icon
            :icon="task.icon"
            width="22"
          />
        </div>

        <div>
          <h4
            :class="[
              task.completed
                ? 'font-bold text-gray-400 text-sm line-through'
                : 'font-bold text-gray-800 text-sm'
            ]"
          >
            {{ task.title }}
          </h4>

          <div class="flex items-center gap-2 mt-1">
            <span
              :class="[
                task.tagClass,
                'text-[10px] px-2 py-0.5 rounded-full font-medium'
              ]"
            >
              {{ task.type }}
            </span>

            <span class="text-[10px] text-gray-400">
              {{ task.time }}
            </span>
          </div>
        </div>
      </div>

      <span
        v-if="task.completed"
        class="text-green-600 text-xs font-bold py-1.5 px-2"
      >
        已完成
      </span>
<button
  v-else
  :class="[
    task.buttonClass,
    'px-4 py-1.5 rounded-full text-xs font-bold transition-all duration-200 active:scale-95'
  ]"
  @click="router.push('/focus-timer')"
>
  开始
</button>
    </div>
  </div>
</template>