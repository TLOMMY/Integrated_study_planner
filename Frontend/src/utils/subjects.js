/**
 * 课程的分科（课表页的 6 种分科色）：理工 sci / 生化 bio / 史地 his / 文艺 art / 社科 soc / 其他 def。
 *
 * 优先用课程编辑器里选的分科色（course.color 等于某个分科色时）；否则按课程名里的关键词判断。
 * 以前的课程颜色是随机分配的，不代表科目，所以不按色相去猜。
 * 颜色本身来自主题变量 --c-subj-*，各主题自己决定深浅。
 */
import { SUBJECTS } from '../themes/index.js'

// 判断顺序有讲究：生物信息学先算生化，经济数学算社科，程序设计不会被"设计"归到文艺
const RULES = [
  ['bio', /生物|生命|化学|生化|医学|药|解剖|生理|病理|护理|农学|植物|动物|微生物|遗传|基因|食品|环境科学|biolog|chem|medic/i],
  ['soc', /经济|管理|会计|金融|财务|营销|法学|法律|法治|思想|政治|马克思|马原|毛概|毛泽东|习近平|中国特色|近现代史纲要|形势与政策|社会|心理|哲学|教育学|军事|职业|就业|创业|伦理|行政|国际关系|econom|manage|law|politic|psycholog|socio|philosoph/i],
  ['sci', /数学|高数|微积分|线代|线性代数|概率|统计|离散|数值|物理|力学|电路|电子|电工|信号|通信|自动化|控制|计算机|程序|编程|软件|算法|数据|网络|操作系统|编译|人工智能|机器学习|工程|机械|材料|土木|建筑|测量|制图|计算|信息|实验|math|calculus|algebra|physic|comput|program|software|algorithm|data|engineer|network/i],
  ['his', /历史|史学|史纲|中国史|世界史|考古|地理|地质|测绘|气象|海洋|旅游|histor|geograph/i],
  ['art', /英语|日语|法语|德语|俄语|韩语|西班牙语|外语|语文|文学|写作|阅读|汉语|语言|翻译|新闻|传播|艺术|美术|音乐|设计|舞蹈|戏剧|影视|书法|摄影|english|japanese|french|german|literat|writing|\bart\b|music|design/i],
]

const BY_COLOR = new Map(SUBJECTS.flatMap((s) => [[s.bg.toUpperCase(), s.key], [s.ink.toUpperCase(), s.key]]))

/** 课程（或课程名字符串）→ 分科 key。 */
export const subjectOf = (course) => {
  const name = typeof course === 'string' ? course : course?.course_name || course?.title || ''
  const picked = typeof course === 'object' && course?.color ? BY_COLOR.get(String(course.color).toUpperCase()) : null
  if (picked) return picked
  for (const [key, re] of RULES) if (re.test(name)) return key
  return 'def'
}

/** 分科的块底色 / 文字色（CSS 颜色字符串，跟随当前主题）。 */
export const subjectBg = (key) => `rgb(var(--c-subj-${key}))`
export const subjectInk = (key) => `rgb(var(--c-subj-${key}-ink))`

/** 课程块的样式：课表页用分科色块；日程页只用 subjectInk 做 6px 色点。 */
export const subjectStyle = (course) => {
  const key = subjectOf(course)
  return { background: subjectBg(key), '--subj-ink': subjectInk(key) }
}

export { SUBJECTS }
