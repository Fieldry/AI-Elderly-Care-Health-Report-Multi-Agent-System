#!/bin/bash

echo "🧹 清理旧数据..."
rm -f /tmp/elderly-care-db/users.db
rm -f /tmp/elderly-care-db/.secret_key

echo "🚀 启动后端服务器..."
cd "$(dirname "$0")"

# 加载 .env 文件
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
    echo "✓ 已加载 .env 文件"
fi

cd api
python3 server.py
