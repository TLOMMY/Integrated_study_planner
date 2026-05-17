import { ref, onBeforeUnmount } from 'vue'

export function useFocusTimer(callback) {
  const timer = ref(null)

  const start = () => {
    stop()

    timer.value = setInterval(() => {
      callback?.()
    }, 1000)
  }

  const stop = () => {
    if (timer.value) {
      clearInterval(timer.value)
      timer.value = null
    }
  }

  onBeforeUnmount(() => {
    stop()
  })

  return {
    start,
    stop,
  }
}