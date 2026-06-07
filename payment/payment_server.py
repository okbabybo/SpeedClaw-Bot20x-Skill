#!/usr/bin/env python3
"""
speedClaw Bot20x - 固定地址订阅系统
三个套餐对应三个固定收款地址，验证地址+金额即可
"""

import os
import sys
import json
import requests
import time
from datetime import datetime, timedelta
from flask import Flask, request, render_template_string, jsonify
import secrets

app = Flask(__name__)

# ===三个套餐对应三个收款地址 ===
SUBSCRIPTION_TIERS = {
    "monthly": {
        "name": "月度订阅",
        "price": 9.9,
        "days": 30,
        "address": "0xFb4f3eFA1FeB256131FEEf2E2Ca4B2F2e9b22d6E"
    },
    "quarterly": {
        "name": "季度订阅",
        "price": 24.9,
        "days": 90,
        "address": "0x6CDD7d0e7865f6DaDB9178dd114890ABD5d5323b"
    },
    "yearly": {
        "name": "年度订阅",
        "price": 79.9,
        "days": 365,
        "address": "0x352f5Cb1CA167500D27741676ab9efA4B07D3D30"
    }
}

LICENSE_DB = "/root/.openclaw/workspace/speedClaw-Bot20x-Skill/.license_db.json"
BSC_RPC = "https://bsc-dataseed.binance.org/"

def generate_key():
    return "SCB-" + secrets.token_hex(8).upper()

def load_db():
    try:
        with open(LICENSE_DB) as f:
            return json.load(f)
    except:
        return {"licenses": []}

def save_db(db):
    os.makedirs(os.path.dirname(LICENSE_DB), exist_ok=True)
    with open(LICENSE_DB, "w") as f:
        json.dump(db, f, indent=2)

def verify_transfer(tx_hash, expected_addr, expected_amount):
    """验证USDT BEP20转账"""
    try:
        payload = {
            "jsonrpc": "2.0",
            "method": "eth_getTransactionByHash",
            "params": [tx_hash],
            "id": 1
        }
        resp = requests.post(BSC_RPC, json=payload, timeout=15)
        data = resp.json()
        
        if "result" not in data or not data["result"]:
            return False, "交易不存在或Pending"
        
        tx = data["result"]
        to_addr = tx.get("to", "").lower()
        
        # 检查收款地址
        if to_addr != expected_addr.lower():
            return False, f"收款地址不匹配"
        
        # 获取input data中的USDT转账信息
        input_data = tx.get("input", "0x")
        
        # USDT合约调用（transfer函数）
        if len(input_data) >= 138:
            # 解析USDT转账金额
            # transfer后32字节是amount
            try:
                amount_hex = "0x" + input_data[74+24:138]
                amount = int(amount_hex, 16) / 1e18
            except:
                # 如果无法解析input data，用value字段
                value_wei = int(tx.get("value", "0x0"), 16)
                amount = value_wei / 1e18
        else:
            value_wei = int(tx.get("value", "0x0"), 16)
            amount = value_wei / 1e18
        
        # 允许10%误差
        if amount < expected_amount * 0.9:
            return False, f"金额不足：收到 {amount:.2f} USDT，需要 {expected_amount} USDT"
        
        return True, f"验证成功：{amount:.2f} USDT"
        
    except requests.exceptions.Timeout:
        return False, "网络超时，请稍后重试"
    except Exception as e:
        return False, f"验证失败：{str(e)}"

def create_license(tx_hash, tier_info):
    db = load_db()
    
    # 检查是否已用过
    for lic in db.get("licenses", []):
        if lic.get("tx_hash") == tx_hash:
            return None, lic["key"], "此TX已使用过，授权码：" + lic["key"]
    
    key = generate_key()
    license_info = {
        "key": key,
        "plan": tier_info["name"],
        "tier": list(SUBSCRIPTION_TIERS.keys())[list(SUBSCRIPTION_TIERS.values()).index(tier_info)],
        "tx_hash": tx_hash,
        "created": datetime.now().isoformat(),
        "expires": (datetime.now() + timedelta(days=tier_info["days"])).isoformat(),
        "active": True
    }
    
    db["licenses"].append(license_info)
    save_db(db)
    
    return key, key, "授权码生成成功"

