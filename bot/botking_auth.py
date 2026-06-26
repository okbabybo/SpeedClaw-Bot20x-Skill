#!/usr/bin/env python3
"""
BotKing 用户认证与权限管理
==============================
三层权限:
  👑 Owner - 老板(完全控制)
  🛡️ Admin - 付费用户(自己机器人的完全控制)
  👤 User  - 试用用户(只读)

用户数据隔离:
  每个用户有自己的配置、API密钥、状态文件
"""
import json
import time
import os
from pathlib import Path
from datetime import datetime
import secrets

# ===================== 路径 =====================
USER_DB_FILE = Path('/root/.openclaw/workspace/botking_users.json')

# 老板的Telegram ID (最高权限)
# 注: 这里需要老板告诉我他的Telegram ID才能完成权限分离
OWNER_TELEGRAM_ID = int(os.environ.get('OWNER_TELEGRAM_ID', '0'))


# ===================== 用户管理 =====================
def load_users():
    if not USER_DB_FILE.exists():
        # 创建默认数据库,老板ID=1时自动拥有owner
        return {"users": {}, "admins": {}, "owner": None, "pending_codes": {}}
    try:
        with open(USER_DB_FILE) as f:
            return json.load(f)
    except:
        return {"users": {}, "admins": {}, "owner": None, "pending_codes": {}}


def save_users(db):
    USER_DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(USER_DB_FILE, 'w') as f:
        json.dump(db, f, indent=2, ensure_ascii=False)


def get_user_level(db, telegram_id):
    """获取用户级别: owner/admin/user/unknown"""
    telegram_id = str(telegram_id)

    # 1. 检查Owner
    if db.get('owner') and str(db['owner'].get('telegram_id', '')) == telegram_id:
        return 'owner'

    # 2. 检查Admin (付费用户)
    if telegram_id in db.get('admins', {}):
        admin = db['admins'][telegram_id]
        # 检查是否过期
        if admin.get('expire_at', 0) > time.time():
            return 'admin'
        else:
            return 'expired'

    # 3. 普通用户
    if telegram_id in db.get('users', {}):
        return 'user'

    return 'unknown'


def is_owner(db, telegram_id):
    return get_user_level(db, telegram_id) == 'owner'


def is_admin(db, telegram_id):
    level = get_user_level(db, telegram_id)
    return level in ('owner', 'admin')


def register_user(db, telegram_id, username='', first_name=''):
    """注册新用户 (默认user级别)"""
    telegram_id = str(telegram_id)
    if telegram_id not in db['users']:
        db['users'][telegram_id] = {
            'telegram_id': telegram_id,
            'username': username,
            'first_name': first_name,
            'registered_at': time.time(),
            'last_active': time.time(),
            'api_bound': False,
        }
        save_users(db)
    else:
        db['users'][telegram_id]['last_active'] = time.time()
        if username:
            db['users'][telegram_id]['username'] = username
        if first_name:
            db['users'][telegram_id]['first_name'] = first_name
        save_users(db)
    return db['users'][telegram_id]


def generate_activation_code(db, duration_days=365, plan='yearly', product='both'):
    """生成激活码 (老板后台用)

    Args:
        product: 'king' (现货) / '20x' (合约) / 'both' (现货+合约)
    """
    code = secrets.token_urlsafe(12).upper().replace('_', '').replace('-', '')[:16]
    db['pending_codes'][code] = {
        'code': code,
        'plan': plan,
        'product': product,  # king=现货, 20x=合约, both=通票
        'duration_days': duration_days,
        'created_at': time.time(),
        'used_by': None,
        'used_at': None,
    }
    save_users(db)
    return code


