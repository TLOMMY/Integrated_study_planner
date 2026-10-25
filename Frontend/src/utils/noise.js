/**
 * 白噪音：全部用 WebAudio 现场生成，不引入任何音频文件。
 * - white：白噪音（均匀随机）
 * - pink：粉红噪音（Paul Kellet 滤波，低频更多，听感柔和）
 * - brown：棕噪音（随机游走积分，像远处的瀑布 / 风声）
 * - rain：雨声近似（低通的棕噪音做底 + 带通白噪音做雨幕 + 随机"雨滴"颗粒）
 *
 * 浏览器要求音频必须在用户手势里首次启动，因此 play() 应由按钮点击触发。
 */

export const NOISES = [
  { key: 'off', label: '关闭', icon: 'lucide:volume-x' },
  { key: 'white', label: '白噪音', icon: 'lucide:audio-lines' },
  { key: 'pink', label: '粉红噪音', icon: 'lucide:waves' },
  { key: 'brown', label: '棕噪音', icon: 'lucide:wind' },
  { key: 'rain', label: '雨声', icon: 'lucide:cloud-rain' },
]

const KIND_KEY = 'focus-noise'
const VOLUME_KEY = 'focus-noise-volume'
const GUARD_KEY = 'focus-guard'

export const noisePrefs = {
  get kind() {
    const value = localStorage.getItem(KIND_KEY)
    return NOISES.some((n) => n.key === value) ? value : 'off'
  },
  set kind(value) {
    localStorage.setItem(KIND_KEY, value)
  },
  get volume() {
    const value = Number(localStorage.getItem(VOLUME_KEY))
    return Number.isFinite(value) && localStorage.getItem(VOLUME_KEY) !== null ? Math.min(1, Math.max(0, value)) : 0.5
  },
  set volume(value) {
    localStorage.setItem(VOLUME_KEY, String(value))
  },
}

/** 防切出提醒开关（默认开启）。 */
export const guardEnabled = () => localStorage.getItem(GUARD_KEY) !== '0'
export const setGuardEnabled = (on) => localStorage.setItem(GUARD_KEY, on ? '1' : '0')

const SECONDS = 4

function fillBuffer(ctx, kind) {
  const length = ctx.sampleRate * SECONDS
  const buffer = ctx.createBuffer(2, length, ctx.sampleRate)
  for (let ch = 0; ch < 2; ch++) {
    const data = buffer.getChannelData(ch)
    let b0 = 0, b1 = 0, b2 = 0, b3 = 0, b4 = 0, b5 = 0, b6 = 0, last = 0
    for (let i = 0; i < length; i++) {
      const white = Math.random() * 2 - 1
      if (kind === 'pink') {
        b0 = 0.99886 * b0 + white * 0.0555179
        b1 = 0.99332 * b1 + white * 0.0750759
        b2 = 0.969 * b2 + white * 0.153852
        b3 = 0.8665 * b3 + white * 0.3104856
        b4 = 0.55 * b4 + white * 0.5329522
        b5 = -0.7616 * b5 - white * 0.016898
        data[i] = (b0 + b1 + b2 + b3 + b4 + b5 + b6 + white * 0.5362) * 0.11
        b6 = white * 0.115926
      } else if (kind === 'brown' || kind === 'rain') {
        last = (last + 0.02 * white) / 1.02
        data[i] = last * 3.5
      } else {
        data[i] = white * 0.5
      }
    }
    // 首尾做短淡入淡出，循环接缝处不"咔哒"
    const fade = Math.floor(ctx.sampleRate * 0.05)
    for (let i = 0; i < fade; i++) {
      const k = i / fade
      data[i] *= k
      data[length - 1 - i] *= k
    }
  }
  return buffer
}

/** 雨滴颗粒：很短的高频衰减脉冲。 */
function dropBuffer(ctx) {
  const length = Math.floor(ctx.sampleRate * 0.03)
  const buffer = ctx.createBuffer(1, length, ctx.sampleRate)
  const data = buffer.getChannelData(0)
  for (let i = 0; i < length; i++) data[i] = (Math.random() * 2 - 1) * Math.exp(-i / (length / 6))
  return buffer
}

class NoisePlayer {
  constructor() {
    this.ctx = null
    this.master = null
    this.nodes = []
    this.kind = 'off'
    this.dropTimer = null
    this.volume = noisePrefs.volume
  }

  ensure() {
    if (this.ctx) return this.ctx
    const Ctx = window.AudioContext || window.webkitAudioContext
    if (!Ctx) return null
    this.ctx = new Ctx()
    this.master = this.ctx.createGain()
    this.master.gain.value = 0
    this.master.connect(this.ctx.destination)
    return this.ctx
  }

  get playing() {
    return this.kind !== 'off' && this.nodes.length > 0
  }

