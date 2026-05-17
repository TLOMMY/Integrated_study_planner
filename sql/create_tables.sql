-- 学习管理App 数据库建表脚本
-- SQLite 版本

PRAGMA foreign_keys = ON;

-- 用户表
CREATE TABLE users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    display_name TEXT,
    avatar_url TEXT,
    level INTEGER DEFAULT 1,
    total_points INTEGER DEFAULT 0,
    current_streak INTEGER DEFAULT 0,
    max_streak INTEGER DEFAULT 0,
    timezone TEXT DEFAULT 'Asia/Shanghai',
    refresh_token TEXT,
    last_login_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 课程表
CREATE TABLE timetables (
    timetable_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    course_name TEXT NOT NULL,
    teacher TEXT,
    classroom TEXT,
    day_of_week INTEGER NOT NULL CHECK (day_of_week BETWEEN 1 AND 7),
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    semester TEXT,
    color TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- 学习计划
CREATE TABLE learning_plans (
    plan_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    plan_date DATE NOT NULL,
    target_hours DECIMAL(4,2) DEFAULT 0 CHECK (target_hours >= 0),
    actual_hours DECIMAL(4,2) DEFAULT 0 CHECK (actual_hours >= 0),
    status TEXT DEFAULT 'pending',
    ai_suggestion TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- 学习任务
CREATE TABLE study_tasks (
    task_id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id INTEGER NOT NULL,
    task_name TEXT NOT NULL,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    completed BOOLEAN DEFAULT FALSE,
    task_status TEXT DEFAULT 'todo',
    note TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (plan_id) REFERENCES learning_plans(plan_id) ON DELETE CASCADE
);

-- 成就定义
CREATE TABLE achievements (
    achievement_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    points_required INTEGER DEFAULT 0,
    icon_url TEXT,
    category TEXT
);

-- 用户成就关联
CREATE TABLE user_achievements (
    user_id INTEGER NOT NULL,
    achievement_id INTEGER NOT NULL,
    unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, achievement_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (achievement_id) REFERENCES achievements(achievement_id) ON DELETE CASCADE
);

-- 专注记录
CREATE TABLE focus_records (
    record_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    record_date DATE NOT NULL,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    duration INTEGER NOT NULL CHECK (duration > 0),
    task_id INTEGER,
    source TEXT DEFAULT 'manual',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (task_id) REFERENCES study_tasks(task_id) ON DELETE SET NULL
);

-- 导入日志
CREATE TABLE import_logs (
    import_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    import_type TEXT,
    file_name TEXT,
    success_count INTEGER DEFAULT 0,
    fail_count INTEGER DEFAULT 0,
    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);