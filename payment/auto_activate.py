#!/usr/bin/env python3
"""
SpeedClaw 自动激活监控 - 方案B
==============================
监控老板USDT地址的BSC链上入账，自动匹配金额+Telegram备注，生成激活码自动发给客户。

工作流程:
1. 每15秒轮询老板USDT地址的最新Transfer事件
2. 解析input data中的Telegram ID备注 (memo)
3. 匹配金额: 59/399/1299 (月付/年付/终身)
4. 自动生成激活码 + 私信客户
5. 推送通知给Owner (含完整交易详情)

依赖:
  pip install web3 python-telegram-bot
"""
import os
import sys
import json
import time
import logging
import asyncio
import requests
from pathlib import Path
from web3 import Web3
try:
    from web3.middleware import ExtraDataToPOAMiddleware
    POA_MIDDLEWARE = ExtraDataToPOAMiddleware
except ImportError:
    try:
        from web3.middleware import geth_poa_middleware
        POA_MIDDLEWARE = geth_poa_middleware
    except ImportError:
        POA_MIDDLEWARE = None

# 配置
OWNER_WALLET = "0x344FfCe2f7B8f580D4e054F7213cb231CD15c3cd"
USDT_BSC_CONTRACT = "0x55d398326f99059fF775485246999027B3197955"
BSC_RPCS = [
    "https://bsc-dataseed.binance.org/",
    "https://bsc-dataseed1.binance.org/",
    "https://bsc-dataseed2.binance.org/",
    "https://bsc-dataseed3.binance.org/",
    "https://bsc-dataseed4.binance.org/",
    "https://bsc-dataseed1.defibit.io/",
    "https://bsc-dataseed1.ninicoin.io/",
]

# 订阅金额(USDT) → plan
# 客户在memo里指定产品: '现货'/'合约'/'通票' (默认现货)
# 金额表(每个产品独立价格):
#   现货 (king):  59/399/1299
#   合约 (20x):   59/399/1299
#   通票 (both):  99/599/1999
AMOUNT_TO_PLAN = {
    # 现货 (BotKing)
    59:   {'plan': 'monthly',  'days': 30,   'product': 'king',  'label': 'BotKing现货月付'},
    399:  {'plan': 'yearly',   'days': 365,  'product': 'king',  'label': 'BotKing现货年付'},
    1299: {'plan': 'lifetime', 'days': 36500,'product': 'king',  'label': 'BotKing现货终身'},
    # 合约 (Bot20x) — 用产品前缀区分
    # 合约同价表需要memo里有"合约"关键词
    # 通票 (现货+合约)
    99:   {'plan': 'monthly',  'days': 30,   'product': 'both',  'label': '现货+合约通票月付'},
    599:  {'plan': 'yearly',   'days': 365,  'product': 'both',  'label': '现货+合约通票年付'},
    1999: {'plan': 'lifetime', 'days': 36500,'product': 'both',  'label': '现货+合约通票终身'},
}

# Telegram配置
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
OWNER_TELEGRAM_ID = int(os.environ.get('OWNER_TELEGRAM_ID', '7204010604'))

# 状态文件
STATE_FILE = Path('/root/.openclaw/workspace/.auto_activate_state.json')
LOG_FILE = Path('/root/.pm2/logs/auto-activate-out.log')
LOG_DIR = Path('/root/.pm2/logs/')

# USDT ABI (只要Transfer事件)
USDT_ABI = [
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "from", "type": "address"},
            {"indexed": True, "name": "to", "type": "address"},
            {"indexed": False, "name": "value", "type": "uint256"}
        ],
        "name": "Transfer",
        "type": "event"
    }
]

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("auto_activate")


def load_state():
    if not STATE_FILE.exists():
        return {'last_block': 0, 'processed_txs': []}
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except:
        return {'last_block': 0, 'processed_txs': []}


def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)


def get_web3():
    for rpc in BSC_RPCS:
        try:
            w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={'timeout': 10}))
            if POA_MIDDLEWARE:
                try:
                    w3.middleware_onion.inject(POA_MIDDLEWARE, layer=0)
                except Exception as e:
                    log.debug(f"POA middleware inject fail: {e}")
            if w3.is_connected():
                log.info(f"✅ 连接BSC节点: {rpc}")
                return w3
        except Exception as e:
            log.warning(f"RPC {rpc} 失败: {e}")
    return None


