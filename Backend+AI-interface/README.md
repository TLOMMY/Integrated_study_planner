# 学业管家 · 后端

FastAPI + SQLAlchemy 2 + SQLite。整体说明见仓库根目录 [README.md](../README.md)；启动后完整接口文档在 http://127.0.0.1:8000/docs 。

```bash
pip install -r requirements.txt
python -m uvicorn main:app --reload
python -m pytest                          # 91 个用例，使用临时库，不会访问外网
python -m app.services.seed --reset       # 重置演示账号数据
```

## 配置（`.env`，均可选）

| 变量 | 默认 | 说明 |
|------|------|------|
| `DATABASE_URL` | `sqlite:///./study_planner.db` | 相对路径固定解析到本目录 |
| `JWT_SECRET_KEY` | 开发用默认值 | **部署时必须修改** |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | 前端会在到期前自动续期 |
| `DEEPSEEK_API_KEY` | 空 | 服务器默认模型（"自动"模式使用）；用户也可在 AI 设置里接入自己的模型 |
| `AI_TIMEOUT` | `45` | 调用模型的超时秒数 |
| `ADMIN_EMAILS` | 空 | 逗号分隔；这些账号可通过 `GET /feedback` 在线查看用户反馈 |
| `FEEDBACK_DIR` | `./feedback` | 用户反馈 txt 的保存目录（已加入 .gitignore） |
| `LOGIN_MAX_FAILS` / `LOGIN_LOCK_MINUTES` | `5` / `10` | 同一账号连续输错密码的次数与锁定分钟数 |
| `AI_ALLOW_PRIVATE_URLS` | `1` | 是否允许接口地址指向本机/内网（Ollama 需要）；**公网部署建议设为 `0`** |
| `CORS_ORIGINS` | `localhost:5173` 等 | 逗号分隔 |
| `SEED_DEMO` | `1` | 启动时创建演示账号与排行榜演示同学 |

## 接口一览

| 模块 | 接口 |
|------|------|
| 认证 | `POST /auth/register` `/auth/login` `/auth/refresh` `/auth/demo` |
| 用户 | `GET/PUT /users/me` · `PUT /users/me/password`（改密后其他设备失效）· `PUT /users/me/email` · `PUT /users/me/phone` · `POST /users/me/logout-all` · `GET/PUT /users/me/study-prefs`（学习时段偏好）· `GET /users/me/export` · `DELETE /users/me` |
| 反馈 | `POST /feedback`（保存为 `feedback/*.txt`）· `GET /feedback` · `GET /feedback/{id}`（管理员） |
| 首页 | `GET /home/summary` |
| 任务 | `GET /task/list?view=today\|upcoming\|overdue\|completed\|range` · `GET /task/detail/{id}` · `POST /task/create` · `PUT /task/update/{id}` · `PUT /task/complete/{id}` · `PUT /task/uncomplete/{id}` · `DELETE /task/delete/{id}` · `POST /task/batch`（批量删除 / 改日期）· `GET /task/list?view=all&q=`（搜索） |
| 课表 | `GET /timetable?week=` · `POST /timetable` · `PUT/DELETE /timetable/{id}` · `PUT /timetable/settings` · `POST /import/timetable?mode=preview\|commit`（Excel）· `POST /import/timetable/web`（教务网页 HTML/MHTML/正方 JSON）· `POST /import/timetable/ai`（图片 / PDF 交给大模型识别）· `POST /import/timetable/commit` |
| 日程 | `GET /day/timeline?date=` |
| 专注与统计 | `POST /study/record` · `GET /study/stats` · `GET /study/leaderboard` |
| 学习计划 | `GET/POST /study-plans`（`status=trash` 查看回收站）· `GET/PUT/DELETE /study-plans/{id}`（删除即移入回收站，30 天后自动清除）· `POST /study-plans/trash/restore` · `POST /study-plans/trash/purge` · `DELETE /study-plans/trash` |
| AI | `GET /ai/health` · `POST /ai/plan`（草稿：`advice` 建议 + `tasks`/`courses` 结构化计划，不写库）· `POST /ai/plan/commit`（可选导入任务/课程） |
| AI 模型设置 | `GET/PUT /ai/settings` · `POST /ai/providers` · `PUT/DELETE /ai/providers/{id}` · `POST /ai/providers/test` · `POST /ai/providers/models`（OpenAI Chat Completions 兼容协议，Key 加密存储、只返回掩码） |

任务路径沿用小组"接口整合锁死版"（`/task/list`、`/task/create` 等），仅新增了 `/task/uncomplete/{id}`。课程时间冲突返回 `409`，`data.conflicts` 列出冲突课程，带 `force: true` 可强制保存。
