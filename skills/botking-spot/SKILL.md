# BotKing Spot Skill

> BotKing 现货机器人 — 币安现货 USDT 双引擎量化策略
> **版本：v1.2** | 币种：BTC, ETH, BNB, SOL, AVAX, XRP, SUI
> 交易所：币安现货 USDT-M

---

## 目录

1. [快速启动](#1-快速启动)
2. [核心概念](#2-核心概念)
3. [市场模式](#3-市场模式)
4. [双引擎说明](#4-双引擎说明)
5. [v1.2核心修复](#5-v12核心修复)
6. [风控矩阵](#6-风控矩阵)
7. [信号计算](#7-信号计算)
8. [配置说明](#8-配置说明)
9. [PM2管理](#9-pm2管理)
10. [快速命令](#10-快速命令)

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

**v1.2网格参数（ATR自适应）**：
| ATR波动率 | 格数 | 每格利润 | 止损 |
|---------|------|---------|------|
| >5% | 2格 | 1.5% | -2% |
| 2-5% | 4格 | 0.5% | -2% |
| <2% | 6格 | 0.33% | -2% |

**分批建仓**：
- Phase1：先开1-2格（真实资本，TP=1%）
- Phase2：止盈后等5分钟，用锁定利润开（TP=0.75%，无真实风险）

**追踪止损（TS）**：
- 激活：浮盈 > 1.5%
- 触发：价格从峰值回落 1.5%
- 动态上调：价格创新高 → TS触发价跟着上移

**网格区间动态重置**：
- 价格偏离网格中心 > 25% → 自动重新居中

---

### TrendEngine（趋势引擎）

**适用模式**：TREND_UP、TREND_UP_RECALL

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

---

## 5. v1.2核心修复

### 修复1：网格期望值彻底重建（最关键）

> v1.0/v1.1致命问题：SL=8% + TP=0.4% → 需要95%胜率才回正，实际不可能

| 参数 | v1.0/v1.1 | **v1.2** | 改善 |
|------|-----------|---------|------|
| 每格利润 | 0.4% | **1.0%** | ×2.5 |
| 止损 | 8% | **2%** | 收窄到1/4 |
| 盈亏比 | 1:20 | **1:2** | 合理化 |
| 最低胜率 | 95% | **50%** | 现实可达 |
| TS激活 | 4% | **1.5%** | 更早锁利 |
| Phase2 TP | 同Phase1 | **0.75%** | 区分风险 |

**4格完整期望值（Phase1=2格，Phase2=2格利润开）**：

| 胜率 | 期望值/周期 | 评价 |
|------|-----------|------|
| 50% | +1.16% | ✅ 仍正期望 |
| 60% | +1.84% | ✅ 良好 |
| 70% | +2.39% | ✅ 优秀 |

### 修复2：API限速与熔断机制

```
- 60秒窗口最多900请求（币安上限1200）
- 连续50次API失败 → 熔断120秒
- 所有API调用前自动限速检查
```

### 修复3：多币关联性敞口检查

```
- BTC熊市时：
  ETH/BNB(≥0.80) → ×0.3
  SOL/AVAX(≥0.60) → ×0.5
  XRP(<0.60) → ×0.8
- 已持有高相关币，新开同档 → 再×0.5
- 总敞口>2.5 → 全部仓位再×0.6
```

---

## 6. 风控矩阵

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
| 9 | API连续50次失败 | 熔断120秒 |
| 10 | 北京时间22:00-02:00 | 禁止开仓 |

---

## 7. 信号计算

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

---

## 8. 配置说明

### 主要参数（bot_king.py 头部）

```python
# ---- 网格引擎参数（v1.2核心修复）----
GRID_PROFIT     = 0.010    # Phase1每格1%
GRID_VOL_PROFIT = 0.015    # 高波动每格1.5%
GRID_SL_PCT     = 0.02    # 网格止损2%（收窄到1/4！）
TS_PCT          = 0.015   # 追踪止损回撤1.5%
GRID_PHASE2_TP  = 0.0075  # Phase2每格0.75%

# ---- 趋势引擎参数（保持不变）----
SL_PCT          = 0.12     # 趋势止损12%
TP_TREND1       = 0.15     # 趋势TP1+15%
TP_TREND2       = 0.25     # 趋势TP2+25%
TS_TREND_PCT    = 0.05     # 趋势追踪回撤5%

# ---- API熔断参数 ----
API_MAX_REQUESTS = 900
API_CIRCUIT_BREAKER_THRESHOLD = 50
API_CIRCUIT_BREAKER_PAUSE = 120
```

---

## 9. PM2管理

```bash
pm2 start /root/.openclaw/workspace/bot_king.py --name bot-king
pm2 restart bot-king
pm2 logs bot-king --nostream --lines 20
pm2 save
```

---

## 10. 快速命令

```bash
pm2 list | grep king
pm2 logs bot-king --nostream --lines 10
grep "余额" /root/.openclaw/workspace/bot_king.log | tail -3
grep "TREND\|RANGE\|VOL" /root/.openclaw/workspace/bot_king.log | tail -5
rm /root/.openclaw/workspace/bot_king_state.json && pm2 restart bot-king
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
