#!/usr/bin/env python3
"""
快速測試 Master to PreMP 轉換規則
可以獨立執行或整合到現有系統中
"""
import os
import sys
import utils

# 加入上一層目錄到路徑
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# 載入設定
try:
    import config
    utils.setup_config()  # 設定環境變數
except ImportError:
    print("警告：無法載入 config 模組，使用預設設定")
    config = None

def quick_test_manifest_conversion(master_file=None, premp_file=None, output_file=None):
    """
    快速測試 manifest 轉換規則
    
    Args:
        master_file: master manifest 檔案路徑（可選，使用對話框選擇）
        premp_file: premp manifest 檔案路徑（可選，使用對話框選擇）
        output_file: 輸出 Excel 檔案路徑（可選，自動生成）
    
    Returns:
        測試是否成功
    """
    import os
    import sys
    from datetime import datetime
    
    # 添加必要的路徑
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    
    try:
        # 如果沒有提供檔案路徑，使用檔案選擇對話框
        if not master_file or not premp_file:
            try:
                from tkinter import filedialog, Tk
                
                # 隱藏主視窗
                root = Tk()
                root.withdraw()
                
                if not master_file:
                    print("請選擇 Master manifest.xml 檔案...")
                    master_file = filedialog.askopenfilename(
                        title="選擇 Master Manifest",
                        filetypes=[("XML files", "*.xml"), ("All files", "*.*")]
                    )
                    if not master_file:
                        print("❌ 未選擇 Master manifest 檔案")
                        return False
                
                if not premp_file:
                    print("請選擇 PreMP manifest.xml 檔案（正確版）...")
                    premp_file = filedialog.askopenfilename(
                        title="選擇 PreMP Manifest（正確版）",
                        filetypes=[("XML files", "*.xml"), ("All files", "*.*")]
                    )
                    if not premp_file:
                        print("❌ 未選擇 PreMP manifest 檔案")
                        return False
                        
            except ImportError:
                # 如果沒有 tkinter，要求輸入路徑
                if not master_file:
                    master_file = input("請輸入 Master manifest.xml 檔案路徑: ").strip()
                if not premp_file:
                    premp_file = input("請輸入 PreMP manifest.xml 檔案路徑（正確版）: ").strip()
        
        # 檢查檔案是否存在
        if not os.path.exists(master_file):
            print(f"❌ Master 檔案不存在: {master_file}")
            return False
        
        if not os.path.exists(premp_file):
            print(f"❌ PreMP 檔案不存在: {premp_file}")
            return False
        
        # 生成輸出檔名
        if not output_file:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f'conversion_test_{timestamp}.xlsx'
        
        print("\n" + "="*60)
        print("🚀 開始測試 Master to PreMP 轉換規則")
        print("="*60)
        print(f"📄 Master 檔案: {os.path.basename(master_file)}")
        print(f"📄 PreMP 檔案: {os.path.basename(premp_file)}")
        print(f"📊 輸出報告: {output_file}")
        print("="*60 + "\n")
        
        # 匯入測試模組
        from test_manifest_conversion import ManifestConversionTester
        
        # 執行測試
        tester = ManifestConversionTester()
        success = tester.test_conversion(master_file, premp_file, output_file)
        
        # 顯示結果
        print("\n" + "="*60)
        if success:
            print("✅ 測試完成 - 所有轉換規則正確！")
        else:
            print("⚠️ 測試完成 - 發現轉換差異")
        print(f"📊 詳細報告已儲存至: {output_file}")
        print("="*60)
        
        # 詢問是否開啟報告
        try:
            response = input("\n是否要開啟測試報告？(Y/N): ").strip().upper()
            if response == 'Y':
                import subprocess
                import platform
                
                if platform.system() == 'Windows':
                    os.startfile(output_file)
                elif platform.system() == 'Darwin':  # macOS
                    subprocess.call(['open', output_file])
                else:  # Linux
                    subprocess.call(['xdg-open', output_file])
        except:
            pass
        
        return success
        
    except Exception as e:
        print(f"❌ 測試失敗: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def integrate_with_main_menu():
    """
    整合到主選單的範例函數
    可以添加到 main.py 中
    """
    print("\n" + "="*60)
    print("📋 Master to PreMP 轉換規則測試")
    print("="*60)
    print("此功能將測試 Master to PreMP 的轉換規則是否正確")
    print("需要提供：")
    print("  1. Master manifest.xml 檔案")
    print("  2. PreMP manifest.xml 檔案（正確版）")
    print("="*60)
    
    # 詢問檔案來源
    print("\n請選擇檔案來源：")
    print("1. 使用本地檔案")
    print("2. 從 Gerrit 下載（需要網路）")
    print("3. 使用範例檔案（如果有）")
    
    choice = input("\n請選擇 (1-3): ").strip()
    
    master_file = None
    premp_file = None
    
    if choice == '1':
        # 使用本地檔案
        return quick_test_manifest_conversion()
        
    elif choice == '2':
        # 從 Gerrit 下載
        print("\n從 Gerrit 下載 manifest 檔案...")
        
        # 這裡可以整合 gerrit_manager 來下載檔案
        try:
            from gerrit_manager import GerritManager
            import tempfile
            import os
            
            gerrit = GerritManager()
            
            # 下載 master manifest
            master_url = input("請輸入 Master manifest 的 Gerrit URL: ").strip()
            if not master_url:
                master_url = "https://mm2sd.rtkbf.com/gerrit/plugins/gitiles/realtek/android/manifest/+/refs/heads/realtek/android-14/master/atv-google-refplus.xml"
                print(f"使用預設 URL: {master_url}")
            
            temp_dir = tempfile.mkdtemp()
            master_file = os.path.join(temp_dir, "master_manifest.xml")
            
            if gerrit.download_file_from_link(master_url, master_file):
                print(f"✅ 成功下載 Master manifest")
            else:
                print(f"❌ 下載 Master manifest 失敗")
                return False
            
            # 下載 premp manifest
            premp_url = input("請輸入 PreMP manifest 的 Gerrit URL: ").strip()
            if not premp_url:
                premp_url = "https://mm2sd.rtkbf.com/gerrit/plugins/gitiles/realtek/android/manifest/+/refs/heads/realtek/android-14/master/atv-google-refplus-premp.xml"
                print(f"使用預設 URL: {premp_url}")
            
            premp_file = os.path.join(temp_dir, "premp_manifest.xml")
            
            if gerrit.download_file_from_link(premp_url, premp_file):
                print(f"✅ 成功下載 PreMP manifest")
            else:
                print(f"❌ 下載 PreMP manifest 失敗")
                return False
            
            # 執行測試
            return quick_test_manifest_conversion(master_file, premp_file)
            
        except ImportError:
            print("❌ 無法匯入 GerritManager，請使用本地檔案")
            return quick_test_manifest_conversion()
            
    elif choice == '3':
        # 使用範例檔案
        print("\n檢查範例檔案...")
        
        sample_master = "./samples/master_manifest.xml"
        sample_premp = "./samples/premp_manifest.xml"
        
        if os.path.exists(sample_master) and os.path.exists(sample_premp):
            print("✅ 找到範例檔案")
            return quick_test_manifest_conversion(sample_master, sample_premp)
        else:
            print("❌ 範例檔案不存在，請使用其他選項")
            return False
    
    else:
        print("❌ 無效的選擇")
        return False


def batch_test_multiple_manifests(test_pairs):
    """
    批次測試多組 manifest 檔案
    
    Args:
        test_pairs: 測試對列表，格式為 [(master1, premp1), (master2, premp2), ...]
    
    Returns:
        測試結果摘要
    """
    from datetime import datetime
    import os
    
    print("\n" + "="*60)
    print("🔄 批次測試 Master to PreMP 轉換規則")
    print(f"📋 共 {len(test_pairs)} 組測試")
    print("="*60)
    
    results = []
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    for i, (master_file, premp_file) in enumerate(test_pairs, 1):
        print(f"\n測試 {i}/{len(test_pairs)}:")
        print(f"  Master: {os.path.basename(master_file)}")
        print(f"  PreMP: {os.path.basename(premp_file)}")
        
        # 生成輸出檔名
        output_file = f'test_{i}_{timestamp}.xlsx'
        
        # 執行測試
        try:
            from test_manifest_conversion import ManifestConversionTester
            tester = ManifestConversionTester()
            success = tester.test_conversion(master_file, premp_file, output_file)
            
            results.append({
                'index': i,
                'master': master_file,
                'premp': premp_file,
                'output': output_file,
                'success': success,
                'stats': tester.stats
            })
            
            if success:
                print(f"  ✅ 測試通過")
            else:
                print(f"  ❌ 發現差異")
                
        except Exception as e:
            print(f"  ❌ 測試失敗: {str(e)}")
            results.append({
                'index': i,
                'master': master_file,
                'premp': premp_file,
                'output': None,
                'success': False,
                'error': str(e)
            })
    
    # 顯示總結
    print("\n" + "="*60)
    print("📊 批次測試結果總結")
    print("="*60)
    
    passed = sum(1 for r in results if r['success'])
    failed = len(results) - passed
    
    print(f"總測試數: {len(results)}")
    print(f"✅ 通過: {passed}")
    print(f"❌ 失敗: {failed}")
    print(f"成功率: {(passed/len(results)*100):.1f}%")
    
    # 顯示詳細結果
    print("\n詳細結果:")
    for result in results:
        status = "✅" if result['success'] else "❌"
        print(f"{status} 測試 {result['index']}: {os.path.basename(result['master'])}")
        if 'stats' in result:
            stats = result['stats']
            print(f"   匹配: {stats['matched']}/{stats['total_projects']}")
        if 'error' in result:
            print(f"   錯誤: {result['error']}")
    
    return results


# 主程式進入點
if __name__ == "__main__":
    import sys
    
    # 檢查命令列參數
    if len(sys.argv) > 1:
        # 如果提供了參數，使用命令列模式
        if len(sys.argv) >= 3:
            master_file = sys.argv[1]
            premp_file = sys.argv[2]
            output_file = sys.argv[3] if len(sys.argv) > 3 else None
            
            success = quick_test_manifest_conversion(master_file, premp_file, output_file)
            sys.exit(0 if success else 1)
        else:
            print("用法: python quick_test.py <master.xml> <premp.xml> [output.xlsx]")
            sys.exit(1)
    else:
        # 互動模式
        print("\n🎯 Master to PreMP 轉換規則測試工具")
        print("="*60)
        print("選擇測試模式：")
        print("1. 單一測試（互動式）")
        print("2. 整合選單測試")
        print("3. 批次測試（多組檔案）")
        print("4. 結束")
        
        choice = input("\n請選擇 (1-4): ").strip()
        
        if choice == '1':
            quick_test_manifest_conversion()
        elif choice == '2':
            integrate_with_main_menu()
        elif choice == '3':
            # 範例批次測試
            test_pairs = [
                # 在這裡添加要測試的檔案對
                # ('master1.xml', 'premp1.xml'),
                # ('master2.xml', 'premp2.xml'),
            ]
            if test_pairs:
                batch_test_multiple_manifests(test_pairs)
            else:
                print("請在程式碼中設定要測試的檔案對")
        else:
            print("結束程式")
            sys.exit(0)