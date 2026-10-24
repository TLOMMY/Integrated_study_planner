# run.py
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "import_api:app",   # 这里写你的文件名:FastAPI实例名
        host="127.0.0.1",
        port=8000,
        reload=True         # 代码改动后自动重启
    )