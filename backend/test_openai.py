#!/usr/bin/env python3
"""
OpenAI API 测试脚本
"""
import sys
import os

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(__file__))

if __name__ == "__main__":
    try:
        # 检查环境变量
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("❌ 请设置环境变量 OPENAI_API_KEY")
            print("例如: export OPENAI_API_KEY='your-api-key-here'")
            sys.exit(1)

        print("✅ 找到 OPENAI_API_KEY 环境变量")

        # 尝试导入并创建客户端
        from openai import OpenAI
        client = OpenAI(api_key=api_key)

        # 测试API连接
        print("🔄 正在测试 OpenAI API 连接...")
        try:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=10
            )
            print("✅ OpenAI API 连接成功")
            print(f"   响应: {response.choices[0].message.content.strip()}")
        except Exception as e:
            print(f"❌ OpenAI API 连接失败: {e}")
            sys.exit(1)

        print("🎉 OpenAI 集成测试完成！")

    except ImportError as e:
        print(f"❌ 导入失败: {e}")
        print("请安装依赖: pip install -r requirements.txt")
    except Exception as e:
        print(f"❌ 测试失败: {e}")