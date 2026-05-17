from fastapi.responses import JSONResponse
from fastapi import status

def success_response(data=None, message="success", code=200):
    return JSONResponse(
        status_code=code,
        content={"code": code, "message": message, "data": data}
    )

def error_response(message, code=400):
    return JSONResponse(
        status_code=code,
        content={"code": code, "message": message, "data": None}
    )