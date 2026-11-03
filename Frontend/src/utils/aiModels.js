/**
 * 模型名称显示：与后端 providers.MODEL_LABELS 保持一致。
 * deepseek-flash → DeepSeek V4.1 Flash（快），deepseek-v4-pro → DeepSeek V4 Pro（强），其余原样。
 */
export const MODEL_LABELS = {
  'deepseek-flash': 'DeepSeek V4.1 Flash（快）',
  'deepseek-v4-pro': 'DeepSeek V4 Pro（强）',
}

export const modelLabel = (model) => {
  const key = String(model || '').trim()
  return MODEL_LABELS[key.toLowerCase()] || key
}

/**
 * 把"名称 · 模型名"这类标签里的模型名换成友好名（旧消息里保存的是原始模型名）。
 * 例："DeepSeek（服务器配置） · deepseek-v4-pro" → "DeepSeek（服务器配置） · DeepSeek V4 Pro（强）"
 */
export const friendlyLabel = (label) => {
  const text = String(label || '')
  const index = text.lastIndexOf(' · ')
  if (index === -1) return modelLabel(text)
  return `${text.slice(0, index)} · ${modelLabel(text.slice(index + 3))}`
}
