# Integrated Study Planner - AI 学习规划模块
> 一个可插拔、轻量化的 AI 学习计划生成引擎，提供智能排课与个性化学习规划能力，可快速接入任何后端项目。

---

## ✨ 项目简介
本模块是「Integrated Study Planner」项目的**AI 核心端口部分**，专注于：
- 根据用户目标、时间、偏好，自动生成合理的学习计划
- 内置学习规则引擎，保证计划健康、可执行（防熬夜、防过载、劳逸结合）
- 记忆用户历史偏好，实现个性化优化
- 提供标准 API 接口，可轻松接入任何后端系统

---

## 📁 精简项目结构（核心文件）
```
integrated_study_planner/
├── app/
│   ├── ai/                 # AI 学习规划核心
│   │   ├── __init__.py
│   │   ├── planner.py      # 计划生成主逻辑
│   │   ├── memory.py       # 用户偏好记忆模块
│   │   └── rules.py        # 学习规则约束引擎
│   ├── api/                # 对外接口
│   │   ├── __init__.py
│   │   └── routes/
│   │       ├── __init__.py
│   │       └── ai.py       # AI 接口入口
│   ├── core/               # 基础配置
│   │   ├── __init__.py
│   │   ├── config.py       # 配置管理
│   │   └── database.py     # 数据库连接
│   └── schemas/            # 数据模型
│       ├── __init__.py
│       └── study_plan.py   # 学习计划数据格式
├── main.py                 # 服务启动入口
├── requirements.txt        # 依赖清单
├── .env                    # 环境变量配置
└── study_planner.db        # SQLite 数据存储
```

---

## 🚀 快速开始

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 配置环境变量
在 `.env` 文件中配置你的基础参数：
```env
# 示例配置
DATABASE_URL=sqlite:///./study_planner.db
```

### 3. 启动服务
```bash
uvicorn main:app --reload
```
启动成功后，可通过 `http://127.0.0.1:8000/docs` 查看自动生成的接口文档。

---

## 📌 核心接口说明

| 接口路径 | 方法 | 说明 |
|---------|------|------|
| `/api/ai/generate-plan` | POST | 根据用户请求生成智能学习计划 |

请求示例：
```json
{
  "subjects": ["数学", "英语"],
  "available_time": {"weekday": 2, "weekend": 6},
  "preferences": {"study_time": "morning", "avoid_night": true}
}
```

---

## 🧠 模块说明

### `app/ai/planner.py`
- 核心逻辑：接收用户参数，调用规则引擎和记忆模块，生成最终学习计划
- 支持科目分配、时间分配、优先级排序

### `app/ai/rules.py`
- 内置健康学习规则：
  - 禁止深夜学习（可配置时间段）
  - 单日学习时长上限
  - 科目均衡分配，避免偏科
  - 劳逸结合，强制休息间隔

### `app/ai/memory.py`
- 记录用户历史学习偏好与执行情况
- 支持后续优化计划生成策略，实现个性化推荐

---

## 🔌 接入方式
本模块设计为**可插拔组件**，支持：
1.  独立运行，作为微服务对外提供 API
2.  直接嵌入 FastAPI 后端项目，复用现有数据库与用户系统
3.  与前端框架（如 Vue/React）通过 HTTP 请求对接

---

## 📄 License
MIT License
