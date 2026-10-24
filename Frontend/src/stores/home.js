import { defineStore } from 'pinia'
import { homeApi } from '@/api'
import { useGameStore } from './game'

export const useHomeStore = defineStore('home', {
  state: () => ({
    summary: null,
    loading: false,
    error: '',
  }),

  actions: {
    async load({ silent = false } = {}) {
      if (!silent) this.loading = true
      this.error = ''
      try {
        this.summary = await homeApi.summary()
        useGameStore().apply(this.summary)
      } catch (error) {
        this.error = error.message
        if (!silent) throw error
      } finally {
        this.loading = false
      }
    },
    refresh() {
      return this.load({ silent: true }).catch(() => {})
    },
  },
})
