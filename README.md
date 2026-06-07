# speedClaw Bot20x

> Binance USDT-M永续合约量化交易机器人
> 20x杠杆 · 多周期EMA确认 · StochRSI信号 · 趋势反转预警

**策略评分：87/100** | v5.2 | Python 3

---

## 订阅授权

本项目采用**固定地址订阅模式**，直接向套餐对应地址转账即可。

### 套餐价格

| 套餐 | 价格 | 收款地址 |
|------|------|----------|
| 月度 | $9.9 | `0xFb4f3eFA1FeB256131FEEf2E2Ca4B2F2e9b22d6E` |
| 季度 | $24.9 | `0x6CDD7d0e7865f6DaDB9178dd114890ABD5d5323b` |
| 年度 | $79.9 | `0x352f5Cb1CA167500D27741676ab9efA4B07D3D30` |

### 使用步骤

```
1. 向对应套餐地址转账USDT（BEP20）
2. 复制转账TX哈希
3. 打开自动发货页面：http://43.129.181.252:80
4. 选择套餐 + 粘贴TX哈希 → 点击验证
5. 自动显示授权码 ✅
```

---

##联系方式

📬 有问题请联系：
- Telegram: @Okbabybo
- Email: 570511887@qq.com

---

## 快速开始

```bash
# 克隆仓库
git clone https://github.com/okbabybo/SpeedClaw-Bot20x-Skill.git
cd SpeedClaw-Bot20x-Skill/bot

# 配置
cp config.py.template config.py
cp license.template .license
# 编辑config.py填入API密钥

# 启动
pm2 start bot_20x.py --name bot20x
```

---

## 文件结构

```
speedClaw-Bot20x-Skill/
├── bot/
│   ├── bot_20x.py           # 主策略脚本（需授权）
│   ├── config.py.template    # API配置模板
│   ├── license.template      # 授权码模板
│   └── license_manager.py   # 授权管理工具
├── payment/
│   └── payment_server.py    # 自动发货系统
├── dashboard/
│   ├── bot_dashboard_api.py  # Web控制台后端
│   └── dashboard.html         # Web控制台前端
├── docs/
│   └── 策略手册.md # 详细策略文档
├── skill/
│   └── SKILL.md              # OpenClaw Skill
└── README.md
```

---

## 版本历史

| 版本 | 日期 | 改动 |
|------|------|------|
| v5.2 | 2026-06-07 | 固定地址订阅系统 + 趋势反转预警 |
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