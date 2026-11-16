/**
 * 安卓 App：在内置浏览器里打开教务系统，同学点页面上的"导入此页课表"后把页面交回来。
 * 只在原生 App 里可用（网页版浏览器不允许读取别的网站，仍用"保存网页 / 存为 PDF"上传）。
 * 不少教务系统点"我的课表"会用 window.open / target=_blank 打开新窗口：普通链接直接在当前窗口打开，
 * 脚本打开的新窗口（插件里是另一个 webview，id 不同）也要注入按钮；关掉这个新窗口只回到上一页，不结束导入。
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
    const popups = new Set()
    let id = null

    const result = await new Promise((resolve, reject) => {
      let settled = false
      const finish = (value, error) => {
        if (settled) return
        settled = true
        error ? reject(error) : resolve(value)
      }
      const run = (target) => browser.executeScript({ code, ...(target ? { id: target } : {}) }).catch(() => {})
      // 页面加载完的是哪个窗口就注入哪个；没带 id 时注入全部打开的窗口（脚本自己会去重）
      const inject = (event) => run(event?.id || null)
      Promise.all([
        browser.addListener('browserPageLoaded', inject),
        browser.addListener('urlChangeEvent', inject),
        browser.addListener('popupWindowOpened', (event) => {
          if (!event?.id) return
          popups.add(event.id)
          // 新窗口可能已经加载完，补注入两次
          run(event.id)
          setTimeout(() => run(event.id), 1200)
        }),
        browser.addListener('messageFromWebview', (event) => {
          const capture = readCapture(event)
          if (!capture) return
          const html = shrinkHtml(capture.html)
          if (!html) return finish(null, new CaptureTooLarge('页面太大，无法读取。请确认打开的是课表页，或改用"存储为 PDF"上传'))
          const file = new File([html], captureFileName(capture.url), { type: 'text/html' })
          finish({ file, url: capture.url, title: capture.title })
        }),
        browser.addListener('closeEvent', (event) => {
          if (event?.id && popups.has(event.id)) return popups.delete(event.id)
          finish(null)
        }),
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
            openBlankTargetInWebView: true,
          })
        })
        .then((opened) => {
          id = opened?.id || null
          // 页面已经加载完才打开时，browserPageLoaded 可能早于监听，补注入一次
          run(id)
        })
        .catch((error) => finish(null, error))
    })
      .finally(async () => {
        await Promise.all(handles.map((h) => h?.remove?.().catch(() => {})))
      })

    // 导入后关掉主窗口；没传 id 的 close 只关当前窗口，所以新开的窗口也逐个关掉
    if (result) {
      for (const popup of popups) await browser.close({ id: popup }).catch(() => {})
      await browser.close(id ? { id } : undefined).catch(() => {})
    }
    return result
  }

  return { supported, open }
}
