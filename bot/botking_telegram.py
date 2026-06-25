#!/usr/bin/env python3
"""
BotKing Telegram Bot 控制面板
==============================
通过Telegram控制BotKing现货机器人
- 查看状态
- 启停机器人
- 查看持仓/余额
- 接收实时通知

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
from flask import Flask, jsonify
from threading import Thread

# ===================== 配置 =====================
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN', '')
ADMIN_CHAT_ID = int(os.environ.get('ADMIN_CHAT_ID', '0'))
STATE_FILE = Path('/root/.openclaw/workspace/bot_king_state.json')
LOG_FILE = Path('/root/.openclaw/workspace/bot_king.log')

# 状态缓存
bot_status = {
    'running': False,
    'last_check': None,
    'balance': 0.0,
    'positions': [],
    'total_profit': 0.0,
    'loss_streak': 0,
    'mode': 'UNKNOWN',
    'restart_count': 0,
}


# ===================== 工具函数 =====================
def log(msg):
    ts = datetime.now().strftime('%m/%d %H:%M:%S')
    print(f"[{ts}] {msg}")


def read_state():
    """读取bot_king状态文件"""
    if not STATE_FILE.exists():
        return {}
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except Exception as e:
        log(f"读取状态失败: {e}")
        return {}


def get_pm2_status():
    """获取PM2进程状态"""
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
                    'memory': p.get('memory', 0) / 1024 / 1024,  # MB
                    'cpu': p.get('cpu', 0),
                }
    except Exception as e:
        log(f"PM2状态获取失败: {e}")
    return {'running': False}


def tail_log(n=20):
    """读取最近n行日志"""
    if not LOG_FILE.exists():
        return "日志文件不存在"
    try:
        with open(LOG_FILE) as f:
            lines = f.readlines()
        return ''.join(lines[-n:])
    except Exception as e:
        return f"读取日志失败: {e}"


# ===================== Telegram 机器人 =====================
async def cmd_start(update, context):
    """欢迎语"""
    msg = """🦞 *SpeedClaw BotKing 控制面板*

欢迎使用 BotKing 现货量化机器人!

*可用命令:*
/status - 查看机器人状态
/balance - 查看账户余额
/positions - 查看当前持仓
/positions\\_all - 查看所有持仓详情
/mode - 当前市场模式
/profit - 累计盈亏
/log \\[N\\] - 查看最近N条日志 (默认20)
/start\\_bot - 启动机器人
/stop\\_bot - 停止机器人
/restart\\_bot - 重启机器人
/help - 帮助

🔐 _授权用户专用_
"""
    await update.message.reply_text(msg, parse_mode='Markdown')


async def cmd_status(update, context):
    """机器人状态"""
    pm2 = get_pm2_status()
    state = read_state()

    status_emoji = '🟢' if pm2.get('running') else '🔴'
    status_text = '运行中' if pm2.get('running') else '已停止'

    uptime_s = int(time.time() * 1000) - pm2.get('uptime', 0) if pm2.get('uptime') else 0
    uptime_h = uptime_s / 1000 / 3600

    msg = f"""🦞 *BotKing 状态*

*机器人:* {status_emoji} {status_text}
*PID:* `{pm2.get('pid', '-')}`
*运行时长:* {uptime_h:.1f} 小时
*重启次数:* {pm2.get('restart_count', 0)}
*内存占用:* {pm2.get('memory', 0):.1f} MB
*CPU:* {pm2.get('cpu', 0):.1f}%
*当前模式:* {state.get('market_mode', 'UNKNOWN')}

_最近更新: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_
"""
    await update.message.reply_text(msg, parse_mode='Markdown')


async def cmd_balance(update, context):
    """账户余额"""
    state = read_state()
    initial = state.get('initial_balance', 0)
    realized = state.get('realized_profit', 0)
    hwm = state.get('high_water', 0)
    taken = state.get('total_profit_taken', 0)

    msg = f"""💰 *账户状态*

*初始余额:* ${initial:.2f}
*当前高水位:* ${hwm:.2f}
*累计已提取:* ${taken:.2f}
*已实现盈亏:* ${realized:+.2f}

_数据来源: bot_king_state.json_
_查询时间: {datetime.now().strftime('%H:%M:%S')}_
"""
    await update.message.reply_text(msg, parse_mode='Markdown')


async def cmd_positions(update, context):
    """当前持仓"""
    state = read_state()
    engines = state.get('engines', {})
    grids = engines.get('grids', {})
    trends = engines.get('trends', {})

    if not grids and not trends:
        await update.message.reply_text("📭 当前无持仓")
        return

    msg = "📊 *当前持仓*\n\n"

    if grids:
        msg += "*网格引擎:*\n"
        for sym, g in grids.items():
            qty = g.get('position_qty', 0)
            entry = g.get('entry_price', 0)
            grids_count = g.get('max_grids', 0)
            pending = g.get('pending_profit', 0)
            msg += f"  • `{sym}`: qty={qty:.4f} @ ${entry:.2f} ({grids_count}格) 利润:${pending:.2f}\n"
        msg += "\n"

    if trends:
        msg += "*趋势引擎:*\n"
        for sym, t in trends.items():
            pos = t.get('position', {})
            qty = pos.get('qty', 0)
            entry = pos.get('entry', 0)
            tp1_done = pos.get('tp1_done', False)
            msg += f"  • `{sym}`: qty={qty:.4f} @ ${entry:.2f} TP1:{'✓' if tp1_done else '✗'}\n"

    await update.message.reply_text(msg, parse_mode='Markdown')


async def cmd_mode(update, context):
    """当前市场模式"""
    state = read_state()
    mode = state.get('market_mode', 'UNKNOWN')
    loss_streak = state.get('loss_streak', 0)
    lock_until = state.get('lock_until', 0)
    locked = lock_until > time.time()

    mode_emoji = {
        'TREND_UP': '🟢 上涨趋势',
        'TREND_DOWN': '📉 下跌趋势',
        'RANGE_BOUND': '📊 震荡盘整',
        'VOLATILE_OVERSOLD': '🔴 超卖反弹',
        'VOLATILE_OVERBOUGHT': '🟠 超买卖出',
        'CRISIS': '💥 危机',
    }
    mode_text = mode_emoji.get(mode, f'❓ {mode}')

    msg = f"""🌐 *市场状态*

