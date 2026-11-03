import { defineStore } from 'pinia'
import { timetableApi } from '@/api'
import { ApiError } from '@/api/request'
import { examApi } from '@/api/growth'
import { useUiStore } from './ui'

export const useTimetableStore = defineStore('timetable', {
  state: () => ({
    data: null,
    week: null,
    loading: false,
    exams: [],
    pastExams: [],
    examsLoaded: false,
  }),

  getters: {
    courses: (state) => state.data?.courses || [],
    courseNames: (state) => [...new Set((state.data?.courses || []).map((c) => c.course_name))],
    meta: (state) => state.data,
    /** 多套课表：{ active_id, active_name, items: [{id,name,is_active,semester,course_count}], max } */
    sets: (state) => state.data?.sets || { active_id: null, active_name: '我的课表', items: [], max: 12 },
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

    // ------------------------------------------------------------ 考试倒计时
    async loadExams() {
      const data = await examApi.list()
      this.exams = data.upcoming
      this.pastExams = data.past
      this.examsLoaded = true
      return data
    },

    async saveExam(payload, id = null) {
      if (id) await examApi.update(id, payload)
      else await examApi.create(payload)
      useUiStore().success(id ? '考试已更新' : '考试已添加')
      await this.loadExams()
    },

    async removeExam(exam) {
      const ui = useUiStore()
      const ok = await ui.confirm({ title: '删除考试', message: `确定删除「${exam.title}」吗？`, confirmText: '删除', danger: true })
      if (!ok) return false
      await examApi.remove(exam.id)
      ui.success('考试已删除')
      await this.loadExams()
      return true
    },

    /** 导入分享课表后直接用返回的课表刷新。 */
    applyPayload(data) {
      if (!data) return
      this.data = data
      this.week = data.week
    },

    // ------------------------------------------------------------ 多套课表
    /** 新建一套课表并（默认）切换过去。 */
    async createSet(payload) {
      const data = await timetableApi.createSet(payload)
      this.week = null
      this.applyPayload(data)
      useUiStore().success(payload.activate === false ? `已新建「${payload.name}」` : `已新建并切换到「${payload.name}」`)
      return data
    },

    async renameSet(set, name) {
      this.applyPayload(await timetableApi.renameSet(set.id, name))
      useUiStore().success('课表已重命名')
    },

    async activateSet(set) {
      if (!set.id || set.is_active) return
      this.applyPayload(await timetableApi.activateSet(set.id))
      useUiStore().success(`已切换到「${set.name}」`)
    },

    /** 整套删除：二次确认，说明会删掉多少门课。 */
    async removeSet(set) {
      const ui = useUiStore()
      const last = (this.data?.sets?.items || []).filter((s) => s.id).length <= 1
      const ok = await ui.confirm({
        title: `删除课表「${set.name}」？`,
        message: `将删除这套课表及其中的 ${set.course_count} 门课程，无法恢复。${set.is_active ? (last ? '删除后课表为空，可重新导入或新建。' : '删除后会自动切换到另一套课表。') : ''}`,
        confirmText: '整套删除',
        danger: true,
      })
      if (!ok) return false
      this.applyPayload(await timetableApi.removeSet(set.id))
      ui.success(`已删除「${set.name}」`)
      return true
    },
  },
})
