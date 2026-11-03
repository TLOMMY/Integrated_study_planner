/**
 * 我的音乐：纯函数部分，不依赖浏览器，便于 node --test 单测。
 * 文件本体存在本机 IndexedDB（见 musicDb.js），播放见 musicPlayer.js。
 */

// 单个文件与总量上限（IndexedDB 一般能用磁盘剩余空间的一大部分，这里主动限制，避免把手机塞满）
export const MAX_FILE_BYTES = 30 * 1024 * 1024
export const MAX_TOTAL_BYTES = 300 * 1024 * 1024
export const MAX_TRACKS = 200
export const MAX_PLAYLISTS = 30
export const NAME_MAX = 40

// 扩展名 → 标准 MIME。"awv" 是常见的手误，按 wav 处理
const EXT_MIME = {
  mp3: 'audio/mpeg',
  wav: 'audio/wav',
  awv: 'audio/wav',
  ogg: 'audio/ogg',
  oga: 'audio/ogg',
  m4a: 'audio/mp4',
  aac: 'audio/aac',
  flac: 'audio/flac',
}
export const ACCEPT = Object.keys(EXT_MIME).map((ext) => `.${ext}`).join(',') + ',audio/*'
export const FORMATS_LABEL = 'mp3 / wav / ogg / m4a / flac'

export const extOf = (name) => {
  const match = /\.([a-z0-9]{1,5})$/i.exec(String(name || ''))
  return match ? match[1].toLowerCase() : ''
}

/** 文件的播放用 MIME：扩展名认识就用标准值（浏览器给的类型常常为空或不准），否则用浏览器给的 audio/*。 */
export function mimeFor(file) {
  const byExt = EXT_MIME[extOf(file?.name)]
  if (byExt) return byExt
  return /^audio\//.test(file?.type || '') ? file.type : ''
}

/**
 * 导入前的检查（能否真正解码要再交给浏览器试一次）。
 * usedBytes：已占用；返回 null 表示通过，否则是中文原因。
 */
export function checkFile(file, usedBytes = 0, trackCount = 0) {
  if (!file) return '没有选择文件'
  if (!mimeFor(file)) return `「${file.name}」不是支持的音频格式（支持 ${FORMATS_LABEL}）`
  if (!file.size) return `「${file.name}」是空文件`
  if (file.size > MAX_FILE_BYTES) return `「${file.name}」有 ${formatBytes(file.size)}，单个文件不能超过 ${formatBytes(MAX_FILE_BYTES)}`
  if (usedBytes + file.size > MAX_TOTAL_BYTES) return `空间不够：已用 ${formatBytes(usedBytes)}，总共最多 ${formatBytes(MAX_TOTAL_BYTES)}`
  if (trackCount >= MAX_TRACKS) return `最多保存 ${MAX_TRACKS} 首歌`
  return null
}

/** 由文件名得到歌名：去掉扩展名，截断到 NAME_MAX。 */
export function trackName(fileName) {
  const base = String(fileName || '').replace(/\.[a-z0-9]{1,5}$/i, '').replace(/[_]+/g, ' ').trim()
  return (base || '未命名').slice(0, NAME_MAX)
}

export function cleanName(value, fallback = '') {
  const text = String(value ?? '').replace(/\s+/g, ' ').trim().slice(0, NAME_MAX)
  return text || fallback
}

export function formatBytes(bytes) {
  const value = Math.max(0, Number(bytes) || 0)
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${Math.round(value / 1024)} KB`
  if (value < 1024 * 1024 * 1024) return `${(value / 1024 / 1024).toFixed(value < 10 * 1024 * 1024 ? 1 : 0)} MB`
  return `${(value / 1024 / 1024 / 1024).toFixed(1)} GB`
}

export function formatDuration(seconds) {
  const total = Math.round(Number(seconds) || 0)
  if (!total) return '--:--'
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = String(total % 60).padStart(2, '0')
  return h ? `${h}:${String(m).padStart(2, '0')}:${s}` : `${m}:${s}`
}

// ---------------------------------------------------------------- 歌单
export const PLAY_MODES = [
  { key: 'loop', label: '列表循环', icon: 'lucide:repeat' },
  { key: 'shuffle', label: '随机播放', icon: 'lucide:shuffle' },
  { key: 'single', label: '单曲循环', icon: 'lucide:repeat-1' },
]
export const nextMode = (mode) => {
  const index = PLAY_MODES.findIndex((m) => m.key === mode)
  return PLAY_MODES[(index + 1) % PLAY_MODES.length].key
}
export const modeOf = (mode) => PLAY_MODES.find((m) => m.key === mode) || PLAY_MODES[0]

/** 专注页"声音"选择里歌单的 key：playlist:<id>，与白噪音的 white / rain 等区分。 */
export const PLAYLIST_PREFIX = 'playlist:'
export const playlistKey = (id) => `${PLAYLIST_PREFIX}${id}`
export const isPlaylistKey = (key) => typeof key === 'string' && key.startsWith(PLAYLIST_PREFIX) && key.length > PLAYLIST_PREFIX.length
export const playlistIdOf = (key) => (isPlaylistKey(key) ? key.slice(PLAYLIST_PREFIX.length) : null)

/** 新建歌单对象。 */
export function makePlaylist(name, id = newId()) {
  return { id, name: cleanName(name, '我的歌单'), trackIds: [], mode: 'loop', createdAt: Date.now() }
}

/** 把歌加入歌单（去重，保持原有顺序）。 */
export function addTracks(playlist, ids) {
  const set = new Set(playlist.trackIds)
  return { ...playlist, trackIds: [...playlist.trackIds, ...ids.filter((id) => !set.has(id) && set.add(id))] }
}

export function removeTrack(playlist, id) {
  return { ...playlist, trackIds: playlist.trackIds.filter((t) => t !== id) }
}

/** 上移 / 下移一首（越界时不变）。 */
export function moveTrack(playlist, index, delta) {
  const target = index + delta
  if (index < 0 || target < 0 || index >= playlist.trackIds.length || target >= playlist.trackIds.length) return playlist
  const ids = [...playlist.trackIds]
  ;[ids[index], ids[target]] = [ids[target], ids[index]]
  return { ...playlist, trackIds: ids }
}

/** 删除一首歌后，从所有歌单里去掉它。 */
export function purgeTrack(playlists, id) {
  return playlists.map((p) => (p.trackIds.includes(id) ? removeTrack(p, id) : p))
}

/** 播放顺序：shuffle 打乱（Fisher-Yates，random 可注入便于测试），其他按歌单顺序。 */
export function playOrder(ids, mode, random = Math.random) {
  const order = [...ids]
  if (mode !== 'shuffle') return order
  for (let i = order.length - 1; i > 0; i--) {
    const j = Math.floor(random() * (i + 1))
    ;[order[i], order[j]] = [order[j], order[i]]
  }
  return order
}

/** 一首播完后下一首的位置：single 重复当前；loop / shuffle 到末尾回到开头（shuffle 由播放器重新打乱）。 */
export function nextIndex(position, length, mode) {
  if (!length) return -1
  if (mode === 'single') return position
  return (position + 1) % length
}

export function newId() {
  return `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`
}
