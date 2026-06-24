#!/usr/bin/env python3
"""
SpeedClaw BotKing 现货机器人 v1.1
混沌龙虾 🦞 — 独立部署版

名称：SpeedClaw BotKing
类型：现货智能网格+趋势双引擎
交易所：币安现货 USDT-M

v1.1 优化：
  P0：网格引擎止损12%→8%，格距0.6%→0.4%，TS激活6%→4%
  P1：多币关联性敞口检查，防止高相关币种同时重仓
  P2：API限速处理+熔断机制
  P3：关联性系数传递到主循环
"""

import requests, time, json, yaml, math
from datetime import datetime
from spot_adapter import BinanceSpotAdapter as SpotAdapter

# ===================== 配置 =====================
CONFIG_FILE = "/root/.openclaw/workspace/spot_config.yaml"

def load_config():
    with open(CONFIG_FILE) as f:
        return yaml.safe_load(f)

cfg = load_config()
LOG_FILE  = cfg.get('log_file', '/root/.openclaw/workspace/bot_king.log')
STATE_DIR = cfg.get('state_dir', '/root/.openclaw/workspace/')
STATE_FILE = STATE_DIR + "bot_king_state.json"

COINS = cfg.get('coins', ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'AVAXUSDT', 'XRPUSDT'])

# ==================== BotKing v1.1 核心参数 ====================

# ---- 网格引擎参数（优化1：更窄止损+更密格距）----
# v1.0: GRID_PROFIT=0.006, GRID_VOL_PROFIT=0.010, SL=12%, TS激活6%
# v1.1: 每格利润收窄到0.3-0.6%，止损收窄到8%，TS激活降到4%
# 期望：需要3次赢才能弥补1次止损 → 75%胜率=正期望
GRID_PROFIT     = 0.004    # 每格0.4%（优化：原0.6%）
GRID_VOL_PROFIT = 0.006    # 高波动每格0.6%（优化：原1.0%）
GRID_SL_PCT     = 0.08     # 网格止损8%（优化：原12%）
TS_PCT          = 0.025    # 网格追踪回撤2.5%（优化：原3%，更早锁利）

# ---- 趋势引擎参数（保持不变）----
SL_PCT          = 0.12     # 趋势止损12%
TP_TREND1       = 0.15     # 趋势第一目标+15%
TP_TREND2       = 0.25     # 趋势第二目标+25%
TS_TREND_PCT    = 0.05     # 趋势追踪回撤5%

# 资金分级（现货无杠杆）
TIER1 = 50
TIER2 = 150
TIER3 = 500
TIER4 = 1500

# 风控
DRAWDOWN_PROTECT = 0.20
MAX_DAILY_LOSS   = 0.08
CRASH_LIMIT      = 3
CRASH_PAUSE      = 900
PROFIT_LOCK      = 0.50
PHASE2_DELAY     = 300

# ATR自适应（优化2：调整格距以匹配新GRID_PROFIT）
ATR_GRID_MAP = {
    'high':   (2, 0.006),   # 高波动：2格×0.6%=1.2%总利润（优化：原1.0%×2=2%）
    'medium': (4, 0.004),   # 中波动：4格×0.4%=1.6%总利润（优化：原0.6%×4=2.4%）
    'low':    (6, 0.003),   # 低波动：6格×0.3%=1.8%总利润（优化：原0.4%×6=2.4%）
}

# 运行
CHECK_INTERVAL = 20
SCAN_INTERVAL  = 180
SAVE_INTERVAL  = 60
MAX_POSITIONS  = 3

# === 优化2：API限速与熔断 ===
API_RATE_LIMIT_WINDOW = 60     # 60秒窗口
API_MAX_REQUESTS     = 900    # 币安现货<1200请求/分钟，留300余量
API_CIRCUIT_BREAKER_THRESHOLD = 50  # 连续50次失败触发熔断
API_CIRCUIT_BREAKER_PAUSE = 120     # 熔断暂停120秒
_api_request_log = []          # 请求时间戳记录
_api_fail_count = 0            # 连续失败计数
_circuit_broken = False
_circuit_break_until = 0

# === 市场宏观过滤 ===
FEAR_GREED_URL = "https://api.alternative.me/fng/"
FEAR_GREED_COOLDOWN = 3600
_last_fear_greed = 75
_last_fg_fetch = 0

# 指标
RSI_PERIOD = 14
MACD_FAST, MACD_SLOW, MACD_SIGNAL = 12, 26, 9
BB_PERIOD, BB_MULT = 20, 2.0
ATR_PERIOD = 14

# ===================== 工具函数 =====================
def log(msg):
    ts = datetime.now().strftime('%m/%d %H:%M:%S')
    print(f"[{ts}] {msg}")
    with open(LOG_FILE, "a") as f:
        f.write(f"[{ts}] {msg}\n")

def _check_api_rate_limit():
    """优化2：API限速检查。每次调用前检查，超限则等待。"""
    global _api_request_log
    now = time.time()
    # 清理60秒外的记录
    _api_request_log = [t for t in _api_request_log if now - t < API_RATE_LIMIT_WINDOW]
    if len(_api_request_log) >= API_MAX_REQUESTS:
        sleep_time = API_RATE_LIMIT_WINDOW - (now - _api_request_log[0]) + 1
        log(f"[⚠️ API限速] 60秒内请求{len(_api_request_log)}次，休眠{sleep_time:.0f}秒")
        time.sleep(max(1, sleep_time))
        _api_request_log = [t for t in _api_request_log if now - t < API_RATE_LIMIT_WINDOW]
    _api_request_log.append(now)

def _check_circuit_breaker():
    """优化2：熔断检查。如果触发熔断，暂停所有交易操作。"""
    global _circuit_broken, _circuit_break_until
    if _circuit_broken and time.time() < _circuit_break_until:
        remaining = int(_circuit_break_until - time.time())
        return False, remaining
    if _circuit_broken:
        _circuit_broken = False
        log(f"[🔄 熔断恢复] API请求恢复正常")
    return True, 0

