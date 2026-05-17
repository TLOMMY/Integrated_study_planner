import { defineStore } from 'pinia'
import { getUserInfoApi } from '@/api/user'

export const useUserStore = defineStore('user', {
  state: () => ({
    userInfo: {},
  }),

  actions: {
    async fetchUserInfo() {
      try {
        const res = await getUserInfoApi()

        this.userInfo = res.data
      } catch (error) {
        console.error('获取用户信息失败:', error)

        // fallback 数据
        this.userInfo = {
          name: '测试用户',
          username: '@guest',
          school: '未知学校',
          email: '暂无邮箱',
          avatar:
            'https://modao.cc/agent-py/media/generated_images/2026-04-19/7555cec16f8b43a088020c21170b905d.jpg',
        }
      }
    },
  },
})