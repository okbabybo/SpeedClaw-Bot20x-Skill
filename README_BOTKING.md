# 🦞 SpeedClaw BotKing v1.4.3 - 现货量化机器人

> **现货网格 + 趋势双引擎** · 综合评分 **9.2/10** · 50k蒙特卡洛精算
> 
> 一键安装 · 零配置启动 · 全自动PM2守护

---

## ✨ 产品亮点

- ✅ **零配置启动** - 输入API即用，无需编程
- ✅ **7种市场模式** - 自动识别趋势/震荡/超买超卖
- ✅ **双引擎架构** - 网格套利 + 趋势追踪
- ✅ **9层风控矩阵** - 余额/日亏/回撤/熔断全套保护
- ✅ **复利滚仓** - Phase2用锁定利润二次开仓
- ✅ **状态持久化** - 重启自动恢复仓位
- ✅ **Web控制台** - 实时监控+手动控制
- ✅ **Docker支持** - 跨平台一键部署

---

## 🚀 快速开始（3种方式）

### 方式1：一键安装脚本（推荐Linux/Mac）

```bash
curl -sSL https://raw.githubusercontent.com/okbabybo/SpeedClaw-Bot20x-Skill/main/setup_king.sh | bash
```

或手动：
```bash
git clone https://github.com/okbabybo/SpeedClaw-Bot20x-Skill.git
cd SpeedClaw-Bot20x-Skill
bash setup_king.sh
```

### 方式2：交互式初始化（推荐新手）

```bash
python3 bot/botking_init.py
```

按提示输入：
1. 币安API Key / Secret
2. 选择交易币种（2/6/7种）
3. 自动生成配置 + 启动

### 方式3：Docker（跨平台）

```bash
# 1. 配置API
cp bot/config_exchange.yaml.template bot/config_exchange.yaml
nano bot/config_exchange.yaml  # 填入API

# 2. 启动
docker-compose up -d

# 3. 查看日志
docker logs -f speedclaw-botking
```

---

## 📊 策略机制（5大模块）

| 模块 | 说明 |
|------|------|
| 7种市场模式 | TREND_UP / RECALL / RANGE / VOL_OVERSOLD / VOL_OVERBOUGHT / TREND_DOWN / CRISIS |
| 网格引擎 | Phase1本金 + Phase2利润复利, ATR自适应格数 |
| 趋势引擎 | TP1+TP2分批止盈 + TS追踪止损 + 12%硬止损 |
| 风控矩阵 | 9层保护 (余额/日亏/回撤/熔断/熊市锁定...) |
| 资金管理 | TIER分级 + 置信度系数 + 关联性敞口检查 |

---

## 📋 详细文档

- **完整策略手册**: `BOTKING_V1.3_STRATEGY.md` 或 [在线版](https://okbabybo.github.io/SpeedClaw-Bot20x-Skill/)
- **快速参考**: `skills/botking-spot/QUICKREF.md`
- **API配置**: `bot/config_exchange.yaml.template`

---

## ⚙️ 配置说明

### 最小配置（bot/config_exchange.yaml）

```yaml
exchanges:
  - name: binance
    api_key: "你的API_KEY"
    secret: "你的SECRET"

coins:
  - BTCUSDT
  - ETHUSDT
```

### 推荐API权限

在币安API管理页面创建API时，**仅勾选**:
- ✅ 启用现货及杠杆交易
- ✅ 启用读取

**不要勾选**:
- ❌ 启用提币（安全风险）

---

## 🎮 常用命令

### PM2管理
```bash
pm2 list | grep king       # 查看状态
pm2 logs bot-king --nostream --lines 20   # 查看日志
pm2 restart bot-king       # 重启
pm2 stop bot-king          # 停止
pm2 delete bot-king        # 删除
pm2 save                   # 保存进程列表（重启后自动恢复）
```

### Web控制台
```bash
python3 dashboard/bot_dashboard_api.py
```
访问 `http://localhost:5000`

### 日志位置
```
/root/.openclaw/workspace/bot_king.log
/root/.openclaw/workspace/bot_king_state.json
```

---

## 🛡️ 风险管理

| 保护层 | 触发条件 | 动作 |
|--------|---------|------|
| 1 | 余额 < $11 | 禁开仓 |
| 2 | 日亏 > 8% | 暂停1小时 |
| 3 | 回撤 > 20% | 清仓+锁30分 |
| 4-5 | 连亏1-2次 | 冷静5-10分 |
| 6 | 连亏3次 | 熔断15分 |
| 7 | 3连亏+熊市 | 暂停至反转 |
| 8 | 日线RSI极端 | 全平+锁30分 |
| 9 | API连50次失败 | 熔断120秒 |

---

## 📈 50k蒙特卡洛精算

| 指标 | 数值 |
|------|------|
| 平均EV/周期 | **+0.9%** |
| 正周期率 | **86.7%** |
| P5 (最差5%) | -1.46% |
| 实盘年化折现 | 25-60% |

---

## 🐛 故障排查

### Bot未启动
```bash
pm2 logs bot-king --nostream --lines 30
# 常见: API密钥错误 / 网络问题 / 余额不足
```

### API 401错误
- 检查 `bot/config_exchange.yaml` 密钥是否正确
- 确认API已开启"现货交易"权限

### Bot频繁重启
```bash
pm2 logs bot-king --nostream --lines 50 | grep -i error
# 可能是网络问题, 等待API熔断恢复(120秒)
```

---

## 💼 订阅信息

| 套餐 | 价格 | 包含 |
|------|------|------|
| BotKing 现货版 | **$399.9 USDT/年** | 全部源码 + 1年更新 + 技术支持 |
| BotKing 终身版 | $999 USDT | 终身使用 + 终身更新 |

**订阅地址**: https://okbabybo.github.io/SpeedClaw-Bot20x-Skill/
**联系方式**: Telegram @Okbabybo

---

## 📜 License

MIT License - 详见 [LICENSE](LICENSE)

---

> 🦞 **混沌龙虾** - 让量化交易触手可及
> 
> 最后更新: 2026-06-25 · BotKing v1.4.3 · commit `3bffd85`