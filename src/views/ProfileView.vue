<script setup>
import { Icon } from '@iconify/vue'
import { useRouter } from 'vue-router'
import { onMounted } from 'vue'
import { useUserStore } from '@/stores/user'
const router = useRouter()
const userStore = useUserStore()

onMounted(() => {
  userStore.fetchUserInfo()
})

const stats = [
  {
    label: '学习天数',
    value: '128',
    color: 'text-blue-600',
  },
  {
    label: '专注小时',
    value: '42',
    color: 'text-indigo-600',
  },
  {
    label: '掌握词汇',
    value: '1.2w',
    color: 'text-orange-600',
  },
]

const securityMenus = [
  {
    icon: 'lucide:mail',
    iconColor: 'text-blue-500',
    title: '邮箱地址',
  },
  {
    icon: 'lucide:lock',
    iconColor: 'text-indigo-500',
    title: '修改密码',
    arrow: true,
  },
]

const preferenceMenus = [
  {
    icon: 'lucide:bell',
    iconColor: 'text-orange-500',
    title: '推送通知',
    switch: true,
  },
  {
    icon: 'lucide:palette',
    iconColor: 'text-pink-500',
    title: '外观主题',
    value: '浅色模式',
  },
]

const logout = () => {
  console.log('退出登录')
}

const goBack = () => {
  router.back()
}
</script>

<template>
  <div
    class="w-full h-[812px] overflow-y-auto scrollbar-hide bg-white pb-[100px]"
  >
    <!-- 顶部 -->
    <div
      class="px-6 pt-12 pb-8 bg-gradient-to-br from-blue-50 to-indigo-50 relative overflow-hidden"
    >
           <div
        class="absolute -right-20 -top-20 w-64 h-64 bg-blue-100/50 rounded-full blur-3xl"
      ></div>

      <div
        class="absolute -left-20 -bottom-20 w-48 h-48 bg-indigo-100/30 rounded-full blur-2xl"
      ></div>

      <div class="relative z-10 flex flex-col items-center">
        <div class="relative">
          <div
            class="w-24 h-24 rounded-full border-4 border-white shadow-xl overflow-hidden"
          >
           <img
             :src="userStore.userInfo?.avatar || 'https://modao.cc/agent-py/media/generated_images/2026-04-19/7555cec16f8b43a088020c21170b905d.jpg'"
              alt=""
             class="w-full h-full object-cover"
           />
          </div>

          <button
            class="absolute bottom-0 right-0 bg-blue-600 text-white p-1.5 rounded-full border-2 border-white shadow-sm"
          >
            <Icon icon="lucide:pencil" width="14" />
          </button>
        </div>

        <h2>
          {{ userStore.userInfo?.name || '未登录用户' }}
        </h2>

        <p>
          {{ userStore.userInfo?.username || '@guest' }}
          ·
          {{ userStore.userInfo?.school || '未知学校' }}
        </p>

        <div class="flex gap-4 mt-6 w-full px-4">
          <div
            v-for="item in stats"
            :key="item.label"
            class="flex-1 bg-white rounded-2xl p-3 shadow-sm border border-gray-100 flex flex-col items-center"
          >
        <span
            class="text-lg font-bold"
            :class="item.color"
            >
          {{ item.value }}
        </span>

            <span
              class="text-[8px] text-gray-400 font-bold uppercase tracking-widest"
            >
              {{ item.label }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- 内容 -->
    <div class="px-6 py-4 space-y-6">
      <!-- 账号安全 -->
      <div>
        <h3
          class="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-3 ml-1"
        >
          账号安全
        </h3>

        <div class="space-y-1 bg-gray-50 rounded-3xl p-2">
          <div
            v-for="item in securityMenus"
            :key="item.title"
            class="flex items-center justify-between p-3 bg-white rounded-2xl shadow-sm border border-gray-50"
          >
            <div class="flex items-center gap-3">
              <Icon
                :icon="item.icon"
                width="18"
                :class="item.iconColor"
              />

              <span class="text-sm font-medium text-gray-700">
                {{ item.title }}
              </span>
            </div>

            <template v-if="item.arrow">
              <Icon
                icon="lucide:chevron-right"
                width="16"
                class="text-gray-300"
              />
            </template>

            <template v-else>
             <span class="text-xs text-gray-400">
             {{
                item.title === '邮箱地址'
                ? userStore.userInfo?.email || '暂无邮箱'
                : item.value
             }}
             </span>
            </template>
          </div>
        </div>
      </div>

      <!-- 偏好设置 -->
      <div>
        <h3
          class="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-3 ml-1"
        >
          偏好设置
        </h3>

        <div class="space-y-1 bg-gray-50 rounded-3xl p-2">
          <div
            v-for="item in preferenceMenus"
            :key="item.title"
            class="flex items-center justify-between p-3 bg-white rounded-2xl shadow-sm border border-gray-50"
          >
            <div class="flex items-center gap-3">
              <Icon
                :icon="item.icon"
                width="18"
                :class="item.iconColor"
              />

              <span class="text-sm font-medium text-gray-700">
                {{ item.title }}
              </span>
            </div>

            <template v-if="item.switch">
              <div class="w-10 h-6 bg-blue-600 rounded-full relative">
                <div
                  class="absolute top-1 right-1 w-4 h-4 bg-white rounded-full"
                ></div>
              </div>
            </template>

            <template v-else>
              <span class="text-xs text-gray-400">
                {{ item.value }}
              </span>
            </template>
          </div>
        </div>
      </div>

      <!-- 底部 -->
      <div class="space-y-3">
        <button
          class="w-full flex items-center justify-between p-4 bg-gray-50 rounded-2xl"
        >
          <div class="flex items-center gap-3">
            <Icon
              icon="lucide:help-circle"
              width="18"
              class="text-gray-500"
            />

            <span class="text-sm font-bold text-gray-700">
              帮助中心
            </span>
          </div>
        </button>

        <button
          @click="logout"
          class="w-full py-4 bg-red-50 text-red-600 font-black text-sm rounded-2xl flex items-center justify-center gap-2 border border-red-100/50"
        >
          退出登录
        </button>

        <p class="text-center text-[10px] text-gray-300 py-4">
          学业管家 v2.4.0 (2026.04.19)
        </p>
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
</style>