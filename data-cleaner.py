"""
数据清洗工具函数
供其他模块调用的公共函数
"""

import re
from typing import List, Tuple, Optional


def clean_weekday(text) -> str:
    """
    统一星期格式
    输入："星期一" / "Monday" / "周一" → 输出："周一"
    """
    if not text:
        return "周一"

    text = str(text).strip()

    weekday_map = {
        '星期一': '周一', 'Monday': '周一', 'Mon': '周一',
        '星期二': '周二', 'Tuesday': '周二', 'Tue': '周二',
        '星期三': '周三', 'Wednesday': '周三', 'Wed': '周三',
        '星期四': '周四', 'Thursday': '周四', 'Thu': '周四',
        '星期五': '周五', 'Friday': '周五', 'Fri': '周五',
        '星期六': '周六', 'Saturday': '周六', 'Sat': '周六',
        '星期日': '周日', 'Sunday': '周日', 'Sun': '周日'
    }

    return weekday_map.get(text, text)


def parse_period(period_text) -> List[int]:
    """
    解析节次
    输入: "1-2节" → 输出: [1, 2]
    输入: "第3节" → 输出: [3]
    输入: "3" → 输出: [3]
    """
    if not period_text:
        return [1]

    text = str(period_text).strip()

    # 匹配 "数字-数字" 格式
    match_range = re.search(r'(\d+)\s*[-~]\s*(\d+)', text)
    if match_range:
        start = int(match_range.group(1))
        end = int(match_range.group(2))
        return list(range(start, end + 1))

    # 匹配单个数字
    match_single = re.search(r'(\d+)', text)
    if match_single:
        return [int(match_single.group(1))]

    return [1]


def clean_course_name(course_name) -> str:
    """
    清理课程名称
    输入: "高等数学A(上)" → 输出: "高等数学"
    """
    if not course_name:
        return ""

    text = str(course_name).strip()

    # 去掉英文括号内容
    text = re.sub(r'\([^)]*\)', '', text)
    # 去掉中文括号内容
    text = re.sub(r'（[^）]*）', '', text)
    # 去掉末尾的 A/B/C 等
    text = re.sub(r'[A-Z]+$', '', text)
    # 去掉末尾的数字
    text = re.sub(r'\d+$', '', text)

    return text.strip()


def clean_location(location) -> str:
    """
    清理地点信息
    输入: "教101室" → 输出: "教101"
    """
    if not location or location == "":
        return "待定"

    text = str(location).strip()

    # 去掉"室"字
    text = re.sub(r'室$', '', text)
    # 去掉多余空格
    text = re.sub(r'\s+', '', text)
    # 统一"教学楼"为"教"
    text = re.sub(r'教学楼', '教', text)

    return text


def deduplicate_courses(courses: List[dict]) -> List[dict]:
    """
    去除重复课程
    """
    seen = set()
    unique = []

    for course in courses:
        key = f"{course.get('weekday', '')}_{course.get('period', '')}_{course.get('course', '')}"
        if key not in seen:
            seen.add(key)
            unique.append(course)

    return unique


def detect_conflicts(courses: List[dict]) -> List[dict]:
    """
    检测时间冲突
    """
    conflicts = []

    for i, c1 in enumerate(courses):
        for j, c2 in enumerate(courses):
            if i >= j:
                continue

            if c1.get('weekday') != c2.get('weekday'):
                continue

            period1 = c1.get('period', '')
            period2 = c2.get('period', '')

            if period1 and period2 and period1 == period2:
                conflicts.append({
                    "course1": c1.get('course'),
                    "course2": c2.get('course'),
                    "weekday": c1.get('weekday'),
                    "period": period1
                })

    return conflicts