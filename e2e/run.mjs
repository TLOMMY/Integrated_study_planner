/**
 * 端到端测试入口：npm test
 *
 * 1. 用临时 SQLite 库启动后端（端口 E2E_API_PORT，默认 8105），不访问外网（DEEPSEEK_API_KEY 置空、邮件走内存）
 * 2. 启动前端开发服务器（端口 E2E_WEB_PORT，默认 5205），/api 代理到上面的后端
 * 3. 用本机 Edge（可用 EDGE_PATH 覆盖）按电脑 1440×900、手机 390×844 各跑一遍 flows.mjs 里的流程
 * 4. 失败时截图到 e2e/artifacts/，最后关掉启动的进程、删掉临时库
 */
import { spawn, execSync } from 'node:child_process'
import { existsSync, mkdirSync, mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium } from 'playwright-core'
import { FLOWS } from './flows.mjs'

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..')
const API_PORT = Number(process.env.E2E_API_PORT || 8105)
const WEB_PORT = Number(process.env.E2E_WEB_PORT || 5205)
const BASE = `http://localhost:${WEB_PORT}`
const ARTIFACTS = join(ROOT, 'e2e', 'artifacts')
const EDGE = process.env.EDGE_PATH || ['C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', 'C:/Program Files/Microsoft/Edge/Application/msedge.exe'].find(existsSync)
const PYTHON = process.env.PYTHON || 'python'
const VIEWPORTS = [
  { name: 'desktop', viewport: { width: 1440, height: 900 } },
  { name: 'mobile', viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true },
]

const children = []
const tmp = mkdtempSync(join(tmpdir(), 'study-e2e-'))

function start(name, cmd, args, options) {
  const child = spawn(cmd, args, { ...options, shell: process.platform === 'win32', stdio: ['ignore', 'pipe', 'pipe'] })
  let log = ''
  const keep = (chunk) => (log = (log + chunk).slice(-4000))
  child.stdout.on('data', keep)
  child.stderr.on('data', keep)
  child.log = () => log
  child.label = name
  children.push(child)
  return child
}

function stopAll() {
  for (const child of children) {
    if (child.exitCode !== null) continue
    try {
      // Windows 上 shell 启动的是 cmd，要连同子进程一起结束
      if (process.platform === 'win32') execSync(`taskkill /pid ${child.pid} /T /F`, { stdio: 'ignore' })
      else child.kill('SIGTERM')
    } catch {
      /* 已退出 */
    }
  }
}

async function waitFor(url, label, child, timeoutMs = 60000) {
  const started = Date.now()
  while (Date.now() - started < timeoutMs) {
    if (child.exitCode !== null) throw new Error(`${label} 启动失败：\n${child.log()}`)
    try {
      const res = await fetch(url)
      if (res.ok) return
    } catch {
      /* 还没起来 */
    }
    await new Promise((r) => setTimeout(r, 500))
  }
  throw new Error(`${label} ${timeoutMs / 1000} 秒内没有就绪：\n${child.log()}`)
}

async function main() {
  if (!EDGE) throw new Error('没有找到 Edge，请用 EDGE_PATH 指定 msedge.exe 的路径')
  rmSync(ARTIFACTS, { recursive: true, force: true }) // 只保留本次运行的失败截图
  mkdirSync(ARTIFACTS, { recursive: true })

  console.log(`→ 启动后端（临时库，端口 ${API_PORT}）`)
  const db = join(tmp, 'e2e.db').replace(/\\/g, '/')
  const api = start('后端', PYTHON, ['-m', 'uvicorn', 'main:app', '--port', String(API_PORT)], {
    cwd: join(ROOT, 'Backend+AI-interface'),
    env: { ...process.env, DATABASE_URL: `sqlite:///${db}`, MAIL_BACKEND: 'memory', FEEDBACK_WEBHOOK: '', DEEPSEEK_API_KEY: '', SEED_DEMO: 'true' },
  })
  await waitFor(`http://127.0.0.1:${API_PORT}/health`, '后端', api)

  console.log(`→ 启动前端开发服务器（端口 ${WEB_PORT}）`)
  const frontend = join(ROOT, 'Frontend')
  execSync('node scripts/build-icons.mjs', { cwd: frontend, stdio: 'ignore' })
  const web = start('前端', 'npx', ['vite', '--port', String(WEB_PORT), '--strictPort'], {
    cwd: frontend,
    env: { ...process.env, VITE_API_TARGET: `http://127.0.0.1:${API_PORT}` },
  })
  await waitFor(`${BASE}/`, '前端', web)
  await waitFor(`${BASE}/api/health`, '前端代理', web)

  const browser = await chromium.launch({ executablePath: EDGE })
  let failed = 0
  let passed = 0
  try {
    for (const vp of VIEWPORTS) {
      console.log(`\n■ ${vp.name}（${vp.viewport.width}×${vp.viewport.height}）`)
      const context = await browser.newContext({ viewport: vp.viewport, isMobile: vp.isMobile, hasTouch: vp.hasTouch, locale: 'zh-CN' })
      const page = await context.newPage()
      page.setDefaultTimeout(10000)
      const errors = []
      page.on('pageerror', (e) => errors.push(e.message))
      const ctx = { page, context, base: BASE, viewport: vp, state: {} }
      for (const flow of FLOWS) {
        if (flow.only && flow.only !== vp.name) continue
        const t0 = Date.now()
        try {
          await flow.run(ctx)
          if (errors.length) throw new Error(`页面脚本报错：${errors.splice(0).join(' | ')}`)
          passed++
          console.log(`  ✓ ${flow.name}（${Date.now() - t0}ms）`)
        } catch (error) {
          failed++
          const shot = join(ARTIFACTS, `${vp.name}-${flow.name.replace(/[^\w\u4e00-\u9fa5]+/g, '_')}.png`)
          await page.screenshot({ path: shot }).catch(() => {})
          console.log(`  ✗ ${flow.name}：${error.message.split('\n')[0]}\n    截图：${shot}`)
          errors.length = 0
          if (flow.critical) break
        }
      }
      await context.close()
    }
  } finally {
    await browser.close()
  }
  console.log(`\n${passed} 通过，${failed} 失败`)
  return failed
}

let code = 1
try {
  code = (await main()) ? 1 : 0
} catch (error) {
  console.error(`\n✗ ${error.message}`)
} finally {
  stopAll()
  await new Promise((r) => setTimeout(r, 500))
  try {
    rmSync(tmp, { recursive: true, force: true })
  } catch {
    /* 数据库文件可能还被占用，系统临时目录会自行清理 */
  }
}
process.exit(code)
