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
    msg = """🦞 SpeedClaw BotKing 控制面板

欢迎使用 BotKing 现货量化机器人！

可用命令：
/status   - 查看机器人状态
/balance  - 查看账户余额
/positions - 查看当前持仓
/mode     - 当前市场模式
/profit   - 累计盈亏
/log      - 查看最近日志
/help     - 帮助信息

启停控制：
/start_bot  - 启动机器人
/stop_bot   - 停止机器人
/restart_bot - 重启机器人
"""
    await update.message.reply_text(msg)


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
    state = read_bot20x_state()
    wallet = state.get('wallet', 0)
    daily_pnl = state.get('daily_pnl', 0)
    positions = state.get('positions', [])
    unrealized = sum(p.get('pnl', 0) for p in positions)

    msg = f"""💰 Bot20x 账户状态

💵 钱包余额：${wallet:.2f}
📅 今日盈亏：${daily_pnl:+.2f}
📊 未实现盈亏：${unrealized:+.2f}
📈 总权益：${wallet + unrealized:.2f}

数据来源：binance_state.json
查询时间：{datetime.now().strftime('%H:%M:%S')}
"""
    await update.message.reply_text(msg)


async def cmd_kpositions_bot20x(update, context):
    state = read_bot20x_state()
    positions = state.get('positions', [])

    if not positions:
        await update.message.reply_text("📭 Bot20x 当前无持仓")
        return

    msg = "📊 Bot20x 当前持仓\n\n"
    for p in positions:
        symbol = p.get('symbol', '?')
        side = p.get('side', '?')
        side_emoji = '🟢LONG' if side == 'LONG' else '🔴SHORT'
        entry = p.get('entry', 0)
        qty = p.get('qty', 0)
        pnl = p.get('pnl', 0)
        pnl_emoji = '🟢' if pnl >= 0 else '🔴'
        sl = p.get('sl', 0)
        tp = p.get('tp', 0)
        msg += f"""  • {symbol} {side_emoji}
    开仓价：${entry:.2f}
    数量：{qty}
    盈亏：{pnl_emoji} ${pnl:+.2f}
    止损：${sl:.2f}
    止盈：${tp:.2f}

"""
    await update.message.reply_text(msg)


async def cmd_kprofit_bot20x(update, context):
    state = read_bot20x_state()
    wallet = state.get('wallet', 0)
    positions = state.get('positions', [])
    unrealized = sum(p.get('pnl', 0) for p in positions)
    daily_pnl = state.get('daily_pnl', 0)
    total_equity = wallet + unrealized

    msg = f"""📈 Bot20x 盈亏详情

💵 钱包余额：${wallet:.2f}
📅 今日盈亏：${daily_pnl:+.2f}
📊 未实现盈亏：${unrealized:+.2f}
📈 总权益：${total_equity:.2f}

查询时间：{datetime.now().strftime('%H:%M:%S')}
"""
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

══════ 🟡 BotKing 现货 ══════
/kstatus   - BotKing 状态
/kbalance  - BotKing 余额
/kpositions - BotKing 持仓
/kmode     - BotKing 市场模式
/kprofit   - BotKing 盈亏
/klog [N]  - BotKing 日志

══════ 🟢 Bot20x 合约 ══════
/xstatus   - Bot20x 状态
/xbalance  - Bot20x 余额
/xpositions - Bot20x 持仓
/xpositions_all - Bot20x 全部持仓详情
/xprofit   - Bot20x 盈亏
/xlog [N]  - Bot20x 日志

══════ 🤖 启停控制 ══════
/start_bot  - 启动 BotKing
/stop_bot   - 停止 BotKing
/restart_bot - 重启 BotKing
/start_bot20x - 启动 Bot20x
/stop_bot20x  - 停止 Bot20x
/restart_bot20x - 重启 Bot20x

══════ 🦞 自然语言 ══════
直接说中文口语，如：
• "看一下状态"
• "我还有多少钱"
• "持仓怎么样"
• "干起来"
• "重启"
• "帮助"

══════ 风险提示 ══════
⚠️ 启停操作有风险，谨慎使用
⚠️ 所有操作记录到 bot_king.log

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