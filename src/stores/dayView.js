import { defineStore } from 'pinia'
import { getDayTimelineApi } from '@/api/day'

export const useDayViewStore = defineStore('dayView', {
  state: () => ({
    currentDate: '',

    currentTitle: '',

    timeline: [],

    loading: false,

    error: null,
  }),

  actions: {
    /**
     * 获取日程时间轴
     */
    async fetchTimeline(date) {
      this.loading = true

      this.error = null

      try {
        const res = await getDayTimelineApi(date)

        /**
         * 后端统一返回:
         * {
         *   code,
         *   message,
         *   data
         * }
         */
        if (res.code !== 200) {
          throw new Error(res.message)
        }

        const data = res.data

        this.currentDate = data.currentDate

        this.currentTitle = data.currentTitle

        /**
         * 数据映射
         * 后端字段 → 前端统一字段
         */
        this.timeline = (data.timeline || []).map((item) => {
          /**
           * 空闲时间块
           */
          if (item.type === 'free') {
            return {
              id: item.id,

              type: 'free',

              startTime: item.start_time,

              endTime: item.end_time,

              duration: item.duration || 0,

              text: item.text || '',
            }
          }

          /**
           * 课程
           */
          if (item.type === 'course') {
            return {
              id: item.id,

              type: 'course',

              startTime: item.start_time,

              endTime: item.end_time,

              title: item.title,

              location: item.location,

              teacher: item.teacher || '',

              description: item.description || '',

              reviewDone: item.review_done ?? false,
            }
          }

          /**
           * 已完成课程
           */
          if (item.type === 'finished-course') {
            return {
              id: item.id,

              type: 'finished-course',

              startTime: item.start_time,

              endTime: item.end_time,

              title: item.title,

              location: item.location || '',
            }
          }

          /**
           * 进行中任务
           */
          if (item.type === 'active-task') {
            return {
              id: item.id,

              type: 'active-task',

              startTime: item.start_time,

              endTime: item.end_time,

              title: item.title,

              icon: item.icon || 'mdi:clock-outline',
            }
          }

          /**
           * 普通任务
           */
          return {
            id: item.id,

            type: 'task',

            startTime: item.start_time,

            endTime: item.end_time,

            title: item.title,

            icon: item.icon || 'mdi:book-open-page-variant',

            link: item.link || '',

            description: item.description || '',
          }
        })
      } catch (error) {
        console.error('获取时间轴失败:', error)

        this.error = error.message || '获取时间轴失败'
      } finally {
        this.loading = false
      }
    },
  },
})