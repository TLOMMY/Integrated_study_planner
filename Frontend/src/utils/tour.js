/**
 * 新手教程：步骤定义 + 气泡定位（纯函数，便于单测）。
 * 每步的 target 是 data-tour 名称；电脑（lg）与手机布局不同，分别给 desktop / mobile。
 * 找不到目标（或 target 为空）时气泡居中显示，不会卡住。
 * panel：手机上这一步要先打开中心按钮面板（一键排今天、专注都在面板里）；离开这一步时自动收起。
 */

export const TOUR_STEPS = [
  {
    key: 'welcome',
    title: '欢迎来到学业管家',
    text: '1 分钟认识最常用的几处：日程 → 导入课表 → 任务 → 中心 AI 按钮（一键排今天、专注都在这里）→ 成长。随时可以跳过，之后在「设置 → 帮助」里能重新查看。',
    icon: 'lucide:sparkles',
  },
  {
    key: 'day',
    title: '日程：今天的一根时间轴',
    text: '打开 App 先看到这里：课程（沙色）、定了时间的任务（珊瑚色）和空闲时段按时间排在一根珠点轴上。点「空闲 · 点按安排」直接往空闲里加任务；顶部可以切换日 / 周 / 月。',
    route: '/view',
    desktop: 'nav-day',
    mobile: 'nav-day',
    icon: 'lucide:calendar-clock',
  },
  {
    key: 'import',
    title: '导入课表',
    text: '在「课表」点这里导入：教务系统网页（安卓 App 可以在内置浏览器里一键导入）、Excel、截图 / PDF（AI 识别），或同学的分享码。考试安排也能从这里旁边的「考试」一起导入。',
    route: '/timetable',
    desktop: 'timetable-import',
    mobile: 'timetable-import',
    icon: 'lucide:file-up',
  },
  {
    key: 'task',
    title: '任务',
    text: '「任务」页按 今天 / 即将 / 收集箱 / 已完成 分开。点这里添加：可以设日期、时间、提醒、子任务；没想好日期的先放收集箱。完成任务得 XP，也算今天打卡。',
    route: '/today-task',
    desktop: 'task-add',
    mobile: 'task-add',
    icon: 'lucide:circle-check-big',
  },
  {
    key: 'ai',
    title: '中间的 AI 按钮',
    text: '底部正中间的「AI」不是直接跳页，而是打开一个面板：一键排今天、AI 对话、快速添加任务 / 课程 / 考试，以及专注（番茄钟）。',
    route: '/view',
    desktop: 'nav-ai',
    mobile: 'nav-ai',
    icon: 'lucide:sparkles',
  },
  {
    key: 'autoplan',
    title: '一键排今天',
    text: '把待办和考前复习按优先级排进今天的空闲时间，本地计算、不用 AI 次数。先在时间轴上预览，点「全部加入」才写入，排错了可以撤销。',
    route: '/view',
    panel: true,
    desktop: 'day-autoplan',
    mobile: 'panel-autoplan',
    icon: 'lucide:wand-sparkles',
  },
  {
    key: 'focus',
    title: '番茄钟搬到这里了',
    text: '手机上的专注（番茄钟）入口在中间 AI 面板的右下角「专注」；电脑在左侧栏顶部。任务旁的 ▶ 也能直接为这个任务计时。专注满 5 分钟就算今天打卡，安卓 App 锁屏也能看到倒计时。',
    route: '/view',
    panel: true,
    desktop: 'focus-start',
    mobile: 'panel-focus',
    icon: 'lucide:timer',
  },
  {
    key: 'growth',
    title: '成长',
    text: '这里看等级、连续打卡、学习足迹和成就。每天专注满 5 分钟或完成 1 个任务就算打卡，连续 7 天得 1 张断签保护卡。「我的」和「设置」也从这里右上角进入。',
    route: '/view',
    desktop: 'nav-growth',
    mobile: 'nav-growth',
    icon: 'lucide:trophy',
  },
  {
    key: 'done',
    title: '准备好了',
    text: '更多用法（教务导入、AI 能听懂的写法、考试导入）都在「设置 → 使用手册」里。祝学习顺利！',
    icon: 'lucide:party-popper',
  },
]

export const targetFor = (step, desktop) => (desktop ? step.desktop : step.mobile) || null

/** 这一步在当前布局下是否要打开中心按钮面板（只有手机布局有面板）。 */
export const needsPanel = (step, desktop) => Boolean(step?.panel) && !desktop

/**
 * 计算气泡位置。rect：目标的 { top, left, width, height }（null 表示居中）；
 * view：{ width, height }；card：{ width, height }。返回 { top, left, placement }。
 * 优先放在目标下方，放不下放上方；目标很高（如侧边栏）时放右侧；最后都夹在屏幕内（留 12px 边距）。
 */
export function placeCard(rect, view, card, gap = 14, margin = 12) {
  const clampX = (x) => Math.max(margin, Math.min(x, view.width - card.width - margin))
  const clampY = (y) => Math.max(margin, Math.min(y, view.height - card.height - margin))
  if (!rect) return { top: clampY((view.height - card.height) / 2), left: clampX((view.width - card.width) / 2), placement: 'center' }
  const centerX = rect.left + rect.width / 2 - card.width / 2
  const below = rect.top + rect.height + gap
  if (below + card.height <= view.height - margin) return { top: below, left: clampX(centerX), placement: 'bottom' }
  const above = rect.top - gap - card.height
  if (above >= margin) return { top: above, left: clampX(centerX), placement: 'top' }
  const right = rect.left + rect.width + gap
  if (right + card.width <= view.width - margin) return { top: clampY(rect.top + rect.height / 2 - card.height / 2), left: right, placement: 'right' }
  return { top: clampY(view.height - card.height - margin), left: clampX(centerX), placement: 'overlay' }
}

/** 高亮框：在目标外扩 pad，并夹在屏幕内。 */
export function spotlight(rect, view, pad = 6) {
  if (!rect) return null
  const left = Math.max(2, rect.left - pad)
  const top = Math.max(2, rect.top - pad)
  return {
    left,
    top,
    width: Math.min(view.width - 2, rect.left + rect.width + pad) - left,
    height: Math.min(view.height - 2, rect.top + rect.height + pad) - top,
  }
}

/** 是否需要自动弹出：已登录、不是演示账号、服务器与本机都没记录看过。 */
export function shouldAutoStart(user, localDone = false) {
  return Boolean(user && !user.is_demo && !user.onboarded && !localDone)
}
