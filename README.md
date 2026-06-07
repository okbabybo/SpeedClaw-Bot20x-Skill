# speedClaw Bot20x

> A Binance USDT-M永续合约量化交易机器人
> 20x杠杆 · 多周期EMA确认 · StochRSI信号 · 趋势反转预警

**策略评分：87/100** | v5.2 | Python 3

---

## 订阅授权

本项目采用**订阅授权模式**，需要授权码才能运行。

### 套餐价格

| 套餐 | 价格 | 说明 |
|------|------|------|
| 月度 | $9.9/月 | 30天有效 |
| 季度 | $24.9/季 | 90天有效 |
| 年度 | $79.9/年 | 365天有效 |

### 付款方式

**USDT (BEP20 - BNB Smart Chain)**：
```
0xFb4f3eFA1FeB256131FEEf2E2Ca4B2F2e9b22d6E
```

付款后联系管理员获取授权码。

### 获取授权码

1. 完成付款后联系管理员
2. 管理员生成授权码并发送
3. 将授权码保存到 `.license` 文件：
   ```bash
   cp license.template .license
   echo '你的授权码' > .license
   ```

### 授权管理（管理员）

```bash
# 生成授权码
python license_manager.py generate user@example.com monthly

# 查看授权码
python license_manager.py list

# 撤销授权码
python license_manager.py revoke SCB-XXXXXXXXXXXXXXXX
```

---

## 快速开始

### 1. 安装依赖

```bash
pip install requests
```

### 2.配置文件

```bash
cd bot
cp config.py.template config.py
# 编辑config.py，填入币安API密钥
```

### 3. 配置授权码

```bash
cp license.template .license
echo 'YOUR_LICENSE_KEY' > .license
```

### 4. 启动

```bash
# 直接运行
python bot_20x.py

# PM2守护模式
pm2 start bot_20x.py --name bot20x
pm2 logs bot20x
```

---

## 策略核心

### 信号系统

| 信号 | 条件 | 触发 |
|------|------|------|
| 做多 | RSI/StochRSI超卖 + 趋势向上 | 评分≥6.5 |
| 做空 | RSI/StochRSI超买 + 趋势向下 | 评分≥6.5 |
| 逆势 | 价格偏离EMA +极端RSI | 评分≥6.5 |

### 风控

- 固定2%止损
- 总仓位按保证金计算（≤150%余额）
- 回撤≥15%自动减半仓
- 连亏3次熔断15分钟

### 止盈

- TP1：浮盈≥2%出半场
- TP2：浮盈≥4%回撤0.8%出清

---

## 文件结构

```
speedClaw-Bot20x-Skill/
├── bot/
│   ├── bot_20x.py           # 主策略脚本（需授权）
│   ├── config.py.template    # API配置模板
│   ├── license.template      # 授权码模板
│   └── license_manager.py # 授权管理工具
├── dashboard/
│   ├── bot_dashboard_api.py   # Web控制台后端
│   └── dashboard.html         # Web控制台前端
├── docs/
│   └── 策略手册.md           # 详细策略文档
├── skill/
│   └── SKILL.md              # OpenClaw Skill
├── LICENSE
├── README.md
├── requirements.txt
└── setup.sh
```

---

## Web控制台

访问 `dashboard.html` 或启动API服务：

```bash
python dashboard/bot_dashboard_api.py
# 访问 http://localhost:5000
```

功能：查看持仓、信号评分、手动平仓、重启Bot

---

## 版本历史

| 版本 | 日期 | 改动 |
|------|------|------|
| v5.2 | 2026-06-07 | 新增订阅授权系统 + 趋势反转预警 |
| v5.1 | 2026-06-07 | 总仓位按保证金计算 |
| v5.0 | 2026-06-06 | ADX + ATR + 连赢加速 + 逆势模式 |

---

## 免责声明

本项目仅供学习和研究使用。实盘交易存在风险，请确保：

1. 充分理解策略逻辑和风险
2. 使用小资金实盘测试
3. 持续监控策略运行状态
4. 自行承担交易盈亏

**作者不对任何交易损失负责。**

---

## License

MIT License