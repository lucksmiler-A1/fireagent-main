#!/usr/bin/env python3
"""
简化的测试服务器 - 跳过数据库初始化
"""
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os

app = FastAPI(title="Fire Hazard Detection API")

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "ok"}

@app.post("/api/v1/analysis/upload")
async def upload_image(
    file: UploadFile = File(...),
    scene: str = Form("campus")
):
    """上传图片并分析"""
    try:
        # 保存文件
        upload_dir = "uploads"
        os.makedirs(upload_dir, exist_ok=True)

        file_path = f"{upload_dir}/{file.filename}"
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)

        # 模拟分析结果
        result = {
            "record_id": f"test_{file.filename}",
            "image_url": f"/static/{file.filename}",
            "annotated_url": None,
            "overall_risk": "低",
            "summary": "测试分析完成 - 模拟结果",
            "items": [
                {
                    "type": "测试隐患",
                    "risk": "低",
                    "desc": "这是一个测试结果",
                    "suggest": "无需处理"
                }
            ]
        }

        return result

    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    print("Starting test server...")
    uvicorn.run(app, host="0.0.0.0", port=8000)