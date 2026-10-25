/**
 * 任务扩展：子任务、标签与清单、提醒、拖拽改期的接口。
 * 只放本模块的接口；路径与后端路由一一对应，契约测试会扫描本文件。
 */
import http from './request'

export const plannerApi = {
  /** 清单与标签：{ lists: [{name,total,open}], tags: [...] } */
  groups: () => http.get('/task/lists'),
  /** kind: 'list' | 'tag'；新名字已存在时合并 */
  renameGroup: (kind, oldName, newName) => http.put('/task/lists/rename', { kind, old_name: oldName, new_name: newName }),
  /** 只去掉名字，任务保留 */
  removeGroup: (kind, name) => http.delete(`/task/lists/${encodeURIComponent(name)}`, { params: { kind } }),
  /** 整体保存子任务 [{id,title,done}] */
  saveChecklist: (id, checklist) => http.put(`/task/checklist/${id}`, { checklist }),
  /** 未来 days 天内需要提醒的未完成任务 */
  reminders: (days = 7) => http.get('/task/reminders', { params: { days } }),
}

export default http
