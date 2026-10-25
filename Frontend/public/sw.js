/**
 * Service Worker：让网页可以"安装"成电脑上的独立应用窗口，并在断网时仍能打开界面。
 * - 安装时预缓存应用外壳：首页 HTML + 其中引用的 js/css + 入口脚本里懒加载的页面分包（文件名带 hash，从 HTML / 入口 js 里解析）
 * - 页面导航：网络优先，失败时回退到缓存的首页（SPA 由前端路由接管）
 * - 静态资源（/assets/ 下带 hash 的 js/css）：缓存优先，文件名变了自然换新
 * - 接口请求（/api/）与跨域请求：一律不缓存，始终走网络；断网时的接口数据由前端 request.js 的本地缓存提供
 */
const CACHE = 'study-planner-v2'
const SHELL = ['/', '/manifest.webmanifest', '/app-icon.svg', '/icons/icon-192.png']

/** 从 HTML / js 文本里找出 /assets/ 下的文件。 */
const assetsIn = (text) => [...new Set([...text.matchAll(/(?:\/|\.\/|")(assets\/[\w.-]+\.(?:js|css|woff2?|svg|png))/g)].map((m) => `/${m[1]}`))]

async function precache() {
  const cache = await caches.open(CACHE)
  await cache.addAll(SHELL)
  try {
    const html = await (await cache.match('/')).text()
    const first = assetsIn(html)
    await cache.addAll(first)
    // 入口脚本里引用了各页面的懒加载分包，一并缓存，断网时切换页面也能打开
    const entries = first.filter((url) => url.endsWith('.js'))
    const nested = new Set()
    for (const url of entries) {
      const res = await cache.match(url)
      if (res) for (const asset of assetsIn(await res.text())) if (!first.includes(asset)) nested.add(asset)
    }
    await Promise.all([...nested].map((url) => cache.add(url).catch(() => {})))
  } catch {
    /* 解析失败不影响安装，访问过的资源仍会按需缓存 */
  }
}

self.addEventListener('install', (event) => {
  event.waitUntil(precache().then(() => self.skipWaiting()))
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key))))
      .then(() => self.clients.claim()),
  )
})

self.addEventListener('fetch', (event) => {
  const { request } = event
  const url = new URL(request.url)
  if (request.method !== 'GET' || url.origin !== self.location.origin || url.pathname.startsWith('/api/')) return

  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then((response) => {
          if (response.ok) {
            const copy = response.clone()
            caches.open(CACHE).then((cache) => cache.put('/', copy))
          }
          return response
        })
        .catch(() => caches.match('/')),
    )
    return
  }

  if (url.pathname.startsWith('/assets/') || url.pathname.startsWith('/icons/') || SHELL.includes(url.pathname)) {
    event.respondWith(
      caches.match(request).then(
        (cached) =>
          cached ||
          fetch(request).then((response) => {
            if (response.ok) {
              const copy = response.clone()
              caches.open(CACHE).then((cache) => cache.put(request, copy))
            }
            return response
          }),
      ),
    )
  }
})
