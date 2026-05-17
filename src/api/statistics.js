import request from './request'

export const getStatisticsApi = () => {
  return request({
    url: '/study/stats',
    method: 'GET',
  })
}