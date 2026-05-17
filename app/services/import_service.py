import os
import re
import fitz  # PyMuPDF
import pandas as pd
from paddleocr import PaddleOCR
from app.db import get_db_connection

# 初始化OCR（首次运行会下载模型）
ocr = PaddleOCR(use_angle_cls=True, lang='ch', show_log=False)

class ImportService:
    @staticmethod
    def ocr_timetable(image_bytes):
        """
        输入：图片二进制数据
        输出：课程列表 [{"course_name": "高数", "weekday": 1, "start_time": "08:00", "end_time": "09:40", "location": "教1-101"}]
        """
        # 保存临时文件或直接使用内存（PaddleOCR 支持文件路径或 numpy array）
        import tempfile
        import cv2
        import numpy as np

        # 将 bytes 转为 numpy array
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        # 调用 OCR
        result = ocr.ocr(img, cls=True)

        # 提取所有识别出的文字及其位置（按行排序）
        text_blocks = []
        for line in result[0]:
            text = line[1][0]
            # 获取文本框的中心 y 坐标（用于行分组）
            box = line[0]
            center_y = (box[0][1] + box[2][1]) / 2
            text_blocks.append((center_y, text))

        # 按 y 坐标排序，得到从上到下的文本行
        text_blocks.sort(key=lambda x: x[0])
        full_text = "\n".join([block[1] for block in text_blocks])

        # 解析课程信息（示例规则，需根据实际课表格式调整）
        courses = []
        # 常见课表格式：周一 8:00-9:40 高数 教1-101
        pattern = r"([周一至周日]+)\s*(\d{1,2}:\d{2})\s*[-~]\s*(\d{1,2}:\d{2})\s*(.+?)\s*(\S*)"
        matches = re.findall(pattern, full_text)

        weekday_map = {"周一": 0, "周二": 1, "周三": 2, "周四": 3, "周五": 4, "周六": 5, "周日": 6}
        for match in matches:
            weekday_cn, start_time, end_time, course_name, location = match
            weekday = weekday_map.get(weekday_cn, 0)
            courses.append({
                "course_name": course_name.strip(),
                "weekday": weekday,
                "start_time": start_time,
                "end_time": end_time,
                "location": location
            })

        # 如果没有匹配到，返回空列表或尝试更宽松的解析
        return courses

    @staticmethod
    def parse_pdf(file_bytes):
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        text = ""
        for page in doc:
            text += page.get_text()
        # 简单按章节拆分任务
        tasks = [{"title": line.strip(), "duration": 60} for line in text.split("\n") if "第" in line and "章" in line]
        return tasks

    @staticmethod
    def import_excel(file_bytes):
        df = pd.read_excel(file_bytes)
        # 假设列名：课程名,星期,开始时间,结束时间,地点
        courses = df.to_dict(orient="records")
        return courses

    @staticmethod
    def save_courses(user_id: int, courses: list):
        with get_db_connection() as conn:
            for c in courses:
                conn.execute("""
                    INSERT INTO courses (user_id, course_name, weekday, start_time, end_time, location)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (user_id, c["course_name"], c["weekday"], c["start_time"], c["end_time"], c.get("location", "")))