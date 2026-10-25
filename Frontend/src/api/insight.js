/**
 * AI 扩展：每周 AI 复盘、PDF 讲义提取章节的接口。（联网搜索只给后端智能体用，没有前端接口）
 * 只放本模块的接口；路径与后端路由一一对应，契约测试会扫描本文件。
 */
import http from './request'

export const insightApi = {
  /**
   * 每周 AI 复盘。params: { week_start?: 'YYYY-MM-DD'（该周任意一天，默认上一完整周）, refresh?: 0 | 1 }
   * 返回 { week_start, week_end, stats, review_markdown, suggestions, provider, model, generated_at, cached, in_progress }
   */
  weeklyReview: (params = {}) => http.get('/ai/review/weekly', { params, timeout: 60000 }),
  /**
   * 上传 PDF 讲义，提取章节树与复习时长估算；模型整理较慢，超时放宽到 90 秒。
   * 返回 { file_name, pages, words, source, chapters: [{title, pages:[from,to], words, est_minutes, children?}], total_minutes, provider, model }
   */
  materialsOutline: (file) => {
    const form = new FormData()
    form.append('file', file)
    return http.post('/ai/materials/outline', form, { timeout: 90000 })
  },
}

export const { weeklyReview, materialsOutline } = insightApi

export default http
