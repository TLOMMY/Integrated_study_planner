<div align="center">

<img src="Frontend/public/icons/icon-192.png" width="96" alt="学业管家 logo" />

# 学业管家 · Integrated Study Planner

**课表 × 待办 × 专注 × 成长** —— 把 WakeUp 课程表、滴答清单、多邻国的长处整合成一个学习规划应用

网页版 · Windows 客户端 · Android App（iOS 规划中）· 正式地址 <https://app.xueyeguanjia.com>（部署中）

[中文](#中文) · [English](#english) · [下载 Download](https://github.com/TLOMMY/Integrated_study_planner/releases)

<img src="docs/screenshots/desktop-home.png" width="860" alt="电脑端首页" />

</div>

---

<a id="中文"></a>

## 中文

### 这是什么

面向大学生的学习规划应用。三类常用 App 各管一摊、互不相通：课表在 WakeUp，待办在滴答清单，坚持靠多邻国的打卡。学业管家把它们放进同一个账号，并让它们**互相联动**：

| 对标 | 学业管家的实现 |
|---|---|
| **WakeUp 课程表** | 节次网格课表、教学周切换、单双周与不连续周（如 `1-3周,18周`）、时间冲突检测、课前 10 分钟提醒；导入支持 **教务系统网页**（正方 / 强智 / 青果等）、**Excel**，以及 **图片 / PDF 交给 AI 识别** |
| **滴答清单** | 今天 / 即将 / 已完成视图、逾期一键挪到今天、四级优先级、重复任务、任务搜索、**多选批量删除或改日期**、日 / 周 / 月三种日程视图 |
| **多邻国** | XP 与等级、连续打卡与断火提醒、每日专注目标、15 个成就、本周 XP 排行榜、学习热力图、升级 / 达成目标的庆祝动画 |
| **AI 学习规划** | 读取你的课表和已有任务，只在**真实空闲时段**排程；回复分为「学习建议」+「可直接导入的结构化计划」，可按天勾选导入；支持任何 OpenAI 兼容模型（DeepSeek、通义千问、Kimi、智谱、Ollama…），记住最近 10 轮对话 |

联动是重点：番茄钟记在任务上；完成任务、专注都会实时结算 XP、连续天数与成就；AI 会按你的专注习惯（上午 / 下午 / 晚上哪段专注最多）优先安排。

### 功能截图

| 课表（教学周、单双周、冲突检测） | 周视图（课程与任务按时间排列） |
|---|---|
| <img src="docs/screenshots/desktop-timetable.png" alt="课表" /> | <img src="docs/screenshots/desktop-week.png" alt="周视图" /> |
| **AI 规划：学习建议 + 结构化计划** | **从教务系统网页导入课表** |
| <img src="docs/screenshots/desktop-ai.png" alt="AI 规划" /> | <img src="docs/screenshots/desktop-import.png" alt="课表导入" /> |
| **成长：等级、打卡、热力图、排行榜** | **设置：账号安全、学习时段偏好、反馈** |
| <img src="docs/screenshots/desktop-stats.png" alt="成长" /> | <img src="docs/screenshots/desktop-settings.png" alt="设置" /> |

<details>
<summary>手机端截图（点击展开）</summary>

| 今日 | 课表 | 日程 | 专注 | 成长 | AI |
|---|---|---|---|---|---|
| <img src="docs/screenshots/mobile-home.png" width="150" /> | <img src="docs/screenshots/mobile-timetable.png" width="150" /> | <img src="docs/screenshots/mobile-day.png" width="150" /> | <img src="docs/screenshots/mobile-focus.png" width="150" /> | <img src="docs/screenshots/mobile-stats.png" width="150" /> | <img src="docs/screenshots/mobile-ai.png" width="150" /> |

</details>

### 下载与使用

所有客户端都只是"外壳"，连接同一个后端服务器，所以**同一个账号在网页、电脑、手机上看到的是同一份数据**，排行榜也是大家一起比。

| 平台 | 获取方式 | 说明 |
|---|---|---|
| 网页版 | <https://app.xueyeguanjia.com> | 电脑浏览器打开即可；Edge / Chrome 地址栏点「安装」可装成独立窗口 |
| Windows | [Releases](https://github.com/TLOMMY/Integrated_study_planner/releases)：`XueYeGuanJia-3.0.0-setup.exe`（安装版）/ `-portable.exe`（免安装） | 未做代码签名，首次运行若出现 SmartScreen 提示，点「更多信息 → 仍要运行」 |
| Android | [Releases](https://github.com/TLOMMY/Integrated_study_planner/releases)：`XueYeGuanJia-3.0.0.apk` | Android 7.0+；安装时允许「安装未知来源应用」 |
| iOS | 规划中 | 需要 Apple 开发者账号；目前可在 Safari 打开网页版并「添加到主屏幕」 |

> 正式服务器上线前，客户端可以连接局域网里的电脑：在 Windows 客户端的「连接服务器」页、或 Android 登录页底部的「服务器」里，填运行项目那台电脑的地址，如 `http://192.168.1.5:5173`。

### 本地运行

需要 **Python 3.11+**（开发环境 3.14）与 **Node.js 20+**。

```bash
# 1. 后端：http://127.0.0.1:8000，接口文档 http://127.0.0.1:8000/docs
cd Backend+AI-interface
python -m venv .venv
.venv\Scripts\activate            # macOS / Linux：source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn main:app --reload

# 2. 前端：http://localhost:5173（/api 自动代理到 8000）
cd Frontend
npm install
npm run dev
```

打开 <http://localhost:5173>，点 **「一键体验演示账号」** 即可看到预置的课表、计划、45 天学习记录与排行榜（`demo@example.com` / `demo123456`）。

**可选配置**：复制 `deploy/backend.env.example` 为 `Backend+AI-interface/.env` 并按需修改。填写 `DEEPSEEK_API_KEY` 后 AI 规划由大模型完成；不填时使用本地规则引擎，功能同样完整。每位用户也可以在「AI 规划 → 设置」里接入自己的模型。

**局域网演示**（手机和同学的电脑一起用）：

```bash
cd Frontend
npm run dev -- --host            # 终端会显示 http://<本机IP>:5173
```

同一 Wi-Fi 下的设备打开该地址即可（Windows 防火墙弹窗时选「允许」；校园网若有设备隔离，改用手机热点）。

### 部署到服务器（xueyeguanjia.com）

规划的地址分配：

| 地址 | 内容 |
|---|---|
| `xueyeguanjia.com` / `www` | 介绍与下载页（暂未上线时自动跳到网页版） |
| `app.xueyeguanjia.com` | 网页版 |
| `app.xueyeguanjia.com/api/` | 后端接口，网页 / Windows / Android / iOS 都连这里 |

步骤：

1. **服务器**：国内云厂商的轻量应用服务器，2 核 2G 及以上、Ubuntu 22.04 / 24.04、包年包月（ICP 备案要求剩余时长 ≥ 3 个月）。
2. **域名与备案**：`xueyeguanjia.com` 完成实名认证后，在云厂商后台提交**个人 ICP 备案**（网站用途：个人学习规划工具，提供网页版及客户端下载）。备案通过前不要用域名对外提供访问。
3. **解析**：添加 `@`、`www`、`app` 三条 A 记录指向服务器公网 IP。
4. **一键部署**（自动安装依赖、生成随机密钥、打包前端、配置 systemd + Nginx + HTTPS 证书 + 每日备份）：

   ```bash
   git clone https://github.com/TLOMMY/Integrated_study_planner.git
   cd Integrated_study_planner
   sudo bash deploy/install.sh 你的邮箱@example.com
   ```

5. **上线后**：网站底部展示备案号并链接 `beian.miit.gov.cn`；30 天内在 `beian.mps.gov.cn` 完成公安备案。
6. **更新版本**：再次运行 `sudo bash deploy/install.sh 你的邮箱`（会拉取最新代码并重启，数据与配置保留）。

| 文件 | 作用 |
|---|---|
| `deploy/install.sh` | 一键部署 / 更新脚本 |
| `deploy/nginx/xueyeguanjia.conf` | 三个域名的 Nginx 配置（HTTPS、单页应用路由、`/api` 反向代理） |
| `deploy/xueyeguanjia.service` | 后端常驻服务（开机自启、崩溃自动重启） |
| `deploy/backend.env.example` | 生产环境配置模板（安装后位于 `/etc/xueyeguanjia/backend.env`） |
| `deploy/backup.sh` | 每天 3:30 备份数据库，保留 30 天 |

> 生产环境务必：`JWT_SECRET_KEY` 使用随机长字符串（install.sh 会自动生成）、`AI_ALLOW_PRIVATE_URLS=0`、`SEED_DEMO=0`；`.env` 与数据库不要提交到仓库。

### 打包客户端

```bash
# Windows：desktop/dist/ 下生成 setup.exe 与 portable.exe
cd desktop
npm install
npm run dist

# Android：需要 JDK 21 + Android SDK（platform 36、build-tools 36）
cd Frontend
npm run build
npx cap sync android
cd android
gradlew assembleRelease          # 输出 app/build/outputs/apk/release/app-release.apk
```

Android 发布签名读取 `Frontend/android/keystore.properties`（不入库，格式见 `app/build.gradle` 注释）；没有该文件时生成未签名包。**签名文件丢失后无法给已安装的用户推送更新，请妥善备份。**

### 项目结构

```
Backend+AI-interface/     后端：FastAPI + SQLAlchemy 2 + SQLite
  app/api/routes/         auth users tasks timetable imports study planning ai_settings feedback
  app/services/           课表与周次、课表解析（Excel / 教务网页）、任务、游戏化、日程聚合、学习偏好
  app/ai/                 中文需求解析、空闲时段排程、OpenAI 兼容客户端、图片 / PDF 识别
  tests/                  91 个 pytest 用例（含前后端接口契约测试）
Frontend/                 前端：Vue 3 + Vite + Pinia + Tailwind（手机 / 平板 / 电脑自适应，PWA）
  android/                Capacitor Android 工程
desktop/                  Windows 客户端（Electron 外壳）
deploy/                   服务器部署脚本与配置
docs/                     截图与早期数据库设计文档
data-import/              课表解析原型脚本与示例课表（测试用）
```

### 设计要点

- **统一接口协议**：所有接口（含报错、校验失败、404）都返回 `{code, message, data}`，`message` 为可直接展示的中文；契约测试保证前端调用的每个接口在后端都存在。
- **账号安全**：JWT 鉴权与数据隔离；密码 PBKDF2 哈希；连续输错 5 次锁定 10 分钟；改密码后其他设备立即下线；API Key 加密存储、只返回掩码。
- **AI 可控**：先出草稿、确认后才写入；模型给出的每个学习块都会校验是否落在真实空闲时段，不合格的剔除，漏排的日子自动补齐，调用失败回退规则引擎。
- **奖励回执**：完成任务、专注、导入等动作统一返回 XP / 升级 / 成就 / 连续天数，按 `(用户, 原因, 引用)` 唯一记账，重复点击不重复加分。
- **数据可回收**：删除的学习计划进入回收站，30 天后自动清除；支持导出全部数据与注销账号。

### 测试

```bash
cd Backend+AI-interface && python -m pytest     # 91 个用例，使用临时数据库，不访问外网
cd Frontend && npm test                          # 6 个前端单元测试
cd Frontend && npm run build                     # 生产构建
```

### 路线图

- [ ] 正式服务器上线（xueyeguanjia.com）与介绍下载页
- [ ] iOS 客户端（TestFlight）
- [ ] 邮箱 / 短信验证码（找回密码、绑定验证）
- [ ] 管理后台（用户、反馈、使用统计）
- [ ] AI 对话与专注进度跨设备同步；App 关闭后的课前推送

### 团队

璞玉计划项目小组。

---

<a id="english"></a>

## English

### What it is

A study planner for university students that combines the strengths of three popular apps — **WakeUp** (class timetable), **TickTick** (to-dos) and **Duolingo** (streaks & motivation) — in one account, and makes them work together.

| Inspired by | What XueYeGuanJia does |
|---|---|
| **WakeUp timetable** | Period-grid timetable, teaching-week switcher, odd/even and non-contiguous weeks (e.g. `1-3,18`), conflict detection, 10-minute class reminders; import from the **school's academic-affairs website** (ZhengFang, QiangZhi, QingGuo…), **Excel**, or **images / PDF recognised by AI** |
| **TickTick** | Today / Upcoming / Completed views, move overdue tasks to today, 4 priority levels, repeating tasks, task search, **multi-select delete or reschedule**, day / week / month calendar views |
| **Duolingo** | XP and levels, streaks with at-risk alerts, daily focus goal, 15 achievements, weekly XP leaderboard, study heatmap, celebration animations |
| **AI planning** | Reads your timetable and existing tasks and only schedules into **real free slots**. Replies have two parts — study advice plus a structured, importable plan (choose which days to import). Works with any OpenAI-compatible model (DeepSeek, Qwen, Kimi, GLM, Ollama…) and remembers the last 10 conversation turns |

Everything is connected: Pomodoro sessions are logged against tasks, completing tasks and focusing settle XP, streaks and achievements in real time, and the AI prefers the time of day you actually focus most.

### Screenshots

See the [Chinese section](#功能截图) above — desktop: timetable, week view, AI planning, timetable import, growth, settings; mobile screenshots are in the collapsible block.

### Download

All clients are thin shells connected to the same backend, so one account shows the same data everywhere and the leaderboard is shared.

| Platform | Get it | Notes |
|---|---|---|
| Web | <https://app.xueyeguanjia.com> | Open in a browser; in Edge / Chrome click "Install" in the address bar for a standalone window |
| Windows | [Releases](https://github.com/TLOMMY/Integrated_study_planner/releases): `XueYeGuanJia-3.0.0-setup.exe` / `-portable.exe` | Not code-signed: on a SmartScreen prompt choose "More info → Run anyway" |
| Android | [Releases](https://github.com/TLOMMY/Integrated_study_planner/releases): `XueYeGuanJia-3.0.0.apk` | Android 7.0+; allow installing from unknown sources |
| iOS | Planned | Requires an Apple Developer account; for now use Safari → "Add to Home Screen" |

> Until the production server is live, clients can connect to a computer on the same LAN: enter its address (e.g. `http://192.168.1.5:5173`) on the Windows "Connect to server" page or under "Server" at the bottom of the Android login screen.

### Run locally

Requires **Python 3.11+** (developed on 3.14) and **Node.js 20+**.

```bash
# 1. Backend: http://127.0.0.1:8000, API docs at /docs
cd Backend+AI-interface
python -m venv .venv
.venv\Scripts\activate            # macOS / Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn main:app --reload

# 2. Frontend: http://localhost:5173 (/api is proxied to port 8000)
cd Frontend
npm install
npm run dev
```

Open <http://localhost:5173> and click **"一键体验演示账号"** (try the demo account) to explore a pre-filled timetable, plans, 45 days of history and the leaderboard (`demo@example.com` / `demo123456`).

**Optional**: copy `deploy/backend.env.example` to `Backend+AI-interface/.env`. With `DEEPSEEK_API_KEY` set, planning uses the LLM; without it a local rule engine provides the full feature set. Each user can also add their own model under AI → Settings.

**LAN demo**: run `npm run dev -- --host` in `Frontend/`, then open the printed `http://<your-ip>:5173` on any device on the same Wi-Fi.

### Deploy (xueyeguanjia.com)

| Address | Serves |
|---|---|
| `xueyeguanjia.com` / `www` | Landing & download page (redirects to the web app until it exists) |
| `app.xueyeguanjia.com` | Web app |
| `app.xueyeguanjia.com/api/` | Backend API used by web, Windows, Android and iOS clients |

1. **Server**: a lightweight cloud instance in mainland China, 2 vCPU / 2 GB+, Ubuntu 22.04 / 24.04, prepaid (ICP filing requires ≥ 3 months remaining).
2. **Domain & ICP filing**: complete real-name verification for `xueyeguanjia.com`, then submit a personal ICP filing through the cloud provider. Do not serve the domain publicly before approval.
3. **DNS**: point `@`, `www` and `app` A records to the server IP.
4. **One-command install** (dependencies, random secrets, frontend build, systemd + Nginx + HTTPS + daily backups):

   ```bash
   git clone https://github.com/TLOMMY/Integrated_study_planner.git
   cd Integrated_study_planner
   sudo bash deploy/install.sh you@example.com
   ```

5. **After launch**: show the ICP number in the site footer linking to `beian.miit.gov.cn`, and complete the public-security filing at `beian.mps.gov.cn` within 30 days.
6. **Updates**: re-run the same command; code is pulled and the service restarted while data and configuration are kept.

In production make sure `JWT_SECRET_KEY` is a long random string (generated by install.sh), `AI_ALLOW_PRIVATE_URLS=0` and `SEED_DEMO=0`; never commit `.env` or the database.

### Build the clients

```bash
# Windows: setup.exe and portable.exe in desktop/dist/
cd desktop && npm install && npm run dist

# Android: needs JDK 21 + Android SDK (platform 36, build-tools 36)
cd Frontend && npm run build && npx cap sync android
cd android && gradlew assembleRelease
```

Release signing reads `Frontend/android/keystore.properties` (not committed). Keep the keystore safe — without it you cannot ship updates to installed users.

### Project layout

```
Backend+AI-interface/   FastAPI + SQLAlchemy 2 + SQLite backend, 91 pytest cases incl. API contract tests
Frontend/               Vue 3 + Vite + Pinia + Tailwind (responsive phone / tablet / desktop, PWA)
  android/              Capacitor Android project
desktop/                Windows client (Electron shell)
deploy/                 Server deployment scripts and configs
docs/                   Screenshots and early database design docs
data-import/            Timetable parsing prototypes and a sample timetable (used by tests)
```

### Highlights

- **One API envelope**: every response, including errors, is `{code, message, data}`; a contract test checks that every frontend call exists on the backend.
- **Account security**: JWT auth with per-user isolation, PBKDF2 password hashes, lockout after 5 failed logins, other sessions revoked on password change, encrypted and masked API keys.
- **Controllable AI**: drafts first, saved only on confirmation; every block is validated against real free slots, invalid blocks are dropped, skipped days are filled in, and failures fall back to the rule engine.
- **Idempotent rewards**: XP is booked once per `(user, reason, reference)`, so repeated clicks never double-count.
- **Recoverable data**: deleted plans go to a 30-day recycle bin; full data export and account deletion are available.

### Tests

```bash
cd Backend+AI-interface && python -m pytest     # 91 cases, temporary database, no network
cd Frontend && npm test && npm run build
```

### Roadmap

- [ ] Production server at xueyeguanjia.com and landing page
- [ ] iOS client (TestFlight)
- [ ] Email / SMS verification codes
- [ ] Admin console (users, feedback, usage)
- [ ] Cross-device sync for AI chats and focus sessions; push reminders when the app is closed

### Team

PuYu Project Team (璞玉计划项目小组).
