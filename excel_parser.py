"""
最终版课表解析器 - 完全适配你的课表格式
"""

import pandas as pd
import re
import json


def parse_my_schedule(file_path: str) -> dict:
    """
    解析你的课表
    """
    try:
        # 读取Excel，不跳过任何行，让我们完全控制
        df = pd.read_excel(file_path, header=None)

        # 根据你的调试输出，第2行（索引1）是列名行
        # 第2行内容：['时间段', '节次', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六']
        header_row = 1  # 第2行（0开始）

        # 获取列名
        columns = []
        for col in range(len(df.columns)):
            val = df.iloc[header_row, col]
            if pd.notna(val):
                columns.append(str(val).strip())
            else:
                columns.append(f"col_{col}")

        # 找到星期几的列
        weekday_cols = []
        for i, col in enumerate(columns):
            if '星期一' in col or '星期二' in col or '星期三' in col or \
                    '星期四' in col or '星期五' in col or '星期六' in col or '星期日' in col:
                weekday_cols.append(i)

        # 找到节次列（通常是第2列，索引1）
        period_col = 1

        # 数据从第3行开始（索引2）
        all_courses = []

        # 遍历数据行
        for row_idx in range(header_row + 1, len(df)):
            # 获取节次
            period_val = df.iloc[row_idx, period_col]
            if pd.isna(period_val):
                continue

            period = str(period_val).strip()
            if period == '' or period == 'nan':
                continue

            # 遍历每一天
            for col_idx in weekday_cols:
                cell = df.iloc[row_idx, col_idx]
                if pd.isna(cell):
                    continue

                cell_content = str(cell).strip()
                if cell_content == '' or cell_content == 'nan':
                    continue

                # 获取星期名
                weekday = columns[col_idx]

                # 解析单元格中的课程
                courses = extract_courses_from_cell(cell_content, weekday, period)
                all_courses.extend(courses)

        return {
            "code": 200,
            "data": all_courses,
            "message": f"成功解析 {len(all_courses)} 门课程",
            "total": len(all_courses)
        }

    except Exception as e:
        return {
            "code": 500,
            "data": [],
            "message": f"解析失败：{str(e)}",
            "total": 0
        }


def extract_courses_from_cell(cell_content: str, weekday: str, period: str) -> list:
    """
    从单元格中提取课程信息
    """
    courses = []

    # 按换行分割
    lines = cell_content.split('\n')

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # 提取课程名（◇之前的内容）
        if '◇' in line:
            course_name = line.split('◇')[0].strip()
        else:
            course_name = line

        if not course_name or len(course_name) > 50:  # 过滤太长的
            continue

        # 提取地点
        location = extract_location(line)

        # 提取教师
        teacher = extract_teacher(line)

        # 提取周次
        weeks = extract_weeks(line)

        course = {
            "weekday": weekday,
            "period": period,
            "course": course_name,
            "location": location,
            "teacher": teacher,
            "weeks": weeks
        }
        courses.append(course)

    return courses


def extract_location(text: str) -> str:
    """提取地点"""
    # 匹配 A1409, A1308, 教101, 机房1 等格式
    patterns = [
        r'[A-Z]\d{3,4}',  # A1409
        r'教\d{3}',  # 教101
        r'机房\d+',  # 机房1
        r'[A-Z]\d+[A-Z]?\d*',  # 其他
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group()
    return "待定"


def extract_teacher(text: str) -> str:
    """提取教师名"""
    # 匹配中文姓名（2-4个字）
    match = re.search(r'[◇]([\u4e00-\u9fa5]{2,4})[◇]', text)
    if match:
        return match.group(1)

    # 匹配 ◇姓名◇ 格式
    match = re.search(r'◇([\u4e00-\u9fa5]{2,4})◇', text)
    if match:
        return match.group(1)

    return ""


def extract_weeks(text: str) -> str:
    """提取周次信息"""
    # 匹配类似 "2-16周" 的内容
    match = re.search(r'(\d+[-]?\d*周)', text)
    if match:
        return match.group(1)
    return ""


# 测试
if __name__ == "__main__":
    # 改成你的文件路径（文件在 docs 文件夹里）
    result = parse_my_schedule("25卓越人才4班课表.xls")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    # 打印解析结果
    if result['code'] == 200:
        print(f"\n=== 共解析出 {result['total']} 门课程 ===")
        for i, c in enumerate(result['data'][:15]):
            print(f"{i + 1}. {c['weekday']} 第{c['period']}节: {c['course']} @ {c['location']}")