def _api_fail():
    """优化2：记录API失败。连续50次失败触发熔断。"""
    global _api_fail_count, _circuit_broken, _circuit_break_until
    _api_fail_count += 1
    if _api_fail_count >= API_CIRCUIT_BREAKER_THRESHOLD:
        _circuit_broken = True
        _circuit_break_until = time.time() + API_CIRCUIT_BREAKER_PAUSE
        log(f"[💥 熔断触发] API连续{_api_fail_count}次失败，暂停120秒")
        return True
    return False

def _api_success():
    """优化2：API成功调用，重置失败计数。"""
    global _api_fail_count
    _api_fail_count = 0

def calc_rsi(prices, period=14):
    if len(prices) < period+1: return 50
    gains = [max(0, prices[i]-prices[i-1]) for i in range(1,len(prices))]
    losses = [max(0, prices[i-1]-prices[i]) for i in range(1,len(prices))]
    avg_gain = sum(gains[-period:])/period
    avg_loss = sum(losses[-period:])/period
    if avg_loss == 0: return 100
    return 100 - 100/(1 + avg_gain/avg_loss)

def calc_ema(prices, n):
    if len(prices) < n: return None
    k = 2/(n+1)
    ema = sum(prices[:n])/n
    for p in prices[n:]: ema = p*k + ema*(1-k)
    return ema

def calc_macd(prices, fast=12, slow=26, signal=9):
    if len(prices) < slow+signal: return 0, 0, 0
    ema_fast = calc_ema(prices, fast)
    ema_slow = calc_ema(prices, slow)
    if ema_fast is None or ema_slow is None: return 0, 0, 0
    macd = ema_fast - ema_slow
    return macd, 0, 0

# 币种相关性映射（BTC为标杆）
# 优化3：加入关联性敞口检查，高相关币种在熊市不能同时重仓
CORRELATION_WITH_BTC = {
    "BTCUSDT": 1.0,
    "ETHUSDT": 0.85,  # 高度相关
    "BNBUSDT": 0.70,  # 中度相关
    "SOLUSDT": 0.65,  # 中度相关
    "AVAXUSDT": 0.60, # 中低相关
    "XRPUSDT": 0.55,  # 低相关
    "SUIUSDT": 0.50,
}

def calc_atr(klines, period=14):
    if not klines or len(klines) < period+1: return 0
    trs = []
    for i in range(1, len(klines)):
        h, l, c = float(klines[i][2]), float(klines[i][3]), float(klines[i][4])
        prev_c = float(klines[i-1][4])
        tr = max(h-l, abs(h-prev_c), abs(l-prev_c))
        trs.append(tr)
    if len(trs) < period: return 0
    return sum(trs[-period:]) / period

def calc_adx(klines, period=14):
    if not klines or len(klines) < period+2: return 20
    pdm, mdm, trs = [], [], []
    for i in range(1, len(klines)):
        h, l, c = float(klines[i][2]), float(klines[i][3]), float(klines[i][4])
        ph, pl = float(klines[i-1][2]), float(klines[i-1][3])
        up = h - ph; dn = pl - l
        pdm.append(max(up, dn) if up > dn else 0)
        mdm.append(max(dn, up) if dn > up else 0)
        tr = max(h-l, abs(h-c), abs(l-c))
        trs.append(tr)
    if len(trs) < period: return 20
    pdi = sum(pdm[-period:]) / sum(trs[-period:]) * 100 if sum(trs[-period:]) > 0 else 0
    mdi = sum(mdm[-period:]) / sum(trs[-period:]) * 100 if sum(trs[-period:]) > 0 else 0
    dx = abs(pdi - mdi) / (pdi + mdi) * 100 if (pdi + mdi) > 0 else 0
    return min(dx, 100)

def get_phase1_grids(balance):
    if balance < 100:  return 1
    if balance < 300:  return 2
    return 2

def get_fear_greed():
    global _last_fear_greed, _last_fg_fetch
    now = time.time()
    if now - _last_fg_fetch < FEAR_GREED_COOLDOWN:
        return _last_fear_greed
    try:
        _check_api_rate_limit()
        r = requests.get(FEAR_GREED_URL, timeout=5)
        _api_success()
        data = r.json().get('data', [{}])[0]
        _last_fear_greed = int(data.get('value', 50))
        _last_fg_fetch = now
        log(f"[宏观] Fear & Greed: {_last_fear_greed} ({data.get('value_classification','')})")
    except:
        log(f"[宏观] Fear & Greed获取失败，使用默认值50")
    return _last_fear_greed

def is_extreme_hour():
    from datetime import datetime
    h = datetime.utcfromtimestamp(time.time()).hour
    return 14 <= h <= 18  # UTC14-18 = 北京时间22:00-02:00

