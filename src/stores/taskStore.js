import { defineStore } from 'pinia'
import { getTaskListApi, completeTaskApi } from '@/api/task'

export const useTaskStore = defineStore('task', {
  state: () => ({
    tasks: [],
    loading: false,
  }),

  actions: {
    /**
     * 获取任务列表
     */
    async fetchTasks() {
      try {
        this.loading = true

        const res = await getTaskListApi()

        this.tasks = res.data
      } catch (error) {
        console.error('获取任务失败:', error)
      } finally {
        this.loading = false
      }
    },

    /**
     * 完成任务
     */
    async completeTask(id) {
      try {
        await completeTaskApi(id)

        const task = this.tasks.find(item => item.id === id)

        if (task) {
          task.completed = true
        }
      } catch (error) {
        console.error('完成任务失败:', error)
      }
    }
  }
})