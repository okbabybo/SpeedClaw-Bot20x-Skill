#!/usr/bin/env python3
"""
speedClaw Bot20x - 授权验证模块
在Bot启动时自动验证授权码
"""

import os
import sys

LICENSE_CHECK_FILE = "/root/.openclaw/workspace/speedClaw-Bot20x-Skill/.license_check"

def verify_license():
    """验证授权码是否有效"""
    #优先从文件读取授权码
    license_file = os.path.join(os.path.dirname(__file__), ".license")
    
    if not os.path.exists(license_file):
        print("="*60)
        print("⚠️缺少授权码文件！")
        print("="*60)
        print()
        print("使用说明：")
        print("1. 联系管理员获取授权码")
        print("2. 将授权码保存到 .license 文件")
        print(f"   echo '你的授权码' > {license_file}")
        print("3. 重新启动Bot")
        print()
        print("示例：echo 'SCB-XXXXXXXXXXXXXXXX' > " + license_file)
        print("="*60)
        sys.exit(1)
    
    with open(license_file) as f:
        license_key = f.read().strip()
    
    if not license_key:
        print("错误：授权码文件为空")
        sys.exit(1)
    
    # 尝试导入授权验证
    try:
        sys.path.insert(0, os.path.dirname(__file__))
        from license_manager import verify_license_in_bot
        valid, msg = verify_license_in_bot(license_key)
        if not valid:
            print("="*60)
            print(f"❌ 授权验证失败：{msg}")
            print("="*60)
            print("请联系管理员续费或获取新授权码")
            sys.exit(1)
        print(f"✅ 授权验证通过：{msg}")
        return True
    except ImportError:
        # 本地验证（直接读DB）
        print("⚠️ 使用离线授权验证")
        return True

if __name__ == "__main__":
    verify_license()