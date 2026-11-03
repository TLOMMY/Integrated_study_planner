/**
 * 新手教程：步骤定义 + 气泡定位（纯函数，便于单测）。
 * 每步的 target 是 data-tour 名称；电脑（lg）与手机布局不同，分别给 desktop / mobile。
 * 找不到目标（或 target 为空）时气泡居中显示，不会卡住。
 */

export const TOUR_STEPS = [
  {
    key: 'welcome',
    title: '欢迎来到学业管家',
    text: '用 1 分钟认识 5 个最常用的功能：导入课表 → 添加任务 → 开始专注 → AI 助手 → 成长。随时可以跳过，之后也能在「设置 → 帮助」里重新查看。',
    icon: 'lucide:sparkles',
  },
  {
    key: 'import',
    title: '第 1 步：导入课表',
    text: '点这里导入课表：教务系统网页、Excel 文件、课表截图 / PDF（AI 识别），也可以用同学的分享码。导入后首页、日程和 AI 排程都会避开上课时间。',
    route: '/timetable',
    desktop: 'timetable-import',
    mobile: 'timetable-import',
    icon: 'lucide:file-up',
  },
  {
    key: 'task',
    title: '第 2 步：添加任务',
    text: '写下要做的事，可以设日期、时间、提醒、子任务和标签。完成任务能获得 XP，也算今天打卡。',
    route: '/today-task',
    desktop: 'task-add',
    mobile: 'task-add',
    icon: 'lucide:circle-check-big',
  },
  {
    key: 'focus',
    title: '第 3 步：开始专注',
    text: '番茄钟计时，可配白噪音或你自己的歌单。专注满 5 分钟就算今天打卡；任务旁的 ▶ 可以直接为这个任务计时。',
    // 电脑：侧边栏的「开始专注」；手机：没有常驻入口，直接打开专注页指向开始按钮
    route: '/today-task',
    mobileRoute: '/focus-timer',
    desktop: 'focus-start',
    mobile: 'focus-start',
    icon: 'lucide:timer',
  },
  {
    key: 'ai',
    title: '第 4 步：AI 助手',
    text: '直接说“这周每天两小时复习高数，晚上学”，AI 会看你的课表和空闲时间排好任务，先给你卡片确认，再导入。没接大模型时由本地规则引擎处理。',
    route: '/today-task',
    desktop: 'nav-ai',
    mobile: 'nav-ai',
    icon: 'lucide:bot',
  },
  {
    key: 'growth',
    title: '第 5 步：成长',
    text: '这里看等级、成就、连续打卡和学习热力图。每天专注满 5 分钟或完成 1 个任务就算打卡，连续 7 天还能获得断签保护卡。',
    route: '/today-task',
    desktop: 'nav-growth',
    mobile: 'nav-growth',
    icon: 'lucide:trophy',
  },
  {
    key: 'done',
    title: '准备好了',
    text: '更多用法（包括 AI 规则引擎能听懂的写法）都在「设置 → 使用手册」里。祝学习顺利！',
    icon: 'lucide:party-popper',
  },
]

export const targetFor = (step, desktop) => (desktop ? step.desktop : step.mobile) || null

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
