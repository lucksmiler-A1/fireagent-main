#!/usr/bin/env python3
"""
文件上传 API 测试脚本
"""
import sys
import os

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(__file__))

if __name__ == "__main__":
    try:
        from app.main import app
        from app.db.session import create_tables
        from fastapi.testclient import TestClient
        import io

        print("开始测试文件上传API...")

        # 确保数据库表存在
        create_tables()

        client = TestClient(app)

        # 创建一个测试图片文件（简单的PNG头部）
        test_image = io.BytesIO()
        # PNG文件头部
        test_image.write(b'\x89PNG\r\n\x1a\n')
        # 添加一些像素数据
        test_image.write(b'\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01')
        test_image.seek(0)

        # 测试文件上传
        files = {"file": ("test.png", test_image, "image/png")}
        data = {"scene": "campus"}

        response = client.post("/api/v1/analysis/upload", files=files, data=data)

        print(f"响应状态码: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print("上传分析成功!")
            print(f"记录ID: {result['record_id']}")
            print(f"风险等级: {result['overall_risk']}")
            print(f"摘要: {result['summary']}")
            print(f"隐患数量: {len(result['items'])}")
        else:
            print(f"上传失败: {response.text}")

    except ImportError as e:
        print(f"导入失败: {e}")
        print("请确保已安装依赖: pip install -r requirements.txt")
    except Exception as e:
        print(f"测试失败: {e}")