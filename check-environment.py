#!/usr/bin/env python3
"""
環境檢查腳本
執行: python check_environment.py
"""
import os
import sys
import subprocess

def check_environment():
    print("=== 環境檢查 ===\n")
    
    # 1. Python 版本
    print(f"1. Python 版本: {sys.version}")
    print(f"   Python 執行檔: {sys.executable}\n")
    
    # 2. 工作目錄
    print(f"2. 當前工作目錄: {os.getcwd()}")
    print(f"   腳本位置: {os.path.abspath(__file__)}\n")
    
    # 3. 檢查 cli_interface.py
    print("3. 檢查 CLI 腳本:")
    possible_paths = [
        'cli_interface.py',
        'vp_lib/cli_interface.py',
        '../vp_lib/cli_interface.py',
        './vp_lib/cli_interface.py'
    ]
    
    cli_found = False
    for path in possible_paths:
        exists = os.path.exists(path)
        print(f"   {path}: {'存在' if exists else '不存在'}")
        if exists:
            cli_found = True
            print(f"      絕對路徑: {os.path.abspath(path)}")
    
    if not cli_found:
        print("   ⚠️  找不到 cli_interface.py！")
    print()
    
    # 4. 檢查輸出目錄
    print("4. 檢查輸出目錄:")
    output_dirs = ['./output', './output/chip_mapping', './output/prebuild_mapping', './downloads']
    for dir_path in output_dirs:
        exists = os.path.exists(dir_path)
        writable = os.access(dir_path, os.W_OK) if exists else False
        print(f"   {dir_path}: {'存在' if exists else '不存在'} {'(可寫)' if writable else '(不可寫)' if exists else ''}")
    print()
    
    # 5. 檢查必要的 Python 套件
    print("5. 檢查 Python 套件:")
    packages = ['pandas', 'flask', 'openpyxl']
    for package in packages:
        try:
            __import__(package)
            print(f"   {package}: ✓ 已安裝")
        except ImportError:
            print(f"   {package}: ✗ 未安裝")
    print()
    
    # 6. 檢查 vp_lib 目錄結構
    print("6. 檢查 vp_lib 目錄:")
    if os.path.exists('vp_lib'):
        print("   vp_lib 目錄存在")
        for item in os.listdir('vp_lib'):
            print(f"      - {item}")
    else:
        print("   ⚠️  vp_lib 目錄不存在！")
    print()
    
    # 7. 測試執行命令
    print("7. 測試執行命令:")
    test_commands = [
        ['python', '--version'],
        ['python3', '--version']
    ]
    
    for cmd in test_commands:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            output = result.stdout.strip() or result.stderr.strip()
            print(f"   {' '.join(cmd)}: {output}")
        except Exception as e:
            print(f"   {' '.join(cmd)}: 執行失敗 - {str(e)}")

if __name__ == '__main__':
    check_environment()