def parse_memo_from_input(input_data):
    """从input data解析Telegram ID备注
    BEP-20 USDT transfer with memo: input = '0x' + '40 hex of memo length' + 'memo in hex'
    """
    if not input_data or input_data == '0x':
        return None
    try:
        # 跳过 method_id (4字节) + memo_length (32字节) + memo (32字节对齐)
        hex_data = input_data[2:] if input_data.startswith('0x') else input_data
        if len(hex_data) < 128:
            return None
        # memo length在第64-128字符
        memo_len = int(hex_data[64:128], 16)
        if memo_len == 0 or memo_len > 64:
            return None
        memo_hex = hex_data[128:128 + memo_len * 2]
        memo = bytes.fromhex(memo_hex).decode('utf-8', errors='ignore').strip('\x00').strip()
        return memo
    except Exception as e:
        log.debug(f"parse memo fail: {e}")
        return None


def extract_telegram_id(memo):
    """从memo提取Telegram ID
    支持格式: "7204010604" / "Telegram: 7204010604" / "tg:7204010604" / "ID:7204010604"
    """
    if not memo:
        return None
    import re
    # 先找9-10位连续数字
    m = re.search(r'\b(\d{9,10})\b', memo)
    if m:
        return int(m.group(1))
    return None


def send_telegram(chat_id, text):
    """发Telegram消息"""
    if not TELEGRAM_TOKEN:
        return False
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        r = requests.post(url, json={'chat_id': chat_id, 'text': text, 'parse_mode': 'Markdown'}, timeout=10)
        return r.json().get('ok', False)
    except Exception as e:
        log.error(f"Telegram send fail: {e}")
        return False


def generate_and_send_code(telegram_id, plan_info, tx_hash, amount):
    """生成激活码 + 自动发送给客户 + 通知Owner"""
    sys.path.insert(0, str(Path(__file__).parent.parent / 'bot'))
    from botking_auth import load_users, save_users, generate_activation_code, get_user_product, activate_code

    # 1. 找或注册用户
    db = load_users()
    user_key = str(telegram_id)
    if user_key not in db.get('users', {}):
        from botking_auth import register_user
        register_user(db, telegram_id, f"auto_{telegram_id}", f"Auto_{telegram_id}")

    # 2. 检查是否已激活过 (旧激活码若没过期则跳过)
    current_product = get_user_product(telegram_id)
    if current_product:
        log.info(f"用户 {telegram_id} 已激活(product={current_product})，跳过")
        return False, "已激活"

    # 3. 生成激活码
    db = load_users()
    code = generate_activation_code(
        db,
        duration_days=plan_info['days'],
        plan=plan_info['plan'],
        product=plan_info['product']
    )

    # 4. 立即激活该用户 (全自动)
    db = load_users()
    success, msg = activate_code(db, telegram_id, code)

    if not success:
        log.error(f"激活失败: {msg}")
        return False, msg

    # 5. 自动私信客户
    customer_msg = (
        f"🎉 **自动激活成功！**\n\n"
        f"检测到您的 USDT 入账\n"
        f"金额: ${amount} USDT\n"
        f"套餐: {plan_info['label']}\n"
        f"激活码: `{code}`\n\n"
        f"📋 **下一步**:\n"
        f"1. /bindapi 绑定你的Binance API\n"
        f"2. /kbalance 查看账户\n"
        f"3. /help 查看所有命令\n\n"
        f"💡 有问题联系 @okbobox"
    )
    send_telegram(telegram_id, customer_msg)

    # 6. 通知Owner
    owner_msg = (
        f"💰 **自动激活成功**\n\n"
        f"客户: `{telegram_id}`\n"
        f"金额: ${amount} USDT\n"
        f"套餐: {plan_info['label']}\n"
        f"激活码: `{code}`\n"
        f"交易: `{tx_hash[:20]}...`\n"
        f"🔗 https://bscscan.com/tx/{tx_hash}"
    )
    send_telegram(OWNER_TELEGRAM_ID, owner_msg)

    return True, code


