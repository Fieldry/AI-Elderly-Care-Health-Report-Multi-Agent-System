#!/bin/bash

echo "🧪 AI 养老健康助手 - 完整测试与启动脚本"
echo "================================================"

# 1. 清理旧数据
echo ""
echo "📦 步骤 1/5: 清理旧数据..."
rm -f /tmp/elderly-care-db/users.db
rm -f /tmp/elderly-care-db/.secret_key
echo "✓ 清理完成"

# 2. 生成测试数据
echo ""
echo "📦 步骤 2/5: 生成测试数据..."
cd "$(dirname "$0")"
python3 generate_test_data.py
if [ $? -ne 0 ]; then
    echo "✗ 测试数据生成失败"
    exit 1
fi
echo "✓ 测试数据生成完成"

# 3. 检查后端依赖
echo ""
echo "📦 步骤 3/5: 检查后端配置..."
if [ ! -f ".env" ]; then
    echo "✗ .env 文件不存在"
    exit 1
fi
echo "✓ 后端配置正常"

# 4. 启动后端
echo ""
echo "📦 步骤 4/5: 启动后端服务..."
echo "后端将在 http://localhost:8001 运行"
echo "请在新终端运行前端: cd AI-Elderly-Care-Health-Report-Frontend && npm run dev"
echo ""
cd api
python3 server.py
