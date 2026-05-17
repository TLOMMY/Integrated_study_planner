import request from './request'

/**
 * 获取课表
 */
export const getTimetableApi = (params) => {
  return request({
    url: '/timetable',
    method: 'GET',
    params,
  })
}