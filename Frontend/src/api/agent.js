/**
 * AI 智能体对话（服务器保存的会话、流式回复、提案确认）的接口。
 * 只放本模块的接口；路径与后端路由一一对应，契约测试会扫描本文件。
 *
 * 流式对话不用 axios：用 fetch + ReadableStream 解析 SSE，地址走 apiBase()（App 外壳里也能用）。
 */
import http, { ApiError, tokenStorage } from './request'
import { apiBase } from './server'

export const agentApi = {
  list: () => http.get('/ai/conversations'),
  create: (title = null) => http.post('/ai/conversations', { title }),
  detail: (id) => http.get(`/ai/conversations/${id}`),
  rename: (id, title) => http.patch(`/ai/conversations/${id}`, { title }),
  remove: (id) => http.delete(`/ai/conversations/${id}`),
  messages: (id) => http.get(`/ai/conversations/${id}/messages`),
  importLegacy: (payload) => http.post('/ai/conversations/import', payload),
  // 非流式兜底（浏览器不支持 ReadableStream 时）
  chatSync: (id, message) => http.post(`/ai/conversations/${id}/chat/sync`, { message }, { timeout: 300000 }),
  apply: (payload) => http.post('/ai/proposals/apply', payload, { timeout: 30000 }),
}

/** 浏览器是否支持流式读取响应体。 */
export const canStream = () => typeof window !== 'undefined' && 'ReadableStream' in window && 'TextDecoder' in window

/**
 * 流式发送一条消息。onEvent(event, data) 依次收到 status / reasoning / text / tool / proposal / error / done。
 * 路径：POST /ai/conversations/{id}/chat（与 chatSync 相同的后端路由模块）。
 * 返回 Promise，结束（done 或连接断开）时 resolve；signal 可中止。
 */
export async function streamChat(id, message, onEvent, { signal } = {}) {
  const headers = { 'Content-Type': 'application/json', Accept: 'text/event-stream' }
  const token = tokenStorage.get()
  if (token) headers.Authorization = `Bearer ${token}`
  let response
  try {
    response = await fetch(`${apiBase()}/ai/conversations/${id}/chat`, {
      method: 'POST', headers, body: JSON.stringify({ message }), signal,
    })
  } catch (error) {
    if (error?.name === 'AbortError') throw error
    throw new ApiError(0, '无法连接服务器，请检查网络')
  }
  if (!response.ok || !response.body) {
    let payload = null
    try {
      payload = await response.json()
    } catch {
      /* 非 JSON 错误体 */
    }
    throw new ApiError(response.status, payload?.message || `请求失败（${response.status}）`, payload?.data)
  }
  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''
  const flush = (block) => {
    let event = 'message'
    const data = []
    for (const line of block.split('\n')) {
      if (line.startsWith('event:')) event = line.slice(6).trim()
      else if (line.startsWith('data:')) data.push(line.slice(5).trimStart())
    }
    if (!data.length) return
    try {
      onEvent(event, JSON.parse(data.join('\n')))
    } catch (error) {
      console.warn('SSE 事件解析失败', error)
    }
  }
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, '\n')
    let index
    while ((index = buffer.indexOf('\n\n')) !== -1) {
      flush(buffer.slice(0, index))
      buffer = buffer.slice(index + 2)
    }
  }
  if (buffer.trim()) flush(buffer)
}

export default http
