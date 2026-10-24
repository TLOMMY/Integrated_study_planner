/**
 * 学业管家 Windows 客户端。
 *
 * 只是一个"外壳"：打开服务器上的网页版（默认 https://app.xueyeguanjia.com），
 * 账号、课表、任务、排行榜都存在服务器上，和网页版、手机 App 是同一份数据。
 * 连不上服务器时显示 offline.html，可以改成局域网里的电脑（如 http://192.168.1.5:5173）。
 */
const { app, BrowserWindow, Menu, dialog, ipcMain, net, shell } = require('electron')
const fs = require('node:fs')
const path = require('node:path')

const DEFAULT_SERVER = 'https://app.xueyeguanjia.com'
const configPath = () => path.join(app.getPath('userData'), 'config.json')

const normalize = (value) => {
  let url = String(value || '').trim().replace(/\/+$/, '')
  if (!url) return ''
  if (!/^https?:\/\//i.test(url)) url = `http://${url}`
  return url.replace(/\/api$/i, '')
}

const readConfig = () => {
  try {
    return JSON.parse(fs.readFileSync(configPath(), 'utf8'))
  } catch {
    return {}
  }
}
const writeConfig = (patch) => {
  const next = { ...readConfig(), ...patch }
  fs.mkdirSync(path.dirname(configPath()), { recursive: true })
  fs.writeFileSync(configPath(), JSON.stringify(next, null, 2))
  return next
}
const currentServer = () => normalize(readConfig().server) || DEFAULT_SERVER

/** 请求后端 /api/health，确认地址可用并且确实是学业管家的服务器。 */
const probe = async (server) => {
  const started = Date.now()
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), 8000)
  try {
    const response = await net.fetch(`${normalize(server)}/api/health`, { signal: controller.signal, cache: 'no-store' })
    const body = await response.json().catch(() => null)
    if (!response.ok || body?.code !== 200) throw new Error('地址可以访问，但不是学业管家的服务器')
    return { ok: true, ms: Date.now() - started }
  } catch (error) {
    const message = error.name === 'AbortError' ? '连接超时' : error.message || '无法连接'
    return { ok: false, message }
  } finally {
    clearTimeout(timer)
  }
}

let win = null

const showOffline = (reason = '') => {
  win.loadFile(path.join(__dirname, 'offline.html'), { query: { server: currentServer(), reason } })
}

const openServer = async () => {
  const server = currentServer()
  const result = await probe(server)
  if (!result.ok) return showOffline(result.message)
  win.loadURL(`${server}/today-task`)
}

const createWindow = () => {
  const saved = readConfig().bounds || {}
  win = new BrowserWindow({
    width: saved.width || 1280,
    height: saved.height || 820,
    x: saved.x,
    y: saved.y,
    minWidth: 380,
    minHeight: 600,
    title: '学业管家',
    backgroundColor: '#F5F7FB',
    icon: path.join(__dirname, 'build', 'icon.png'),
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  })

  // 外部链接（不是当前服务器的地址）用系统浏览器打开
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (!url.startsWith(currentServer())) shell.openExternal(url)
    return { action: url.startsWith(currentServer()) ? 'allow' : 'deny' }
  })
  win.webContents.on('did-fail-load', (_event, code, description, url, isMainFrame) => {
    if (isMainFrame && code !== -3 && !url.startsWith('file:')) showOffline(`页面加载失败：${description}`)
  })
  win.on('close', () => writeConfig({ bounds: win.getBounds() }))
  openServer()
}

ipcMain.handle('server:get', () => ({ server: currentServer(), fallback: DEFAULT_SERVER }))
ipcMain.handle('server:test', (_event, value) => probe(value))
ipcMain.handle('server:save', async (_event, value) => {
  writeConfig({ server: normalize(value) })
  await openServer()
  return currentServer()
})
ipcMain.handle('server:retry', () => openServer())

const buildMenu = () =>
  Menu.setApplicationMenu(
    Menu.buildFromTemplate([
      {
        label: '学业管家',
        submenu: [
          { label: '重新加载', accelerator: 'F5', click: () => openServer() },
          { label: '更换服务器…', click: () => showOffline('') },
          { type: 'separator' },
          { label: '开发者工具', accelerator: 'F12', click: () => win?.webContents.toggleDevTools() },
          {
            label: '关于',
            click: () =>
              dialog.showMessageBox(win, {
                title: '关于学业管家',
                message: `学业管家 ${app.getVersion()}`,
                detail: `课表 × 待办 × 专注 × 成长\n当前服务器：${currentServer()}\n璞玉计划项目小组`,
              }),
          },
          { type: 'separator' },
          { label: '退出', role: 'quit' },
        ],
      },
    ]),
  )

if (!app.requestSingleInstanceLock()) {
  app.quit()
} else {
  app.on('second-instance', () => {
    if (win) {
      if (win.isMinimized()) win.restore()
      win.focus()
    }
  })
  app.whenReady().then(() => {
    buildMenu()
    createWindow()
  })
  app.on('window-all-closed', () => app.quit())
}
