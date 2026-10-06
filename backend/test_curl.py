#!/usr/bin/env python3
"""
使用Python的requests库测试API（模拟curl）
"""
import sys
import os

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(__file__))

try:
    import requests
    import json
except ImportError:
    print("需要安装requests库: pip install requests")
    sys.exit(1)

def test_api():
    """测试API接口"""
    base_url = "http://localhost:8000"

    print("=== 消防隐患识别API测试 ===")
    print()

    try:
        # 1. 测试健康检查
        print("1. 健康检查")
        response = requests.get(f"{base_url}/health")
        print(f"   状态码: {response.status_code}")
        print(f"   响应: {response.json()}")
        print()

        # 2. 测试获取记录列表
        print("2. 获取记录列表")
        response = requests.get(f"{base_url}/api/v1/records?limit=20&offset=0")
        print(f"   状态码: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   总记录数: {data['total']}")
            print(f"   返回记录数: {len(data['records'])}")
            if data['records']:
                record = data['records'][0]
                print(f"   示例记录ID: {record['record_id']}")
                print(f"   风险等级: {record['overall_risk']}")
                print(f"   缩略图URL: {record['thumbnail_url']}")
        else:
            print(f"   错误: {response.text}")
        print()

        # 3. 测试获取单个记录详情
        print("3. 获取单个记录详情")
        # 先获取记录列表中的第一个记录ID
        response = requests.get(f"{base_url}/api/v1/records?limit=1&offset=0")
        if response.status_code == 200:
            data = response.json()
            if data['records']:
                record_id = data['records'][0]['record_id']
                print(f"   获取记录: {record_id}")

                response = requests.get(f"{base_url}/api/v1/records/{record_id}")
                print(f"   状态码: {response.status_code}")
                if response.status_code == 200:
                    record = response.json()
                    print(f"   记录ID: {record['record_id']}")
                    print(f"   创建时间: {record['created_at']}")
                    print(f"   场景: {record['scene']}")
                    print(f"   风险等级: {record['overall_risk']}")
                    print(f"   隐患数量: {len(record['items'])}")
                else:
                    print(f"   错误: {response.text}")
            else:
                print("   没有找到记录")
        print()

        # 4. 测试不存在的记录
        print("4. 测试不存在的记录")
        response = requests.get(f"{base_url}/api/v1/records/nonexistent_id")
        print(f"   状态码: {response.status_code}")
        if response.status_code == 404:
            print("   正确返回404")
        else:
            print(f"   意外响应: {response.text}")
        print()

        print("=== 测试完成 ===")

    except requests.exceptions.ConnectionError:
        print("❌ 连接失败，请确保后端服务正在运行")
        print("运行: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000")
    except Exception as e:
        print(f"❌ 测试失败: {e}")

if __name__ == "__main__":
    test_api()