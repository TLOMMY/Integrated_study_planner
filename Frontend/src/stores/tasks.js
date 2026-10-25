import { defineStore } from 'pinia'
import { taskApi } from '@/api'
import { plannerApi } from '@/api/planner'
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
    // 首页按清单 / 标签筛选（一次只选一个）：{ kind: 'list' | 'tag', name }，null 表示全部
    filter: null,
    groups: { lists: [], tags: [] },
    // 任务每变化一次 +1，提醒模块据此重新拉取 / 重排系统通知
    version: 0,
  }),

  getters: {
    todayOpen: (state) => state.today.filter((task) => !task.completed),
    todayDone: (state) => state.today.filter((task) => task.completed),
    filterParams: (state) => {
      if (!state.filter) return {}
      return state.filter.kind === 'tag' ? { tag: state.filter.name } : { list_name: state.filter.name }
    },
  },

  actions: {
    async loadToday() {
      this.loading = true
      try {
        const date = todayStr()
        const [today, overdue] = await Promise.all([
          taskApi.list({ view: 'today', date, ...this.filterParams }),
          taskApi.list({ view: 'overdue', date, ...this.filterParams }),
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
      const data = await taskApi.list({ view, date: todayStr(), ...this.filterParams })
      this[view] = data.items
      this.counts = data.counts
    },

    range(start, end) {
      return taskApi.list({ view: 'range', start, end }).then((data) => data.items)
    },

    async loadGroups() {
      this.groups = await plannerApi.groups()
      // 筛选的清单 / 标签已经不存在（被改名、删除）时回到全部
      const f = this.filter
      if (f && !(f.kind === 'tag' ? this.groups.tags : this.groups.lists).some((g) => g.name === f.name)) this.filter = null
      return this.groups
    },

    setFilter(filter) {
      this.filter = filter
      return this.loadToday()
    },

    /** 任务变化后同步首页卡片与列表（静默，不打断用户）。 */
    afterChange() {
      this.version++
      useHomeStore().refresh()
      this.loadGroups().catch(() => {})
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

    /** 勾选某个子任务（列表里快速勾选）：先改界面，失败时回滚。 */
    async toggleChecklistItem(task, itemId) {
      const before = task.checklist.map((item) => ({ ...item }))
      const next = before.map((item) => (item.id === itemId ? { ...item, done: !item.done } : item))
      Object.assign(task, { checklist: next, checklist_done: next.filter((item) => item.done).length })
      try {
        const saved = await plannerApi.saveChecklist(task.id, next)
        Object.assign(task, { checklist: saved.checklist, checklist_done: saved.checklist_done, checklist_total: saved.checklist_total })
      } catch (error) {
        Object.assign(task, { checklist: before, checklist_done: before.filter((item) => item.done).length })
        useUiStore().fail(error)
      }
    },

    /** 批量删除 / 移动（due_date 指定日期，或 shift_days 顺延 N 天；保留原来的时刻与时长）。 */
    async batch(payload, message) {
      const result = await taskApi.batch(payload)
      useUiStore().success(message || `已处理 ${result.count} 个任务`)
      await this.afterChange()
      return result
    },

    /**
     * 日程拖拽改期：改日期走 batch move（保留时刻、时长，提醒随之平移），改开始时间走 update。
     * 返回撤销函数。
     */
    async reschedule(task, { due_date: dueDate, start_time: startTime }) {
      const before = { due_date: task.due_date, start_time: task.start_time }
      if (startTime !== undefined && startTime !== task.start_time) {
        await taskApi.update(task.id, { due_date: dueDate || task.due_date, start_time: startTime })
      } else if (dueDate && dueDate !== task.due_date) {
        await taskApi.batch({ ids: [task.id], action: 'move', due_date: dueDate })
      } else {
        return null
      }
      this.afterChange()
      // 撤销：把日期与时刻一起改回原样（提醒会按同样的偏移平移回去）
      return async () => {
        await taskApi.update(task.id, before)
        await this.afterChange()
      }
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