def get_usdt_balance(w3):
    """获取老板地址的USDT余额 (wei)"""
    try:
        # USDT.balanceOf(address)
        selector = w3.keccak(text='balanceOf(address)').hex()[:10]
        addr_padded = '0x' + Web3.to_checksum_address(OWNER_WALLET)[2:].lower().rjust(64, '0')
        data = selector + addr_padded[2:]
        result = w3.eth.call({
            'to': Web3.to_checksum_address(USDT_BSC_CONTRACT),
            'data': data
        }, 'latest')
        return int(result.hex(), 16) if isinstance(result, bytes) else int.from_bytes(result, 'big')
    except Exception as e:
        log.error(f"get balance fail: {e}")
        return None


def scan_block(w3, block_number, owner_address):
    """扫描一个区块，查所有USDT Transfer给老板的交易
    使用 getBlockByNumber + 逐个eth_getTransactionByHash (不被限流)
    """
    try:
        block = w3.eth.get_block(block_number, full_transactions=True)
        if not block or not block.get('transactions'):
            return []

        # USDT合约的selector: 0xa9059cbb (transfer)
        USDT_TRANSFER_SELECTOR = '0xa9059cbb'
        owner_low = Web3.to_checksum_address(owner_address).lower()
        usdt_low = Web3.to_checksum_address(USDT_BSC_CONTRACT).lower()

        matched = []
        for tx in block['transactions']:
            try:
                to = tx.get('to')
                if not to or to.lower() != usdt_low:
                    continue
                # 必须是transfer to 老板
                input_data = tx.get('input', '0x')
                if not input_data or input_data == '0x':
                    continue
                if not input_data.lower().startswith(USDT_TRANSFER_SELECTOR):
                    continue
                # 解析 to address (前32字节去前12字节)
                to_in_tx = '0x' + input_data[34:74]
                if to_in_tx.lower() != owner_low:
                    continue

                # 解析 amount (后32字节)
                amount_hex = input_data[74:138]
                amount = int(amount_hex, 16) / 10**6

                # 剩余是memo
                memo_data = input_data[138:]  # 跳过methodId(8) + to(64) + amount(64)
                memo = ''
                if memo_data and len(memo_data) >= 128:
                    # memo length (32字节) + memo (N字节补齐到32)
                    memo_len = int(memo_data[:64], 16)
                    if 0 < memo_len <= 64:
                        memo_hex = memo_data[64:64 + memo_len * 2]
                        try:
                            memo = bytes.fromhex(memo_hex).decode('utf-8', errors='ignore').strip('\x00').strip()
                        except:
                            pass

                matched.append({
                    'tx_hash': tx['hash'].hex() if hasattr(tx['hash'], 'hex') else tx['hash'],
                    'amount': amount,
                    'memo': memo,
                })
            except Exception as ex:
                log.debug(f"parse tx fail: {ex}")
                continue

        return matched
    except Exception as e:
        log.error(f"scan_block {block_number} fail: {e}")
        return []


