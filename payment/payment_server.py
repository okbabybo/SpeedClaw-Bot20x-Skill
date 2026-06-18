#!/usr/bin/env python3
"""
SpeedClaw Bot20× -全自动收款授权系统
功能：
  - 用户访问页面输入邮箱
  - 显示USDT TRC20收款地址
  - 用户转账后输入txid验证
  - 验证成功自动生成授权码并展示
"""

from flask import Flask, request, jsonify, render_template_string, redirect
import requests
import json
import time
import sys
import os
import threading
import hashlib
from datetime import datetime, timedelta
from urllib.parse import urlencode

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")
from bot.license_manager import generate_key, load_db, save_db

# ========== 配置 ==========
TRC20_ADDRESS = "0x344FfCe2f7B8f580D4e054F7213cb231CD15c3cd"
PRICE_USDT = 399.9
LICENSE_DAYS = 365
CHECK_ADDRESS = "TXYZopYRhr2StqEWrSE7JUGDTZpJ3M5LA"  # TRC20收款地址
TRONGRID_API = "https://api.trongrid.io"  # Tron mainnet

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False

# ========== 邮件发送 ==========
def send_email(to_email, subject, body):
    """发送邮件通知用户授权码"""
    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        SMTP_SERVER = os.environ.get("SMTP_SERVER", "")
        SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
        SMTP_USER = os.environ.get("SMTP_USER", "")
        SMTP_PASS = os.environ.get("SMTP_PASS", "")
        
        if not SMTP_USER:
            print(f"[邮件] 未配置SMTP，跳过邮件发送 -> {to_email}: {subject}")
            return False
        
        msg = MIMEMultipart()
        msg['From'] = SMTP_USER
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'html', 'utf-8'))
        
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        print(f"[邮件] 发送成功 -> {to_email}")
        return True
    except Exception as e:
        print(f"[邮件] 发送失败 -> {to_email}: {e}")
        return False

# ========== TRC20 验证 ==========
def check_trc20_payment(txid, expected_amount=PRICE_USDT):
    """
    通过TronGrid API验证TRC20转账是否成功
    返回: (success, message)
    """
    try:
        # 先获取交易信息
        url = f"{TRONGRID_API}/v1/transactions/{txid}/info"
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            return False, "交易不存在或网络错误"
        
        data = r.json()
        if data.get("ret", [{}])[0].get("contractRet") != "SUCCESS":
            return False, "交易未成功"
        
        # 获取交易详情（含TRC20转账）
        detail_url = f"{TRONGRID_API}/v1/transactions/{txid}/events"
        r2 = requests.get(detail_url, timeout=10)
        if r2.status_code != 200:
            return False, "无法获取交易详情"
        
        events = r2.json().get("data", [])
        
        for event in events:
            if event.get("type") == "Transfer" and event.get("contract_address") == "":
                # 过滤TRC20 USDT (空地址=Tron USDD/USDT)
                continue
            
            # 解析TRC20转账参数
            try:
                result_data = event.get("result", {})
                to_addr = result_data.get("to_address", "")
                amount_raw = result_data.get("value", "0")
                
                # 将TRC20精度转换 (USDT精度=6)
                amount = int(amount_raw) / 1e6
                
                # 检查目标地址和金额
                if to_addr == CHECK_ADDRESS and amount >= expected_amount:
                    return True, f"✅ 收到 {amount} USDT，转账成功！"
            except:
                continue
        
        return False, f"未检测到向 {CHECK_ADDRESS} 的 {expected_amount} USDT 转账"
        
    except Exception as e:
        return False, f"验证异常: {e}"

# ========== 生成授权码 ==========
def auto_generate_license(email):
    """付款验证成功后，自动生成授权码"""
    db = load_db()
    
    # 检查是否已有该邮箱的年订阅（未过期）
    now = datetime.now()
    for lic in db.get("licenses", []):
        if lic.get("email", "").lower() == email.lower() and lic.get("plan") == "yearly":
            if lic.get("active") and datetime.fromisoformat(lic["expires"]) > now:
                key = lic["key"]
                return key, "该邮箱已有有效年订阅"
    
    # 生成新授权码
    key = generate_key()
    expires = (now + timedelta(days=LICENSE_DAYS)).isoformat()
    
    lic_info = {
        "key": key,
        "email": email,
        "plan": "yearly",
        "price_paid": PRICE_USDT,
        "created": now.isoformat(),
        "expires": expires,
        "active": True
    }
    db.setdefault("licenses", []).append(lic_info)
    save_db(db)
    
    return key, expires[:10]

