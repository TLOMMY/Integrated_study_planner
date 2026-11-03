/**
 * 语音输入：网页端用 Web Speech API（zh-CN），安卓 App 用 @capgo/capacitor-speech-recognition。
 * - speechSupport：响应式的"当前环境能否语音输入"，不支持时界面不显示麦克风按钮
 *   （Electron 外壳、Firefox、安卓里没有语音识别服务的设备都不显示）
 * - useSpeech({ onText })：start / stop / toggle；识别中通过 onText(base, spoken) 实时回传文字
 */
import { onBeforeUnmount, ref } from 'vue'
import { isNativeApp } from '@/api/server'
import { collectResults, speechErrorMessage, webSpeechCtor } from '@/utils/speech'
import { useUiStore } from '@/stores/ui'

export const speechSupport = ref(typeof window !== 'undefined' && !isNativeApp() && Boolean(webSpeechCtor(window)))

let pluginPromise = null
const loadPlugin = () =>
  (pluginPromise ||= import('@capgo/capacitor-speech-recognition')
    .then(async ({ SpeechRecognition }) => {
      const { available } = await SpeechRecognition.available()
      return available ? SpeechRecognition : null
    })
    .catch(() => null))

// 原生 App：插件可用且设备有语音识别服务才显示按钮
if (typeof window !== 'undefined' && isNativeApp()) loadPlugin().then((plugin) => (speechSupport.value = Boolean(plugin)))

// 同一时间只允许一个输入框在听写
let activeStop = null

export function useSpeech({ onText, onEnd } = {}) {
  const ui = useUiStore()
  const listening = ref(false)
  let recognition = null
  let listeners = []
  let finalText = ''

  const report = (code, native = false) => {
    const message = speechErrorMessage(code, { native })
    if (message) ui.toast(message, 'warning', 3600)
  }

  const finish = () => {
    if (!listening.value) return
    listening.value = false
    if (activeStop === stop) activeStop = null
    onEnd?.()
  }

  // ------------------------------------------------------------ 网页
  const startWeb = (base) => {
    const Ctor = webSpeechCtor(window)
    if (!Ctor) return ui.toast('当前浏览器不支持语音输入，可以换 Chrome / Edge 或直接打字', 'warning')
    if (navigator.onLine === false) return ui.toast('语音识别需要联网，请检查网络后再试', 'warning')
    recognition = new Ctor()
    recognition.lang = 'zh-CN'
    recognition.continuous = true
    recognition.interimResults = true
    recognition.onresult = (event) => {
      const { final, interim } = collectResults(event.results)
      onText?.(base, final + interim)
    }
    recognition.onerror = (event) => report(event.error)
    recognition.onend = () => {
      recognition = null
      finish()
    }
    try {
      recognition.start()
      listening.value = true
    } catch {
      recognition = null
      ui.toast('语音识别启动失败，请稍后再试', 'warning')
    }
  }

  // ------------------------------------------------------------ 安卓 App
  const startNative = async (base) => {
    const plugin = await loadPlugin()
    if (!plugin) return ui.toast('这台设备没有可用的语音识别服务', 'warning')
    try {
      let { speechRecognition } = await plugin.checkPermissions()
      if (speechRecognition !== 'granted') ({ speechRecognition } = await plugin.requestPermissions())
      if (speechRecognition !== 'granted') return report('not-allowed', true)
    } catch {
      return report('not-allowed', true)
    }
    finalText = ''
    listeners = await Promise.all([
      plugin.addListener('partialResults', (event) => {
        finalText = event.accumulatedText || event.accumulated || event.matches?.[0] || finalText
        onText?.(base, finalText)
      }),
      plugin.addListener('error', (event) => report(event.code, true)),
      plugin.addListener('listeningState', (event) => {
        if (event.state === 'stopped' || event.status === 'stopped') cleanupNative()
      }),
    ])
    listening.value = true
    try {
      await plugin.start({ language: 'zh-CN', partialResults: true, popup: false, addPunctuation: true, maxResults: 1 })
    } catch (error) {
      report(error?.message || error, true)
      cleanupNative()
    }
  }

  const cleanupNative = () => {
    listeners.forEach((l) => l?.remove?.())
    listeners = []
    finish()
  }

  // ------------------------------------------------------------ 对外
  const start = (base = '') => {
    if (listening.value) return
    activeStop?.()
    activeStop = stop
    if (isNativeApp()) startNative(base)
    else startWeb(base)
  }

  function stop() {
    if (!listening.value) return
    if (recognition) {
      try {
        recognition.stop()
      } catch {
        finish()
      }
      return
    }
    if (isNativeApp()) {
      loadPlugin().then((plugin) => plugin?.stop().catch(() => {}))
      // 有的设备 stop 后不再发 stopped 事件，稍后兜底收尾
      setTimeout(() => listening.value && cleanupNative(), 1500)
    }
  }

  const toggle = (base) => (listening.value ? stop() : start(base))

  onBeforeUnmount(() => {
    if (recognition) recognition.abort?.()
    else if (listening.value) stop()
  })

  return { listening, start, stop, toggle }
}
