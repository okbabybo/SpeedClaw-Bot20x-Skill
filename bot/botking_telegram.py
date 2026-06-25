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

══════ 💰 订阅后可用 ══════
• 查看自己账户的实时余额/持仓
• 控制自己的BotKing机器人
• 查看自己的Bot20x合约状态
• 多设备同步监控

══════ 💳 订阅价格 ══════
年付：$399.9 USDT (BSC BEP20)
终身：$999 USDT

📧 联系Owner: @Okbabybo
"""
    await update.message.reply_text(msg, parse_mode='Markdown')


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
async def cmd_subscribe(update, context):
    """查看订阅方案"""
    msg = """💳 SpeedClaw BotKing 订阅方案

═══════════════════════
🟡 BotKing 现货网格机器人
   • 6个币种 (BTC/ETH/BNB/SOL/AVAX/XRP)
   • 7种市场模式自动识别
   • 9层风控保护
   • Phase2 复利滚仓
   • 综合评分 9.2/10
═══════════════════════

💰 订阅价格:

1️⃣ 年付会员
   💵 $399.9 USDT
   ⏰ 有效期 365天
   ✨ 包含: 源码 + 1年更新 + 技术支持

2️⃣ 终身会员
   💵 $999 USDT
   ♾️ 永久使用
   ✨ 包含: 源码 + 终身更新 + 优先支持

═══════════════════════
💳 支付方式:

USDT (推荐) - BSC (BEP20) 网络
地址: 0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb1
金额: 对应套餐价格 + 备注您的Telegram ID

📧 支付完成后:
   1. 截图发送到此机器人
   2. Owner会为您生成激活码
   3. 输入激活码: /activate <激活码>

═══════════════════════
❓ 问题联系: @Okbabybo
"""
    await update.message.reply_text(msg)


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
        api_bound = bool(admin.get('api_key'))
        msg += f"""
套餐：{plan}
剩余天数：{days} 天
到期时间：{datetime.fromtimestamp(expire).strftime('%Y-%m-%d')}
API绑定：{'✅ 已绑定' if api_bound else '❌ 未绑定'}

💡 下一步：
{'API未绑定 - 输入 /bindapi' if not api_bound else '订阅生效中 - 享受全部功能'}
"""

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

💡 续订联系Owner: @Okbabybo
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
            f"💡 联系: @Okbabybo"
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


# ===================== Owner 命令 =====================
async def cmd_gencode(update, context):
    """Owner生成激活码"""
    user = update.effective_user
    db = load_users()
    if not is_owner(db, user.id):
        await update.message.reply_text("🚫 仅Owner可生成激活码")
        return

    duration = 365  # 默认年付
    if context.args:
        try:
            duration = int(context.args[0])
        except:
            pass

    plan = 'lifetime' if duration >= 3650 else 'yearly' if duration >= 365 else f'{duration}d'
    code = generate_activation_code(db, duration_days=duration, plan=plan)
    await update.message.reply_text(
        f"🎫 激活码生成成功\n\n"
        f"激活码：`{code}`\n"
        f"有效期：{duration} 天 ({plan})\n\n"
        f"📋 使用方法:\n"
        f"发给用户: /activate {code}\n\n"
        f"⚠️ 一次使用，请妥善保存"
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
    'kstatus': ['king状态', 'kstatus', 'king', 'BotKing状态', '现货状态', '现货机器人', '现货怎么'],
    'kbalance': ['king余额', 'kbalance', '现货余额', '现货账户', '现货钱', '现货有多少', 'BotKing余额'],
    'kpositions': ['king持仓', 'kpositions', '现货持仓', '现货仓位', 'BotKing持仓', '现货货'],
    'kmode': ['king模式', 'kmode', '现货模式', '现货市场', '现货趋势', 'BotKing模式'],
    'kprofit': ['king盈亏', 'kprofit', '现货盈亏', '现货赚', 'BotKing盈亏', '现货收益'],
    'klog': ['king日志', 'klog', '现货日志', '现货log', 'BotKing日志'],

    # Bot20x 合约 (x前缀)
    'xstatus': ['20x状态', 'xstatus', 'Bot20x状态', '合约状态', '合约机器人', '合约怎么', 'bot20x', 'x状态'],
    'xbalance': ['20x余额', 'xbalance', '合约余额', '合约账户', '合约钱', '合约有多少', 'Bot20x余额', 'x余额'],
    'xpositions': ['20x持仓', 'xpositions', '合约持仓', '合约仓位', 'Bot20x持仓', '合约货', 'x持仓'],
    'xprofit': ['20x盈亏', 'xprofit', '合约盈亏', '合约赚', 'Bot20x盈亏', '合约收益', 'x盈亏'],
    'xlog': ['20x日志', 'xlog', '合约日志', '合约log', 'Bot20x日志', 'x日志'],

    # BotKing 控制
    'start_bot': ['启动现货', '现货启动', '启动BotKing', '现货跑起来', '现货开', '现货干'],
    'stop_bot': ['停止现货', '现货停', '停止BotKing', '现货别跑了'],
    'restart_bot': ['重启现货', '现货重启', '重启BotKing', '现货重新'],

    # Bot20x 控制
    'start_bot20x': ['启动合约', '合约启动', '启动Bot20x', '合约跑起来', '合约开', '合约干', '20x启动', '启动20x', '启动bot20x'],
    'stop_bot20x': ['停止合约', '合约停', '停止Bot20x', '合约别跑了', '20x停', '20x停止', '停bot20x'],
    'restart_bot20x': ['重启合约', '合约重启', '重启Bot20x', '合约重新', '20x重启', '重启20x', '重启bot20x'],

    # 帮助
    'help': ['帮助', 'help', '怎么用', '不会用', '指令', '命令', '菜单', '能做什么', '你会什么', '有什么功能', '怎么控制'],
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
            if kw.lower() in text_lower:
                # Bot20x/BotKing特定关键词优先 (因为有歧义)
                if intent.startswith('x') and '20x' in kw.lower():
                    score += 100 + len(kw)
                elif intent.startswith('k') and 'king' in kw.lower():
                    score += 100 + len(kw)
                else:
                    score += len(kw)
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

══════ 👑 Owner专用 ══════
/gencode [天数] - 生成激活码
/listusers     - 查看所有用户
/grant <id>    - 授权用户

══════ 🦞 自然语言 ══════
"现货余额" "Bot20x状态" "持仓怎么样"
"启动合约" "重启" "帮助"

══════ 风险提示 ══════
⚠️ 启停操作谨慎使用
⚠️ 所有操作记录到日志

═══════════════════
v1.4.3 · @Okbabybo
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
    from telegram.ext import Application, CommandHandler, MessageHandler, filters

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

    log("✅ Telegram Bot已启动")
    log("📱 在Telegram搜索你的机器人用户名,发送 /start 开始")
    log(f"🌐 Web API: http://localhost:{os.environ.get('BOTKING_API_PORT', 5002)}/api/status")

    app_tg.run_polling()


if __name__ == "__main__":
    main()