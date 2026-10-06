#!/usr/bin/env python3
"""
网络配置自动检测和设置脚本
"""
import socket
import subprocess
import platform
import re


def get_local_ip():
    """获取本地IP地址"""
    try:
        # 创建一个socket连接到外部地址，获取本机IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))  # 连接到Google DNS
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        return None


def get_network_info_windows():
    """Windows系统网络信息"""
    try:
        result = subprocess.run(['ipconfig'], capture_output=True, text=True, encoding='gbk')
        output = result.stdout

        # 查找IPv4地址
        ipv4_pattern = r'IPv4 地址[ .\s]*:\s*(\d+\.\d+\.\d+\.\d+)'
        matches = re.findall(ipv4_pattern, output)

        # 过滤出内网地址
        private_ips = []
        for ip in matches:
            if ip.startswith(('192.168.', '10.', '172.')):
                private_ips.append(ip)

        return private_ips[:3]  # 返回前3个内网地址
    except Exception as e:
        print(f"获取Windows网络信息失败: {e}")
        return []


def get_network_info_unix():
    """Unix系统网络信息"""
    try:
        result = subprocess.run(['ifconfig'], capture_output=True, text=True)
        if result.returncode != 0:
            # 尝试ip addr命令
            result = subprocess.run(['ip', 'addr'], capture_output=True, text=True)

        output = result.stdout

        # 查找inet地址
        inet_pattern = r'inet (\d+\.\d+\.\d+\.\d+)'
        matches = re.findall(inet_pattern, output)

        # 过滤出内网地址
        private_ips = []
        for ip in matches:
            if ip.startswith(('192.168.', '10.', '172.')) and not ip.endswith('.1'):
                private_ips.append(ip)

        return private_ips[:3]  # 返回前3个内网地址
    except Exception as e:
        print(f"获取Unix网络信息失败: {e}")
        return []


def update_config_file(ip_address):
    """更新配置文件"""
    config_file = "../utils/config.js"  # 相对于backend目录

    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # 替换BASE_URL
        old_pattern = r"BASE_URL: '[^']*'"
        new_value = f"BASE_URL: 'http://{ip_address}:8000'"
        new_content = re.sub(old_pattern, new_value, content)

        with open(config_file, 'w', encoding='utf-8') as f:
            f.write(new_content)

        print(f"✅ 已更新配置文件: {config_file}")
        print(f"   BASE_URL: http://{ip_address}:8000")

    except Exception as e:
        print(f"❌ 更新配置文件失败: {e}")


def main():
    """主函数"""
    print("🔍 网络配置检测工具")
    print("=" * 40)

    # 检测操作系统
    system = platform.system().lower()

    # 获取网络信息
    if system == "windows":
        ips = get_network_info_windows()
    else:
        ips = get_network_info_unix()

    # 尝试获取本地IP
    local_ip = get_local_ip()
    if local_ip and local_ip not in ips:
        ips.insert(0, local_ip)

    if not ips:
        print("❌ 未找到可用的内网IP地址")
        print("请手动检查网络配置")
        return

    print("📋 检测到的内网IP地址:")
    for i, ip in enumerate(ips, 1):
        print(f"   {i}. {ip}")

    print()

    # 让用户选择IP
    while True:
        try:
            choice = input("请选择要使用的IP地址编号 (1-{}): ".format(len(ips)))
            choice_num = int(choice)
            if 1 <= choice_num <= len(ips):
                selected_ip = ips[choice_num - 1]
                break
            else:
                print("无效选择，请重新输入")
        except ValueError:
            print("请输入有效的数字")

    print(f"🎯 选择IP: {selected_ip}")

    # 更新配置文件
    update_config_file(selected_ip)

    print()
    print("🚀 下一步:")
    print("1. 启动后端服务器:")
    print("   cd backend")
    print("   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000")
    print()
    print("2. 测试连接:")
    print(f"   curl http://{selected_ip}:8000/health")
    print()
    print("3. 重新编译小程序")
    print("4. 测试图片上传功能")

    print()
    print("📝 注意:")
    print("- 确保手机和电脑在同一WiFi网络")
    print("- 如果连接仍然失败，检查防火墙设置")


if __name__ == "__main__":
    main()