HTML = '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>🦞 speedClaw Bot20x - 订阅授权</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: linear-gradient(135deg, #0a0e17 0%, #1a1f2e 100%);
  min-height: 100vh;
  color: #e0e6ed;
  padding: 20px;
}
.container { max-width: 520px; margin: 0 auto; }
.header {
  text-align: center;
  padding: 30px 0;
  border-bottom: 1px solid #1e2732;
  margin-bottom: 30px;
}
.header h1 { font-size: 28px; color: #00d26a; margin-bottom: 8px; }
.header p { color: #6b7280; font-size: 14px; }
.card {
  background: #111827;
  border: 1px solid #1f2937;
  border-radius: 16px;
  padding: 24px;
  margin-bottom: 20px;
}
.tier {
  background: #1a2332;
  border: 1px solid #1f2937;
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 12px;
  cursor: pointer;
  transition: border-color 0.2s;
}
.tier:hover { border-color: #00d26a; }
.tier.selected { border-color: #00d26a; background: rgba(0,210,106,0.05); }
.tier-name {
  font-size: 16px;
  font-weight: 600;
  color: #e0e6ed;
  margin-bottom: 6px;
}
.tier-price { font-size: 24px; color: #00d26a; font-weight: 700; }
.tier-days { font-size: 12px; color: #6b7280; }
.tier-addr {
  font-size: 11px;
  color: #4b5563;
  margin-top: 8px;
  word-break: break-all;
}
.section-title {
  font-size: 14px;
  color: #6b7280;
  margin-bottom: 16px;
  text-transform: uppercase;
  letter-spacing: 1px;
}
.input-group { margin-bottom: 16px; }
.input-group label {
  display: block;
  font-size: 13px;
  color: #6b7280;
  margin-bottom: 6px;
}
.input-group input {
  width: 100%;
  padding: 12px 16px;
  background: #1a2332;
  border: 1px solid #1f2937;
  border-radius: 8px;
  color: #e0e6ed;
  font-size: 14px;
}
.input-group input:focus { outline: none; border-color: #00d26a; }
.btn {
  width: 100%;
  padding: 14px;
  background: linear-gradient(135deg, #00d26a, #4ade80);
  border: none;
  border-radius: 10px;
  color: #0a0e17;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
}
.btn:hover { transform: translateY(-2px); box-shadow: 0 4px 20px rgba(0,210,106,0.3); }
.btn:disabled { opacity: 0.6; cursor: not-allowed; }
.result {
  margin-top: 20px;
  padding: 16px;
  border-radius: 12px;
  font-size: 14px;
  display: none;
}
.result.success { background: rgba(0,210,106,0.1); border: 1px solid #00d26a; }
.result.error { background: rgba(255,71,87,0.1); border: 1px solid #ff4757; }
.result.info { background: rgba(59,130,246,0.1); border: 1px solid #3b82f6; }
.license-key {
  background: #0a0e17;
  padding: 14px;
  border-radius: 8px;
  font-family: monospace;
  font-size: 18px;
  color: #00d26a;
  word-break: break-all;
  margin-top: 10px;
}
.footer {
  text-align: center;
  padding: 20px;
  color: #6b7280;
  font-size: 12px;
}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>🦞 speedClaw Bot20x</h1>
    <p>订阅授权 -验证付款即用</p>
  </div>

  <div class="card">
    <div class="section-title">选择套餐（向对应地址转账）</div>
    
    <div class="tier" data-tier="monthly" onclick="selectTier('monthly')">
      <div class="tier-name">月度订阅</div>
      <div class="tier-price">$9.9</div>
      <div class="tier-days">30天有效</div>
      <div class="tier-addr">0xFb4f3eFA1FeB256131FEEf2E2Ca4B2F2e9b22d6E</div>
    </div>
    
    <div class="tier" data-tier="quarterly" onclick="selectTier('quarterly')">
      <div class="tier-name">季度订阅</div>
      <div class="tier-price">$24.9</div>
      <div class="tier-days">90天有效</div>
      <div class="tier-addr">0x6CDD7d0e7865f6DaDB9178dd114890ABD5d5323b</div>
    </div>
    
    <div class="tier" data-tier="yearly" onclick="selectTier('yearly')">
      <div class="tier-name">年度订阅</div>
      <div class="tier-price">$79.9</div>
      <div class="tier-days">365天有效</div>
      <div class="tier-addr">0x352f5Cb1CA167500D27741676ab9efA4B07D3D30</div>
    </div>
  </div>

  <div class="card">
    <div class="section-title">粘贴转账TX哈希</div>
    <form id="form">
      <div class="input-group">
        <label>USDT BEP20 转账 TX Hash *</label>
        <input type="text" name="tx_hash" placeholder="0x..." required id="txInput">
      </div>
      <button type="submit" class="btn" id="btn">验证并获取授权码</button>
    </form>
    <div class="result" id="result"></div>
  </div>

  <div class="footer">
    speedClaw Bot20x v5.2 | 策略评分 87/100
  </div>
</div>

<script>
let selectedTier = null;

function selectTier(tier) {
  selectedTier = tier;
  document.querySelectorAll('.tier').forEach(el => el.classList.remove('selected'));
  document.querySelector(`[data-tier="${tier}"]`).classList.add('selected');
}

document.getElementById('form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const btn = document.getElementById('btn');
  const result = document.getElementById('result');
  const tx = document.getElementById('txInput').value.trim();
  
  if (!selectedTier) {
    result.className = 'result error';
    result.style.display = 'block';
    result.innerHTML = '请先选择套餐';
    return;
  }
  
  if (!tx || !tx.startsWith('0x')) {
    result.className = 'result error';
    result.style.display = 'block';
    result.innerHTML = '请输入有效的TX哈希';
    return;
  }
  
  btn.disabled = true;
  btn.textContent = '验证中...';
  result.style.display = 'none';
  
  try {
    const resp = await fetch('/api/verify', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({tx_hash: tx, tier: selectedTier})
    });
    const data = await resp.json();
    
    if (data.success) {
      result.className = 'result success';
      result.innerHTML = `
        <strong>✅ 验证通过！</strong><br><br>
        您的授权码：<div class="license-key">${data.license_key}</div>
        <p style="margin-top:12px;font-size:12px;color:#6b7280;">
          有效期：${data.days}天｜到期：${data.expires}
        </p>
      `;
    } else {
      result.className = 'result error';
      result.innerHTML = `<strong>❌ ${data.message}</strong>`;
    }
  } catch (e) {
    result.className = 'result error';
    result.innerHTML = '<strong>网络错误，请稍后重试</strong>';
  }
  
  result.style.display = 'block';
  btn.disabled = false;
  btn.textContent = '验证并获取授权码';
});
</script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/api/verify', methods=['POST'])
def verify():
    data = request.json
    tx_hash = data.get('tx_hash', '').strip()
    tier = data.get('tier', '').strip()
    
    if not tx_hash or not tier:
        return jsonify({"success": False, "message": "参数不完整"})
    
    if tier not in SUBSCRIPTION_TIERS:
        return jsonify({"success": False, "message": "未知的套餐"})
    
    tier_info = SUBSCRIPTION_TIERS[tier]
    
    # 验证
    valid, msg = verify_transfer(tx_hash, tier_info["address"], tier_info["price"])
    if not valid:
        return jsonify({"success": False, "message": msg})
    
    # 生成授权码
    _, key, gen_msg = create_license(tx_hash, tier_info)
    
    return jsonify({
        "success": True,
        "license_key": key,
        "days": tier_info["days"],
        "expires": (datetime.now() + timedelta(days=tier_info["days"])).strftime('%Y-%m-%d')
    })

if __name__ == '__main__':
    print("="*60)
    print("speedClaw Bot20x - 固定地址订阅系统")
    print("="*60)
    print("访问：http://localhost:5001")
    print()
    print("三个套餐收款地址：")
    for tier, info in SUBSCRIPTION_TIERS.items():
        print(f"  {info['name']} (${info['price']}): {info['address']}")
    print()
    app.run(host='0.0.0.0', port=5001, debug=False)