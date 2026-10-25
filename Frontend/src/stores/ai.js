import { defineStore } from 'pinia'
import { aiApi } from '@/api'
import { agentApi, canStream, streamChat } from '@/api/agent'
import { useUiStore } from './ui'
import { useTasksStore } from './tasks'
import { useTimetableStore } from './timetable'

// v2 版保存在浏览器本地的对话；首次进入时迁移成一条服务器会话后清除
const legacyKey = (userId) => `ai-chat-v2-${userId}`
const currentKey = (userId) => `ai-conv-${userId}`
let seq = 0

/** 旧版助手消息（advice + 结构化计划）压缩成一段文字，迁移后模型仍能看懂上下文。 */
const legacyText = (m) => {
  const d = m.draft
  if (!d) return (m.text || '').slice(0, 3800)
  const tasks = (d.tasks || []).slice(0, 12).map((t) => `${t.date.slice(5)} ${t.start_time} ${t.title}`)
  return [
    d.advice || m.text || '',
    `【当时的计划】${d.title}（${d.start_date} 至 ${d.end_date}）${m.saved ? '，已导入' : ''}`,
    tasks.join('；'),
  ].filter(Boolean).join('\n').slice(0, 3800)
}

const emptyMeta = () => ({ reasoning: '', tools: [], proposals: [], engine: '', model: '' })

