# 智能学习规划系统 | 前端工程

> 基于 Vue3 + Vite + Pinia 的移动端 WebApp 风格前端项目，处于前后端联调阶段。
> 项目前端 UI 约完成 80%，后端接口部分完成，当前目标为整理工程 + 稳定联调。

---

## 一、技术栈

| 技术 | 用途 | 版本状态 |
|------|------|----------|
| **Vue 3** | 前端框架（组合式 API / `<script setup>`） | ✅ 已安装 |
| **Vite** | 构建工具 | ✅ 已配置 |
| **Pinia** | 全局状态管理 | ✅ 多个 Store 已建立 |
| **Vue Router** | 单页路由管理 | ⚠️ 版本需确认（当前 `^5.0.6`，Vue3 可用） |
| **Axios** | HTTP 请求封装 | ✅ 已封装 `request.js` |
| **TailwindCSS** | 原子化 CSS 样式 | ✅ 已配置 |
| **ECharts** | 数据可视化图表 | ✅ 已用于 Statistics |
| **FullCalendar** | 课程表/日历视图 | ✅ 已用于 Timetable |

---

## 二、项目目录结构

```
Integrated_study_planner-qianduan-xiao/
├── .vscode/
│   └── extensions.json          # VSCode 推荐插件配置
├── public/
│   ├── favicon.svg              # 网站图标
│   └── icons.svg                # 图标资源
├── src/
│   ├── api/                     # API 请求封装（按业务模块分层）
│   │   ├── ai.js                # AI 相关接口（/ai/plan, /ai/replan）
│   │   ├── auth.js              # 认证接口（/auth/login, /auth/register）
│   │   ├── day.js               # 日程视图接口
│   │   ├── import.js            # 导入相关接口
│   │   ├── request.js           # Axios 统一封装（baseURL: '/api', token 拦截器）
│   │   ├── statistics.js        # 统计接口（/study/stats）
│   │   ├── study.js             # 学习记录接口（/study/record）
│   │   ├── task.js              # 任务接口（/tasks，后端尚未完成）
│   │   ├── timetable.js         # 课表接口（/timetable，后端尚未完成）
│   │   └── user.js              # 用户接口（/user/me）
│   ├── assets/
│   │   └── main.css             # 全局样式
│   ├── components/              # 公共/业务组件（按页面模块分组）
│   │   ├── ai/                  # AI 助手相关组件（9 个）
│   │   │   ├── AiHeader.vue
│   │   │   ├── AiPlanCard.vue
│   │   │   ├── ChatInput.vue
│   │   │   ├── ChatMessage.vue
│   │   │   ├── EmptyState.vue
│   │   │   ├── MessageAvatar.vue
│   │   │   ├── PlanTaskItem.vue
│   │   │   ├── SuggestionChip.vue
│   │   │   ├── ThinkingBubble.vue
│   │   │   └── TypingCursor.vue
│   │   ├── common/              # 通用公共组件（4 个）
│   │   │   ├── BottomNav.vue
│   │   │   ├── EmptyState.vue
│   │   │   ├── PageHeader.vue
│   │   │   └── ProgressBar.vue
│   │   ├── day/                 # 日程视图组件（3 个）
│   │   │   ├── BottomNav.vue
│   │   │   ├── DayFreeBlock.vue
│   │   │   └── DayTimelineItem.vue
│   │   ├── layout/              # 布局组件
│   │   │   └── BottomNav.vue
│   │   ├── plan/                # 学习计划组件
│   │   │   └── PlanCard.vue
│   │   ├── profile/             # 用户中心组件
│   │   │   └── ProfileStatCard.vue
│   │   ├── statistics/          # 统计组件（2 个）
│   │   │   ├── AchievementBadge.vue
│   │   │   └── StatsCard.vue
│   │   ├── task/                # 任务组件（3 个）
│   │   │   ├── TaskCard.vue
│   │   │   ├── TaskList.vue
│   │   │   └── TaskProgress.vue
│   │   ├── timetable/           # 课表组件（2 个）
│   │   │   ├── CourseCard.vue
│   │   │   └── WeekTabs.vue
│   │   └── today-task/          # 今日任务组件（2 个）
│   │       ├── AddTaskModal.vue
│   │       └── TaskCard.vue
│   ├── composables/             # 组合式函数（业务逻辑复用）
│   │   ├── useFocusTimer.js     # 专注计时器逻辑
│   │   └── usePlanStats.js      # 计划统计逻辑
│   ├── layouts/                 # 页面布局
│   │   └── MainLayout.vue       # 主布局（含底部导航）
│   ├── router/                  # 路由配置
│   │   └── index.js             # 路由表定义
│   ├── stores/                  # Pinia 状态管理（按模块分离）
│   │   ├── aiStore.js           # AI 状态
│   │   ├── dayView.js           # 日程视图状态
│   │   ├── focusStore.js        # 专注计时状态
│   │   ├── plan.js              # 学习计划状态
│   │   ├── statistics.js        # 统计状态
│   │   ├── taskStore.js         # 任务状态
│   │   ├── timetable.js         # 课表状态
│   │   ├── todayTaskStore.js    # 今日任务状态
│   │   └── user.js              # 用户状态
│   ├── utils/                   # 工具函数
│   │   ├── formatter/
│   │   │   └── date.js          # 日期格式化
│   │   ├── mapper/
│   │   │   └── taskMapper.js    # 任务数据映射
│   │   ├── format.js            # 通用格式化
│   │   ├── planMapper.js        # 计划数据映射
│   │   ├── storage.js           # 本地存储封装
│   │   └── token.js             # Token 管理
│   ├── views/                   # 页面视图（8 个主页面）
│   │   ├── AiAssistantView.vue  # AI 学习规划
│   │   ├── DayView.vue          # 日程视图
│   │   ├── FocusTimerView.vue   # 专注计时
│   │   ├── PlansView.vue        # 学习计划
│   │   ├── ProfileView.vue      # 用户中心
│   │   ├── StatisticsView.vue   # 学习统计（ECharts）
│   │   ├── TimetableView.vue    # 课程表（FullCalendar）
│   │   └── TodayTaskView.vue    # 今日任务
│   ├── App.vue                  # 根组件
│   ├── main.js                  # 入口文件（创建 Vue 实例、注册 Pinia/Router）
│   └── style.css                # 全局样式
├── .gitignore                   # Git 忽略规则
├── index.html                   # HTML 入口
├── package-lock.json            # 依赖锁定
├── package.json                 # 项目依赖配置
├── postcss.config.js            # PostCSS 配置
├── README.md                    # 项目说明
├── tailwind.config.js           # TailwindCSS 配置
└── vite.config.js               # Vite 配置（含 Proxy 代理）
```

