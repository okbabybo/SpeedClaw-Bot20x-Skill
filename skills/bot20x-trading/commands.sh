#!/bin/bash
# bot20x-trading Skill 快速命令卡
# 使用方法: bash ~/workspace/skills/bot20x-trading/commands.sh

echo "=== bot20x 交易机器人状态检查 ==="
echo ""

echo "【1】PM2进程状态"
pm2 list | grep bot20x

echo ""
echo "【2】最近日志 (最后10条)"
tail -10 bot_20x.log

echo ""
echo "【3】BTC持仓状态"
cat st_btc_short.json 2>/dev/null || echo "无BTC持仓"
cat st_btc_long.json 2>/dev/null || echo "无BTC做多"

echo ""
echo "【4】ETH持仓状态"
cat st_eth_short.json 2>/dev/null || echo "无ETH持仓"
cat st_eth_long.json 2>/dev/null || echo "无ETH做多"

echo ""
echo "【5】今日账户余额"
python3 -c "
import requests, hmac, hashlib, time
API_KEY = 'QccKkNLbtV61rJpOms4h2E0RWoZMfMhG2ar3v9tueF5kbQ6KkN4sUf5CFLLkMhzx'
SECRET = 'Q549z4g3QlOnVs0PDSCzW6Xy2nVt9763DMqWo64MLLDoUeV8MigrUGUQn2nZTDuU'
ts = str(int(time.time()*1000))
p = f'timestamp={ts}'
sig = hmac.new(SECRET.encode(), p.encode(), hashlib.sha256).hexdigest()
r = requests.get(f'https://fapi.binance.com/fapi/v2/account?{p}&signature={sig}', headers={'X-MBX-APIKEY': API_KEY}, timeout=10).json()
print(f\"余额: {r.get('availableBalance')} USDT\")
print(f\"总保证金: {r.get('totalMarginBalance')} USDT\")
" 2>/dev/null || echo "获取失败"