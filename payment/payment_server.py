#!/usr/bin/env python3
"""
speedClaw Bot20x - 自动订阅系统
用户扫码付款 → 系统自动监控 → 自动显示授权码
"""

from flask import Flask, render_template_string, jsonify, request
import json
import time
import threading
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
        "label": "$9.9 / 月"
    },
    "quarterly": {
        "name": "季度订阅",
        "price": 24.9,
        "days": 90,
        "address": "0x6CDD7d0e7865f6DaDB9178dd114890ABD5d5323b",
        "label": "$24.9 / 季度"
    },
    "yearly": {
        "name": "年度订阅",
        "price": 79.9,
        "days": 365,
        "address": "0x352f5Cb1CA167500D27741676ab9efA4B07D3D30",
        "label": "$79.9 / 年"
    }
}

LICENSE_DB_FILE = "/root/.openclaw/workspace/speedClaw-Bot20x-Skill/.license_db.json"
pending_payments = {}  # tier -> {address, amount, start_time}
detected_payments = {}  # tx_hash -> license_key

def load_license_db():
    try:
        with open(LICENSE_DB_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_license_db(db):
    with open(LICENSE_DB_FILE, 'w') as f:
        json.dump(db, f, indent=2)

def generate_license_key():
    import secrets
    return "SCB-" + secrets.token_hex(4).upper()

def check_address_transactions(address, min_amount=1):
    """检查地址是否有新转账入账"""
    try:
        w3 = Web3(Web3.HTTPProvider(BSC_RPC))
        address = Web3.to_checksum_address(address)
        
        # 获取最近20个交易
        current_balance = w3.eth.get_balance(address)
        
        # 使用eth_getLogs查询最近12小时内的交易
        from_block = w3.eth.block_number - 5000  # 大约2小时内
        
        logs = w3.eth.get_logs({
            'fromBlock': max(0, from_block),
            'toBlock': 'latest',
            'address': address,
            'topics': [
                '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef',  # Transfer event
            ]
        })
        
        txs = []
        for log in logs:
            try:
                # 解析 Transfer event (Transfer(address from, address to, uint256 value))
                # topics[0] = Transfer event hash
                # topics[1] = from address
                # topics[2] = to address
                # topics[3] = value (amount)
                
                if len(log.topics) >= 3:
                    from_addr = "0x" + log.topics[1].hex()[-40:]
                    to_addr = "0x" + log.topics[2].hex()[-40:]
                    
                    # 只关心转入当前地址的交易
                    if to_addr.lower() == address.lower():
                        amount = int(log.data.hex(), 16) / 1e18 # USDT decimals
                        tx_hash = log.transactionHash.hex()
                        
                        txs.append({
                            'hash': tx_hash,
                            'from': from_addr,
                            'amount': amount,
                            'block': log.blockNumber,
                            'timestamp': log.blockNumber * 3  # BSC block time approx
                        })
            except Exception as e:
                continue
        
        return txs
    except Exception as e:
        print(f"检查交易失败: {e}")
        return []

def monitor_address(tier_key):
    """后台监控线程"""
    tier = TIERS[tier_key]
    address = tier['address']
    min_amount = tier['price'] * 0.9  # 允许10%误差
    
    known_txs = set()
    check_interval = 10  # 每10秒检查一次
    
    while True:
        try:
            txs = check_address_transactions(address)
            
            for tx in txs:
                tx_hash = tx['hash']
                amount = tx['amount']
                
                if tx_hash not in known_txs and amount >= min_amount:
                    known_txs.add(tx_hash)
                    
                    # 发现有效转账！生成授权码
                    wallet_address = tx.get('from', 'unknown')
                    
                    # 检查是否已生成过这个tx的授权码
                    db = load_license_db()
                    if tx_hash not in db.get('transactions', {}):
                        license_key = generate_license_key()
                        expiry = int(time.time()) + tier['days'] * 86400
                        
                        #记录到数据库
                        db.setdefault('transactions', {})[tx_hash] = {
                            'license_key': license_key,
                            'tier': tier_key,
                            'wallet': wallet_address,
                            'amount': amount,
                            'created': int(time.time()),
                            'expiry': expiry,
                            'used': False
                        }
                        save_license_db(db)
                        
                        print(f"✅ 检测到付款！TX: {tx_hash[:10]}...金额: ${amount} 生成授权码: {license_key}")
            
        except Exception as e:
            print(f"监控异常: {e}")
        
        time.sleep(check_interval)

def start_monitoring():
    """启动后台监控"""
    for tier_key in TIERS.keys():
        t = threading.Thread(target=monitor_address, args=(tier_key,), daemon=True)
        t.start()
        print(f"启动监控线程: {tier_key}")

# ========== 网页路由 ==========
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>speedClaw Bot20x - 自动订阅</title>
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
.tier:hover {
  border-color: #00d4aa;
  transform: translateY(-2px);
}
.tier.selected {
  border-color: #00d4aa;
  background: rgba(0,212,170,0.1);
}
.tier-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.tier-name { font-size: 18px; font-weight: 600; }
.tier-price { font-size: 24px; color: #00d4aa; font-weight: 700; }
.tier-address {
  background: rgba(0,0,0,0.3);
  padding: 10px;
  border-radius: 8px;
  font-size: 12px;
  color: #9ca3af;
  word-break: break-all;
  margin-bottom: 12px;
}
.tier-days { color: #6b7280; font-size: 13px; }

.qr-section {
  background: rgba(255,255,255,0.05);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 12px;
  padding: 24px;
  margin: 20px 0;
  display: none;
  text-align: center;
}
.qr-section.active { display: block; }
.qr-title { font-size: 18px; margin-bottom: 16px; color: #00d4aa; }
.qr-code {
  background: white;
  padding: 16px;
  border-radius: 12px;
  display: inline-block;
  margin: 16px 0;
}
.qr-code img { width: 200px; height: 200px; display: block; }
.copy-addr {
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
.copy-addr:hover { background: #00e4bb; }

.wallet-section {
  margin: 20px 0;
  display: none;
}
.wallet-section.active { display: block; }
.wallet-section label {
  display: block;
  margin-bottom: 8px;
  color: #9ca3af;
  font-size: 14px;
}
.wallet-section input {
  width: 100%;
  padding: 14px;
  border: 1px solid rgba(255,255,255,0.2);
  border-radius: 8px;
  background: rgba(255,255,255,0.05);
  color: #e0e6ed;
  font-size: 16px;
}
.wallet-section input:focus {
  outline: none;
  border-color: #00d4aa;
}

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
.license-key {
  background: rgba(0,0,0,0.3);
  padding: 16px24px;
  border-radius: 8px;
  font-size: 20px;
  font-weight: 700;
  color: #00d4aa;
  letter-spacing: 2px;
  margin: 16px 0;
  word-break: break-all;
}
.result-note { color: #9ca3af; font-size: 13px; margin-top: 12px; }

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
    <p>自动订阅系统 - 扫码支付即可使用</p>
  </div>

  <div class="tiers">
    {% for tier_key, tier in tiers.items() %}
    <div class="tier" data-tier="{{ tier_key }}">
      <div class="tier-header">
        <span class="tier-name">{{ tier.name }}</span>
        <span class="tier-price">{{ tier.label }}</span>
      </div>
      <div class="tier-address">{{ tier.address }}</div>
      <div class="tier-days">有效期：{{ tier.days }} 天</div>
    </div>
    {% endfor %}
  </div>

  <div class="qr-section" id="qrSection">
    <div class="qr-title">📱 扫码支付</div>
    <div class="qr-code">
      <img id="qrImage" src="" alt="QR Code">
    </div>
    <div style="color:#9ca3af;font-size:14px;margin:12px 0;">
     收款地址：<span id="payAddr" style="font-size:12px;"></span>
    </div>
    <button class="copy-addr" onclick="copyAddress()">📋 复制地址</button>
  </div>

  <div class="wallet-section" id="walletSection">
    <label>请输入您的钱包地址（用于关联授权码）：</label>
    <input type="text" id="walletInput" placeholder="0x...">
    <button class="verify-btn" id="verifyBtn" onclick="checkPayment()">🔍 检查支付 & 获取授权码</button>
  </div>

  <div class="waiting" id="waiting">
    <div class="spinner"></div>
    <div>检测交易中，请稍候...</div>
  </div>

  <div class="result" id="result">
    <div class="result-title">🎉 支付成功！</div>
    <div class="license-key" id="licenseKey"></div>
    <div class="result-note">
      授权码有效期已记录<br>
      请妥善保存授权码
    </div>
  </div>
</div>

<script>
const tiers = {{ tiers_json | safe }};
let selectedTier = null;

document.querySelectorAll('.tier').forEach(el => {
  el.addEventListener('click', () => {
    document.querySelectorAll('.tier').forEach(t => t.classList.remove('selected'));
    el.classList.add('selected');
    selectedTier = el.dataset.tier;
    
    const tier = tiers[selectedTier];
    document.getElementById('qrSection').classList.add('active');
    document.getElementById('walletSection').classList.add('active');
    document.getElementById('payAddr').textContent = tier.address;
    
    // 生成QR码
    document.getElementById('qrImage').src = 
      'https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=' + 
      encodeURIComponent(`tron:transfer?address=${tier.address}&amount=${tier.price}`);
    
    document.getElementById('result').classList.remove('active');
  });
});

function copyAddress() {
  if (selectedTier) {
    navigator.clipboard.writeText(tiers[selectedTier].address);
    alert('地址已复制！');
  }
}

function checkPayment() {
  const wallet = document.getElementById('walletInput').value.trim();
  if (!wallet) {
    alert('请输入钱包地址');
    return;
  }
  
  document.getElementById('waiting').classList.add('active');
  document.getElementById('verifyBtn').disabled = true;
  
  fetch('/api/check_payment', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      tier: selectedTier,
      wallet: wallet
    })
  })
  .then(r => r.json())
  .then(data => {
    document.getElementById('waiting').classList.remove('active');
    document.getElementById('verifyBtn').disabled = false;
    
    if (data.success) {
      document.getElementById('licenseKey').textContent = data.license_key;
      document.getElementById('result').classList.add('active');
    } else {
      alert(data.message || '未检测到支付，请稍候再试');
    }
  })
  .catch(e => {
    document.getElementById('waiting').classList.remove('active');
    document.getElementById('verifyBtn').disabled = false;
    alert('检查失败: ' + e.message);
  });
}
</script>
</body>
</html>
'''

@app.route('/')
def index():
    tiers_json = json.dumps(TIERS)
    return render_template_string(HTML_TEMPLATE, tiers=TIERS, tiers_json=tiers_json)

@app.route('/api/check_payment', methods=['POST'])
def api_check_payment():
    data = request.json
    tier_key = data.get('tier')
    wallet = data.get('wallet', '').lower()
    
    if not tier_key or tier_key not in TIERS:
        return jsonify({'success': False, 'message': '无效的套餐'})
    
    tier = TIERS[tier_key]
    min_amount = tier['price'] * 0.9
    
    # 检查该地址的转账
    txs = check_address_transactions(tier['address'])
    
    for tx in txs:
        if tx['amount'] >= min_amount:
            tx_hash = tx['hash']
            
            # 检查数据库
            db = load_license_db()
            if tx_hash in db.get('transactions', {}):
                record = db['transactions'][tx_hash]
                return jsonify({
                    'success': True,
                    'license_key': record['license_key'],
                    'message': '授权码获取成功'
                })
            
            # 没找到？可能监控还没更新，手动检查
            # 允许用户主动查询
            if wallet and tx.get('from', '').lower() == wallet:
                # 生成授权码
                license_key = generate_license_key()
                expiry = int(time.time()) + tier['days'] * 86400
                
                db.setdefault('transactions', {})[tx_hash] = {
                    'license_key': license_key,
                    'tier': tier_key,
                    'wallet': wallet,
                    'amount': tx['amount'],
                    'created': int(time.time()),
                    'expiry': expiry,
                    'used': False
                }
                save_license_db(db)
                
                return jsonify({
                    'success': True,
                    'license_key': license_key,
                    'message': '授权码获取成功'
                })
    
    return jsonify({'success': False, 'message': '未检测到支付，请确保已转账且金额正确'})

@app.route('/api/status')
def api_status():
    return jsonify({'status': 'ok', 'tiers': list(TIERS.keys())})

if __name__ == '__main__':
    print("🚀 启动自动订阅系统...")
    start_monitoring()
    print(f"📡 服务端口: {PORT}")
    app.run(host='0.0.0.0', port=PORT, debug=False)