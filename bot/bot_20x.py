#!/usr/bin/env python3
"""
speedClaw Bot20x - 20x杠杆精准信号策略 v5.2

A Binance USDT-M永续合约量化交易机器人
特点：多周期EMA确认 + StochRSI信号 + 趋势反转预警

依赖：pip install requests
配置：cp config.py.template config.py 并填入API密钥

Usage:
    python bot_20x.py                    # 运行bot
    pm2 start bot_20x.py --name bot20x   # PM2守护模式运行
"""

import os
import sys
import requests, time, json, hmac, hashlib
from datetime import datetime

# === 配置文件加载 ===
try:
    from config import API_KEY, SECRET
except ImportError:
    print("错误：请复制 config.py.template 为 config.py 并填入API密钥")
    sys.exit(1)

LOG_FILE = os.path.join(os.path.dirname(__file__), "bot_20x.log")

# === 策略参数 ===
ADX_PERIOD = 14
ADX_TREND_THRESH = 25
ADX_WEAK_THRESH = 20
LOSS_STREAK_LIMIT = 3
LOSS_STREAK_PAUSE = 15*60

TREND_CONFLICT_FILTER = True  # 趋势冲突过滤
API_RETRY_MAX = 3
API_RETRY_DELAY = 2
API_TIMEOUT = 15

loss_streak_count = 0
last_loss_time = 0

LEVER = 20
RISK_PCT = 0.10
MIN_BAL = 3
OPEN_COOLDOWN = 0

SL_ATR_MULT = 0.02 # 固定2%止损
TP1_PCT = 0.02       # TP1：2%浮盈出半场
TP2_TRIGGER = 0.04   # TP2：4%浮盈出清
TP2_BUFFER = 0.008   # 追踪回撤0.8%
WIN_STREAK_ACCEL = 2 # 连赢2次激活加速
WIN_STREAK_THRESH = 0.05
ACCEL_SCORE_BOOST = 2

MAX_POS_PCT = 0.30
MAX_TOTAL_EXPOSURE = 1.50
DRAWDOWN_PROTECT = 0.15
DRAWDOWN_COOLDOWN = 1800
DRAWDOWN_COOLDOWN_FILE = os.path.join(os.path.dirname(__file__), ".drawdown_cooldown")
HIGH_WATER_FILE = os.path.join(os.path.dirname(__file__), ".high_water")
RISK_DANGER = 20
RISK_DANGER_PCT = 0.05
RISK_RICH_PCT = 0.08

TREND_STATE_FILE = os.path.join(os.path.dirname(__file__), ".trend_state")
TREND_WARN_COOLDOWN = 300
WARN_FILE = os.path.join(os.path.dirname(__file__), ".trend_warn")

# ============== 指标计算函数 ==============

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

def calc_adx(klines, period=14):
    if len(klines) < period*2+1: return 20, False
    trs, pos_dm, neg_dm = [], [], []
    for i in range(1, len(klines)):
        high, low = float(klines[i][2]), float(klines[i][3])
        prev_close = float(klines[i-1][4])
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        dm_plus = max(high - float(klines[i-1][2]), 0) if (high - float(klines[i-1][2])) > (float(klines[i-1][3]) - low) else 0
        dm_minus = max(float(klines[i-1][3]) - low, 0) if (float(klines[i-1][3]) - low) > (high - float(klines[i-1][2])) else 0
        trs.append(tr); pos_dm.append(dm_plus); neg_dm.append(dm_minus)
    adx_vals = []
    for i in range(period, len(trs)+1):
        tr_s = trs[i-period:i]; pdm_s = pos_dm[i-period:i]; ndm_s = neg_dm[i-period:i]
        atr_i = sum(tr_s)/period if sum(tr_s) > 0 else 1
        dp = sum(pdm_s)/period/atr_i*100 if atr_i > 0 else 0
        dn = sum(ndm_s)/period/atr_i*100 if atr_i > 0 else 0
        dx = abs(dp-dn)/(dp+dn)*100 if (dp+dn) > 0 else 0
        adx_vals.append(dx)
    adx = sum(adx_vals[-period:])/period if adx_vals else 20
    return min(adx, 60), sum(pos_dm[-period:])/period/trs[-1]*100 if trs[-1] > 0 else 0

