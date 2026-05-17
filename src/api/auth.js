import request from './request'

// 登录
export const loginApi = (data) => {
  return request({
    url: '/auth/login',
    method: 'POST',
    data,
  })
}

// 注册
export const registerApi = (data) => {
  return request({
    url: '/auth/register',
    method: 'POST',
    data,
  })
}