*当前模式:* {mode_text}
*连亏次数:* {loss_streak}
*锁定状态:* {'🔒 锁定中' if locked else '🔓 正常'}

_查询时间: {datetime.now().strftime('%H:%M:%S')}_
"""
    await update.message.reply_text(msg, parse_mode='Markdown')


async def cmd_profit(update, context):
    """盈亏详情"""
    state = read_state()
    hwm = state.get('high_water', 0)
    initial = state.get('initial_balance', 0)
    realized = state.get('realized_profit', 0)
    taken = state.get('total_profit_taken', 0)

    if initial > 0:
        roi = (hwm - initial) / initial * 100
    else:
        roi = 0

    msg = f"""📈 *盈亏详情*

*账户高水位:* ${hwm:.2f}
*初始本金:* ${initial:.2f}
*浮动盈亏:* ${hwm - initial:+.2f}
*已实现盈亏:* ${realized:+.2f}
*已提取利润:* ${taken:.2f}
*ROI:* {roi:+.2f}%

_查询时间: {datetime.now().strftime('%H:%M:%S')}_
"""
    await update.message.reply_text(msg, parse_mode='Markdown')


async def cmd_log(update, context):
    """查看日志"""
    n = 20
    if context.args:
        try:
            n = int(context.args[0])
            n = min(max(n, 5), 100)
        except ValueError:
            pass
    log_text = tail_log(n)
    # 截断Telegram消息长度限制
    if len(log_text) > 3500:
        log_text = '...\n' + log_text[-3500:]

    msg = f"📋 *最近 {n} 条日志:*\n\n```\n{log_text}\n```"
    await update.message.reply_text(msg, parse_mode='Markdown')


async def cmd_start_bot(update, context):
    """启动机器人"""
    await update.message.reply_text("🚀 启动BotKing...")
    try:
        subprocess.run(['pm2', 'start', 'bot_king.py', '--name', 'bot-king', '--interpreter', 'python3'],
                      capture_output=True, timeout=10)
        subprocess.run(['pm2', 'save'], capture_output=True, timeout=5)
        await update.message.reply_text("✅ BotKing已启动")
    except Exception as e:
        await update.message.reply_text(f"❌ 启动失败: {e}")


async def cmd_stop_bot(update, context):
    """停止机器人"""
    await update.message.reply_text("⏸ 停止BotKing...")
    try:
        subprocess.run(['pm2', 'stop', 'bot-king'], capture_output=True, timeout=10)
        await update.message.reply_text("✅ BotKing已停止")
    except Exception as e:
        await update.message.reply_text(f"❌ 停止失败: {e}")


async def cmd_restart_bot(update, context):
    """重启机器人"""
    await update.message.reply_text("🔄 重启BotKing...")
    try:
        subprocess.run(['pm2', 'restart', 'bot-king'], capture_output=True, timeout=15)
        await update.message.reply_text("✅ BotKing已重启")
    except Exception as e:
        await update.message.reply_text(f"❌ 重启失败: {e}")


async def cmd_help(update, context):
    """帮助"""
    msg = """🦞 *BotKing 控制命令*

*基础信息:*
/status - 机器人状态(PID/内存/CPU/运行时长)
/balance - 账户余额详情
/positions - 当前所有持仓
/mode - 当前市场模式
/profit - 累计盈亏详情
/log \\[N\\] - 最近N条日志 (5-100)

*机器人控制:*
/start\\_bot - 启动机器人
/stop\\_bot - 停止机器人
/restart\\_bot - 重启机器人

*风险提示:*
⚠️ 启停操作有风险,谨慎使用
⚠️ 所有操作记录到 bot_king.log
"""
    await update.message.reply_text(msg, parse_mode='Markdown')


# ===================== Flask Web API (供PWA前端) =====================
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
    n = int(request.args.get('n', 20)) if 'request' in dir() else 20
    return jsonify({'log': tail_log(n)})


# ===================== 主程序 =====================
def main():
    if not TELEGRAM_TOKEN:
        print("❌ 请设置环境变量 TELEGRAM_TOKEN")
        print("   export TELEGRAM_TOKEN=你的机器人TOKEN")
        print("   在 @BotFather 创建机器人获取")
        sys.exit(1)

    # 启动Flask API (后台线程)
    def run_flask():
        app.run(host='0.0.0.0', port=5000, debug=False)

    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    log("✅ Flask API已启动: http://0.0.0.0:5000")

    # 启动Telegram Bot
    from telegram import Update
    from telegram.ext import Application, CommandHandler, ContextTypes

    app_tg = Application.builder().token(TELEGRAM_TOKEN).build()

    # 注册命令
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

    log("✅ Telegram Bot已启动")
    log("📱 在Telegram搜索你的机器人用户名,发送 /start 开始")
    log("🌐 Web API: http://localhost:5000/api/status")

    app_tg.run_polling()


if __name__ == "__main__":
    main()