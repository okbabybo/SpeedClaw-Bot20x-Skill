#!/bin/bash
ALERT_FILE="/root/.openclaw/workspace/monitor/last_alert.json"
MONITOR_LOG="/root/.openclaw/workspace/monitor/monitor.log"
cd /root/.openclaw/workspace/monitor

RESULT=$(python3 market_monitor.py 2>&1)
echo "$RESULT" >> "$MONITOR_LOG"

# 提取告警行
ALERTS=$(echo "$RESULT" | grep ">> 🔴\|>> 🟢\|>> ⚠️\|>> 🚀\|>> 📉" | sed 's/  >> //')

if [ -n "$ALERTS" ]; then
    LAST_ALERT=$(cat "$ALERT_FILE" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('last',''))" 2>/dev/null)
    
    if [ "$ALERTS" != "$LAST_ALERT" ]; then
        TOKEN_RESP=$(curl -s -X POST 'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal' \
            -H 'Content-Type: application/json' \
            -d '{"app_id":"cli_a937a37e16b85cc7","app_secret":"82d0j94AKv3QpHISQXT79gAGnJVfYOfX"}')
        TOKEN=$(echo "$TOKEN_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tenant_access_token',''))")
        
        if [ -n "$TOKEN" ]; then
            NOW=$(date '+%Y-%m-%d %H:%M:%S GMT+8')
            # 提取表格部分
            TABLE=$(echo "$RESULT" | grep -A 20 "🦞 【OKX")
            
            MSG="🦞【自动盯盘提醒】${NOW}

📡 触发信号：
$ALERTS

📊 当前行情：
$(echo "$TABLE" | grep "^BTC\|^ETH\|^—\|^账户" | head -10)

⚡ 自动盯盘中，有机会第一时间通知你！"
            
            curl -s -X POST 'https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id' \
                -H "Authorization: Bearer $TOKEN" \
                -H 'Content-Type: application/json' \
                -d "{\"receive_id\":\"ou_ce5a94cfca07b266414b003138b8f1f8\",\"msg_type\":\"text\",\"content\":\"{\\\"text\\\":\\\"$(echo "$MSG" | sed 's/"/\\"/g' | tr '\n' ';')\\\"}\"}" > /dev/null
            
            echo "ALERT SENT: $ALERTS"
        fi
        
        echo "{\"last\":\"$ALERTS\",\"time\":\"$(date -Iseconds)\"}" > "$ALERT_FILE"
    else
        echo "[$(date)] 信号未变"
    fi
else
    echo "[$(date)] 无触发信号"
fi