def calc_atr(klines, period=14):
    if len(klines) < period+1: return 0
    trs = []
    for i in range(1, len(klines)):
        high = float(klines[i][2]); low = float(klines[i][3])
        prev_close = float(klines[i-1][4])
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        trs.append(tr)
    return sum(trs[-period:]) / period if trs else 0

# ============== API请求 ==============

def api_retry_call(func, *args, **kwargs):
    delay = API_RETRY_DELAY
    for attempt in range(API_RETRY_MAX):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if attempt < API_RETRY_MAX - 1:
                time.sleep(delay)
                delay *= 2
            else:
                log(f"API重试{API_RETRY_MAX}次失败: {e}")
                raise

def bn_get(endpoint, params=""):
    ts = str(int(time.time()*1000))
    p = f"{params}&timestamp={ts}" if params else f"timestamp={ts}"
    sig = hmac.new(SECRET.encode(), p.encode(), hashlib.sha256).hexdigest()
    return api_retry_call(requests.get,
        f"https://fapi.binance.com{endpoint}?{p}&signature={sig}",
        headers={"X-MBX-APIKEY": API_KEY}, timeout=API_TIMEOUT).json()

def bn_post(endpoint, params):
    ts = str(int(time.time()*1000))
    p = f"{params}&timestamp={ts}"
    sig = hmac.new(SECRET.encode(), p.encode(), hashlib.sha256).hexdigest()
    return api_retry_call(requests.post,
        f"https://fapi.binance.com{endpoint}?{p}&signature={sig}",
        headers={"X-MBX-APIKEY": API_KEY}, timeout=API_TIMEOUT).json()

def get_balance():
    try: return float(bn_get("/fapi/v2/account").get('availableBalance', 0))
    except: return 0

def get_all_positions(symbol):
    positions = {}
    for p in bn_get("/fapi/v2/positionRisk", f"symbol={symbol}"):
        amt = float(p.get('positionAmt', 0))
        if amt != 0:
            side = p['positionSide']
            positions[side] = {"dir": "LONG" if amt > 0 else "SHORT",
                                "qty": abs(amt), "entry": abs(float(p['entryPrice']))}
    return positions

def do_order(symbol, side, posSide, qty):
    params = f"symbol={symbol}&side={side}&positionSide={posSide}&type=MARKET&quantity={qty:.3f}"
    resp = bn_post("/fapi/v1/order", params)
    return resp.get("orderId") is not None

def get_klines(symbol, interval, limit=100):
    def _fetch():
        r = requests.get(
            f'https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={limit}',
            timeout=API_TIMEOUT)
        return r.json()
    return api_retry_call(_fetch)

# ============== 信号计算 ==============

