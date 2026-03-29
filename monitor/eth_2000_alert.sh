#!/bin/bash
# ETH 2000 突破预警脚本（由cron调用）
# 每2分钟运行一次，价格>2000时发送飞书通知

STATE_FILE="/root/.openclaw/workspace/monitor/eth_2000_state.json"
LOG_FILE="/root/.openclaw/workspace/monitor/eth_2000_watch.log"

# 获取OKX ETH价格
PRICE=$(curl -s "https://www.okx.com/api/v5/market/ticker?instId=ETH-USDT-SWAP" | python3 -c "
import json,sys
d=json.load(sys.stdin)
print(d['data'][0]['last'])
" 2>/dev/null)

if [ -z "$PRICE" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 价格获取失败" >> "$LOG_FILE"
    exit 1
fi

THRESHOLD=2000
PRICE_F=$(python3 -c "print(float('$PRICE'))")

echo "[$(date '+%Y-%m-%d %H:%M:%S')] ETH=\$$PRICE_F 阈值=$THRESHOLD" >> "$LOG_FILE"

# 检查是否高于阈值
python3 -c "
price = float('$PRICE')
threshold = $THRESHOLD
import sys
sys.exit(0 if price > threshold else 1)
"
ABOVE=$?

if [ $ABOVE -eq 0 ]; then
    # 检查是否10分钟内已发过
    if [ -f "$STATE_FILE" ]; then
        LAST_EPOCH=$(python3 -c "
import json
d = json.load(open('$STATE_FILE'))
print(d.get('last_time_epoch', 0))
" 2>/dev/null)
        NOW_EPOCH=$(date +%s)
        DIFF=$((NOW_EPOCH - LAST_EPOCH))
        if [ $DIFF -lt 600 ]; then
            echo "[$(date '+%Y-%m-%d %H:%M:%S')] 10分钟内已发预警，跳过" >> "$LOG_FILE"
            exit 0
        fi
    fi
    
    NOW=$(date '+%Y-%m-%d %H:%M:%S GMT+8')
    
    # 获取飞书token
    TOKEN=$(curl -s -X POST 'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal' \
        -H 'Content-Type: application/json' \
        -d '{"app_id":"cli_a937a37e16b85cc7","app_secret":"82d0j94AKv3QpHISQXT79gAGnJVfYOfX"}' | python3 -c "import sys,json; print(json.load(sys.stdin).get('tenant_access_token',''))")
    
    if [ -n "$TOKEN" ]; then
        # 使用简单格式（已验证可用）
        curl -s -X POST 'https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id' \
            -H "Authorization: Bearer $TOKEN" \
            -H 'Content-Type: application/json' \
            -d "{\"receive_id\":\"ou_ce5a94cfca07b266414b003138b8f1f8\",\"msg_type\":\"text\",\"content\":\"{\\\"text\\\":\\\"🚀 ETH 突破2000！当前约\\\$$PRICE_F，$NOW。多头信号！止损设\$1990。如BTC配合破66500，ETH目标2040-2070。\\\"}\"}" > /dev/null 2>&1
        
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✅ 预警已发送：ETH=\$$PRICE_F" >> "$LOG_FILE"
        
        python3 -c "
import json
from datetime import datetime
d = {
    'last_alert': 'ETH突破$THRESHOLD',
    'last_time': datetime.now().isoformat(),
    'last_time_epoch': $(date +%s),
    'price_triggered': $PRICE_F
}
json.dump(d, open('$STATE_FILE', 'w'))
"
    else
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] ❌ Token获取失败" >> "$LOG_FILE"
    fi
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ETH=\$$PRICE_F 未触发（需>$THRESHOLD）" >> "$LOG_FILE"
fi
