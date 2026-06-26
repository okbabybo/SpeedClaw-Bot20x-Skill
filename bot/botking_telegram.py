#!/usr/bin/env python3
"""
BotKing Telegram Bot 控制面板
==============================
通过Telegram控制BotKing现货机器人
- 查看状态/启停机器人/查看持仓/余额/接收通知

用法:
  1. 在 @BotFather 创建机器人,获取TOKEN
  2. 设置环境变量: export TELEGRAM_TOKEN=xxx
  3. python3 botking_telegram.py

依赖: pip install python-telegram-bot flask
"""
import os
import sys
import json
import time
import asyncio
import subprocess
import requests
from pathlib import Path
from datetime import datetime
from flask import Flask, jsonify, request
from threading import Thread

# ===================== 配置 =====================
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN', '')
ADMIN_CHAT_ID = int(os.environ.get('ADMIN_CHAT_ID', '0'))
STATE_FILE = Path('/root/.openclaw/workspace/bot_king_state.json')
LOG_FILE = Path('/root/.openclaw/workspace/bot_king.log')

# Bot20x 配置
BOT20X_STATE_FILE = Path('/root/.openclaw/workspace/binance_state.json')
BOT20X_LOG_FILE = Path('/root/.openclaw/workspace/binance_v40.log')  # 或实际日志路径

# 实时API配置 (老板的币安账户)
BOT20X_API_KEY = "QccKkNLbtV61rJpOms4h2E0RWoZMfMhG2ar3v9tueF5kbQ6KkN4sUf5CFLLkMhzx"
BOT20X_SECRET = "Q549z4g3QlOnVs0PDSCzW6Xy2nVt9763DMqWo64MLLDoUeV8MigrUGUQn2nZTDuU"
BOT20X_SYMBOLS = ['BTCUSDT', 'ETHUSDT']  # Bot20x实际交易币种

# 权限管理
import sys
sys.path.insert(0, str(Path(__file__).parent))
from botking_auth import (
    load_users, save_users, get_user_level,
    register_user, generate_activation_code, activate_code,
    bind_api, get_user_api, list_users, is_owner, is_admin,
    OWNER_TELEGRAM_ID,
)


# ===================== 工具函数 =====================
def log(msg):
    ts = datetime.now().strftime('%m/%d %H:%M:%S')
    print(f"[{ts}] {msg}", flush=True)


def read_state():
    if not STATE_FILE.exists():
        return {}
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except Exception as e:
        log(f"读取状态失败: {e}")
        return {}


def get_pm2_status():
    try:
        result = subprocess.run(
            ['pm2', 'jlist'],
            capture_output=True, text=True, timeout=5
        )
        procs = json.loads(result.stdout)
        for p in procs:
            if p.get('name') == 'bot-king':
                return {
                    'running': p.get('pm2_env', {}).get('status') == 'online',
                    'pid': p.get('pid'),
                    'uptime': p.get('pm2_env', {}).get('pm_uptime', 0),
                    'restart_count': p.get('pm2_env', {}).get('restart_time', 0),
                    'memory': p.get('memory', 0) / 1024 / 1024,
                    'cpu': p.get('cpu', 0),
                }
    except Exception as e:
        log(f"PM2状态获取失败: {e}")
    return {'running': False}


def tail_log(n=20):
    if not LOG_FILE.exists():
        return "日志文件不存在"
    try:
        with open(LOG_FILE) as f:
            lines = f.readlines()
        return ''.join(lines[-n:])
    except Exception as e:
        return f"读取日志失败: {e}"


def read_bot20x_state():
    if not BOT20X_STATE_FILE.exists():
        return {}
    try:
        with open(BOT20X_STATE_FILE) as f:
            return json.load(f)
    except Exception as e:
        log(f"读取Bot20x状态失败: {e}")
        return {}


def get_bot20x_status():
    try:
        result = subprocess.run(['pm2', 'jlist'], capture_output=True, text=True, timeout=5)
        procs = json.loads(result.stdout)
        for p in procs:
            if p.get('name') == 'bot20x':
                return {
                    'running': p.get('pm2_env', {}).get('status') == 'online',
                    'pid': p.get('pid'),
                    'uptime': p.get('pm2_env', {}).get('pm_uptime', 0),
                    'restart_count': p.get('pm2_env', {}).get('restart_time', 0),
                    'memory': p.get('memory', 0) / 1024 / 1024,
                    'cpu': p.get('cpu', 0),
                }
    except Exception as e:
        log(f"Bot20x PM2状态获取失败: {e}")
    return {'running': False}


def tail_bot20x_log(n=20):
    if not BOT20X_LOG_FILE.exists():
        return "Bot20x日志文件不存在"
    try:
        with open(BOT20X_LOG_FILE) as f:
            lines = f.readlines()
        return ''.join(lines[-n:])
    except Exception as e:
        return f"读取Bot20x日志失败: {e}"


# ===================== Bot20x 实时API查询 =====================
_binance_adapter = None

def get_binance_adapter():
    """获取币安适配器(单例)"""
    global _binance_adapter
    if _binance_adapter is None:
        import sys
        sys.path.insert(0, '/root/.openclaw/workspace')
        from exchange_adapter import BinanceAdapter
        _binance_adapter = BinanceAdapter(BOT20X_API_KEY, BOT20X_SECRET)
    return _binance_adapter


def fetch_bot20x_positions_realtime():
    """实时查询Bot20x持仓 (调用Binance API)"""
    try:
        adapter = get_binance_adapter()
        positions = []
        for symbol in BOT20X_SYMBOLS:
            pos = adapter.get_positions(symbol)
            if pos:
                for side_key, info in pos.items():
                    if info.get('qty', 0) != 0:
                        positions.append({
                            'symbol': symbol,
                            'side': info.get('dir', side_key),
                            'qty': info.get('qty', 0),
                            'entry': info.get('entry', 0),
                        })
        return positions, None
    except Exception as e:
        return [], str(e)


def fetch_bot20x_balance_realtime():
    """实时查询Bot20x余额 (调用Binance API)"""
    try:
        adapter = get_binance_adapter()
        balance = adapter.get_balance()
        return balance, None
    except Exception as e:
        return 0.0, str(e)


def fetch_bot20x_full_realtime(api_key=None, api_secret=None):
    """一次性查询余额+所有持仓+未实现盈亏"""
    # 如果未传api_key,用全局默认(老板的)
    if not api_key or not api_secret:
        api_key = BOT20X_API_KEY
        api_secret = BOT20X_SECRET

    try:
        import requests as req
        import time as _t
        import hmac as _hm
        import hashlib as _hl
        base = "https://fapi.binance.com"
        ts = str(int(_t.time() * 1000))
        query = f"timestamp={ts}"
        sig = _hm.new(api_secret.encode(), query.encode(), _hl.sha256).hexdigest()
        url = f"{base}/fapi/v2/account?{query}&signature={sig}"
        r = req.get(url, headers={"X-MBX-APIKEY": api_key}, timeout=10).json()

        balance = float(r.get('availableBalance', 0))
        unrealized = float(r.get('totalUnrealizedProfit', 0))
        margin_used = float(r.get('totalInitialMargin', 0))
        wallet_total = float(r.get('totalWalletBalance', 0))

        # 查询持仓
        positions = []
        for sym in BOT20X_SYMBOLS:
            ts2 = str(int(_t.time() * 1000))
            q2 = f"symbol={sym}&timestamp={ts2}"
            sig2 = _hm.new(api_secret.encode(), q2.encode(), _hl.sha256).hexdigest()
            url2 = f"{base}/fapi/v2/positionRisk?{q2}&signature={sig2}"
            data = req.get(url2, headers={"X-MBX-APIKEY": api_key}, timeout=10).json()
            if isinstance(data, list):
                for p in data:
                    amt = float(p.get('positionAmt', 0))
                    if amt != 0:
                        side = 'LONG' if amt > 0 else 'SHORT'
                        positions.append({
                            'symbol': p['symbol'],
                            'side': side,
                            'qty': abs(amt),
                            'entry': float(p.get('entryPrice', 0)),
                            'mark': float(p.get('markPrice', 0)),
                            'pnl': float(p.get('unRealizedProfit', 0)),
                            'leverage': int(float(p.get('leverage', 1))),
                            'marginType': p.get('marginType', 'cross'),
                        })

        return {
            'balance': balance,
            'unrealized': unrealized,
            'wallet_total': wallet_total,
            'margin_used': margin_used,
            'positions': positions,
            'total_equity': balance + unrealized,
        }, None
    except Exception as e:
        return None, str(e)


def send_long_message(update, text):
    """发送长消息，自动分段(Telegram限制4096字符)"""
    if len(text) <= 4000:
        return update.message.reply_text(text)

    # 分段发送
    parts = []
    while len(text) > 4000:
        split_at = text.rfind('\n', 0, 4000)
        if split_at == -1:
            split_at = 4000
        parts.append(text[:split_at])
        text = text[split_at:].lstrip('\n')
    parts.append(text)

    for i, part in enumerate(parts):
        if i == 0:
            update.message.reply_text(part)
        else:
            update.message.reply_text(f"📄 (续 {i+1}/{len(parts)})\n\n{part}")


