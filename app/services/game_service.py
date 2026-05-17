from app.db import get_db_connection
from datetime import date, timedelta

class GameService:
    @staticmethod
    def add_study_record(user_id: int, record_date: str, minutes: int):
        with get_db_connection() as conn:
            # 插入或更新
            conn.execute("""
                INSERT INTO study_records (user_id, date, focus_minutes)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id, date) DO UPDATE SET focus_minutes = focus_minutes + ?
            """, (user_id, record_date, minutes, minutes))
            # 检查徽章（示例：首次专注、累计10小时）
            total = conn.execute(
                "SELECT SUM(focus_minutes) as total FROM study_records WHERE user_id=?",
                (user_id,)
            ).fetchone()["total"] or 0
            if total >= 600:  # 10小时
                conn.execute("INSERT OR IGNORE INTO badges (user_id, badge_name) VALUES (?, ?)",
                             (user_id, "专注达人"))
            return True

    @staticmethod
    def get_stats(user_id: int):
        with get_db_connection() as conn:
            total = conn.execute(
                "SELECT SUM(focus_minutes) as total FROM study_records WHERE user_id=?",
                (user_id,)
            ).fetchone()["total"] or 0
            today = date.today().isoformat()
            today_min = conn.execute(
                "SELECT focus_minutes FROM study_records WHERE user_id=? AND date=?",
                (user_id, today)
            ).fetchone()
            today_min = today_min["focus_minutes"] if today_min else 0
            # 连续天数（简单示例）
            streak = 0
            check_date = date.today()
            while True:
                rec = conn.execute(
                    "SELECT focus_minutes FROM study_records WHERE user_id=? AND date=?",
                    (user_id, check_date.isoformat())
                ).fetchone()
                if rec and rec["focus_minutes"] > 0:
                    streak += 1
                    check_date -= timedelta(days=1)
                else:
                    break
            # 热力图数据（最近30天）
            heatmap = {}
            start = date.today() - timedelta(days=30)
            rows = conn.execute("""
                SELECT date, focus_minutes FROM study_records
                WHERE user_id=? AND date >= ?
            """, (user_id, start.isoformat())).fetchall()
            for row in rows:
                heatmap[row["date"]] = row["focus_minutes"]
            return {
                "total_minutes": total,
                "today_minutes": today_min,
                "streak_days": streak,
                "heatmap_data": heatmap
            }

    @staticmethod
    def get_badges(user_id: int):
        with get_db_connection() as conn:
            rows = conn.execute(
                "SELECT badge_name, earned_at FROM badges WHERE user_id=?",
                (user_id,)
            ).fetchall()
            return [{"name": r["badge_name"], "earned_at": r["earned_at"]} for r in rows]