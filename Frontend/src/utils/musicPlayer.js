/**
 * 我的音乐 · 播放器：用一个 <audio> 依次播放歌单里的本地歌曲（列表循环 / 随机 / 单曲循环）。
 * 由 noise.js 统一调度：专注页选择"歌单"时，白噪音播放器把 play / pause / stop / 音量转交到这里。
 * musicState 是响应式的，界面可以显示"正在播放"和错误原因。
 */
import { reactive } from 'vue'
import { useUiStore } from '@/stores/ui'
import { getBlob, getPlaylist, listTracks } from './musicDb'
import { modeOf, nextIndex, playOrder } from './music'

export const musicState = reactive({
  playlistId: null,
  playlistName: '',
  trackName: '',
  playing: false,
  mode: 'loop',
  error: '',
})

class MusicPlayer {
  constructor() {
    this.audio = null
    this.url = null
    this.ids = []
    this.order = []
    this.names = {}
    this.position = 0
    this.failures = 0
    this.volume = 0.5
    this.token = 0
  }

  ensure() {
    if (this.audio) return this.audio
    const audio = new Audio()
    audio.preload = 'auto'
    audio.addEventListener('ended', () => this.advance())
    audio.addEventListener('error', () => {
      // 没有 src（已停止）时的错误忽略
      if (!audio.getAttribute('src')) return
      this.failures += 1
      if (this.failures >= this.order.length) {
        this.fail('歌单里的歌曲都无法播放，可能文件已损坏或格式不受支持')
        return
      }
      this.advance()
    })
    audio.addEventListener('playing', () => {
      this.failures = 0
      musicState.playing = true
      musicState.error = ''
    })
    audio.addEventListener('pause', () => (musicState.playing = false))
    this.audio = audio
    return audio
  }

  get active() {
    return Boolean(musicState.playlistId)
  }

  setVolume(value) {
    this.volume = Math.min(1, Math.max(0, value))
    // 与白噪音一致用平方曲线，小音量更细腻
    if (this.audio) this.audio.volume = this.volume * this.volume
  }

  /**
   * 播放某个歌单。必须在点击等用户手势里调用（audio 元素在这里同步创建并解锁）。
   * 返回 Promise<boolean>：歌单为空或不存在时 false，原因写在 musicState.error。
   */
  async play(playlistId) {
    const audio = this.ensure()
    this.setVolume(this.volume)
    if (musicState.playlistId === playlistId && audio.getAttribute('src')) {
      this.resume()
      return true
    }
    const token = ++this.token
    const [playlist, tracks] = await Promise.all([getPlaylist(playlistId), listTracks()]).catch(() => [null, []])
    if (token !== this.token) return false
    if (!playlist) return this.fail('这个歌单已被删除，请重新选择')
    const known = new Set(tracks.map((t) => t.id))
    const ids = playlist.trackIds.filter((id) => known.has(id))
    if (!ids.length) return this.fail(`歌单「${playlist.name}」里还没有歌，到 设置 → 专注 → 我的音乐 里添加`)
    this.names = Object.fromEntries(tracks.map((t) => [t.id, t.name]))
    Object.assign(musicState, { playlistId, playlistName: playlist.name, mode: modeOf(playlist.mode).key, error: '' })
    this.ids = ids
    this.order = playOrder(ids, musicState.mode)
    this.position = 0
    this.failures = 0
    return this.load(token)
  }

  async load(token = this.token) {
    const id = this.order[this.position]
    const blob = await getBlob(id).catch(() => null)
    if (token !== this.token) return false
    const audio = this.ensure()
    if (this.url) URL.revokeObjectURL(this.url)
    this.url = null
    if (!blob) {
      this.failures += 1
      if (this.failures >= this.order.length) return this.fail('歌单里的歌曲已从本机删除')
      return this.advance()
    }
    this.url = URL.createObjectURL(blob)
    musicState.trackName = this.names[id] || ''
    audio.src = this.url
    audio.volume = this.volume * this.volume
    try {
      await audio.play()
      return true
    } catch (error) {
      if (token !== this.token) return false
      if (error?.name === 'NotAllowedError') return this.fail('浏览器拦截了自动播放，请再点一次播放')
      // 解码失败会同时触发 error 事件并切到下一首，这里不重复处理
      return false
    }
  }

  advance() {
    const length = this.order.length
    if (!length) return false
    let next = nextIndex(this.position, length, musicState.mode)
    // 随机播放一轮结束后重新打乱，避免每轮顺序相同
    if (musicState.mode === 'shuffle' && next === 0) this.order = playOrder(this.ids, 'shuffle')
    this.position = next
    return this.load()
  }

  /** 跳到下一首（专注页的"下一首"按钮）。 */
  skip() {
    if (!this.active) return
    if (musicState.mode === 'single') this.position = (this.position + 1) % this.order.length
    else return this.advance()
    return this.load()
  }

  pause() {
    this.audio?.pause()
  }

  resume() {
    if (this.audio?.getAttribute('src')) this.audio.play().catch(() => {})
  }

  stop() {
    this.token += 1
    if (this.audio) {
      this.audio.pause()
      this.audio.removeAttribute('src')
      this.audio.load()
    }
    if (this.url) URL.revokeObjectURL(this.url)
    this.url = null
    this.order = []
    this.ids = []
    Object.assign(musicState, { playlistId: null, playlistName: '', trackName: '', playing: false })
  }

  fail(message) {
    this.stop()
    musicState.error = message
    // 播放可能由专注开始 / 设置页试听等任何地方触发，在这里统一提示（专注本身照常进行）
    try {
      useUiStore().toast(message, 'warning', 3600)
    } catch {
      /* pinia 尚未就绪 */
    }
    return false
  }

  /** 播放中切换了循环方式：之后的顺序按新方式。 */
  setMode(mode) {
    if (!this.active || musicState.mode === mode) return
    const current = this.order[this.position]
    musicState.mode = mode
    // 随机：当前这首放最前面、其余打乱；其他方式恢复歌单原顺序
    this.order = mode === 'shuffle' ? [current, ...playOrder(this.ids.filter((id) => id !== current), 'shuffle')] : [...this.ids]
    this.position = Math.max(0, this.order.indexOf(current))
  }
}

export const music = new MusicPlayer()
