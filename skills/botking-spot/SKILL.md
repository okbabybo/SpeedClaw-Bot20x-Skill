# BotKing Spot Skill

> BotKing 现货机器人 — 币安现货 USDT 双引擎量化策略
> 版本：v1.0 | 币种：BTC, ETH, BNB, SOL, AVAX, XRP, SUI
> 交易所：币安现货 USDT-M

---

## 目录

1. [快速启动](#1-快速启动)
2. [核心概念](#2-核心概念)
3. [市场模式](#3-市场模式)
4. [双引擎说明](#4-双引擎说明)
5. [风控矩阵](#5-风控矩阵)
6. [信号计算](#6-信号计算)
7. [配置说明](#7-配置说明)
8. [PM2管理](#8-pm2管理)
9. [快速命令](#9-快速命令)

---

## 1. 快速启动

### 安装依赖
```bash
pip3 install requests pyyaml
```

### 配置API
编辑 `/root/.openclaw/workspace/config_exchange.yaml`：
```yaml
exchanges:
  - name: binance
    api_key: "你的API密钥"
    secret: "你的API密码"
```

### 启动机器人
```bash
pm2 start /root/.openclaw/workspace/bot_king.py --name bot-king
```

### 查看状态
```bash
pm2 logs bot-king --nostream --lines 20
```

---

## 2. 核心概念

### 双引擎架构
```
BotKing
├── GridEngine（网格引擎）  → 震荡市专用，低买高卖反复收割
└── TrendEngine（趋势引擎） → 单边市专用，吃完整个趋势

两种引擎互不干扰，根据市场模式自动切换或同时运行
```

### 资金分配
| 账户余额 | 每币最大投入 |
|---------|------------|
| $20-50 | $50 |
| $50-200 | $150 |
| $200-1000 | $500 |
| >$1000 | $1500 |

---

## 3. 市场模式

BotKing 自动识别7种市场模式：

| 模式 | 条件 | 信号 |
|------|------|------|
| **TREND_UP** | ADX>25 + EMA20三周期同向上 | 🟢 趋势做多 |
| **TREND_UP_RECALL** | ADX>20 + 上升趋势 + RSI<40 | 📈 回调买入 |
| **RANGE_BOUND** | ADX<20 | 📊 网格套利 |
| **VOL_OVERSOLD** | 波幅>8% + RSI<35 + 放量/底背离 | 🔴 超卖反弹 |
| **VOL_OVERBOUGHT** | 波幅>8% + RSI>65 + 放量 | 🟠 超买止盈 |
| **TREND_DOWN** | ADX>25 + EMA20两周期同向下 | 📉 做空/观望 |
| **CRISIS** | 日线RSI>80 或 <20 | 💥 全部暂停 |

### 模式判断指标
```
EMA20（15m + 1H + 4H + 1D） → 方向
RSI（1H + 1D）              → 超买超卖 + 底背离
ADX（1H + 4H均值）          → 趋势强度
ATR（1H）                   → 波动率 → 网格格数自适应
成交量比率                   → 信号真假过滤
Fear & Greed                → 宏观情绪
```

---

## 4. 双引擎说明

### GridEngine（网格引擎）

**适用模式**：RANGE_BOUND、VOL_OVERSOLD

**原理**：把资金分成N格，每格等距分布。价格跌到某格就买，涨回来就卖。

```
例子（4格，间距0.6%）:
价格 →  格5止盈  格4  格3(中心)  格2  格1  格0买  格-1止损
       +0.6%   +0.4%   0%      -0.4%  -0.6%  -1.0%  -12%
```

**网格格数（ATR自适应）**：
| ATR波动率 | 格数 | 每格利润 |
|---------|------|---------|
| >5% | 2格 | 1.0% |
| 2-5% | 4格 | 0.6% |
| <2% | 6格 | 0.4% |

**追踪止损（TS）**：
- 激活：浮盈 > 6%
- 触发：价格从峰值回落 3%
- 动态上调：价格创新高 → TS触发价跟着上移

**网格区间动态重置**：
- 价格偏离网格中心 > 25% → 自动重新居中
- 避免单边行情下网格完全失效

---

### TrendEngine（趋势引擎）

**适用模式**：TREND_UP、TREND_UP_RECALL

**原理**：EMA确认方向，持有直到趋势破坏。不做短线高卖低买。

**买入信号**：
```
EMA20(1D + 4H + 1H) 三周期全部向上
ADX > 25（强趋势）
```

**分批止盈**：
| 阶段 | 条件 | 操作 |
|------|------|------|
| TP1 | 浮盈 ≥ +15% | 卖 50% |
| TP2 | 浮盈 ≥ +25% | 全卖 |

**趋势追踪止损（TS）**：
- 浮盈 > 15% 后激活
- 从峰值回落 5% → 全仓TS

**趋势破坏止损**：
- 从峰值回落 > 8% 且盈利 > 10%
- = 趋势已经破坏，立即止损

---

## 5. 风控矩阵

| 层级 | 触发条件 | 保护动作 |
|------|---------|---------|
| 1 | 余额 < $11 | 禁止开仓 |
| 2 | 单日亏损 > 8% | 暂停1小时 |
| 3 | 从高点回撤 > 20% | 全部止损 + 锁定30分钟 |
| 4 | 止损1次 | 冷静期5分钟 |
| 5 | 止损2次 | 冷静期10分钟 |
| 6 | 止损3次（熔断） | 暂停15分钟 |
| 7 | 3连亏+熊市 | 暂停至TREND_UP信号 |
| 8 | 日线RSI>80或<20 | 全部平仓暂停30分钟 |
| 9 | BTC熊市+关联币 | 降低该币开仓优先级 |
| 10 | 北京时间22:00-02:00 | 禁止开仓 |

### 关联性降权
```
BTC熊市时：
  ETH/BNB（关联>0.7）  → 仓位 ×0.3
  SOL/AVAX（关联0.6）  → 仓位 ×0.6
  XRP/SUI（关联<0.6）  → 仓位 ×1.0
```

### 置信度仓位
```
信号置信度：
  >80%  → 仓位 ×1.3（重仓）
  <65%  → 仓位 ×0.7（轻仓）
  <60%  → 不开仓
```

---

## 6. 信号计算

### 置信度评分（0-100%）

```
基础分 = 0%
+ ADX>25 → +20%
+ EMA20排列确认 → +15%
+ RSI底背离 → +15%
+ MACD同向 → +10%
+ Fear&Greed配合 → +10%
+ 交易量放大 → +10%
+ ATR适中 → +5%

低于60% → 禁止开仓
```

### Fear & Greed 宏观过滤
```
极度恐慌(<25)：超卖信号置信度 +15%
极度贪婪(>75)：超买信号置信度 +10%
每60分钟更新一次
```

### 交易量过滤
```
当前成交量 < 30日均量70% → 信号置信度 ×0.7
低量信号不可信
```

---

## 7. 配置说明

### 主要参数（bot_king.py 头部）

```python
COINS = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'AVAXUSDT', 'XRPUSDT', 'SUIUSDT']
GRID_PROFIT = 0.006    # 网格每格利润（0.6%）
GRID_COUNT = 4         # 默认网格格数
GRID_SL = 0.12         # 网格止损（-12%）
TP1 = 0.15             # 趋势TP1（+15%）
TP2 = 0.25             # 趋势TP2（+25%）
TS_START = 0.06        # 追踪止损激活（+6%）
TS_TRAIL = 0.03        # 追踪止损回落（-3%）
CHECK_INTERVAL = 20    # 主循环间隔（秒）
SCAN_INTERVAL = 180   # 市场扫描间隔（秒）
MAX_POSITIONS = 3     # 最大同时持仓数
```

---

## 8. PM2管理

### 启动
```bash
pm2 start /root/.openclaw/workspace/bot_king.py --name bot-king
```

### 重启
```bash
pm2 restart bot-king
```

### 查看日志
```bash
pm2 logs bot-king --nostream --lines 20
```

### 监控面板
```bash
pm2 monit
```

### 开机自启
```bash
pm2 save
pm2 startup
```

---

## 9. 快速命令

```bash
# 查看机器人状态
pm2 list | grep king

# 查看最新日志
pm2 logs bot-king --nostream --lines 10

# 重启机器人
pm2 restart bot-king

# 查看余额
grep "余额" /root/.openclaw/workspace/bot_king.log | tail -3

# 查看当前市场模式
grep "TREND\|RANGE\|VOL" /root/.openclaw/workspace/bot_king.log | tail -5

# 强制刷新状态文件
rm /root/.openclaw/workspace/bot_king_state.json
pm2 restart bot-king
```

---

## 文件路径

| 文件 | 路径 |
|------|------|
| 主脚本 | `/root/.openclaw/workspace/bot_king.py` |
| 状态文件 | `/root/.openclaw/workspace/bot_king_state.json` |
| 日志文件 | `/root/.openclaw/workspace/bot_king.log` |
| API配置 | `/root/.openclaw/workspace/config_exchange.yaml` |
| GitHub | `speedClaw-Bot20x-Skill/bot/bot_king.py` |

---

## 订阅信息

- 价格：$399.9 USDT/年
- 联系：@Okbabybo
- 订阅地址：https://okbabybo.github.io/SpeedClaw-Bot20x-Skill/
