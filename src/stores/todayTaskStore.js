import { defineStore } from 'pinia'
import { getTaskListApi } from '@/api/task'

export const useTodayTaskStore = defineStore('todayTask', {
  state: () => ({
    tasks: [],
    loading: false,
  }),

  actions: {
    async fetchTasks() {
      this.loading = true

      try {
        const res = await getTaskListApi()

        this.tasks = res.data || []
      } catch (error) {
        console.error('获取任务失败:', error)

        // fallback mock 数据
        this.tasks = [
          {
            id: 1,
            title: '高等数学',
            subject: '数学',
            progress: 75,
            duration: '2h',
          },
          {
            id: 2,
            title: '英语单词',
            subject: '英语',
            progress: 40,
            duration: '1h',
          },
          {
            id: 3,
            title: '数据结构',
            subject: '计算机',
            progress: 20,
            duration: '3h',
          },
        ]
      } finally {
        this.loading = false
      }
    },
  },
})