  setVolume(value) {
    this.volume = Math.min(1, Math.max(0, value))
    noisePrefs.volume = this.volume
    if (this.ctx && this.playing) this.master.gain.setTargetAtTime(this.gainFor(this.kind), this.ctx.currentTime, 0.05)
  }

  gainFor(kind) {
    // 不同噪音的响度差别较大，统一到接近的听感
    const base = { white: 0.35, pink: 0.6, brown: 0.7, rain: 0.8 }[kind] || 0.5
    return base * this.volume * this.volume
  }

  /** 开始（或切换到）某种噪音。必须在用户手势中首次调用。 */
  play(kind = noisePrefs.kind) {
    if (!kind || kind === 'off') return this.stop()
    const ctx = this.ensure()
    if (!ctx) return false
    if (ctx.state === 'suspended') ctx.resume().catch(() => {})
    if (this.kind === kind && this.playing) {
      this.resume()
      return true
    }
    this.teardown()
    this.kind = kind

    const source = ctx.createBufferSource()
    source.buffer = fillBuffer(ctx, kind)
    source.loop = true
    let tail = source
    if (kind === 'rain') {
      const low = ctx.createBiquadFilter()
      low.type = 'lowpass'
      low.frequency.value = 900
      source.connect(low)
      tail = low
      // 雨幕：带通白噪音
      const hiss = ctx.createBufferSource()
      hiss.buffer = fillBuffer(ctx, 'white')
      hiss.loop = true
      const band = ctx.createBiquadFilter()
      band.type = 'bandpass'
      band.frequency.value = 2600
      band.Q.value = 0.6
      const hissGain = ctx.createGain()
      hissGain.gain.value = 0.35
      hiss.connect(band).connect(hissGain).connect(this.master)
      hiss.start()
      this.nodes.push(hiss)
      this.scheduleDrops()
    }
    tail.connect(this.master)
    source.start()
    this.nodes.push(source)
    this.master.gain.cancelScheduledValues(ctx.currentTime)
    this.master.gain.setTargetAtTime(this.gainFor(kind), ctx.currentTime, 0.4)
    return true
  }

  scheduleDrops() {
    clearTimeout(this.dropTimer)
    const ctx = this.ctx
    const drop = dropBuffer(ctx)
    const tick = () => {
      if (this.kind !== 'rain' || !this.ctx) return
      const count = 2 + Math.floor(Math.random() * 4)
      for (let i = 0; i < count; i++) {
        const src = ctx.createBufferSource()
        src.buffer = drop
        src.playbackRate.value = 0.6 + Math.random() * 1.2
        const g = ctx.createGain()
        g.gain.value = 0.05 + Math.random() * 0.12
        const pan = ctx.createStereoPanner ? ctx.createStereoPanner() : null
        if (pan) {
          pan.pan.value = Math.random() * 2 - 1
          src.connect(g).connect(pan).connect(this.master)
        } else src.connect(g).connect(this.master)
        src.start(ctx.currentTime + Math.random() * 0.25)
      }
      this.dropTimer = setTimeout(tick, 120 + Math.random() * 200)
    }
    tick()
  }

  /** 暂停：淡出但保留 kind，resume() 可恢复。 */
  pause() {
    if (!this.ctx || !this.playing) return
    this.master.gain.setTargetAtTime(0, this.ctx.currentTime, 0.2)
    clearTimeout(this.dropTimer)
    const ctx = this.ctx
    setTimeout(() => ctx.state === 'running' && this.master.gain.value < 0.01 && ctx.suspend().catch(() => {}), 900)
  }

  resume() {
    if (!this.ctx || !this.playing) return
    this.ctx.resume().catch(() => {})
    this.master.gain.setTargetAtTime(this.gainFor(this.kind), this.ctx.currentTime, 0.4)
    if (this.kind === 'rain') this.scheduleDrops()
  }

  /** 立即断开当前所有声源（切换噪音种类时用）。 */
  teardown() {
    clearTimeout(this.dropTimer)
    const nodes = this.nodes
    this.nodes = []
    nodes.forEach(stopNode)
    if (this.ctx) {
      this.master.gain.cancelScheduledValues(this.ctx.currentTime)
      this.master.gain.setValueAtTime(0, this.ctx.currentTime)
    }
  }

  /** 淡出后停止。 */
  stop() {
    this.kind = 'off'
    clearTimeout(this.dropTimer)
    if (!this.ctx) return true
    const nodes = this.nodes
    this.nodes = []
    this.master.gain.setTargetAtTime(0, this.ctx.currentTime, 0.12)
    setTimeout(() => nodes.forEach(stopNode), 600)
    return true
  }
}

function stopNode(node) {
  try {
    node.stop()
    node.disconnect()
  } catch {
    // 节点可能已经停止
  }
}

export const noise = new NoisePlayer()
