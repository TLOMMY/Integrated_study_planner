import request from './request'

export const getUserInfoApi = () => {
  return request({
    url: '/user/me',
    method: 'GET',
  })
}