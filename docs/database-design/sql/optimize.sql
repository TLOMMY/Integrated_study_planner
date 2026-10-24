-- 数据库优化脚本：索引 + 触发器 + 自动更新时间

-- 1. 自动更新 users 表的 updated_at
CREATE TRIGGER update_users_updated_at
AFTER UPDATE ON users
BEGIN
    UPDATE users SET updated_at = CURRENT_TIMESTAMP WHERE user_id = NEW.user_id;
END;

-- 2. 高频查询索引
CREATE INDEX idx_timetables_user_semester ON timetables(user_id, semester);
CREATE INDEX idx_learning_plans_user_date ON learning_plans(user_id, plan_date);
CREATE INDEX idx_study_tasks_plan ON study_tasks(plan_id);
CREATE INDEX idx_focus_records_user_date ON focus_records(user_id, record_date);