def get_signal(symbol):
    k4h = get_klines(symbol, "4h", 60)
    k1h = get_klines(symbol, "1h", 100)
    k15m = get_klines(symbol, "15m", 100)
    
    c4h = [float(k[4]) for k in k4h]
    c1h = [float(k[4]) for k in k1h]
    c15m = [float(k[4]) for k in k15m]
    v15m = [float(k[5]) for k in k15m]
    
    cur = c1h[-1]
    r4 = calc_rsi(c4h, 14)
    r1 = calc_rsi(c1h, 14)
    r15 = calc_rsi(c15m, 14)
    sk15, _ = calc_stoch_rsi(c15m, 14, 3, 3)
    sk1, _ = calc_stoch_rsi(c1h, 14, 3, 3)
    vr = v15m[-1] / (sum(v15m[-20:])/20) if len(v15m) >= 20 else 1
    
    adx_val, _ = calc_adx(k1h, ADX_PERIOD)
    market_trending = adx_val >= ADX_TREND_THRESH
    market_weak = adx_val < ADX_WEAK_THRESH

    ema4h_20 = calc_ema(c4h, 20)
    ema4h_20_prev = calc_ema(c4h[:-4], 20)
    ema1h_20 = calc_ema(c1h, 20)
    ema1h_20_prev = calc_ema(c1h[:-1], 20)
    ema15m_20 = calc_ema(c15m, 20)
    ema15m_20_prev = calc_ema(c15m[:-1], 20)
    
    trend4h_price = cur > ema4h_20 and ema4h_20 > ema4h_20_prev
    trend1h_price = cur > ema1h_20 and ema1h_20 > ema1h_20_prev
    trend15m_price = c15m[-1] > ema15m_20 and ema15m_20 > ema15m_20_prev
    trend_up = trend1h_price and trend4h_price
    vr = v15m[-1] / (sum(v15m[-20:])/20) if len(v15m) >= 20 else 1
    
    r15_prev = calc_rsi(c15m[:-1], 14)
    div_bull = r15 < 50 and r15 > r15_prev and r15_prev < 52
    div_bear = r15 > 50 and r15 < r15_prev and r15_prev > 48
    
    ema_deviation = abs(cur - ema1h_20) / ema1h_20 * 100
    
    counter_trend_sig = None; counter_trend_reasons = []
    
    if r1 < 40 and ema_deviation > 0.5 and not market_weak:
        ct_score = 0; ct_reasons = []
        if r1 < 30: ct_score += 2; ct_reasons.append(f"R1={r1:.0f}<30")
        elif r1 < 35: ct_score += 1.5; ct_reasons.append(f"R1={r1:.0f}<35")
        else: ct_score += 1; ct_reasons.append(f"R1={r1:.0f}<40")
        if cur < ema1h_20 * 0.995: ct_score += 1.5; ct_reasons.append("偏离>0.5%")
        if sk15 < 20: ct_score += 2; ct_reasons.append(f"Stoch15={sk15:.0f}<20")
        if sk1 < 20: ct_score += 1; ct_reasons.append(f"Stoch1={sk1:.0f}<20")
        if div_bull: ct_score += 1.5; ct_reasons.append("底背")
        if ct_score >= 6.5:
            counter_trend_sig = "LONG"; counter_trend_reasons = ct_reasons
    
    if r1 > 60 and ema_deviation > 0.5 and r4 >= 15 and not market_weak:
        ct_score = 0; ct_reasons = []
        if r1 > 70: ct_score += 2; ct_reasons.append(f"R1={r1:.0f}>70")
        elif r1 > 65: ct_score += 1.5; ct_reasons.append(f"R1={r1:.0f}>65")
        else: ct_score += 1; ct_reasons.append(f"R1={r1:.0f}>60")
        if cur > ema1h_20 * 1.005: ct_score += 1.5; ct_reasons.append("偏离>0.5%")
        if sk15 > 80: ct_score += 2; ct_reasons.append(f"Stoch15={sk15:.0f}>80")
        if sk1 > 80: ct_score += 1; ct_reasons.append(f"Stoch1={sk1:.0f}>80")
        if div_bear: ct_score += 1.5; ct_reasons.append("顶背")
        if ct_score >= 6.5:
            counter_trend_sig = "SHORT"; counter_trend_reasons = ct_reasons
    
    long_score = 0; long_reasons = []
    if r1 < 40: long_score += 1; long_reasons.append(f"R1={r1:.0f}<40")
    elif r1 < 45: long_score += 0.5; long_reasons.append(f"R1={r1:.0f}<45")
    if r4 < 50: long_score += 1; long_reasons.append(f"R4={r4:.0f}<50")
    if r15 < 40: long_score += 1; long_reasons.append(f"R15={r15:.0f}<40")
    if trend_up: long_score += 1; long_reasons.append("趋势↑")
    if sk15 < 20: long_score += 2; long_reasons.append(f"Stoch15={sk15:.0f}<20")
    if sk1 < 20: long_score += 1; long_reasons.append(f"Stoch1={sk1:.0f}<20")
    stoich_extreme = sk15 < 20 or sk1 < 20
    if 40 <= r1 < 45 and not stoich_extreme:
        long_score -= 0.5; long_reasons.append("放宽区无Stoch极端")
    if div_bull: long_score += 2; long_reasons.append("底背")
    if vr > 1.5: long_score += 1; long_reasons.append(f"V={vr:.1f}x")
    
    short_score = 0; short_reasons = []
    if r1 > 35: short_score += 1; short_reasons.append(f"R1={r1:.0f}>35")
    elif r1 > 30: short_score += 0.5; short_reasons.append(f"R1={r1:.0f}>30")
    if r4 > 50: short_score += 1; short_reasons.append(f"R4={r4:.0f}>50")
    if r4 < 40: short_score += 0.5; short_reasons.append(f"R4={r4:.0f}<40强势")
    if r15 > 55: short_score += 1; short_reasons.append(f"R15={r15:.0f}>55")
    if not trend_up: short_score += 1; short_reasons.append("趋势↓")
    if sk15 > 80: short_score += 2; short_reasons.append(f"Stoch15={sk15:.0f}>80")
    if sk1 > 80: short_score += 1; short_reasons.append(f"Stoch1={sk1:.0f}>80")
    if div_bear: short_score += 2; short_reasons.append("顶背")
    if vr > 1.5: short_score += 1; short_reasons.append(f"V={vr:.1f}x")
    
    sig = None; reasons = []
    if long_score >= 6.5:
        sig = "LONG"; reasons = long_reasons
    elif counter_trend_sig:
        sig = counter_trend_sig; reasons = counter_trend_reasons
    elif short_score >= 6.5:
        sig = "SHORT"; reasons = short_reasons
    elif counter_trend_sig:
        sig = counter_trend_sig; reasons = counter_trend_reasons
    
    trend_conflict = TREND_CONFLICT_FILTER and (trend4h_price != trend1h_price)
    if trend_conflict:
        sig = None; reasons = ["趋势冲突"]
    
    return {
        'cur': cur, 'r4': r4, 'r1': r1, 'r15': r15,
        'sk15': sk15, 'sk1': sk1, 'vr': vr,
        'trend_up': trend_up,
        'trend_reasons': (["4H↑EMA"] if trend4h_price else ["4H↓EMA"]) + (["1H↑EMA"] if trend1h_price else ["1H↓EMA"]),
        'sig': sig, 'reasons': reasons,
        'trend_conflict': trend_conflict
    }

