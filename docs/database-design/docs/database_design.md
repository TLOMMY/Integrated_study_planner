
---

# 数据库详细设计文档
## 1. 文档概述
### 1.1 项目背景
本系统为**学习管理类应用**提供底层数据支撑，覆盖用户管理、课程表、学习计划、任务管理、专注记录、成就系统、导入日志等核心能力，适用于移动端 App 或轻量 Web 服务，采用 **SQLite** 作为持久化存储。

### 1.2 设计目标
- 数据结构清晰、关系合理、可扩展；
- 保证数据一致性、完整性、安全性；
- 支持多端同步、时间线管理、统计分析；
- 易于维护、便于迁移、便于开源协作。

### 1.3 适用范围
本文档描述数据库所有表结构、字段含义、约束、索引、触发器及业务规则，为开发、测试、维护提供统一依据。

### 1.4 术语定义
- **级联删除（ON DELETE CASCADE）**：主记录删除时自动删除关联记录；
- **外键约束**：保证引用完整性；
- **专注记录**：用户学习时长统计；
- **连续打卡（Streak）**：用户每日活跃连续天数；
- **刷新令牌（Refresh Token）**：用于登录态续期。

---

## 2. 数据库总体设计
### 2.1 数据库类型
- 数据库：SQLite 3.x
- 字符集：UTF-8
- 外键：开启（PRAGMA foreign_keys = ON）

### 2.2 核心模块
1. 用户模块（users）
2. 课程表模块（timetables）
3. 学习计划模块（learning_plans）
4. 学习任务模块（study_tasks）
5. 成就系统（achievements + user_achievements）
6. 专注记录（focus_records）
7. 导入日志（import_logs）

### 2.3 实体关系简述
- **1:N**：用户 → 课表、计划、专注记录、导入日志
- **1:N**：学习计划 → 学习任务
- **N:M**：用户 ↔ 成就（通过中间表）
- **N:1**：专注记录 → 学习任务（可空）

---

## 3. 表结构详细设计
### 3.1 users（用户表）
**说明**：存储用户账号、资料、成长数据、登录态。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| user_id | INTEGER | PK、自增 | 用户唯一ID |
| username | VARCHAR(50) | UNIQUE、NOT NULL | 用户名 |
| email | VARCHAR(100) | UNIQUE | 邮箱 |
| password_hash | VARCHAR(255) | NOT NULL | 密码哈希（无明文） |
| display_name | VARCHAR(50) | | 昵称 |
| avatar_url | TEXT | | 头像地址 |
| level | INTEGER | DEFAULT 1 | 用户等级 |
| total_points | INTEGER | DEFAULT 0 | 累计积分 |
| current_streak | INTEGER | DEFAULT 0 | 当前连续打卡天数 |
| max_streak | INTEGER | DEFAULT 0 | 历史最大连续天数 |
| timezone | VARCHAR(50) | DEFAULT 'Asia/Shanghai' | 时区 |
| refresh_token | TEXT | | 登录刷新令牌 |
| last_login_at | TIMESTAMP | | 最近登录时间 |
| created_at | TIMESTAMP | DEFAULT NOW | 创建时间 |
| updated_at | TIMESTAMP | DEFAULT NOW、触发器更新 | 更新时间 |

**触发器**：更新时自动更新 updated_at。

---

### 3.2 timetables（课程表）
**说明**：存储用户个人课表，支持学期、颜色、周几、时间段。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| timetable_id | INTEGER | PK、自增 | 课表ID |
| user_id | INTEGER | FK、NOT NULL | 所属用户 |
| course_name | VARCHAR(100) | NOT NULL | 课程名 |
| teacher | VARCHAR(50) | | 教师 |
| classroom | VARCHAR(50) | | 教室 |
| day_of_week | INTEGER | 1~7、NOT NULL | 星期几（1=周一） |
| start_time | TIME | NOT NULL | 开始时间 |
| end_time | TIME | NOT NULL | 结束时间 |
| semester | VARCHAR(20) | | 学期（2026-spring） |
| color | VARCHAR(20) | | 前端显示颜色 |
| created_at | TIMESTAMP | DEFAULT NOW | 创建时间 |

**索引**：(user_id, semester)

---

### 3.3 learning_plans（学习计划表）
**说明**：按天制定学习计划，含目标时长、实际时长、AI建议。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| plan_id | INTEGER | PK、自增 | 计划ID |
| user_id | INTEGER | FK、NOT NULL | 所属用户 |
| plan_date | DATE | NOT NULL | 计划日期 |
| target_hours | DECIMAL(4,2) | ≥0 | 目标小时数 |
| actual_hours | DECIMAL(4,2) | ≥0、默认0 | 实际完成小时 |
| status | VARCHAR(20) | 默认 pending | 状态：pending/completed/failed |
| ai_suggestion | TEXT | | AI 学习建议 |
| created_at | TIMESTAMP | DEFAULT NOW | 创建时间 |

