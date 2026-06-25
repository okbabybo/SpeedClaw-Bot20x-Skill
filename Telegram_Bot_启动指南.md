# 🦞 BotKing Telegram Bot - 5分钟启动指南

## 第1步：创建Telegram机器人（2分钟）

### 1.1 找 @BotFather
在Telegram搜索 `@BotFather`（官方机器人，有蓝色对勾）

### 1.2 发送 `/newbot`
```
你: /newbot
BotFather: Alright, a new bot. How are we going to call it?
         Please choose a name for your bot.
你: BotKing 我的量化机器人
BotFather: Good. Now let's choose a username for your bot.
         It must end in `bot`. Like this, for example: TetrisBot or tetris_bot.
你: my_botking_bot
BotFather: Done! Congratulations on your new bot.
         You will find it at t.me/my_botking_bot
         Use this token to access the HTTP API:
         7123456789:AAHxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
         ...
```

**复制那串token**（格式：`数字:字母数字混合`）

### 1.3 （可选）设置机器人信息
```
/setdescription - 设置机器人简介
/setabouttext - 设置关于信息
/setuserpic - 设置头像
```

## 第2步：部署BotKing（1分钟）

### 2.1 SSH到服务器
```bash
ssh root@your-server
cd /root/.openclaw/workspace
```

### 2.2 设置Token
```bash
export TELEGRAM_TOKEN="刚才复制的token"
echo 'export TELEGRAM_TOKEN="你的token"' >> ~/.bashrc  # 持久化
```

### 2.3 启动Telegram Bot
```bash
# 方式1: 前台运行（看日志）
python3 bot/botking_telegram.py

# 方式2: PM2守护（推荐）
pm2 start "python3 bot/botking_telegram.py" --name botking-tg
pm2 save
```

## 第3步：第一次使用（30秒）

### 3.1 在Telegram找到你的机器人
- 搜索 `@my_botking_bot`
- 点 **START** 或发送 `/start`

### 3.2 试试这些命令
```
/start       - 欢迎语
/status      - 查看机器人状态
/balance     - 账户余额
/positions   - 当前持仓
/mode        - 市场模式
/profit      - 累计盈亏
/log 20      - 最近20条日志
```

## 故障排查

### Bot不响应
```bash
# 查看Telegram Bot日志
pm2 logs botking-tg --nostream --lines 30
```

### Token错误
```bash
# 重新设置token
export TELEGRAM_TOKEN="新的token"
pm2 restart botking-tg
```

### BotKing状态读不到
- 确保bot_king.py正在运行
- 检查 `/root/.openclaw/workspace/bot_king_state.json` 存在

## 高级配置

### 只允许自己使用
修改 `bot/botking_telegram.py`:
```python
ADMIN_CHAT_ID = 123456789  # 你的Telegram用户ID
# 找ID: 搜索 @userinfobot 获取
```

### 添加到机器人回复
```python
async def cmd_status(update, context):
    if update.effective_user.id != ADMIN_CHAT_ID:
        await update.message.reply_text("🚫 未授权")
        return
    # ... 原逻辑
```

## 常用命令速查

| 命令 | 功能 |
|------|------|
| /start | 欢迎语 |
| /status | 机器人状态 |
| /balance | 账户余额 |
| /positions | 当前持仓 |
| /mode | 市场模式 |
| /profit | 累计盈亏 |
| /log [N] | 最近N条日志 |
| /start_bot | 启动BotKing |
| /stop_bot | 停止BotKing |
| /restart_bot | 重启BotKing |
| /help | 帮助 |

## 一键部署脚本

```bash
#!/bin/bash
# quick_deploy_tg.sh

echo "🦞 BotKing Telegram Bot 一键部署"
echo ""

# 检查环境
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3未安装"
    exit 1
fi

# 安装依赖
echo "📦 安装依赖..."
pip3 install -q python-telegram-bot flask

# 获取token
read -p "请输入你的Telegram Bot Token: " TG_TOKEN
if [ -z "$TG_TOKEN" ]; then
    echo "❌ Token不能为空"
    exit 1
fi

# 保存到.bashrc
grep -v TELEGRAM_TOKEN ~/.bashrc > /tmp/bashrc_temp
echo "export TELEGRAM_TOKEN=\"$TG_TOKEN\"" >> /tmp/bashrc_temp
mv /tmp/bashrc_temp ~/.bashrc
export TELEGRAM_TOKEN="$TG_TOKEN"

# PM2启动
pm2 delete botking-tg 2>/dev/null
pm2 start "python3 bot/botking_telegram.py" --name botking-tg
pm2 save

echo ""
echo "✅ 部署完成!"
echo "📱 在Telegram搜索你的机器人用户名"
echo "📋 查看日志: pm2 logs botking-tg"
```

---

> 🦞 完成后老板就有一个完全私有的Telegram控制面板
> 任何时候打开Telegram就能看交易状态、控机器