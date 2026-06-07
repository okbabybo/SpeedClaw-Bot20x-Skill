# speedClaw Bot20x - OpenClaw Strategy Skill

## Skill Metadata

|字段 | 值 |
|------|------|
| Name | speedClaw Bot20x |
| Version | v5.2 |
| Author | okbabbo |
| Description | Binance USDT-M永续合约20x杠杆量化交易策略 |
| Tags | trading, binance, perpetual, 20x-leverage |
| Trigger | "bot20x", "speedClaw", "量化交易" |

---

## 核心能力

### 1. 策略执行
- 自动监控BTC/ETH永续合约信号
- 市价开仓/平仓
-追踪止盈（TP1/TP2）

### 2. 风险管理
- 固定2%止损
- 复利风控（余额动态调整）
- 回撤保护 +熔断机制
- 总仓位按保证金计算（已修复）

### 3. 信号系统
- EMA20多周期趋势确认
- StochRSI超买超卖捕捉
- 逆势反弹/回调信号
- 趋势冲突过滤（v5.2新增）

### 4. 预警机制
- 趋势反转预警（v5.2新增）
- API重试机制（v5.2新增）
- PM2进程守护

---

## 使用方法

### 启动Bot

```bash
pm2 start /root/.openclaw/workspace/bot_20x.py --name bot20x
```

### 查看状态

```bash
pm2 list | grep bot20x
tail -20 /root/.openclaw/workspace/bot_20x.log
```

### 手动平仓

通过Web控制台：http://43.129.181.252:5000

或直接执行：

```python
# 平仓BTC SHORT
do_order("BTCUSDT", "BUY", "SHORT", 0.001)
# 平仓ETH SHORT
do_order("ETHUSDT", "BUY", "SHORT", 0.008)
```

---

## 策略参数

| 参数 | 值 | 说明 |
|------|------|------|
| LEVER | 20x | 杠杆 |
| SL_ATR_MULT | 0.02 | 2%固定止损 |
| TP1_PCT | 0.02 | 2%出半场 |
| TP2_TRIGGER | 0.04 | 4%出清 |
| TP2_BUFFER | 0.008 | 0.8%追踪回撤 |
| TREND_CONFLICT_FILTER | True | 趋势冲突过滤 |
| API_RETRY_MAX | 3 | 重试3次 |

---

## 信号评分规则

### 做多（≥6.5分触发）

- RSI1H < 40 → +1
- RSI4H < 50 → +1
- RSI15M < 40 → +1
- 趋势向上 → +1
- StochRSI15M < 20 → +2
- StochRSI1H < 20 → +1
- RSI底背离 → +2

### 做空（≥6.5分触发）

- RSI1H > 35 → +1
- RSI4H ≥15 且 <60 → +1
- 趋势向下 → +1
- StochRSI15M > 80 → +2
- StochRSI1H > 80 → +1
- RSI顶背离 → +2

---

## 注意事项

1. **API密钥**：必须在config.py中配置
2. **余额建议**：≥$10 USDT
3. **推荐运行环境**：Linux + PM2
4. **网络要求**：稳定连接Binance API

---

## 相关文件

| 文件 | 用途 |
|------|------|
| `bot/bot_20x.py` | 主策略脚本 |
| `bot/config.py.template` | API配置模板 |
| `dashboard/` | Web控制台 |
| `docs/策略手册.md` | 详细策略文档 |