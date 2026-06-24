# SpeedClaw BotKing v1.3 — 新手完全上手指南

> 给完全没用过的小白：如何安装 → 启动 → 调教 → 让BotKing自己赚钱

---

## 📖 目录

- [第0章：5分钟理解BotKing是什么](#第0章5分钟理解botking是什么)
- [第1章：环境准备](#第1章环境准备-15分钟)
- [第2章：安装BotKing](#第2章安装botking-15分钟)
- [第3章：配置交易所](#第3章配置交易所-15分钟)
- [第4章：启动BotKing](#第4章启动botking-10分钟)
- [第5章：观察与监控](#第5章观察与监控)
- [第6章：训练AI工作路径](#第6章训练ai工作路径)
- [第7章：常见问题FAQ](#第7章常见问题faq)

---

## 第0章：5分钟理解BotKing是什么

### BotKing 是干什么的？

| 项目 | 说明 |
|------|------|
| **类型** | 现货智能交易机器人（不是合约！）|
| **标的** | BTC / ETH / BNB / SOL / AVAX / XRP / SUI 共7个币种 |
| **策略** | 双引擎：网格震荡 + 趋势跟踪 |
| **交易所** | 币安现货（Binance Spot） |
| **资金门槛** | 最低 $20 USDT，建议 $50+ |
| **风险等级** | 中等（已8层风控） |

### 网格策略 vs 趋势策略

```
震荡市 (RANGE_BOUND)：价格来回震荡
  → 用网格：低买高卖，每格赚1%，亏0.5%止损
  
上涨趋势 (TREND_UP)：价格持续走高  
  → 用趋势：分批止盈 TP1=15%, TP2=25%, SL=12%

下跌/危机：不开仓 or 平仓走人
```

### 为什么用BotKing而不是自己炒？

- ✅ **不睡觉** — 7×24小时自动监控
- ✅ **不情绪化** — 没有恐惧和贪婪
- ✅ **风控完善** — 8层保护机制
- ✅ **精算胜率** — 蒙特卡洛验证正EV

---

## 第1章：环境准备（15分钟）

### 1.1 硬件要求

| 项目 | 最低 | 推荐 |
|------|------|------|
| CPU | 1核 | 2核 |
| 内存 | 2GB | 4GB |
| 硬盘 | 10GB | 20GB |
| 网络 | 稳定宽带 | 固定IP（云服务器） |

### 1.2 系统要求

- ✅ Ubuntu 20.04+ / Debian 11+ / macOS 12+
- ✅ 任何能跑 Python 的系统都行

### 1.3 注册币安账户

1. 打开 https://www.binance.com 注册
2. 完成 KYC（实名认证）
3. 充值 USDT（BEP20网络最便宜）
4. **最少充值 $20**

---

## 第2章：安装BotKing（15分钟）

### 2.1 安装 Python 和依赖

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3 python3-pip git -y

# 检查版本
python3 --version  # 应该 >= 3.8
```

### 2.2 克隆代码

```bash
git clone https://github.com/okbabybo/SpeedClaw-Bot20x-Skill.git
cd SpeedClaw-Bot20x-Skill/bot
```

### 2.3 安装 Python 依赖

```bash
pip3 install requests pandas numpy
```

### 2.4 安装 PM2（守护进程）

```bash
# 安装Node.js
curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
sudo apt install -y nodejs

# 安装PM2
sudo npm install -g pm2
```

---

## 第3章：配置交易所（15分钟）

### 3.1 创建币安 API Key

1. 登录币安 → 用户中心 → API管理
2. 创建API，**只勾选"现货交易"**
3. **关闭提币权限**（重要！）
4. 绑定 IP 白名单（你的服务器IP）
5. 保存好：
   - API Key
   - Secret Key

### 3.2 填写配置文件

编辑 `bot/config_exchange.yaml`：

```yaml
binance:
  api_key: "你的API_KEY"
  api_secret: "你的SECRET_KEY"
  testnet: false
```

⚠️ **绝对不要把这个文件上传到 GitHub！**

---

## 第4章：启动BotKing（10分钟）

### 4.1 测试启动

```bash
cd SpeedClaw-Bot20x-Skill/bot
python3 bot_king.py
```

你应该看到类似输出：
```
[启动] BotKing v1.3 启动
[宏观] Fear & Greed: 17 (Extreme Fear)
  📊⚪ BTCUSDT    $  62804.6500 | RSI= 65.5 ADX=  38 | FG 17
  ...
```

按 `Ctrl+C` 退出（只是测试）。

### 4.2 用 PM2 守护运行

```bash
pm2 start "python3 bot_king.py" --name bot-king
pm2 save
pm2 startup
```

现在BotKing在后台运行，关掉终端也不会停。

### 4.3 查看状态

```bash
pm2 list              # 查看所有进程
pm2 logs bot-king     # 查看日志
pm2 restart bot-king  # 重启
pm2 stop bot-king     # 停止
```

---

## 第5章：观察与监控

### 5.1 日志文件位置

```
/root/.openclaw/workspace/spot_bot.log
```

### 5.2 关键日志解读

```log
[06/24 17:31:10] [宏观] Fear & Greed: 17 (Extreme Fear)
[06/24 17:31:10]   📊⚪ BTCUSDT    $  62804 | RSI= 65 ADX= 38 | FG 17 | 60% | RANGE_BOUND
                                        ↑价格   ↑RSI  ↑ADX   ↑情绪  ↑置信  ↑市场模式
[06/24 17:31:10] [📊 关联敞口] 当前总暴露: 0.00 (BTC=1.0基准)
[06/24 17:31:10] [7] 网格0格 | 趋势0仓 | 总投入$0.00 | 盈亏$0.00
                                          ↑当前仓位状态
```

### 5.3 健康检查清单

每天至少检查一次：

- [ ] PM2 进程 online
- [ ] 日志没有 ERROR
- [ ] 余额正常
- [ ] 持仓数符合预期

---

## 第6章：训练AI工作路径

### 6.1 AI 分工：让 AI 帮你做这些

| 任务 | 谁来做 |
|------|--------|
| 启动/停止 Bot | AI 自动 |
| 查看账户余额 | AI 自动（PM2 + API）|
| 分析行情 | AI 每天主动汇报 |
| 风险预警 | AI 实时监控 |
| 策略调优 | **AI 主动建议，你决定** |
| 实盘交易 | AI 自动 + 8层风控 |

### 6.2 给 AI 的指令模板

**每日报告**：
```
给我今日交易报告：账户余额、今日盈亏、开仓情况、风险评估
```

**行情分析**：
```
分析 BTC/ETH 当前走势，给出多空判断和操作建议
```

**策略调整**：
```
我看到市场大跌，BotKing 会怎么处理？需要手动干预吗？
```

**紧急处理**：
```
立刻平掉所有仓位，停止交易
```

### 6.3 AI 应该主动做的事

✅ **主动监控**：定期检查 PM2 状态
✅ **主动汇报**：发现异常立刻告诉你
✅ **主动记录**：所有重要事件写进 MEMORY.md
✅ **主动学习**：从亏损中总结经验

### 6.4 你应该做的事

✅ **充值管理**：保持账户有 $20+ USDT
✅ **关键决策**：大额充值/提现、停止交易
✅ **定期复盘**：每周看一次 BotKing 表现
✅ **信任 AI**：让 AI 自动跑，别天天盯盘

---

## 第7章：常见问题FAQ

### Q1: BotKing 会亏光我的钱吗？
A: 不会。有8层风控：单日8%亏损暂停、日亏5%减仓、连亏暂停、关联性过滤、CRISIS不交易等。

### Q2: 最低需要多少钱？
A: $20 USDT，但建议 $50+ 才能更好分散。

### Q3: 能用合约吗？
A: 不能。BotKing 只做**现货**，合约请用 Bot20x。

### Q4: 为什么开不了仓？
A: 检查：
- 余额是否 ≥ $20
- 市场模式是不是 RANGE_BOUND/TREND_UP
- API Key 权限是否正确

### Q5: 多久能赚钱？
A: 蒙特卡洛验证 vol=1% 时 +0.12%/周期 ≈ 月化 +60%~+200%（取决于循环频率）。实盘会有滑点和手续费，实际可能更低。

### Q6: 出错了怎么办？
A:
```bash
pm2 logs bot-king --lines 50   # 看错误日志
pm2 restart bot-king            # 重启
```
还是不行就找 AI 帮你看日志。

### Q7: 怎么升级版本？
A: AI 会自动 git pull + pm2 restart，你只需要确认。

---

## 🦞 总结：从0到运行

```bash
# 1. 安装环境
sudo apt install python3 python3-pip git -y
curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
sudo apt install -y nodejs
sudo npm install -g pm2

# 2. 克隆代码
git clone https://github.com/okbabybo/SpeedClaw-Bot20x-Skill.git
cd SpeedClaw-Bot20x-Skill/bot
pip3 install requests pandas numpy

# 3. 配置API
nano config_exchange.yaml
# 填入 binance api_key 和 api_secret

# 4. 启动
pm2 start "python3 bot_king.py" --name bot-king
pm2 save && pm2 startup

# 5. 监控
pm2 logs bot-king
```

**总计：1小时内完成从安装到运行。** 🦞