# ============== 风控函数 ==============

def calc_sl(entry, direction):
    sl_dist = entry * SL_ATR_MULT
    return entry - sl_dist if direction == "LONG" else entry + sl_dist

def get_risk_pct(balance):
    if balance < RISK_DANGER: return RISK_DANGER_PCT
    elif balance > 80: return RISK_RICH_PCT
    else: return RISK_PCT

def get_max_pos_qty(balance, price):
    return round((balance * MAX_POS_PCT) / price, 3)

def get_high_water():
    try:
        with open(HIGH_WATER_FILE) as f: return float(f.read().strip())
    except: return 0

def save_high_water(bal):
    with open(HIGH_WATER_FILE, "w") as f: f.write(str(bal))

def check_drawdown_protection(balance):
    high = get_high_water()
    if high > 0 and balance < high * (1 - DRAWDOWN_PROTECT):
        return True, high
    return False, high

def calc_qty(balance, price):
    risk_pct = get_risk_pct(balance)
    risk_amount = balance * risk_pct
    sl_dist = price * SL_ATR_MULT
    if sl_dist == 0: return 0
    qty = risk_amount / sl_dist
    min_qty = max(0.001, round(risk_amount / price, 3))
    max_qty = get_max_pos_qty(balance, price)
    return max(min_qty, min(round(qty, 3), max_qty))

