/**
 * 考试倒计时、课表分享、学习小组、断签保护、每周报告、专注同步的接口。
 * 只放本模块的接口；路径与后端路由一一对应，契约测试会扫描本文件。
 */
import http from './request'

export const examApi = {
  list: () => http.get('/exams'),
  create: (payload) => http.post('/exams', payload),
  update: (id, payload) => http.put(`/exams/${id}`, payload),
  remove: (id) => http.delete(`/exams/${id}`),
  // 导入考试安排：上传文件或粘贴文字，只返回预览；本地解析不出来时才用模型识别（最长约 2 分钟）
  importPreview: ({ file = null, text = null, providerId = null } = {}, onUploadProgress = null) => {
    const form = new FormData()
    if (file) form.append('file', file)
    else form.append('text', text || '')
    if (providerId) form.append('provider_id', providerId)
    return http.post('/import/exams', form, { timeout: 150000, onUploadProgress })
  },
  importCommit: (items) => http.post('/import/exams/commit', { items }),
}

export const shareApi = {
  create: () => http.post('/timetable/share'),
  preview: (code) => http.get(`/timetable/share/${encodeURIComponent(code)}`),
  importCourses: (code, payload) => http.post(`/timetable/share/${encodeURIComponent(code)}/import`, payload),
}

export const groupApi = {
  list: () => http.get('/groups'),
  create: (name) => http.post('/groups', { name }),
  join: (inviteCode) => http.post('/groups/join', { invite_code: inviteCode }),
  detail: (id) => http.get(`/groups/${id}`),
  leave: (id) => http.post(`/groups/${id}/leave`),
  dissolve: (id) => http.delete(`/groups/${id}`),
  resetCode: (id) => http.post(`/groups/${id}/invite-code`),
}

export const growthApi = {
  freezes: () => http.get('/streak/freezes'),
  subjects: (days = 30) => http.get('/study/subjects', { params: { days } }),
  weeklyReport: (weekStart) => http.get('/study/weekly-report', { params: { week_start: weekStart || undefined } }),
  // 每周 AI 复盘：{week_start, week_end, stats, review_markdown, suggestions, provider, model, generated_at}
  aiReview: (weekStart, refresh = false) =>
    http.get('/ai/review/weekly', { params: { week_start: weekStart || undefined, refresh: refresh ? 1 : undefined }, timeout: 90000 }),
}

export const focusSyncApi = {
  get: () => http.get('/study/focus-state', { skipAuthRedirect: true }),
  put: (payload) => http.put('/study/focus-state', payload, { skipAuthRedirect: true }),
}

export default http