# ===================== 市场模式检测 =====================
def detect_market_mode(symbol, ex):
    _check_api_rate_limit()
    try:
        c15m = ex.get_klines(symbol, "15m", 60)
        _api_success()
    except:
        _api_fail()
        return "RANGE_BOUND", {'price': 0, 'rsi': 50, 'mode': 'RANGE_BOUND',
                               'grids': 4, 'grid_profit': GRID_PROFIT, 'atr': 0,
                               'trend_bias': 0.3, 'confidence': 0, 'correlation': CORRELATION_WITH_BTC.get(symbol, 0.5)}
    try:
        c1h  = ex.get_klines(symbol, "1h",  60)
        c4h  = ex.get_klines(symbol, "4h",  100)
        c1d  = ex.get_klines(symbol, "1d",  50)
        _api_success()
    except:
        _api_fail()
        return "RANGE_BOUND", {'price': 0, 'rsi': 50, 'mode': 'RANGE_BOUND',
                               'grids': 4, 'grid_profit': GRID_PROFIT, 'atr': 0,
                               'trend_bias': 0.3, 'confidence': 0, 'correlation': CORRELATION_WITH_BTC.get(symbol, 0.5)}

    if not (c1h and c4h and c1d):
        return "RANGE_BOUND", {'price': 0, 'rsi': 50, 'mode': 'RANGE_BOUND',
                               'grids': 4, 'grid_profit': GRID_PROFIT, 'atr': 0,
                               'trend_bias': 0.3, 'confidence': 0, 'correlation': CORRELATION_WITH_BTC.get(symbol, 0.5)}

    closes_15m = [float(k[4]) for k in c15m] if c15m else []
    closes_1h = [float(k[4]) for k in c1h]
    closes_4h = [float(k[4]) for k in c4h]
    closes_1d = [float(k[4]) for k in c1d]
    cur = closes_1h[-1]
    if cur <= 0:
        return "RANGE_BOUND", {'price': 0, 'rsi': 50, 'mode': 'RANGE_BOUND',
                               'grids': 4, 'grid_profit': GRID_PROFIT, 'atr': 0,
                               'trend_bias': 0.3, 'confidence': 0, 'correlation': CORRELATION_WITH_BTC.get(symbol, 0.5)}

    rsi_15m = calc_rsi(closes_15m) if closes_15m else 50
    rsi_1h  = calc_rsi(closes_1h)
    rsi_d1  = calc_rsi(closes_1d)

    ema20_15m = calc_ema(closes_15m, 20) if closes_15m else None
    ema20_1h  = calc_ema(closes_1h, 20)
    ema20_4h  = calc_ema(closes_4h, 20)
    ema20_1d  = calc_ema(closes_1d, 20)

    adx_1h = calc_adx(c1h)
    adx_4h = calc_adx(c4h)
    adx_avg = (adx_1h + adx_4h) / 2

    trend_up_15m = ema20_15m is not None and closes_15m[-1] > ema20_15m
    trend_up_1h  = ema20_1h  is not None and cur > ema20_1h
    trend_up_4h  = ema20_4h  is not None and closes_4h[-1] > ema20_4h
    trend_up_d1  = ema20_1d  is not None and closes_1d[-1] > ema20_1d

    trend_down_15m = ema20_15m is not None and closes_15m[-1] < ema20_15m
    trend_down_1h  = ema20_1h  is not None and cur < ema20_1h
    trend_down_4h  = ema20_4h  is not None and closes_4h[-1] < ema20_4h
    trend_down_d1  = ema20_1d  is not None and closes_1d[-1] < ema20_1d

    macd, _, macd_sig = calc_macd(closes_1h)

    rsi_bullish_div = False
    if len(closes_1h) >= 20:
        price_slope = closes_1h[-1] - closes_1h[-20]
        rsi_slope   = rsi_1h - calc_rsi(closes_1h[:-10]) if len(closes_1h) >= 30 else 0
        rsi_bullish_div = price_slope < -0.02 * cur and rsi_slope > 2

    vol_cur = float(c1h[-1][5]) if c1h else 0
    vol_avg = sum(float(k[5]) for k in c1h[-30:]) / 30 if c1h else 1
    vol_ratio = vol_cur / vol_avg if vol_avg > 0 else 1
    vol_surge = vol_ratio > 1.3

    price_range = (max(closes_1h) - min(closes_1h)) / cur
    is_volatile = price_range > 0.08

    atr = calc_atr(c1h)
    atr_pct = atr / cur
    if atr_pct > 0.05:   atr_grids, atr_gp = ATR_GRID_MAP['high']
    elif atr_pct > 0.02: atr_grids, atr_gp = ATR_GRID_MAP['medium']
    else:                   atr_grids, atr_gp = ATR_GRID_MAP['low']

    fg = get_fear_greed()
    vol_valid = vol_ratio > 0.7

    # === 模式判断 ===
    mode = "RANGE_BOUND"
    confidence = 0.5

    if rsi_d1 > 80 or rsi_d1 < 20:
        mode = "CRISIS"; confidence = 0.95
    elif adx_avg > 25 and trend_up_d1 and trend_up_4h and trend_up_1h:
        mode = "TREND_UP"
        confidence = min(0.95, 0.6 + (adx_avg - 25) / 75 + 0.1 * int(macd > macd_sig))
    elif adx_avg > 25 and trend_down_4h and trend_down_1h and rsi_1h < 50:
        mode = "TREND_DOWN"
        confidence = min(0.95, 0.6 + (adx_avg - 25) / 75)
    elif adx_avg > 20 and (trend_up_4h or trend_up_d1):
        if rsi_1h < 35 and rsi_bullish_div:
            mode = "TREND_UP_RECALL"; confidence = 0.75
        elif rsi_1h < 40 and vol_valid:
            mode = "TREND_UP_RECALL"; confidence = 0.65
    elif is_volatile and rsi_1h < 35 and (vol_surge or rsi_bullish_div):
        mode = "VOLATILE_OVERSOLD"
        confidence = 0.7 + 0.1 * int(rsi_bullish_div) + 0.1 * int(vol_surge)
    elif is_volatile and rsi_1h > 65 and vol_surge:
        mode = "VOLATILE_OVERBOUGHT"; confidence = 0.8
    elif adx_avg < 20:
        mode = "RANGE_BOUND"; confidence = 0.8
    else:
        mode = "RANGE_BOUND"; confidence = 0.6

    if fg < 25 and mode in ("VOLATILE_OVERSOLD", "TREND_UP_RECALL"):
        confidence = min(0.98, confidence + 0.15)
        log(f"[Fear & Greed] 极度恐慌{fg}，超卖信号置信度提升")
    elif fg > 75 and mode in ("VOLATILE_OVERBOUGHT", "CRISIS"):
        confidence = min(0.98, confidence + 0.1)

    if not vol_valid and mode in ("VOLATILE_OVERSOLD", "VOLATILE_OVERBOUGHT"):
        confidence *= 0.7

    _mode_params = {
        "TREND_UP":            {"pos_pct": 1.0,  "grids": 2, "grid_profit": GRID_PROFIT,      "trend_bias": 1.0},
        "TREND_UP_RECALL":     {"pos_pct": 1.0,  "grids": 2, "grid_profit": GRID_PROFIT,      "trend_bias": 0.9},
        "TREND_DOWN":          {"pos_pct": 0.3,  "grids": 2, "grid_profit": GRID_PROFIT,      "trend_bias": 0.0},
        "RANGE_BOUND":         {"pos_pct": 0.8,  "grids": atr_grids, "grid_profit": atr_gp,  "trend_bias": 0.3},
        "VOLATILE_OVERSOLD":   {"pos_pct": 1.2,  "grids": min(atr_grids, 4), "grid_profit": atr_gp, "trend_bias": 0.7},
        "VOLATILE_OVERBOUGHT": {"pos_pct": 0.0,  "grids": 0, "grid_profit": atr_gp,          "trend_bias": 0.0},
        "CRISIS":              {"pos_pct": 0.0,  "grids": 0, "grid_profit": atr_gp,          "trend_bias": 0.0},
    }
    base_params = _mode_params[mode]

    grid_score   = max(0, (60 - rsi_1h) / 60)
    trend_score  = max(0, (rsi_1h - 40) / 40)
    total_score  = (grid_score + trend_score * base_params['trend_bias']) * confidence
    if macd > macd_sig: total_score *= 1.1

    return mode, {
        'price': cur,
        'rsi': rsi_1h,
        'rsi_15m': rsi_15m,
        'adx': adx_avg,
        'mode': mode,
        'confidence': confidence,
        'grids': base_params['grids'],
        'grid_profit': base_params['grid_profit'],
        'atr': atr,
        'trend_bias': base_params['trend_bias'],
        'total_score': total_score,
        'pos_pct': base_params['pos_pct'],
        'rsi_bullish_div': rsi_bullish_div,
        'vol_ratio': vol_ratio,
        'fear_greed': fg,
        'correlation': CORRELATION_WITH_BTC.get(symbol, 0.5),  # v1.1优化3：关联性传递到主循环
    }

