/**
 * 全部后端接口。每个函数直接返回信封里的 data；失败时抛出 ApiError（见 request.js）。
 * 路径与后端 FastAPI 路由一一对应，可在 http://127.0.0.1:8000/docs 查看完整契约。
 */
import http from './request'

const noRedirect = { skipAuthRedirect: true }

export const authApi = {
  login: (identifier, password) => http.post('/auth/login', { identifier, password }, noRedirect),
  register: (payload) => http.post('/auth/register', payload, noRedirect),
  demo: () => http.post('/auth/demo', null, noRedirect),
  refresh: () => http.post('/auth/refresh', null, noRedirect),
}

export const userApi = {
  me: () => http.get('/users/me'),
  update: (payload) => http.put('/users/me', payload),
  changePassword: (payload) => http.put('/users/me/password', payload),
  changeEmail: (payload) => http.put('/users/me/email', payload),
  changePhone: (payload) => http.put('/users/me/phone', payload),
  logoutAll: () => http.post('/users/me/logout-all'),
  studyPrefs: () => http.get('/users/me/study-prefs'),
  saveStudyPrefs: (payload) => http.put('/users/me/study-prefs', payload),
  exportData: () => http.get('/users/me/export', { timeout: 30000 }),
  deleteAccount: (password) => http.delete('/users/me', { data: { password } }),
}

export const feedbackApi = {
  submit: (payload) => http.post('/feedback', payload),
}

export const homeApi = {
  summary: (date) => http.get('/home/summary', { params: { date } }),
}

export const taskApi = {
  list: (params) => http.get('/task/list', { params }),
  detail: (id) => http.get(`/task/detail/${id}`),
  create: (payload) => http.post('/task/create', payload),
  update: (id, payload) => http.put(`/task/update/${id}`, payload),
  complete: (id) => http.put(`/task/complete/${id}`),
  uncomplete: (id) => http.put(`/task/uncomplete/${id}`),
  remove: (id) => http.delete(`/task/delete/${id}`),
  search: (q) => http.get('/task/list', { params: { view: 'all', q } }),
  batch: (payload) => http.post('/task/batch', payload),
}

export const timetableApi = {
  get: (week) => http.get('/timetable', { params: { week } }),
  create: (payload) => http.post('/timetable', payload),
  update: (id, payload) => http.put(`/timetable/${id}`, payload),
  remove: (id) => http.delete(`/timetable/${id}`),
  saveSettings: (payload) => http.put('/timetable/settings', payload),
  importFile: (file, mode = 'preview', selected = null) => {
    const form = new FormData()
    form.append('file', file)
    if (selected) form.append('selected', selected.join(','))
    return http.post('/import/timetable', form, { params: { mode, replace: true }, timeout: 30000 })
  },
  // 教务网页：保存的 .html/.mhtml，或把粘贴的源代码包装成文件上传（避开表单字段 1MB 限制）
  importWeb: (file, mode = 'preview', selected = null) => {
    const form = new FormData()
    form.append('file', file)
    if (selected) form.append('selected', selected.join(','))
    return http.post('/import/timetable/web', form, { params: { mode, replace: true }, timeout: 30000 })
  },
  // 图片 / PDF 交给大模型识别，只返回预览；视觉模型较慢，超时放宽到 90 秒
  recognize: (file, providerId = null) => {
    const form = new FormData()
    form.append('file', file)
    if (providerId) form.append('provider_id', providerId)
    return http.post('/import/timetable/ai', form, { timeout: 90000 })
  },
  // 提交预览里勾选的课程（AI 识别结果），服务器重新校验后写入，不会再次调用模型
  commitCourses: (payload) => http.post('/import/timetable/commit', payload),
}

export const dayApi = {
  timeline: (date) => http.get('/day/timeline', { params: { date } }),
}

export const studyApi = {
  record: (payload) => http.post('/study/record', payload),
  stats: () => http.get('/study/stats'),
  leaderboard: () => http.get('/study/leaderboard'),
}

export const planApi = {
  list: (status = 'all') => http.get('/study-plans', { params: { status } }),
  detail: (id) => http.get(`/study-plans/${id}`),
  create: (payload) => http.post('/study-plans', payload),
  update: (id, payload) => http.put(`/study-plans/${id}`, payload),
  remove: (id) => http.delete(`/study-plans/${id}`),
  restore: (ids) => http.post('/study-plans/trash/restore', { ids }),
  purge: (ids) => http.post('/study-plans/trash/purge', { ids }),
  emptyTrash: () => http.delete('/study-plans/trash'),
}

export const aiApi = {
  health: () => http.get('/ai/health'),
  // 大模型生成较慢，单独放宽超时（后端默认 45 秒）
  draft: (payload) => http.post('/ai/plan', payload, { timeout: 60000 }),
  commit: (draft) => http.post('/ai/plan/commit', draft),
  settings: () => http.get('/ai/settings'),
  activate: (active) => http.put('/ai/settings', { active }),
  createProvider: (payload) => http.post('/ai/providers', payload),
  updateProvider: (id, payload) => http.put(`/ai/providers/${id}`, payload),
  removeProvider: (id) => http.delete(`/ai/providers/${id}`),
  testProvider: (payload) => http.post('/ai/providers/test', payload, { timeout: 30000 }),
  listModels: (payload) => http.post('/ai/providers/models', payload, { timeout: 30000 }),
}
