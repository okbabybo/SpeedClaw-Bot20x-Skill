#!/usr/bin/env python3
"""bot20x Web控制台后端 API"""
from flask import Flask, jsonify, request
import requests, time, json, hmac, hashlib, subprocess
from datetime import datetime

app = Flask(__name__)

API_KEY = "QccKkNLbtV61rJpOms4h2E0RWoZMfMhG2ar3v9tueF5kbQ6KkN4sUf5CFLLkMhzx"
SECRET  = "Q549z4g3QlOnVs0PDSCzW6Xy2nVt9763DMqWo64MLLDoUeV8MigrUGUQn2nZTDuU"

def bn_get(endpoint, params=""):
    ts = str(int(time.time()*1000))
    p = f"{params}&timestamp={ts}" if params else f"timestamp={ts}"
    sig = hmac.new(SECRET.encode(), p.encode(), hashlib.sha256).hexdigest()
    return requests.get(f"https://fapi.binance.com{endpoint}?{p}&signature={sig}",
                       headers={"X-MBX-APIKEY": API_KEY}, timeout=10).json()

def bn_post(endpoint, params):
    ts = str(int(time.time()*1000))
    p = f"{params}&timestamp={ts}"
    sig = hmac.new(SECRET.encode(), p.encode(), hashlib.sha256).hexdigest()
    return requests.post(f"https://fapi.binance.com{endpoint}?{p}&signature={sig}",
                        headers={"X-MBX-APIKEY": API_KEY}, timeout=10).json()

def get_balance():
    try: return float(bn_get("/fapi/v2/account").get('availableBalance', 0))
    except: return 0

def get_positions(symbol):
    positions = {}
    try:
        for p in bn_get("/fapi/v2/positionRisk", f"symbol={symbol}"):
            amt = float(p.get('positionAmt', 0))
            if amt != 0:
                side = p['positionSide']
                positions[side] = {
                    "dir": "LONG" if amt > 0 else "SHORT",
                    "qty": abs(amt),
                    "entry": abs(float(p['entryPrice'])),
                    "unrealizedProfit": float(p.get('unRealizedProfit', 0))
                }
    except: pass
    return positions

def get_klines(symbol, interval, limit=100):
    r = requests.get(f'https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={limit}', timeout=10)
    return r.json()

def calc_rsi(prices, period=14):
    if len(prices) < period+1: return 50
    gains = [max(0, prices[i]-prices[i-1]) for i in range(1,len(prices))]
    losses = [max(0, prices[i-1]-prices[i]) for i in range(1,len(prices))]
    avg_gain = sum(gains[-period:])/period
    avg_loss = sum(losses[-period:])/period
    if avg_loss == 0: return 100
    return 100 - 100/(1 + avg_gain/avg_loss)

def calc_stoch_rsi(prices, period=14, smooth_k=3, smooth_d=3):
    if len(prices) < period+1: return 50, 50
    rsi_values = []
    for i in range(period, len(prices)+1):
        rsi = calc_rsi(prices[:i], period)
        rsi_values.append(rsi)
    if len(rsi_values) < 3: return 50, 50
    rsi_arr = rsi_values[-smooth_k:]
    lowest = min(rsi_arr); highest = max(rsi_arr)
    if highest == lowest: return 50, 50
    k = (rsi_values[-1] - lowest) / (highest - lowest) * 100
    d = sum(rsi_arr[-smooth_d:]) / smooth_d if len(rsi_arr) >= smooth_d else k
    return k, d

def calc_ema(prices, n):
    if len(prices) < n: return None
    k = 2/(n+1)
    ema = sum(prices[:n])/n
    for p in prices[n:]:
        ema = p*k + ema*(1-k)
    return ema

