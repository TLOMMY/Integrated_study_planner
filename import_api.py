"""
导入模块 API 服务
提供三个接口：
1. POST /import/excel  → 解析 Excel 课表
2. POST /import/pdf    → 解析 PDF 教学大纲
3. GET  /import/result → 查询最近一次导入结果
"""

import os
import tempfile
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# 导入你之前写好的解析函数
from 璞玉项目.excel_parser import parse_my_schedule
from pdf_parser import extract_chapters_from_pdf

# 创建 FastAPI 应用
app = FastAPI(title="课表与大纲导入服务")

# 允许前端跨域访问（重要！）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 开发时允许所有来源，上线后可以限制
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 临时存储最近一次导入结果（仅用于演示，实际项目会存数据库）
last_import_result = {"type": None, "data": None}

# =================== 接口1：Excel 导入 ===================
@app.post("/import/excel")
async def import_excel(file: UploadFile = File(...)):
    """
    上传 Excel 课表文件（.xls 或 .xlsx）
    返回解析后的课程列表
    """
    # 1. 校验文件扩展名
    if not file.filename.endswith(('.xls', '.xlsx')):
        raise HTTPException(status_code=400, detail="文件格式错误，请上传 .xls 或 .xlsx 文件")

    # 2. 保存为临时文件
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xls") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        # 3. 调用你已有的解析函数
        result = parse_my_schedule(tmp_path)

        # 4. 记录到全局变量（供接口3查询）
        global last_import_result
        last_import_result = {
            "type": "excel",
            "data": result.get("data", []),
            "total": result.get("total", 0),
            "message": result.get("message", "")
        }

        # 5. 返回结果（直接返回字典，FastAPI 会自动转成 JSON）
        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"解析失败：{str(e)}")
    finally:
        # 6. 删除临时文件
        os.unlink(tmp_path)


# =================== 接口2：PDF 导入 ===================
@app.post("/import/pdf")
async def import_pdf(file: UploadFile = File(...)):
    """
    上传 PDF 教学大纲，提取章节列表
    """
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="文件格式错误，请上传 PDF 文件")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        result = extract_chapters_from_pdf(tmp_path)

        global last_import_result
        last_import_result = {
            "type": "pdf",
            "data": result.get("data", {}).get("chapters", []),
            "total": result.get("data", {}).get("total", 0),
            "message": result.get("message", "")
        }

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"解析失败：{str(e)}")
    finally:
        os.unlink(tmp_path)


# =================== 接口3：查询最近导入结果 ===================
@app.get("/import/result")
async def get_import_result():
    """返回最近一次导入的课程/任务列表，用于前端校验"""
    if last_import_result["type"] is None:
        return JSONResponse(status_code=404, content={"code": 404, "message": "暂无导入记录", "data": None})
    return {
        "code": 200,
        "message": "success",
        "data": last_import_result
    }


# =================== 根路径（测试用） ===================
@app.get("/")
async def root():
    return {"message": "导入服务已启动，请访问 /docs 查看接口文档"}