---

## 三、页面模块与完成状态

| 页面 | 功能描述 | 核心组件/技术 | 联调状态 |
|------|----------|--------------|----------|
| **TodayTask** | 今日任务管理 | `today-task/` 组件 + `todayTaskStore.js` | ⚠️ 前端 UI 完成，后端 `/tasks` 接口缺失 |
| **AIAssistant** | AI 学习计划生成器 | `ai/` 组件（9 个）+ `aiStore.js` | ⚠️ 前端 UI 完成，但前后端逻辑不一致（前端像聊天，后端是 `/ai/plan`） |
| **FocusTimer** | 专注计时器（倒计时 + 记录） | `useFocusTimer.js` + `focusStore.js` | ✅ 已联调 `POST /study/record` |
| **Statistics** | 学习统计与数据图表 | `statistics/` 组件 + ECharts + `statistics.js` | ✅ 已联调 `GET /study/stats` |
| **Profile** | 用户中心（动态信息 + 头像） | `profile/` 组件 + `user.js` | ✅ 已联调 `GET /user/me` |
| **Timetable** | 课程表（周视图 + 交互） | `timetable/` 组件 + FullCalendar + `timetable.js` | ⚠️ 前端 UI 完成，后端 `/timetable` 接口缺失 |
| **Plans** | 学习计划 | `plan/` 组件 + `plan.js` | ⚠️ 前端 UI 完成，后端 `/plans` 接口缺失 |
| **DayView** | 日程视图 | `day/` 组件 + `dayView.js` | ⚠️ 前端 UI 完成，后端接口缺失 |

