/**
 * 我的音乐 · 本机存储（IndexedDB）。音频文件只保存在这台设备的浏览器里，不上传服务器。
 * - tracks：歌曲信息 { id, name, size, type, duration, addedAt }
 * - blobs：音频本体 { id, blob }（与信息分开存，列出歌曲时不必读出整段音频）
 * - playlists：歌单 { id, name, trackIds, mode, createdAt }
 */
import { MAX_PLAYLISTS, checkFile, cleanName, makePlaylist, mimeFor, newId, purgeTrack, trackName } from './music'

const DB_NAME = 'study-music'
const VERSION = 1
let dbPromise = null

export const musicSupported = () => typeof indexedDB !== 'undefined'

function open() {
  if (!musicSupported()) return Promise.reject(new Error('当前浏览器不支持本机存储音乐'))
  dbPromise ||= new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, VERSION)
    request.onupgradeneeded = () => {
      const db = request.result
      if (!db.objectStoreNames.contains('tracks')) db.createObjectStore('tracks', { keyPath: 'id' })
      if (!db.objectStoreNames.contains('blobs')) db.createObjectStore('blobs', { keyPath: 'id' })
      if (!db.objectStoreNames.contains('playlists')) db.createObjectStore('playlists', { keyPath: 'id' })
    }
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => {
      dbPromise = null
      reject(new Error('无法打开本机音乐库（可能处于无痕模式或存储被禁用）'))
    }
  })
  return dbPromise
}

/** 在一个事务里执行 fn(stores)，事务完成后返回 fn 的结果。 */
async function tx(names, mode, fn) {
  const db = await open()
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(names, mode)
    const stores = Object.fromEntries(names.map((n) => [n, transaction.objectStore(n)]))
    let result
    Promise.resolve(fn(stores)).then((value) => (result = value), reject)
    transaction.oncomplete = () => resolve(result)
    transaction.onerror = () => reject(transaction.error?.name === 'QuotaExceededError' ? new Error('设备存储空间不足，请删掉一些歌曲后再试') : transaction.error)
    transaction.onabort = () => reject(transaction.error || new Error('保存失败'))
  })
}

const req = (request) =>
  new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error)
  })

// ---------------------------------------------------------------- 歌曲
export async function listTracks() {
  const items = await tx(['tracks'], 'readonly', (s) => req(s.tracks.getAll()))
  return items.sort((a, b) => a.addedAt - b.addedAt)
}

export async function usage() {
  const tracks = await listTracks()
  return { bytes: tracks.reduce((sum, t) => sum + (t.size || 0), 0), count: tracks.length }
}

/** 让浏览器试着解码，拿到时长；解码不了的文件拒绝导入。 */
export function probeAudio(blob, timeoutMs = 10000) {
  return new Promise((resolve, reject) => {
    const audio = new Audio()
    const url = URL.createObjectURL(blob)
    let done = false
    const finish = (fn, value) => {
      if (done) return
      done = true
      clearTimeout(timer)
      audio.removeAttribute('src')
      audio.load()
      URL.revokeObjectURL(url)
      fn(value)
    }
    const timer = setTimeout(() => finish(reject, new Error('读取超时')), timeoutMs)
    audio.preload = 'metadata'
    audio.onloadedmetadata = () => finish(resolve, Number.isFinite(audio.duration) ? audio.duration : 0)
    audio.onerror = () => finish(reject, new Error('浏览器无法解码'))
    audio.src = url
  })
}

/**
 * 导入一批文件：逐个检查格式、大小、能否解码，返回 { added, failed: [{ name, reason }] }。
 */
export async function importFiles(files) {
  const added = []
  const failed = []
  let { bytes, count } = await usage()
  if (navigator.storage?.persist) navigator.storage.persist().catch(() => {})
  for (const file of files) {
    const problem = checkFile(file, bytes, count)
    if (problem) {
      failed.push({ name: file.name, reason: problem })
      continue
    }
    // 扩展名对但浏览器给的类型为空 / 不准时（如 .awv），按标准类型重新包装
    const type = mimeFor(file)
    const blob = file.type === type ? file : new Blob([file], { type })
    let duration = 0
    try {
      duration = await probeAudio(blob)
    } catch (error) {
      failed.push({ name: file.name, reason: `「${file.name}」${error.message}，换成 mp3 试试` })
      continue
    }
    const track = { id: newId(), name: trackName(file.name), size: file.size, type, duration, addedAt: Date.now() + added.length }
    try {
      await tx(['tracks', 'blobs'], 'readwrite', (s) => {
        s.tracks.put(track)
        s.blobs.put({ id: track.id, blob })
      })
    } catch (error) {
      failed.push({ name: file.name, reason: error.message || '保存失败' })
      break
    }
    bytes += file.size
    count += 1
    added.push(track)
  }
  return { added, failed }
}

export async function getBlob(id) {
  const row = await tx(['blobs'], 'readonly', (s) => req(s.blobs.get(id)))
  return row?.blob || null
}

export async function renameTrack(id, name) {
  return tx(['tracks'], 'readwrite', async (s) => {
    const track = await req(s.tracks.get(id))
    if (!track) return null
    track.name = cleanName(name, track.name)
    s.tracks.put(track)
    return track
  })
}

/** 删除歌曲，同时从所有歌单里移除。 */
export async function deleteTrack(id) {
  const playlists = await listPlaylists()
  const next = purgeTrack(playlists, id)
  await tx(['tracks', 'blobs', 'playlists'], 'readwrite', (s) => {
    s.tracks.delete(id)
    s.blobs.delete(id)
    next.forEach((p, i) => p !== playlists[i] && s.playlists.put(p))
  })
}

// ---------------------------------------------------------------- 歌单
export async function listPlaylists() {
  const items = await tx(['playlists'], 'readonly', (s) => req(s.playlists.getAll()))
  return items.sort((a, b) => a.createdAt - b.createdAt)
}

export async function getPlaylist(id) {
  return tx(['playlists'], 'readonly', (s) => req(s.playlists.get(id)))
}

export async function createPlaylist(name) {
  const existing = await listPlaylists()
  if (existing.length >= MAX_PLAYLISTS) throw new Error(`最多 ${MAX_PLAYLISTS} 个歌单`)
  const playlist = makePlaylist(name)
  await savePlaylist(playlist)
  return playlist
}

export async function savePlaylist(playlist) {
  const clean = { ...playlist, name: cleanName(playlist.name, '我的歌单'), trackIds: [...playlist.trackIds] }
  await tx(['playlists'], 'readwrite', (s) => s.playlists.put(clean))
  return clean
}

export async function deletePlaylist(id) {
  await tx(['playlists'], 'readwrite', (s) => s.playlists.delete(id))
}

/** 浏览器给这个网站的总配额（只用于展示，拿不到时返回 null）。 */
export async function storageEstimate() {
  try {
    const { quota, usage: used } = await navigator.storage.estimate()
    return { quota, used }
  } catch {
    return null
  }
}