# ============== 趋势预警 ==============

def load_trend_state():
    try:
        with open(TREND_STATE_FILE) as f: return json.load(f)
    except: return {"btc_trend": None, "eth_trend": None, "last_warn": 0}

def save_trend_state(state):
    with open(TREND_STATE_FILE, "w") as f: json.dump(state, f)

def check_trend_reversal_warning(symbol, current_trend_up, positions):
    now = time.time()
    state = load_trend_state()
    key = symbol.replace("USDT", "").lower() + "_trend"
    prev_trend = state.get(key)
    last_warn = state.get("last_warn", 0)
    
    if prev_trend is not None and prev_trend != current_trend_up:
        if now - last_warn < TREND_WARN_COOLDOWN: return
        for direction in ["LONG", "SHORT"]:
            pos = positions.get(direction)
            if not pos: continue
            if (current_trend_up and direction == "SHORT") or (not current_trend_up and direction == "LONG"):
                old_str = "下降" if not prev_trend else "上升"
                new_str = "上升" if current_trend_up else "下降"
                msg = f"⚠️ 【趋势反转预警】\n\n{symbol} 1H趋势：{old_str} → {new_str}\n\n当前持仓：{direction} {pos['qty']} @ ${round(pos['entry'], 2)}\n\n建议：考虑手动平仓\n\n—— speedClaw Bot20x"
                log(f"🚨 趋势反转预警：{symbol} {direction} 逆势持仓中！")
                state["pending_warn"] = msg
                state["last_warn"] = now
                save_trend_state(state)
                with open(WARN_FILE, "w") as f: f.write(msg)
                return
    state[key] = current_trend_up
    save_trend_state(state)

# ============== 日志 ==============

def log(msg):
    ts = datetime.now().strftime('%m/%d %H:%M:%S')
    print(f"[{ts}] {msg}")
    with open(LOG_FILE, "a") as f: f.write(f"[{ts}] {msg}\n")

# ============== 主循环 ==============