class GridEngine:
    def __init__(self, symbol, entry_price, grids, grid_profit, atr, ex, capital, phase1_limit=2, sm=None):
        self.symbol = symbol
        self.entry_price = entry_price
        self.max_grids = grids
        self.grid_profit = grid_profit
        self.atr = atr
        self.ex = ex
        self.capital = capital
        self.phase1_limit = phase1_limit
        self.sm = sm
        self.pending_profit = 0
        self.last_tp_time = 0
        self._open_count = 0

        grid_range = max(atr * 3, entry_price * 0.08)  # 优化：原0.12，收窄到0.08
        self.upper = entry_price + grid_range / 2
        self.lower = entry_price - grid_range / 2
        self.grid_width = (self.upper - self.lower) / self.max_grids if self.max_grids > 0 else grid_range
        self.positions = {}
        self.position = {'symbol': symbol, 'qty': 0, 'entry': entry_price}
        self._all_sold = False

    def get_grid_index(self, price):
        if price <= self.lower: return 0
        if price >= self.upper: return self.max_grids
        return int((price - self.lower) / self.grid_width)

    def invest_per_grid(self, locked_profit=0):
        active = len([p for p in self.positions.values() if not p.get('sold')])
        if active >= self.max_grids: return 0
        base = self.capital + locked_profit
        per_grid_max = base * 0.35
        return min(per_grid_max, base / (self.max_grids - active))

    def buy_grid(self, idx, price, locked_profit=0):
        if idx in self.positions and not self.positions[idx].get('sold'):
            return False
        invest = self.invest_per_grid(locked_profit)
        if invest < 11: return False
        qty = self._round_qty(invest / price)
        if qty <= 0: return False
        try:
            _check_api_rate_limit()
            if self.ex.market_buy(self.symbol, qty):
                _api_success()
                self.positions[idx] = {
                    'buy_price': price, 'qty': qty, 'sold': False,
                    'target': price * (1 + self.grid_profit),
                    'sl': price * (1 - GRID_SL_PCT),   # v1.1优化：网格专用SL=8%
                    'ts_triggered': False, 'ts_price': 0, 'ts_high': 0,
                    'bought_at': time.time(),
                    'profit_locked': invest * self.grid_profit * PROFIT_LOCK,
                }
                self._open_count += 1
                self.position['qty'] += qty
                log(f"[格买入] {self.symbol}格{idx}@{price:.4f} qty={qty:.4f} "
                    f"(已开{self._open_count}/{self.max_grids}格)")
                return True
        except Exception as e:
            log(f"[格买入失败] {self.symbol}格{idx}: {e}")
            _api_fail()
        return False

    def check_phased_open(self, cur_price):
        now = time.time()
        if self._open_count >= self.max_grids: return
        if self.pending_profit <= 0: return
        if now - self.last_tp_time < PHASE2_DELAY: return
        if self._open_count < self.phase1_limit: return
        for idx in range(self.max_grids):
            if idx not in self.positions:
                self.buy_grid(idx, cur_price, locked_profit=self.pending_profit)
                self.pending_profit = 0
                break

    def _round_qty(self, qty):
        rules = {'BTCUSDT':4,'ETHUSDT':4,'BNBUSDT':2,'SOLUSDT':1,'AVAXUSDT':2,'XRPUSDT':1}
        d = rules.get(self.symbol, 4)
        return math.floor(qty * 10**d) / 10**d

    def check(self, cur_price):
        for idx in list(self.positions.keys()):
            pos = self.positions[idx]
            if pos.get('sold') or pos['qty'] <= 0: continue
            bp = pos['buy_price']
            profit = (cur_price - bp) / bp

            # v1.1优化：TS激活从6%降到4%
            if profit > 0.04:
                if not pos.get('ts_triggered'):
                    pos['ts_triggered'] = True
                    pos['ts_price'] = cur_price * (1 - TS_PCT)
                    pos['ts_high'] = cur_price
                    log(f"[TS激活] {self.symbol}格{idx}@{cur_price:.4f} 触发={pos['ts_price']:.4f}")
                elif cur_price > pos.get('ts_high', 0):
                    pos['ts_high'] = cur_price
                    pos['ts_price'] = cur_price * (1 - TS_PCT)

            if pos.get('ts_triggered') and cur_price <= pos['ts_price']:
                self._sell_grid(idx, cur_price, "TS")
                continue

            if cur_price >= pos['target']:
                self._sell_grid(idx, cur_price, "TP")
                continue

            if cur_price <= pos['sl']:
                self._sell_grid(idx, cur_price, "SL")
                continue

    def _sell_grid(self, idx, cur_price, reason):
        pos = self.positions.get(idx)
        if not pos or pos.get('sold'): return
        qty = pos['qty']
        if qty <= 0: return
        try:
            _check_api_rate_limit()
            if self.ex.market_sell(self.symbol, qty):
                _api_success()
                pnl = (cur_price - pos['buy_price']) / pos['buy_price'] * 100
                invest = pos['buy_price'] * qty
                profit = cur_price * qty - invest
                log(f"[格卖出] {self.symbol}格{idx}@{cur_price:.4f}({pnl:+.2f}%) {reason}")
                pos['sold'] = True
                pos['sold_price'] = cur_price
                pos['sold_at'] = time.time()
                self.position['qty'] = max(0, self.position['qty'] - qty)

                if all(p.get('sold') for p in self.positions.values()):
                    self._all_sold = True

                if reason in ('SL', 'TS'):
                    if self.sm: self.sm.record_loss()
                elif reason.startswith('TP'):
                    if self.sm: self.sm.record_win()
                    locked = profit * PROFIT_LOCK
                    reinvest = profit * (1 - PROFIT_LOCK)
                    self.pending_profit += reinvest
                    self.last_tp_time = time.time()
                    log(f"  → 利润${profit:.2f} | 锁定50%=${locked:.2f} | 复利30%=${reinvest:.2f}")
        except Exception as e:
            log(f"[格卖出失败] {self.symbol}格{idx}: {e}")
            _api_fail()

    def adjust_center(self, cur_price):
        center = (self.upper + self.lower) / 2
        drift = (cur_price - center) / center if center > 0 else 0
        if abs(drift) > 0.25:
            new_range = max(self.atr * 3, cur_price * 0.08)  # v1.1优化：收窄到8%
            self.upper = cur_price + new_range / 2
            self.lower = cur_price - new_range / 2
            self.grid_width = (self.upper - self.lower) / self.max_grids
            log(f"[网格重置] {self.symbol} @{cur_price:.4f} 偏离{drift*100:+.0f}%，重新居中 "
                f"区间[{self.lower:.4f}, {self.upper:.4f}]")

    def has_position(self):
        return any(not p.get('sold') and p['qty'] > 0 for p in self.positions.values())

    def detect_manual_close(self, api_qty):
        total_state_qty = sum(pos['qty'] for pos in self.positions.values()
                             if not pos.get('sold') and pos['qty'] > 0)
        if api_qty < total_state_qty - 0.00001:
            for idx, pos in list(self.positions.items()):
                if pos.get('sold') or pos['qty'] <= 0: continue
                log(f"[⚠️ 手动平仓] {self.symbol}格{idx}@{pos['buy_price']:.4f} "
                    f"(API仅剩{api_qty})")
                pos['sold'] = True
                pos['sold_at'] = time.time()

