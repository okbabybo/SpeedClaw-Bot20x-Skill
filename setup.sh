#!/bin/bash
# speedClaw Bot20x - 快速安装脚本

echo "=========================================="
echo "speedClaw Bot20x v5.2 安装脚本"
echo "=========================================="

# 检查Python
if ! command -v python3 &> /dev/null; then
    echo "错误：需要Python3"
    exit 1
fi

# 安装依赖
echo "安装依赖..."
pip install -r requirements.txt

# 检查配置
if [ ! -f bot/config.py ]; then
    echo "复制配置文件..."
    cp bot/config.py.template bot/config.py
    echo "请编辑 bot/config.py 填入API密钥"
else
    echo "配置文件已存在"
fi

echo ""
echo "=========================================="
echo "安装完成！"
echo ""
echo "下一步："
echo "1. 编辑 bot/config.py 填入API密钥"
echo "2. 运行：pm2 start bot/bot_20x.py --name bot20x"
echo "3. 查看日志：pm2 logs bot20x"
echo "=========================================="