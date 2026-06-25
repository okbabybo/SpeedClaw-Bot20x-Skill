#!/bin/bash
# ============================================================
# BotKing Telegram Bot 一键部署脚本
# 输入Token即可完成所有配置
# ============================================================

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo ""
echo "============================================================"
echo "  🦞 BotKing Telegram Bot 一键部署"
echo "============================================================"
echo ""

# 1. 检查Python
echo -e "${YELLOW}[1/5]${NC} 检查环境..."
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python3未安装${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Python3就绪${NC}"

# 2. 安装依赖
echo -e "${YELLOW}[2/5]${NC} 安装依赖..."
pip3 install -q python-telegram-bot flask 2>/dev/null || {
    echo -e "${RED}❌ 依赖安装失败${NC}"
    exit 1
}
echo -e "${GREEN}✅ 依赖就绪${NC}"

# 3. 获取Token
echo -e "${YELLOW}[3/5]${NC} 配置Telegram Bot Token"
echo "  💡 如何获取Token:"
echo "     1. Telegram搜索 @BotFather"
echo "     2. 发送 /newbot"
echo "     3. 按提示设置名称和用户名"
echo "     4. 复制返回的Token"
echo ""
read -p "  请粘贴你的Token: " TG_TOKEN
if [ -z "$TG_TOKEN" ]; then
    echo -e "${RED}❌ Token不能为空${NC}"
    exit 1
fi

# 4. 保存Token
echo -e "${YELLOW}[4/5]${NC} 保存Token..."
grep -v "TELEGRAM_TOKEN" ~/.bashrc > /tmp/bashrc_temp 2>/dev/null || true
echo "export TELEGRAM_TOKEN=\"$TG_TOKEN\"" >> /tmp/bashrc_temp
mv /tmp/bashrc_temp ~/.bashrc
export TELEGRAM_TOKEN="$TG_TOKEN"
echo -e "${GREEN}✅ Token已保存到 ~/.bashrc${NC}"

# 5. PM2启动
echo -e "${YELLOW}[5/5]${NC} 启动Bot..."
cd /root/.openclaw/workspace
pm2 delete botking-tg 2>/dev/null || true
pm2 start "python3 /root/.openclaw/workspace/speedClaw-Bot20x-Skill/bot/botking_telegram.py" \
    --name botking-tg \
    --cwd /root/.openclaw/workspace
pm2 save

echo ""
echo "============================================================"
echo -e "${GREEN}  ✅ 部署完成!${NC}"
echo "============================================================"
echo ""
echo "  📱 步骤:"
echo "     1. 在Telegram搜索你的机器人用户名"
echo "     2. 发送 /start"
echo "     3. 试试 /status /balance /positions"
echo ""
echo "  📋 常用命令:"
echo "     pm2 logs botking-tg        # 查看日志"
echo "     pm2 restart botking-tg     # 重启"
echo "     pm2 stop botking-tg        # 停止"
echo "     pm2 list | grep botking    # 状态"
echo ""
echo "  💡 提示: Token已保存到 ~/.bashrc,新终端自动生效"
echo "============================================================"