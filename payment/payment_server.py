#!/usr/bin/env python3
"""
speedClaw Bot20x - 付款确认自动发货系统
用户付款后提交TX哈希，系统验证后自动生成授权码
"""

import os
import sys
import json
import requests
import time
import hashlib
from datetime import datetime, timedelta
from flask import Flask, request, render_template_string, jsonify

app = Flask(__name__)

# === 配置 ===
LICENSE_DB = "/root/.openclaw/workspace/speedClaw-Bot20x-Skill/.license_db.json"
RECIPIENT_ADDRESS = "0xFb4f3eFA1FeB256131FEEf2E2Ca4B2F2e9b22d6E"
PRICES_USDT = {
    "monthly": 9.9,
    "quarterly": 24.9,
    "yearly": 79.9
}
PRICE_NAMES = {
    "monthly": "月度订阅 ($9.9)",
    "quarterly": "季度订阅 ($24.9)",
    "yearly": "年度订阅 ($79.9)"
}

# BSC RPC
BSC_RPC = "https://bsc-dataseed.binance.org/"

def generate_license_key():
    import secrets
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

def verify_bnb_tx(tx_hash, expected_amount):
    """验证BNB Smart Chain上的USDT转账"""
    try:
        # BSC用eth_getTransactionByHash查
        payload = {
            "jsonrpc": "2.0",
            "method": "eth_getTransactionByHash",
            "params": [tx_hash],
            "id": 1
        }
        resp = requests.post(BSC_RPC, json=payload, timeout=15)
        data = resp.json()
        
        if "result" not in data or not data["result"]:
            return False, "交易不存在或 Pending"
        
        tx = data["result"]
        to_addr = tx.get("to", "").lower()
        value_wei = int(tx.get("value", "0x0"), 16)
        value_bnb = value_wei / 1e18
        
        # 检查接收地址
        if to_addr != RECIPIENT_ADDRESS.lower():
            return False, f"收款地址不匹配：{to_addr}"
        
        # 检查金额（至少覆盖订阅费用）
        if value_bnb < expected_amount * 0.95:  # 允许5%误差
            return False, f"金额不足：{value_bnb:.4f} BNB（需要 {expected_amount} USDT）"
        
        return True, f"验证成功：{value_bnb:.4f} BNB"
    except requests.exceptions.Timeout:
        return False, "网络超时，请稍后重试"
    except Exception as e:
        return False, f"验证失败：{str(e)}"

