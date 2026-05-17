import { defineStore } from 'pinia'
import { generatePlanApi } from '@/api/ai'

export const useAiStore = defineStore('ai', {
  state: () => ({
    messages: [],
    generatedPlan: null,
    thinking: false,
    error: null,
  }),

  actions: {
    async sendMessage(text) {
      const content = text?.trim?.()

      if (!content || this.thinking) return

      this.error = null
      this.generatedPlan = null

      // user message
      this.messages.push({
        id: Date.now(),
        role: 'user',
        content,
      })

      this.thinking = true

      try {
        const res = await generatePlanApi({
          goal: content,
        })

        // 保存计划
        this.generatedPlan =
          res?.data?.plan || res?.data || null

        // ai reply
        this.messages.push({
          id: Date.now() + 1,
          role: 'assistant',
          content: this.generatedPlan
            ? '已为你生成学习计划。'
            : '暂未生成学习计划。',
        })

      } catch (error) {
        console.error(error)

        this.error = 'AI 服务暂时不可用'

        this.messages.push({
          id: Date.now() + 2,
          role: 'assistant',
          content: 'AI 服务暂时不可用，请稍后再试。',
        })
      } finally {
        this.thinking = false
      }
    },
  },
})