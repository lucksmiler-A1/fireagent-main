#!/usr/bin/env python3
"""
Quick test for local proxy endpoint:
POST http://127.0.0.1:8000/api/v1/chat/completions
"""
import json
import os
import sys

import requests


def main() -> int:
    if not os.getenv("SILICONFLOW_API_KEY"):
        print("Missing env var: SILICONFLOW_API_KEY")
        print("PowerShell example:")
        print('$env:SILICONFLOW_API_KEY="your_new_key_here"')
        return 1

    url = "http://127.0.0.1:8000/api/v1/chat/completions"
    payload = {
        "model": "Qwen/Qwen3.6-35B-A3B",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Introduce yourself in one sentence."},
        ],
        "stream": False,
        "temperature": 0.7,
        "max_tokens": 256,
    }

    try:
        resp = requests.post(url, json=payload, timeout=120)
    except requests.RequestException as exc:
        print(f"Request failed: {exc}")
        return 1

    print(f"HTTP {resp.status_code}")
    try:
        data = resp.json()
    except ValueError:
        print(resp.text)
        return 1

    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0 if resp.ok else 1


if __name__ == "__main__":
    sys.exit(main())
