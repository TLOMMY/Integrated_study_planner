/**
 * 管理后台、问题反馈、邮箱验证码、前端错误上报的接口。
 * 只放本模块的接口；路径与后端路由一一对应，契约测试会扫描本文件。
 */
import http from './request'

export const adminApi = {
  // 反馈
  feedbackList: (params) => http.get('/admin/feedback', { params }),
  feedbackDetail: (id) => http.get(`/admin/feedback/${id}`),
  feedbackStatus: (id, status) => http.put(`/admin/feedback/${id}/status`, { status }),
  feedbackReply: (id, payload) => http.post(`/admin/feedback/${id}/reply`, payload),
  // 用户
  users: (params) => http.get('/admin/users', { params }),
  user: (id) => http.get(`/admin/users/${id}`),
  updateUser: (id, payload) => http.put(`/admin/users/${id}`, payload),
  resetPassword: (id) => http.post(`/admin/users/${id}/reset-password`),
  // 看板与错误
  dashboard: () => http.get('/admin/dashboard'),
  errors: (params) => http.get('/admin/errors', { params }),
  removeError: (id) => http.delete(`/admin/errors/${id}`),
  // 设置
  settings: () => http.get('/admin/settings'),
  saveSettings: (payload) => http.put('/admin/settings', payload),
  testNotify: () => http.post('/admin/settings/test-notify', null, { timeout: 30000 }),
}

export default http
