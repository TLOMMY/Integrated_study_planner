/**
 * 我的音乐 · 共享的歌曲 / 歌单列表（设置页、专注页共用一份，任何一处修改后调用 reloadLibrary()）。
 */
import { reactive } from 'vue'
import { listPlaylists, listTracks, musicSupported } from '@/utils/musicDb'
import { isPlaylistKey, playlistIdOf } from '@/utils/music'

export const library = reactive({ tracks: [], playlists: [], loaded: false, error: '' })

let pending = null
export function reloadLibrary() {
  if (!musicSupported()) {
    Object.assign(library, { loaded: true, error: '当前浏览器不支持本机存储音乐（可能处于无痕模式）' })
    return Promise.resolve(library)
  }
  pending ||= Promise.all([listTracks(), listPlaylists()])
    .then(([tracks, playlists]) => Object.assign(library, { tracks, playlists, loaded: true, error: '' }))
    .catch((error) => Object.assign(library, { loaded: true, error: error.message || '读取本机音乐失败' }))
    .finally(() => (pending = null))
  return pending
}

export const ensureLibrary = () => (library.loaded ? Promise.resolve(library) : reloadLibrary())

/** 声音选择（focus.noiseKind）对应的歌单；不是歌单或歌单已删除时返回 null。 */
export const playlistForKey = (key) => (isPlaylistKey(key) ? library.playlists.find((p) => p.id === playlistIdOf(key)) || null : null)
