import request from './request'

/**
 * 提交学习记录
 */
export const recordStudyApi = (data) => {
  return request({
    url: '/study/record',
    method: 'post',
    data,
  })
}