# ========== 页面 ==========
PAYMENT_PAGE = """
<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SpeedClaw Bot20× - 订阅授权</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, 'PingFang SC', sans-serif; background: #0a0a0f; color: #e0e0e0; min-height: 100vh; display: flex; align-items: center; justify-content: center; }
  .container { background: #111; border: 1px solid #333; border-radius: 16px; padding: 40px; max-width: 520px; width: 95%; }
  .logo { text-align: center; margin-bottom: 30px; }
  .logo h1 { font-size: 28px; color: #f7931a; margin-bottom: 6px; }
  .logo p { color: #888; font-size: 14px; }
  .price-tag { background: linear-gradient(135deg, #f7931a, #e6760a); color: #fff; text-align: center; padding: 20px; border-radius: 12px; margin-bottom: 28px; }
  .price-tag .amount { font-size: 42px; font-weight: 700; }
  .price-tag .period { font-size: 14px; opacity: 0.85; }
  .form-group { margin-bottom: 18px; }
  label { display: block; font-size: 13px; color: #888; margin-bottom: 6px; }
  input { width: 100%; padding: 12px 14px; background: #1a1a2e; border: 1px solid #333; border-radius: 8px; color: #fff; font-size: 15px; outline: none; transition: border 0.2s; }
  input:focus { border-color: #f7931a; }
  .btn { width: 100%; padding: 14px; background: #f7931a; color: #fff; border: none; border-radius: 8px; font-size: 16px; font-weight: 600; cursor: pointer; margin-top: 8px; }
  .btn:hover { background: #e6760a; }
  .btn:disabled { background: #555; cursor: not-allowed; }
  .address-box { background: #1a1a2e; border: 1px solid #f7931a44; border-radius: 8px; padding: 14px; margin: 18px 0; word-break: break-all; font-size: 13px; color: #aaa; }
  .address-box .label { color: #f7931a; font-weight: 600; margin-bottom: 6px; }
  .address-box .addr { color: #4fc3f7; font-family: monospace; font-size: 14px; }
  .copy-btn { background: #333; color: #aaa; border: none; padding: 4px 12px; border-radius: 4px; font-size: 12px; cursor: pointer; margin-top: 6px; }
  .copy-btn:hover { background: #444; }
  .result { background: #0d1f0d; border: 1px solid #4caf50; border-radius: 12px; padding: 24px; text-align: center; margin-top: 20px; }
  .result .key { background: #1a1a2e; padding: 14px; border-radius: 8px; font-family: monospace; font-size: 20px; color: #4fc3f7; letter-spacing: 2px; margin: 12px 0; word-break: break-all; }
  .result .desc { color: #888; font-size: 13px; line-height: 1.6; }
  .error { background: #1f0d0d; border: 1px solid #f44336; border-radius: 8px; padding: 12px; color: #f44336; font-size: 14px; margin-top: 10px; }
  .steps { background: #1a1a2e; border-radius: 8px; padding: 16px; margin: 18px 0; }
  .steps .step { display: flex; align-items: flex-start; margin-bottom: 12px; font-size: 14px; color: #bbb; }
  .steps .step-num { background: #f7931a; color: #fff; width: 22px; height: 22px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 700; flex-shrink: 0; margin-right: 10px; }
  .steps .step:last-child { margin-bottom: 0; }
  .txid-group { display: none; }
  .txid-group.show { display: block; }
  .spinner { display: inline-block; width: 18px; height: 18px; border: 2px solid #333; border-top-color: #f7931a; border-radius: 50%; animation: spin 0.8s linear infinite; vertical-align: middle; }
  @keyframes spin { to { transform: rotate(360deg); } }
</style>
</head>
<body>
<div class="container">
  <div class="logo">
    <h1>🦞 SpeedClaw Bot20×</h1>
    <p>订阅授权 · 全自动发货</p>
  </div>

  <div class="price-tag">
    <div class="amount">$399.9 <span style="font-size:18px">USDT</span></div>
    <div class="period">年订阅 · 永久使用 · 随时下载更新</div>
  </div>

  <div class="steps">
    <div class="step"><span class="step-num">1</span> 输入邮箱，点击"生成收款地址"</div>
    <div class="step"><span class="step-num">2</span> 向下方地址转账 <b style="color:#f7931a">399.9 USDT</b>（TRC20网络）</div>
    <div class="step"><span class="step-num">3</span> 转账后复制交易哈希(TxHash)，粘贴到下方验证</div>
    <div class="step"><span class="step-num">4</span> 授权码自动生成，页面直接显示</div>
  </div>

  {% if error %}<div class="error">{{ error }}</div>{% endif %}

  <form method="post" action="/create" id="createForm">
    <div class="form-group">
      <label>📧 您的邮箱地址</label>
      <input type="email" name="email" placeholder="license@email.com" required value="{{ email or '' }}">
    </div>
    <button type="submit" class="btn" id="createBtn">生成收款地址</button>
  </form>

  {% if payment_address %}
  <div class="address-box" id="addressBox">
    <div class="label">📤 向此地址转账</div>
    <div class="addr">{{ payment_address }}</div>
    <button class="copy-btn" onclick="copyAddr()">复制地址</button>
    <div style="margin-top:10px; font-size:12px; color:#888;">
     金额: <b style="color:#f7931a">{{ price }} USDT</b> · 网络: <b>TRC20 (TRON)</b>
    </div>
  </div>

  <form method="post" action="/verify" id="verifyForm" class="txid-group show">
    <div class="form-group">
      <label>🔗 交易哈希 (TxHash)</label>
      <input type="text" name="txid" placeholder="粘贴您的USDT转账TxHash" required>
      <input type="hidden" name="email" value="{{ email }}">
    </div>
    <button type="submit" class="btn" id="verifyBtn">验证并获取授权码</button>
  </form>
  {% endif %}

  {% if license_key %}
  <div class="result">
    <div style="font-size:16px; color:#4caf50; margin-bottom:8px;">🎉 付款成功！您的授权码：</div>
    <div class="key">{{ license_key }}</div>
    <div class="desc">
      到期时间：{{ expires_date }}<br>
      授权邮箱：{{ email }}<br>
      <br>
      <b>下载链接：</b><br>
      <a href="https://github.com/okbabybo/SpeedClaw-Bot20x-Skill" style="color:#4fc3f7;">https://github.com/okbabybo/SpeedClaw-Bot20x-Skill</a>
    </div>
  </div>
  {% endif %}
</div>

<script>
function copyAddr() {
  navigator.clipboard.writeText("{{ payment_address }}").then(() => {
    alert("地址已复制！");
  });
}
</script>
</body>
</html>
"""

