#!/usr/bin/env python3
"""每6小时清理超时订单(>24h)"""
import json
import time
from pathlib import Path

PENDING = Path('/root/.openclaw/workspace/.pending_payments.json')
TIMEOUT = 24 * 3600

if not PENDING.exists():
    print("no pending file")
    exit(0)

data = json.loads(PENDING.read_text())
now = time.time()
cleaned = 0
for pid, p in list(data.items()):
    if p.get('status') == 'pending' and now - p.get('created_at', 0) > TIMEOUT:
        p['status'] = 'expired'
        p['expired_at'] = now
        cleaned += 1

PENDING.write_text(json.dumps(data, indent=2, ensure_ascii=False))
print(f"cleaned {cleaned} expired orders")
