<div align="center">

<img src="Frontend/public/icons/icon-192.png" width="96" alt="学业管家" />

# 学业管家 · Integrated Study Planner

**课表 · 待办 · 专注 · 成长 一体化的大学生学习规划系统**

网页版 · Windows 客户端 · Android 客户端　|　域名：`xueyeguanjia.com`

[中文](#中文) · [English](#english)

<img src="docs/screenshots/desktop-home.png" width="860" alt="电脑端首页" />

</div>

---

<a id="中文"></a>

## 中文

### 项目简介

学业管家是面向大学生的学习规划系统。它以课表为基础，把课程安排、学习任务、专注计时、学习激励与 AI 规划统一在同一个账号和同一份数据中：课表决定可用时间，AI 在空闲时段内安排学习任务，专注时长记录到具体任务上，完成情况实时转化为经验值、等级与连续学习天数。

### 现有应用的局限

| 应用类型 | 常见局限 |
|---|---|
| 课程表类应用 | 只记录上课时间，不知道课余时间用来做什么；无法把复习计划与课表关联 |
| 通用待办清单 | 不了解课程安排，任务时间需要手动避开上课时段；缺少面向学习的统计与反馈 |
| 学习打卡、激励类应用 | 激励与真实学习任务脱节，打卡数据无法反映课程与计划的完成情况 |
| AI 对话助手 | 不了解个人课表与已有安排，给出的计划无法直接执行，需要手动誊抄 |

学生通常需要在多个应用之间来回切换、重复录入，数据彼此割裂。

### 学业管家的完整功能

**课表管理**
- 节次网格课表，按教学周切换，支持单双周与不连续周（如 `1-3周,18周`）
- 课程时间冲突检测，自定义开学日期、总周数与每节课时间
- 三种导入方式：教务系统网页（正方、强智、青果等常见格式）、Excel 课表文件、图片或 PDF 经大模型识别
- 课前 10 分钟提醒

**任务与日程**
- 今天、即将、已完成三种任务视图，逾期任务一键移到今天
- 四级优先级、重复任务（每天、工作日、每周）、未定时间的全天任务
- 按标题、科目、备注搜索全部任务；多选后批量删除或修改日期
- 日、周、月三种日程视图，课程与任务按时间顺序统一展示

**专注计时**
- 番茄钟可关联具体任务，预设时长与自定义时长（1–180 分钟）
- 基于时间戳计时，切换页面、锁屏或刷新不影响准确性；提前结束按实际分钟记录

**成长激励**
- 经验值与等级、连续学习天数及断签提醒、每日专注目标
- 15 项成就、本周经验值排行榜、学习热力图、近 7 天与近 30 天统计
- 奖励按"用户、原因、对象"唯一记账，重复操作不会重复计分，撤销完成会相应扣回

**AI 学习规划**
- 读取个人课表与已有任务，只在真实空闲时段内安排学习，并避开用餐时间与深夜
- 每次回复分为两部分：学习建议，以及可直接导入的结构化计划（日程任务与新增课程），可按天勾选导入
- 识别"11.1-11.10""11月5日前""下周"等日期表达；结合最近 10 轮对话记忆，追问时只修改提到的部分
- 支持任何 OpenAI 兼容模型（DeepSeek、通义千问、Kimi、智谱、Ollama 等），密钥加密保存；无模型时由本地规则引擎完成规划
- 按学习时段偏好排程：根据近 60 天专注记录自动判断，也可自定义优先时段、避开时段与单次时长

**学习计划**
- 手动创建或由 AI 生成，显示进度与专注时长
- 进行中、已完成、已归档三种状态；删除的计划进入回收站，30 天内可恢复，支持多选恢复、彻底删除与一键清空

**账号与安全**
- 邮箱注册登录、演示账号；绑定邮箱与手机号、修改密码、退出其他设备
- 连续输错密码 5 次锁定 10 分钟；修改密码后其他设备上的登录立即失效
- 导出全部个人数据、注销账号；问题反馈以文本文件保存，便于技术人员处理

**多端使用**
- 手机、平板、电脑自适应布局；电脑端为侧边栏与多栏布局，支持作为独立窗口安装（PWA）
- Windows 客户端与 Android 客户端，与网页版连接同一服务器，账号数据实时一致；客户端内可切换服务器地址

### 功能截图

| 课表 | 周视图 |
|---|---|
| <img src="docs/screenshots/desktop-timetable.png" alt="课表" /> | <img src="docs/screenshots/desktop-week.png" alt="周视图" /> |
| **AI 学习规划** | **从教务系统网页导入课表** |
| <img src="docs/screenshots/desktop-ai.png" alt="AI 学习规划" /> | <img src="docs/screenshots/desktop-import.png" alt="课表导入" /> |
| **成长统计** | **设置** |
| <img src="docs/screenshots/desktop-stats.png" alt="成长统计" /> | <img src="docs/screenshots/desktop-settings.png" alt="设置" /> |

<details>
<summary>手机端截图</summary>

| 今日 | 课表 | 日程 | 专注 | 成长 | AI |
|---|---|---|---|---|---|
| <img src="docs/screenshots/mobile-home.png" width="150" /> | <img src="docs/screenshots/mobile-timetable.png" width="150" /> | <img src="docs/screenshots/mobile-day.png" width="150" /> | <img src="docs/screenshots/mobile-focus.png" width="150" /> | <img src="docs/screenshots/mobile-stats.png" width="150" /> | <img src="docs/screenshots/mobile-ai.png" width="150" /> |

</details>

### 版本迭代

**v1.0 · 基础模块**
- 后端 FastAPI 框架与 SQLite 数据库设计
- 教务 Excel 课表解析、PDF 章节提取与导入接口
- 学习任务与学习计划的基础接口
- 接入 DeepSeek 生成学习计划
- Vue 3 前端页面框架

**v2.0 · 系统重构与联动**
- 统一接口协议 `{code, message, data}`，JWT 鉴权与用户数据隔离，前后端接口契约测试
- 课表支持教学周、单双周、冲突检测，自动识别开学日期与总周数
- 任务视图、优先级、重复任务、自然语言快速添加
- 番茄钟专注计时，专注时长记录到任务
- 经验值、等级、连续打卡、成就、排行榜与学习热力图
- AI 规划改为读取课表、按空闲时段排程，先生成草稿、确认后导入；无模型时使用规则引擎
- 日、周、月日程视图；旧数据库启动时自动升级

**v3.0 · 智能化与多端**
- AI 支持自定义 OpenAI 兼容模型；回复分为学习建议与结构化计划，可按天导入；10 轮对话记忆与日期范围识别
- 课表新增教务系统网页导入与图片、PDF 的 AI 识别导入
- 学习时段偏好设置，AI 排程优先安排习惯时段
- 设置页：绑定邮箱与手机号、修改密码、退出其他设备、数据导出、注销账号、问题反馈
- 任务搜索与批量操作；学习计划回收站与归档
- 登录失败锁定、修改密码后旧凭证失效
- 电脑端多栏布局与 PWA 安装；Windows 与 Android 客户端

### 本地运行

环境要求：Python 3.11 及以上，Node.js 20 及以上。

```bash
# 后端：http://127.0.0.1:8000，接口文档 http://127.0.0.1:8000/docs
cd Backend+AI-interface
python -m venv .venv
.venv\Scripts\activate            # macOS / Linux：source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn main:app --reload

# 前端：http://localhost:5173（/api 自动转发到后端）
cd Frontend
npm install
npm run dev
```

打开 <http://localhost:5173>，点击「一键体验演示账号」即可查看预置的课表、计划、学习记录与排行榜（`demo@example.com` / `demo123456`）。

如需使用大模型，在 `Backend+AI-interface/.env` 中配置 `DEEPSEEK_API_KEY`（配置项参考 `deploy/backend.env.example`），或登录后在「AI 规划 → 设置」中添加模型。未配置时由本地规则引擎完成规划。

### 打包客户端

```bash
# Windows：在 desktop/dist/ 生成安装版与免安装版 exe
cd desktop
npm install
npm run dist

# Android：需要 JDK 21 与 Android SDK（platform 36、build-tools 36）
cd Frontend
npm run build
npx cap sync android
cd android
gradlew assembleRelease
```

### 项目结构

```
Backend+AI-interface/   后端：FastAPI + SQLAlchemy 2 + SQLite
  app/api/routes/       认证、用户、任务、课表、导入、专注统计、学习计划与 AI、模型设置、反馈
  app/services/         课表与周次、课表解析、任务、成长激励、日程聚合、学习偏好
  app/ai/               需求解析、空闲时段排程、模型客户端、图片与 PDF 识别
  tests/                后端测试
Frontend/               前端：Vue 3 + Vite + Pinia + Tailwind CSS
  android/              Android 客户端工程（Capacitor）
desktop/                Windows 客户端（Electron）
deploy/                 服务器配置文件
docs/                   功能截图与数据库设计文档
data-import/            课表解析原型与示例课表
```

### 测试

```bash
cd Backend+AI-interface && python -m pytest     # 后端 91 个用例，使用临时数据库，不访问外网
cd Frontend && npm test                          # 前端 6 个单元测试
cd Frontend && npm run build                     # 生产构建
```

后端测试覆盖认证与数据隔离、课表与导入、任务、成长激励、AI 规划与模型接入、账号安全、回收站与批量操作，并包含前后端接口契约测试：前端调用的每一个接口都必须在后端存在，否则测试失败。

### 路线图

| 版本 | 状态 | 内容 |
|---|---|---|
| v1.0 | ✅ 已完成 | 基础模块：后端框架、课表解析、任务与计划接口、DeepSeek 接入、前端框架 |
| v2.0 | ✅ 已完成 | 系统重构：统一协议与鉴权、课表周次、任务体系、专注计时、成长激励、空闲时段排程 |
| v3.0 | ✅ 已完成 | 智能化与多端：多模型 AI、多种课表导入、学习偏好、账号安全、Windows 与 Android 客户端 |

### AI 贡献

Claude 参与了前端的设计与美化。

### 团队

璞玉计划项目小组

---

<a id="english"></a>

## English

### Overview

XueYeGuanJia is a study planning system for university students. Built around the class timetable, it brings courses, study tasks, focus sessions, motivation and AI planning into a single account and a single data set: the timetable defines available time, the AI schedules study tasks into free slots, focus time is recorded against specific tasks, and progress is converted into experience points, levels and study streaks in real time.

### Limitations of existing apps

| App category | Common limitations |
|---|---|
| Timetable apps | Record class times only; no link between free time and revision plans |
| General to-do lists | Unaware of the class schedule, so tasks must be manually kept clear of lectures; no study-oriented statistics |
| Habit and motivation apps | Rewards are detached from real study tasks; streaks do not reflect course or plan progress |
| AI chat assistants | Do not know the user's timetable or existing commitments; plans cannot be executed directly and must be copied by hand |

Students typically switch between several apps, re-enter the same information and end up with fragmented data.

### Features

**Timetable**
- Period-grid timetable by teaching week, with odd/even and non-contiguous weeks (e.g. `1-3, 18`)
- Conflict detection; configurable semester start, number of weeks and period times
- Three import methods: the school's academic-affairs web pages (ZhengFang, QiangZhi, QingGuo and similar), Excel files, and images or PDFs recognised by a large language model
- Reminders 10 minutes before class

**Tasks and calendar**
- Today, Upcoming and Completed views; move overdue tasks to today in one step
- Four priority levels, repeating tasks (daily, weekdays, weekly) and all-day tasks without a fixed time
- Search across titles, subjects and notes; multi-select to delete or reschedule in bulk
- Day, week and month views with courses and tasks shown together in chronological order

**Focus timer**
- Pomodoro sessions linked to tasks, with presets and custom durations (1–180 minutes)
- Timestamp-based timing that stays accurate across page switches, screen locks and reloads; early finishes are recorded by actual minutes

**Motivation**
- Experience points and levels, study streaks with at-risk alerts, daily focus goal
- 15 achievements, weekly leaderboard, study heatmap, 7-day and 30-day statistics
- Rewards are booked once per user, reason and target, so repeated actions never double-count and undoing a completion revokes its reward

**AI study planning**
- Reads the user's timetable and existing tasks and schedules only into real free slots, avoiding meal times and late nights
- Every reply has two parts: study advice and a structured, importable plan (tasks and new courses), with per-day selection for import
- Understands date expressions such as "11.1-11.10", "before 5 Nov" and "next week"; remembers the last 10 turns and changes only what the user asks to change
- Works with any OpenAI-compatible model (DeepSeek, Qwen, Kimi, GLM, Ollama and others) with encrypted key storage; a local rule engine handles planning when no model is configured
- Schedules by study-time preference, either learned from the last 60 days of focus records or set manually (preferred and avoided periods, session length)

**Study plans**
- Created manually or generated by AI, with progress and focus time
- Active, Completed and Archived states; deleted plans go to a recycle bin for 30 days, with multi-select restore, permanent deletion and empty-bin

**Account and security**
- Email sign-up and sign-in, demo account; email and phone binding, password change, sign out of other devices
- Lockout for 10 minutes after 5 failed sign-in attempts; other sessions are revoked when the password changes
- Full data export, account deletion, and in-app feedback saved as text files for the maintainers

**Multi-platform**
- Responsive layout for phones, tablets and desktops; sidebar and multi-column layout on desktop, installable as a standalone window (PWA)
- Windows and Android clients connected to the same server as the web app, so account data stays consistent; the server address can be changed in the client

### Screenshots

See the [Chinese section](#功能截图) above for desktop and mobile screenshots.

### Release history

**v1.0 · Foundations**
- FastAPI backend and SQLite schema
- Excel timetable parsing, PDF chapter extraction and import endpoints
- Basic task and study-plan APIs
- DeepSeek-based plan generation
- Vue 3 frontend skeleton

**v2.0 · Rebuild and integration**
- Unified `{code, message, data}` protocol, JWT authentication with per-user isolation, frontend–backend API contract tests
- Teaching weeks, odd/even weeks, conflict detection, automatic semester detection on import
- Task views, priorities, repeating tasks, natural-language quick add
- Pomodoro focus timer recorded against tasks
- Experience points, levels, streaks, achievements, leaderboard and heatmap
- AI planning based on the timetable and free slots, draft-then-confirm import, rule-engine fallback
- Day, week and month views; automatic upgrade of older databases at startup

**v3.0 · Intelligence and multi-platform**
- Custom OpenAI-compatible models; two-part replies with per-day import; 10-turn memory and date-range recognition
- Timetable import from academic-affairs web pages and AI recognition of images and PDFs
- Study-time preferences used by the scheduler
- Settings: email and phone binding, password change, sign out of other devices, data export, account deletion, feedback
- Task search and bulk actions; recycle bin and archiving for study plans
- Sign-in lockout and session revocation on password change
- Desktop multi-column layout and PWA installation; Windows and Android clients

### Run locally

Requires Python 3.11+ and Node.js 20+.

```bash
# Backend: http://127.0.0.1:8000, API docs at /docs
cd Backend+AI-interface
python -m venv .venv
.venv\Scripts\activate            # macOS / Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn main:app --reload

# Frontend: http://localhost:5173 (/api is forwarded to the backend)
cd Frontend
npm install
npm run dev
```

Open <http://localhost:5173> and choose "一键体验演示账号" (demo account) to explore a pre-filled timetable, plans, study history and leaderboard (`demo@example.com` / `demo123456`).

To use a large language model, set `DEEPSEEK_API_KEY` in `Backend+AI-interface/.env` (see `deploy/backend.env.example` for all options), or add a model under AI → Settings after signing in. Without a model, the local rule engine handles planning.

### Build the clients

```bash
# Windows: installer and portable exe in desktop/dist/
cd desktop && npm install && npm run dist

# Android: requires JDK 21 and Android SDK (platform 36, build-tools 36)
cd Frontend && npm run build && npx cap sync android
cd android && gradlew assembleRelease
```

### Project layout

```
Backend+AI-interface/   Backend: FastAPI + SQLAlchemy 2 + SQLite
Frontend/               Frontend: Vue 3 + Vite + Pinia + Tailwind CSS
  android/              Android client (Capacitor)
desktop/                Windows client (Electron)
deploy/                 Server configuration files
docs/                   Screenshots and database design documents
data-import/            Timetable parsing prototypes and a sample timetable
```

### Tests

```bash
cd Backend+AI-interface && python -m pytest     # 91 backend cases, temporary database, no network access
cd Frontend && npm test                          # 6 frontend unit tests
cd Frontend && npm run build                     # production build
```

Backend tests cover authentication and data isolation, timetable and import, tasks, motivation, AI planning and model integration, account security, recycle bin and bulk actions, plus a contract test that fails if the frontend calls any endpoint the backend does not provide.

### Roadmap

| Version | Status | Scope |
|---|---|---|
| v1.0 | ✅ Done | Foundations: backend framework, timetable parsing, task and plan APIs, DeepSeek integration, frontend skeleton |
| v2.0 | ✅ Done | Rebuild: unified protocol and auth, teaching weeks, task system, focus timer, motivation, free-slot scheduling |
| v3.0 | ✅ Done | Intelligence and multi-platform: multi-model AI, multiple import methods, study preferences, account security, Windows and Android clients |

### AI contribution

Claude contributed to the design and visual polish of the frontend.

### Team

PuYu Project Team (璞玉计划项目小组)