# ========== 路由 ==========
@app.route("/")
def index():
    return render_template_string(PAYMENT_PAGE)

@app.route("/create", methods=["POST"])
def create():
    email = request.form.get("email", "").strip()
    if not email or "@" not in email:
        return render_template_string(PAYMENT_PAGE, error="请输入有效的邮箱地址")
    return render_template_string(PAYMENT_PAGE, email=email, payment_address=TRC20_ADDRESS, price=PRICE_USDT)

@app.route("/verify", methods=["POST"])
def verify():
    email = request.form.get("email", "").strip()
    txid = request.form.get("txid", "").strip()
    
    if not txid:
        return render_template_string(PAYMENT_PAGE, email=email, payment_address=TRC20_ADDRESS, price=PRICE_USDT, error="请输入交易哈希")
    
    ok, msg = check_trc20_payment(txid, PRICE_USDT)
    
    if ok:
        key, result = auto_generate_license(email)
        if "已有" in result:
            expires = result
            send_email(email, "SpeedClaw Bot20× 订阅查询", f"<p>您的邮箱已有有效订阅，授权码：<b>{key}</b></p><p>到期：{expires}</p>")
        else:
            expires = result
            body = f"""
            <h2>🦞 SpeedClaw Bot20× 授权码</h2>
            <p>感谢您的订阅！</p>
            <p><b>授权码：{key}</b></p>
            <p>到期时间：{expires}</p>
            <p>下载：<a href="https://github.com/okbabybo/SpeedClaw-Bot20x-Skill">GitHub 仓库</a></p>
            """
            send_email(email, "您的 SpeedClaw Bot20× 授权码", body)
        
        return render_template_string(PAYMENT_PAGE, email=email, license_key=key, expires_date=expires)
    else:
        return render_template_string(PAYMENT_PAGE, email=email, payment_address=TRC20_ADDRESS, price=PRICE_USDT, error=msg)

@app.route("/api/check", methods=["GET"])
def api_check():
    """API查询授权码状态"""
    key = request.args.get("key", "").strip()
    if not key:
        return jsonify({"error": "缺少key参数"})
    
    db = load_db()
    for lic in db.get("licenses", []):
        if lic.get("key") == key:
            if not lic.get("active"):
                return jsonify({"valid": False, "msg": "授权码已被禁用"})
            expires = datetime.fromisoformat(lic["expires"])
            if datetime.now() > expires:
                return jsonify({"valid": False, "msg": "授权码已过期"})
            return jsonify({"valid": True, "email": lic.get("email"), "expires": lic["expires"][:10]})
    return jsonify({"valid": False, "msg": "授权码无效"})

@app.route("/api/status", methods=["GET"])
def api_status():
    """服务状态"""
    return jsonify({"status": "ok", "price": PRICE_USDT, "currency": "USDT", "plan": "yearly"})

if __name__ == "__main__":
    print(f"SpeedClaw 收款系统启动 | 年订阅 ${PRICE_USDT} USDT")
    print(f"收款地址: {TRC20_ADDRESS}")
    app.run(host="0.0.0.0", port=5000, debug=False)
