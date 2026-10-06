#!/usr/bin/env python3
"""
启动脚本
"""
import sys
import os

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(__file__))

if __name__ == "__main__":
    try:
        from app.main import app
        print("FastAPI应用创建成功")

        # 测试健康检查
        from fastapi.testclient import TestClient
        client = TestClient(app)
        response = client.get("/health")
        if response.status_code == 200 and response.json() == {"status": "ok"}:
            print("健康检查通过")
        else:
            print("健康检查失败")

        print("后端服务准备就绪！")
        print("运行以下命令启动服务：")
        print("uvicorn app.main:app --reload --host 0.0.0.0 --port 8000")

    except ImportError as e:
        print(f"❌ 导入失败: {e}")
        print("请确保已安装依赖: pip install -r requirements.txt")
    except Exception as e:
        print(f"❌ 启动失败: {e}")