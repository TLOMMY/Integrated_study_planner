import request from './request'

/**
 * AI 生成学习计划
 */
export const generatePlanApi = (data) => {
  return request({
    url: '/ai/plan',
    method: 'POST',
    data
  })
}