# 端到端测试

用本机 Edge 跑学业管家的核心流程，电脑（1440×900）和手机（390×844）各一遍。

```bash
cd e2e
npm install   # 只装 playwright-core（不下载浏览器）
npm test
```

脚本会自动：

1. 用系统临时目录里的新 SQLite 库启动后端（端口 8105），不访问外网（AI Key 置空、邮件走内存）
2. 启动前端开发服务器（端口 5205），`/api` 代理到上面的后端
3. 依次执行 `flows.mjs`：演示账号登录 → 新建任务 → 完成任务 → 开始并结束一次专注 → 日程切换日/周/月 → 打开 AI 页 → 切换主题 → 快捷键（仅电脑）→ 断网可看 → 退出登录
4. 结束后关掉启动的进程、删除临时库

失败的流程会截图到 `e2e/artifacts/`，有失败时退出码为 1。

可用环境变量：`E2E_API_PORT`、`E2E_WEB_PORT`、`EDGE_PATH`（msedge.exe 路径）、`PYTHON`（Python 可执行文件）。
需要先装好后端依赖（`pip install -r Backend+AI-interface/requirements.txt`）和前端依赖（`cd Frontend && npm install`）。
