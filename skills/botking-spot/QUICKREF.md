# BotKing Spot - Quick Reference

## 启动/停止
```bash
pm2 start /root/.openclaw/workspace/bot_king.py --name bot-king
pm2 restart bot-king
pm2 logs bot-king --nostream --lines 15
```

## 核心参数
| 参数 | 值 |
|------|------|
| 网格利润 | 0.4%-1.0%（ATR自适应）|
| 网格止损 | -12% |
| 趋势TP1 | +15% → 卖50% |
| 趋势TP2 | +25% → 全卖 |
| 追踪止损 | 激活+6%，触发-3% |
| 最大持仓 | 3个币 |

## 7种市场模式
```
TREND_UP         → 趋势做多（ADX>25 + EMA三周期向上）
TREND_UP_RECALL → 回调买入（上升趋势中RSI<40）
RANGE_BOUND      → 网格套利（ADX<20）
VOL_OVERSOLD     → 超卖反弹（波幅>8% + RSI<35）
VOL_OVERBOUGHT   → 超买止盈（波幅>8% + RSI>65）
TREND_DOWN       → 做空/观望（ADX>25 + EMA向下）
CRISIS           → 全部暂停（日RSI>80或<20）
```

## 风控红线
```
余额<$11    → 禁止开仓
日亏>8%     → 暂停1小时
回撤>20%    → 全部止损+锁30分
连亏3次     → 熔断15分钟
22:00-02:00 → 禁止开仓
```

## 文件
```
主脚本:   /root/.openclaw/workspace/bot_king.py
状态:     /root/.openclaw/workspace/bot_king_state.json
日志:     /root/.openclaw/workspace/bot_king.log
配置:     /root/.openclaw/workspace/config_exchange.yaml
```
