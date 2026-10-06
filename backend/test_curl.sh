#!/bin/bash

# 消防隐患识别API测试脚本

BASE_URL="http://localhost:8000"

echo "=== 消防隐患识别API测试 ==="
echo

# 1. 测试健康检查
echo "1. 健康检查"
curl -s "${BASE_URL}/health" | jq .
echo

# 2. 测试获取记录列表
echo "2. 获取记录列表"
curl -s "${BASE_URL}/api/v1/records?limit=20&offset=0" | jq .
echo

# 3. 测试获取单个记录（如果有记录的话）
echo "3. 获取单个记录详情"
# 先获取一个记录ID
RECORD_ID=$(curl -s "${BASE_URL}/api/v1/records?limit=1&offset=0" | jq -r '.records[0].record_id' 2>/dev/null)

if [ "$RECORD_ID" != "null" ] && [ -n "$RECORD_ID" ]; then
    echo "获取记录: $RECORD_ID"
    curl -s "${BASE_URL}/api/v1/records/${RECORD_ID}" | jq .
else
    echo "没有找到记录，跳过详情测试"
fi
echo

# 4. 测试不存在的记录
echo "4. 测试不存在的记录"
curl -s "${BASE_URL}/api/v1/records/nonexistent_id" | jq .
echo

echo "=== 测试完成 ==="