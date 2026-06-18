# SpeedClaw Bot20×

> **BTC + ETH 永续合约量化交易机器人**
>
> Binance USDT-M · 20x杠杆 · 多周期EMA确认 · StochRSI信号 · 趋势反转预警

**策略评分：87/100** | v5.4 | Python 3 | 胜率：100%(4/4全胜)

**🚀 订阅页面：https://okbabybo.github.io/SpeedClaw-Bot20x-Skill/**

---

## 🎯 交易品种

| 币种 | 合约 | 特点 |
|------|------|------|
| **BTC（比特币）** | BTCUSDT 永续合约 | 流动性最强，波动稳定 |
| **ETH（以太坊）** | ETHUSDT 永续合约 | 波动更大，机会更多 |

机器人同时监控 BTC 和 ETH，独立运行、独立计算仓位。

---

## ⚡ 核心特点

| 功能 | 说明 |
|------|------|
| 20x杠杆 | 迷你仓位运行，控制风险 |
| 多周期确认 | 4H主趋势 + 1H确认 + 15M入场 |
| EMA趋势 | EMA20多头空头排列判断 |
| StochRSI信号 | 超买超卖捕捉精确入场点 |
| 趋势反转预警 | 实时监控趋势变化，提前推送预警 |
| 自动止损止盈 | 2%固定止损 + TP1/TP2分批出仓 |
| 趋势冲突过滤 | 4H与1H趋势矛盾时跳过信号 |

---

## 💰 订阅价格

| 套餐 | 价格 | 说明 |
|------|------|------|
| 年度订阅 | **$399.9 USDT** | BSC (BEP20) 网络 |

---

## 📋 订阅流程

**第一步：联系购买**
> 复制以下地址，发送给我
```
Telegram：@Okbabybo
```

**第二步：付款**
> 我会发送收款地址给你
> 向指定地址转账 **$399.9 USDT**（BSC网络）

**第三步：获取授权**
> 付款后我直接发给你：
> - 授权码（1个）
> - 完整机器人安装包
> - 使用文档

---

## 📥 下载 & 安装

**仓库地址**：https://github.com/okbabybo/SpeedClaw-Bot20x-Skill

```bash
git clone https://github.com/okbabybo/SpeedClaw-Bot20x-Skill.git
cd SpeedClaw-Bot20x-Skill/bot
```

详细安装说明见 [策略手册](./docs/策略手册.md)

---

## 📊 实盘数据

| 指标 | 数据 |
|------|------|
| 胜率 | 100%（4/4全胜） |
| 账户收益 | +47.07%（$36 → $56.77） |
| 最大回撤 | <15% |
| 运行时间 | 稳定运行中 |

---

## 🚀 快速启动

```bash
# 克隆仓库
git clone https://github.com/okbabybo/SpeedClaw-Bot20x-Skill.git
cd SpeedClaw-Bot20x-Skill/bot

# 配置API
cp config.py.template config.py
# 填入你的Binance API密钥

# 启动
pm2 start bot_20x.py --name bot20x
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
│   ├── bot_20x.py           # 主策略脚本（BTC+ETH双币种）
│   ├── config.py.template   # API配置模板
│   ├── license_manager.py   # 授权管理工具
│   └── startup_check.py     # 启动检查
├── dashboard/
│   ├── bot_dashboard_api.py  # Web控制台后端
│   └── dashboard.html        # Web控制台界面
├── docs/
│   └── 策略手册.md          # 详细策略文档
├── payment/
│   └── payment_server.py    # 订阅页面
├── skill/
│   └── SKILL.md             # OpenClaw Skill
└── README.md
```

---

## 📈 版本历史

| 版本 | 日期 | 重大更新 |
|------|------|----------|
| v5.4 | 2026-06-09 | 启动自检API类型 + 安全模式(频繁重启则暂停) + api_retry_call防御性处理 |
| v5.3 | 2026-06-08 | 双模式趋势跟随 - 强趋势中RSI门槛自动放宽到55/45 |
| v5.2 | 2026-06-07 | 趋势冲突过滤 + 趋势反转预警 + API重试机制 |

---

## License

MIT License
