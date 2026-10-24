import { defineStore } from 'pinia'
import { aiApi } from '@/api'
import { useUiStore } from './ui'
import { useTasksStore } from './tasks'
import { useTimetableStore } from './timetable'

const LIMIT = 40
const HISTORY = 20

/** 把一版计划压缩成给模型看的文字摘要：标题、范围、每天的学习块（每天最多列 4 个）。 */
const summarize = (m) => {
  const d = m.draft
  if (!d) return (m.text || '').slice(0, 500)
  const days = new Map()
  for (const t of d.tasks || []) {
    if (!days.has(t.date)) days.set(t.date, [])
    days.get(t.date).push(`${t.start_time} ${t.title} ${t.duration_minutes}分`)
  }
  const lines = [...days.entries()].map(([date, items]) => `${date.slice(5)}：${items.slice(0, 4).join('；')}${items.length > 4 ? `等${items.length}个` : ''}`)
  const courses = (d.courses || []).map((c) => `${c.course_name} 周${c.day_of_week} ${c.start_period}-${c.end_period}节`)
  return [
    `【上一版计划】${d.title}（${d.start_date} 至 ${d.end_date}，每天 ${d.daily_minutes} 分钟，科目：${(d.subjects || []).join('、')}）`,
    ...lines,
    courses.length ? `课程：${courses.join('；')}` : '',
    m.saved ? '（学生已导入此计划）' : '',
    `建议摘要：${(d.advice || '').replace(/\s+/g, ' ').slice(0, 300)}`,
  ].filter(Boolean).join('\n').slice(0, 1500)
}
let seq = Date.now()

// v2：回复拆为 advice + 结构化 plan，旧格式的本地记录不再兼容
const storageKey = (userId) => `ai-chat-v2-${userId}`

/** 快捷调整：在上一次请求参数上打补丁再重新生成。 */
export const ADJUSTMENTS = [
  { key: 'variant', label: '换一版', icon: 'lucide:shuffle' },
  { key: 'lighter', label: '轻松一点', icon: 'lucide:feather' },
  { key: 'harder', label: '再多一点', icon: 'lucide:flame' },
  { key: 'evening', label: '只排晚上', icon: 'lucide:moon' },
  { key: 'longer', label: '延长一周', icon: 'lucide:calendar-plus' },
]

const patch = (request, draft, key) => {
  const next = { ...request, start_date: draft.start_date, days: draft.days, daily_minutes: draft.daily_minutes }
  if (key === 'variant') next.variant = (request.variant || 0) + 1
  if (key === 'lighter') next.daily_minutes = Math.max(30, Math.round(draft.daily_minutes * 0.7))
  if (key === 'harder') next.daily_minutes = Math.min(360, Math.round(draft.daily_minutes * 1.3))
  if (key === 'evening') next.prefer = 'evening'
  if (key === 'longer') next.days = Math.min(31, draft.days + 7)
  return next
}

