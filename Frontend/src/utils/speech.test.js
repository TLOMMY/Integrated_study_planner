import { test } from 'node:test'
import assert from 'node:assert/strict'
import { collectResults, isElectronUA, mergeTranscript, speechErrorMessage, webSpeechCtor } from './speech.js'

function Ctor() {}

test('只在支持的网页环境返回识别构造函数', () => {
  const chrome = { navigator: { userAgent: 'Mozilla/5.0 Chrome/140.0 Safari/537.36' }, webkitSpeechRecognition: Ctor }
  assert.equal(webSpeechCtor(chrome), Ctor)
  assert.equal(webSpeechCtor({ ...chrome, SpeechRecognition: Ctor, webkitSpeechRecognition: undefined }), Ctor)
  // Firefox：没有 API
  assert.equal(webSpeechCtor({ navigator: { userAgent: 'Firefox/140.0' } }), null)
  // Electron 外壳：有构造函数但实际不可用
  const electron = { navigator: { userAgent: 'Mozilla/5.0 Chrome/140.0 Electron/38.1.0 Safari/537.36' }, webkitSpeechRecognition: Ctor }
  assert.ok(isElectronUA(electron.navigator.userAgent))
  assert.equal(webSpeechCtor(electron), null)
  // 安卓 App：走原生插件，不用 WebView 里的 API
  assert.equal(webSpeechCtor({ ...chrome, Capacitor: { isNativePlatform: () => true } }), null)
  assert.equal(webSpeechCtor(null), null)
})

test('识别文字接在原有内容后面', () => {
  assert.equal(mergeTranscript('', '这周复习高数'), '这周复习高数')
  assert.equal(mergeTranscript('明天', '复习英语'), '明天复习英语')
  assert.equal(mergeTranscript('学习 C', 'plus plus'), '学习 C plus plus')
  assert.equal(mergeTranscript('第3', '章'), '第3章')
  assert.equal(mergeTranscript('原文', '   '), '原文')
})

test('把已确认与正在识别的结果合并', () => {
  const results = [
    Object.assign([{ transcript: '这周每天' }], { isFinal: true }),
    Object.assign([{ transcript: '两小时' }], { isFinal: false }),
  ]
  assert.deepEqual(collectResults(results), { final: '这周每天', interim: '两小时' })
  assert.deepEqual(collectResults(undefined), { final: '', interim: '' })
})

test('错误提示：权限、网络、没听清、主动停止', () => {
  assert.match(speechErrorMessage('not-allowed'), /站点设置/)
  assert.match(speechErrorMessage('INSUFFICIENT_PERMISSIONS', { native: true }), /手机设置/)
  assert.match(speechErrorMessage('Missing permission', { native: true }), /麦克风权限/)
  assert.match(speechErrorMessage('network'), /联网/)
  assert.match(speechErrorMessage('NETWORK_TIMEOUT', { native: true }), /联网/)
  assert.match(speechErrorMessage('no-speech'), /没有听清/)
  assert.match(speechErrorMessage('NO_MATCH', { native: true }), /没有听清/)
  assert.match(speechErrorMessage('audio-capture'), /麦克风/)
  assert.equal(speechErrorMessage('aborted'), '')
  assert.equal(speechErrorMessage('CLIENT', { native: true }), '')
  assert.match(speechErrorMessage('weird'), /出错/)
})
