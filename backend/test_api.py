#!/usr/bin/env python3
"""
API 测试脚本
"""
import sys
import os

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(__file__))

if __name__ == "__main__":
    try:
        from app.main import app
        from app.db.session import create_tables
        print("FastAPI应用创建成功")

        # 确保数据库表存在
        create_tables()
        print("数据库表创建完成")

        # 测试健康检查
        from fastapi.testclient import TestClient
        client = TestClient(app)

        # 健康检查
        response = client.get("/health")
        if response.status_code == 200 and response.json() == {"status": "ok"}:
            print("健康检查通过")
        else:
            print("健康检查失败")

        # 测试API v1路由
        response = client.get("/api/v1/records?page=1&page_size=1")
        if response.status_code == 200:
            print("记录API测试通过")
        else:
            print(f"记录API测试失败: {response.status_code}")

        print("API测试完成")

    except ImportError as e:
        print(f"导入失败: {e}")
        print("请确保已安装依赖: pip install -r requirements.txt")
    except Exception as e:
        print(f"测试失败: {e}")