<script setup>
defineProps({
  show: Boolean
})

const emit = defineEmits(['close'])
</script>

<template>
<transition name="fade">
<div
  v-if="show"
  class="absolute inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-end"
  @click="emit('close')"
>
    <div
      class="bg-white w-full rounded-t-[32px] p-6 animate-slide-up"
    >
      <div class="w-12 h-1 bg-gray-200 rounded-full mx-auto mb-6" />

      <h3 class="text-xl font-bold text-gray-900 mb-6">
        添加新任务
      </h3>

      <div class="space-y-4">
        <div>
          <label
            class="text-xs font-bold text-gray-400 uppercase tracking-wider"
          >
            任务名称
          </label>

          <input
            type="text"
            placeholder="例如：复习线性代数"
            class="w-full mt-1 px-4 py-3 bg-gray-50 rounded-xl border-none focus:ring-2 focus:ring-blue-500 outline-none text-sm"
          />
        </div>

        <div class="grid grid-cols-2 gap-4">
          <div>
            <label
              class="text-xs font-bold text-gray-400 uppercase tracking-wider"
            >
              开始时间
            </label>

            <input
              type="time"
              value="14:00"
              class="w-full mt-1 px-4 py-3 bg-gray-50 rounded-xl border-none text-sm"
            />
          </div>

          <div>
            <label
              class="text-xs font-bold text-gray-400 uppercase tracking-wider"
            >
              预估时长
            </label>

            <select
              class="w-full mt-1 px-4 py-3 bg-gray-50 rounded-xl border-none text-sm"
            >
              <option>30 分钟</option>
              <option selected>1 小时</option>
              <option>2 小时</option>
            </select>
          </div>
        </div>

        <div>
          <label
            class="text-xs font-bold text-gray-400 uppercase tracking-wider"
          >
            快捷模板
          </label>

          <div class="flex gap-2 mt-2">
            <span
              class="px-3 py-1.5 bg-blue-50 text-blue-600 rounded-full text-xs font-medium border border-blue-100 cursor-pointer"
            >
              预习
            </span>

            <span
              class="px-3 py-1.5 bg-green-50 text-green-600 rounded-full text-xs font-medium border border-green-100 cursor-pointer"
            >
              复习
            </span>

            <span
              class="px-3 py-1.5 bg-orange-50 text-orange-600 rounded-full text-xs font-medium border border-orange-100 cursor-pointer"
            >
              作业
            </span>
          </div>
        </div>
      </div>

      <div class="flex gap-3 mt-8 pb-4">
        <button
          class="flex-1 py-4 bg-gray-100 text-gray-600 font-bold rounded-2xl"
          @click="emit('close')"
        >
          取消
        </button>

        <button
          class="flex-1 py-4 bg-blue-600 text-white font-bold rounded-2xl shadow-lg shadow-blue-200"
          @click="emit('close')"
        >
          确认添加
        </button>
      </div>
    </div>
  </div>
  </transition>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: all 0.25s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.animate-slide-up {
  animation: slideUp 0.25s ease-out;
}

@keyframes slideUp {
  from {
    transform: translateY(100%);
  }

  to {
    transform: translateY(0);
  }
}
</style>