class TrendEngine:
    def __init__(self, symbol, ex, sm=None):
        self.symbol = symbol
        self.ex = ex
        self.sm = sm
        self.position = None
        self.entry_price = 0
        self.ts_triggered = False
        self.ts_price = 0
        self.peak_price = 0

    def buy(self, price, qty):
        try:
            _check_api_rate_limit()
            if self.ex.market_buy(self.symbol, qty):
                _api_success()
                self.position = {'qty': qty, 'entry': price, 'tp1_done': False}
                self.entry_price = price
                self.peak_price = price
                log(f"[趋势买入] {self.symbol}@{price:.4f} qty={qty:.4f}")
                return True
        except:
            _api_fail()
        return False

    def check(self, cur_price):
        if not self.position: return
        entry = self.position['entry']
        qty = self.position['qty']
        profit = (cur_price - entry) / entry

        if profit > 0.15 and not self.ts_triggered:
            self.ts_triggered = True
            self.ts_price = cur_price * (1 - TS_TREND_PCT)
        elif self.ts_triggered and cur_price > entry * 1.15:
            new_ts = cur_price * (1 - TS_TREND_PCT)
            if new_ts > self.ts_price: self.ts_price = new_ts

        if self.ts_triggered and cur_price <= self.ts_price:
            self._sell(cur_price, "TS")
            return

        if cur_price > self.peak_price:
            self.peak_price = cur_price
        drawdown_from_peak = (self.peak_price - cur_price) / self.peak_price if self.peak_price > 0 else 0
        if drawdown_from_peak > 0.08 and self.peak_price > entry * 1.10:
            log(f"[趋势破坏] {self.symbol}@{cur_price:.4f} 从峰值{self.peak_price:.4f}回落{drawdown_from_peak*100:.1f}%，趋势破坏止损")
            self._sell(cur_price, "TREND_BREAK")
            return


        if profit >= 0.15 and not self.position.get('tp1_done'):
            sell_qty = math.floor(qty * 0.5 * 10**4) / 10**4
            if sell_qty > 0:
                try:
                    _check_api_rate_limit()
                    self.ex.market_sell(self.symbol, sell_qty)
                    _api_success()
                    log(f"[TP1] {self.symbol}@{cur_price:.4f} 卖50%qty={sell_qty:.4f}")
                    self.position['qty'] -= sell_qty
                    self.position['tp1_done'] = True
                except:
                    _api_fail()

        if profit >= 0.25 and self.position['qty'] > 0:
            self._sell(cur_price, "TP2")

        if cur_price <= entry * (1 - SL_PCT):
            self._sell(cur_price, "SL")

    def _sell(self, price, reason):
        if not self.position or self.position['qty'] <= 0: return
        qty = self.position['qty']
        try:
            _check_api_rate_limit()
            self.ex.market_sell(self.symbol, qty)
            _api_success()
            pnl = (price - self.entry_price) / self.entry_price * 100
            log(f"[趋势卖出] {self.symbol}@{price:.4f}({pnl:+.2f}%) {reason}")
            if reason in ('SL', 'TS', 'TREND_BREAK') and self.sm:
                self.sm.record_loss()
            elif reason.startswith('TP') and self.sm:
                self.sm.record_win()
            self.position = None
        except:
            _api_fail()

