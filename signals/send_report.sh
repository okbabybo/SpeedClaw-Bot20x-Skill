#!/bin/bash
cd /root/.openclaw/workspace/signals
python3 lobster_trader.py > /tmp/watch_report.txt 2>&1

TOKEN_RESP=$(curl -s -X POST 'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal' \
    -H 'Content-Type: application/json' \
    -d '{"app_id":"cli_a937a37e16b85cc7","app_secret":"82d0j94AKv3QpHISQXT79gAGnJVfYOfX"}')
TOKEN=$(echo "$TOKEN_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tenant_access_token',''))")

if [ -n "$TOKEN" ]; then
    REPORT=$(cat /tmp/watch_report.txt)
    curl -s -X POST 'https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id' \
        -H "Authorization: Bearer $TOKEN" \
        -H 'Content-Type: application/json' \
        -d "{\"receive_id\":\"ou_ce5a94cfca07b266414b003138b8f1f8\",\"msg_type\":\"text\",\"content\":{\"text\":\"$REPORT\"}}" > /dev/null 2>&1
fi
