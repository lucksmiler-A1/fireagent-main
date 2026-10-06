#!/usr/bin/env python3
"""
记录相关 API 测试脚本
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

        print("开始测试记录相关API...")

        # 确保数据库表存在
        create_tables()

        client = TestClient(app)

        # 1. 先上传一个测试记录
        print("1. 上传测试记录...")
        test_image = io.BytesIO()
        test_image.write(b'\x89PNG\r\n\x1a\n')
        test_image.write(b'\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01')
        test_image.seek(0)

        files = {"file": ("test.png", test_image, "image/png")}
        data = {"scene": "campus"}

        upload_response = client.post("/api/v1/analysis/upload", files=files, data=data)
        if upload_response.status_code == 200:
            upload_result = upload_response.json()
            record_id = upload_result["record_id"]
            print(f"   上传成功，记录ID: {record_id}")
        else:
            print(f"   上传失败: {upload_response.status_code}")
            sys.exit(1)

        # 2. 测试获取记录列表
        print("2. 测试获取记录列表...")
        list_response = client.get("/api/v1/records?limit=20&offset=0")
        print(f"   响应状态码: {list_response.status_code}")

        if list_response.status_code == 200:
            list_result = list_response.json()
            print(f"   总记录数: {list_result['total']}")
            print(f"   返回记录数: {len(list_result['records'])}")

            if list_result['records']:
                record = list_result['records'][0]
                print(f"   示例记录: {record['record_id'][:10]}...")
                print(f"   风险等级: {record['overall_risk']}")
                print(f"   缩略图URL: {record['thumbnail_url']}")
        else:
            print(f"   获取列表失败: {list_response.text}")

        # 3. 测试获取单个记录详情
        print("3. 测试获取单个记录详情...")
        detail_response = client.get(f"/api/v1/records/{record_id}")
        print(f"   响应状态码: {detail_response.status_code}")

        if detail_response.status_code == 200:
            detail_result = detail_response.json()
            print(f"   记录ID: {detail_result['record_id']}")
            print(f"   创建时间: {detail_result['created_at']}")
            print(f"   场景: {detail_result['scene']}")
            print(f"   风险等级: {detail_result['overall_risk']}")
            print(f"   隐患数量: {len(detail_result['items'])}")
        else:
            print(f"   获取详情失败: {detail_response.text}")

        # 4. 测试不存在的记录
        print("4. 测试不存在的记录...")
        not_found_response = client.get("/api/v1/records/nonexistent_id")
        print(f"   响应状态码: {not_found_response.status_code}")
        if not_found_response.status_code == 404:
            print("   正确返回404")
        else:
            print(f"   意外的状态码: {not_found_response.status_code}")

        print("记录API测试完成")

    except ImportError as e:
        print(f"导入失败: {e}")
        print("请确保已安装依赖: pip install -r requirements.txt")
    except Exception as e:
        print(f"测试失败: {e}")