def main():
    log("="*60)
    log("speedClaw Bot20x v5.2 | 20x杠杆精准信号策略")
    log("="*60)
    
    state_files = {
        "BTCUSDT": {
            "LONG": os.path.join(os.path.dirname(__file__), "st_btc_long.json"),
            "SHORT": os.path.join(os.path.dirname(__file__), "st_btc_short.json")
        },
        "ETHUSDT": {
            "LONG": os.path.join(os.path.dirname(__file__), "st_eth_long.json"),
            "SHORT": os.path.join(os.path.dirname(__file__), "st_eth_short.json")
        },
    }
    
    while True:
        try:
            bal = get_balance()
            now = time.time()
            
            high_water = get_high_water()
            if bal > high_water:
                save_high_water(bal)
                high_water = bal
            
            try:
                with open(DRAWDOWN_COOLDOWN_FILE) as f: last_drawdown = float(f.read().strip())
            except: last_drawdown = 0
            
            drawback_triggered, high = check_drawdown_protection(bal)
            if drawback_triggered and (now - last_drawdown) > DRAWDOWN_COOLDOWN:
                log(f"⚠️ 回撤保护触发：高点${high:.2f} → 当前${bal:.2f}，减半仓")
                with open(DRAWDOWN_COOLDOWN_FILE, "w") as f: f.write(str(now))
                for sym, sf in state_files.items():
                    for direction in ["LONG", "SHORT"]:
                        try:
                            with open(sf[direction]) as f: s = json.load(f)
                        except: continue
                        if s.get("pos") and s.get("qty"):
                            half_qty = round(s["qty"] / 2, 3)
                            if half_qty >= 0.001:
                                do_order(sym, "SELL" if s["pos"]=="LONG" else "BUY", s["pos"], half_qty)
                                log(f"{sym} {s['pos']} 回撤保护减半：出{half_qty}")
                                s["qty"] = round(s["qty"] - half_qty, 3)
                                if s["qty"] < 0.001: s.clear()
                                with open(sf[direction], "w") as f: json.dump(s, f)
                time.sleep(2)
                time.sleep(3); continue
            
            total_exposure = 0
            for sym in ["BTCUSDT", "ETHUSDT"]:
                try:
                    cur_price = float(get_klines(sym, "1m", 1)[0][4])
                except: cur_price = 0
                for p in bn_get("/fapi/v2/positionRisk", f"symbol={sym}"):
                    amt = abs(float(p.get('positionAmt', 0)))
                    if amt > 0:
                        entry = abs(float(p.get('entryPrice', 0)))
                        price_used = cur_price if cur_price > 0 else entry
                        total_exposure += (amt * price_used) / LEVER
            if total_exposure > bal * MAX_TOTAL_EXPOSURE:
               log(f"⚠️ 总仓位超限：${total_exposure:.2f} > ${bal:.2f}×{MAX_TOTAL_EXPOSURE}")
                time.sleep(15); continue

            global loss_streak_count, last_loss_time
            if loss_streak_count >= LOSS_STREAK_LIMIT and (now - last_loss_time) < LOSS_STREAK_PAUSE:
                log(f"熔断中：连亏{loss_streak_count}次，剩余{int(LOSS_STREAK_PAUSE-(now-last_loss_time))/60:.0f}分钟")
                time.sleep(15); continue
            elif loss_streak_count >= LOSS_STREAK_LIMIT:
                loss_streak_count = 0; log("熔断恢复")

            for symbol in ["BTCUSDT", "ETHUSDT"]:
                sf = state_files[symbol]
                info = get_signal(symbol)
                positions = get_all_positions(symbol)
                check_trend_reversal_warning(symbol, info.get('trend_up', False), positions)
                
                for direction in ["LONG", "SHORT"]:
                    sf_file = sf[direction]
                    try:
                        with open(sf_file) as f: s = json.load(f)
                    except: s = {}
                    
                    pos = positions.get(direction)
                    
                    if s.get("pos") and not pos:
                        log(f"{symbol} {direction} 手动平仓已同步 | 上次:{s.get('last','?')}")
                        s["closed"] = now
                        s["last"] = s.get("last", "closed")
                        s.pop("pos", None)
                        with open(sf_file, "w") as f: json.dump(s, f)
                        continue
                    
                    if not pos:
                        sig = info['sig']
                        closed_time = s.get("closed", now - OPEN_COOLDOWN - 1)
                        win_streak = s.get("win_streak", 0)
                        
                        if win_streak >= WIN_STREAK_ACCEL:
                            if direction == "SHORT" and info.get('r1', 99) > 33:
                                sig = "SHORT"
                            elif direction == "LONG" and info.get('trend_up') and info.get('r1', 99) < 47:
                                sig = "LONG"
                        
                        trend_ok = info['long_ready'] if direction == "LONG" else info['short_ready']
                        if not trend_ok:
                            log(f"{symbol} {direction} 趋势不符 {info['trend_reasons']} 跳过")
                            continue
                        
                        sig_ok = sig == direction
                        if sig_ok and bal > MIN_BAL and (now - closed_time) > OPEN_COOLDOWN:
                            qty = calc_qty(bal, info['cur'])
                            log(f"{symbol} -> {direction} {info['reasons']} @{info['cur']:.0f} qty:{qty}")
                            if do_order(symbol, "BUY" if direction=="LONG" else "SELL", direction, qty):
                                s.clear()
                                s.update({
                                    "pos": direction, "entry": info['cur'], "qty": qty,
                                    "sl": calc_sl(info['cur'], direction),
                                    "best": info['cur'], "opened": now,
                                    "tp1_done": False, "tp2_done": False,
                                    "last": None, "win_streak": 0
                                })
                                with open(sf_file, "w") as f: json.dump(s, f)
                                time.sleep(3)
                        else:
                            sig_str = sig if sig else "无信号"
                            log(f"{symbol} {direction} {info['cur']:.0f} R4={info['r4']:.0f}/R1={info['r1']:.0f} Sk15={info['sk15']:.0f} {sig_str}")
                    else:
                        d = pos["dir"]; entry = pos["entry"]; cur = info['cur']
                        
                        if "sl" not in s: s["sl"] = calc_sl(entry, d)
                        if "best" not in s: s["best"] = entry
                        
                        if d == "LONG":
                            pnl = (cur - entry) / entry * 100
                            best_high = max(s.get("best", entry), cur)
                            s["best"] = best_high
                            tp1_price = entry * (1 + TP1_PCT)
                            if not s.get("tp1_done") and cur >= tp1_price:
                                half_qty = round(pos["qty"] / 2, 3)
                                do_order(symbol, "SELL", d, half_qty)
                                log(f"{symbol} {d} TP1 @{cur:.0f} ({pnl:+.1f}%) 出{half_qty}")
                                s["tp1_done"] = True
                                s["win_streak"] = s.get("win_streak", 0) + 1
                            if pnl >= TP2_TRIGGER * 100 and not s.get("tp2_done"):
                                trail_tp = best_high * (1 - TP2_BUFFER)
                                if cur <= trail_tp:
                                    remaining = round(pos["qty"] * 0.5, 3)
                                    do_order(symbol, "SELL", d, remaining)
                                    log(f"{symbol} {d} TP2 @{cur:.0f} ({pnl:+.1f}%) 剩余出清")
                                    s["tp2_done"] = True; s["last"] = "win"; s.clear()
                                    with open(sf_file, "w") as f: json.dump(s, f)
                                    continue
                        else:
                            pnl = (entry - cur) / entry * 100
                            best_low = min(s.get("best", entry), cur)
                            s["best"] = best_low
                            tp1_price = entry * (1 - TP1_PCT)
                            if not s.get("tp1_done") and cur <= tp1_price:
                                half_qty = round(pos["qty"] / 2, 3)
                                do_order(symbol, "BUY", d, half_qty)
                                log(f"{symbol} {d} TP1 @{cur:.0f} ({pnl:+.1f}%) 出{half_qty}")
                                s["tp1_done"] = True
                                s["win_streak"] = s.get("win_streak", 0) + 1
                            if pnl >= TP2_TRIGGER * 100 and not s.get("tp2_done"):
                                trail_tp = best_low * (1 + TP2_BUFFER)
                                if cur >= trail_tp:
                                    remaining = round(pos["qty"] * 0.5, 3)
                                    do_order(symbol, "BUY", d, remaining)
                                    log(f"{symbol} {d} TP2 @{cur:.0f} ({pnl:+.1f}%) 剩余出清")
                                    s["tp2_done"] = True; s["last"] = "win"; s.clear()
                                    with open(sf_file, "w") as f: json.dump(s, f)
                                    continue
                        
                        markers = []
                        if s.get("tp1_done"): markers.append("TP1[OK]")
                        if s.get("tp2_done"): markers.append("TP2[OK]")
                        fire = "🔥" if pnl > 1.0 else ""
                        m = " " + ",".join(markers) if markers else ""
                        log(f"{symbol} {d} {pnl:+.1f}%{fire}{m}")
                        with open(sf_file, "w") as f: json.dump(s, f)
            
            time.sleep(15)
        except KeyboardInterrupt:
            log("STOPPED"); break
        except Exception as e:
            log(f"ERROR: {e}"); import traceback; traceback.print_exc(); time.sleep(15)

if __name__ == "__main__":
    main()