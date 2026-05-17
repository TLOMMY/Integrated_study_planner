import request from '@/utils/request'

export const getTaskList = () => {
  return request({
    url: '/tasks',
    method: 'GET',
  })
}