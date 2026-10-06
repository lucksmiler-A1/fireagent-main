#!/usr/bin/env python3
"""
网络连接测试脚本
"""
import socket
import requests
import time
import os

def test_server_connection(ip, port=8000):
    """测试服务器连接"""
    try:
        # 测试TCP连接
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((ip, port))
        sock.close()

        if result == 0:
            print(f"✅ TCP连接成功: {ip}:{port}")
            return True
        else:
            print(f"❌ TCP连接失败: {ip}:{port}")
            return False
    except Exception as e:
        print(f"❌ TCP连接错误: {e}")
        return False

def test_api_endpoints(base_url):
    """测试API端点"""
    endpoints = [
        "/health",
        "/api/v1/records?limit=1&offset=0"
    ]

    for endpoint in endpoints:
        try:
            url = base_url + endpoint
            print(f"测试 {url}...")
            response = requests.get(url, timeout=10)

            if response.status_code == 200:
                print(f"  ✅ {endpoint}: {response.status_code}")
                if endpoint == "/health":
                    data = response.json()
                    print(f"     响应: {data}")
            else:
                print(f"  ❌ {endpoint}: {response.status_code}")
                print(f"     错误: {response.text[:100]}")

        except requests.exceptions.RequestException as e:
            print(f"  ❌ {endpoint}: 连接失败 - {e}")

        time.sleep(0.5)  # 避免请求过快

def main():
    """主函数"""
    print("🔗 网络连接测试")
    print("=" * 40)

    # 配置信息
    server_ip = os.getenv("FIREAGENT_SERVER_IP", "127.0.0.1")
    server_port = int(os.getenv("FIREAGENT_SERVER_PORT", "8000"))
    base_url = f"http://{server_ip}:{server_port}"

    print(f"目标服务器: {base_url}")
    print()

    # 1. 测试TCP连接
    print("1. 测试TCP连接...")
    if not test_server_connection(server_ip, server_port):
        print()
        print("❌ 无法连接到服务器")
        print("请确保：")
        print("  - 后端服务器已启动")
        print("  - 命令: cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000")
        print("  - 防火墙允许连接")
        return

    print()

    # 2. 测试API端点
    print("2. 测试API端点...")
    test_api_endpoints(base_url)

    print()
    print("🎯 如果所有测试都通过，说明网络配置正确")
    print("现在可以重新编译小程序测试图片上传功能")

if __name__ == "__main__":
    main()
