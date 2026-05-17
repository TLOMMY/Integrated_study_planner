<script setup>
import { ref } from 'vue'
import { Icon } from '@iconify/vue'
import { useTimetableStore } from '@/stores/timetable'

const timetableStore = useTimetableStore()

const showImportPanel = ref(false)

const importActions = [
  {
    title: '拍照解析',
    icon: 'lucide:camera',
    iconClass: 'text-blue-600',
  },
  {
    title: 'PDF/文件',
    icon: 'lucide:file-text',
    iconClass: 'text-indigo-600',
  },
]
</script>

<template>
  <div class="relative w-full h-full bg-white overflow-hidden">
    <!-- 顶部导航 -->
    <div
      class="h-[88px] px-6 pt-10 pb-4 flex justify-between items-center bg-white border-b border-slate-100"
    >
      <div>
        <h1 class="text-xl font-bold text-gray-900">
          {{ timetableStore.semester }}
        </h1>

        <p class="text-xs text-gray-400 font-medium">
          {{ timetableStore.weekInfo }}
        </p>
      </div>

      <div class="flex gap-2">
        <button
          class="w-10 h-10 bg-gray-50 rounded-full flex items-center justify-center text-gray-600"
        >
          <Icon icon="lucide:settings-2" width="20" />
        </button>

        <button
          class="w-10 h-10 bg-blue-600 rounded-full flex items-center justify-center text-white shadow-lg shadow-blue-100"
          @click="showImportPanel = true"
        >
          <Icon icon="lucide:plus" width="22" />
        </button>
      </div>
    </div>

    <!-- 内容区域 -->
    <div class="h-[644px] overflow-y-auto scrollbar-hide pb-24">
      <!-- 导入课表 -->
      <div
        v-if="showImportPanel"
        class="px-6 py-4 bg-blue-50/50 border-b border-blue-100"
      >
        <h3
          class="text-sm font-bold text-blue-900 mb-3 flex items-center gap-2"
        >
          <Icon icon="lucide:sparkles" width="16" />
          智能导入课表
        </h3>

        <div class="grid grid-cols-2 gap-3">
          <button
            v-for="item in importActions"
            :key="item.title"
            class="bg-white p-3 rounded-2xl shadow-sm border border-blue-100 flex flex-col items-center gap-1.5 hover:border-blue-300"
          >
            <Icon
              :icon="item.icon"
              width="20"
              :class="item.iconClass"
            />

            <span class="text-[10px] font-bold text-gray-700">
              {{ item.title }}
            </span>
          </button>
        </div>

        <button
          class="w-full mt-3 py-2 text-[10px] font-bold text-blue-400"
          @click="showImportPanel = false"
        >
          稍后再说
        </button>
      </div>

      <!-- 课表 -->
      <div class="px-2 py-4">
        <div class="grid grid-cols-6 gap-1">
          <!-- 表头 -->
          <div class="h-10"></div>

          <div
            v-for="day in timetableStore.days"
            :key="day.week"
            class="text-center"
          >
            <span
              class="block text-[10px] font-bold"
              :class="
                day.active
                  ? 'text-blue-600 italic'
                  : 'text-gray-900'
              "
            >
              {{ day.week }}
            </span>

            <span
              class="text-[8px]"
              :class="
                day.active
                  ? 'text-blue-400'
                  : 'text-gray-400'
              "
            >
              {{ day.date }}
            </span>
          </div>

          <!-- 节次 -->
          <template
            v-for="section in timetableStore.sections"
            :key="section.id"
          >
            <!-- 时间 -->
            <div
              class="flex flex-col items-center justify-center text-[9px] text-gray-400 font-medium py-4"
            >
              <span>{{ section.start }}</span>

              <span
                class="h-4 border-l border-dashed border-gray-200 my-1"
              ></span>

              <span>{{ section.end }}</span>
            </div>

            <!-- 课程 -->
            <template
              v-for="(course, index) in section.courses"
              :key="index"
            >
              <div class="h-20">
                <div
                  v-if="course"
                  class="course-card"
                  :class="course.className"
                >
                  {{ course.name }}

                  <span class="opacity-70 mt-1">
                    {{ course.location }}
                  </span>
                </div>
              </div>
            </template>

            <!-- 午休 -->
            <div
              v-if="section.breakAfter"
              class="col-span-6 flex items-center justify-center py-2"
            >
              <div
                class="w-full border-t border-gray-50 flex items-center justify-center"
              >
                <span
                  class="bg-gray-50 px-3 text-[8px] text-gray-300 font-bold uppercase tracking-widest"
                >
                  Lunch Break
                </span>
              </div>
            </div>
          </template>
        </div>
      </div>

      <!-- AI 推荐 -->
      <div class="mt-8 px-6 text-center pb-8">
        <div
          class="bg-gray-50 rounded-2xl p-6 border-2 border-dashed border-gray-200"
        >
          <p
            class="text-xs text-gray-400 leading-relaxed font-medium"
          >
            周末无课？AI 建议你利用空闲时间
            <br />
            进行“六级单词速记”
          </p>

          <button
            class="mt-4 text-xs font-bold text-blue-600 flex items-center justify-center gap-1 mx-auto"
          >
            查看详细规划

            <Icon
              icon="lucide:chevron-right"
              width="14"
            />
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.scrollbar-hide::-webkit-scrollbar {
  display: none;
}

.scrollbar-hide {
  scrollbar-width: none;
}

.course-card {
  border-radius: 12px;
  padding: 6px;
  font-size: 10px;
  line-height: 1.2;
  font-weight: 600;
  text-align: center;
  display: flex;
  flex-direction: column;
  justify-content: center;
  height: 100%;
  transition: all 0.2s;
}

.course-blue {
  background-color: #eef2ff;
  color: #4338ca;
  border-left: 3px solid #6366f1;
}

.course-green {
  background-color: #f0fdf4;
  color: #15803d;
  border-left: 3px solid #22c55e;
}

.course-orange {
  background-color: #fffaf5;
  color: #c2410c;
  border-left: 3px solid #f97316;
}

.course-purple {
  background-color: #faf5ff;
  color: #7e22ce;
  border-left: 3px solid #a855f7;
}
</style>