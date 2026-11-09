/**
 * 安卓 App：在内置浏览器里打开教务系统，同学点页面上的"导入此页课表"后把页面交回来。
 * 只在原生 App 里可用（网页版浏览器不允许读取别的网站，仍用"保存网页 / 存为 PDF"上传）。
 *
 * const { supported, open } = useJwxtBrowser()
 * const capture = await open(url, { accent })   // 同学点了导入：{ file, url, title }；关掉浏览器：null
 */
import { isNativeApp } from '@/api/server'
import { captureFileName, captureScript, readCapture, shrinkHtml } from '@/utils/jwxtCapture'

// Capacitor 插件是代理对象，不能直接作为 Promise 的结果（会被当成 thenable 调用 then() 卡住），所以包一层
let pluginPromise = null
const plugin = () => {
  if (!isNativeApp()) return Promise.resolve({ browser: null })
  pluginPromise ||= import('@capgo/inappbrowser').then((m) => ({ browser: m.InAppBrowser })).catch(() => ({ browser: null }))
  return pluginPromise
}

export class CaptureTooLarge extends Error {}

export function useJwxtBrowser() {
  const supported = isNativeApp()

  /** 打开教务系统；同学点导入或关闭浏览器后结束。同一时间只打开一个。 */
  const open = async (url, { accent } = {}) => {
    const { browser } = await plugin()
    if (!browser) throw new Error('当前版本的 App 不支持内置浏览器，请更新 App，或用"保存网页"上传')
    const code = captureScript(accent)
    const handles = []
    let id = null

    const result = await new Promise((resolve, reject) => {
      let settled = false
      const finish = (value, error) => {
        if (settled) return
        settled = true
        error ? reject(error) : resolve(value)
      }
      const inject = () => browser.executeScript({ code, ...(id ? { id } : {}) }).catch(() => {})
      Promise.all([
        browser.addListener('browserPageLoaded', inject),
        browser.addListener('messageFromWebview', (event) => {
          const capture = readCapture(event)
          if (!capture) return
          const html = shrinkHtml(capture.html)
          if (!html) return finish(null, new CaptureTooLarge('页面太大，无法读取。请确认打开的是课表页，或改用"存储为 PDF"上传'))
          const file = new File([html], captureFileName(capture.url), { type: 'text/html' })
          finish({ file, url: capture.url, title: capture.title })
        }),
        browser.addListener('closeEvent', () => finish(null)),
      ])
        .then((list) => {
          handles.push(...list)
          return browser.openWebView({
            url,
            title: '教务系统',
            toolbarType: 'navigation',
            activeNativeNavigationForWebview: true,
            showReloadButton: true,
            materialPicker: true,
          })
        })
        .then((opened) => {
          id = opened?.id || null
          // 页面已经加载完才打开时，browserPageLoaded 可能早于监听，补注入一次
          inject()
        })
        .catch((error) => finish(null, error))
    })
      .finally(async () => {
        await Promise.all(handles.map((h) => h?.remove?.().catch(() => {})))
      })

    if (result) await browser.close(id ? { id } : undefined).catch(() => {})
    return result
  }

  return { supported, open }
}
