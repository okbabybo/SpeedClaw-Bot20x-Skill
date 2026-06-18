#!/usr/bin/env python3
"""
speedClaw Bot20x - 订阅授权管理系统
用法：python license_manager.py [命令] [参数]

命令：
  python license_manager.py generate <邮箱> <套餐> 生成授权码
  python license_manager.py check <授权码>             检查授权码
  python license_manager.py revoke <授权码>           撤销授权码
  python license_manager.py list                     列出所有授权码
"""

import sys
import json
import hashlib
import time
from datetime import datetime, timedelta

LICENSE_DB = "/root/.openclaw/workspace/speedClaw-Bot20x-Skill/.license_db.json"

PLANS = {
    "yearly": {"days": 365, "price": "$399.9/年"},
}

def load_db():
    try:
        with open(LICENSE_DB) as f:
            return json.load(f)
    except:
        return {"licenses": []}

def save_db(db):
    with open(LICENSE_DB, "w") as f:
        json.dump(db, f, indent=2)

def generate_key():
    import secrets
    return "SCB-" + secrets.token_hex(8).upper()

def generate_license(email, plan):
    if plan not in PLANS:
        print(f"错误：未知套餐 '{plan}'")
        print(f"可用套餐：{', '.join(PLANS.keys())}")
        return
    
    db = load_db()
    key = generate_key()
    
    license_info = {
        "key": key,
        "email": email,
        "plan": plan,
        "created": datetime.now().isoformat(),
        "expires": (datetime.now() + timedelta(days=PLANS[plan]["days"])).isoformat(),
        "active": True
    }
    
    db["licenses"].append(license_info)
    save_db(db)
    
    print(f"✅ 授权码已生成")
    print(f"授权码：{key}")
    print(f"套餐：{PLANS[plan]['price']}")
    print(f"到期：{license_info['expires'][:10]}")
    print(f"用户：{email}")

def check_license(key):
    db = load_db()
    for lic in db["licenses"]:
        if lic["key"] == key:
            if not lic["active"]:
                print("❌ 授权码已被禁用")
                return False
            expires = datetime.fromisoformat(lic["expires"])
            if datetime.now() > expires:
                days_overdue = (datetime.now() - expires).days
                print(f"❌ 授权码已过期（过期{days_overdue}天）")
                return False
            days_left = (expires - datetime.now()).days
            print(f"✅ 授权有效")
            print(f"套餐：{lic['plan']}")
            print(f"到期：{lic['expires'][:10]}（还剩{days_left}天）")
            return True
    print("❌ 授权码无效")
    return False

def revoke_license(key):
    db = load_db()
    for lic in db["licenses"]:
        if lic["key"] == key:
            lic["active"] = False
            save_db(db)
            print(f"✅ 授权码已撤销：{key}")
            return
    print(f"❌ 未找到授权码：{key}")

def list_licenses():
    db = load_db()
    if not db["licenses"]:
        print("暂无授权码")
        return
    print(f"{'授权码':<25} {'用户':<25} {'套餐':<10} {'到期':<12} {'状态'}")
    print("-" * 80)
    for lic in sorted(db["licenses"], key=lambda x: x["created"], reverse=True):
        expires = lic["expires"][:10]
        status = "✅" if lic["active"] and datetime.now() <= datetime.fromisoformat(lic["expires"]) else "❌"
        print(f"{lic['key']:<25} {lic['email']:<25} {lic['plan']:<10} {expires:<12} {status}")

def verify_license_in_bot(key):
    """Bot启动时调用此函数验证授权"""
    db = load_db()
    for lic in db["licenses"]:
        if lic["key"] == key:
            if not lic["active"]:
                return False, "授权码已被禁用"
            expires = datetime.fromisoformat(lic["expires"])
            if datetime.now() > expires:
                return False, f"授权码已过期"
            return True, f"授权有效（{lic['plan']}，到期{expires[:10]}）"
    return False, "授权码无效"

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else None
    
    if cmd == "generate" and len(sys.argv) >= 4:
        generate_license(sys.argv[2], sys.argv[3])
    elif cmd == "check" and len(sys.argv) >= 3:
        check_license(sys.argv[2])
    elif cmd == "revoke" and len(sys.argv) >= 3:
        revoke_license(sys.argv[2])
    elif cmd == "list":
        list_licenses()
    else:
        print(__doc__)