#!/usr/bin/env python3
"""
speedClaw Bot20x - 付款验证+文件下载系统
用户付款后输入TX哈希 → 验证通过 → 显示下载链接
"""

from flask import Flask, render_template_string, jsonify, request
import json
import time
from web3 import Web3

app = Flask(__name__)

# ========== 配置 ==========
BSC_RPC = "https://bsc-dataseed.binance.org/"
PORT = 80

# 三个套餐的收款地址
TIERS = {
    "monthly": {
        "name": "月度订阅",
        "price": 9.9,
        "days": 30,
        "address": "0xFb4f3eFA1FeB256131FEEf2E2Ca4B2F2e9b22d6E",
        "label": "$9.9 / 月",
        "files": [
            {"name": "speedClaw-Bot20x-Skill.zip", "desc": "完整策略文件"},
        ]
    },
    "quarterly": {
        "name": "季度订阅", 
        "price": 24.9,
        "days": 90,
        "address": "0x6CDD7d0e7865f6DaDB9178dd114890ABD5d5323b",
        "label": "$24.9 / 季度",
        "files": [
            {"name": "speedClaw-Bot20x-Skill.zip", "desc": "完整策略文件"},
        ]
    },
    "yearly": {
        "name": "年度订阅",
        "price": 79.9,
        "days": 365,
        "address": "0x352f5Cb1CA167500D27741676ab9efA4B07D3D30",
        "label": "$79.9 / 年",
        "files": [
            {"name": "speedClaw-Bot20x-Skill.zip", "desc": "完整策略文件（含VIP专属参数）"},
        ]
    }
}

PAID_TXS_FILE = "/root/.openclaw/workspace/speedClaw-Bot20x-Skill/.paid_txs.json"
GITHUB_REPO = "https://github.com/okbabybo/SpeedClaw-Bot20x-Skill/archive/refs/heads/main.zip"

