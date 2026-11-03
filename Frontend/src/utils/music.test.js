import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  MAX_FILE_BYTES, MAX_TOTAL_BYTES, addTracks, checkFile, cleanName, formatBytes, formatDuration, isPlaylistKey,
  makePlaylist, mimeFor, modeOf, moveTrack, nextIndex, nextMode, playOrder, playlistIdOf, playlistKey, purgeTrack, removeTrack, trackName,
} from './music.js'

const file = (name, size = 1000, type = '') => ({ name, size, type })

test('支持的格式按扩展名识别，awv 当作 wav', () => {
  assert.equal(mimeFor(file('a.mp3')), 'audio/mpeg')
  assert.equal(mimeFor(file('b.WAV')), 'audio/wav')
  assert.equal(mimeFor(file('c.awv')), 'audio/wav')
  assert.equal(mimeFor(file('d.flac')), 'audio/flac')
  assert.equal(mimeFor(file('e.m4a')), 'audio/mp4')
  assert.equal(mimeFor(file('f.ogg')), 'audio/ogg')
  assert.equal(mimeFor(file('g.opus', 10, 'audio/opus')), 'audio/opus')
  assert.equal(mimeFor(file('h.txt', 10, 'text/plain')), '')
})

test('导入检查：格式、空文件、单文件上限、总量上限', () => {
  assert.equal(checkFile(file('ok.mp3')), null)
  assert.match(checkFile(file('x.pdf', 10, 'application/pdf')), /不是支持的音频格式/)
  assert.match(checkFile(file('empty.mp3', 0)), /空文件/)
  assert.match(checkFile(file('big.mp3', MAX_FILE_BYTES + 1)), /单个文件不能超过 30 MB/)
  assert.match(checkFile(file('a.mp3', 10 * 1024 * 1024), MAX_TOTAL_BYTES - 1024), /空间不够/)
  assert.match(checkFile(file('a.mp3'), 0, 200), /最多保存 200 首/)
})

test('歌名与大小 / 时长显示', () => {
  assert.equal(trackName('雨天_钢琴.mp3'), '雨天 钢琴')
  assert.equal(trackName('.mp3'), '未命名')
  assert.equal(trackName('x'.repeat(80) + '.wav').length, 40)
  assert.equal(cleanName('  歌单   一 '), '歌单 一')
  assert.equal(cleanName('   ', '默认'), '默认')
  assert.equal(formatBytes(512), '512 B')
  assert.equal(formatBytes(2048), '2 KB')
  assert.equal(formatBytes(5.5 * 1024 * 1024), '5.5 MB')
  assert.equal(formatBytes(300 * 1024 * 1024), '300 MB')
  assert.equal(formatDuration(0), '--:--')
  assert.equal(formatDuration(65), '1:05')
  assert.equal(formatDuration(3725), '1:02:05')
})

test('歌单：添加去重、移除、排序、删除歌曲时同步移除', () => {
  let p = makePlaylist('  ', 'p1')
  assert.equal(p.name, '我的歌单')
  assert.equal(p.mode, 'loop')
  p = addTracks(p, ['a', 'b', 'a'])
  p = addTracks(p, ['b', 'c'])
  assert.deepEqual(p.trackIds, ['a', 'b', 'c'])
  assert.deepEqual(moveTrack(p, 2, -1).trackIds, ['a', 'c', 'b'])
  assert.deepEqual(moveTrack(p, 0, 1).trackIds, ['b', 'a', 'c'])
  assert.equal(moveTrack(p, 0, -1), p, '越界不变')
  assert.equal(moveTrack(p, 2, 1), p, '越界不变')
  assert.deepEqual(removeTrack(p, 'b').trackIds, ['a', 'c'])
  const other = { ...makePlaylist('二', 'p2'), trackIds: ['c'] }
  const untouched = { ...makePlaylist('三', 'p3'), trackIds: ['x'] }
  const [first, second, third] = purgeTrack([p, other, untouched], 'c')
  assert.deepEqual(first.trackIds, ['a', 'b'])
  assert.deepEqual(second.trackIds, [])
  assert.equal(third, untouched, '没包含的歌单保持原对象（不必重新保存）')
})

test('播放方式：列表循环 / 随机 / 单曲循环', () => {
  assert.equal(nextMode('loop'), 'shuffle')
  assert.equal(nextMode('shuffle'), 'single')
  assert.equal(nextMode('single'), 'loop')
  assert.equal(modeOf('unknown').key, 'loop')
  assert.deepEqual(playOrder(['a', 'b', 'c'], 'loop'), ['a', 'b', 'c'])
  // random 恒为 0：Fisher-Yates 每次与第 0 位交换
  assert.deepEqual(playOrder(['a', 'b', 'c'], 'shuffle', () => 0), ['b', 'c', 'a'])
  const shuffled = playOrder(['a', 'b', 'c', 'd', 'e'], 'shuffle')
  assert.deepEqual([...shuffled].sort(), ['a', 'b', 'c', 'd', 'e'], '随机只改顺序不丢歌')
  assert.equal(nextIndex(0, 3, 'loop'), 1)
  assert.equal(nextIndex(2, 3, 'loop'), 0, '列表循环回到开头')
  assert.equal(nextIndex(2, 3, 'shuffle'), 0)
  assert.equal(nextIndex(1, 3, 'single'), 1, '单曲循环重复当前')
  assert.equal(nextIndex(0, 0, 'loop'), -1)
})

test('专注声音选择里的歌单 key', () => {
  assert.equal(playlistKey('abc'), 'playlist:abc')
  assert.ok(isPlaylistKey('playlist:abc'))
  assert.ok(!isPlaylistKey('playlist:'))
  assert.ok(!isPlaylistKey('rain'))
  assert.ok(!isPlaylistKey(null))
  assert.equal(playlistIdOf('playlist:abc'), 'abc')
  assert.equal(playlistIdOf('white'), null)
})
