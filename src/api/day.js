import request from './request'

/**
 * 获取日视图时间轴
 */
export const getDayTimelineApi = (date) => {
  return request({
    url: '/day/timeline',
    method: 'GET',

    params: {
      date,
    },
  })
}