def generate_license(email, plan, tx_hash):
    """生成授权码"""
    db = load_db()
    key = generate_license_key()
    
    # 检查是否已用过这个TX
    for lic in db.get("licenses", []):
        if lic.get("tx_hash") == tx_hash:
            return None, "此交易已使用过，请勿重复提交"
    
    license_info = {
        "key": key,
        "email": email,
        "plan": plan,
        "tx_hash": tx_hash,
        "created": datetime.now().isoformat(),
        "expires": (datetime.now() + timedelta(days=30 if plan=="monthly" else 90 if plan=="quarterly" else 365)).isoformat(),
        "active": True
    }
    
    db["licenses"].append(license_info)
    save_db(db)
    
    return key, "授权码生成成功"

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>speedClaw Bot20x - 订阅授权</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: linear-gradient(135deg, #0a0e17 0%, #1a1f2e 100%);
  min-height: 100vh;
  color: #e0e6ed;
  padding: 20px;
}
.container { max-width: 600px; margin: 0 auto; }
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
  padding: 30px;
  margin-bottom: 20px;
}
.section-title {
  font-size: 16px;
  color: #00d26a;
  margin-bottom: 20px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.input-group { margin-bottom: 16px; }
.input-group label {
  display: block;
  font-size: 13px;
  color: #6b7280;
  margin-bottom: 6px;
}
.input-group input, .input-group select {
  width: 100%;
  padding: 12px 16px;
  background: #1a2332;
  border: 1px solid #1f2937;
  border-radius: 8px;
  color: #e0e6ed;
  font-size: 14px;
}
.input-group input:focus, .input-group select:focus {
  outline: none;
  border-color: #00d26a;
}
.price-card {
  background: #1a2332;
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 20px;
}
.price-row {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid #1f2937;
  font-size: 14px;
}
.price-row:last-child { border: none; }
.price-row .name { color: #9ca3af; }
.price-row .value { font-weight: 600; }
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
  transition: transform 0.2s, box-shadow 0.2s;
}
.btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 20px rgba(0,210,106,0.3);
}
.btn:disabled { opacity: 0.6; cursor: not-allowed; }
.result {
  margin-top: 20px;
  padding: 16px;
  border-radius: 12px;
  font-size: 14px;
  display: none;
}
.result.success {
  background: rgba(0,210,106,0.1);
  border: 1px solid #00d26a;
  color: #00d26a;
}
.result.error {
  background: rgba(255,71,87,0.1);
  border: 1px solid #ff4757;
  color: #ff4757;
}
.license-key {
  background: #0a0e17;
  padding: 12px 16px;
  border-radius: 8px;
  font-family: monospace;
  font-size: 18px;
  color: #00d26a;
  word-break: break-all;
  margin-top: 12px;
}
.copy-btn {
  margin-top: 12px;
  padding: 8px 20px;
  background: #1f2937;
  border: none;
  border-radius: 6px;
  color: #e0e6ed;
  cursor: pointer;
}
.copy-btn:hover { background: #374151; }
.info-box {
  background: #1a2332;
  border-radius: 12px;
  padding: 16px;
  margin-top: 20px;
  font-size: 13px;
  color: #9ca3af;
}
.info-box h4 { color: #e0e6ed; margin-bottom: 12px; }
.info-box ol { padding-left: 20px; }
.info-box li { margin-bottom: 8px; }
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
    <p>订阅授权 - 自动发货系统</p>
  </div>

  <div class="card">
    <div class="section-title">💰 套餐选择</div>
    <div class="price-card">
      <div class="price-row"><span class="name">月度订阅</span><span class="value">$9.9 / 30天</span></div>
      <div class="price-row"><span class="name">季度订阅</span><span class="value">$24.9 / 90天</span></div>
      <div class="price-row"><span class="name">年度订阅</span><span class="value">$79.9 / 365天</span></div>
    </div>

    <div class="section-title">📝 提交付款信息</div>
    <form id="paymentForm">
      <div class="input-group">
        <label>选择套餐 *</label>
        <select name="plan" required>
          <option value="">请选择套餐</option>
          <option value="monthly">月度订阅 - $9.9</option>
          <option value="quarterly">季度订阅 - $24.9</option>
          <option value="yearly">年度订阅 - $79.9</option>
        </select>
      </div>
      <div class="input-group">
        <label>USDT BEP20 转账 TX Hash *</label>
        <input type="text" name="tx_hash" placeholder="粘贴交易哈希（如 0x...）" required>
      </div>
      <div class="input-group">
        <label>邮箱 *</label>
        <input type="email" name="email" placeholder="用于接收授权码" required>
      </div>
      <div class="input-group">
        <label>Telegram（选填）</label>
        <input type="text" name="telegram" placeholder="@username">
      </div>
      <button type="submit" class="btn" id="submitBtn">验证并获取授权码</button>
    </form>

    <div class="result" id="resultBox"></div>
  </div>

  <div class="info-box">
    <h4>📋 操作步骤</h4>
    <ol>
      <li>向以下地址转账对应套餐金额的 USDT（BEP20）：<br>
      <code style="color:#00d26a;word-break:break-all;">0xFb4f3eFA1FeB256131FEEf2E2Ca4B2F2e9b22d6E</code></li>
      <li>复制转账交易哈希（TX Hash）粘贴到上方输入框</li>
      <li>填写邮箱和联系方式</li>
      <li>点击「验证并获取授权码」</li>
      <li>验证通过后自动显示授权码</li>
    </ol>
  </div>

  <div class="footer">
    speedClaw Bot20x v5.2 | 策略评分 87/100
  </div>
</div>

<script>
const form = document.getElementById('paymentForm');
const resultBox = document.getElementById('resultBox');
const submitBtn = document.getElementById('submitBtn');

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  submitBtn.disabled = true;
  submitBtn.textContent = '验证中...';
  resultBox.style.display = 'none';
  
  const formData = new FormData(form);
  const data = Object.fromEntries(formData);
  
  try {
    const resp = await fetch('/api/verify', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(data)
    });
    const result = await resp.json();
    
    if (result.success) {
      resultBox.className = 'result success';
      resultBox.innerHTML = `
        <strong>✅ 验证通过！</strong><br>
        您的授权码：<div class="license-key">${result.license_key}</div>
        <button class="copy-btn" onclick="copyKey('${result.license_key}')">复制授权码</button>
        <p style="margin-top:12px;font-size:12px;color:#6b7280;">
          到期：${result.expires}<br>
          有效期：${result.days}天
        </p>
      `;
    } else {
      resultBox.className = 'result error';
      resultBox.innerHTML = `<strong>❌ 验证失败：${result.message}</strong>`;
    }
  } catch (err) {
    resultBox.className = 'result error';
    resultBox.innerHTML = `<strong>❌ 网络错误，请稍后重试</strong>`;
  }
  
  resultBox.style.display = 'block';
  submitBtn.disabled = false;
  submitBtn.textContent = '验证并获取授权码';
});

function copyKey(key) {
  navigator.clipboard.writeText(key).then(() => {
    alert('授权码已复制！');
  });
}
</script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/verify', methods=['POST'])
def verify():
    data = request.json
    tx_hash = data.get('tx_hash', '').strip()
    plan = data.get('plan', '').strip()
    email = data.get('email', '').strip()
    
    if not tx_hash or not plan or not email:
        return jsonify({"success": False, "message": "请填写完整信息"})
    
    if not tx_hash.startswith('0x') or len(tx_hash) < 64:
        return jsonify({"success": False, "message": "TX Hash 格式不正确"})
    
    if plan not in PRICES_USDT:
        return jsonify({"success": False, "message": "未知的套餐"})
    
    # 验证交易
    expected_amount = PRICES_USDT[plan]
    valid, msg = verify_bnb_tx(tx_hash, expected_amount)
    
    if not valid:
        return jsonify({"success": False, "message": msg})
    
    # 生成授权码
    key, gen_msg = generate_license(email, plan, tx_hash)
    
    if key is None:
        return jsonify({"success": False, "message": gen_msg})
    
    # 计算到期日
    days = 30 if plan == "monthly" else 90 if plan == "quarterly" else 365
    expires = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')
    
    return jsonify({
        "success": True,
        "license_key": key,
        "expires": expires,
        "days": days
    })

if __name__ == '__main__':
    print("="*60)
    print("speedClaw Bot20x - 付款确认自动发货系统")
    print("="*60)
    print("访问：http://localhost:5001")
    print("按 Ctrl+C 停止")
    print()
    app.run(host='0.0.0.0', port=5001, debug=False)