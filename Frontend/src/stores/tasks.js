import { defineStore } from 'pinia'
import { taskApi } from '@/api'
import { todayStr } from '@/utils/dates'
import { useHomeStore } from './home'
import { useUiStore } from './ui'

const emptyCounts = () => ({ today: 0, today_done: 0, overdue: 0, upcoming: 0, completed: 0 })

export const useTasksStore = defineStore('tasks', {
  state: () => ({
    today: [],
    overdue: [],
    upcoming: [],
    completed: [],
    counts: emptyCounts(),
    loading: false,
    loaded: false,
  }),

  getters: {
    todayOpen: (state) => state.today.filter((task) => !task.completed),
    todayDone: (state) => state.today.filter((task) => task.completed),
  },

  actions: {
    async loadToday() {
      this.loading = true
      try {
        const date = todayStr()
        const [today, overdue] = await Promise.all([
          taskApi.list({ view: 'today', date }),
          taskApi.list({ view: 'overdue', date }),
        ])
        this.today = today.items
        this.overdue = overdue.items
        this.counts = today.counts
        this.loaded = true
      } finally {
        this.loading = false
      }
    },

    async loadView(view) {
      const data = await taskApi.list({ view, date: todayStr() })
      this[view] = data.items
      this.counts = data.counts
    },

    range(start, end) {
      return taskApi.list({ view: 'range', start, end }).then((data) => data.items)
    },

    /** 任务变化后同步首页卡片与列表（静默，不打断用户）。 */
    afterChange() {
      useHomeStore().refresh()
      return this.loadToday().catch(() => {})
    },

    async create(payload) {
      const task = await taskApi.create(payload)
      useUiStore().success('已添加任务')
      await this.afterChange()
      return task
    },

    async update(id, payload) {
      const task = await taskApi.update(id, payload)
      useUiStore().success('已保存')
      await this.afterChange()
      return task
    },

    async remove(task) {
      const ui = useUiStore()
      const ok = await ui.confirm({ title: '删除任务', message: `确定删除「${task.title}」吗？`, confirmText: '删除', danger: true })
      if (!ok) return false
      await taskApi.remove(task.id)
      ui.success('已删除')
      await this.afterChange()
      return true
    },

    /** 勾选 / 取消勾选。先改界面再请求，失败时回滚并返回 false。 */
    async toggle(task) {
      const ui = useUiStore()
      const next = !task.completed
      task.completed = next
      try {
        if (next) {
          const result = await taskApi.complete(task.id)
          ui.reward(result.reward)
          if (result.next_task) ui.toast(`已生成下一次：${result.next_task.due_date}`, 'info')
        } else {
          await taskApi.uncomplete(task.id)
          ui.toast('已恢复为未完成', 'info')
        }
      } catch (error) {
        task.completed = !next
        ui.fail(error)
        return false
      }
      await this.afterChange()
      return true
    },

    /** 批量删除 / 移动（due_date 指定日期，或 shift_days 顺延 N 天；保留原来的时刻与时长）。 */
    async batch(payload, message) {
      const result = await taskApi.batch(payload)
      useUiStore().success(message || `已处理 ${result.count} 个任务`)
      await this.afterChange()
      return result
    },

    /** 把逾期任务一次性挪到今天。 */
    async moveOverdueToToday() {
      const date = todayStr()
      await Promise.all(this.overdue.map((task) => taskApi.update(task.id, { due_date: date })))
      useUiStore().success(`已将 ${this.overdue.length} 个任务移到今天`)
      await this.afterChange()
    },
  },
})
