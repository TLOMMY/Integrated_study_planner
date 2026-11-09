/**
 * 提示条的显示规则（纯函数，便于测试）。
 * - 停留时间随文字长度增加：短提示保持调用方给的时长，长提示每多 1 个字多停 60ms，最多 9 秒；
 * - 失败提示按后端返回的 reason 附上"查看说明"，跳到使用手册的对应位置。
 */

const MS_PER_CHAR = 60
const SHORT_CHARS = 24
const MAX_MS = 9000

/** 按文字长度延长停留时间：不短于调用方给的时长，不长于 9 秒。 */
export const toastDuration = (message, base = 2400) => {
  const extra = Math.max(0, String(message || '').length - SHORT_CHARS) * MS_PER_CHAR
  return Math.min(Math.max(base, MAX_MS), base + extra)
}

/** 后端失败原因 → 使用手册锚点。 */
const HELP_BY_REASON = {
  ai_quota: { label: '查看说明', hash: '#ai' },
  no_model: { label: '查看说明', hash: '#ai' },
  model_error: { label: '查看说明', hash: '#ai' },
  timeout: { label: '查看说明', hash: '#ai' },
  no_vision: { label: '查看说明', hash: '#import-ai' },
  bad_output: { label: '查看说明', hash: '#import-ai' },
  no_courses: { label: '查看说明', hash: '#import' },
}

/** 从接口错误里找到对应的帮助链接；没有时返回 null。 */
export const helpForError = (error) => HELP_BY_REASON[error?.data?.reason] || null
