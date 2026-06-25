#!/bin/bash
# ============================================================
# SpeedClaw BotKing v1.4.3 - 一键安装脚本
# 现货网格+趋势双引擎量化机器人
# GitHub: okbabybo/SpeedClaw-Bot20x-Skill
# ============================================================

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo ""
echo "============================================================"
echo "  🦞 SpeedClaw BotKing v1.4.3 现货机器人 一键安装"
echo "============================================================"
echo ""

# 1. 检查Python
echo -e "${YELLOW}[1/5]${NC} 检查Python..."
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ 未找到Python3${NC}"
    echo "请先安装: apt install python3 python3-pip"
    exit 1
fi
PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo -e "${GREEN}✅ Python $PY_VERSION${NC}"

# 2. 安装依赖
echo -e "${YELLOW}[2/5]${NC} 安装依赖..."
pip3 install -q requests pyyaml python-docx 2>/dev/null || {
    echo -e "${RED}❌ 依赖安装失败${NC}"
    exit 1
}
echo -e "${GREEN}✅ 依赖安装完成${NC}"

# 3. 检查/安装PM2
echo -e "${YELLOW}[3/5]${NC} 检查PM2..."
if ! command -v pm2 &> /dev/null; then
    echo -e "${YELLOW}  PM2未安装, 正在安装...${NC}"
    npm install -g pm2 2>/dev/null || {
        echo -e "${YELLOW}  ⚠️ PM2安装失败, 可手动启动: python3 bot_king.py${NC}"
    }
fi
if command -v pm2 &> /dev/null; then
    echo -e "${GREEN}✅ PM2就绪${NC}"
else
    echo -e "${YELLOW}⚠️ PM2未就绪, 跳过PM2管理${NC}"
fi

# 4. 配置文件
echo -e "${YELLOW}[4/5]${NC} 配置文件..."
CONFIG_FILE="bot/config_exchange.yaml"
if [ ! -f "$CONFIG_FILE" ]; then
    cp bot/config_exchange.yaml.template "$CONFIG_FILE"
    chmod 600 "$CONFIG_FILE"
    echo -e "${GREEN}  ✅ 已生成配置文件 $CONFIG_FILE${NC}"
    echo -e "${YELLOW}  ⚠️ 请编辑填入你的API密钥: nano $CONFIG_FILE${NC}"
else
    echo -e "${GREEN}  ✅ 配置文件已存在${NC}"
fi

# 5. 启动
echo -e "${YELLOW}[5/5]${NC} 启动BotKing..."
if command -v pm2 &> /dev/null; then
    pm2 delete bot-king 2>/dev/null || true
    pm2 start bot/bot_king.py --name bot-king --interpreter python3
    pm2 save
    echo -e "${GREEN}✅ BotKing已启动${NC}"
else
    echo -e "${YELLOW}  ⚠️ PM2未安装, 请手动: python3 bot/bot_king.py${NC}"
fi

echo ""
echo "============================================================"
echo "  🎉 安装完成!"
echo "============================================================"
echo ""
echo "  常用命令:"
echo "    pm2 logs bot-king --nostream --lines 20  # 查看日志"
echo "    pm2 restart bot-king                      # 重启"
echo "    pm2 stop bot-king                         # 停止"
echo "    pm2 list | grep king                      # 状态"
echo ""
echo "  文档: https://okbabybo.github.io/SpeedClaw-Bot20x-Skill/"
echo "  联系: @Okbabybo"
echo "============================================================"