import os
import json

def diagnose_directory_structure(task_id):
    """診斷目錄結構，找出為什麼 PreMP vs Wave 沒有資料"""
    
    download_dir = os.path.join('downloads', task_id)
    
    if not os.path.exists(download_dir):
        print(f"找不到目錄: {download_dir}")
        return
    
    print(f"\n=== 診斷目錄結構: {download_dir} ===\n")
    
    # 收集所有模組位置
    module_locations = {}
    
    for root, dirs, files in os.walk(download_dir):
        # 顯示當前路徑
        rel_path = os.path.relpath(root, download_dir)
        print(f"掃描: {rel_path}")
        
        # 判斷版本類型
        version_type = None
        if 'master' in root.lower():
            version_type = 'master'
        elif 'premp' in root.lower() or 'pre-mp' in root.lower():
            version_type = 'premp'
        elif 'wave' in root.lower() and 'backup' not in root.lower():
            version_type = 'wave'
        elif 'backup' in root.lower():
            version_type = 'backup'
        
        # 如果找到關鍵檔案
        for file in files:
            if file in ['manifest.xml', 'F_Version.txt', 'Version.txt']:
                print(f"  找到: {file} (版本類型: {version_type})")
                
                # 提取模組名稱
                path_parts = root.split(os.sep)
                module_name = None
                
                # 從路徑中找模組名稱（通常是最後一個非版本標識的目錄）
                for part in reversed(path_parts):
                    if part and part not in ['master', 'premp', 'wave', 'backup', 'downloads', task_id]:
                        module_name = part
                        break
                
                if module_name:
                    if module_name not in module_locations:
                        module_locations[module_name] = {}
                    module_locations[module_name][version_type or 'unknown'] = root
                    print(f"  模組: {module_name}, 版本: {version_type}")
    
    print(f"\n=== 模組位置摘要 ===")
    print(json.dumps(module_locations, indent=2, ensure_ascii=False))
    
    # 分析哪些模組有 PreMP 和 Wave
    print(f"\n=== PreMP vs Wave 可比對的模組 ===")
    premp_wave_modules = []
    for module_name, locations in module_locations.items():
        if 'premp' in locations and 'wave' in locations:
            premp_wave_modules.append(module_name)
            print(f"✓ {module_name}")
            print(f"  PreMP: {locations['premp']}")
            print(f"  Wave:  {locations['wave']}")
    
    if not premp_wave_modules:
        print("❌ 沒有找到同時有 PreMP 和 Wave 的模組！")
        print("\n可能的原因：")
        print("1. 目錄結構不符合預期")
        print("2. 版本標識（premp/wave）在路徑中的位置不正確")
        print("3. 檔案下載不完整")
    
    return module_locations

if __name__ == "__main__":
    task_id = input("請輸入 task_id: ").strip()
    if task_id:
        diagnose_directory_structure(task_id)