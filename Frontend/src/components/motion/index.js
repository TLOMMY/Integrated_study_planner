/**
 * 动效与情绪图形的注册表。
 *
 * 功能图标（导航、按钮、列表）统一用 lucide 线性图标；需要"情绪"的地方用这里登记的原创 SVG 组件。
 * 每个组件只用主题变量取色（rgb(var(--c-xxx))），换主题自动跟随；系统开了"减少动态效果"时显示最后一帧。
 * 想换一套样式：新写一个同样 props 的组件，改这里的映射即可，调用处不用动。
 *
 *   celebrate.checkin  打卡成功      props: days, from, play, size
 *   celebrate.level    升级 / 成就   props: level, play, size（默认插槽可换中间的图形）
 *   status.taskCheck   任务完成圈    props: done, ringClass
 */
import LevelBadge from './LevelBadge.vue'
import StreakFlame from './StreakFlame.vue'
import TaskCheck from './TaskCheck.vue'

export const motion = {
  celebrate: { checkin: StreakFlame, level: LevelBadge },
  status: { taskCheck: TaskCheck },
}

export { LevelBadge, StreakFlame, TaskCheck }
