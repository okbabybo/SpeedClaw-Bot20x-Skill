# SpeedClaw Bot20×

> **BTC + ETH 永续合约量化交易机器人**
>
> Binance USDT-M ·20x杠杆 · 多周期EMA确认 · StochRSI信号 · 趋势反转预警

**策略评分：87/100** | v5.2 | Python 3

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
| EMA趋势 | EMA20/50多头空头排列判断 |
| StochRSI信号 | 超买超卖捕捉精确入场点 |
| 趋势反转预警 | 实时监控趋势变化，提前推送预警 |
| 自动止损止盈 | 2%固定止损 + TP1/TP2分批出仓 |
| 趋势冲突过滤 | 4H与1H趋势矛盾时跳过信号 |

---

## 📊 策略优势

### 顺势交易
- 4H趋势向上 + 1H确认向上 +15M回调结束 → 做多
- 4H趋势向下 + 1H确认向下 + 15M反弹结束 → 做空

### 逆势交易
- RSI1H < 30 或 RSI1H > 70 时检测到极端位置
- 逆势开仓抓反弹/回调机会

### 风险管理
- 2%固定止损：每笔最大亏损2%
- 连亏3次暂停15分钟
- 账户回撤15%自动减半仓
- 总仓位不超过余额150%

---

## 💰 年度订阅

| 套餐 | 价格 | 收款地址（USDT BEP20） |
|------|------|----------------------|
| 年度订阅 | $79.9 | `0x352f5Cb1CA167500D27741676ab9efA4B07D3D30` |

### 使用流程

```
1. 向套餐地址转账USDT
2. 联系 Telegram @SpeedClawBot 或 邮箱 speedclawx@gmail.com
3. 提供转账截图 + 邮箱
4. 收到完整策略文件 🎉
```

---

## 📥 下载页面

**https://okbabybo.github.io/SpeedClaw-Bot20x-Skill/**

（打开后查看套餐信息和使用教程）

---

## 联系方式

| 方式 | 信息 |
|------|------|
| Telegram | @SpeedClawBot |
| Email | speedclawx@gmail.com |

---

## 🚀 快速开始

```bash
# 克隆仓库
git clone https://github.com/okbabybo/SpeedClaw-Bot20x-Skill.git
cd SpeedClaw-Bot20x-Skill/bot

# 配置
cp config.py.template config.py
# 编辑config.py填入你的Binance API密钥

# 启动
pm2 start bot_20x.py --name bot20x
```

---

## 📁 文件结构

```
speedClaw-Bot20x-Skill/
├── bot/
│   ├── bot_20x.py           # 主策略脚本（BTC+ETH双币种）
│   ├── config.py.template   # API配置模板
│   ├── license_manager.py   # 授权管理工具
│   └── startup_check.py # 启动检查
├── dashboard/
│   ├── bot_dashboard_api.py  # Web控制台后端
│   └── dashboard.html         # Web控制台界面
├── docs/
│   ├── index.html             # 下载页面
│   └── 策略手册.md            # 详细策略文档
├── skill/
│   └── SKILL.md              # OpenClaw Skill
├── LICENSE
└── README.md
```

---

## 📈 版本历史

| 版本 | 日期 | 重大更新 |
|------|------|----------|
| v5.2 | 2026-06-07 | 趋势冲突过滤 + 趋势反转预警 + API重试机制 |
| v5.1 | 2026-06-07 | 总仓位改为保证金计算，修复超仓bug |
| v5.0 | 2026-06-06 | ADX趋势判断 + ATR止损 + 连赢加速 + 逆势模式 |

---

## ⚠️ 免责声明

本项目仅供学习和研究使用。实盘交易存在风险，请确保：

1. 充分理解策略逻辑和风险
2. 使用小资金实盘测试
3. 持续监控策略运行状态
4. 自行承担交易盈亏

**作者不对任何交易损失负责。**

---

## License

MIT License