export const useAiStore = defineStore('ai', {
  state: () => ({
    userId: null,
    loaded: false,
    conversations: [],
    currentId: null,
    messages: [],
    loadingMessages: false,
    streaming: false,
    controller: null,
    engine: { provider: 'rule', label: '本地规则引擎' },
    settings: null,
  }),

  getters: {
    current: (state) => state.conversations.find((c) => c.id === state.currentId) || null,
    // 兼容旧页面里的 ai.thinking
    thinking: (state) => state.streaming,
  },

  actions: {
    init(userId) {
      if (this.userId === userId) return
      this.$reset()
      this.userId = userId
      this.refreshEngine()
    },

    refreshEngine() {
      return aiApi.health().then((data) => (this.engine = data)).catch(() => {})
    },

    // ---------------------------------------------------------------- 会话
    async ensureLoaded() {
      if (this.loaded) return
      await this.migrateLegacy()
      await this.loadConversations()
      this.loaded = true
      const saved = Number(localStorage.getItem(currentKey(this.userId)))
      const target = this.conversations.find((c) => c.id === saved) || this.conversations[0]
      if (target) await this.select(target.id)
    },

    async loadConversations() {
      const data = await agentApi.list()
      this.conversations = data.items
    },

    async migrateLegacy() {
      if (!this.userId) return
      let old = []
      try {
        old = JSON.parse(localStorage.getItem(legacyKey(this.userId)) || '[]')
      } catch {
        old = []
      }
      const messages = old
        .filter((m) => !m.error && (m.text || m.draft))
        .slice(-80)
        .map((m) => ({ role: m.role === 'user' ? 'user' : 'assistant', content: m.role === 'user' ? String(m.text).slice(0, 3800) : legacyText(m) }))
        .filter((m) => m.content.trim())
      if (!messages.length) {
        localStorage.removeItem(legacyKey(this.userId))
        return
      }
      try {
        await agentApi.importLegacy({ title: '之前的对话', messages })
        localStorage.removeItem(legacyKey(this.userId))
      } catch (error) {
        console.warn('旧对话迁移失败，下次进入再试', error)
      }
    },

    async select(id) {
      if (this.streaming) return
      this.currentId = id
      localStorage.setItem(currentKey(this.userId), String(id))
      this.loadingMessages = true
      try {
        const data = await agentApi.messages(id)
        if (this.currentId === id) this.messages = data.items
      } catch (error) {
        useUiStore().fail(error)
        if (error.status === 404) {
          this.conversations = this.conversations.filter((c) => c.id !== id)
          this.newConversation()
        }
      } finally {
        this.loadingMessages = false
      }
    },

    /** 只清空界面；第一次发送时才在服务器上创建，避免产生一堆空对话。 */
    newConversation() {
      if (this.streaming) return
      this.currentId = null
      this.messages = []
      localStorage.removeItem(currentKey(this.userId))
    },

    async rename(id, title) {
      const data = await agentApi.rename(id, title)
      this.upsert(data)
    },

    async remove(conversation) {
      const ok = await useUiStore().confirm({
        title: '删除对话', message: `删除「${conversation.title}」？已导入的任务和课程不受影响。`, confirmText: '删除', danger: true,
      })
      if (!ok) return
      await agentApi.remove(conversation.id)
      this.conversations = this.conversations.filter((c) => c.id !== conversation.id)
      if (this.currentId === conversation.id) this.newConversation()
    },

    upsert(conversation, toTop = false) {
      if (!conversation) return
      const rest = this.conversations.filter((c) => c.id !== conversation.id)
      const index = this.conversations.findIndex((c) => c.id === conversation.id)
      if (toTop || index === -1) this.conversations = [conversation, ...rest]
      else this.conversations.splice(index, 1, conversation)
    },

    // ---------------------------------------------------------------- 对话
    async send(text) {
      const message = String(text || '').trim()
      if (!message || this.streaming) return
      const ui = useUiStore()
      this.streaming = true
      try {
        if (!this.currentId) {
          const created = await agentApi.create()
          this.upsert(created, true)
          this.currentId = created.id
          localStorage.setItem(currentKey(this.userId), String(created.id))
        }
      } catch (error) {
        this.streaming = false
        ui.fail(error)
        return
      }
      const conversationId = this.currentId
      this.messages.push({ id: `u${++seq}`, role: 'user', content: message, meta: {}, pending: true })
      this.messages.push({ id: `a${++seq}`, role: 'assistant', content: '', meta: emptyMeta(), live: true, status: '正在连接…' })
      const live = this.messages[this.messages.length - 1]
      const userTemp = this.messages[this.messages.length - 2]

      const finish = (data) => {
        if (this.currentId !== conversationId) return
        const index = this.messages.indexOf(live)
        if (data?.message && index !== -1) this.messages.splice(index, 1, data.message)
        const userIndex = this.messages.indexOf(userTemp)
        if (data?.user_message && userIndex !== -1) this.messages.splice(userIndex, 1, data.user_message)
        if (data?.conversation) this.upsert(data.conversation, true)
      }
      const onEvent = (event, data) => {
        if (event === 'status') live.status = data.text
        else if (event === 'reasoning') {
          live.meta.reasoning += data.delta
          live.status = '正在思考…'
        } else if (event === 'text') {
          // replace：后端把调工具前的过渡语移进了思考过程，用它覆盖正文
          if (typeof data.replace === 'string') live.content = data.replace
          live.content += data.delta
          live.status = ''
        } else if (event === 'tool') {
          const found = live.meta.tools.find((t) => t.id === data.id)
          if (found) Object.assign(found, data)
          else live.meta.tools.push({ ...data })
          live.status = data.status === 'running' ? `${data.label}…` : live.status
        } else if (event === 'proposal') {
          const list = live.meta.proposals
          const index = data.replaces ? list.findIndex((p) => p.id === data.replaces) : -1
          if (index !== -1) list.splice(index, 1, data.proposal)
          else list.push(data.proposal)
        } else if (event === 'error') {
          live.meta.error = data.message
        } else if (event === 'done') {
          finish(data)
        }
      }

      try {
        if (canStream()) {
          this.controller = new AbortController()
          await streamChat(conversationId, message, onEvent, { signal: this.controller.signal })
        } else {
          finish(await agentApi.chatSync(conversationId, message))
        }
      } catch (error) {
        if (error?.name === 'AbortError') {
          live.meta.error = '已停止生成'
        } else {
          live.meta.error = error.message || 'AI 服务暂时不可用'
        }
      } finally {
        live.live = false
        live.status = ''
        this.streaming = false
        this.controller = null
        this.refreshEngine()
      }
      // 中途停止 / 断网：以服务器保存的为准
      if (live.meta.error && this.currentId === conversationId && this.messages.includes(live)) {
        await new Promise((resolve) => setTimeout(resolve, 400))
        if (!this.streaming && this.currentId === conversationId) {
          const keep = live.meta.error
          await this.select(conversationId)
          const last = this.messages[this.messages.length - 1]
          if (!last || last.role !== 'assistant') {
            this.messages.push({ id: `a${++seq}`, role: 'assistant', content: '', meta: { ...emptyMeta(), error: keep } })
          }
        }
      }
    },

    stop() {
      this.controller?.abort()
    },

    /** 点选追问选项：标记已回答并作为下一条消息发送。 */
    answer(proposal, option) {
      if (this.streaming) return
      proposal.answered = option
      this.send(option)
    },

    /**
     * 导入提案：items 为用户编辑、勾选后的条目。逐条返回成功 / 失败原因，写回卡片。
     */
    async applyProposal(message, proposal, items) {
      const ui = useUiStore()
      const result = await agentApi.apply({
        kind: proposal.type,
        items,
        title: proposal.title || null,
        goal: proposal.summary || null,
        plan_id: proposal.plan_id || null,
        message_id: typeof message.id === 'number' ? message.id : null,
        proposal_id: proposal.id,
      })
      proposal.results = { ...(proposal.results || {}) }
      for (const r of result.results) if (r.key) proposal.results[r.key] = r
      proposal.applied = true
      if (result.plan?.id) proposal.plan_id = result.plan.id
      ui.reward(result.reward)
      if (result.ok_count && !result.fail_count) ui.success(`已导入 ${result.ok_count} 条`)
      else if (result.ok_count) ui.toast(`已导入 ${result.ok_count} 条，${result.fail_count} 条未导入，原因见卡片`, 'warning', 3600)
      else ui.toast('全部未能导入，请查看每条的原因并修改后重试', 'error', 3600)
      if (proposal.type !== 'courses') useTasksStore().afterChange()
      if (proposal.type !== 'tasks') useTimetableStore().load().catch(() => {})
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
    setThinking(thinking) {
      return this.applySettings(aiApi.setThinking(thinking), null)
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
