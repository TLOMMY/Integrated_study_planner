/**
 * AI 对话输入框里"待发送"的附件：选好就开始上传（显示进度），失败可重试，发送前可删。
 * 图片用本地 blob 地址立刻显示缩略图，不用等上传完；发送后的消息里改用服务器地址。
 */
import { computed, reactive } from 'vue'
import { agentApi } from '@/api/agent'
import { useUiStore } from '@/stores/ui'

export const MAX_ATTACHMENTS = 4
export const MAX_BYTES = 10 * 1024 * 1024
export const IMAGE_ACCEPT = 'image/png,image/jpeg,image/webp,image/gif,image/bmp'
export const FILE_ACCEPT = '.pdf,.docx,.pptx,.xlsx,.xls,.csv,.txt,.md,application/pdf'
const FILE_EXT = /\.(pdf|docx|pptx|xlsx|xls|csv|txt|md|markdown)$/i
const OLD_OFFICE = /\.(doc|ppt)$/i

let seq = 0

export const isImageFile = (file) => /^image\//.test(file?.type || '') || /\.(png|jpe?g|webp|gif|bmp)$/i.test(file?.name || '')

export function useChatAttachments(conversationId = () => null) {
  const ui = useUiStore()
  const items = reactive([])

  const upload = async (item) => {
    item.status = 'uploading'
    item.progress = 0
    item.error = ''
    try {
      const data = await agentApi.uploadAttachment(item.file, conversationId(), (event) => {
        if (event.total) item.progress = Math.min(99, Math.round((event.loaded / event.total) * 100))
      })
      Object.assign(item, { ...data, key: item.key, localUrl: item.localUrl, file: item.file, status: 'ready', progress: 100 })
    } catch (error) {
      item.status = 'error'
      item.error = error?.message || '上传失败'
    }
  }

  const add = (files) => {
    for (const file of Array.from(files || [])) {
      if (items.length >= MAX_ATTACHMENTS) {
        ui.toast(`一次最多 ${MAX_ATTACHMENTS} 个附件`, 'warning')
        break
      }
      if (OLD_OFFICE.test(file.name)) {
        ui.toast(`「${file.name}」是旧版格式，请另存为 .docx / .pptx 再发`, 'warning', 3600)
        continue
      }
      const image = isImageFile(file)
      if (!image && !FILE_EXT.test(file.name)) {
        ui.toast(`暂不支持「${file.name}」：可以发图片、PDF、Word、PPT、表格和文本`, 'warning', 3600)
        continue
      }
      if (file.size > MAX_BYTES) {
        ui.toast(`「${file.name}」超过 10MB`, 'warning')
        continue
      }
      const item = reactive({
        key: `att-${++seq}`, id: null, name: file.name || (image ? '图片' : '文件'), kind: image ? 'image' : 'file',
        size: file.size, pages: null, scanned: false, localUrl: image ? URL.createObjectURL(file) : '',
        file, status: 'uploading', progress: 0, error: '',
      })
      items.push(item)
      upload(item)
    }
  }

  const remove = (item) => {
    const index = items.indexOf(item)
    if (index === -1) return
    items.splice(index, 1)
    if (item.localUrl) URL.revokeObjectURL(item.localUrl)
    // 已上传的待发送附件顺手删掉（失败不要紧，服务器一天后会自动清理）
    if (item.id) agentApi.removeAttachment(item.id).catch(() => {})
  }

  const uploading = computed(() => items.some((i) => i.status === 'uploading'))
  const ready = computed(() => items.filter((i) => i.status === 'ready'))

  /** 发送用：已上传附件的信息（消息气泡里显示用）。 */
  const snapshot = () =>
    ready.value.map((i) => ({ id: i.id, name: i.name, kind: i.kind, size: i.size, pages: i.pages, scanned: i.scanned, has_preview: i.kind === 'image', localUrl: i.localUrl }))

  /** 消息已发出：从附件栏移走这些附件；本地缩略图还在气泡里用，一分钟后再释放。 */
  const clearSent = (list) => {
    const ids = new Set(list.map((i) => i.id))
    for (const item of [...items]) if (ids.has(item.id)) items.splice(items.indexOf(item), 1)
    setTimeout(() => list.forEach((i) => i.localUrl && URL.revokeObjectURL(i.localUrl)), 60000)
  }

  return { items, add, remove, retry: upload, snapshot, clearSent, uploading, ready }
}