**索引**：(user_id, plan_date)

---

### 3.4 study_tasks（学习任务表）
**说明**：每日计划下的具体任务，支持时间拖拽、多状态。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| task_id | INTEGER | PK、自增 | 任务ID |
| plan_id | INTEGER | FK、NOT NULL | 所属计划 |
| task_name | VARCHAR(100) | NOT NULL | 任务名称 |
| start_time | DATETIME | NOT NULL | 开始时间 |
| end_time | DATETIME | NOT NULL | 结束时间 |
| completed | BOOLEAN | 默认 false | 是否完成 |
| task_status | VARCHAR(20) | 默认 todo | todo/doing/done |
| note | TEXT | | 备注 |
| created_at | TIMESTAMP | DEFAULT NOW | 创建时间 |

**索引**：(plan_id)

---

### 3.5 achievements（成就定义表）
**说明**：系统预设成就模板。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| achievement_id | INTEGER | PK、自增 | 成就ID |
| name | VARCHAR(50) | NOT NULL | 成就名称 |
| description | TEXT | | 描述 |
| points_required | INTEGER | NOT NULL | 解锁所需积分 |
| icon_url | TEXT | | 图标地址 |
| category | VARCHAR(20) | | 分类（streak/focus/plan） |

---

### 3.6 user_achievements（用户成就关联表）
**说明**：多对多关系，记录用户解锁成就。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| user_id | INTEGER | PK、FK | 用户ID |
| achievement_id | INTEGER | PK、FK | 成就ID |
| unlocked_at | TIMESTAMP | DEFAULT NOW | 解锁时间 |

**主键**：(user_id, achievement_id)

---

### 3.7 focus_records（专注记录表）
**说明**：记录用户学习专注时长，可关联任务、区分来源。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| record_id | INTEGER | PK、自增 | 记录ID |
| user_id | INTEGER | FK、NOT NULL | 用户ID |
| record_date | DATE | NOT NULL | 日期 |
| start_time | TIME | NOT NULL | 开始时间 |
| end_time | TIME | NOT NULL | 结束时间 |
| duration | INTEGER | >0、NOT NULL | 时长（分钟） |
| task_id | INTEGER | FK、可空 | 关联任务ID |
| source | VARCHAR(20) | 默认 manual | manual/ai/timer |
| created_at | TIMESTAMP | DEFAULT NOW | 创建时间 |

**索引**：(user_id, record_date)

---

### 3.8 import_logs（导入日志表）
**说明**：记录课表导入历史。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| import_id | INTEGER | PK、自增 | 导入ID |
| user_id | INTEGER | FK、NOT NULL | 用户ID |
| import_type | VARCHAR(20) | | excel/pdf/ocr |
| file_name | TEXT | | 文件名 |
| success_count | INTEGER | 默认0 | 成功条数 |
| fail_count | INTEGER | 默认0 | 失败条数 |
| imported_at | TIMESTAMP | DEFAULT NOW | 导入时间 |

---

## 4. 约束与业务规则
### 4.1 完整性约束
- 外键全部开启级联删除，避免孤儿数据；
- day_of_week 限制 1–7；
- duration > 0；
- target_hours、actual_hours ≥ 0；
- 密码只存哈希，无明文。

### 4.2 业务规则
- 用户删除 → 级联删除课表、计划、专注记录、导入日志；
- 计划删除 → 级联删除任务；
- 专注记录可无任务（独立计时）；
- 连续打卡每日更新，断卡清零；
- 成就自动根据积分/条件解锁。

---

## 5. 索引设计
```sql
-- 用户课表
CREATE INDEX idx_timetables_user_semester ON timetables(user_id, semester);

-- 学习计划
CREATE INDEX idx_learning_plans_user_date ON learning_plans(user_id, plan_date);

-- 任务
CREATE INDEX idx_study_tasks_plan ON study_tasks(plan_id);

-- 专注记录
CREATE INDEX idx_focus_records_user_date ON focus_records(user_id, record_date);
```

---

## 6. 触发器设计
```sql
-- users 更新时自动更新 updated_at
CREATE TRIGGER update_users_updated_at
AFTER UPDATE ON users
BEGIN
    UPDATE users SET updated_at = CURRENT_TIMESTAMP WHERE user_id = NEW.user_id;
END;
```

---

## 7. 数据库初始化脚本
见 `/sql/create_tables.sql` 与 `/sql/optimize.sql`。

---

## 8. 扩展设计说明
- 可扩展：好友、群组、分享、评论、通知表；
- 可增加：软删除字段 `is_deleted`；
- 可迁移：结构兼容 MySQL/PostgreSQL（仅语法微调）。

---

## 9. 版本记录
- V1.0：初始设计，8 张基础表；
- V1.1：增加 CHECK 约束、索引、触发器；
- V1.2：完善字段注释、文档结构标准化。

---