---

## 四、后端接口现状

### 后端已提供接口

| 接口 | 方法 | 用途 | 前端调用位置 |
|------|------|------|-------------|
| `/study/stats` | GET | 学习统计数据 | `statistics.js` → `StatisticsView.vue` |
| `/study/record` | POST | 提交专注记录 | `study.js` → `FocusTimerView.vue` |
| `/user/me` | GET | 获取用户信息 | `user.js` → `ProfileView.vue` |
| `/auth/login` | POST | 用户登录 | `auth.js` |
| `/auth/register` | POST | 用户注册 | `auth.js` |
| `/ai/plan` | POST | AI 生成学习计划 | `ai.js` → `AiAssistantView.vue` |
| `/ai/replan` | POST | AI 重新规划 | `ai.js` → `AiAssistantView.vue` |

### 后端尚未提供接口（前端已预留）

| 接口 | 方法 | 用途 | 前端预留位置 |
|------|------|------|-------------|
| `/tasks` | - | 任务 CRUD | `task.js` + `taskStore.js` |
| `/plans` | - | 学习计划 | `plan.js` + `plan.js` (store) |
| `/timetable` | - | 课表数据 | `timetable.js` + `timetable.js` (store) |
| `/ai/chat` | - | AI 聊天对话 | `ai.js`（前端聊天 UI 已做，但后端无此接口） |

---

## 五、当前真实进度评估

### 已完成（✅）

1. **工程架构**
   - Vue3 + Vite 项目搭建
   - TailwindCSS 配置
   - PostCSS 配置
   - 移动端 UI 容器（375x812 iPhone 模拟）

2. **路由系统**
   - 8 个页面路由已配置
   - 路由守卫/拦截器（`request.js` 中 `router.push('/login')`）

3. **状态管理**
   - 9 个 Pinia Store 已建立
   - Store 按业务模块分离

4. **API 分层**
   - 10 个 API 模块文件
   - Axios 统一封装（`request.js`）
   - Token 自动携带
   - 响应拦截器

5. **组件体系**
   - 26 个业务组件（按页面分组）
   - 公共组件（BottomNav、PageHeader 等）
   - 布局组件（MainLayout）

6. **工具函数**
   - 日期格式化
   - 数据映射（taskMapper、planMapper）
   - 本地存储封装
   - Token 管理

7. **组合式函数**
   - `useFocusTimer.js`（专注计时逻辑复用）
   - `usePlanStats.js`（计划统计逻辑复用）

8. **已联调模块**
   - Statistics（`GET /study/stats`）
   - FocusTimer（`POST /study/record`）
   - Profile（`GET /user/me`）
   - AI Assistant（`POST /ai/plan`，但逻辑不匹配）

### 进行中/待完善（⚠️）

1. **联调稳定化**
   - 4 个页面仍使用 mock/fallback 数据
   - 需要逐一验证真实后端响应

2. **字段统一**
   - 前后端字段命名可能不一致
   - 需要对照 API 文档核对

3. **AI 模块逻辑对齐**
   - 前端 UI 是聊天形式
   - 后端接口是 `/ai/plan`（计划生成）
   - 需要确认产品形态：聊天机器人 vs 计划生成器

4. **登录流程**
   - `request.js` 中有 `router.push('/login')`
   - 但项目目前没有 `LoginView.vue` 页面
   - 需要补充登录页或移除该逻辑

### 已知问题（❌）