def main_loop():
    log.info("="*60)
    log.info("SpeedClaw 自动激活监控 - 方案B")
    log.info("="*60)
    log.info(f"监控地址: {OWNER_WALLET}")
    log.info(f"USDT合约: {USDT_BSC_CONTRACT}")
    log.info(f"订阅金额: {list(AMOUNT_TO_PLAN.keys())} USDT")
    log.info(f"轮询间隔: 15秒")
    log.info("")

    if not TELEGRAM_TOKEN:
        log.error("❌ TELEGRAM_TOKEN 未设置")
        return

    # 连接BSC
    w3 = get_web3()
    if not w3:
        log.error("❌ 所有BSC RPC都连不上")
        return

    state = load_state()

    # 初始化
    if state.get('last_block', 0) == 0:
        try:
            latest = w3.eth.block_number
            state['last_block'] = max(0, latest - 5)
            save_state(state)
            log.info(f"初始化扫描起点: block {state['last_block']}")
        except Exception as e:
            log.error(f"初始化失败: {e}")
            return

    if state.get('last_balance') is None:
        bal = get_usdt_balance(w3)
        if bal is not None:
            state['last_balance'] = bal
            save_state(state)
            log.info(f"初始USDT余额: {bal/10**6} USDT")

    log.info("✅ 开始监控 (余额变动触发模式)...")
    log.info("")

    owner_checksum = Web3.to_checksum_address(OWNER_WALLET)

    while True:
        try:
            latest = w3.eth.block_number
            current = state['last_block']
            current_balance = state.get('last_balance', 0)

            # 查最新余额
            new_balance = get_usdt_balance(w3)
            if new_balance is None:
                time.sleep(30)
                continue

            # 余额增加 → 触发扫描
            balance_increased = new_balance > current_balance

            if latest > current or balance_increased:
                if balance_increased:
                    log.info(f"💰 余额增加: {current_balance/10**6} → {new_balance/10**6} USDT")
                    # 余额增加：扫描最近10个块
                    start = max(current, latest - 10)
                else:
                    # 纯跟块：只扫最新块
                    start = current

                # 扫描新区块
                for bn in range(start + 1, latest + 1):
                    if bn % 100 == 0:
                        log.info(f"扫描区块 {bn}/{latest}...")

                    matched = scan_block(w3, bn, owner_checksum)
                    for tx_info in matched:
                        tx_hash = tx_info['tx_hash']
                        if tx_hash in state.get('processed_txs', []):
                            continue

                        amount = tx_info['amount']
                        memo = tx_info['memo']
                        telegram_id = extract_telegram_id(memo)

                        log.info(f"  TX {tx_hash[:16]}... amount={amount} memo='{memo}' tg={telegram_id}")

                        if not telegram_id:
                            state.setdefault('processed_txs', []).append(tx_hash)
                            continue

                        amount_int = int(amount)
                        plan_info = AMOUNT_TO_PLAN.get(amount_int)
                        if not plan_info:
                            log.info(f"  ⏭ 金额不匹配: {amount} USDT")
                            state.setdefault('processed_txs', []).append(tx_hash)
                            continue

                        # memo里有产品关键词 → 覆盖产品
                        memo_l = memo.lower()
                        if '合约' in memo or '20x' in memo_l or 'futures' in memo_l:
                            # 合约同价位 (59/399/1299)
                            product_override = '20x'
                            plan_info = dict(plan_info)
                            plan_info['product'] = '20x'
                            plan_info['label'] = plan_info['label'].replace('现货', '合约')
                            log.info(f"  → memo指定产品: 合约 (Bot20x)")
                        elif '通票' in memo or 'both' in memo_l or '套餐' in memo or '两个' in memo:
                            # 通票价不一样 (99/599/1999)
                            if amount_int in (99, 599, 1999):
                                log.info(f"  → memo指定产品: 通票")
                            else:
                                log.info(f"  ⚠ memo说通票但金额不匹配 ({amount})")
                                state.setdefault('processed_txs', []).append(tx_hash)
                                continue
                        elif '现货' in memo or 'king' in memo_l or 'spot' in memo_l:
                            # 现货 (默认)
                            pass
                        else:
                            # 未指定 → 默认现货
                            log.info(f"  → 未指定产品，默认现货")

                        state.setdefault('processed_txs', []).append(tx_hash)
                        save_state(state)

                        try:
                            ok, result = generate_and_send_code(
                                telegram_id, plan_info, tx_hash, amount_int
                            )
                            if ok:
                                log.info(f"  ✅ 自动激活成功: {telegram_id}")
                            else:
                                log.info(f"  ⚠ 跳过: {result}")
                        except Exception as ex:
                            log.error(f"  ❌ 失败: {ex}")

                    state['last_block'] = bn

                state['last_balance'] = new_balance
                save_state(state)
            else:
                log.debug(f"最新块 {latest}, 余额无变化")

            time.sleep(15)

        except KeyboardInterrupt:
            log.info("停止监控")
            break
        except Exception as e:
            log.error(f"loop error: {e}")
            time.sleep(30)
            w3 = get_web3()


if __name__ == "__main__":
    main_loop()
