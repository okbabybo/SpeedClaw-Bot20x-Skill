#!/bin/bash
# SpeedClaw BotKing 现货机器人 - 快速安装脚本

echo "=========================================="
echo "SpeedClaw BotKing 现货机器人 安装脚本"
echo "=========================================="

# 检查Python
if ! command -v python3 &> /dev/null; then
    echo "错误：需要Python3"
    exit 1
fi

# 安装依赖
echo "安装依赖..."
pip install requests pyyaml -q

# 检查配置
if [ ! -f bot/bot_king_config.py ]; then
    echo "复制配置文件..."
    cp bot/bot_king_config.py.template bot/bot_king_config.py
    echo "请编辑 bot/bot_king_config.py 填入API密钥"
else
    echo "配置文件已存在"
fi

echo ""
echo "=========================================="
echo "安装完成！"
echo ""
echo "下一步："
echo "1. 编辑 bot/bot_king_config.py 填入API密钥"
echo "2. 运行：pm2 start bot/bot_king.py --name bot-king"
echo "3. 查看日志：pm2 logs bot-king"
echo "=========================================="
