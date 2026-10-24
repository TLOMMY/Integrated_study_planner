import { defineStore } from 'pinia'
import { timetableApi } from '@/api'
import { ApiError } from '@/api/request'
import { useUiStore } from './ui'

export const useTimetableStore = defineStore('timetable', {
  state: () => ({
    data: null,
    week: null,
    loading: false,
  }),

  getters: {
    courses: (state) => state.data?.courses || [],
    courseNames: (state) => [...new Set((state.data?.courses || []).map((c) => c.course_name))],
    meta: (state) => state.data,
  },

  actions: {
    async load(week = this.week) {
      this.loading = !this.data
      try {
        this.data = await timetableApi.get(week || undefined)
        this.week = this.data.week
      } finally {
        this.loading = false
      }
      return this.data
    },

    async ensure() {
      if (!this.data) await this.load()
      return this.data
    },

    /** 保存课程；遇到时间冲突（409）时询问是否仍要保存。 */
    async saveCourse(payload, id = null) {
      const ui = useUiStore()
      const send = (body) => (id ? timetableApi.update(id, body) : timetableApi.create(body))
      try {
        await send(payload)
      } catch (error) {
        if (!(error instanceof ApiError) || error.status !== 409) throw error
        const ok = await ui.confirm({ title: '课程时间冲突', message: `${error.message}。确定仍要保存吗？`, confirmText: '仍然保存' })
        if (!ok) return false
        await send({ ...payload, force: true })
      }
      ui.success(id ? '课程已更新' : '课程已添加')
      await this.load()
      return true
    },

    async removeCourse(course) {
      const ui = useUiStore()
      const ok = await ui.confirm({ title: '删除课程', message: `确定删除「${course.course_name}」（${course.week_text}）吗？`, confirmText: '删除', danger: true })
      if (!ok) return false
      await timetableApi.remove(course.id)
      ui.success('课程已删除')
      await this.load()
      return true
    },

    async saveSettings(payload) {
      this.data = await timetableApi.saveSettings(payload)
      this.week = this.data.week
      useUiStore().success('学期设置已保存')
    },
  },
})
