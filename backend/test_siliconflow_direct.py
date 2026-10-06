import os
import sys
from dotenv import load_dotenv

# 1. 尝试加载 .env
load_dotenv()

api_key = os.getenv("SILICONFLOW_API_KEY")
print(f"Loaded API Key: {api_key[:5]}...***" if api_key else "API Key NOT FOUND")

# 2. 尝试导入 openai
try:
    from openai import OpenAI
    print("OpenAI library imported successfully.")
except ImportError as e:
    print(f"Failed to import openai: {e}")
    sys.exit(1)

# 3. 尝试调用 API
if api_key:
    client = OpenAI(api_key=api_key, base_url="https://api.siliconflow.cn/v1")
    try:
        print("Sending test request...")
        response = client.chat.completions.create(
            model="Qwen/Qwen2.5-7B-Instruct", # 使用一个小一点的纯文本模型测试连通性
            messages=[
                {"role": "user", "content": "Hello"}
            ],
            max_tokens=10
        )
        print("Response received:")
        print(response.choices[0].message.content)
    except Exception as e:
        print(f"API call failed: {e}")
else:
    print("Skipping API call due to missing key.")