| 问题 | 位置 | 影响 | 建议处理 |
|------|------|------|----------|
| 后端 `/tasks` 未实现 | `task.js` | TodayTask 用假数据 | 等后端或先用 mock |
| 后端 `/plans` 未实现 | `plan.js` | Plans 用假数据 | 等后端或先用 mock |
| 后端 `/timetable` 未实现 | `timetable.js` | Timetable 用假数据 | 等后端或先用 mock |
| AI 前后端不一致 | `ai.js` + `AiAssistantView.vue` | 功能逻辑混乱 | 需产品确认形态 |
| 缺少 Login 页面 | `request.js` | 拦截器跳转报错 | 补充 LoginView 或改拦截逻辑 |
| vue-router 版本 | `package.json` | 可能兼容性问题 | 确认 `^5.0.6` 是否可用 |

---

## 六、开发环境配置

### Vite Proxy（`vite.config.js`）

```javascript
server: {
  proxy: {
    '/api': {
      target: 'http://localhost:8000',
      changeOrigin: true,
      rewrite: path => path.replace(/^\/api/, '')
    }
  }
}
```

### Axios 封装（`src/api/request.js`）

```javascript
const instance = axios.create({
  baseURL: '/api'
});
```

> 开发环境所有 `/api` 开头的请求自动代理到 `http://localhost:8000`。

---

## 七、当前开发策略

**核心原则：先稳定，后优化，一次只处理一个模块。**

### 第一目标：项目稳定运行，页面不白屏

- 检查所有页面的 fallback/mock 数据是否正常
- 确保后端异常时前端有默认值保护

### 第二目标：至少一个页面成功联调真实后端

**推荐从 Statistics 开始**，因为：
- 后端接口 `/study/stats` 已确认存在
- 前端 Store + API + 组件链路完整
- ECharts 图表渲染逻辑已通

### 第三目标：逐模块联调

按优先级顺序：
1. Statistics（已联调，需验证稳定性）
2. FocusTimer（已联调，需验证 POST 数据）
3. Profile（已联调，需验证数据展示）
4. TodayTask（等后端 `/tasks`）
5. Timetable（等后端 `/timetable`）
6. Plans（等后端 `/plans`）
7. AI Assistant（需前后端对齐需求）

---

## 八、快速开始

```bash
# 安装依赖
npm install

# 启动开发服务器（自动代理 API 到 localhost:8000）
npm run dev

# 构建生产环境
npm run build
```

> 开发服务器默认运行在 `http://localhost:5173`。

---

## 九、给组长（非前端背景）的关键信息

### 这个项目是什么？

一个**移动端学习规划 App 的前端**，类似「番茄钟 + 课程表 + AI 学习计划」的组合。

### 前端到底完成了多少？

| 维度 | 完成度 | 说明 |
|------|--------|------|
| UI 界面 | ~80% | 8 个页面都有界面，但部分用假数据 |
| 前端架构 | ~90% | 路由、状态、API、组件体系已搭好 |
| 后端联调 | ~40% | 4 个接口已调通，4 个页面等后端 |
| 整体可用 | ~50% | 能跑起来看效果，但不能全链路跑通 |

### 当前最大风险是什么？

1. **代码混乱**：多次 AI 生成后，可能存在重复组件、冗余逻辑、不一致的命名
2. **假数据陷阱**：部分页面看起来正常，实际都是 mock 数据
3. **AI 模块逻辑不清**：前端像聊天机器人，后端是计划生成器，需求没对齐

### 下一步该让前端同学做什么？

**不要加新功能！** 按这个顺序：

1. **检查 Statistics 页面** → 确认是否真调了 `/study/stats`
2. **检查 FocusTimer** → 确认 POST `/study/record` 是否成功
3. **检查 Profile** → 确认 GET `/user/me` 数据是否正常
4. **整理 AI 模块** → 确认产品需求是「聊天」还是「计划生成」
5. **补充 Login 页面** → 或修改 `request.js` 中的跳转逻辑
6. **等后端补齐接口** → `/tasks`、`/plans`、`/timetable`

---

> 文档版本：v2.0 | 更新日期：2026-05-23 | 适用对象：组长（非前端技术背景）
