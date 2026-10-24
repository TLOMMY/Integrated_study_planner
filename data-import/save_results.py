"""
保存导入模块的返回结果到 JSON 文件（用于长期保存）
"""

import requests
import json
from datetime import datetime

# 服务地址（如果改了端口或 IP，在这里修改）
BASE_URL = "http://127.0.0.1:8000"


def save_excel_result():
    """保存 Excel 课表解析结果"""
    file_path = "25卓越人才4班课表.xls"

    with open(file_path, "rb") as f:
        files = {"file": f}
        response = requests.post(f"{BASE_URL}/import/excel", files=files)

    if response.status_code == 200:
        data = response.json()
        filename = f"excel_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, "w", encoding="utf-8") as out:
            json.dump(data, out, ensure_ascii=False, indent=2)
        print(f"✅ Excel 结果已保存到: {filename}")
        print(f"   共 {data.get('total', 0)} 门课程")
    else:
        print(f"❌ Excel 请求失败: {response.status_code}")


def save_pdf_result():
    """保存 PDF 大纲解析结果"""
    file_path = "C++大学教程(第九版)中文目录_可搜索.pdf"

    with open(file_path, "rb") as f:
        files = {"file": f}
        response = requests.post(f"{BASE_URL}/import/pdf", files=files)

    if response.status_code == 200:
        data = response.json()
        filename = f"pdf_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, "w", encoding="utf-8") as out:
            json.dump(data, out, ensure_ascii=False, indent=2)
        print(f"✅ PDF 结果已保存到: {filename}")
        chapters = data.get("data", {}).get("chapters", [])
        print(f"   共 {len(chapters)} 个章节")
    else:
        print(f"❌ PDF 请求失败: {response.status_code}")


def save_query_result():
    """保存最近查询结果"""
    response = requests.get(f"{BASE_URL}/import/result")

    if response.status_code == 200:
        data = response.json()
        filename = f"query_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, "w", encoding="utf-8") as out:
            json.dump(data, out, ensure_ascii=False, indent=2)
        print(f"✅ 查询结果已保存到: {filename}")
    else:
        print(f"❌ 查询请求失败: {response.status_code}")


if __name__ == "__main__":
    print("=" * 50)
    print("开始保存导入模块的返回结果...")
    print("=" * 50)

    save_excel_result()
    print()
    save_pdf_result()
    print()
    save_query_result()

    print("=" * 50)
    print("全部保存完成！")