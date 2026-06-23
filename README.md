# SpeedClaw 量化机器人家族

> **两大交易机器人 — 合约 + 现货双线作战**
>
> 订阅地址：https://okbabybo.github.io/SpeedClaw-Bot20x-Skill/

---

## 🦞 产品总览

| | **Bot20× 合约版** | **BotKing 现货版** |
|---|---|---|
| **交易类型** | 永续合约 | 现货 |
| **交易所** | Binance USDT-M | Binance 现货 |
| **杠杆** | 20x | 无（0x） |
| **核心策略** | 趋势追踪 + StochRSI | 网格套利 + 趋势双引擎 |
| **交易品种** | BTC, ETH | BTC, ETH, BNB, SOL, AVAX, XRP |
| **订阅价格** | $399.9/年 | $399.9/年 |
| **策略评分** | 87/100 | 91/100 |

---

## 🤖 Bot20× 永续合约版

> **BTC + ETH 永续合约 · 20x杠杆**
>
> **策略评分：87/100** | v5.4 | 胜率：100%(4/4全胜)

[→ 详细策略手册](./docs/策略手册.md)

### 核心特点
- 20x杠杆，迷你仓位控制风险
- 多周期确认（4H主趋势 + 1H确认 + 15M入场）
- EMA20趋势排列 + StochRSI精确入场
- 自动止损止盈（2%止损 + TP1/TP2分批出仓）
- 趋势反转预警，提前推送通知

### 订阅价格
| 套餐 | 价格 | 网络 |
|------|------|------|
| 年度订阅 | **$399.9 USDT** | BSC (BEP20) |

---

## 🤖 BotKing 现货版

> **6大币种现货 · 网格套利 + 趋势追踪双引擎**
>
> **策略评分：91/100** | v1.0 | 全天候运行

[→ BotKing策略手册](./docs/BotKing策略手册.md)

### 核心特点
- **双引擎**：网格套利（震荡市）+ 趋势追踪（单边市）
- **7种市场模式**全自动切换（TREND_UP/DOWN, RANGE_BOUND, VOL_OVERSOLD/OVERBOUGHT, CRISIS, TREND_UP_RECALL）
- **9层风控**：止损/熔断/回撤/日亏/极端时段/熊市锁定
- **多指标确认**：EMA + ADX + RSI底背离 + MACD + ATR自适应
- **Fear & Greed宏观过滤**：极度恐慌时超卖信号置信度+15%
- **无强平风险**：现货0杠杆，不会被交易所强平
- **手动平仓识别**：用户操作不影响机器人

### 订阅价格
| 套餐 | 价格 | 网络 |
|------|------|------|
| 年度订阅 | **$399.9 USDT** | BSC (BEP20) |

---

## 📋 订阅流程

**第一步：联系购买**
> Telegram：**@Okbabybo**

**第二步：付款**
> 我会发送收款地址
> 向指定地址转账 **$399.9 USDT**（BSC网络）

**第三步：获取授权**
> 付款后发送：
> - 授权码
> - 完整机器人安装包
> - 使用文档

---

## 📥 下载安装

**仓库地址**：https://github.com/okbabybo/SpeedClaw-Bot20x-Skill

### Bot20× 安装
```bash
git clone https://github.com/okbabybo/SpeedClaw-Bot20x-Skill.git
cd SpeedClaw-Bot20x-Skill/bot
cp config.py.template config.py
# 编辑 config.py 填入API密钥
pm2 start bot_20x.py --name bot20x
```

### BotKing 安装
```bash
cd SpeedClaw-Bot20x-Skill/bot
cp bot_king_config.py.template bot_king_config.py
# 编辑 bot_king_config.py 填入API密钥
pm2 start bot_king.py --name bot-king
```

---

## ⚠️ 免责声明

本项目仅供学习和研究使用。实盘交易存在风险，请确保：
1. 充分理解策略逻辑和风险
2. 使用小资金实盘测试
3. 持续监控策略运行状态
4. 自行承担交易盈亏

**作者不对任何交易损失负责。**

---

## 联系方式

| 方式 | 信息 |
|------|------|
| Telegram | **@Okbabybo** |
| Email | speedclawx@gmail.com |

---

## 📁 文件结构

```
speedClaw-Bot20x-Skill/
├── bot/
│   ├── bot_20x.py              # Bot20× 永续合约策略
│   ├── bot_king.py             # BotKing 现货机器人
│   ├── spot_adapter.py         # 现货API适配器
│   ├── bot_king_config.py.template
│   ├── config.py.template
│   └── license_manager.py
├── docs/
│   ├── 策略手册.md             # Bot20×策略手册
│   └── BotKing策略手册.md      # BotKing策略手册
├── dashboard/
├── payment/
└── README.md
```

---

## License

MIT License
