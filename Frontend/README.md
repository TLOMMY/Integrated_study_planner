# 学业管家 · 前端

Vue 3 + Vite + Pinia + Tailwind CSS。整体说明、启动方式与设计要点见仓库根目录 [README.md](../README.md)。

```bash
npm install
npm run dev      # http://localhost:5173，/api 代理到 http://localhost:8000
npm test         # 单元测试（node:test）
npm run build    # 生产构建
```

## 约定

- **接口**：只在 `src/api/index.js` 定义请求，函数直接返回后端信封里的 `data`，失败抛出 `ApiError`（`status` + 中文 `message`）。新增接口后运行后端 `pytest`，契约测试会校验路径与方法。
- **状态**：`stores/` 下按领域拆分；跨模块联动统一走 `tasks.afterChange()`（刷新首页卡片与今日列表）和 `ui.reward(reward)`（结算 XP / 成就 / 连续打卡并决定是否弹出庆祝层）。
- **反馈**：成功、失败、确认一律使用 `ui.success / ui.fail / await ui.confirm(...)`，不使用 `alert / confirm / prompt`。
- **弹层**：底部弹层用 `components/common/BottomSheet.vue`，统一挂载到 `#overlay-root`；手机上是底部抽屉，≥1024px 自动变成居中对话框。
- **多端**：`src/api/server.js` 决定接口地址——网页版同源 `/api`，Android App 使用登录页里设置的服务器地址（默认 `https://app.xueyeguanjia.com`）。`android/` 为 Capacitor 工程，打包见根目录 README。
- **图标**：只用 `lucide:*`。`npm run dev / build` 前会自动运行 `scripts/build-icons.mjs` 裁剪出用到的图标打包进产物，写错图标名会直接报错。