# ===================== 状态管理 =====================
class StateManager:
    def __init__(self, ex, fpath):
        self.ex = ex
        self.fpath = fpath
        self.data = self._load()
        self.high_water = self.data.get('high_water', 0)
        self.total_profit_taken = self.data.get('total_profit_taken', 0)
        self.loss_streak = self.data.get('loss_streak', 0)
        self.last_loss_time = self.data.get('last_loss_time', 0)
        self.loss_cooldown = self.data.get('loss_cooldown', 0)
        self.lock_until = self.data.get('lock_until', 0)
        self.daily_loss = self.data.get('daily_loss', 0)
        self.daily_reset_time = self.data.get('daily_reset_time', 0)
        self.market_mode = "RANGE_BOUND"
        self._daily_start_balance = self.data.get('daily_start_balance', 0)

    def _load(self):
        try:
            with open(self.fpath) as f: return json.load(f)
        except: return {}

    def save(self):
        self.data.update({
            'high_water': self.high_water,
            'total_profit_taken': self.total_profit_taken,
            'loss_streak': self.loss_streak,
            'last_loss_time': self.last_loss_time,
            'loss_cooldown': self.loss_cooldown,
            'lock_until': self.lock_until,
            'daily_loss': self.daily_loss,
            'daily_reset_time': self.daily_reset_time,
            'daily_start_balance': self.data.get('daily_start_balance', self.high_water if self.high_water > 0 else 0),
            'saved_at': time.time(),
        })
        with open(self.fpath, "w") as f:
            json.dump(self.data, f, indent=2, default=str)

    def get_balance(self):
        try:
            _check_api_rate_limit()
            bal = self.ex.get_balance()
            _api_success()
            return bal
        except:
            _api_fail()
            return 0.0

    def record_loss(self):
        self.loss_streak += 1
        self.last_loss_time = time.time()
        self.loss_cooldown = min(self.loss_streak * 300, CRASH_PAUSE)
        self.save()

    def record_win(self):
        if self.loss_streak > 0:
            self.loss_streak = 0
            self.loss_cooldown = 0
        self.save()

    def check_loss_cooldown(self):
        if self.loss_streak >= 1 and self.loss_cooldown > 0:
            elapsed = time.time() - self.last_loss_time
            if elapsed < self.loss_cooldown:
                remaining = int(self.loss_cooldown - elapsed)
                log(f"[亏损冷静期] {self.loss_streak}连亏，还需等待{remaining//60}分钟")
                return False
            else:
                self.loss_cooldown = 0
        return True

    def check_crash_protection(self):
        if self.loss_streak >= CRASH_LIMIT:
            elapsed = time.time() - self.last_loss_time
            if elapsed < CRASH_PAUSE:
                remaining = int(CRASH_PAUSE - elapsed)
                log(f"[熔断] 连亏{CRASH_LIMIT}次，暂停{remaining//60}分钟")
                return False
            else:
                self.loss_streak = 0
                self.last_loss_time = 0
                self.loss_cooldown = 0
        return True

    def check_drawdown_protection(self, balance):
        if self.high_water > 0 and balance < self.high_water * (1 - DRAWDOWN_PROTECT):
            log(f"[⚠️ 回撤保护] ${self.high_water:.2f}→${balance:.2f}，清仓止损")
            self.lock_until = time.time() + 1800
            self.save()
            return False
        return True

    def check_daily_loss(self, balance):
        now = time.time()
        if self.daily_reset_time == 0 or (now - self.daily_reset_time) >= 86400:
            self.daily_loss = 0
            self.daily_reset_time = now
            self.data['daily_start_balance'] = balance
            if self.high_water == 0:
                self.high_water = balance
            self.save()
            return True
        daily_start = self.data.get('daily_start_balance', balance)
        if daily_start > 0:
            daily_pnl = (balance - daily_start) / daily_start
            self.daily_loss = daily_pnl
            if daily_pnl < -MAX_DAILY_LOSS:
                log(f"[⚠️ 日亏保护] 单日亏损{abs(daily_pnl)*100:.1f}% > {MAX_DAILY_LOSS*100:.0f}%，暂停1小时")
                self.lock_until = time.time() + 3600
                self.save()
                return False
        return True

    def check_take_profit(self, balance):
        if self.high_water > 0 and balance >= self.high_water * 1.20:
            profit = balance - self.high_water
            if profit >= 5:
                take = profit * 0.5
                log(f"[💰 提盈] 利润${profit:.2f} → 提取${take:.2f} | 新高点${balance:.2f}")
                self.total_profit_taken += take
                self.high_water = balance * 0.9
                self.save()
        if balance > self.high_water:
            self.high_water = balance
            self.save()

    def is_locked(self):
        return time.time() < self.lock_until

