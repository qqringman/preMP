#!/usr/bin/env python3
"""
快速測試 Master to PreMP 轉換規則
可以獨立執行或整合到現有系統中
修改：增加失敗案例詳細顯示功能
"""
import os
import sys

# 加入上一層目錄到路徑
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

import utils

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
        from manifest_conversion import ManifestConversionTester
        
        # 執行測試
        tester = ManifestConversionTester()
        success = tester.test_conversion(master_file, premp_file, output_file)
        
        # 🆕 顯示詳細結果，包含失敗案例資訊
        print("\n" + "="*60)
        if success:
            print("✅ 測試完成 - 所有轉換規則正確！")
        else:
            print("⚠️ 測試完成 - 發現轉換差異")
            
            # 🆕 如果有失敗案例，顯示詳細資訊
            if hasattr(tester, 'failed_cases') and tester.failed_cases:
                print(f"\n❌ 失敗案例摘要 ({len(tester.failed_cases)} 個):")
                
                # 按規則類型分組顯示
                rule_failures = {}
                for case in tester.failed_cases:
                    rule_type = case['轉換規則類型']
                    if rule_type not in rule_failures:
                        rule_failures[rule_type] = []
                    rule_failures[rule_type].append({
                        'sn': case['SN'],
                        'name': case['專案名稱'],
                        'master': case['Master Revision'],
                        'converted': case['轉換後 Revision'],
                        'expected': case['PreMP Revision (正確版)']
                    })
                
                for rule_type, failures in rule_failures.items():
                    print(f"\n  🔴 {rule_type} ({len(failures)} 個失敗):")
                    for failure in failures[:3]:  # 只顯示前3個
                        print(f"    SN {failure['sn']}: {failure['name']}")
                        print(f"      Master: {failure['master']}")
                        print(f"      轉換後: {failure['converted']}")
                        print(f"      期望值: {failure['expected']}")
                    
                    if len(failures) > 3:
                        print(f"    ... 還有 {len(failures) - 3} 個失敗案例")
                
                print(f"\n💡 詳細失敗資訊請查看 Excel 報告中的 '失敗案例詳細對照' 頁籤")
                print(f"💡 轉換規則分析請查看 '轉換規則統計' 頁籤的 '失敗案例SN列表' 欄位")
            
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
            
            # 🔥 使用 config.py 動態生成預設 URL
            master_url = input("請輸入 Master manifest 的 Gerrit URL: ").strip()
            if not master_url:
                master_url = config.get_master_manifest_url()
                print(f"使用預設 URL: {master_url}")
                print(f"🔧 動態生成，當前 Android 版本: {config.get_current_android_version()}")
            
            temp_dir = tempfile.mkdtemp()
            master_file = os.path.join(temp_dir, "master_manifest.xml")
            
            if gerrit.download_file_from_link(master_url, master_file):
                print(f"✅ 成功下載 Master manifest")
            else:
                print(f"❌ 下載 Master manifest 失敗")
                return False
            
            # 🔥 使用 config.py 動態生成預設 URL
            premp_url = input("請輸入 PreMP manifest 的 Gerrit URL: ").strip()
            if not premp_url:
                premp_url = config.get_premp_manifest_url()
                print(f"使用預設 URL: {premp_url}")
                print(f"🔧 動態生成，當前 Android 版本: {config.get_current_android_version()}")
            
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
    修改：顯示更詳細的轉換成功資訊和失敗案例摘要
    
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
            from manifest_conversion import ManifestConversionTester
            tester = ManifestConversionTester()
            success = tester.test_conversion(master_file, premp_file, output_file)
            
            results.append({
                'index': i,
                'master': master_file,
                'premp': premp_file,
                'output': output_file,
                'success': success,
                'stats': tester.stats,
                'failed_cases': getattr(tester, 'failed_cases', [])  # 🆕 新增失敗案例
            })
            
            # 顯示詳細的轉換統計
            stats = tester.stats
            print(f"  📊 統計結果:")
            print(f"    - 總專案數: {stats['total_projects']}")
            print(f"    - 🔵 參與轉換: {stats['revision_projects']}")
            print(f"    - ⚪ 無revision: {stats['no_revision_projects']}")
            print(f"    - 🟢 原始相同: {stats['same_revision_projects']}")
            print(f"    - 🟣 完全跳過: {stats['skipped_special_projects']}")
            print(f"    - ✅ 轉換成功: {stats['matched']}")
            print(f"    - ❌ 轉換失敗: {stats['mismatched']}")
            
            if stats['revision_projects'] > 0:
                success_rate = (stats['matched'] / stats['revision_projects'] * 100)
                print(f"    - 📈 成功率: {success_rate:.2f}%")
            
            # 🆕 顯示失敗案例摘要
            if hasattr(tester, 'failed_cases') and tester.failed_cases:
                print(f"    - 🔴 失敗案例: {len(tester.failed_cases)} 個")
                
                # 顯示失敗案例的專案名稱（最多3個）
                failed_names = [case['專案名稱'] for case in tester.failed_cases[:3]]
                print(f"      {', '.join(failed_names)}")
                if len(tester.failed_cases) > 3:
                    print(f"      ... 還有 {len(tester.failed_cases) - 3} 個")
            
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
                'error': str(e),
                'failed_cases': []
            })
    
    # 顯示總結
    print("\n" + "="*60)
    print("📊 批次測試結果總結")
    print("="*60)
    
    passed = sum(1 for r in results if r['success'])
    failed = len(results) - passed
    
    # 計算整體統計
    total_projects = sum(r['stats']['total_projects'] for r in results if 'stats' in r)
    total_revision_projects = sum(r['stats']['revision_projects'] for r in results if 'stats' in r)
    total_no_revision = sum(r['stats']['no_revision_projects'] for r in results if 'stats' in r)
    total_skipped_complete = sum(r['stats']['skipped_special_projects'] for r in results if 'stats' in r)
    total_same_revision = sum(r['stats']['same_revision_projects'] for r in results if 'stats' in r)
    total_matched = sum(r['stats']['matched'] for r in results if 'stats' in r)
    total_mismatched = sum(r['stats']['mismatched'] for r in results if 'stats' in r)
    
    # 🆕 統計全部失敗案例
    all_failed_cases = []
    for r in results:
        if 'failed_cases' in r:
            all_failed_cases.extend(r['failed_cases'])
    
    print(f"🔢 整體統計:")
    print(f"  總測試數: {len(results)}")
    print(f"  ✅ 通過: {passed}")
    print(f"  ❌ 失敗: {failed}")
    print(f"  成功率: {(passed/len(results)*100):.1f}%")
    print(f"\n📊 專案轉換統計:")
    print(f"  總專案數: {total_projects}")
    print(f"  🔵 參與轉換專案: {total_revision_projects}")
    print(f"  ⚪ 無revision專案: {total_no_revision}")
    print(f"  🟢 原始相同專案: {total_same_revision}")
    print(f"  🟣 完全跳過專案: {total_skipped_complete}")
    print(f"  ✅ 轉換成功: {total_matched} (包括原始相同)")
    print(f"  ❌ 轉換失敗: {total_mismatched}")
    
    if total_revision_projects > 0:
        overall_success_rate = (total_matched / total_revision_projects * 100)
        print(f"  📈 整體轉換成功率: {overall_success_rate:.2f}%")
    
    # 🆕 顯示失敗案例總結
    if all_failed_cases:
        print(f"\n🔴 失敗案例總結 ({len(all_failed_cases)} 個):")
        
        # 按規則類型分組統計
        rule_failures = {}
        for case in all_failed_cases:
            rule_type = case['轉換規則類型']
            if rule_type not in rule_failures:
                rule_failures[rule_type] = 0
            rule_failures[rule_type] += 1
        
        for rule_type, count in sorted(rule_failures.items(), key=lambda x: x[1], reverse=True):
            print(f"  {rule_type}: {count} 個失敗")
    
    # 顯示詳細結果
    print("\n詳細結果:")
    for result in results:
        status = "✅" if result['success'] else "❌"
        print(f"{status} 測試 {result['index']}: {os.path.basename(result['master'])}")
        if 'stats' in result:
            stats = result['stats']
            print(f"   參與轉換: {stats['revision_projects']}, 成功: {stats['matched']}, 失敗: {stats['mismatched']}")
        if 'failed_cases' in result and result['failed_cases']:
            print(f"   失敗案例: {len(result['failed_cases'])} 個")
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