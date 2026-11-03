/**
 * 语音输入的纯函数部分：环境判断、识别文字合并、错误提示。界面与识别流程见 composables/useSpeech.js。
 */

/** Electron 外壳里的 webkitSpeechRecognition 需要 Google 的 Key，实际不可用。 */
export const isElectronUA = (ua = '') => /\bElectron\//.test(ua)

/**
 * 网页端能否用 Web Speech API：有构造函数、不是 Electron、不是原生 App（App 走插件）。
 * win 用参数传入，便于测试。
 */
export function webSpeechCtor(win) {
  if (!win || win.Capacitor?.isNativePlatform?.()) return null
  if (isElectronUA(win.navigator?.userAgent || '')) return null
  return win.SpeechRecognition || win.webkitSpeechRecognition || null
}

/**
 * 把识别到的文字接到输入框原有内容后面。
 * base：开始识别时输入框里已有的文字；spoken：本次识别的全部文字（已确认 + 正在识别）。
 * 中文之间不加空格；原文末尾是英文 / 数字且识别结果以英文 / 数字开头时补一个空格。
 */
export function mergeTranscript(base, spoken) {
  const head = String(base || '')
  const tail = String(spoken || '').trim()
  if (!tail) return head
  if (!head) return tail
  const needSpace = /[A-Za-z0-9]$/.test(head) && /^[A-Za-z0-9]/.test(tail)
  return head + (needSpace ? ' ' : '') + tail
}

/** Web Speech 的 results 列表 → { final, interim }。 */
export function collectResults(results) {
  let final = ''
  let interim = ''
  for (let i = 0; i < (results?.length || 0); i++) {
    const result = results[i]
    const text = result?.[0]?.transcript || ''
    if (result?.isFinal) final += text
    else interim += text
  }
  return { final, interim }
}

/** 识别错误 → 中文提示；返回 '' 表示不需要提示（如用户主动停止）。 */
export function speechErrorMessage(code, { native = false } = {}) {
  const value = String(code || '').toLowerCase()
  // aborted：网页端主动停止；client：安卓识别器在停止时常报的客户端错误，都不需要提示
  if (value === 'aborted' || value === 'client') return ''
  if (value.includes('not-allowed') || value.includes('permission') || value.includes('denied') || value === 'service-not-allowed' || value === 'insufficient_permissions') {
    return native ? '没有麦克风权限：请到 手机设置 → 应用 → 学业管家 → 权限 中允许使用麦克风' : '没有麦克风权限：请点地址栏左侧的站点设置，允许使用麦克风后再试'
  }
  if (value.includes('network')) return '语音识别需要联网，请检查网络后再试'
  if (value.includes('no-speech') || value.includes('no_match') || value.includes('no match') || value.includes('speech_timeout')) return '没有听清，请靠近麦克风再说一次'
  if (value.includes('audio-capture') || value.includes('audio')) return '没有找到可用的麦克风'
  if (value.includes('language')) return '当前设备不支持中文语音识别'
  if (value.includes('busy')) return '语音识别正忙，请稍后再试'
  return '语音识别出错了，请重试或直接打字'
}
