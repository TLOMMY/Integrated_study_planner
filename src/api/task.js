import request from './request'

/**
 * 获取任务列表
 */
export const getTaskListApi = (params = {}) => {
  return request({
    url: '/task/list',
    method: 'GET',
    params,
  })
}

/**
 * 获取任务详情
 */
export const getTaskDetailApi = (id) => {
  return request({
    url: `/task/detail/${id}`,
    method: 'GET',
  })
}

/**
 * 创建任务
 */
export const createTaskApi = (data) => {
  return request({
    url: '/task/create',
    method: 'POST',
    data,
  })
}

/**
 * 更新任务
 */
export const updateTaskApi = (id, data) => {
  return request({
    url: `/task/update/${id}`,
    method: 'PUT',
    data,
  })
}

/**
 * 完成任务
 */
export const completeTaskApi = (id) => {
  return request({
    url: `/task/complete/${id}`,
    method: 'PUT',
  })
}

/**
 * 删除任务
 */
export const deleteTaskApi = (id) => {
  return request({
    url: `/task/delete/${id}`,
    method: 'DELETE',
  })
}