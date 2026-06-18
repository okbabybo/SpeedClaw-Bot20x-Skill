#!/usr/bin/env python3
"""
SpeedClaw Bot20× - 订阅页面
"""

from flask import Flask, render_template_string
import sys, os

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False

CONTACT = "@Okbabybo"
GITHUB = "https://github.com/okbabybo/SpeedClaw-Bot20x-Skill"
PRICE = "399.9 USDT / 年"
WALLET = "0x344FfCe2f7B8f580D4e054F7213cb231CD15c3cd"

PAGE = """
<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SpeedClaw Bot20× - 订阅</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, 'PingFang SC', sans-serif; background: #0a0a0f; color: #e0e0e0; min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 20px; }
  .card { background: #111; border: 1px solid #333; border-radius: 20px; padding: 48px 40px; max-width: 520px; width: 100%; text-align: center; }
  .logo { font-size: 36px; margin-bottom: 8px; }
  .logo h1 { font-size: 28px; color: #f7931a; }
  .logo p { color: #666; font-size: 14px; margin-top: 4px; }
  .divider { border: none; border-top: 1px solid #333; margin: 30px 0; }
  .github-box { background: #1a1a2e; border: 2px solid #f7931a; border-radius: 14px; padding: 24px; margin-bottom: 24px; }
  .github-box .label { color: #888; font-size: 13px; margin-bottom: 8px; }
  .github-box a { color: #4fc3f7; font-size: 15px; text-decoration: none; word-break: break-all; }
  .github-box a:hover { color: #81d4fa; }
  .features { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 24px; }
  .feature { background: #1a1a2e; padding: 14px; border-radius: 8px; text-align: center; }
  .feature .val { font-size: 20px; font-weight: 700; color: #f7931a; }
  .feature .lab { font-size: 11px; color: #666; margin-top: 2px; }
  .strategy { background: #1a1a2e; border-radius: 12px; padding: 18px; margin-bottom: 24px; text-align: left; }
  .strategy ul { list-style: none; }
  .strategy li { color: #aaa; font-size: 13px; padding: 4px 0; }
  .strategy li::before { content: "✓ "; color: #4caf50; margin-right: 6px; }
  .price { background: linear-gradient(135deg, #f7931a, #e6760a); color: #fff; padding: 16px; border-radius: 12px; margin-bottom: 24px; }
  .price .amount { font-size: 32px; font-weight: 700; }
  .price .desc { font-size: 13px; opacity: 0.85; margin-top: 4px; }
  .contact { background: #1a1a2e; border: 1px solid #333; border-radius: 12px; padding: 24px; margin-bottom: 20px; }
  .contact h3 { color: #fff; margin-bottom: 10px; font-size: 15px; }
  .contact p { color: #888; font-size: 13px; line-height: 1.6; margin-bottom: 14px; }
  .contact .telegram { display: inline-block; background: #0088cc; color: #fff; padding: 12px 32px; border-radius: 8px; font-size: 16px; font-weight: 600; text-decoration: none; }
  .contact .telegram:hover { background: #0077b3; }
  .note { color: #555; font-size: 12px; line-height: 1.5; }
  .step-box { background: #1a1a2e; border-radius: 12px; padding: 16px; margin-bottom: 20px; text-align: left; }
  .step-box h4 { color: #f7931a; font-size: 13px; margin-bottom: 10px; }
  .step { display: flex; align-items: center; margin-bottom: 8px; font-size: 13px; color: #aaa; }
  .step-num { background: #333; color: #f7931a; width: 22px; height: 22px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 700; margin-right: 10px; flex-shrink: 0; }
  .wallet-box { background: #0d2d1a; border: 2px solid #4caf50; border-radius: 14px; padding: 20px; margin-bottom: 20px; }
  .wallet-box .label { color: #4caf50; font-size: 13px; font-weight: 600; margin-bottom: 8px; }
  .wallet-box .addr { color: #fff; font-family: monospace; font-size: 13px; background: #0a1f10; padding: 10px; border-radius: 8px; word-break: break-all; margin-bottom: 8px; }
  .wallet-box .network { color: #888; font-size: 12px; }
  .wallet-box .copy-btn { background: #4caf50; color: #fff; border: none; padding: 6px 16px; border-radius: 6px; font-size: 13px; cursor: pointer; }
  .wallet-box .copy-btn:hover { background: #45a049; }
</style>
</head>
<body>
<div class="card">
  <div class="logo">
    <div>🦞</div>
    <h1>SpeedClaw Bot20×</h1>
    <p>BTC + ETH 永续合约量化交易机器人 · 20x杠杆</p>
  </div>

  <hr class="divider">

  <div class="features">
    <div class="feature"><div class="val">20x</div><div class="lab">杠杆</div></div>
    <div class="feature"><div class="val">87</div><div class="lab">策略评分</div></div>
    <div class="feature"><div class="val">100%</div><div class="lab">胜率</div></div>
    <div class="feature"><div class="val">4H+1H</div><div class="lab">多周期确认</div></div>
  </div>

  <div class="github-box">
    <div class="label">📦 GitHub 订阅地址</div>
    <a href="https://github.com/okbabybo/SpeedClaw-Bot20x-Skill" target="_blank">github.com/okbabybo/SpeedClaw-Bot20x-Skill</a>
  </div>

  <div class="price">
    <div class="amount">$399.9 USDT / 年</div>
    <div class="desc">订阅后获取授权码 + 完整策略包</div>
  </div>

  <div class="wallet-box">
    <div class="label">💰 BSC 收款地址（转账到此地址）</div>
    <div class="addr" id="walletAddr">{{ WALLET }}</div>
    <div class="network">网络：BSC (BEP20) · 只收 USDT</div>
    <button class="copy-btn" onclick="copyWallet()">📋 复制地址</button>
  </div>

  <div class="step-box">
    <h4>📋 订阅流程</h4>
    <div class="step"><span class="step-num">1</span> 复制上方收款地址</div>
    <div class="step"><span class="step-num">2</span> 向该地址转账 <b style="color:#f7931a">399.9 USDT</b>（BSC网络）</div>
    <div class="step"><span class="step-num">3</span> 联系 Telegram 发送转账截图</div>
    <div class="step"><span class="step-num">4</span> 收到授权码 + GitHub 下载机器人</div>
  </div>

  <div class="contact">
    <h3>💬 联系订阅</h3>
    <p>复制下方 Telegram 直接联系我</p>
    <a href="https://t.me/Okbabybo" class="telegram" target="_blank">@Okbabybo</a>
  </div>

  <p class="note">
    支持：币安 USDT-M 永续合约（BTC / ETH）<br>
    网络：BSC (BEP20)
  </p>
</div>

<script>
function copyWallet() {
  navigator.clipboard.writeText("{{ WALLET }}").then(() => {
    alert("收款地址已复制！");
  });
}
</script>
</div>
</body>
</html>
"""

@app.route("/")
def index():
    return redirect("https://okbabybo.github.io/SpeedClaw-Bot20x-Skill/")

@app.route("/api/status")
def api_status():
    return {
        "status": "ok",
        "price": PRICE,
        "contact": CONTACT,
        "github": GITHUB
    }

if __name__ == "__main__":
    print(f"SpeedClaw 订阅页面启动 | 联系: {CONTACT}")
    app.run(host="0.0.0.0", port=5000, debug=False)