def load_paid_txs():
    try:
        with open(PAID_TXS_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_paid_txs(data):
    with open(PAID_TXS_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def verify_tx_on_bsc(tx_hash, expected_address, min_amount):
    """验证BSC链上TX"""
    try:
        w3 = Web3(Web3.HTTPProvider(BSC_RPC))
        
        # 获取交易收据
        receipt = w3.eth.get_transaction_receipt(tx_hash)
        if not receipt:
            return None
        
        # 检查交易状态
        if receipt['status'] != 1:
            return None
        
        # 解析logs寻找USDT Transfer事件
        for log in receipt['logs']:
            # 跳过新币安的USDTSmartChain事件（不是我们要的）
            if len(log['topics']) < 3:
                continue
                
            try:
                # Transfer(address from, address to, uint256 value)
                from_addr = "0x" + log['topics'][1].hex()[-40:]
                to_addr = "0x" + log['topics'][2].hex()[-40:]
                
                # 检查是否转入目标地址
                if to_addr.lower() == expected_address.lower():
                    # USDT代币
                    if log['address'].lower() in ['0x55d398326f99059ff775485246999027b3197955', '0xe9e7cea694dedb6a0c89c92e2f0a1b2b5e0c3d4', '0x7ef95a0eee953a1a23d4b413aec8e3f2e3ee0a3c']:
                        # USDT代币转账
                        amount = int(log['data'].hex() or '0x0', 16) / 1e18
                        if amount >= min_amount:
                            return {'from': from_addr, 'amount': amount}
            except:
                continue
        
        return None
        
    except Exception as e:
        print(f"验证TX失败: {e}")
        return None

# ========== 网页 ==========
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>speedClaw Bot20x - 订阅下载</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: linear-gradient(135deg, #0a0e17 0%, #1a1f2e 100%);
  min-height: 100vh;
  color: #e0e6ed;
  padding: 20px;
}
.container { max-width: 700px; margin: 0 auto; }
.header {
  text-align: center;
  padding: 30px 0;
}
.header h1 { color: #00d4aa; font-size: 28px; margin-bottom: 8px; }
.header p { color: #6b7280; font-size: 14px; }

.tiers {
  display: grid;
  gap: 16px;
  margin: 30px 0;
}
.tier {
  background: rgba(255,255,255,0.05);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 12px;
  padding: 20px;
  cursor: pointer;
  transition: all 0.3s;
}
.tier:hover { border-color: #00d4aa; transform: translateY(-2px); }
.tier.selected { border-color: #00d4aa; background: rgba(0,212,170,0.1); }
.tier-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.tier-name { font-size: 18px; font-weight: 600; }
.tier-price { font-size: 24px; color: #00d4aa; font-weight: 700; }
.tier-address {
  background: rgba(0,0,0,0.3);
  padding: 10px;
  border-radius: 8px;
  font-size: 12px;
  color: #9ca3af;
  word-break: break-all;
  margin: 12px 0;
}

.pay-section {
  background: rgba(255,255,255,0.05);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 12px;
  padding: 24px;
  margin: 20px 0;
  display: none;
}
.pay-section.active { display: block; }
.pay-title { font-size: 18px; margin-bottom: 16px; color: #00d4aa; }

.copy-btn {
  background: #00d4aa;
  color: #0a0e17;
  border: none;
  padding: 12px 24px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  margin-top: 12px;
}
.copy-btn:hover { background: #00e4bb; }

.verify-section {
  margin: 20px 0;
}
.verify-section label {
  display: block;
  margin-bottom: 8px;
  color: #9ca3af;
  font-size: 14px;
}
.verify-section input {
  width: 100%;
  padding: 14px;
  border: 1px solid rgba(255,255,255,0.2);
  border-radius: 8px;
  background: rgba(255,255,255,0.05);
  color: #e0e6ed;
  font-size: 14px;
  font-family: monospace;
}
.verify-section input:focus { outline: none; border-color: #00d4aa; }

.verify-btn {
  width: 100%;
  background: #00d4aa;
  color: #0a0e17;
  border: none;
  padding: 16px;
  border-radius: 8px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  margin-top: 16px;
}
.verify-btn:hover { background: #00e4bb; }
.verify-btn:disabled { background: #4b5563; cursor: not-allowed; }

.result {
  background: rgba(0,212,170,0.15);
  border: 2px solid #00d4aa;
  border-radius: 12px;
  padding: 24px;
  margin: 20px 0;
  text-align: center;
  display: none;
}
.result.active { display: block; }
.result-title { color: #00d4aa; font-size: 18px; margin-bottom: 16px; }
.download-links { margin: 16px 0; }
.download-link {
  display: block;
  background: rgba(0,0,0,0.3);
  padding: 16px;
  border-radius: 8px;
  margin: 8px 0;
  color: #00d4aa;
  text-decoration: none;
  font-size: 14px;
}
.download-link:hover { background: rgba(0,212,170,0.2); }
.download-link span { display: block; color: #9ca3af; font-size: 12px; margin-top: 4px; }

.waiting {
  text-align: center;
  padding: 30px;
  color: #9ca3af;
  display: none;
}
.waiting.active { display: block; }
.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid rgba(255,255,255,0.1);
  border-top-color: #00d4aa;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin: 0 auto 16px;
}
@keyframes spin { to { transform: rotate(360deg); } }

.error {
  background: rgba(239,68,68,0.15);
  border: 1px solid #ef4444;
  border-radius: 8px;
  padding: 12px;
  margin: 12px 0;
  color: #ef4444;
  font-size: 14px;
  display: none;
}
.error.active { display: block; }

.footer {
  text-align: center;
  margin-top: 40px;
  color: #4b5563;
  font-size: 12px;
}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>🦞 speedClaw Bot20x</h1>
    <p>付款后立即下载完整策略文件</p>
  </div>

  <div class="tiers">
    {% for tier_key, tier in tiers.items() %}
    <div class="tier" data-tier="{{ tier_key }}" onclick="selectTier('{{ tier_key }}')">
      <div class="tier-header">
        <span class="tier-name">{{ tier.name }}</span>
        <span class="tier-price">{{ tier.label }}</span>
      </div>
      <div style="color:#6b7280;font-size:13px;">{{ tier.days }}天有效期</div>
      <div class="tier-address">{{ tier.address }}</div>
    </div>
    {% endfor %}
  </div>

  <div class="pay-section" id="paySection">
    <div class="pay-title">📋 向以下地址转账 {{ selected_price }}</div>
    <div style="background:rgba(0,0,0,0.3);padding:16px;border-radius:8px;word-break:break-all;font-size:14px;" id="payAddress"></div>
    <button class="copy-btn" onclick="copyAddress()">📋 复制地址</button>
    
    <div class="verify-section" style="margin-top:24px;">
      <label>粘贴转账交易的 TX 哈希：</label>
      <input type="text" id="txHash" placeholder="0x...">
      <div class="error" id="errorMsg"></div>
      <button class="verify-btn" id="verifyBtn" onclick="verifyPayment()">🔍 验证支付 & 下载文件</button>
    </div>
  </div>

  <div class="waiting" id="waiting">
    <div class="spinner"></div>
    <div>验证中，请稍候...</div>
  </div>

  <div class="result" id="result">
    <div class="result-title">🎉 支付成功！</div>
    <div style="color:#9ca3af;font-size:14px;margin-bottom:16px;">以下是您的下载链接</div>
    <div class="download-links" id="downloadLinks"></div>
    <div style="color:#6b7280;font-size:12px;margin-top:16px;">
      * 下载后请查看 README.md 开始使用<br>
      * 如有问题联系 Telegram @Okbabybo
    </div>
  </div>
</div>

<script>
const tiers = {{ tiers_json | safe }};
let selectedTier = null;
let selectedPrice = 0;

function selectTier(key) {
  document.querySelectorAll('.tier').forEach(t => t.classList.remove('selected'));
  document.querySelector(`[data-tier="${key}"]`).classList.add('selected');
  selectedTier = key;
  selectedPrice = tiers[key].price;
  
  document.getElementById('payAddress').textContent = tiers[key].address;
  document.getElementById('paySection').classList.add('active');
  document.getElementById('result').classList.remove('active');
  document.getElementById('errorMsg').classList.remove('active');
}

function copyAddress() {
  navigator.clipboard.writeText(document.getElementById('payAddress').textContent);
  alert('地址已复制！');
}

function verifyPayment() {
  const txHash = document.getElementById('txHash').value.trim();
  if (!txHash || !txHash.startsWith('0x')) {
    showError('请输入有效的TX哈希（以0x开头）');
    return;
  }
  
  document.getElementById('waiting').classList.add('active');
  document.getElementById('verifyBtn').disabled = true;
  document.getElementById('errorMsg').classList.remove('active');
  
  fetch('/api/verify', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      tier: selectedTier,
      tx_hash: txHash
    })
  })
  .then(r => r.json())
  .then(data => {
    document.getElementById('waiting').classList.remove('active');
    document.getElementById('verifyBtn').disabled = false;
    
    if (data.success) {
      // 显示下载链接
      const linksHtml = data.files.map(f => 
        `<a href="${f.url}" class="download-link" target="_blank">
          📥 ${f.name}
          <span>${f.desc}</span>
        </a>`
      ).join('');
      document.getElementById('downloadLinks').innerHTML = linksHtml;
      document.getElementById('result').classList.add('active');
      document.getElementById('paySection').classList.remove('active');
    } else {
      showError(data.message || '验证失败，请检查TX哈希是否正确');
    }
  })
  .catch(e => {
    document.getElementById('waiting').classList.remove('active');
    document.getElementById('verifyBtn').disabled = false;
    showError('验证请求失败: ' + e.message);
  });
}

function showError(msg) {
  document.getElementById('errorMsg').textContent = msg;
  document.getElementById('errorMsg').classList.add('active');
}
</script>
</body>
</html>
'''

@app.route('/')
def index():
    tiers_json = json.dumps(TIERS)
    return render_template_string(HTML_TEMPLATE, tiers=TIERS, tiers_json=tiers_json)

@app.route('/api/verify', methods=['POST'])
def api_verify():
    data = request.json
    tier_key = data.get('tier')
    tx_hash = data.get('tx_hash', '').strip()
    
    if not tier_key or tier_key not in TIERS:
        return jsonify({'success': False, 'message': '无效的套餐'})
    
    if not tx_hash or not tx_hash.startswith('0x'):
        return jsonify({'success': False, 'message': '无效的TX哈希'})
    
    tier = TIERS[tier_key]
    min_amount = tier['price'] * 0.9  # 10%容差
    
    # 检查是否已验证过
    paid_txs = load_paid_txs()
    if tx_hash in paid_txs:
        # 已验证过，直接返回下载链接
        return jsonify({
            'success': True,
            'files': tier['files'],
            'message': '验证通过（已记录）'
        })
    
    # 验证TX
    result = verify_tx_on_bsc(tx_hash, tier['address'], min_amount)
    
    if result:
        # 记录已验证的TX
        paid_txs[tx_hash] = {
            'tier': tier_key,
            'amount': result['amount'],
            'time': int(time.time())
        }
        save_paid_txs(paid_txs)
        
        return jsonify({
            'success': True,
            'files': tier['files'],
            'message': '验证成功'
        })
    else:
        return jsonify({
            'success': False,
            'message': f'未检测到向 {tier["address"][:10]}... 转账 {tier["price"]} USDT 的交易'
        })

@app.route('/api/status')
def api_status():
    return jsonify({'status': 'ok', 'tiers': list(TIERS.keys())})

if __name__ == '__main__':
    print("🚀 启动付款验证系统...")
    print(f"📡 服务端口: {PORT}")
    app.run(host='0.0.0.0', port=PORT, debug=False)