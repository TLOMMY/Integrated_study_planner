import { defineStore } from 'pinia'
import { getTimetableApi } from '@/api/timetable'

export const useTimetableStore = defineStore('timetable', {
  state: () => ({
    semester: '',
    weekInfo: '',

    days: [],

    sections: [],

    loading: false,

    error: null,
  }),

  actions: {
    async fetchTimetable() {
      this.loading = true
      this.error = null

      try {
        const res = await getTimetableApi()

        /**
         * 后端统一格式：
         * {
         *   code,
         *   message,
         *   data
         * }
         */
const result = res.data

if (result.code !== 200) {
  this.error = result.message || '获取课表失败'
  return
}

const data = result.data || {}

        const data = res.data || {}

        this.semester = data.semester || ''
        this.weekInfo = data.weekInfo || ''

        this.days = data.days || []

        this.sections = data.sections || []
      } catch (error) {
        console.log(error)

        this.error = '网络异常'
      } finally {
        this.loading = false
      }
    },
  },
})