def get_signal_scores(symbol):
    """计算信号评分"""
    k1h = get_klines(symbol, "1h", 100)
    k15m = get_klines(symbol, "15m", 100)
    c1h = [float(k[4]) for k in k1h]
    c15m = [float(k[4]) for k in k15m]
    v15m = [float(k[5]) for k in k15m]
    
    cur = c1h[-1]
    r1 = calc_rsi(c1h, 14)
    r15 = calc_rsi(c15m, 14)
    sk15, _ = calc_stoch_rsi(c15m, 14, 3, 3)
    sk1, _ = calc_stoch_rsi(c1h, 14, 3, 3)
    
    ema1h_20 = calc_ema(c1h, 20)
    ema1h_20_prev = calc_ema(c1h[:-1], 20)
    
    vr = v15m[-1] / (sum(v15m[-20:])/20) if len(v15m) >= 20 else 1
    
    # 趋势
    trend_up = cur > ema1h_20 and ema1h_20 > ema1h_20_prev
    trend_score = 1 if trend_up else 0
    
    # 做多评分
    long_score = 0
    if r1 < 40: long_score += 1
    if r1 < 45: long_score += 0.5
    if r15 < 40: long_score += 1
    if trend_up: long_score += 1
    if sk15 < 20: long_score += 2
    if sk1 < 20: long_score += 1
    
    # 做空评分
    short_score = 0
    if r1 > 35: short_score += 1
    if r1 > 60: short_score += 1
    if not trend_up: short_score += 1
    if sk15 > 80: short_score += 2
    if sk1 > 80: short_score += 1
    
    return {
        "price": cur,
        "rsi_1h": round(r1, 1),
        "rsi_15m": round(r15, 1),
        "stoch_15m": round(sk15, 1),
        "stoch_1h": round(sk1, 1),
        "volume_ratio": round(vr, 2),
        "trend_up": trend_up,
        "long_score": round(long_score, 1),
        "short_score": round(short_score, 1),
        "long_ready": long_score >= 6.5,
        "short_ready": short_score >= 6.5
    }

@app.route('/api/status')
def status():
    """获取整体状态"""
    bal = get_balance()
    
    # Bot进程状态
    try:
        result = subprocess.run(['pm2', 'list'], capture_output=True, text=True)
        bot_online = 'bot20x' in result.stdout and 'online' in result.stdout
        restart_count = 0
        for line in result.stdout.split('\n'):
            if 'bot20x' in line:
                parts = line.split()
                for i, p in enumerate(parts):
                    if '↺' in p or 'restart' in p.lower():
                        try: restart_count = int(parts[i].replace('↺',''))
                        except: pass
                break
    except:
        bot_online = False
        restart_count = 0
    
    return jsonify({
        "balance": round(bal, 2),
        "bot_online": bot_online,
        "restart_count": restart_count,
        "timestamp": datetime.now().strftime('%H:%M:%S')
    })

@app.route('/api/positions')
def positions():
    """获取持仓"""
    result = {}
    for sym in ["BTCUSDT", "ETHUSDT"]:
        try:
            pos = get_positions(sym)
            if pos:
                result[sym] = pos
        except: pass
    return jsonify(result)

@app.route('/api/signals')
def signals():
    """获取信号"""
    result = {}
    for sym in ["BTCUSDT", "ETHUSDT"]:
        try:
            result[sym] = get_signal_scores(sym)
        except Exception as e:
            result[sym] = {"error": str(e)}
    return jsonify(result)

@app.route('/api/close', methods=['POST'])
def close_position():
    """平仓"""
    data = request.json
    symbol = data.get('symbol')
    side = data.get('side')
    pos_side = data.get('pos_side')
    qty = data.get('qty')
    
    if not all([symbol, side, pos_side, qty]):
        return jsonify({"error": "参数不全"}), 400
    
    params = f"symbol={symbol}&side={side}&positionSide={pos_side}&type=MARKET&quantity={qty:.3f}"
    resp = bn_post("/fapi/v1/order", params)
    
    if resp.get("orderId"):
        return jsonify({"success": True, "orderId": resp["orderId"]})
    else:
        return jsonify({"error": resp}), 400

@app.route('/api/bot/restart', methods=['POST'])
def restart_bot():
    """重启Bot"""
    subprocess.run(['pm2', 'restart', 'bot20x'])
    return jsonify({"success": True})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