export const useAiStore = defineStore('ai', {
  state: () => ({
    userId: null,
    messages: [],
    thinking: false,
    engine: { provider: 'rule', label: '本地规则引擎' },
    settings: null,
  }),

  actions: {
    init(userId) {
      if (this.userId === userId) return
      this.userId = userId
      try {
        this.messages = JSON.parse(localStorage.getItem(storageKey(userId)) || '[]')
      } catch {
        this.messages = []
      }
      this.refreshEngine()
    },

    refreshEngine() {
      return aiApi.health().then((data) => (this.engine = data)).catch(() => {})
    },

    persist() {
      if (!this.userId) return
      localStorage.setItem(storageKey(this.userId), JSON.stringify(this.messages.slice(-LIMIT)))
    },

    clear() {
      this.messages = []
      this.persist()
    },

    /**
     * 最近 10 轮（20 条）对话。助手回合除了建议，还附上那一版计划的摘要（日期范围、每天安排），
     * 模型追问时才"记得"自己排过什么——之前只传 6 条且只有建议文字，3-4 轮后就会丢失要点。
     */
    history() {
      return this.messages
        .filter((m) => !m.error)
        .slice(-HISTORY)
        .map((m) => ({ role: m.role, content: m.role === 'assistant' ? summarize(m) : m.text.slice(0, 500) }))
    },

    /** 上一版计划的结构化记忆（科目、日期范围、时长、偏好、要点），追问时由后端在此基础上修改。 */
    memory() {
      const last = [...this.messages].reverse().find((m) => m.role === 'assistant' && m.draft?.memory)
      return last?.draft.memory || null
    },

    async ask(text) {
      const message = text.trim()
      if (!message || this.thinking) return
      const history = this.history()
      const memory = this.memory()
      this.messages.push({ id: ++seq, role: 'user', text: message })
      await this.run({ message, history, memory })
    },

    async adjust(draftMessage, key) {
      const label = ADJUSTMENTS.find((item) => item.key === key)?.label || '调整'
      const history = this.history()
      this.messages.push({ id: ++seq, role: 'user', text: label })
      await this.run({ ...patch(draftMessage.request, draftMessage.draft, key), history, memory: draftMessage.draft.memory || null })
    },

    async run(request) {
      this.thinking = true
      this.persist()
      try {
        const draft = await aiApi.draft(request)
        const { history, memory, ...stored } = request
        this.messages.push({ id: ++seq, role: 'assistant', text: draft.reply, draft, request: stored, saved: false })
        this.refreshEngine()
      } catch (error) {
        this.messages.push({ id: ++seq, role: 'assistant', text: error.message || 'AI 服务暂时不可用', error: true })
      } finally {
        this.thinking = false
        this.persist()
      }
    },

    /** 采纳：tasks 为用户勾选的那几天的学习块；课程可单独选择是否导入。 */
    async adopt(message, { tasks = message.draft.tasks, importCourses = true } = {}) {
      const ui = useUiStore()
      const { draft } = message
      const result = await aiApi.commit({
        title: draft.title,
        goal: draft.goal,
        summary: draft.summary,
        advice: draft.advice,
        start_date: draft.start_date,
        end_date: draft.end_date,
        days: draft.days,
        provider: draft.provider,
        model: draft.model,
        insights: draft.insights,
        tasks,
        courses: draft.courses || [],
        import_tasks: tasks.length > 0,
        import_courses: importCourses,
      })
      message.saved = true
      message.planId = result.plan?.id || null
      message.result = {
        tasks: result.plan?.task_total || 0,
        courses: result.courses_saved.length,
        skipped: result.courses_skipped,
      }
      this.persist()
      ui.reward(result.reward)
      ui.success(`已加入：${[message.result.tasks && `${message.result.tasks} 个任务`, message.result.courses && `${message.result.courses} 门课程`].filter(Boolean).join('、') || '无'}`)
      if (result.courses_skipped.length) ui.toast(`${result.courses_skipped.length} 门课程与现有课表冲突，已跳过`, 'warning', 3600)
      useTasksStore().afterChange()
      if (result.courses_saved.length) useTimetableStore().load().catch(() => {})
      return result
    },

    // ---------------------------------------------------------------- 模型设置
    async loadSettings() {
      this.settings = await aiApi.settings()
      this.engine = this.settings.resolved
      return this.settings
    },
    async applySettings(promise, message) {
      this.settings = await promise
      this.engine = this.settings.resolved
      if (message) useUiStore().success(message)
      return this.settings
    },
    activate(active) {
      return this.applySettings(aiApi.activate(active), '已切换模型')
    },
    saveProvider(payload, id = null) {
      return this.applySettings(id ? aiApi.updateProvider(id, payload) : aiApi.createProvider(payload), id ? '已保存' : '已添加并启用')
    },
    async removeProvider(provider) {
      const ok = await useUiStore().confirm({ title: '删除模型配置', message: `确定删除「${provider.name}」吗？`, confirmText: '删除', danger: true })
      if (!ok) return
      return this.applySettings(aiApi.removeProvider(provider.id), '已删除')
    },
  },
})
