#!/usr/bin/env python3
"""
SFTP 下載與比較系統 - 安裝設定腳本
"""
import os
import sys
import subprocess

def check_python_version():
    """檢查 Python 版本"""
    if sys.version_info < (3, 6):
        print("錯誤：需要 Python 3.6 或更高版本")
        sys.exit(1)
    print(f"✓ Python 版本: {sys.version.split()[0]}")

def install_requirements():
    """安裝必要的套件"""
    requirements = [
        'paramiko>=2.7.0',
        'pandas>=1.2.0',
        'openpyxl>=3.0.0',
        'lxml>=4.6.0'
    ]
    
    print("\n正在安裝必要套件...")
    for package in requirements:
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', package])
            print(f"✓ 已安裝 {package}")
        except subprocess.CalledProcessError:
            print(f"✗ 安裝 {package} 失敗")
            return False
    return True

def create_directories():
    """建立必要的目錄"""
    directories = [
        './downloads',
        './compare_results',
        './zip_output'
    ]
    
    print("\n建立目錄結構...")
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)
            print(f"✓ 建立目錄: {directory}")
        else:
            print(f"✓ 目錄已存在: {directory}")

def create_sample_excel():
    """建立範例 Excel 檔案"""
    try:
        import pandas as pd
        
        sample_data = {
            'SN': [1, 2, 3, 4, 5, 6],
            '模組': ['bootcode', 'emcu', 'dolby_ta', 'ufsd_ko', 'bootcode', 'Merlin7'],
            'ftp path': [
                '/DailyBuild/PrebuildFW/bootcode/RDDB-942_realtek_merlin8_premp.google-refplus/2025_06_24-18_16_9624861',
                '/DailyBuild/PrebuildFW/emcu/RDDB-1193_merlin8_android-14_premp.google-refplus/2025_06_24-17_41_e54f7a5',
                '/DailyBuild/PrebuildFW/dolby_ta/RDDB-932_mac7p_v3.0_common_android11_premp.google-refplus.upgrade-11.rtd2851a/2025_06_18-15_30_e05abe4',
                '/DailyBuild/PrebuildFW/ufsd_ko/RDDB-982_mac8q_android11_premp.google-refplus.upgrade-11/20250717_1455_618e9e1',
                '/DailyBuild/PrebuildFW/bootcode/RDDB-320_realtek_mac8q_premp.google-refplus/20250729_3333_4440eec',
                '/DailyBuild/Merlin7/DB2302_Merlin7_32Bit_FW_Android14_Ref_Plus_GoogleGMS/533_all_202507282300'
            ],
            '備註': ['主要版本', '測試版本', 'Wave backup 版本', 'Wave 版本', 'PreMP 版本', '特殊格式']
        }
        
        df = pd.DataFrame(sample_data)
        df.to_excel('sample_ftp_paths.xlsx', index=False)
        print("\n✓ 已建立範例 Excel 檔案: sample_ftp_paths.xlsx")
        return True
    except Exception as e:
        print(f"\n✗ 建立範例 Excel 檔案失敗: {str(e)}")
        return False

def update_config():
    """更新設定檔"""
    print("\n設定 SFTP 連線資訊...")
    print("（按 Enter 使用預設值）")
    
    host = input("SFTP 伺服器位址 [your.sftp.server.com]: ").strip()
    port = input("SFTP 連接埠 [22]: ").strip()
    username = input("使用者名稱 [your_username]: ").strip()
    password = input("密碼 [your_password]: ").strip()
    
    # 詢問 Gerrit URL
    print("\n設定 Gerrit URL（選填）")
    gerrit_prebuilt = input("Gerrit Prebuilt URL [保持預設]: ").strip()
    gerrit_normal = input("Gerrit Normal URL [保持預設]: ").strip()
    
    # 更新 config.py
    config_updates = []
    if host:
        config_updates.append(f"SFTP_HOST = '{host}'")
    if port:
        config_updates.append(f"SFTP_PORT = {port}")
    if username:
        config_updates.append(f"SFTP_USERNAME = '{username}'")
    if password:
        config_updates.append(f"SFTP_PASSWORD = '{password}'")
    if gerrit_prebuilt:
        config_updates.append(f"GERRIT_BASE_URL_PREBUILT = '{gerrit_prebuilt}'")
    if gerrit_normal:
        config_updates.append(f"GERRIT_BASE_URL_NORMAL = '{gerrit_normal}'")
    
    if config_updates:
        try:
            with open('config.py', 'r') as f:
                lines = f.readlines()
            
            # 更新設定
            for i, line in enumerate(lines):
                for update in config_updates:
                    key = update.split(' = ')[0]
                    if line.strip().startswith(key):
                        lines[i] = update + '\n'
            
            with open('config.py', 'w') as f:
                f.writelines(lines)
            
            print("✓ 設定檔已更新")
        except Exception as e:
            print(f"✗ 更新設定檔失敗: {str(e)}")

def test_system():
    """測試系統"""
    print("\n測試系統...")
    try:
        import main
        import sftp_downloader
        import file_comparator
        import zip_packager
        import excel_handler
        import utils
        print("✓ 所有模組載入成功")
        return True
    except ImportError as e:
        print(f"✗ 模組載入失敗: {str(e)}")
        return False

def main():
    """主程式"""
    print("=== SFTP 下載與比較系統 - 安裝設定 ===\n")
    
    # 檢查 Python 版本
    check_python_version()
    
    # 安裝套件
    if not install_requirements():
        print("\n安裝失敗！請檢查錯誤訊息。")
        sys.exit(1)
    
    # 建立目錄
    create_directories()
    
    # 建立範例檔案
    create_sample_excel()
    
    # 更新設定
    update_config()
    
    # 測試系統
    if test_system():
        print("\n=== 安裝完成 ===")
        print("\n快速開始：")
        print("1. 互動式模式: python main.py")
        print("2. 查看說明: python main.py -h")
        print("3. 測試連線: python main.py（選擇選項 4）")
        print("4. 使用範例 Excel: python main.py download --excel sample_ftp_paths.xlsx")
    else:
        print("\n安裝完成但測試失敗，請檢查所有檔案是否正確。")

if __name__ == '__main__':
    main()