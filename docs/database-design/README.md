# Study-App-Database
学习管理类 App 数据库设计（SQLite），包含用户体系、课表、学习计划、任务管理、专注记录、成就系统。

## 功能模块
- 用户注册/登录/成长体系（等级、积分、连续打卡）
- 个人课程表管理
- 每日学习计划 + 可拖拽时间任务
- 专注时长记录（番茄钟）
- 成就勋章系统
- 课表导入日志

## 数据库表结构
1. **users** - 用户信息表
2. **timetables** - 课程表
3. **learning_plans** - 学习计划表
4. **study_tasks** - 学习任务表
5. **achievements** - 成就定义表
6. **user_achievements** - 用户成就关联表
7. **focus_records** - 专注记录
8. **import_logs** - 导入日志

## 技术栈
- 数据库：SQLite
- 适用：移动端 App / 小型 Web 应用

## 使用方法
1. 执行 `sql/create_tables.sql` 完成建表
2. （可选）执行 `sql/optimize.sql` 启用优化、索引、触发器

## 优化亮点
- 外键约束 + 级联删除，保证数据一致性
- 密码哈希存储，无明文密码
- 自动更新时间触发器
- 高频查询字段索引优化
- 完整字段约束校验