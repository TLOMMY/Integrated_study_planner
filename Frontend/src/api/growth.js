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
  // 每周 AI 复盘（代理 F 实现）：{week_start, week_end, stats, review_markdown, suggestions, provider, model, generated_at}
  aiReview: (weekStart, refresh = false) =>
    http.get('/ai/review/weekly', { params: { week_start: weekStart || undefined, refresh: refresh ? 1 : undefined }, timeout: 90000 }),
}

export const focusSyncApi = {
  get: () => http.get('/study/focus-state', { skipAuthRedirect: true }),
  put: (payload) => http.put('/study/focus-state', payload, { skipAuthRedirect: true }),
}

export default http