def activate_code(db, telegram_id, code):
    """用户输入激活码,升级为admin"""
    telegram_id = str(telegram_id)
    code = code.upper().strip()

    if code not in db.get('pending_codes', {}):
        return False, "激活码无效"

    code_info = db['pending_codes'][code]
    if code_info.get('used_by'):
        return False, "激活码已被使用"

    # 激活
    code_info['used_by'] = telegram_id
    code_info['used_at'] = time.time()
    duration = code_info['duration_days']
    plan = code_info['plan']

    # 升级为admin
    db['admins'][telegram_id] = {
        'telegram_id': telegram_id,
        'activated_at': time.time(),
        'expire_at': time.time() + duration * 86400,
        'plan': plan,
        'product': code_info.get('product', 'both'),  # 默认both兼容旧码
        'code_used': code,
        'api_key': None,    # 用户自己的API密钥
        'api_secret': None,
        'bound_symbols': [],  # 用户可以交易的币种
    }

    save_users(db)
    product = code_info.get('product', 'both')
    product_name = {'king': 'BotKing现货', '20x': 'Bot20x合约', 'both': '现货+合约通票'}.get(product, product)
    return True, f"激活成功!{plan}会员 ({product_name}),有效期{duration}天"


def get_user_product(telegram_id):
    """获取用户的产品权限: king / 20x / both"""
    db = load_users()
    admin = db.get('admins', {}).get(str(telegram_id))
    if admin and admin.get('expire_at', 0) > time.time():
        return admin.get('product', 'both')
    return None


def has_product_access(telegram_id, product):
    """检查用户是否有某个产品的权限
    product: 'king' 或 '20x'
    """
    user_product = get_user_product(telegram_id)
    if not user_product:
        return False
    if user_product == 'both':
        return True
    return user_product == product


def bind_api(db, telegram_id, api_key, api_secret):
    """绑定用户自己的Binance API"""
    telegram_id = str(telegram_id)
    if telegram_id not in db.get('admins', {}):
        return False, "请先激活订阅"

    db['admins'][telegram_id]['api_key'] = api_key
    db['admins'][telegram_id]['api_secret'] = api_secret
    save_users(db)
    return True, "API绑定成功"


def get_user_api(db, telegram_id):
    """获取用户绑定的API"""
    telegram_id = str(telegram_id)
    level = get_user_level(db, telegram_id)
    if level in ('owner', 'admin'):
        admin = db['admins'].get(telegram_id, {})
        return admin.get('api_key'), admin.get('api_secret')
    return None, None


def list_users(db, level_filter=None):
    """列出用户"""
    if level_filter == 'all':
        return {
            'owner': db.get('owner'),
            'admins': db['admins'],
            'users': db['users'],
        }
    elif level_filter == 'admin':
        return db['admins']
    elif level_filter == 'user':
        return db['users']
    return {}


# ===================== 授权检查装饰器 =====================
def require_owner(func):
    """只允许Owner执行"""
    async def wrapper(update, context, *args, **kwargs):
        from botking_telegram import load_users, get_user_level
        db = load_users()
        uid = update.effective_user.id
        level = get_user_level(db, uid)
        if level != 'owner':
            await update.message.reply_text(
                "🚫 此命令仅限Owner使用\n\n"
                f"你的权限级别: {level}\n"
                "如有需要请联系老板 @okbobox"
            )
            return
        return await func(update, context, *args, **kwargs)
    return wrapper


def require_admin(func):
    """允许Owner/Admin执行"""
    async def wrapper(update, context, *args, **kwargs):
        from botking_telegram import load_users, get_user_level
        db = load_users()
        uid = update.effective_user.id
        level = get_user_level(db, uid)
        if level not in ('owner', 'admin'):
            await update.message.reply_text(
                "🚫 此命令需要订阅会员\n\n"
                "免费用户仅可使用:\n"
                "• /start - 注册\n"
                "• /subscribe - 查看订阅方案\n"
                "• /mysub - 我的订阅状态\n\n"
                "完整功能请订阅BotKing/Bot20x"
            )
            return
        return await func(update, context, *args, **kwargs)
    return wrapper