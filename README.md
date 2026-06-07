# speedClaw Bot20x

> Binance USDT-M永续合约量化交易机器人
> 20x杠杆 · 多周期EMA确认 · StochRSI信号 · 趋势反转预警

**策略评分：87/100** | v5.2 | Python 3

---

## 📦 购买方式

### 套餐价格

| 套餐 | 价格 | 收款地址（USDT BEP20） |
|------|------|----------------------|
| 月度 | $9.9 | `0xFb4f3eFA1FeB256131FEEf2E2Ca4B2F2e9b22d6E` |
| 季度 | $24.9 | `0x6CDD7d0e7865f6DaDB9178dd114890ABD5d5323b` |
| 年度 | $79.9 | `0x352f5Cb1CA167500D27741676ab9efA4B07D3D30` |

### 使用流程

```
1. 向套餐地址转账USDT
2. 联系 Telegram @Okbabybo 或 邮箱 570511887@qq.com
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
| Telegram | @Okbabybo |
| Email | 570511887@qq.com |

---

## 快速开始

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

## 文件结构

```
speedClaw-Bot20x-Skill/
├── bot/
│   ├── bot_20x.py           # 主策略脚本
│   ├── config.py.template   # API配置模板
│   └── license_manager.py   # 授权管理工具
├── dashboard/
│   ├── bot_dashboard_api.py  # Web控制台后端
│   └── dashboard.html        # Web控制台前端
├── docs/
│   └── index.html            # 下载页面
├── skill/
│   └── SKILL.md             # OpenClaw Skill
└── README.md
```

---

## 版本历史

| 版本 | 日期 | 改动 |
|------|------|------|
| v5.2 | 2026-06-07 | 趋势冲突过滤 + 趋势反转预警 |
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