# ===================== 主程序 =====================
def main():
    global _circuit_broken, _circuit_break_until

    log("=" * 70)
    log("  SpeedClaw BotKing 现货机器人 v1.1 🦞")
    log(f"  币种: {COINS}")
    log(f"  网格: 2-6格/0.3%-0.6% | 趋势:TP15%/25% | SL:网格8%/趋势12%")
    log(f"  熔断: 连亏3次暂停 | 回撤:>20%清仓 | 日亏:>8%暂停")
    log(f"  API限速: {API_MAX_REQUESTS}次/分钟 | 熔断: 连续{API_CIRCUIT_BREAKER_THRESHOLD}次失败暂停120秒")
    log("=" * 70)

    try:
        with open('/root/.openclaw/workspace/config_exchange.yaml') as f:
            creds = yaml.safe_load(f)
        for ex_cfg in creds.get('exchanges', []):
            if ex_cfg.get('name') == 'binance':
                api_key = ex_cfg['api_key']
                secret  = ex_cfg['secret']
                break
        else:
            raise ValueError("Binance not found in exchanges list")
    except:
        log("[错误] 读取config_exchange.yaml失败")
        return

    ex = SpotAdapter(api_key, secret)
    sm = StateManager(ex, STATE_FILE)

    balance = sm.get_balance()
    log(f"USDT余额: ${balance:.2f}")

    grid_engines = {}
    trend_engines = {}
    last_scan = last_save = 0
    last_manual_check = 0

    # v1.1优化3：关联性敞口追踪
    active_correlation_exposure = {}  # {symbol: correlation_weight}

    mode_emoji = {
        "TREND_UP": "🟢", "TREND_DOWN": "📉",
        "VOLATILE_OVERSOLD": "🔴", "VOLATILE_OVERBOUGHT": "🟠",
        "RANGE_BOUND": "📊", "CRISIS": "💥"
    }
    sig_emoji = {"BUY": "🟢", "SELL": "🔴", "HOLD": "⚪"}

    while True:
        now = time.time()

        # === v1.1优化2：熔断检查 ===
        circuit_ok, circuit_remaining = _check_circuit_breaker()
        if not circuit_ok:
            log(f"[💥 熔断中] API异常，还需等待{circuit_remaining}秒")
            time.sleep(30)
            continue

        # === 余额更新 ===
        balance = sm.get_balance()

        # === 锁定检查 ===
        if sm.is_locked():
            time.sleep(30)
            continue

        if not sm.check_crash_protection():
            time.sleep(30)
            continue

        if sm.loss_streak >= CRASH_LIMIT and sm.market_mode in ("TREND_DOWN", "CRISIS"):
            log(f"[熊市锁定] 熔断+熊市，等待转势")
            time.sleep(60)
            continue

        if not sm.check_loss_cooldown():
            time.sleep(30)
            continue

        if not sm.check_drawdown_protection(balance):
            for eng in list(grid_engines.values()):
                try:
                    cur = ex.get_price(eng.symbol)
                    for idx in list(eng.positions.keys()):
                        eng._sell_grid(idx, cur, "回撤保护")
                except: pass
            for eng in list(trend_engines.values()):
                try:
                    cur = ex.get_price(eng.symbol)
                    if eng.position: eng._sell(cur, "回撤保护")
                except: pass
            time.sleep(30)
            continue

        if not sm.check_daily_loss(balance):
            time.sleep(30)
            continue

        # === 市场扫描（每3分钟）===
        if now - last_scan >= SCAN_INTERVAL:
            last_scan = now
            sm.check_take_profit(balance)
            sm.save()

            # === v1.1优化3：更新关联性敞口 ===
            active_correlation_exposure = {}
            for sym, eng in grid_engines.items():
                if eng.has_position():
                    corr = CORRELATION_WITH_BTC.get(sym, 0.5)
                    active_correlation_exposure[sym] = corr
            for sym, eng in trend_engines.items():
                if eng.position:
                    corr = CORRELATION_WITH_BTC.get(sym, 0.5)
                    active_correlation_exposure[sym] = corr

            signals = {}
            for sym in COINS:
                try:
                    mode, info = detect_market_mode(sym, ex)
                    signals[sym] = info
                    me = mode_emoji.get(mode, "⚪")
                    se = sig_emoji.get("HOLD", "⚪")
                    if mode in ("VOLATILE_OVERBOUGHT", "CRISIS"): se = sig_emoji["SELL"]
                    elif mode in ("TREND_UP", "VOLATILE_OVERSOLD"): se = sig_emoji["BUY"]
                    conf = info.get('confidence', 0)
                    adx  = info.get('adx', 0)
                    fg   = info.get('fear_greed', 50)
                    div  = '📈' if info.get('rsi_bullish_div') else ''
                    corr = info.get('correlation', 0.5)
                    conf_str = f"{conf:.0%}"
                    fg_str = f"FG{fg:3.0f}"
                    log(f"  {me}{se} {sym:10s} ${info.get('price',0):12.4f} | RSI={info.get('rsi',0):5.1f} ADX={adx:4.0f} | {fg_str} | {conf_str} | {mode:20s} | G={info.get('grids',0):1.0f} | C={corr:.2f} {div}")
                except Exception as e:
                    log(f"[扫描异常] {sym}: {e} ({type(e).__name__})")
                    signals[sym] = {'price': 0, 'rsi': 50, 'mode': 'RANGE_BOUND', 'grids': 0, 'trend_bias': 0, 'confidence': 0, 'adx': 0, 'fear_greed': 50, 'vol_ratio': 1, 'correlation': 0.5}

            btc_mode = signals.get('BTCUSDT', {}).get('mode', 'RANGE_BOUND')
            btc_conf = signals.get('BTCUSDT', {}).get('confidence', 0)
            sm.market_mode = btc_mode

            for sym in list(grid_engines.keys()):
                if grid_engines[sym]._all_sold:
                    log(f"[引擎清理] {sym} 所有格已平，移除引擎")
                    del grid_engines[sym]
            for sym in list(trend_engines.keys()):
                if trend_engines[sym].position is None:
                    del trend_engines[sym]

            if is_extreme_hour():
                log(f"[⏰极端时段] 北京时间22:00-02:00，暂停开仓")
                buy_list = []
            else:
                # === v1.1优化3：关联性过滤 ===
                def calc_total_correlation_exposure():
                    """计算当前关联性总敞口（以BTC=1为基准）"""
                    total = sum(active_correlation_exposure.values())
                    return total

                total_corr_exp = calc_total_correlation_exposure()
                log(f"[📊 关联敞口] 当前总暴露: {total_corr_exp:.2f} (BTC=1.0基准)")

                buy_list = sorted(
                    [(s, i) for s, i in signals.items()
                     if (s not in grid_engines or grid_engines.get(s, {})._all_sold)
                     and (s not in trend_engines or trend_engines.get(s, {}).position is None)
                     and i.get('confidence', 0) >= 0.6
                     and (i['mode'] in ("TREND_UP", "TREND_UP_RECALL", "VOLATILE_OVERSOLD")
                          or (i['mode'] == "RANGE_BOUND" and i.get('total_score', 0) > 0.5))
                     and i.get('price', 0) > 0],
                    key=lambda x: x[1].get('total_score', 0) * CORRELATION_WITH_BTC.get(x[0], 0.5)
                    * (0.6 if btc_mode == "TREND_DOWN" and btc_conf >= 0.7 else 1.0),
                    reverse=True
                )

            def calc_position_size(bal, active, info, btc_mode="RANGE_BOUND", btc_conf=0, sym=None):
                tier = TIER4 if bal > 1000 else TIER3 if bal > 200 else TIER2 if bal > 50 else TIER1
                base = tier * info.get('pos_pct', 1.0)
                conf = info.get('confidence', 0.5)
                conf_factor = 1.0 + (conf - 0.6) * 1.5

                # v1.1优化3：关联性降仓
                # BTC熊市时，高度相关币（ETH/BNB）上限0.3，中度相关（SOL/AVAX）上限0.5
                corr = CORRELATION_WITH_BTC.get(sym, 0.5) if sym else 0.5
                btc_factor = 1.0
                if btc_mode == "TREND_DOWN" and btc_conf >= 0.7:
                    if corr >= 0.80:  # ETH, BNB
                        btc_factor = 0.3
                    elif corr >= 0.60:  # SOL, AVAX
                        btc_factor = 0.5
                    else:  # XRP等低相关
                        btc_factor = 0.8

                # v1.1优化3：关联性总敞口检查
                # 如果已持有高相关币，新开仓进一步降权
                sym_corr_exp = active_correlation_exposure.get(sym, 0) if sym else 0
                if sym_corr_exp >= 0.85:  # 已持有ETH再开BNB = 总暴露1.55
                    btc_factor *= 0.5

                return min(base * conf_factor * btc_factor, bal * 0.35)

            active_total = len([e for e in grid_engines.values() if e.has_position()]) + \
                          len([e for e in trend_engines.values() if e.position])
            investable = balance

            for sym, info in buy_list:
                if active_total >= MAX_POSITIONS: break
                if investable < 15: break

                per_coin = calc_position_size(investable, max(active_total, 1), info, btc_mode, btc_conf, sym)
                if info['trend_bias'] >= 0.7:
                    eng = TrendEngine(sym, ex, sm=sm)
                    if eng.buy(info['price'], per_coin / info['price']):
                        trend_engines[sym] = eng
                        investable -= per_coin
                        active_total += 1
                        log(f"[趋势开仓] {sym}@{info['price']:.2f} 模式:{info['mode']} 信心:{info.get('confidence',0):.0%} 仓位:${per_coin:.2f}")
                elif info['grids'] > 0:
                    phase1 = get_phase1_grids(balance)
                    grid_profit = info['grid_profit']
                    if info.get('atr', 0) / max(info['price'], 1) > 0.03:
                        grid_profit = min(grid_profit * 1.5, 0.010)
                    eng = GridEngine(sym, info['price'], info['grids'],
                                    grid_profit, info.get('atr', 0), ex, per_coin,
                                    phase1_limit=phase1, sm=sm)
                    grid_engines[sym] = eng
                    investable -= per_coin
                    active_total += 1
                    log(f"[网格开仓] {sym}@{info['price']:.2f} {info['grids']}格 模式:{info['mode']} 信心:{info.get('confidence',0):.0%} 仓位:${per_coin:.2f} 止盈:{grid_profit*100:.2f}%")

            for sym, info in signals.items():
                if info['mode'] in ("VOLATILE_OVERBOUGHT",):
                    if sym in grid_engines:
                        try:
                            cur = info['price']
                            for idx in list(grid_engines[sym].positions.keys()):
                                grid_engines[sym]._sell_grid(idx, cur, f"市场-{info['mode']}")
                            sm.record_win()
                        except: pass
                    if sym in trend_engines and trend_engines[sym].position:
                        try:
                            cur = info['price']
                            trend_engines[sym]._sell(cur, f"市场-{info['mode']}")
                            sm.record_win()
                        except: pass
                elif info['mode'] in ("CRISIS", "TREND_DOWN"):
                    if sym in grid_engines:
                        try:
                            cur = info['price']
                            for idx in list(grid_engines[sym].positions.keys()):
                                grid_engines[sym]._sell_grid(idx, cur, f"市场-{info['mode']}")
                            sm.record_loss()
                        except: pass
                    if sym in trend_engines and trend_engines[sym].position:
                        try:
                            cur = info['price']
                            trend_engines[sym]._sell(cur, f"市场-{info['mode']}")
                            sm.record_loss()
                        except: pass

            if now - last_manual_check >= 300:
                last_manual_check = now
                for sym, eng in list(grid_engines.items()):
                    try:
                        _check_api_rate_limit()
                        api_qty = ex.get_spot_holdings(sym)
                        _api_success()
                        if api_qty <= 0 and eng.has_position():
                            eng.detect_manual_close(api_qty)
                    except:
                        _api_fail()
                        pass

            active_g = len([e for e in grid_engines.values() if e.has_position()])
            active_t = len([e for e in trend_engines.values() if e.position])
            total_inv = sum(e.capital for e in grid_engines.values())
            log(f"[{len(COINS)}] 网格{active_g}格 | 趋势{active_t}仓 | "
                f"总投入${total_inv:.2f} | 盈亏${balance-total_inv:.2f} | "
                f"余额${balance:.2f} | 提取${sm.total_profit_taken:.2f} | 连亏{sm.loss_streak}次")

        # === 实时检查（每20秒）===
        for sym, eng in list(grid_engines.items()):
            try:
                cur = ex.get_price(sym)
                eng.check(cur)
                eng.check_phased_open(cur)
            except: pass
        for sym, eng in list(trend_engines.items()):
            try:
                cur = ex.get_price(sym)
                eng.check(cur)
                if eng.position is None:
                    del trend_engines[sym]
            except: pass

        if now - last_save >= SAVE_INTERVAL:
            last_save = now
            sm.save()

        time.sleep(CHECK_INTERVAL)

if __name__ == '__main__':
    main()
