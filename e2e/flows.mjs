/**
 * 核心流程。每个流程拿到 { page, context, base, viewport, state }，按顺序执行；
 * critical: true 的流程失败时跳过本尺寸后面的流程（例如没登录上，后面都没意义）。
 */
const assert = (ok, message) => {
  if (!ok) throw new Error(message)
}

/** 关掉可能弹出的庆祝层（升级 / 达成目标 / 新成就）。 */
async function dismissCelebration(page) {
  for (let i = 0; i < 3; i++) {
    const btn = page.getByRole('button', { name: '太棒了' })
    if (!(await btn.isVisible().catch(() => false))) return
    await btn.click()
    await page.waitForTimeout(300)
  }
}

/** 确认框（ConfirmHost）里点某个按钮。 */
const confirmDialog = (page, text) => page.getByRole('alertdialog').getByRole('button', { name: text, exact: true }).click()

export const FLOWS = [
  {
    name: '演示账号登录',
    critical: true,
    async run({ page, base }) {
      await page.goto(`${base}/login`)
      await page.getByText('一键体验演示账号').click()
      await page.waitForURL(/\/today-task/)
      await page.getByPlaceholder('搜索任务：标题、科目、备注').waitFor()
    },
  },
  {
    name: '新建任务',
    async run({ page, state, viewport }) {
      state.title = `端到端测试任务 ${viewport.name} ${Date.now() % 100000}`
      await page.getByRole('button', { name: '添加任务' }).first().click()
      const sheet = page.getByRole('dialog')
      await sheet.getByPlaceholder('准备做什么？').fill(state.title)
      await sheet.getByRole('button', { name: '添加任务' }).click()
      await sheet.waitFor({ state: 'detached' })
      await page.getByText(state.title, { exact: true }).first().waitFor()
    },
  },
  {
    name: '完成任务',
    async run({ page, state }) {
      // 新建的任务没有日期时在「即将」里，带今天日期时在「今天」里：先在当前列表找，找不到用搜索
      let row = page.locator('article, li, div').filter({ has: page.getByText(state.title, { exact: true }) }).filter({ has: page.getByRole('button', { name: '完成任务' }) }).last()
      if (!(await row.count())) {
        await page.getByPlaceholder('搜索任务：标题、科目、备注').fill(state.title)
        row = page.locator('div').filter({ has: page.getByText(state.title, { exact: true }) }).filter({ has: page.getByRole('button', { name: '完成任务' }) }).last()
      }
      await row.getByRole('button', { name: '完成任务' }).click()
      await dismissCelebration(page)
      // 以服务器为准确认已完成
      await page.waitForFunction(async (title) => {
        const res = await fetch(`/api/task/list?view=all&q=${encodeURIComponent(title)}`, { headers: { Authorization: `Bearer ${localStorage.getItem('access_token')}` } })
        const data = (await res.json()).data
        const items = Array.isArray(data) ? data : data?.items || Object.values(data || {}).flat()
        return items.some((t) => t?.title === title && t.completed)
      }, state.title, { polling: 300, timeout: 8000 })
    },
  },
  {
    name: '开始并结束一次专注',
    async run({ page, base }) {
      await page.goto(`${base}/focus-timer`)
      await page.getByRole('button', { name: /开始专注/ }).click()
      await page.getByRole('button', { name: '暂停' }).waitFor()
      // 专注满 1 分钟才会记录：计时基于 Date.now() 差值，把页面时钟往前拨 2 分钟
      await page.evaluate(() => {
        const realNow = Date.now.bind(Date)
        Date.now = () => realNow() + 2 * 60 * 1000 + 5000
      })
      await page.waitForTimeout(1200)
      await page.getByRole('button', { name: '提前完成' }).click()
      await confirmDialog(page, '结束并记录')
      await page.getByText(/专注了 \d+ 分钟|本次未计入/).waitFor()
      await dismissCelebration(page)
      await page.getByRole('button', { name: '完成', exact: true }).click()
      await page.waitForURL((url) => !url.pathname.startsWith('/focus-timer'))
      // 恢复真实时钟，避免影响后面的流程
      await page.reload()
    },
  },
  {
    name: '日程切换日 / 周 / 月',
    async run({ page, base }) {
      await page.goto(`${base}/view`)
      for (const [label, check] of [
        ['周', /\d+月\d+日 – \d+月\d+日/],
        ['月', /\d{4} 年 \d+ 月/],
        ['日', /周[一二三四五六日]|今天|\d+月\d+日/],
      ]) {
        await page.getByRole('button', { name: label, exact: true }).filter({ visible: true }).first().click()
        await page.getByRole('button', { name: label, exact: true, pressed: true }).filter({ visible: true }).first().waitFor()
        await page.getByText(check).first().waitFor()
      }
    },
  },
  {
    name: '打开 AI 页',
    async run({ page, base }) {
      await page.goto(`${base}/ai`)
      await page.locator('textarea, input[type="text"]').filter({ visible: true }).last().waitFor()
    },
  },
  {
    name: '切换主题（深色 → 默认）',
    async run({ page, base }) {
      await page.goto(`${base}/settings`)
      const html = page.locator('html')
      await page.locator('[data-theme-option="dark"]').click()
      await page.waitForFunction(() => document.documentElement.dataset.theme === 'dark')
      const scheme = await html.evaluate((el) => getComputedStyle(el).colorScheme)
      assert(scheme.includes('dark'), `深色主题下 color-scheme 应为 dark，实际 ${scheme}`)
      const bg = await page.evaluate(() => getComputedStyle(document.querySelector('.phone')).backgroundColor)
      assert(bg !== 'rgb(245, 247, 251)', '深色主题下页面底色没有变化')
      // 刷新后仍是深色（本地 + 账号都已保存）
      await page.waitForTimeout(500)
      await page.reload()
      await page.waitForFunction(() => document.documentElement.dataset.theme === 'dark')
      await page.locator('[data-theme-option="default"]').click()
      await page.waitForFunction(() => document.documentElement.dataset.theme === 'default')
      await page.waitForTimeout(500)
    },
  },
  {
    name: '快捷键',
    only: 'desktop',
    async run({ page, base }) {
      await page.goto(`${base}/today-task`)
      await page.getByPlaceholder('搜索任务：标题、科目、备注').waitFor()
      await page.locator('body').click({ position: { x: 5, y: 5 } })
      await page.keyboard.press('Shift+Slash')
      await page.getByRole('dialog', { name: '键盘快捷键' }).waitFor()
      await page.keyboard.press('Escape')
      await page.getByRole('dialog', { name: '键盘快捷键' }).waitFor({ state: 'detached' })
      await page.keyboard.press('g')
      await page.keyboard.press('c')
      await page.waitForURL(/\/timetable/)
      await page.keyboard.press('Control+k')
      await page.waitForURL(/\/today-task/)
      await page.waitForFunction(() => document.activeElement?.getAttribute('aria-label') === '搜索任务')
      // 输入框里按 g、c 不应跳转
      await page.keyboard.type('gc')
      await page.waitForTimeout(300)
      assert(page.url().includes('/today-task'), '在输入框里按键不应触发快捷键')
      await page.keyboard.press('Escape')
    },
  },
  {
    name: '断网可看',
    async run({ page, base, context }) {
      const nav = (label) => page.getByRole('link', { name: label }).filter({ visible: true }).first().click()
      // 先在线访问一次日程（页面代码载入、接口数据写入离线缓存），再回到今日。
      // 开发服务器没有 Service Worker，页面代码只能靠这一次载入；正式部署由 sw.js 预缓存。
      await page.goto(`${base}/today-task`)
      await page.getByPlaceholder('搜索任务：标题、科目、备注').waitFor()
      await nav('日程')
      await page.waitForURL(/\/view/)
      await page.waitForTimeout(800)
      await nav(/^今日/)
      await page.waitForURL(/\/today-task/)
      await page.waitForTimeout(300)
      await context.setOffline(true)
      try {
        // 前端路由切到日程：接口失败，应返回缓存数据并显示离线横幅
        await nav('日程')
        await page.waitForURL(/\/view/)
        await page.getByText('网络已断开，正在显示离线数据').waitFor()
        // 离线写操作：给出提示
        await nav(/^今日/)
        await page.getByRole('button', { name: '添加任务' }).first().click()
        const sheet = page.getByRole('dialog')
        await sheet.getByPlaceholder('准备做什么？').fill('离线时新建')
        await sheet.getByRole('button', { name: '添加任务' }).click()
        await page.getByText(/离线状态下无法保存/).first().waitFor()
      } finally {
        await context.setOffline(false)
      }
      await page.keyboard.press('Escape')
      // 恢复联网后浏览器的 online 事件会自动探测并隐藏横幅；还在的话点「重试」
      const retry = page.getByRole('button', { name: '重试' })
      if (await retry.isVisible().catch(() => false)) await retry.click().catch(() => {})
      await page.getByText('网络已断开').waitFor({ state: 'detached' })
    },
  },
  {
    name: '退出登录',
    async run({ page, base }) {
      await page.goto(`${base}/profile`)
      await page.getByText('退出登录', { exact: true }).click()
      await confirmDialog(page, '退出')
      await page.waitForURL(/\/login/)
      const leftovers = await page.evaluate(() => Object.keys(localStorage).filter((k) => k.startsWith('offline:')).length)
      assert(leftovers === 0, `退出后仍有 ${leftovers} 条离线缓存`)
    },
  },
]
