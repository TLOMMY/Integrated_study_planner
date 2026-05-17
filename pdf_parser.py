"""
PDF 教学大纲解析模块
功能：从PDF中提取章节标题
"""

import fitz  # PyMuPDF库，用于读取PDF
import re  # 正则表达式库，用于匹配文字模式
import json
from typing import Dict, List


def extract_chapters_from_pdf(file_path: str) -> Dict:
    """
    从PDF中提取章节标题

    参数:
        file_path: PDF文件路径

    返回:
        {"code": 200, "data": {"chapters": [...], "total": n}, "message": "..."}
    """
    try:
        # 第1步：打开PDF文件
        doc = fitz.open(file_path)

        # 第2步：提取所有页的文本
        full_text = ""
        for page_num in range(len(doc)):
            page = doc[page_num]
            full_text += page.get_text()

        # 第3步：关闭文件
        doc.close()

        # 第4步：用正则表达式找章节标题
        chapters = []

        # 多种匹配模式（按优先级排序）
        patterns = [
            # 匹配中文数字：第1章、第2章、第10章
            r'第[0-9一二三四五六七八九十百千万]+章\s*[：]?\s*(.*?)(?=\n|$)',

            # 匹配：第一章、第二章
            r'[第]?[一二三四五六七八九十百千万]+章\s*[：]?\s*(.*?)(?=\n|$)',

            # 匹配：Chapter 1、Chapter 2
            r'[Cc]hapter\s+[0-9]+\s*[：]?\s*(.*?)(?=\n|$)',

            # 匹配：1. 标题、2. 标题
            r'^[0-9]+\.\s+(.*?)(?=\n|$)',

            # 匹配：1.1 标题、2.1 标题
            r'^[0-9]+\.[0-9]+\s+(.*?)(?=\n|$)',
        ]

        # 按行分割，逐行匹配（更准确）
        lines = full_text.split('\n')

        for line in lines:
            line = line.strip()
            if not line:
                continue

            for pattern in patterns:
                match = re.match(pattern, line)
                if match:
                    # 提取标题内容
                    title = match.group(1) if match.lastindex else match.group(0)
                    title = title.strip()

                    # 过滤太短或太长的
                    if 2 <= len(title) <= 50:
                        if title not in chapters:
                            chapters.append(title)
                    break  # 匹配到一个模式就跳出

        # 第5步：如果没有找到任何章节，尝试提取目录
        if not chapters:
            chapters = extract_toc_from_text(full_text)

        # 第6步：如果还是没找到，返回前10行作为预览
        if not chapters:
            lines = [line.strip() for line in full_text.split('\n') if line.strip()]
            chapters = lines[:10]

        return {
            "code": 200,
            "data": {
                "chapters": chapters,
                "total": len(chapters),
                "preview": full_text[:500]
            },
            "message": f"成功提取 {len(chapters)} 个章节"
        }

    except Exception as e:
        return {
            "code": 500,
            "data": {"chapters": [], "total": 0},
            "message": f"解析失败：{str(e)}"
        }


def extract_toc_from_text(text: str) -> List[str]:
    """
    从文本中提取目录（针对教材类PDF）
    """
    chapters = []

    # 常见的目录模式
    patterns = [
        # 匹配 "第1章 C++基础 1" 格式
        r'第[0-9]+章\s+([^\d]+?)\s+\d+',
        # 匹配 "1 C++基础" 格式
        r'^\d+\s+([^\d]+?)$',
        # 匹配 "1.1 变量" 格式
        r'^\d+\.\d+\s+([^\d]+?)$',
    ]

    lines = text.split('\n')
    for line in lines[:200]:  # 只看前200行
        line = line.strip()
        for pattern in patterns:
            match = re.search(pattern, line)
            if match:
                title = match.group(1).strip()
                if title and len(title) < 50 and title not in chapters:
                    chapters.append(title)
                break

    return chapters


def extract_all_content(file_path: str) -> Dict:
    """
    提取PDF中的所有内容（不限于章节）
    用于处理没有明确章节结构的PDF
    """
    try:
        doc = fitz.open(file_path)
        full_text = ""
        for page_num in range(len(doc)):
            page = doc[page_num]
            full_text += page.get_text()
        doc.close()

        # 按行分割，过滤空行
        lines = [line.strip() for line in full_text.split('\n') if line.strip()]

        return {
            "code": 200,
            "data": {
                "total_lines": len(lines),
                "preview": lines[:50],  # 前50行
                "full_text": full_text[:2000]  # 前2000字
            },
            "message": f"成功提取 {len(lines)} 行内容"
        }
    except Exception as e:
        return {
            "code": 500,
            "data": {},
            "message": f"提取失败：{str(e)}"
        }


# 测试代码
if __name__ == "__main__":
    # 测试章节提取
    result = extract_chapters_from_pdf("C++大学教程(第九版)中文目录_可搜索.pdf")
    print("=== 章节提取结果 ===")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    # 如果章节提取不理想，使用全部内容提取
    if result['data']['total'] == 0:
        print("\n=== 尝试提取全部内容 ===")
        content_result = extract_all_content("C++大学教程(第九版)中文目录_可搜索.pdf")
        print(json.dumps(content_result, ensure_ascii=False, indent=2))