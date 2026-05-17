<script setup>
import { ref, onMounted } from 'vue'
import { Icon } from '@iconify/vue'
import { useRouter } from 'vue-router'
import { useTodayTaskStore } from '@/stores/todayTaskStore'

import TaskCard from '@/components/today-task/TaskCard.vue'
import AddTaskModal from '@/components/today-task/AddTaskModal.vue'

const store = useTodayTaskStore()

const router = useRouter()

const showModal = ref(false)

const toggleModal = (show) => {
  showModal.value = show
}

onMounted(() => {
  store.fetchTasks()
})

</script>

<template>
  <div class="w-full h-full flex flex-col overflow-hidden bg-slate-50">
    <!-- 滚动区域 -->
    <div class="flex-1 overflow-y-auto scrollbar-hide">
      <div class="px-6 pt-10 pb-28">
        <!-- 顶部 -->
        <div class="pb-4 border-b border-slate-100">
          <div class="flex justify-between items-start">
            <div>
              <h2 class="text-gray-500 text-sm font-medium">
                2026年4月19日 周日
              </h2>

              <h1 class="text-2xl font-bold text-gray-900 mt-1">
                你好, 博文! 👋
              </h1>
            </div>

            <div
              class="bg-blue-50 p-2 rounded-xl text-blue-600 flex items-center gap-1"
            >
              <Icon icon="lucide:cloud-sun" width="20" />

              <span class="text-sm font-bold">22°</span>
            </div>
          </div>

          <!-- 概览 -->
          <div
            class="mt-6 bg-gradient-to-br from-blue-600 to-indigo-700 rounded-3xl p-5 text-white shadow-lg shadow-blue-200"
          >
            <div class="flex justify-between items-center">
              <div>
                <p class="opacity-80 text-xs">
                  今日概览
                </p>

                <p class="text-lg font-bold mt-1">
                  2 节课程 · {{ store.tasks.length }} 个任务
                </p>
              </div>

              <div
                class="h-12 w-12 rounded-full border-4 border-white/20 flex items-center justify-center relative"
              >
                <span class="text-sm font-bold">60%</span>

                <svg class="absolute inset-0 w-full h-full -rotate-90">
                  <circle
                    cx="24"
                    cy="24"
                    r="20"
                    fill="none"
                    stroke="white"
                    stroke-width="4"
                    stroke-dasharray="125"
                    stroke-dashoffset="50"
                  />
                </svg>
              </div>
            </div>
          </div>
        </div>

        <!-- 今日任务 -->
        <div class="mt-6">
          <div class="flex justify-between items-center mb-4">
            <h3 class="font-bold text-gray-800">
              今日任务
            </h3>

            <button
              class="text-blue-600 flex items-center gap-1 text-sm font-medium"
              @click="toggleModal(true)"
            >
              <Icon icon="lucide:plus-circle" width="18" />

              添加任务
            </button>
          </div>

          <div class="space-y-4">
            <TaskCard
              v-for="task in store.tasks"
              :key="task.id"
              :task="task"
            />

            <!-- AI -->
            <div
              class="bg-indigo-50 border border-indigo-100 rounded-2xl p-5 relative overflow-hidden"
            >
              <div class="relative z-10">
                <h4 class="font-bold text-indigo-900 text-sm">
                  问问 AI 助手？
                </h4>

                <p class="text-xs text-indigo-600 mt-1">
                  今天下午有空档，要生成备考计划吗？
                </p>

               <button
  class="mt-3 inline-block bg-indigo-600 text-white text-[10px] font-bold px-4 py-1.5 rounded-full shadow-sm"
  @click="router.push('/ai')"
>
  立即咨询
</button>
              </div>

              <Icon
                icon="lucide:sparkles"
                width="80"
                class="absolute -right-2 -bottom-2 text-indigo-200 opacity-50"
              />
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 弹窗 -->
    <AddTaskModal
      :show="showModal"
      @close="() => toggleModal(false)"
    />
  </div>

</template>

<style scoped>
.scrollbar-hide::-webkit-scrollbar {
  display: none;
}

.scrollbar-hide {
  scrollbar-width: none;
}
</style>