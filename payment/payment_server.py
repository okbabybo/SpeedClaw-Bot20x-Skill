#!/usr/bin/env python3
"""
SpeedClaw Bot20× - 订阅页面
功能：展示策略 + 联系方式，简单直接
"""

from flask import Flask, render_template_string
import sys, os

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False

PRICE = "399.9 USDT"
CONTACT = "@Okbabybo"  # 你的Telegram

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
  .card { background: #111; border: 1px solid #333; border-radius: 20px; padding: 48px 40px; max-width: 480px; width: 100%; text-align: center; }
  .logo { font-size: 36px; margin-bottom: 8px; }
  .logo h1 { font-size: 28px; color: #f7931a; }
  .logo p { color: #666; font-size: 14px; margin-top: 4px; }
  .divider { border: none; border-top: 1px solid #333; margin: 30px 0; }
  .strategy { background: #1a1a2e; border-radius: 12px; padding: 20px; margin-bottom: 28px; text-align: left; }
  .strategy h3 { color: #f7931a; margin-bottom: 12px; font-size: 15px; }
  .strategy ul { list-style: none; }
  .strategy li { color: #aaa; font-size: 13px; padding: 5px 0; }
  .strategy li::before { content: "✓ "; color: #4caf50; margin-right: 6px; }
  .price { background: linear-gradient(135deg, #f7931a, #e6760a); color: #fff; padding: 18px; border-radius: 12px; margin-bottom: 28px; }
  .price .amount { font-size: 36px; font-weight: 700; }
  .price .desc { font-size: 13px; opacity: 0.85; margin-top: 4px; }
  .contact { background: #1a1a2e; border: 1px solid #333; border-radius: 12px; padding: 24px; }
  .contact h3 { color: #fff; margin-bottom: 10px; font-size: 15px; }
  .contact p { color: #888; font-size: 13px; line-height: 1.6; margin-bottom: 14px; }
  .contact .telegram { display: inline-block; background: #0088cc; color: #fff; padding: 12px 28px; border-radius: 8px; font-size: 15px; font-weight: 600; text-decoration: none; }
  .contact .telegram:hover { background: #0077b3; }
  .note { color: #555; font-size: 12px; margin-top: 20px; line-height: 1.5; }
  .features { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin: 18px 0; }
  .feature { background: #1a1a2e; padding: 12px; border-radius: 8px; text-align: center; }
  .feature .val { font-size: 20px; font-weight: 700; color: #f7931a; }
  .feature .lab { font-size: 11px; color: #666; margin-top: 2px; }
</style>
</head>
<body>
<div class="card">
  <div class="logo">
    <div>🦞</div>
    <h1>SpeedClaw Bot20×</h1>
    <p>加密货币量化交易机器人 · BTC + ETH 永续合约</p>
  </div>

  <hr class="divider">

  <div class="features">
    <div class="feature"><div class="val">20x</div><div class="lab">杠杆</div></div>
    <div class="feature"><div class="val">87</div><div class="lab">策略评分</div></div>
    <div class="feature"><div class="val">87%</div><div class="lab">胜率</div></div>
    <div class="feature"><div class="val">4H+1H</div><div class="lab">多周期确认</div></div>
  </div>

  <div class="strategy">
    <h3>策略特点</h3>
    <ul>
      <li>多周期EMA趋势确认（4H主趋势 + 1H确认 + 15M入场）</li>
      <li>StochRSI超买超卖信号，精准捕捉入场点</li>
      <li>趋势反转预警，实时监控持仓风险</li>
      <li>分批止盈（TP1 2%出半 + TP2 4%追踪）</li>
      <li>自动止损（2%固定）+ 连亏熔断保护</li>
      <li>多币种同时运行，独立计算仓位</li>
    </ul>
  </div>

  <div class="price">
    <div class="amount">$399.9 USDT / 年</div>
    <div class="desc">BSC (BEP20) 网络 · 永久使用 · 免费更新</div>
  </div>

  <div class="contact">
    <h3>📩 订阅方式</h3>
    <p>联系下方 Telegram 获取订阅方式和安装指引</p>
    <a href="https://t.me/Okbabybo" class="telegram" target="_blank">@Okbabybo</a>
  </div>

  <p class="note">
    付款后获得授权码 + 完整安装包 + 使用文档<br>
    支持：币安 USDT-M 永续合约（BTC / ETH）<br>
    机器人运行在云服务器，开箱即用，无需自建
  </p>
</div>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(PAGE)

@app.route("/api/status")
def api_status():
    return {"status": "ok", "price": PRICE, "contact": CONTACT}

if __name__ == "__main__":
    print(f"SpeedClaw 订阅页面启动 | 联系: {CONTACT}")
    app.run(host="0.0.0.0", port=5000, debug=False)