# ===================== Telegram 机器人命令 =====================
async def cmd_start(update, context):
    """欢迎语 + 自动注册"""
    user = update.effective_user
    db = load_users()

    # 检查/初始化Owner
    if db.get('owner') is None and OWNER_TELEGRAM_ID != 0:
        db['owner'] = {
            'telegram_id': str(OWNER_TELEGRAM_ID),
            'set_at': time.time(),
        }
        save_users(db)

    # 自动注册
    register_user(db, user.id, user.username or '', user.first_name or '')
    level = get_user_level(db, user.id)

    # 处理邀请码: /start INV123456789
    if context.args and context.args[0].startswith('INV'):
        inviter_id = context.args[0].replace('INV', '')
        if inviter_id.isdigit() and inviter_id != str(user.id):
            db.setdefault('invited_by', {})[str(user.id)] = inviter_id
            save_users(db)

    level_badge = {
        'owner': '👑 Owner (老板)',
        'admin': '🛡️ Admin (订阅会员)',
        'user': '👤 User (免费用户)',
        'unknown': '👋 未注册',
    }.get(level, level)

    msg = f"""🦞 SpeedClaw BotKing 量化机器人

欢迎，{user.first_name or '朋友'}！
身份：{level_badge}
ID：`{user.id}`

══════ 🆓 免费功能 ══════
/mysub   - 我的订阅状态
/subscribe - 查看订阅方案
/help    - 完整命令菜单

══════ 💎 订阅后可解锁 ══════
• 实时余额/持仓/盈亏查询
• 控制自己的 BotKing 现货机器人
• 控制自己的 Bot20x 合约机器人
• 多设备同步监控 + 报单推送

══════ 💰 六档订阅 (现货+合约+通票) ══════
🟡 **BotKing现货** | 🟢 **Bot20x合约** | 🟡🟢 **现货+合约通票**

| 档位 | 现货 | 合约 | 通票 |
|------|------|------|------|
| 月付 | $59 | $59 | $99 |
| 年付 | $399 | $399 | $599 |
| 终身 | $1299 | $1299 | $1999 |

💳 支付网络: BSC (BEP20)
💳 USDT 地址: `0x344FfCe2f7B8f580D4e054F7213cb231CD15c3cd`
📧 客服: @okbobox

💡 也可直接输入:
    · “订阅” / “现货订阅” / “合约订阅” / “通票订阅”
    · “月付” / “年付” / “终身” / “通票”
    · 数字: “59” / “99” / “399” / “599” / “1299” / “1999”

🤖 **全自动模式 (推荐)**:
    转账备注您的 Telegram ID + 产品 (如 “Telegram: 1234567890 合约”),
    ≤15秒自动激活并发送激活码

═══════════════════════════════
🎁 **邀请奖励**: 朋友付费 你得 10% 返现 (永久有效)
    例: 朋友买 ¥399 → 你得 ¥39.9
    💡 /invite 生成你的专属邀请链接
"""
    # 生成邀请链接
    invite_code = f"INV{user.id}"
    invite_link = f"https://t.me/my_botking_V2_bot?start={invite_code}"

    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    keyboard = [
        [InlineKeyboardButton("💎 查看订阅方案", callback_data="show_subscribe"),
         InlineKeyboardButton("🎁 邀请赚钱", callback_data="show_invite")],
        [InlineKeyboardButton("🔗 复制邀请链接", callback_data=f"copy_invite_{user.id}")],
        [InlineKeyboardButton("📚 帮助菜单", callback_data="show_help")],
    ]
    await update.message.reply_text(
        msg,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

    # 单独发邀请链接 (便于复制)
    invite_text = (
        f"🎁 **你的专属邀请链接**\n\n"
        f"`{invite_link}`\n\n"
        f"📊 你的邀请数据: 详见 /invite"
    )
    await update.message.reply_text(invite_text, parse_mode='Markdown')


async def cmd_status(update, context):
    pm2 = get_pm2_status()
    state = read_state()

    status_emoji = '🟢' if pm2.get('running') else '🔴'
    status_text = '运行中' if pm2.get('running') else '已停止'

    uptime_s = int(time.time() * 1000) - pm2.get('uptime', 0) if pm2.get('uptime') else 0
    uptime_h = uptime_s / 1000 / 3600

    msg = f"""🦞 BotKing 状态

🤖 机器人：{status_emoji} {status_text}
📌 PID：{pm2.get('pid', '-')}
⏰ 运行时长：{uptime_h:.1f} 小时
🔁 重启次数：{pm2.get('restart_count', 0)}
💾 内存占用：{pm2.get('memory', 0):.1f} MB
⚙️ CPU：{pm2.get('cpu', 0):.1f}%
🌐 当前模式：{state.get('market_mode', 'UNKNOWN')}

最近更新：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    await update.message.reply_text(msg)


async def cmd_balance(update, context):
    state = read_state()
    initial = state.get('initial_balance', 0)
    realized = state.get('realized_profit', 0)
    hwm = state.get('high_water', 0)
    taken = state.get('total_profit_taken', 0)

    msg = f"""💰 账户状态

💵 初始余额：${initial:.2f}
📈 当前高水位：${hwm:.2f}
💸 累计已提取：${taken:.2f}
📊 已实现盈亏：${realized:+.2f}

数据来源：bot_king_state.json
查询时间：{datetime.now().strftime('%H:%M:%S')}
"""
    await update.message.reply_text(msg)


async def cmd_positions(update, context):
    state = read_state()
    engines = state.get('engines', {})
    grids = engines.get('grids', {})
    trends = engines.get('trends', {})

    if not grids and not trends:
        await update.message.reply_text("📭 当前无持仓")
        return

    msg = "📊 当前持仓\n\n"

    if grids:
        msg += "🔲 网格引擎：\n"
        for sym, g in grids.items():
            qty = g.get('position_qty', 0)
            entry = g.get('entry_price', 0)
            grids_count = g.get('max_grids', 0)
            pending = g.get('pending_profit', 0)
            msg += f"  • {sym}: qty={qty:.4f} @ ${entry:.2f} ({grids_count}格) 利润:${pending:.2f}\n"
        msg += "\n"

    if trends:
        msg += "📈 趋势引擎：\n"
        for sym, t in trends.items():
            pos = t.get('position', {})
            qty = pos.get('qty', 0)
            entry = pos.get('entry', 0)
            tp1_done = pos.get('tp1_done', False)
            tp1_mark = '✓' if tp1_done else '✗'
            msg += f"  • {sym}: qty={qty:.4f} @ ${entry:.2f} TP1:{tp1_mark}\n"

    await update.message.reply_text(msg)


async def cmd_mode(update, context):
    state = read_state()
    mode = state.get('market_mode', 'UNKNOWN')
    loss_streak = state.get('loss_streak', 0)
    lock_until = state.get('lock_until', 0)
    locked = lock_until > time.time()

    mode_map = {
        'TREND_UP': '🟢 上涨趋势',
        'TREND_DOWN': '📉 下跌趋势',
        'RANGE_BOUND': '📊 震荡盘整',
        'VOLATILE_OVERSOLD': '🔴 超卖反弹',
        'VOLATILE_OVERBOUGHT': '🟠 超买卖出',
        'CRISIS': '💥 危机',
    }
    mode_text = mode_map.get(mode, f'❓ {mode}')

    lock_emoji = '🔒' if locked else '🔓'
    lock_text = '锁定中' if locked else '正常'

    msg = f"""🌐 市场状态

当前模式：{mode_text}
连亏次数：{loss_streak}
锁定状态：{lock_emoji} {lock_text}

查询时间：{datetime.now().strftime('%H:%M:%S')}
"""
    await update.message.reply_text(msg)


async def cmd_profit(update, context):
    state = read_state()
    hwm = state.get('high_water', 0)
    initial = state.get('initial_balance', 0)
    realized = state.get('realized_profit', 0)
    taken = state.get('total_profit_taken', 0)

    if initial > 0:
        roi = (hwm - initial) / initial * 100
    else:
        roi = 0

    msg = f"""📈 盈亏详情

账户高水位：${hwm:.2f}
初始本金：${initial:.2f}
浮动盈亏：${hwm - initial:+.2f}
已实现盈亏：${realized:+.2f}
已提取利润：${taken:.2f}
ROI：{roi:+.2f}%

查询时间：{datetime.now().strftime('%H:%M:%S')}
"""
    await update.message.reply_text(msg)


async def cmd_log(update, context):
    n = 20
    if context.args:
        try:
            n = int(context.args[0])
            n = min(max(n, 5), 100)
        except ValueError:
            pass
    log_text = tail_log(n)
    if len(log_text) > 3500:
        log_text = '...\n' + log_text[-3500:]

    msg = f"📋 最近 {n} 条日志：\n\n```\n{log_text}\n```"
    await update.message.reply_text(msg, parse_mode='Markdown')  # log用代码块安全


async def cmd_start_bot(update, context):
    await update.message.reply_text("🚀 启动BotKing...")
    try:
        subprocess.run(['pm2', 'start', 'bot_king.py', '--name', 'bot-king', '--interpreter', 'python3'],
                      capture_output=True, timeout=10)
        subprocess.run(['pm2', 'save'], capture_output=True, timeout=5)
        await update.message.reply_text("✅ BotKing已启动")
    except Exception as e:
        await update.message.reply_text(f"❌ 启动失败: {e}")


async def cmd_stop_bot(update, context):
    await update.message.reply_text("⏸ 停止BotKing...")
    try:
        subprocess.run(['pm2', 'stop', 'bot-king'], capture_output=True, timeout=10)
        await update.message.reply_text("✅ BotKing已停止")
    except Exception as e:
        await update.message.reply_text(f"❌ 停止失败: {e}")


async def cmd_restart_bot(update, context):
    await update.message.reply_text("🔄 重启BotKing...")
    try:
        subprocess.run(['pm2', 'restart', 'bot-king'], capture_output=True, timeout=15)
        await update.message.reply_text("✅ BotKing已重启")
    except Exception as e:
        await update.message.reply_text(f"❌ 重启失败: {e}")


# ===================== Bot20x 命令 =====================
# ===================== 订阅配置 =====================
PAYMENT_WALLET = "0x344FfCe2f7B8f580D4e054F7213cb231CD15c3cd"  # 老板的BSC BEP20收款地址
PAYMENT_NETWORK = "BSC (BEP20)"

SUBSCRIPTION_PLANS = {
    "monthly":  {"label": "月付",   "days": 30,   "price": 59,   "emoji": "1️⃣",  "tag": "灵活试用"},
    "yearly":   {"label": "年付",   "days": 365,  "price": 399,  "emoji": "2️⃣",  "tag": "🔥 最受欢迎", "highlight": True},
    "lifetime": {"label": "终身",   "days": 36500,"price": 1299, "emoji": "3️⃣",  "tag": "♾️ 长期投资"},
}

# 产品清单 (双产品统一价格表)
PRODUCTS = {
    "king": {
        "name": "BotKing 现货网格机器人",
        "emoji": "🟡",
        "short": "BotKing",
        "desc": [
            "   • 6个币种 BTC/ETH/BNB/SOL/AVAX/XRP",
            "   • 7种市场模式自动识别",
            "   • 9层风控保护",
            "   • Phase2 复利滚仓",
            "   • 综合评分 9.2/10",
        ],
    },
    "20x": {
        "name": "Bot20x 合约机器人",
        "emoji": "🟢",
        "short": "Bot20x",
        "desc": [
            "   • BTC + ETH 永续合约 (20倍杠杆)",
            "   • MACD + 布林带双指标信号",
            "   • 趋势跟随 + 精准止盈止损",
            "   • v5.6 冷静期熔断保护",
            "   • 5年回测 + 实盘验证",
        ],
    },
}

# 产品价格表 (每个产品独立档位价格)
# 现货(BotKing)与合约(Bot20x)同价，通票(两都要)加价
PRODUCT_PRICES = {
    "king": {
        "monthly":  59,
        "yearly":   399,
        "lifetime": 1299,
    },
    "20x": {
        "monthly":  59,
        "yearly":   399,
        "lifetime": 1299,
    },
    "both": {
        "monthly":  99,    # 通票月付
        "yearly":   599,   # 通票年付
        "lifetime": 1999,  # 通票终身
    },
}


def render_subscribe_message(product="all"):
    """统一渲染订阅方案消息

    Args:
        product: 'king' / '20x' / 'both' / 'all' (默认全部)
    """
    if product == "all":
        header = "💳 SpeedClaw 产品订阅 (现货+合约+通票)"
    elif product == "king":
        header = "💳 SpeedClaw BotKing 现货订阅"
    elif product == "20x":
        header = "💳 SpeedClaw Bot20x 合约订阅"
    elif product == "both":
        header = "💳 SpeedClaw 现货+合约 通票订阅"
    else:
        header = "💳 SpeedClaw 产品订阅"

    lines = [
        header,
        "",
        "═══════════════════════════════",
    ]

    # 决定显示哪些产品
    if product == "all":
        show_products = ["king", "20x", "both"]
    else:
        show_products = [product]

    for pidx, pid in enumerate(show_products):
        price_map = PRODUCT_PRICES[pid]
        if pid == "both":
            lines.append(f"🟡🟢 **现货+合约 通票** (同时控制2个机器人)")
            lines.append("   • BotKing现货 6币种网格 + Bot20x合约 BTC/ETH")
            lines.append("   • 适合两个产品都要的客户，加价40%比单买2个产品优惠")
        else:
            prod = PRODUCTS[pid]
            lines.append(f"{prod['emoji']} {prod['name']}")
            for d in prod['desc']:
                lines.append(d)
        lines.append("")
        lines.append("   💰 **价格表**:")
        lines.append(f"   1️⃣ 月付 ${price_map['monthly']} USDT (30天)")
        lines.append(f"   2️⃣ 年付 ${price_map['yearly']} USDT (365天) 🔥 最受欢迎")
        lines.append(f"   3️⃣ 终身 ${price_map['lifetime']} USDT (永久)")
        if pid == "both":
            lines.append(f"   💡 通票价=2个产品加价40%，比单买2个年付省 \$199/年")
        else:
            lines.append(f"   💡 平均每天仅 \${price_map['yearly']/365:.2f}，比月付省 \${price_map['monthly']*12-price_map['yearly']:.0f}/年")
        lines.append("")
        if pidx < len(show_products) - 1:
            lines.append("═══════════════════════════════")
            lines.append("")

    lines.extend([
        "═══════════════════════════════",
        f"💳 支付方式 (USDT):",
        f"   网络: {PAYMENT_NETWORK}",
        f"   地址: `{PAYMENT_WALLET}`",
        f"   ⚠️ 务必确认BSC网络，转错网络资产无法找回",
        "",
        "📋 参与流程 (4步):",
        "   1️⃣  选择产品+档位 (现货/合约/通票 × 月付/年付/终身)",
        "   2️⃣  向地址转账对应金额 USDT",
        f"      • 现货 59/399/1299  合约 59/399/1299  通票 99/599/1999",
        f"   3️⃣  转账备注您的 Telegram ID + 产品",
        f"      示例: 'Telegram: 1234567890 现货'",
        f"      示例: 'Telegram: 1234567890 合约'",
        f"      示例: 'Telegram: 1234567890 通票'",
        f"   4️⃣  收到激活码后，发送: /activate <激活码>",
        "",
        "═══════════════════════════════",
        "💡 智能提示:",
        "   • 输入 \"订阅\" / \"购买\" → 显示全部套餐",
        "   • 输入 \"现货订阅\" / \"合约订阅\" / \"通票订阅\" → 只看单一产品",
        "   • 输入 \"月付\" / \"年付\" / \"终身\" → 查看套餐详情",
        "   • 输入 \"59\" / \"99\" / \"399\" / \"599\" / \"1299\" / \"1999\" → 识别金额",
        "",
        "🤖 **全自动模式 (推荐)**:",
        "   转账备注 Telegram ID，系统自动检测+生成激活码+发送给您，无需联系Owner",
        "   半自动模式: 发支付截图到机器人，Owner审核后发激活码",
        "",
        "📧 客服: @okbobox",
        "═══════════════════════════════",
    ])

    # 🎁 邀请奖励 (全局)
    lines.extend([
        "",
        "🎁 **邀请奖励计划** (10%返利)",
        "   • 朋友付款后，你获得 10% USDT 返现",
        "   • 朋友买 399 → 你得 39.9 USDT",
        "   • 朋友买 1299 → 你得 129.9 USDT",
        "   • 终身买断也能返现！",
        "   💡 查邀请链接 + 奖励: /invite",
    ])
    return "\n".join(lines)


async def cmd_subscribe(update, context):
    """查看订阅方案 (默认全部)"""
    product = "all"
    if context.args:
        arg = context.args[0].lower()
        if arg in ("king", "botking", "现货"):
            product = "king"
        elif arg in ("20x", "bot20x", "合约"):
            product = "20x"
        elif arg in ("both", "通票", "套餐", "两个", "全部产品"):
            product = "both"
    await update.message.reply_text(render_subscribe_message(product), parse_mode='Markdown')


async def cmd_plan_detail(update, context, intent):
    """显示某个具体套餐的详情"""
    plan_key = intent.replace('plan_', '')
    p = SUBSCRIPTION_PLANS.get(plan_key)
    if not p:
        await cmd_subscribe(update, context)
        return

    # 算性价比
    yearly_equiv = p['price'] / 365 if p['days'] < 36500 else 0
    save_vs_monthly = ""
    if plan_key == 'yearly':
        save_vs_monthly = f"   💡 比月付省 ${(59*12-399):.0f}/年 (省 {(1 - 399/(59*12))*100:.0f}%)"
    elif plan_key == 'lifetime':
        save_vs_monthly = f"   💡 相当于 {1299/(59*12):.1f}年月付价格，但永久使用"

    msg = f"""💎 {p['label']}会员详情 {p.get('tag','')}

═══════════════════════
💵 价格: ${p['price']} USDT
⏰ 有效期: {p['days']}天 {('(永久)' if p['days']>=36500 else '')}
"""
    if yearly_equiv:
        msg += f"📅 平均: ${yearly_equiv:.2f}/天\n"
    msg += save_vs_monthly
    msg += f"""
═══════════════════════
✨ 包含内容:
   • BotKing 现货机器人 完整功能
   • 6个币种 (BTC/ETH/BNB/SOL/AVAX/XRP)
   • 7种市场模式自动识别
   • 9层风控保护
   • Phase2 复利滚仓
   • 源码 + 更新 + 技术支持
═══════════════════════
💳 支付 (USDT - BSC BEP20):
   地址: `{PAYMENT_WALLET}`
   金额: ${p['price']} USDT
   ⚠️ 转错网络资产无法找回

📋 下一步:
   1. 向地址转账 ${p['price']} USDT (BSC BEP20)
   2. 截图发送到此机器人
   3. 备注您的 Telegram ID
   4. 收到激活码后 /activate <激活码>

💡 输入 "订阅" 返回总菜单
"""
    await update.message.reply_text(msg, parse_mode='Markdown')


async def cmd_mysub(update, context):
    """查看我的订阅"""
    user = update.effective_user
    db = load_users()
    level = get_user_level(db, user.id)

    level_name = {
        'owner': '👑 Owner',
        'admin': '🛡️ Admin (订阅会员)',
        'expired': '⏰ 已过期',
        'user': '👤 免费用户',
        'unknown': '👋 未注册',
    }.get(level, level)

    msg = f"""📋 我的订阅状态

ID：`{user.id}`
用户名：{user.username or '未设置'}
姓名：{user.first_name or '未设置'}
身份：{level_name}
"""
    if level == 'admin':
        admin = db['admins'].get(str(user.id), {})
        expire = admin.get('expire_at', 0)
        remain = expire - time.time()
        days = int(remain / 86400)
        plan = admin.get('plan', 'unknown')
        product = admin.get('product', 'unknown')
        api_bound = bool(admin.get('api_key'))
        product_emoji = {'king': '🟡现货', '20x': '🟢合约', 'both': '🟡🟢通票'}.get(product, product)
        plan_label = {'monthly': '月付', 'yearly': '年付', 'lifetime': '终身'}.get(plan, plan)
        msg += f"""
产品：{product_emoji}
套餐：{plan_label} ({plan}){' 🎁体验中' if plan == 'trial' else ''}
剩余天数：{days} 天
到期时间：{datetime.fromtimestamp(expire).strftime('%Y-%m-%d %H:%M')}
API绑定：{'✅ 已绑定' if api_bound else '❌ 未绑定'}

💡 下一步：
{'API未绑定 - 输入 /bindapi' if not api_bound else '订阅生效中 - 享受全部功能'}
{'套餐已过期 - 输入 /subscribe 续费' if remain < 0 else ''}"""

        # 🎁体验专用提示
        if plan == 'trial':
            if remain > 0:
                msg += f"""

🎁 **体验还剩 {days} 天**, 到期后折扣价: /renew 了解"""
            else:
                msg += """

🎁 体验已结束
仅 $59/月 或 $399/年 享受同等功能, 限时优惠: /subscribe"""

    elif level == 'user' or level == 'unknown':
        msg += """
⏰ 未订阅

💡 下一步：
1. /subscribe 查看订阅方案
2. USDT支付 (BSC网络)
3. /activate <激活码> 激活
"""

    elif level == 'expired':
        msg += """
⏰ 订阅已过期

💡 续订联系Owner: @okbobox
"""

    await update.message.reply_text(msg, parse_mode='Markdown')


async def cmd_activate(update, context):
    """激活码激活"""
    user = update.effective_user
    if not context.args:
        await update.message.reply_text(
            "请输入激活码：\n"
            "/activate ABC123XYZ456\n\n"
            "激活码在支付后由Owner提供"
        )
        return

    code = context.args[0]
    db = load_users()
    success, msg = activate_code(db, user.id, code)
    if success:
        await update.message.reply_text(
            f"✅ {msg}\n\n"
            f"🎉 欢迎订阅SpeedClaw BotKing！\n\n"
            f"📋 下一步:\n"
            f"1. /bindapi 绑定你的Binance API\n"
            f"2. /kbalance 查看你的账户余额\n"
            f"3. /help 查看所有可用命令\n\n"
            f"💡 联系: @okbobox"
        )
    else:
        await update.message.reply_text(f"❌ {msg}")


async def cmd_bindapi(update, context):
    """绑定用户自己的Binance API"""
    user = update.effective_user
    db = load_users()
    level = get_user_level(db, user.id)

    if level not in ('owner', 'admin'):
        await update.message.reply_text(
            "🚫 此功能仅订阅会员可用\n\n"
            "请先 /subscribe 查看订阅方案"
        )
        return

    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "📝 绑定Binance API\n\n"
            "格式:\n"
            "/bindapi <API_KEY> <SECRET>\n\n"
            "示例:\n"
            "/bindapi xxxxxxxxxxxx yyyyyyyyy\n\n"
            "⚠️ 安全提示:\n"
            "• 仅勾选'启用现货交易'+'启用读取'\n"
            "• 不要勾选'启用提币'\n"
            "• API密钥仅保存在本地"
        )
        return

    api_key = context.args[0]
    api_secret = context.args[1]
    success, msg = bind_api(db, user.id, api_key, api_secret)
    if success:
        await update.message.reply_text(
            f"✅ {msg}\n\n"
            f"你现在可以:\n"
            f"• /kbalance 查看你的账户余额\n"
            f"• /kpositions 查看你的持仓\n"
            f"• /xbalance 查看你的合约余额"
        )
    else:
        await update.message.reply_text(f"❌ {msg}")


async def cmd_myapi(update, context):
    """查看API绑定状态"""
    user = update.effective_user
    db = load_users()
    api_key, api_secret = get_user_api(db, user.id)

    if api_key:
        masked = api_key[:8] + "..." + api_key[-4:]
        await update.message.reply_text(
            f"✅ API已绑定\n\n"
            f"Key: {masked}\n"
            f"状态: {'活跃' if get_user_level(db, user.id) in ('owner', 'admin') else '未激活'}"
        )
    else:
        await update.message.reply_text(
            "❌ 未绑定API\n\n"
            "请使用 /bindapi 绑定"
        )


async def cmd_unbindapi(update, context):
    """解绑Binance API"""
    user = update.effective_user
    db = load_users()
    level = get_user_level(db, user.id)

    if level not in ('owner', 'admin'):
        await update.message.reply_text("🚫 此功能仅订阅会员可用")
        return

    admin = db['admins'].get(str(user.id), {})
    if not admin.get('api_key'):
        await update.message.reply_text(
            "❌ 未绑定API，无需解绑\n\n"
            "如需绑定: /bindapi"
        )
        return

    # 确认按钮
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    keyboard = [
        [
            InlineKeyboardButton("✅ 确认解绑", callback_data=f"unbind_confirm_{user.id}"),
            InlineKeyboardButton("❌ 取消", callback_data="unbind_cancel"),
        ]
    ]
    await update.message.reply_text(
        f"⚠️ 确认解绑API?\n\n"
        f"Key: {admin['api_key'][:8]}...{admin['api_key'][-4:]}\n\n"
        f"解绑后机器人会停止交易，需重新 /bindapi 才能使用",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def cmd_myorders(update, context):
    """查看我的订单状态（半自动付款流程）"""
    user = update.effective_user
    PENDING_FILE = Path('/root/.openclaw/workspace/.pending_payments.json')

    if not PENDING_FILE.exists():
        await update.message.reply_text(
            "📦 你还没有订单记录\n\n"
            "💡 首次订阅: /subscribe\n"
            "💡 发截图: 直接发支付截图到机器人"
        )
        return

    try:
        all_payments = json.loads(PENDING_FILE.read_text())
    except:
        all_payments = {}

    my_orders = [p for p in all_payments.values() if p.get('user_id') == str(user.id)]

    if not my_orders:
        await update.message.reply_text(
            "📦 你还没有订单记录\n\n"
            "💡 首次订阅: /subscribe\n"
            "💡 发截图: 直接发支付截图到机器人"
        )
        return

    lines = ["📦 **我的订单**", ""]
    for idx, p in enumerate(my_orders[-5:], 1):  # 最近5单
        plan = p.get('detected_plan', '?')
        product = p.get('detected_product', '?')
        status_emoji = {'pending': '⏳', 'approved': '✅', 'rejected': '❌'}.get(p.get('status'), '?')
        status_text = {'pending': '待审核', 'approved': '已通过', 'rejected': '已拒绝'}.get(p.get('status'), p.get('status'))
        product_emoji = {'king': '🟡现货', '20x': '🟢合约', 'both': '🟡🟢通票'}.get(product, product)
        plan_label = {'monthly': '月付', 'yearly': '年付', 'lifetime': '终身'}.get(plan, plan)
        created = datetime.fromtimestamp(p.get('created_at', 0)).strftime('%m-%d %H:%M')
        lines.append(
            f"{status_emoji} **{idx}. {product_emoji} {plan_label}** ({status_text})\n"
            f"   订单号: `{p['payment_id'][:20]}...`\n"
            f"   时间: {created}"
        )
        if p.get('code'):
            lines.append(f"   激活码: `{p['code']}`")
        lines.append("")

    lines.append("💡 如订单超1小时未处理: 联系 @okbobox")
    await update.message.reply_text("\n".join(lines), parse_mode='Markdown')


async def cmd_renew(update, context):
    """一键续费 (生成年付激活码)"""
    user = update.effective_user
    db = load_users()
    level = get_user_level(db, user.id)

    if level == 'owner':
        await update.message.reply_text("👑 你是Owner，订阅永久有效")
        return

    if level == 'unknown' or level == 'user':
        await update.message.reply_text(
            "❌ 你还没有订阅\n\n"
            "💡 首次订阅: /subscribe"
        )
        return

    # 看上下文参数 (默认当前产品+年付)
    admin = db['admins'].get(str(user.id), {})
    current_product = admin.get('product', 'both')
    product_emoji = {'king': '🟡现货', '20x': '🟢合约', 'both': '🟡🟢通票'}[current_product]

    plan = 'yearly'
    plan_label = '年付'
    if context.args:
        arg = context.args[0].lower()
        if '月' in arg or 'monthly' in arg or '30' in arg or '59' in arg or '99' in arg:
            plan = 'monthly'
            plan_label = '月付'
        elif '终' in arg or 'lifetime' in arg or '永久' in arg or '1299' in arg or '1999' in arg:
            plan = 'lifetime'
            plan_label = '终身'

    p = SUBSCRIPTION_PLANS[plan]
    price = PRODUCT_PRICES.get(current_product, PRODUCT_PRICES['king'])[plan]
    days = p['days']

    # 显示续费信息
    msg = f"""💎 **续费 {product_emoji} {plan_label}**

价格: ${price} USDT
有效期: {days}天{' (永久)' if days >= 36500 else ''}
收款地址: `{PAYMENT_WALLET}`
网络: {PAYMENT_NETWORK}

💡 两种续费方式:
1. 转账${price} USDT到地址，memo写 `Telegram: {user.id} {current_product}`
   ≤15秒全自动激活

2. 转账后发支付截图 (备注: '续费+{plan_label}'), Owner手动发码
"""


async def cmd_trial(update, context):
    """生成/领取体验码 (仅1次/人, 7天BotKing现货体验)"""
    user = update.effective_user
    db = load_users()

    # 检查是否已领取过体验
    if str(user.id) in db.get('trial_used', {}):
        trial_info = db['trial_used'][str(user.id)]
        used_at = datetime.fromtimestamp(trial_info['used_at']).strftime('%Y-%m-%d %H:%M')
        await update.message.reply_text(
            f"❌ 你已领取过体验码 (于 {used_at})\n\n"
            f"每人仅限 1 次体验\n"
            f"请 /subscribe 购买正式订阅"
        )
        return

    # 检查是否已是订阅会员 (会员不允许领体验码)
    level = get_user_level(db, user.id)
    if level in ('owner', 'admin'):
        await update.message.reply_text(
            "❌ 你是订阅会员，无需领取体验码\n\n"
            "快去交易 /kstatus /kbalance"
        )
        return

    # 生成体验激活码 (7天BotKing现货)
    code = generate_activation_code(db, duration_days=7, plan='trial', product='king')
    db['trial_used'] = db.get('trial_used', {})
    db['trial_used'][str(user.id)] = {
        'telegram_id': str(user.id),
        'used_at': time.time(),
        'code': code,
    }
    save_users(db)

    msg = f"""🎁 **体验码领取成功！**

激活码: `{code}`
有效期: 7天
产品: 🟡 BotKing现货 (6个币种网格交易)

💡 **下一步**:
1. /activate {code} (激活订阅)
2. /bindapi <key> <secret> (绑定Binance API)
3. /start_bot (启动现货机器人)
4. /kbalance (查看账户)

⚠️ 提示: 体验码仅可领 1 次，过期后可 /subscribe 购买正式订阅。
   有问题: @okbobox
"""
    await update.message.reply_text(msg, parse_mode='Markdown')


async def cmd_switch(update, context):
    """切换产品 (现货<->合约<->通票) - 仅Owner可用"""
    user = update.effective_user
    db = load_users()
    if not is_owner(db, user.id):
        await update.message.reply_text("🚫 仅Owner可用")
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "用法: /switch <user_id> <product>\n"
            "product: king / 20x / both\n\n"
            "示例: /switch 123456789 both (升级为通票)"
        )
        return

    target_id = context.args[0]
    new_product = context.args[1].lower()
    if new_product not in ('king', '20x', 'both'):
        await update.message.reply_text("❌ product必须是: king / 20x / both")
        return

    admin = db.get('admins', {}).get(target_id)
    if not admin:
        await update.message.reply_text(f"❌ 用户 {target_id} 不是admin")
        return

    old_product = admin.get('product', 'both')
    if old_product == new_product:
        await update.message.reply_text(
            f"⚠️ 用户 {target_id} 已是 {new_product}, 无需切换"
        )
        return

    # 差价检查 (升级才需补差, 降级不退)
    plan = admin.get('plan', 'monthly')
    old_price = PRODUCT_PRICES.get(old_product, PRODUCT_PRICES['king'])[plan]
    new_price = PRODUCT_PRICES.get(new_product, PRODUCT_PRICES['king'])[plan]
    diff = new_price - old_price

    product_emoji = {'king': '🟡现货', '20x': '🟢合约', 'both': '🟡🟢通票'}

    if diff > 0:
        # 升级需补差价
        await update.message.reply_text(
            f"⚠️ 升级需补差价: ${diff}\n\n"
            f"  原产品: {product_emoji[old_product]} = ${old_price}\n"
            f"  新产品: {product_emoji[new_product]} = ${new_price}\n"
            f"  需补: ${diff} USDT\n\n"
            f"如同意, 回复: /switch_confirm {target_id} {new_product}"
        )
        # 暂存意向
        db.setdefault('switch_pending', {})[target_id] = {
            'old_product': old_product,
            'new_product': new_product,
            'diff': diff,
            'at': time.time(),
        }
        save_users(db)
        return

    admin['product'] = new_product
    save_users(db)

    await update.message.reply_text(
        f"✅ 用户 {target_id} 产品已切换\n"
        f"   {product_emoji[old_product]} → {product_emoji[new_product]}\n"
        f"   补差: $0 (降级/同价)"
    )


async def cmd_switch_confirm(update, context):
    """确认升级补差后的产品切换"""
    user = update.effective_user
    db = load_users()
    if not is_owner(db, user.id):
        await update.message.reply_text("🚫 仅Owner可用")
        return

    if len(context.args) < 2:
        await update.message.reply_text("用法: /switch_confirm <user_id> <product>")
        return

    target_id = context.args[0]
    new_product = context.args[1].lower()

    pending = db.get('switch_pending', {}).get(target_id)
    if not pending:
        await update.message.reply_text(f"❌ 用户 {target_id} 没有待确认的切换")
        return

    admin = db.get('admins', {}).get(target_id)
    if not admin:
        await update.message.reply_text(f"❌ 用户 {target_id} 不是admin")
        return

    admin['product'] = new_product
    db.get('switch_pending', {}).pop(target_id, None)
    save_users(db)

    product_emoji = {'king': '🟡现货', '20x': '🟢合约', 'both': '🟡🟢通票'}
    await update.message.reply_text(
        f"✅ 升级完成\n"
        f"   {product_emoji[pending['old_product']]} → {product_emoji[new_product]}\n"
        f"   补差: ${pending['diff']} USDT"
    )

    # 通知客户
    try:
        await update.get_bot().send_message(
            chat_id=int(target_id),
            text=(
                f"🔄 你的订阅产品已切换！\n\n"
                f"新产品: {product_emoji[new_product]}\n\n"
                f"如需查询权限: /mysub"
            ),
            parse_mode='Markdown'
        )
    except Exception:
        pass


async def cmd_history(update, context):
    """历史交易记录 (从bot状态文件读取)"""
    user = update.effective_user
    db = load_users()
    level = get_user_level(db, user.id)

    if level not in ('owner', 'admin'):
        await update.message.reply_text("🚫 此功能仅订阅会员可用")
        return

    # 读取bot状态文件中的历史成交
    STATE_FILE = Path('/root/.openclaw/workspace/binance_state.json')
    lines = ["📜 **历史交易记录** (最近20笔)\n"]

    if not STATE_FILE.exists():
        await update.message.reply_text(
            "📜 **历史交易记录**\n\n"
            "机器人未启动，暂无成交记录"
        )
        return

    try:
        import json
        state = json.loads(STATE_FILE.read_text())

        # 1. trades 字段 (主要)
        trades = state.get('trades', [])

        # 2. 兼容 positions (当前持仓 + last_report)
        if not trades:
            lines = ["📜 **交易历史概览**\n"]
            lines.append(f"  · 更新时间: {datetime.fromtimestamp(state.get('updated', 0)).strftime('%Y-%m-%d %H:%M')}")
            lines.append(f"  · 当前持仓: {len(state.get('positions', []))} 个")
            lines.append(f"  · 今日盈亏: ${state.get('daily_pnl', 0):.2f}")
            lines.append(f"  · 总盈亏: ${state.get('total_pnl', 0):.2f}")
            lines.append(f"  · 多仓: {'有' if state.get('has_long') else '无'}")
            lines.append(f"  · 空仓: {'有' if state.get('has_short') else '无'}")
            lines.append(f"  · 上次报告: {state.get('last_report', '无')}")
            lines.append("\n💡 交易历史保存在 Binance API 侧，可查询 Binance 账户成交记录")
            await update.message.reply_text("\n".join(lines), parse_mode='Markdown')
            return

        # 最近20笔
        for t in trades[-20:]:
            ts = datetime.fromtimestamp(t.get('time', 0)).strftime('%m-%d %H:%M')
            symbol = t.get('symbol', '?')
            side = t.get('side', '?')
            price = t.get('price', 0)
            qty = t.get('qty', 0)
            pnl = t.get('pnl', 0)
            side_emoji = '🟢' if side == 'buy' else '🔴'
            pnl_str = f"+${pnl:.2f}" if pnl >= 0 else f"-${abs(pnl):.2f}"
            lines.append(
                f"{side_emoji} {ts} {symbol} {side} @ ${price:.2f} × {qty}\n"
                f"   盈亏: {pnl_str}"
            )
        await update.message.reply_text("\n".join(lines), parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"❌ 读取历史失败: {e}")


async def cmd_clean_orders(update, context):
    """清理超时未审核订单 (超过24小时未处理的)"""
    user = update.effective_user
    db = load_users()
    if not is_owner(db, user.id):
        await update.message.reply_text("🚫 仅Owner可用")
        return

    PENDING_FILE = Path('/root/.openclaw/workspace/.pending_payments.json')
    if not PENDING_FILE.exists():
        await update.message.reply_text("✅ 没有订单需要清理")
        return

    pending = json.loads(PENDING_FILE.read_text())
    now = time.time()
    timeout = 24 * 3600
    cleaned = []
    for pid, p in list(pending.items()):
        if p.get('status') == 'pending' and now - p.get('created_at', 0) > timeout:
            p['status'] = 'expired'
            p['expired_at'] = now
            cleaned.append(pid)

    with open(PENDING_FILE, 'w') as f:
        json.dump(pending, f, indent=2, ensure_ascii=False)

    if cleaned:
        await update.message.reply_text(
            f"✅ 清理 {len(cleaned)} 个超时订单\n"
            f"状态已设为 expired (过期)，不再待审"
        )
    else:
        await update.message.reply_text("✅ 没有超时订单")

    await update.message.reply_text(msg, parse_mode='Markdown')


# ===================== Owner 命令 =====================
async def cmd_gencode(update, context):
    """Owner生成激活码 - 支持套餐参数 + 自然语言 + 确认按钮"""
    user = update.effective_user
    db = load_users()
    if not is_owner(db, user.id):
        await update.message.reply_text("🚫 仅Owner可生成激活码")
        return

    # 1. 解析套餐参数 (支持: 月付/年付/终身/monthly/yearly/lifetime/30/365/36500)
    args_list = context.args if context.args else ['yearly']
    full_arg = ' '.join(args_list).lower().strip()

    PLAN_ALIASES = {
        # 中文别名
        '月': 'monthly', '月付': 'monthly', '包月': 'monthly', '一月': 'monthly', '月度': 'monthly',
        '年': 'yearly', '年付': 'yearly', '包年': 'yearly', '一年': 'yearly', '年度': 'yearly',
        '终身': 'lifetime', '永久': 'lifetime', '买断': 'lifetime', '不限期': 'lifetime',
        # 英文别名
        'm': 'monthly', 'monthly': 'monthly',
        'y': 'yearly', 'yearly': 'yearly', 'year': 'yearly',
        'l': 'lifetime', 'lifetime': 'lifetime', 'forever': 'lifetime',
        # 数字别名 (金额/天数/套餐代码)
        '59': 'monthly', '59u': 'monthly',
        '399': 'yearly', '399u': 'yearly',
        '1299': 'lifetime', '1299u': 'lifetime',
        '1999': 'lifetime', '1999u': 'lifetime',
        '30': 'monthly', '365': 'yearly', '36500': 'lifetime',
    }

    PRODUCT_ALIASES = {
        # 现货 (BotKing)
        '现货': 'king', 'king': 'king', 'spot': 'king',
        '现货版': 'king', '现货机器': 'king', '现货机器人': 'king',
        'k': 'king', 'botking': 'king', 'bot_k': 'king', 'bot_king': 'king',
        # 合约 (Bot20x)
        '合约': '20x', '20x': '20x', 'futures': '20x',
        '合约版': '20x', '合约机器人': '20x', '合约机器': '20x',
        'x': '20x', 'bot20x': '20x', 'bot_20x': '20x', 'botx': '20x',
        # 通票 (现货+合约)
        '通票': 'both', '全部': 'both', '两个': 'both', '俩': 'both',
        '现货合约': 'both', '合约现货': 'both', '现货+合约': 'both', '合约+现货': 'both',
        'all': 'both', 'both': 'both', 'full': 'both',
    }

    # 2. 扫描args列表提取plan + product
    plan = None
    product = None
    for arg in args_list:
        arg_l = arg.lower().strip()
        if arg_l in PLAN_ALIASES and not plan:
            plan = PLAN_ALIASES[arg_l]
            continue
        if arg_l in PRODUCT_ALIASES and not product:
            product = PRODUCT_ALIASES[arg_l]
            continue
        # 尝试数字解析为天数
        if not plan:
            try:
                days = int(arg)
                if days >= 3650:
                    plan = 'lifetime'
                elif days >= 365:
                    plan = 'yearly'
                elif days >= 28:
                    plan = 'monthly'
            except ValueError:
                pass

    # 3. 默认值
    if not plan:
        plan = 'yearly'
    if not product:
        product = 'both'  # 默认通票 (老客户兼容)

    p = SUBSCRIPTION_PLANS[plan]
    code = generate_activation_code(db, duration_days=p['days'], plan=plan, product=product)

    product_label = {'king': '🟡 BotKing现货', '20x': '🟢 Bot20x合约', 'both': '🟡🟢 现货+合约通票'}[product]

    await update.message.reply_text(
        f"🎫 激活码生成成功\n\n"
        f"激活码：`{code}`\n"
        f"套餐: {p['emoji']} **{p['label']}** ({plan})\n"
        f"产品: {product_label}\n"
        f"价格: ${p['price']} USDT\n"
        f"有效期: {p['days']}天 {('(永久)' if p['days']>=36500 else '')}\n\n"
        f"📋 使用方法:\n"
        f"   发给用户: /activate {code}\n\n"
        f"⚠️ 一次使用，请妥善保存\n"
        f"💡 用法示例:\n"
        f"   /gencode 年付 现货\n"
        f"   /gencode 年付 合约\n"
        f"   /gencode 年付 通票",
        parse_mode='Markdown'
    )


async def cmd_listusers(update, context):
    """Owner查看所有用户"""
    user = update.effective_user
    db = load_users()
    if not is_owner(db, user.id):
        await update.message.reply_text("🚫 仅Owner可查看用户列表")
        return

    users = db.get('users', {})
    admins = db.get('admins', {})
    pending = db.get('pending_codes', {})

    msg = f"""📋 用户列表

👑 Owner: {db.get('owner', {}).get('telegram_id', '未设置')}

🛡️ Admin (订阅会员): {len(admins)} 人
"""
    for uid, info in list(admins.items())[:10]:
        expire = datetime.fromtimestamp(info.get('expire_at', 0))
        api = '✅' if info.get('api_key') else '❌'
        msg += f"  • `{uid}` {info.get('plan', '?')} 到期:{expire.strftime('%m-%d')} API:{api}\n"

    msg += f"\n👤 Free Users: {len(users)} 人\n"
    for uid, info in list(users.items())[:5]:
        msg += f"  • `{uid}` @{info.get('username', '')} {info.get('first_name', '')}\n"

    unused_codes = [c for c, info in pending.items() if not info.get('used_by')]
    msg += f"\n🎫 未使用激活码: {len(unused_codes)} 张"

    await update.message.reply_text(msg, parse_mode='Markdown')


async def cmd_grant(update, context):
    """Owner直接授权用户"""
    user = update.effective_user
    db = load_users()
    if not is_owner(db, user.id):
        await update.message.reply_text("🚫 仅Owner可授权用户")
        return


async def cmd_invite(update, context):
    """生成我的邀请链接 + 查邀请奖励"""
    user = update.effective_user
    db = load_users()
    BOT_USERNAME = 'my_botking_V2_bot'  # 去掉@

    invite_code = f"INV{user.id}"
    invite_link = f"https://t.me/{BOT_USERNAME}?start={invite_code}"

    invites = db.get('invites', {})
    my_invites = invites.get(str(user.id), {'count': 0, 'rewards': 0, 'codes': []})

    rewards = my_invites.get('rewards', 0)
    codes = my_invites.get('codes', [])

    lines = [
        "🎁 **邀请奖励计划**",
        "",
        f"你的邀请链接:",
        f"`{invite_link}`",
        "",
        f"📊 你的邀请数据:",
        f"  · 邀请付费客户: {my_invites.get('count', 0)} 人",
        f"  · 累计奖励: ${rewards} USDT",
        f"  · 详细记录: {len(codes)} 条",
        "",
        "💡 **奖励规则**:",
        "  · 朋友付款后:  自动返 10% USDT",
        "  · 朋友买 399 → 你得 39.9",
        "  · 朋友买 1299 → 你得 129.9",
        "  · 终身买断也能返！",
        "",
        "💡 提现: 累计 \$50 USDT 后可申请提现",
    ]

    if codes:
        lines.append("\n📋 最近邀请记录:")
        for c in codes[-5:]:
            if isinstance(c, dict):
                lines.append(f"  · 被邀请: {c.get('invitee', '?')} | 返利: +${c.get('reward', 0)}")
            else:
                lines.append(f"  · 激活码: `{c}`")

    # 提现按钮
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    if rewards >= 50:
        keyboard = [
            [InlineKeyboardButton(f"💰 申请提现 ${rewards}", callback_data=f"withdraw_{user.id}")],
        ]
    else:
        need = 50 - rewards
        keyboard = [[InlineKeyboardButton(f"再推荐累计到 $50 (还差 ${need:.1f})", callback_data="show_subscribe")]]

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def cmd_withdraw(update, context):
    """申请提现邀请奖励"""
    user = update.effective_user
    db = load_users()

    invites = db.get('invites', {})
    my_invites = invites.get(str(user.id), {'count': 0, 'rewards': 0, 'codes': []})
    rewards = my_invites.get('rewards', 0)

    if rewards < 50:
        await update.message.reply_text(
            f"❌ 提现门槛为 \$50 USDT\n"
            f"当前累计: ${rewards} USDT\n"
            f"还差 ${50-rewards} USDT 可提现"
        )
        return

    # 检查是否已设置提现地址
    admin = db.get('admins', {}).get(str(user.id), {})
    wallet = admin.get('withdraw_wallet')

    if not wallet:
        # 未设置地址 - 提示先去设置
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        keyboard = [
            [InlineKeyboardButton("💳 立即设置提现地址", callback_data="set_wallet_start")],
            [InlineKeyboardButton("💡 查看设置指南", callback_data="set_wallet_help")],
        ]
        await update.message.reply_text(
            f"⚠️ 提现需要先设置提现地址\n\n"
            f"可提现金额: ${rewards} USDT\n\n"
            f"📋 设置方法:\n"
            f"/setwallet <USDT-BSC地址>\n\n"
            f"示例: /setwallet 0x344FfCe2f7B8f580D4e054F7213cb231CD15c3cd\n\n"
            f"⚠️ 务必使用 BSC (BEP20) 地址，转错网络资产无法找回！\n"
            f"⚠️ 建议使用交易所充值地址 (如Binance/OKX) 避免转错",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    # 检查是否已有待处理提现
    pending_withdraws = db.get('pending_withdraws', {})
    if str(user.id) in pending_withdraws:
        existing = pending_withdraws[str(user.id)]
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        keyboard = [
            [InlineKeyboardButton("❌ 取消申请", callback_data=f"cancel_withdraw_{user.id}")],
        ]
        await update.message.reply_text(
            f"⏳ 你有提现申请待处理中\n\n"
            f"金额: ${existing['amount']} USDT\n"
            f"申请时间: {datetime.fromtimestamp(existing['requested_at']).strftime('%Y-%m-%d %H:%M')}\n"
            f"提现地址: `{existing.get('wallet', wallet)}`\n\n"
            f"💡 如需取消: 点下方按钮或联系 @okbobox",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    # 创建提现申请 (含预设地址)
    pending_withdraws[str(user.id)] = {
        'amount': rewards,
        'wallet': wallet,
        'requested_at': time.time(),
        'status': 'pending',
    }
    db.setdefault('pending_withdraws', {}).update(pending_withdraws)
    save_users(db)

    # 通知Owner (带预设地址, 一键转账)
    try:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        keyboard = [
            [InlineKeyboardButton(f"✅ 立即转账 ${rewards}", callback_data=f"pay_withdraw_{user.id}")],
            [InlineKeyboardButton("❌ 拒绝", callback_data=f"reject_withdraw_{user.id}")],
        ]
        await context.bot.send_message(
            chat_id=OWNER_TELEGRAM_ID,
            text=(
                f"💰 **提现申请**\n\n"
                f"申请人: {user.id} (@{user.username or user.first_name or '匿名'})\n"
                f"金额: ${rewards} USDT\n"
                f"邀请数: {my_invites.get('count', 0)} 人\n"
                f"提现地址: `{wallet}`\n\n"
                f"⚠️ 点击下方按钮 → BSC转账 → 报交易哈希\n"
                f"⚠️ 提现限额: \$50起, 单笔不超该用户累计"
            ),
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    except Exception as e:
        log(f"通知Owner提现申请失败: {e}")

    await update.message.reply_text(
        f"✅ 提现申请已提交\n\n"
        f"金额: ${rewards} USDT\n"
        f"提现地址: `{wallet}`\n\n"
        f"📤 Owner会在24h内处理转账\n"
        f"💡 状态查询: /withdraw\n"
        f"💡 修改地址: /setwallet <新地址>",
        parse_mode='Markdown',
    )


async def cmd_setwallet(update, context):
    """设置USDT提现地址 (BSC BEP20)"""
    user = update.effective_user
    db = load_users()

    if not context.args:
        # 查看当前地址
        admin = db.get('admins', {}).get(str(user.id), {})
        wallet = admin.get('withdraw_wallet')
        if wallet:
            masked = wallet[:8] + '...' + wallet[-6:]
            await update.message.reply_text(
                f"💳 **当前提现地址**\n\n"
                f"`{wallet}`\n\n"
                f"💡 修改地址: /setwallet <新地址>\n"
                f"⚠️ 务必BSC (BEP20) 地址，转错网络资产无法找回",
                parse_mode='Markdown',
            )
        else:
            await update.message.reply_text(
                f"💳 **设置USDT提现地址**\n\n"
                f"格式: /setwallet <USDT-BSC地址>\n\n"
                f"示例: /setwallet 0x344FfCe2f7B8f580D4e054F7213cb231CD15c3cd\n\n"
                f"⚠️ 务必确认是 BSC (BEP20) 地址！\n"
                f"⚠️ 可用交易所充值地址 (Binance/OKX) 避免转错"
            )
        return

    new_wallet = context.args[0].strip()

    # 验证地址格式
    if not (new_wallet.startswith('0x') and len(new_wallet) == 42):
        await update.message.reply_text(
            f"❌ 地址格式错误\n\n"
            f"请提供 42位 0x开头的 BSC地址\n"
            f"示例: 0x344FfCe2f7B8f580D4e054F7213cb231CD15c3cd"
        )
        return

    # 验证checksum
    try:
        from web3 import Web3
        if not Web3.is_address(new_wallet):
            await update.message.reply_text(f"❌ 地址checksum错误: {new_wallet}")
            return
        canonical = Web3.to_checksum_address(new_wallet)
    except ImportError:
        canonical = new_wallet

    # 保存
    admin = db.setdefault('admins', {}).setdefault(str(user.id), {
        'telegram_id': str(user.id),
    })
    admin['withdraw_wallet'] = canonical
    admin['withdraw_wallet_set_at'] = time.time()
    save_users(db)

    await update.message.reply_text(
        f"✅ 提现地址已设置\n\n"
        f"地址: `{canonical}`\n\n"
        f"💡 提现门槛: \$50 USDT\n"
        f"💡 查余额: /withdraw\n"
        f"💡 修改地址: /setwallet <新地址>",
        parse_mode='Markdown',
    )

    # 通知Owner (新设置地址告警)
    try:
        await context.bot.send_message(
            chat_id=OWNER_TELEGRAM_ID,
            text=(
                f"⚠️ **用户设置提现地址**\n\n"
                f"用户: {user.id} (@{user.username or user.first_name})\n"
                f"地址: `{canonical}`\n"
                f"设置时间: {datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M')}\n\n"
                f"请注意: 提现仅会转到此地址"
            ),
            parse_mode='Markdown',
        )
    except Exception:
        pass


async def cmd_mywallet(update, context):
    """查看我的提现地址"""
    await cmd_setwallet(update, context)


async def cmd_pay_withdraw(update, context):
    """Owner一键转账USDT给客户的提现地址"""
    query = update.callback_query if hasattr(update, 'callback_query') and update.callback_query else None
    if query:
        await query.answer()
        user_id = query.data.replace('pay_withdraw_', '')
    else:
        if not context.args:
            await update.message.reply_text("用法: /pay_withdraw <user_id>")
            return
        user_id = context.args[0]

    db = load_users()
    if not query:
        # 命令调用时验证Owner
        if not is_owner(db, update.effective_user.id):
            await update.message.reply_text("🚫 仅Owner可用")
            return

    # 查提现申请
    pending = db.get('pending_withdraws', {})
    withdraw = pending.get(str(user_id))
    if not withdraw or withdraw.get('status') != 'pending':
        msg_text = f"❌ 用户 {user_id} 没有待处理的提现申请"
        if query:
            await query.edit_message_text(msg_text)
        else:
            await update.message.reply_text(msg_text)
        return

    amount = withdraw['amount']
    wallet = withdraw['wallet']

    # 调用BSC转账
    try:
        sys.path.insert(0, '/root/.openclaw/workspace/speedClaw-Bot20x-Skill')
        from payment.auto_activate import send_usdt_from_owner, BSC_RPC_URL, OWNER_WALLET
        tx_hash = send_usdt_from_owner(wallet, amount)

        # 标记已转账
        withdraw['status'] = 'paid'
        withdraw['paid_at'] = time.time()
        withdraw['tx_hash'] = tx_hash
        save_users(db)

        # 扣减返利余额
        invites = db.get('invites', {}).get(str(user_id), {})
        if invites:
            invites['rewards'] = max(0, round(invites.get('rewards', 0) - amount, 2))
            invites.setdefault('withdraws', []).append({
                'amount': amount,
                'wallet': wallet,
                'tx_hash': tx_hash,
                'paid_at': time.time(),
            })
        save_users(db)

        success_msg = (
            f"✅ 提现已转账\n\n"
            f"用户: {user_id}\n"
            f"金额: ${amount} USDT\n"
            f"地址: `{wallet}`\n"
            f"交易: `{tx_hash}`\n\n"
            f"🔗 https://bscscan.com/tx/{tx_hash}"
        )
        if query:
            await query.edit_message_text(success_msg, parse_mode='Markdown')
        else:
            await update.message.reply_text(success_msg, parse_mode='Markdown')

        # 通知客户
        try:
            bot = update.get_bot() if hasattr(update, 'get_bot') else context.bot
            await bot.send_message(
                chat_id=int(user_id),
                text=(
                    f"🎉 **提现已到账！**\n\n"
                    f"金额: ${amount} USDT\n"
                    f"地址: `{wallet}`\n"
                    f"交易: `{tx_hash}`\n\n"
                    f"🔗 https://bscscan.com/tx/{tx_hash}\n\n"
                    f"请在钱包查收 (BSC USDT)"
                ),
                parse_mode='Markdown',
            )
        except Exception as e:
            log(f"通知客户提现成功失败: {e}")

    except Exception as e:
        err_msg = f"❌ 转账失败: {e}"
        if query:
            await query.edit_message_text(err_msg)
        else:
            await update.message.reply_text(err_msg)



async def cmd_invite_for_callback(update, context):
    """邀请页用于 Inline 按钮回调"""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    query = update.callback_query
    user = query.from_user
    db = load_users()

    BOT_USERNAME = 'my_botking_V2_bot'
    invite_code = f"INV{user.id}"
    invite_link = f"https://t.me/{BOT_USERNAME}?start={invite_code}"

    invites = db.get('invites', {})
    my_invites = invites.get(str(user.id), {'count': 0, 'rewards': 0, 'codes': []})

    lines = [
        "🎁 **邀请奖励计划**\n",
        f"你的专属邀请链接:",
        f"`{invite_link}`\n",
        f"📊 **你的邀请数据**:",
        f"  · 邀请付费客户: {my_invites['count']} 人",
        f"  · 累计奖励: ${my_invites['rewards']} USDT\n",
        "💡 **奖励规则**:",
        "  · 朋友付款后: 返 10% USDT",
        "  · 朋友买 399 → 你得 39.9",
        "  · 朋友买 1299 → 你得 129.9",
        "  · 终身买断也能返！\n",
        "📢 分享邀请链接到:",
        "  · Telegram 朋友",
        "  · Twitter/X",
        "  · 微信 / QQ群\n",
        "💡 查详细: /invite",
    ]

    keyboard = [
        [InlineKeyboardButton("🔗 复制邀请链接", callback_data=f"copy_invite_{user.id}")],
        [InlineKeyboardButton("🔙 返回", callback_data="show_subscribe")],
    ]
    await query.edit_message_text(
        "\n".join(lines),
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def cmd_invite_bind(update, context):
    """Owner记录邀请奖励 (返现10%)"""
    user = update.effective_user
    db = load_users()
    if not is_owner(db, user.id):
        await update.message.reply_text("🚫 仅Owner可记录")
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "用法: /invite_bind <invite_id> <code>\n"
            "invite_id: 邀请人Telegram ID\n"
            "code: 被邀请人使用的激活码\n\n"
            "示例: /invite_bind 123456789 ABC123XYZ"
        )
        return

    inviter_id = context.args[0]
    code = context.args[1].upper()

    pending = db.get('pending_codes', {})
    if code not in pending:
        await update.message.reply_text(f"❌ 激活码 {code} 不存在")
        return

    code_info = pending[code]
    used_by = code_info.get('used_by')
    if not used_by:
        await update.message.reply_text(f"❌ 激活码 {code} 尚未被使用")
        return

    # 计算奖励 (按价格10%)
    plan = code_info.get('plan', 'monthly')
    product = code_info.get('product', 'king')
    price = PRODUCT_PRICES.get(product, PRODUCT_PRICES['king'])[plan]
    reward = round(price * 0.1, 2)

    # 记录
    invites = db.setdefault('invites', {})
    inviter = invites.setdefault(inviter_id, {'count': 0, 'rewards': 0, 'codes': []})
    inviter['count'] += 1
    inviter['rewards'] += reward
    inviter['codes'].append(code)
    save_users(db)

    await update.message.reply_text(
        f"✅ 邀请奖励记录成功\n\n"
        f"邀请人: {inviter_id}\n"
        f"被邀请人: {used_by}\n"
        f"套餐: {plan} ({product})\n"
        f"价格: ${price}\n"
        f"奖励: ${reward} (10%)\n\n"
        f"累计奖励: ${inviter['rewards']} USDT"
    )

    if not context.args:
        await update.message.reply_text("用法: /grant <telegram_id> [天数]")
        return

    target_id = context.args[0]
    duration = int(context.args[1]) if len(context.args) > 1 else 365

    db['admins'][target_id] = {
        'telegram_id': target_id,
        'activated_at': time.time(),
        'expire_at': time.time() + duration * 86400,
        'plan': f'{duration}d',
        'granted_by': str(user.id),
    }
    save_users(db)
    await update.message.reply_text(
        f"✅ 用户 `{target_id}` 已授权 {duration} 天"
    )
async def cmd_kstatus_bot20x(update, context):
    pm2 = get_bot20x_status()
    state = read_bot20x_state()

    status_emoji = '🟢' if pm2.get('running') else '🔴'
    status_text = '运行中' if pm2.get('running') else '已停止'

    uptime_s = int(time.time() * 1000) - pm2.get('uptime', 0) if pm2.get('uptime') else 0
    uptime_h = uptime_s / 1000 / 3600

    positions = state.get('positions', [])
    pos_count = len(positions)
    has_long = state.get('has_long', False)
    has_short = state.get('has_short', False)
    direction = []
    if has_long: direction.append('🟢多')
    if has_short: direction.append('🔴空')

    msg = f"""🟢 Bot20x 状态

🤖 机器人：{status_emoji} {status_text}
📌 PID：{pm2.get('pid', '-')}
⏰ 运行时长：{uptime_h:.1f} 小时
🔁 重启次数：{pm2.get('restart_count', 0)}
💾 内存占用：{pm2.get('memory', 0):.1f} MB
⚙️ CPU：{pm2.get('cpu', 0):.1f}%
📊 持仓数：{pos_count}
🎯 当前方向：{' '.join(direction) if direction else '⚪ 空仓'}

最近更新：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    await update.message.reply_text(msg)


async def cmd_kbalance_bot20x(update, context):
    """Bot20x余额 - 实时API (支持用户自己的API)"""
    user = update.effective_user
    db = load_users()
    api_key, api_secret = get_user_api(db, user.id)

    # Owner未绑定时使用默认
    if get_user_level(db, user.id) == 'owner' and not api_key:
        api_key, api_secret = BOT20X_API_KEY, BOT20X_SECRET

    if not api_key:
        await update.message.reply_text(
            "❌ 未绑定API\n\n"
            "请先 /bindapi 绑定你的Binance API\n"
            "或 /subscribe 查看订阅方案"
        )
        return

    await update.message.reply_text("🔄 查询Binance实时数据...")
    data, err = fetch_bot20x_full_realtime(api_key, api_secret)

    if err:
        await update.message.reply_text(f"❌ 查询失败: {err}")
        return

    balance = data['balance']
    unrealized = data['unrealized']
    total = data['total_equity']

    msg = f"""💰 Bot20x 账户状态 (实时)

💵 可用余额：${balance:.2f}
📊 未实现盈亏：${unrealized:+.2f}
📈 总权益：${total:.2f}
💼 钱包总额：${data['wallet_total']:.2f}
📦 已用保证金：${data['margin_used']:.2f}

⚡ 实时查询 Binance API
⏰ 查询时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    await update.message.reply_text(msg)


async def cmd_kpositions_bot20x(update, context):
    """Bot20x持仓 - 实时API (支持用户自己的API)"""
    user = update.effective_user
    db = load_users()
    api_key, api_secret = get_user_api(db, user.id)

    if get_user_level(db, user.id) == 'owner' and not api_key:
        api_key, api_secret = BOT20X_API_KEY, BOT20X_SECRET

    if not api_key:
        await update.message.reply_text("❌ 未绑定API，请 /bindapi")
        return

    await update.message.reply_text("🔄 查询Binance实时持仓...")
    data, err = fetch_bot20x_full_realtime(api_key, api_secret)

    if err:
        await update.message.reply_text(f"❌ 查询失败: {err}")
        return

    positions = data['positions']
    if not positions:
        await update.message.reply_text(
            "📭 当前无持仓\n\n"
            f"💵 可用余额：${data['balance']:.2f}\n"
            f"⚡ 实时查询 Binance API\n"
            f"⏰ {datetime.now().strftime('%H:%M:%S')}"
        )
        return

    msg = "📊 Bot20x 当前持仓 (实时)\n\n"
    for p in positions:
        side_emoji = '🟢LONG' if p['side'] == 'LONG' else '🔴SHORT'
        pnl_emoji = '🟢' if p['pnl'] >= 0 else '🔴'
        msg += f"""  • {p['symbol']} {side_emoji} {p['leverage']}x
    开仓价：${p['entry']:.2f}
    标记价：${p['mark']:.2f}
    数量：{p['qty']}
    盈亏：{pnl_emoji} ${p['pnl']:+.2f}
    模式：{p['marginType']}

"""
    msg += f"💵 可用余额：${data['balance']:.2f}\n"
    msg += f"📊 未实现盈亏：${data['unrealized']:+.2f}\n"
    msg += f"⚡ 实时 Binance API"
    await update.message.reply_text(msg)


async def cmd_kprofit_bot20x(update, context):
    """Bot20x盈亏 - 实时API (支持用户自己的API)"""
    user = update.effective_user
    db = load_users()
    api_key, api_secret = get_user_api(db, user.id)

    if get_user_level(db, user.id) == 'owner' and not api_key:
        api_key, api_secret = BOT20X_API_KEY, BOT20X_SECRET

    if not api_key:
        await update.message.reply_text("❌ 未绑定API，请 /bindapi")
        return

    await update.message.reply_text("🔄 查询Binance实时盈亏...")
    data, err = fetch_bot20x_full_realtime(api_key, api_secret)

    if err:
        await update.message.reply_text(f"❌ 查询失败: {err}")
        return

    msg = f"""📈 Bot20x 盈亏详情 (实时)

💵 可用余额：${data['balance']:.2f}
📊 未实现盈亏：${data['unrealized']:+.2f}
📈 总权益：${data['total_equity']:.2f}
💼 钱包总额：${data['wallet_total']:.2f}
📦 已用保证金：${data['margin_used']:.2f}

📋 持仓数：{len(data['positions'])}
"""
    if data['positions']:
        for p in data['positions']:
            side = p['side']
            pnl = p['pnl']
            pnl_e = '🟢' if pnl >= 0 else '🔴'
            msg += f"  • {p['symbol']} {side} 盈亏：{pnl_e} ${pnl:+.2f}\n"

    msg += f"\n⚡ 实时 Binance API\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    await update.message.reply_text(msg)


async def cmd_klog_bot20x(update, context):
    n = 20
    if context.args:
        try:
            n = int(context.args[0])
            n = min(max(n, 5), 100)
        except ValueError:
            pass
    log_text = tail_bot20x_log(n)
    if len(log_text) > 3500:
        log_text = '...\n' + log_text[-3500:]
    msg = f"📋 Bot20x 最近 {n} 条日志：\n\n```\n{log_text}\n```"
    await update.message.reply_text(msg, parse_mode='Markdown')


async def cmd_start_bot20x(update, context):
    await update.message.reply_text("🚀 启动Bot20x...")
    try:
        subprocess.run(['pm2', 'start', 'bot20x'], capture_output=True, timeout=10)
        await update.message.reply_text("✅ Bot20x已启动")
    except Exception as e:
        await update.message.reply_text(f"❌ 启动失败: {e}")


async def cmd_stop_bot20x(update, context):
    await update.message.reply_text("⏸ 停止Bot20x...")
    try:
        subprocess.run(['pm2', 'stop', 'bot20x'], capture_output=True, timeout=10)
        await update.message.reply_text("✅ Bot20x已停止")
    except Exception as e:
        await update.message.reply_text(f"❌ 停止失败: {e}")


async def cmd_restart_bot20x(update, context):
    await update.message.reply_text("🔄 重启Bot20x...")
    try:
        subprocess.run(['pm2', 'restart', 'bot20x'], capture_output=True, timeout=15)
        await update.message.reply_text("✅ Bot20x已重启")
    except Exception as e:
        await update.message.reply_text(f"❌ 重启失败: {e}")


# ===================== 自然语言处理 =====================
INTENT_KEYWORDS = {
    # BotKing 现货 (k前缀)
    'kstatus': ['king状态', 'kstatus', 'king', 'BotKing状态', '现货状态', '现货机器人', '现货怎么', '现货跑了没', '现货跑着没', '现货跑着吗', '现货跑没', '现货开了吗', '现货好吗', '现货好了吗', '现货怎么样', '现货活着吗', '现货开着吗', '现货开着没', '现货跑'],
    'kbalance': ['king余额', 'kbalance', '现货余额', '现货账户', '现货钱', '现货有多少', 'BotKing余额', '现货多少钱', '现货还剩多少', '现货剩多少', '现货账号', '现货资金', '看看现货', '我现货', '现货资金多少'],
    'kpositions': ['king持仓', 'kpositions', '现货持仓', '现货仓位', 'BotKing持仓', '现货货', '现货开了什么', '现货开了啥', '现货仓位详情', '现货明细'],
    'kmode': ['king模式', 'kmode', '现货模式', '现货市场', '现货趋势', 'BotKing模式'],
    'kprofit': ['king盈亏', 'kprofit', '现货盈亏', '现货赚', 'BotKing盈亏', '现货收益', '现货亏', '现货赚了多少', '现货亏了多少', '现货总账'],
    'klog': ['king日志', 'klog', '现货日志', '现货log', 'BotKing日志', '现货最近', '现货干嘛了', '现货干了什么'],

    # Bot20x 合约 (x前缀)
    'xstatus': ['20x状态', 'xstatus', 'Bot20x状态', '合约状态', '合约机器人', '合约怎么', 'bot20x', 'x状态', '合约跑着没', '合约跑着吗', '合约跑了没', '20x跑着没', '20x跑着吗', '20x跑', '合约活了', '20x活着吗', '20x开了吗', '20x开了没', '20x怎么样', '合约开着吗', '合约开着没', '合约怎么样', '合约好吗', '合约好了吗', '合约活着吗', '合约启动了'],
    'xbalance': ['20x余额', 'xbalance', '合约余额', '合约账户', '合约钱', '合约有多少', 'Bot20x余额', 'x余额', '合约多少钱', '合约还剩多少', '合约剩多少', '合约资金', '合约账号', '看看合约'],
    'xpositions': ['20x持仓', 'xpositions', '合约持仓', '合约仓位', 'Bot20x持仓', '合约货', 'x持仓', '合约开了什么', '合约明细'],
    'xprofit': ['20x盈亏', 'xprofit', '合约盈亏', '合约赚', 'Bot20x盈亏', '合约收益', 'x盈亏', '合约亏', '合约赚了多少', '合约亏了多少'],
    'xlog': ['20x日志', 'xlog', '合约日志', '合约log', 'Bot20x日志', 'x日志', '合约最近', '合约干嘛了'],

    # BotKing 控制
    'start_bot': ['启动现货', '现货启动', '启动BotKing', '现货跑起来', '现货开', '现货干', '现货开始', '现货跑', '现货干起来', '现货拉起来', '现货启动一下'],
    'stop_bot': ['停止现货', '现货停', '停止BotKing', '现货别跑了', '现货关了', '现货关闭', '现货停下来', '现货停掉', '现货关了', '现货关', '现货关了'],
    'restart_bot': ['重启现货', '现货重启', '重启BotKing', '现货重新'],

    # Bot20x 控制
    'start_bot20x': ['启动合约', '合约启动', '启动Bot20x', '合约跑起来', '合约开', '合约干', '20x启动', '启动20x', '启动bot20x', '20x跑', '20x跑起来', '20x开', '20x干', '20x开始', '20x干起来'],
    'stop_bot20x': ['停止合约', '合约停', '停止Bot20x', '合约别跑了', '20x停', '20x停止', '停bot20x', '20x关了', '20x关闭', '20x停掉'],
    'restart_bot20x': ['重启合约', '合约重启', '重启Bot20x', '合约重新', '20x重启', '重启20x', '重启bot20x'],

    # 帮助
    'help': ['帮助', 'help', '怎么用', '不会用', '指令', '命令', '菜单', '能做什么', '你会什么', '有什么功能', '怎么控制'],

    # 订阅 (价格 / 套餐 / 购买)
    'subscribe': [
        '订阅', '订阅方案', '购买', '价格', '多少钱', '怎么付费', '付费', '开会员', '会员',
        '付', '付款', '收钱', '交钱', '订阅一下', '购买订阅', '我要订阅', '想用',
    ],
    'subscribe_king': ['现货订阅', 'king订阅', 'botking订阅', '现货会员', '现货怎么订阅'],
    'subscribe_20x':  ['合约订阅', '20x订阅', 'bot20x订阅', '合约会员', '合约怎么订阅'],
    'plan_monthly':  ['月付', '月度', '按月', '59', '59u', '59usdt', '一月', '包月'],
    'plan_yearly':   ['年付', '年度', '按年', '399', '399u', '399usdt', '一年', '包年', '年会员', '年订阅'],
    'plan_lifetime': ['终身', '永久', '1299', '1299u', '1299usdt', '1999', '1999u', '买断', '一次买断', '终身会员', '终身订阅', '不限期'],

    # Owner生成激活码 (仅Owner可用，但识别要给提示)
    'gencode': ['生成激活码', '生成月付激活码', '生成年付激活码', '生成终身激活码', '生成现货激活码', '生成合约激活码', '生成通票激活码', '生成现货年付激活码', '生成合约年付激活码', '生成现货月付激活码', '生成合约月付激活码', '生成现货终身激活码', '生成合约终身激活码', '生成通票年付激活码', '生成通票月付激活码', '生成通票终身激活码', '出个码', '给我个码', '生成一个码', '要个激活码', '发个激活码', '出个现货码', '出个合约码', '出个通票码', '来个现货年付', '来个合约年付', '现货年付', '合约年付', '现货终身', '合约终身', '通票年付', '通票终身', '现货月付', '合约月付', '现货的', '合约的', '通票的', '现货年付码', '合约年付码', '现货终身码', '合约终身码', '现货月付码', '合约月付码', '通票年付码', '通票终身码', '通票月付码', 'gencode', '生成', '出个', '来个', '要个', '发个', '生成个', '生成一个', '出个激活码', '来个激活码'],

    # 新增命令
    'unbindapi': ['unbindapi', '解绑api', '解绑api', '解除绑定', '解绑', '解除api', '取消绑定', 'unbind', '不绑了'],
    'myorders': ['我的订单', '我的付款', '订单状态', '订单记录', 'myorders', '我的订单', '查看订单', '我的订阅订单'],
    'renew': ['续费', '续订', 'renew', '怎么续费', '怎么续订', '续期', '延卡', '延长', '充值', '我要续费', '再续一年', '再续', '续上'],
    'trial': ['体验', '体验码', '体验一下', '试用', '试用码', '试一下', '免费试试', '领体验码', '要体验', '可以体验吗', '能试试吗', 'trial'],
    'history': ['历史', '交易记录', '历史交易', '成交记录', '我的交易', 'history', '账单', '我的账单'],
    'switch': ['切换', '切换产品', '换产品', '换套餐', 'switch', '升级', '降级', '要合约', '要现货'],
    'clean_orders': ['清理订单', '清理过期订单', '过期订单', '超时订单'],
    'invite': ['邀请', '邀请码', '邀请链接', '推荐', '推荐奖励', '邀请奖励', '拉人', '拉奖励', '怎么赚钱', '有奖励吗'],
    'withdraw': ['提现', '返利', '提奖', '提取奖励', '拿奖励', '取钱', '提现金', 'withdraw', '怎么提现', '返利提现'],
    'setwallet': ['setwallet', '设置地址', '设地址', '提现地址', '设置提现', '换地址', '改地址', '我的钱包', 'mywallet', '设置钱包'],
    'mywallet': ['我的地址', '我的提现地址', '查地址', 'mywallet'],
}


def detect_intent(text):
    """从自然语言识别用户意图"""
    text_lower = text.lower().strip()

    # 1. 先看是否就是 /开头的命令
    if text_lower.startswith('/'):
        cmd = text_lower[1:].split()[0] if text_lower[1:] else 'help'
        return cmd

    # 2. 按优先级匹配: Bot20x/BotKing特定关键词优先
    scores = {}
    for intent, keywords in INTENT_KEYWORDS.items():
        score = 0
        for kw in keywords:
            kw_l = kw.lower()
            # 检查文本是否含 gencode 动词 (先生效,给所有匹配的intent加分)
            has_gencode_verb = any(x in text_lower for x in ['生成', '出个', '来个', '要个', '发个', '给我个', '发个'])
            if kw_l in text_lower:
                # 状态查询关键词优先级高于控制
                # “跑了/开着/活了/状态/怎么样/如何” 是状态
                # “启动/开始/跑起来” 是控制
                is_status_keyword = any(x in kw_l for x in ['跑了', '跑着', '活了', '开着', '开了', '状态', '怎么', '活着', '好不好', '好吗'])
                is_control_keyword = any(x in kw_l for x in ['启动', '开始', '跑起来', '跑', '干', '关', '停', '重启'])
                # Bot20x/BotKing特定关键词优先 (因为有歧义)
                if intent.startswith('x') and '20x' in kw_l:
                    base = 100 + len(kw_l)
                elif intent.startswith('k') and 'king' in kw_l:
                    base = 100 + len(kw_l)
                elif intent == 'gencode':
                    # 有gencode动词+任意关键字 → +200
                    # 无gencode动词(如 '现货年付') → +50
                    if has_gencode_verb:
                        base = 250 + len(kw_l)
                    else:
                        base = 200 + len(kw_l)
                else:
                    base = len(kw_l)
                # 状态词优先级+50，控制词不降低（移除之前的bug逻辑）
                if is_status_keyword:
                    base += 50
                # 含gencode动词时，其他intent(plan_*)的keyword优先级-50
                if has_gencode_verb and intent.startswith('plan_'):
                    base = max(base - 50, 1)  # 最低保留1分
                score += base
        if score > 0:
            scores[intent] = score

    if scores:
        return max(scores, key=scores.get)
    return None


async def handle_natural_language(update, context):
    """处理自然语言消息"""
    text = update.message.text.strip()
    intent = detect_intent(text)

    if not intent:
        await update.message.reply_text(
            "🤔 没听懂你说的意思\n\n"
            "可以这样跟我说：\n"
            "• 查看一下余额\n"
            "• 现在什么状态\n"
            "• 持仓情况\n"
            "• 启动机器人\n"
            "• 帮助\n\n"
            "或者直接发 /help 看所有命令"
        )
        return

    # 显示识别结果，让用户知道系统理解对了
    intent_emoji = {
        # BotKing
        'kstatus': '🟡 King 状态',
        'kbalance': '🟡 King 余额',
        'kpositions': '🟡 King 持仓',
        'kmode': '🟡 King 模式',
        'kprofit': '🟡 King 盈亏',
        'klog': '🟡 King 日志',
        # Bot20x
        'xstatus': '🟢 20x 状态',
        'xbalance': '🟢 20x 余额',
        'xpositions': '🟢 20x 持仓',
        'xprofit': '🟢 20x 盈亏',
        'xlog': '🟢 20x 日志',
        # 控制
        'start_bot': '🟡 启动现货',
        'stop_bot': '🟡 停止现货',
        'restart_bot': '🟡 重启现货',
        'start_bot20x': '🟢 启动合约',
        'stop_bot20x': '🟢 停止合约',
        'restart_bot20x': '🟢 重启合约',
        # 帮助
        'help': '❓ 帮助',
        'subscribe': '💳 订阅方案 (全部)',
        'subscribe_king': '🟡 BotKing 现货订阅',
        'subscribe_20x': '🟢 Bot20x 合约订阅',
        'plan_monthly': '1️⃣ 月付 $59',
        'plan_yearly': '2️⃣ 年付 $399',
        'plan_lifetime': '3️⃣ 终身 $1299',
        'gencode': '🎫 生成激活码 (Owner)',
    }
    await update.message.reply_text(
        f"🎤 识别意图：{intent_emoji.get(intent, intent)}"
    )

    # 路由到对应命令
    handlers = {
        # BotKing
        'kstatus': cmd_status,
        'kbalance': cmd_balance,
        'kpositions': cmd_positions,
        'kmode': cmd_mode,
        'kprofit': cmd_profit,
        # Bot20x
        'xstatus': cmd_kstatus_bot20x,
        'xbalance': cmd_kbalance_bot20x,
        'xpositions': cmd_kpositions_bot20x,
        'xprofit': cmd_kprofit_bot20x,
        # 控制
        'start_bot': cmd_start_bot,
        'stop_bot': cmd_stop_bot,
        'restart_bot': cmd_restart_bot,
        'start_bot20x': cmd_start_bot20x,
        'stop_bot20x': cmd_stop_bot20x,
        'restart_bot20x': cmd_restart_bot20x,
        # 帮助
        'help': cmd_help,
        # 订阅
        'subscribe': cmd_subscribe,
    }

    if intent in ('log', 'klog', 'xlog'):
        # 提取数字参数（如"看20条日志"）
        import re
        nums = re.findall(r'\d+', text)
        if nums:
            context.args = [nums[0]]
        else:
            context.args = ['20']
        if intent == 'klog':
            await cmd_log(update, context)
        else:
            await cmd_klog_bot20x(update, context)
    elif intent in handlers:
        await handlers[intent](update, context)
    elif intent in ('plan_monthly', 'plan_yearly', 'plan_lifetime'):
        await cmd_plan_detail(update, context, intent)
    elif intent in ('subscribe_king', 'subscribe_20x'):
        product = 'king' if intent == 'subscribe_king' else '20x'
        context.args = [product]
        await cmd_subscribe(update, context)
    elif intent == 'gencode':
        # 从自然语言中提取套餐 + 产品
        plan_arg = None
        if '月付' in text or '月' in text or '59' in text:
            plan_arg = '月付'
        elif '年付' in text or '年' in text or '399' in text:
            plan_arg = '年付'
        elif '终身' in text or '永久' in text or '1299' in text or '1999' in text:
            plan_arg = '终身'

        product_arg = None
        if '通票' in text or '全部' in text or '两个' in text:
            product_arg = '通票'
        elif '现货' in text or 'king' in text.lower():
            product_arg = '现货'
        elif '合约' in text or '20x' in text.lower():
            product_arg = '合约'

        context.args = [a for a in [plan_arg, product_arg] if a] or ['yearly']
        await cmd_gencode(update, context)
    elif intent == 'unbindapi':
        await cmd_unbindapi(update, context)
    elif intent == 'myorders':
        await cmd_myorders(update, context)
    elif intent == 'renew':
        # 提取renew参数
        renew_arg = None
        if '月' in text or '30' in text or '59' in text or '99' in text:
            renew_arg = '月付'
        elif '终' in text or '永久' in text or '1299' in text or '1999' in text:
            renew_arg = '终身'
        context.args = [renew_arg] if renew_arg else []
        await cmd_renew(update, context)
    elif intent == 'trial':
        await cmd_trial(update, context)
    elif intent == 'history':
        await cmd_history(update, context)
    elif intent == 'switch':
        await cmd_switch(update, context)
    elif intent == 'clean_orders':
        await cmd_clean_orders(update, context)
    elif intent == 'invite':
        await cmd_invite(update, context)
    elif intent == 'withdraw':
        await cmd_withdraw(update, context)
    elif intent == 'setwallet':
        await cmd_setwallet(update, context)
    elif intent == 'mywallet':
        await cmd_mywallet(update, context)


# ===================== 半自动订阅支付验证 =====================
PENDING_PAYMENTS_FILE = Path('/root/.openclaw/workspace/.pending_payments.json')


def load_pending_payments():
    if not PENDING_PAYMENTS_FILE.exists():
        return {}
    try:
        with open(PENDING_PAYMENTS_FILE) as f:
            return json.load(f)
    except:
        return {}


def save_pending_payments(payments):
    with open(PENDING_PAYMENTS_FILE, 'w') as f:
        json.dump(payments, f, indent=2, ensure_ascii=False)


async def handle_payment_proof(update, context):
    """处理客户发的支付截图 (半自动验证流程)"""
    user = update.effective_user
    caption = (update.message.caption or '').strip()
    photo = update.message.photo[-1] if update.message.photo else None

    if not photo:
        return

    # 1. 自动识别套餐金额 (从caption提取)
    detected_plan = None
    detected_amount = None

    # 检查caption是否包含金额或套餐关键词
    caption_lower = caption.lower()
    for plan_key, p in SUBSCRIPTION_PLANS.items():
        if p['label'] in caption or str(p['price']) in caption:
            detected_plan = plan_key
            detected_amount = p['price']
            break

    # 如果caption没说明，让用户在下一步选择
    pending = load_pending_payments()
    payment_id = f"{user.id}_{int(time.time())}"

    pending[payment_id] = {
        'payment_id': payment_id,
        'user_id': str(user.id),
        'username': user.username or '',
        'first_name': user.first_name or '',
        'photo_file_id': photo.file_id,
        'caption': caption,
        'detected_plan': detected_plan,
        'detected_product': None,  # 现货/合约/通票
        'detected_amount': detected_amount,
        'status': 'pending',  # pending / approved / rejected
        'created_at': time.time(),
        'code': None,
    }
    save_pending_payments(pending)

    # 2. 给客户回复 (要求确认套餐 - 两步: 先选plan，再选product)
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    # 第一步: 选 plan
    keyboard = []
    for plan_key, p in SUBSCRIPTION_PLANS.items():
        keyboard.append([
            InlineKeyboardButton(
                f"{p['emoji']} {p['label']} ${p['price']}",
                callback_data=f"pay_plan_{payment_id}_{plan_key}"
            )
        ])

    reply = (
        f"✅ 已收到支付截图\n\n"
        f"订单号: {payment_id}\n"
        f"📋 **第1步: 请选择订阅档位**:"
    )
    if detected_plan:
        p = SUBSCRIPTION_PLANS[detected_plan]
        reply = (
            f"✅ 已收到支付截图\n\n"
            f"订单号: {payment_id}\n"
            f"🎯 从备注识别: {p['emoji']} **{p['label']}** ${p['price']} USDT\n\n"
            f"📋 **第1步: 请确认订阅档位**:"
        )

    await update.message.reply_text(
        reply,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )


async def handle_payment_callback(update, context):
    """处理客户选择的套餐 + 推送给Owner审核"""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    query = update.callback_query
    await query.answer()

    data = query.data

    # /start 菜单按钮
    if data == 'show_subscribe':
        await query.edit_message_text(render_subscribe_message('all'), parse_mode='Markdown')
        return
    if data == 'show_invite':
        # 调用cmd_invite逻辑
        await cmd_invite_for_callback(update, context)
        return
    if data == 'show_help':
        await query.edit_message_text("💡 完整菜单: /help\n查看订阅: /subscribe\n查订阅: /mysub")
        return
    if data.startswith('copy_invite_'):
        await query.answer("✅ 邀请链接已上方发送，可复制", show_alert=True)
        return

    # unbindapi 确认
    if data.startswith('unbind_confirm_'):
        user_id = data.replace('unbind_confirm_', '')
        db = load_users()
        admin = db.get('admins', {}).get(user_id)
        if admin:
            admin['api_key'] = None
            admin['api_secret'] = None
            save_users(db)
            await query.edit_message_text("✅ API已解绑\n\n重新绑定: /bindapi")
        else:
            await query.edit_message_text("❌ 未找到账户")
        return
    if data == 'unbind_cancel':
        await query.edit_message_text("✅ 已取消")
        return

    # 提现管理
    if data.startswith('reject_withdraw_'):
        user_id = data.replace('reject_withdraw_', '')
        db = load_users()
        pending = db.get('pending_withdraws', {})
        if str(user_id) in pending:
            pending[str(user_id)]['status'] = 'rejected'
            pending[str(user_id)]['rejected_at'] = time.time()
            save_users(db)
            await query.edit_message_text(
                f"❌ 已拒绝提现\n\n"
                f"用户: {user_id}\n"
                f"金额: ${pending[str(user_id)].get('amount', 0)} USDT"
            )
            # 通知客户
            try:
                await context.bot.send_message(
                    chat_id=int(user_id),
                    text=f"❌ 你的提现申请被拒绝\n\n如有疑问联系 @okbobox",
                )
            except Exception:
                pass
        return
    if data.startswith('cancel_withdraw_'):
        user_id = data.replace('cancel_withdraw_', '')
        db = load_users()
        pending = db.get('pending_withdraws', {})
        if str(user_id) in pending:
            del pending[str(user_id)]
            save_users(db)
            await query.edit_message_text(
                f"✅ 提现申请已取消\n\n"
                f"你的提现申请已撤销\n"
                f"余额仍存在, 可随时重新申请"
            )
        return
    if data == 'set_wallet_start':
        await query.edit_message_text(
            "💳 **设置提现地址**\n\n"
            "格式: `/setwallet <USDT-BSC地址>`\n\n"
            "示例: `/setwallet 0x344FfCe2f7B8f580D4e054F7213cb231CD15c3cd`\n\n"
            "⚠️ 务必使用 BSC (BEP20) 地址！\n"
            "⚠️ 建议用交易所充值地址 (Binance/OKX) 避免转错",
            parse_mode='Markdown',
        )
        return
    if data == 'set_wallet_help':
        await query.edit_message_text(
            "💡 **设置USDT-BSC地址指南**\n\n"
            "**1. Binance交易所**\n"
            "   App → 钱包 → 充值 → 选USDT → 选BSC(BEP20)网络 → 复制地址\n\n"
            "**2. OKX交易所**\n"
            "   App → 资产 → 充值 → 选USDT → 选BSC(BEP20) → 复制地址\n\n"
            "**3. Trust Wallet / MetaMask**\n"
            "   钱包 → 接收USDT → 选BSC网络 → 复制地址\n\n"
            "⚠️ 转错网络(ERC20/TRC20)资产无法找回！\n"
            "✅ BSC (BEP20) 地址格式: 0x开头 + 40位字符",
            parse_mode='Markdown',
        )
        return


    data = query.data
    # 客户选套餐: pay_plan_{payment_id}_{plan} → 第1步选档位
    if data.startswith('pay_plan_'):
        _, _, payment_id, plan_key = data.split('_', 3)
        pending = load_pending_payments()
        if payment_id not in pending:
            await query.edit_message_text("❌ 订单不存在或已过期")
            return

        payment = pending[payment_id]
        payment['detected_plan'] = plan_key
        payment['user_choice_at'] = time.time()
        save_pending_payments(pending)

        # 第2步: 选产品 (现货/合约/通票)
        PRODUCT_LABELS = {
            'king': ('🟡 BotKing现货', '$59 / $399 / $1299'),
            '20x':  ('🟢 Bot20x合约', '$59 / $399 / $1299'),
            'both': ('🟡🟢 现货+合约通票', '$99 / $599 / $1999'),
        }
        keyboard2 = []
        for prod_key, (label, prices) in PRODUCT_LABELS.items():
            keyboard2.append([
                InlineKeyboardButton(
                    f"{label} ({prices})",
                    callback_data=f"pay_product_{payment_id}_{prod_key}"
                )
            ])

        p = SUBSCRIPTION_PLANS[plan_key]
        await query.edit_message_text(
            f"✅ 第1步已选: {p['emoji']} **{p['label']}** ${p['price']} USDT\n\n"
            f"📋 **第2步: 请选择产品**\n\n"
            f"🟡 BotKing现货 = 6币种网格交易\n"
            f"🟢 Bot20x合约 = BTC/ETH永续合约20倍杠杆\n"
            f"🟡🟢 通票 = 现货+合约 (适合两个都要的人)",
            reply_markup=InlineKeyboardMarkup(keyboard2),
            parse_mode='Markdown'
        )
        return

    # 第2步选产品: pay_product_{payment_id}_{product} → 提交Owner审核
    if data.startswith('pay_product_'):
        _, _, payment_id, product_key = data.split('_', 3)
        pending = load_pending_payments()
        if payment_id not in pending:
            await query.edit_message_text("❌ 订单不存在或已过期")
            return

        payment = pending[payment_id]
        payment['detected_product'] = product_key
        payment['submitted_at'] = time.time()
        save_pending_payments(pending)

        plan_key = payment['detected_plan']
        p = SUBSCRIPTION_PLANS[plan_key]
        product_label = {'king': '🟡 BotKing现货', '20x': '🟢 Bot20x合约', 'both': '🟡🟢 现货+合约通票'}[product_key]

        await query.edit_message_text(
            f"✅ 已提交审核\n\n"
            f"订单号: {payment_id}\n"
            f"档位: {p['emoji']} **{p['label']}** ${p['price']} USDT\n"
            f"产品: {product_label}\n\n"
            f"⏳ 等待Owner审核 (通常<1小时)\n"
            f"收到激活码后: /activate <激活码>",
            parse_mode='Markdown'
        )

        # 推送给Owner
        try:
            owner_keyboard = [
                [
                    InlineKeyboardButton("✅ 通过", callback_data=f"pay_approve_{payment_id}"),
                    InlineKeyboardButton("❌ 拒绝", callback_data=f"pay_reject_{payment_id}"),
                ]
            ]
            owner_msg = (
                f"🔔 **新订单待审核**\n\n"
                f"客户: [{payment['first_name']}](tg://user?id={payment['user_id']}) (`{payment['user_id']}`)\n"
                f"用户名: @{payment['username']}\n"
                f"档位: {p['emoji']} **{p['label']}** ${p['price']} USDT\n"
                f"产品: {product_label}\n"
                f"备注: {payment.get('caption', '(无)')}\n"
                f"订单号: `{payment_id}`\n\n"
                f"📷 [查看截图](tg://msg?photo={payment['photo_file_id']})\n\n"
                f"⚡ 点击下方按钮决定:"
            )
            await context.bot.send_message(
                chat_id=OWNER_TELEGRAM_ID,
                text=owner_msg,
                reply_markup=InlineKeyboardMarkup(owner_keyboard),
                parse_mode='Markdown'
            )
        except Exception as e:
            log(f"推送给Owner失败: {e}")
        return

    # Owner审核: pay_approve_{payment_id} / pay_reject_{payment_id}
    db = load_users()
    if not is_owner(db, query.from_user.id):
        await query.edit_message_text("🚫 仅Owner可审核")
        return

    if data.startswith('pay_approve_'):
        payment_id = data.replace('pay_approve_', '')
        pending = load_pending_payments()
        if payment_id not in pending:
            await query.edit_message_text("❌ 订单不存在")
            return

        payment = pending[payment_id]
        plan_key = payment['detected_plan']
        p = SUBSCRIPTION_PLANS[plan_key]

        # 生成激活码
        db = load_users()
        product = payment.get('detected_product', 'both')
        code = generate_activation_code(db, duration_days=p['days'], plan=plan_key, product=product)

        payment['status'] = 'approved'
        payment['code'] = code
        payment['approved_at'] = time.time()
        save_pending_payments(pending)

        product_label = {'king': '🟡 BotKing现货', '20x': '🟢 Bot20x合约', 'both': '🟡🟢 现货+合约通票'}[product]

        # 告知Owner审核结果
        await query.edit_message_text(
            f"✅ 已通过审核\n\n"
            f"订单号: `{payment_id}`\n"
            f"客户: `{payment['user_id']}`\n"
            f"档位: {p['emoji']} **{p['label']}** ${p['price']} USDT\n"
            f"产品: {product_label}\n"
            f"激活码: `{code}`\n\n"
            f"📤 已自动发送给客户",
            parse_mode='Markdown'
        )

        # 自动私信客户激活码
        try:
            await context.bot.send_message(
                chat_id=int(payment['user_id']),
                text=(
                    f"🎉 订阅审核通过！\n\n"
                    f"档位: {p['emoji']} **{p['label']}** ${p['price']} USDT\n"
                    f"产品: {product_label}\n"
                    f"激活码: `{code}`\n\n"
                    f"📋 使用方法:\n"
                    f"1. /activate {code}\n"
                    f"2. /bindapi 绑定你的Binance API\n"
                    f"3. /kbalance 查看账户\n\n"
                    f"💡 有问题联系 @okbobox"
                ),
                parse_mode='Markdown'
            )
        except Exception as e:
            log(f"发送激活码给客户失败: {e}")
            # 退一步：把激活码交给Owner手动发送
            await context.bot.send_message(
                chat_id=OWNER_TELEGRAM_ID,
                text=f"⚠️ 自动发送失败，请手动发给客户:\n\n激活码: {code}"
            )

        # 🎁 自动返利 (半自动流程)
        try:
            inviter_id = db.get('invited_by', {}).get(str(payment['user_id']))
            if inviter_id:
                price = p.get('price', 0)
                reward = round(price * 0.1, 2)

                invites = db.setdefault('invites', {})
                inviter = invites.setdefault(inviter_id, {'count': 0, 'rewards': 0, 'codes': []})
                inviter['count'] += 1
                inviter['rewards'] = round(inviter['rewards'] + reward, 2)
                inviter['codes'].append({
                    'code': code,
                    'invitee': str(payment['user_id']),
                    'amount': price,
                    'reward': reward,
                    'at': time.time(),
                })
                save_users(db)

                # 私信邀请人
                try:
                    await context.bot.send_message(
                        chat_id=int(inviter_id),
                        text=(
                            f"🎁 **返利到账！**\n\n"
                            f"你的邀请人 {payment['user_id']} 已购买订阅\n"
                            f"档位: {p['label']}\n"
                            f"价格: ${price}\n"
                            f"你的返利: **+${reward}** USDT (10%)\n\n"
                            f"📊 累计奖励: ${inviter['rewards']} USDT\n"
                            f"💡 查邀请: /invite"
                        ),
                        parse_mode='Markdown'
                    )
                except Exception:
                    pass

                # 通知Owner
                await context.bot.send_message(
                    chat_id=OWNER_TELEGRAM_ID,
                    text=(
                        f"🎁 **返利通知 (半自动)**\n\n"
                        f"邀请人: {inviter_id}\n"
                        f"被邀请: {payment['user_id']}\n"
                        f"返利: +${reward} USDT"
                    )
                )
        except Exception as e:
            log(f"返利异常: {e}")

    elif data.startswith('pay_reject_'):
        payment_id = data.replace('pay_reject_', '')
        pending = load_pending_payments()
        if payment_id in pending:
            pending[payment_id]['status'] = 'rejected'
            pending[payment_id]['rejected_at'] = time.time()
            save_pending_payments(pending)

        await query.edit_message_text(f"❌ 已拒绝订单 `{payment_id}`")

        # 通知客户
        try:
            payment = pending.get(payment_id, {})
            if payment:
                await context.bot.send_message(
                    chat_id=int(payment['user_id']),
                    text=(
                        f"❌ 支付审核未通过\n\n"
                        f"订单号: `{payment_id}`\n\n"
                        f"可能原因:\n"
                        f"  • 截图不清晰\n"
                        f"  • 金额不匹配\n"
                        f"  • 还未到账\n\n"
                        f"请重新发送清晰截图，或联系 @okbobox"
                    ),
                    parse_mode='Markdown'
                )
        except Exception as e:
            log(f"通知客户拒绝失败: {e}")


async def cmd_help(update, context):
    """帮助菜单 - 修复版：纯文本不用Markdown"""
    msg = """🦞 BotKing & Bot20x 控制面板

══════ 🆓 免费功能 ══════
/mysub       - 我的订阅状态
/subscribe   - 查看订阅方案

══════ 🛡️ Admin (订阅后) ══════
BotKing 现货：
/kstatus     - BotKing 状态
/kbalance    - BotKing 余额
/kpositions  - BotKing 持仓
/kmode       - BotKing 市场模式
/kprofit     - BotKing 盈亏
/klog [N]    - BotKing 日志

Bot20x 合约：
/xstatus     - Bot20x 状态
/xbalance    - Bot20x 余额
/xpositions  - Bot20x 持仓
/xprofit     - Bot20x 盈亏
/xlog [N]    - Bot20x 日志

启停控制：
/start_bot      - 启动 BotKing
/stop_bot       - 停止 BotKing
/restart_bot    - 重启 BotKing
/start_bot20x   - 启动 Bot20x
/stop_bot20x    - 停止 Bot20x
/restart_bot20x - 重启 Bot20x

API管理：
/bindapi       - 绑定你的Binance API
/myapi         - 查看API绑定状态
/unbindapi     - 解绑API (重新换账号)

订单与订阅：
/subscribe     - 查看6档订阅方案 (现货/合约/通票)
/trial         - 领取体验码 (7天现货, 每人限1次)
/activate <码> - 激活激活码
/mysub         - 我的订阅状态 (含产品+到期)
/myorders      - 查看我的订单状态 (半自动付款后查)
/renew         - 一键续费 (自动生成套餐详情+地址)

🎁 推广赚钱：
/invite        - 生成邀请链接 + 查奖励 (朋友付费返10%)
/setwallet     - 设置USDT提现地址 (BSC BEP20)
/mywallet      - 查看我的提现地址
/withdraw      - 申请提现 (门槛 \$50)

══════ 📊 查询与交易 ══════
/kstatus /xstatus     - 现货/合约机器人状态
/kbalance /xbalance   - 现货/合约账户余额
/kpositions /xpositions - 持仓
/kprofit /xprofit     - 盈亏
/history     - 历史成交记录 (最近20笔)

══════ 👑 Owner专用 ══════
/gencode [产品] [档位] - 生成激活码 (现货/合约/通票 × 月付/年付/终身)
/switch <id> <产品>   - 切换用户产品 (现货/合约/通票)
/listusers     - 查看所有用户
/grant <id>    - 授权用户
/clean_orders  - 清理超时订单 (24h+)

══════ 🦞 自然语言 ══════
"现货余额" "Bot20x状态" "持仓怎么样"
"启动合约" "重启" "帮助"
"月付" "年付" "终身" "59" "399" "1299"
"订阅" "购买" "价格" "续费" "我的订单"
"生成年付激活码" "出个码" "解绑"

══════ 💳 六档订阅 ══════
| 档位 | 现货 | 合约 | 通票 |
| 月付 | $59 | $59 | $99 |
| 年付 | $399 | $399 | $599 |
| 终身 | $1299 | $1299 | $1999 |

输入 “订阅” → 总菜单 / “现货订阅” “合约订阅” “通票订阅”

══════ 风险提示 ══════
⚠️ 启停操作谨慎使用
⚠️ 所有操作记录到日志

═══════════════════
v1.4.4 · @okbobox
"""
    await update.message.reply_text(msg)


# ===================== Flask Web API =====================
app = Flask(__name__)


@app.route('/api/status')
def api_status():
    pm2 = get_pm2_status()
    state = read_state()
    return jsonify({
        'bot': pm2,
        'state': state,
        'timestamp': datetime.now().isoformat(),
    })


@app.route('/api/balance')
def api_balance():
    state = read_state()
    return jsonify({
        'initial_balance': state.get('initial_balance', 0),
        'high_water': state.get('high_water', 0),
        'realized_profit': state.get('realized_profit', 0),
        'total_profit_taken': state.get('total_profit_taken', 0),
    })


@app.route('/api/positions')
def api_positions():
    state = read_state()
    engines = state.get('engines', {})
    return jsonify({
        'grids': engines.get('grids', {}),
        'trends': engines.get('trends', {}),
    })


@app.route('/api/log')
def api_log():
    n = int(request.args.get('n', 20))
    return jsonify({'log': tail_log(n)})


# ===================== 主程序 =====================
def main():
    if not TELEGRAM_TOKEN:
        print("❌ 请设置环境变量 TELEGRAM_TOKEN")
        print("   export TELEGRAM_TOKEN=你的机器人TOKEN")
        sys.exit(1)

    # 启动Flask API (后台线程)
    def run_flask():
        port = int(os.environ.get('BOTKING_API_PORT', 5002))
        log(f"✅ Flask API启动中 (端口{port})")
        app.run(host='0.0.0.0', port=port, debug=False)

    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()

    # 启动Telegram Bot
    from telegram import Update
    from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters

    app_tg = Application.builder().token(TELEGRAM_TOKEN).build()

    app_tg.add_handler(CommandHandler("start", cmd_start))
    app_tg.add_handler(CommandHandler("status", cmd_status))
    app_tg.add_handler(CommandHandler("balance", cmd_balance))
    app_tg.add_handler(CommandHandler("positions", cmd_positions))
    app_tg.add_handler(CommandHandler("mode", cmd_mode))
    app_tg.add_handler(CommandHandler("profit", cmd_profit))
    app_tg.add_handler(CommandHandler("log", cmd_log))
    app_tg.add_handler(CommandHandler("start_bot", cmd_start_bot))
    app_tg.add_handler(CommandHandler("stop_bot", cmd_stop_bot))
    app_tg.add_handler(CommandHandler("restart_bot", cmd_restart_bot))
    app_tg.add_handler(CommandHandler("help", cmd_help))
    app_tg.add_handler(CommandHandler("subscribe", cmd_subscribe))
    app_tg.add_handler(CommandHandler("mysub", cmd_mysub))
    app_tg.add_handler(CommandHandler("activate", cmd_activate))
    app_tg.add_handler(CommandHandler("bindapi", cmd_bindapi))
    app_tg.add_handler(CommandHandler("myapi", cmd_myapi))
    app_tg.add_handler(CommandHandler("unbindapi", cmd_unbindapi))
    app_tg.add_handler(CommandHandler("myorders", cmd_myorders))
    app_tg.add_handler(CommandHandler("renew", cmd_renew))
    app_tg.add_handler(CommandHandler("trial", cmd_trial))
    app_tg.add_handler(CommandHandler("switch", cmd_switch))
    app_tg.add_handler(CommandHandler("history", cmd_history))
    app_tg.add_handler(CommandHandler("clean_orders", cmd_clean_orders))
    app_tg.add_handler(CommandHandler("invite", cmd_invite))
    app_tg.add_handler(CommandHandler("invite_bind", cmd_invite_bind))
    app_tg.add_handler(CommandHandler("withdraw", cmd_withdraw))
    app_tg.add_handler(CommandHandler("setwallet", cmd_setwallet))
    app_tg.add_handler(CommandHandler("mywallet", cmd_mywallet))
    app_tg.add_handler(CommandHandler("pay_withdraw", cmd_pay_withdraw))
    app_tg.add_handler(CallbackQueryHandler(handle_payment_callback, pattern=r'^withdraw_'))
    app_tg.add_handler(CommandHandler("switch_confirm", cmd_switch_confirm))

    # unbindapi 确认按钮
    app_tg.add_handler(CallbackQueryHandler(handle_payment_callback, pattern=r'^unbind_'))
    app_tg.add_handler(CallbackQueryHandler(handle_payment_callback, pattern=r'^(show_|copy_)'))
    app_tg.add_handler(CommandHandler("gencode", cmd_gencode))
    app_tg.add_handler(CommandHandler("listusers", cmd_listusers))
    app_tg.add_handler(CommandHandler("grant", cmd_grant))

    # Bot20x 命令
    app_tg.add_handler(CommandHandler("xstatus", cmd_kstatus_bot20x))
    app_tg.add_handler(CommandHandler("xbalance", cmd_kbalance_bot20x))
    app_tg.add_handler(CommandHandler("xpositions", cmd_kpositions_bot20x))
    app_tg.add_handler(CommandHandler("xpositions_all", cmd_kpositions_bot20x))
    app_tg.add_handler(CommandHandler("xprofit", cmd_kprofit_bot20x))
    app_tg.add_handler(CommandHandler("xlog", cmd_klog_bot20x))
    app_tg.add_handler(CommandHandler("start_bot20x", cmd_start_bot20x))
    app_tg.add_handler(CommandHandler("stop_bot20x", cmd_stop_bot20x))
    app_tg.add_handler(CommandHandler("restart_bot20x", cmd_restart_bot20x))

    # 自然语言消息处理（文本消息但不是命令）
    app_tg.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_natural_language
    ))

    # 图片/截图处理 (半自动订阅验证)
    app_tg.add_handler(MessageHandler(
        filters.PHOTO,
        handle_payment_proof
    ))

    # 按钮回调处理 (Owner确认/拒绝支付)
    app_tg.add_handler(CallbackQueryHandler(handle_payment_callback, pattern=r'^pay_'))

    log("✅ Telegram Bot已启动")
    log("📱 在Telegram搜索你的机器人用户名,发送 /start 开始")
    log(f"🌐 Web API: http://localhost:{os.environ.get('BOTKING_API_PORT', 5002)}/api/status")

    app_tg.run_polling()


if __name__ == "__main__":
    main()