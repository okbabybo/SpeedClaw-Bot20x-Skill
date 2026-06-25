#!/usr/bin/env python3
"""
BotKing 初始化向导
==================
交互式配置 BotKing 现货机器人
- 输入API密钥
- 选择交易币种
- 设置风险参数
- 自动启动PM2

用法: python3 botking_init.py
"""
import os
import sys
import subprocess
import getpass
from pathlib import Path

CONFIG_FILE = Path(__file__).parent / "config_exchange.yaml"
TEMPLATE_FILE = Path(__file__).parent / "config_exchange.yaml.template"
SETUP_SCRIPT = Path(__file__).parent / "setup_king.sh"


def print_banner():
    print("""
╔════════════════════════════════════════════════════════╗
║                                                        ║
║       🦞  SpeedClaw BotKing v1.4.3 现货机器人          ║
║                                                        ║
║            现货网格 + 趋势双引擎量化                    ║
║            评分 9.2/10 | GitHub: okbabybo              ║
║                                                        ║
╚════════════════════════════════════════════════════════╝
    """)


def check_python():
    if sys.version_info < (3, 8):
        print("❌ 需要 Python 3.8+")
        sys.exit(1)
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor}")


def install_deps():
    print("\n📦 安装依赖...")
    deps = ["requests", "pyyaml", "python-docx"]
    for d in deps:
        try:
            __import__(d.replace("-", "_"))
            print(f"  ✅ {d}")
        except ImportError:
            print(f"  📥 安装 {d}...")
            subprocess.run([sys.executable, "-m", "pip", "install", "-q", d], check=True)
            print(f"  ✅ {d}")


def get_api_keys():
    print("\n🔑 配置币安API密钥")
    print("  (推荐: 仅勾选'启用现货交易'+'启用读取', 不要勾选提币权限)")
    print()
    api_key = input("  API Key: ").strip()
    secret = getpass.getpass("  Secret: ").strip()
    if not api_key or not secret:
        print("❌ API密钥不能为空")
        sys.exit(1)
    return api_key, secret


def choose_coins():
    print("\n💰 选择交易币种 (多选用逗号分隔, 直接回车用默认):")
    print("  [1] BTC ETH (推荐新手, 2币种)")
    print("  [2] BTC ETH BNB SOL AVAX XRP (6币种)")
    print("  [3] BTC ETH BNB SOL AVAX XRP TON (7币种, 含TON)")
    choice = input("  选择 [1/2/3]: ").strip() or "1"
    coins_map = {
        "1": ["BTCUSDT", "ETHUSDT"],
        "2": ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "AVAXUSDT", "XRPUSDT"],
        "3": ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "AVAXUSDT", "XRPUSDT", "TONUSDT"],
    }
    return coins_map.get(choice, coins_map["1"])


def create_config(api_key, secret, coins):
    """生成 config_exchange.yaml"""
    content = f"""# BotKing v1.4.3 配置文件
# 由 botking_init.py 自动生成
# 生成时间: 自动

exchanges:
  - name: binance
    api_key: "{api_key}"
    secret: "{secret}"

# 交易币种
coins: {coins}

# 日志和状态文件
log_file: /root/.openclaw/workspace/bot_king.log
state_dir: /root/.openclaw/workspace/
state_file: bot_king_state.json

# 启动选项
auto_start: true
log_level: INFO
"""
    CONFIG_FILE.write_text(content)
    CONFIG_FILE.chmod(0o600)  # 仅root可读
    print(f"  ✅ 配置文件: {CONFIG_FILE}")


def start_pm2():
    """用PM2启动BotKing"""
    bot_dir = Path(__file__).parent
    bot_script = bot_dir.parent / "bot_king.py"

    if not bot_script.exists():
        print(f"❌ 未找到 {bot_script}")
        sys.exit(1)

    print(f"\n🚀 启动BotKing (PM2)...")
    try:
        # 停止旧实例
        subprocess.run(["pm2", "delete", "bot-king"],
                      capture_output=True, text=True)
        # 启动新实例
        result = subprocess.run(
            ["pm2", "start", str(bot_script), "--name", "bot-king",
             "--interpreter", "python3"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            subprocess.run(["pm2", "save"], capture_output=True)
            print("  ✅ BotKing已启动")
            print("\n  查看状态: pm2 list | grep bot-king")
            print("  查看日志: pm2 logs bot-king --nostream --lines 20")
            print("  停止:     pm2 stop bot-king")
        else:
            print(f"  ⚠️ PM2启动失败: {result.stderr}")
    except FileNotFoundError:
        print("  ⚠️ 未安装PM2, 请手动启动: python3 bot_king.py")


def main():
    print_banner()
    print("🚀 BotKing 初始化向导\n")
    check_python()
    install_deps()
    api_key, secret = get_api_keys()
    coins = choose_coins()
    create_config(api_key, secret, coins)
    print("\n" + "="*60)
    print("✅ 配置完成!")
    print("="*60)
    start_choice = input("\n立即启动BotKing? [Y/n]: ").strip().lower() or "y"
    if start_choice == "y":
        start_pm2()
    print("\n🦞 完成! 祝你交易顺利!")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ 已取消")
        sys.exit(0)