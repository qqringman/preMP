"""
主程式 - 互動式選單系統
整合所有功能模組，提供使用者友善的操作介面
"""
import os
import sys
from typing import Optional, Dict, Any
import utils
from feature_one import FeatureOne
from feature_two import FeatureTwo
from feature_three import FeatureThree

logger = utils.setup_logger(__name__)

class MainApplication:
    """主應用程式類別"""
    
    def __init__(self):
        self.logger = logger
        self.feature_one = FeatureOne()
        self.feature_two = FeatureTwo()
        self.feature_three = FeatureThree()
        
        # 初始化系統設定
        self._setup_system()
    
    def _setup_system(self):
        """初始化系統設定"""
        try:
            # 透過 utils 設定系統組態
            success = utils.setup_config()
            if success:
                self.logger.info("系統設定載入成功")
            else:
                self.logger.warning("系統設定載入失敗，使用預設值")
        except Exception as e:
            self.logger.error(f"系統設定初始化錯誤: {str(e)}")
            # 繼續執行，使用預設值
    
    def show_main_menu(self):
        """顯示主選單"""
        print("\n" + "="*60)
        print("     🔧 JIRA/Gerrit 整合工具系統")
        print("="*60)
        print()
        print("📋 主要功能群組:")
        print()
        print("  🔍 [1] 晶片映射表處理")
        print("      ├─ 1-1. 擴充晶片映射表 (功能一)")
        print("      └─ 1-2. 檢視晶片映射表資訊")
        print()
        print("  🌿 [2] 分支管理工具")
        print("      ├─ 2-1. 建立分支映射表 (功能二)")
        print("      ├─ 2-2. 批次建立分支")
        print("      └─ 2-3. 查詢分支狀態")
        print()
        print("  📄 [3] Manifest 處理工具")
        print("      ├─ 3-1. 去除版本號產生新 manifest (功能三)")
        print("      ├─ 3-2. 比較 manifest 差異")
        print("      └─ 3-3. 下載 Gerrit manifest")
        print()
        print("  ⚙️  [4] 系統工具")
        print("      ├─ 4-1. 測試 JIRA 連線")
        print("      ├─ 4-2. 測試 Gerrit 連線")
        print("      └─ 4-3. 系統設定")
        print()
        print("  ❌ [0] 離開程式")
        print()
        print("="*60)
    
    def run(self):
        """執行主程式"""
        try:
            self.logger.info("系統啟動")
            
            while True:
                self.show_main_menu()
                choice = input("請選擇功能 (輸入數字): ").strip()
                
                if choice == '0':
                    self._confirm_exit()
                    break
                elif choice == '1':
                    self._chip_mapping_menu()
                elif choice == '2':
                    self._branch_management_menu()
                elif choice == '3':
                    self._manifest_tools_menu()
                elif choice == '4':
                    self._system_tools_menu()
                elif choice in ['1-1', '11']:
                    self._execute_feature_one()
                elif choice in ['2-1', '21']:
                    self._execute_feature_two()
                elif choice in ['3-1', '31']:
                    self._execute_feature_three()
                else:
                    print(f"\n❌ 無效的選項: {choice}")
                    input("按 Enter 繼續...")
                    
        except KeyboardInterrupt:
            print("\n\n👋 使用者中斷程式")
        except Exception as e:
            self.logger.error(f"程式執行錯誤: {str(e)}")
            print(f"\n❌ 程式發生錯誤: {str(e)}")
        finally:
            self.logger.info("系統關閉")
            print("\n👋 感謝使用，再見！")
    
    def _chip_mapping_menu(self):
        """晶片映射表處理選單"""
        while True:
            print("\n" + "="*50)
            print("  🔍 晶片映射表處理")
            print("="*50)
            print("  [1] 擴充晶片映射表 (功能一)")
            print("  [2] 檢視晶片映射表資訊")
            print("  [0] 返回主選單")
            print("="*50)
            
            choice = input("請選擇功能: ").strip()
            
            if choice == '0':
                break
            elif choice == '1':
                self._execute_feature_one()
            elif choice == '2':
                self._view_chip_mapping_info()
            else:
                print(f"❌ 無效的選項: {choice}")
                input("按 Enter 繼續...")
    
    def _branch_management_menu(self):
        """分支管理工具選單"""
        while True:
            print("\n" + "="*50)
            print("  🌿 分支管理工具")
            print("="*50)
            print("  [1] 建立分支映射表 (功能二)")
            print("  [2] 批次建立分支")
            print("  [3] 查詢分支狀態")
            print("  [0] 返回主選單")
            print("="*50)
            
            choice = input("請選擇功能: ").strip()
            
            if choice == '0':
                break
            elif choice == '1':
                self._execute_feature_two()
            elif choice == '2':
                self._batch_create_branches()
            elif choice == '3':
                self._query_branch_status()
            else:
                print(f"❌ 無效的選項: {choice}")
                input("按 Enter 繼續...")
    
    def _manifest_tools_menu(self):
        """Manifest 處理工具選單"""
        while True:
            print("\n" + "="*50)
            print("  📄 Manifest 處理工具")
            print("="*50)
            print("  [1] 去除版本號產生新 manifest (功能三)")
            print("  [2] 比較 manifest 差異")
            print("  [3] 下載 Gerrit manifest")
            print("  [0] 返回主選單")
            print("="*50)
            
            choice = input("請選擇功能: ").strip()
            
            if choice == '0':
                break
            elif choice == '1':
                self._execute_feature_three()
            elif choice == '2':
                self._compare_manifest_diff()
            elif choice == '3':
                self._download_gerrit_manifest()
            else:
                print(f"❌ 無效的選項: {choice}")
                input("按 Enter 繼續...")
    
    def _system_tools_menu(self):
        """系統工具選單"""
        while True:
            print("\n" + "="*50)
            print("  ⚙️ 系統工具")
            print("="*50)
            print("  [1] 測試 JIRA 連線")
            print("  [2] 測試 Gerrit 連線")
            print("  [3] 系統設定")
            print("  [4] 診斷連線問題")
            print("  [0] 返回主選單")
            print("="*50)
            
            choice = input("請選擇功能: ").strip()
            
            if choice == '0':
                break
            elif choice == '1':
                self._test_jira_connection()
            elif choice == '2':
                self._test_gerrit_connection()
            elif choice == '3':
                self._system_settings()
            elif choice == '4':
                self._diagnose_connection_issues()
            else:
                print(f"❌ 無效的選項: {choice}")
                input("按 Enter 繼續...")
    
    def _diagnose_connection_issues(self):
        """診斷連線問題"""
        print("\n🔍 診斷連線問題")
        print("=" * 50)
        
        try:
            import config
            
            print("📋 目前設定檢查:")
            print(f"\n🔸 JIRA 設定:")
            print(f"  Site: {getattr(config, 'JIRA_SITE', 'N/A')}")
            print(f"  User: {getattr(config, 'JIRA_USER', 'N/A')}")
            print(f"  Password 長度: {len(getattr(config, 'JIRA_PASSWORD', ''))}")
            print(f"  Token 長度: {len(getattr(config, 'JIRA_TOKEN', ''))}")
            
            print(f"\n🔸 Gerrit 設定:")
            print(f"  Base: {getattr(config, 'GERRIT_BASE', 'N/A')}")
            print(f"  User: {getattr(config, 'GERRIT_USER', 'N/A')}")
            print(f"  Password 長度: {len(getattr(config, 'GERRIT_PW', ''))}")
            
            print(f"\n🔍 常見問題檢查:")
            
            # 檢查 JIRA 設定
            jira_issues = []
            if not getattr(config, 'JIRA_SITE', ''):
                jira_issues.append("JIRA_SITE 未設定")
            if not getattr(config, 'JIRA_USER', ''):
                jira_issues.append("JIRA_USER 未設定")
            if not getattr(config, 'JIRA_PASSWORD', ''):
                jira_issues.append("JIRA_PASSWORD 未設定")
            
            if jira_issues:
                print(f"  ❌ JIRA 設定問題: {', '.join(jira_issues)}")
            else:
                print(f"  ✅ JIRA 基本設定完整")
            
            # 檢查 Gerrit 設定
            gerrit_issues = []
            if not getattr(config, 'GERRIT_BASE', ''):
                gerrit_issues.append("GERRIT_BASE 未設定")
            if not getattr(config, 'GERRIT_USER', ''):
                gerrit_issues.append("GERRIT_USER 未設定")
            if not getattr(config, 'GERRIT_PW', ''):
                gerrit_issues.append("GERRIT_PW 未設定")
            
            if gerrit_issues:
                print(f"  ❌ Gerrit 設定問題: {', '.join(gerrit_issues)}")
            else:
                print(f"  ✅ Gerrit 基本設定完整")
            
            print(f"\n💡 常見解決方案:")
            print("  📌 JIRA HTTP 403 錯誤:")
            print("    1. 檢查帳號密碼是否正確")
            print("    2. 確認帳號沒有被鎖定")
            print("    3. 嘗試在瀏覽器登入 JIRA 確認帳號狀態")
            print("    4. 考慮使用 API Token 替代密碼")
            print("    5. 確認帳號有存取對應專案的權限")
            
            print("  📌 Gerrit 連線問題:")
            print("    1. 確認 VPN 連線 (如果需要)")
            print("    2. 檢查防火牆設定")
            print("    3. 確認帳號已註冊到 Gerrit")
            print("    4. 檢查 SSH 金鑰設定 (如果使用 SSH)")
            
            print("  📌 網路連線問題:")
            print("    1. 檢查是否能 ping 到伺服器")
            print("    2. 確認公司網路政策")
            print("    3. 嘗試使用不同的網路環境")
            
        except ImportError:
            print("❌ 無法載入 config 模組")
        except Exception as e:
            print(f"❌ 診斷過程發生錯誤: {str(e)}")
        
        input("\n按 Enter 繼續...")
    
    def _execute_feature_one(self):
        """執行功能一：擴充晶片映射表"""
        print("\n" + "="*60)
        print("  🔍 功能一：擴充晶片映射表")
        print("="*60)
        
        try:
            # 取得輸入檔案
            input_file = self._get_input_file("請輸入 all_chip_mapping_table.xlsx 檔案路徑")
            if not input_file:
                return
            
            # 取得輸出資料夾
            output_folder = self._get_output_folder("請輸入輸出資料夾路徑")
            if not output_folder:
                return
            
            print(f"\n📋 處理參數:")
            print(f"  輸入檔案: {input_file}")
            print(f"  輸出資料夾: {output_folder}")
            
            if not self._confirm_execution():
                return
            
            print("\n🔄 開始處理...")
            success = self.feature_one.process(input_file, output_folder)
            
            if success:
                print("\n✅ 功能一執行成功！")
                print(f"📁 結果檔案位於: {output_folder}")
            else:
                print("\n❌ 功能一執行失敗")
                
        except Exception as e:
            print(f"\n❌ 執行過程發生錯誤: {str(e)}")
        
        input("\n按 Enter 繼續...")
    
    def _execute_feature_two(self):
        """執行功能二：建立分支映射表"""
        print("\n" + "="*60)
        print("  🌿 功能二：建立分支映射表")
        print("="*60)
        
        try:
            # 取得輸入檔案
            input_file = self._get_input_file("請輸入 manifest.xml 檔案路徑")
            if not input_file:
                return
            
            # 選擇處理類型
            process_type = self._select_process_type()
            if not process_type:
                return
            
            # 取得輸出檔案名稱
            default_output = f"manifest_{process_type}.xlsx"
            output_file = input(f"請輸入輸出檔案名稱 (預設: {default_output}): ").strip()
            if not output_file:
                output_file = default_output
            
            # 選擇是否去重複
            remove_duplicates = self._get_yes_no_input("是否去除重複資料？", False)
            
            # 選擇是否建立分支
            create_branches = self._get_yes_no_input("是否建立分支？", False)
            
            print(f"\n📋 處理參數:")
            print(f"  輸入檔案: {input_file}")
            print(f"  處理類型: {process_type}")
            print(f"  輸出檔案: {output_file}")
            print(f"  去除重複: {'是' if remove_duplicates else '否'}")
            print(f"  建立分支: {'是' if create_branches else '否'}")
            
            if not self._confirm_execution():
                return
            
            print("\n🔄 開始處理...")
            success = self.feature_two.process(
                input_file, process_type, output_file, 
                remove_duplicates, create_branches
            )
            
            if success:
                print("\n✅ 功能二執行成功！")
                print(f"📁 結果檔案: {output_file}")
            else:
                print("\n❌ 功能二執行失敗")
                
        except Exception as e:
            print(f"\n❌ 執行過程發生錯誤: {str(e)}")
        
        input("\n按 Enter 繼續...")
    
    def _execute_feature_three(self):
        """執行功能三：去除版本號產生新 manifest"""
        print("\n" + "="*60)
        print("  📄 功能三：去除版本號產生新 manifest")
        print("="*60)
        
        try:
            # 取得輸入路徑
            input_path = input("請輸入 manifest.xml 檔案或資料夾路徑: ").strip()
            if not input_path or not os.path.exists(input_path):
                print("❌ 檔案或路徑不存在")
                input("按 Enter 繼續...")
                return
            
            # 取得輸出資料夾
            output_folder = self._get_output_folder("請輸入輸出資料夾路徑")
            if not output_folder:
                return
            
            # 選擇處理類型
            process_types = ['master', 'premp', 'mp', 'mpbackup']
            print("\n請選擇處理類型:")
            for i, ptype in enumerate(process_types, 1):
                print(f"  [{i}] {ptype}")
            
            while True:
                try:
                    choice = int(input("請選擇 (1-4): ").strip())
                    if 1 <= choice <= 4:
                        process_type = process_types[choice - 1]
                        break
                    else:
                        print("❌ 請輸入 1-4 之間的數字")
                except ValueError:
                    print("❌ 請輸入有效的數字")
            
            # 自定義 Excel 檔名（可選）
            excel_filename = input("請輸入 Excel 檔名 (可選，按 Enter 使用預設): ").strip()
            if not excel_filename:
                excel_filename = None
            
            print(f"\n📋 處理參數:")
            print(f"  輸入路徑: {input_path}")
            print(f"  輸出資料夾: {output_folder}")
            print(f"  處理類型: {process_type}")
            print(f"  Excel 檔名: {excel_filename or '使用預設'}")
            
            if not self._confirm_execution():
                return
            
            print("\n🔄 開始處理...")
            success = self.feature_three.process(
                input_path, output_folder, process_type, excel_filename
            )
            
            if success:
                print("\n✅ 功能三執行成功！")
                print(f"📁 結果檔案位於: {output_folder}")
            else:
                print("\n❌ 功能三執行失敗")
                
        except Exception as e:
            print(f"\n❌ 執行過程發生錯誤: {str(e)}")
        
        input("\n按 Enter 繼續...")
    
    def _get_input_file(self, prompt: str) -> Optional[str]:
        """取得輸入檔案路徑"""
        while True:
            file_path = input(f"{prompt}: ").strip()
            if not file_path:
                print("❌ 請輸入檔案路徑")
                continue
            
            if not os.path.exists(file_path):
                print(f"❌ 檔案不存在: {file_path}")
                retry = input("是否重新輸入？(y/n): ").strip().lower()
                if retry != 'y':
                    return None
                continue
            
            return file_path
    
    def _get_output_folder(self, prompt: str) -> Optional[str]:
        """取得輸出資料夾路徑"""
        output_folder = input(f"{prompt}: ").strip()
        if not output_folder:
            output_folder = "./output"
            print(f"使用預設輸出路徑: {output_folder}")
        
        # 確保資料夾存在
        utils.ensure_dir(output_folder)
        return output_folder
    
    def _select_process_type(self) -> Optional[str]:
        """選擇處理類型"""
        types = {
            '1': 'master_vs_premp',
            '2': 'premp_vs_mp', 
            '3': 'mp_vs_mpbackup'
        }
        
        print("\n請選擇處理類型:")
        print("  [1] master_vs_premp")
        print("  [2] premp_vs_mp")
        print("  [3] mp_vs_mpbackup")
        
        while True:
            choice = input("請選擇 (1-3): ").strip()
            if choice in types:
                return types[choice]
            elif choice == '0':
                return None
            else:
                print("❌ 請輸入 1-3 之間的數字")
    
    def _get_yes_no_input(self, prompt: str, default: bool = False) -> bool:
        """取得是/否輸入"""
        default_text = "Y/n" if default else "y/N"
        while True:
            response = input(f"{prompt} ({default_text}): ").strip().lower()
            if not response:
                return default
            elif response in ['y', 'yes', '是']:
                return True
            elif response in ['n', 'no', '否']:
                return False
            else:
                print("❌ 請輸入 y/n 或是/否")
    
    def _confirm_execution(self) -> bool:
        """確認執行"""
        return self._get_yes_no_input("\n是否確認執行？", True)
    
    def _confirm_exit(self):
        """確認離開"""
        if self._get_yes_no_input("確定要離開程式嗎？", False):
            return
        else:
            print("繼續使用程式...")
    
    def _view_chip_mapping_info(self):
        """檢視晶片映射表資訊"""
        print("\n🔍 檢視晶片映射表資訊")
        print("⚠️  此功能尚未實作")
        input("按 Enter 繼續...")
    
    def _batch_create_branches(self):
        """批次建立分支"""
        print("\n🌿 批次建立分支")
        print("⚠️  此功能尚未實作")
        input("按 Enter 繼續...")
    
    def _query_branch_status(self):
        """查詢分支狀態"""
        print("\n📊 查詢分支狀態")
        print("⚠️  此功能尚未實作")
        input("按 Enter 繼續...")
    
    def _compare_manifest_diff(self):
        """比較 manifest 差異"""
        print("\n📄 比較 manifest 差異")
        print("⚠️  此功能尚未實作")
        input("按 Enter 繼續...")
    
    def _download_gerrit_manifest(self):
        """下載 Gerrit manifest"""
        print("\n⬇️  下載 Gerrit manifest")
        print("⚠️  此功能尚未實作")
        input("按 Enter 繼續...")
    
    def _test_jira_connection(self):
        """測試 JIRA 連線"""
        print("\n🔗 測試 JIRA 連線")
        print("=" * 50)
        
        try:
            from jira_manager import JiraManager
            jira = JiraManager()
            
            print(f"📊 連線資訊:")
            print(f"  伺服器: {jira.base_url}")
            print(f"  用戶: {jira.user}")
            print(f"  認證: {'密碼' if jira.password else '無'}")
            print(f"  Token: {'有' if jira.token else '無'}")
            
            print(f"\n🔄 執行連線測試...")
            
            # 原本的連線測試
            result = jira.test_connection()
            
            if result['success']:
                print("✅ JIRA 連線測試成功")
                # ... 原有成功邏輯 ...
            else:
                print("❌ JIRA 連線測試失敗")
                print(f"📄 錯誤訊息: {result['message']}")
                
                # 如果原本的方法失敗，嘗試替代方案
                print(f"\n🔍 嘗試替代 API 路徑...")
                alt_result = jira.test_alternative_apis()
                
                if alt_result['working_apis']:
                    print("✅ 找到可用的 API 路徑:")
                    for api in alt_result['working_apis']:
                        print(f"  ✓ {api['auth_method']}: {api['url']} (HTTP {api['status']})")
                else:
                    print("❌ 所有替代 API 路徑都失敗")
                    
                    # 嘗試 Session 登入
                    print(f"\n🔑 嘗試 Session 登入...")
                    session_result = jira.try_session_login()
                    
                    if session_result['success']:
                        print(f"✅ Session 登入成功: {session_result['message']}")
                    else:
                        print(f"❌ Session 登入失敗: {session_result['message']}")
                
                # 提供具體解決建議
                print(f"\n💡 根據診斷結果的建議:")
                print("  🎯 主要問題：JIRA 所有 API 都回傳 HTML 而非 JSON")
                print("  📋 可能原因：")
                print("    1. JIRA 設定了強制登入才能存取 REST API")
                print("    2. 帳號沒有 REST API 存取權限")
                print("    3. 需要特殊的認證方式")
                print("  🛠️ 建議解決方案：")
                print("    1. 在瀏覽器登入 JIRA，確認帳號正常")
                print("    2. 聯絡 JIRA 管理員確認 REST API 設定")
                print("    3. 嘗試產生 Personal Access Token")
                print("    4. 檢查是否需要加入特定的使用者群組")
            
        except Exception as e:
            print(f"❌ JIRA 連線測試發生錯誤: {str(e)}")
        
        input("\n按 Enter 繼續...")
    
    def _test_gerrit_connection(self):
        """測試 Gerrit 連線"""
        print("\n🔗 測試 Gerrit 連線")
        print("=" * 50)
        
        try:
            from gerrit_manager import GerritManager
            gerrit = GerritManager()
            
            print(f"📊 連線資訊:")
            print(f"  伺服器: {gerrit.base_url}")
            print(f"  API URL: {gerrit.api_url}")
            print(f"  用戶: {gerrit.user}")
            print(f"  認證: {'有' if gerrit.password else '無'}")
            
            print(f"\n🔄 執行連線測試...")
            
            # 使用新的連線測試方法
            result = gerrit.test_connection()
            
            if result['success']:
                print("✅ Gerrit 連線測試成功")
                print(f"📄 測試結果:")
                details = result.get('details', {})
                if 'name' in details:
                    print(f"  登入用戶: {details['name']}")
                if 'username' in details:
                    print(f"  用戶名: {details['username']}")
                if 'email' in details:
                    print(f"  電子郵件: {details['email']}")
                if 'test_project' in details:
                    print(f"  測試專案: {details['test_project']}")
                if 'branch_count' in details:
                    print(f"  分支數量: {details['branch_count']}")
                
                # 顯示測試過程
                if result.get('tests_performed'):
                    print(f"🔍 執行的測試:")
                    for test in result['tests_performed']:
                        print(f"  ✓ {test}")
                        
            else:
                print("❌ Gerrit 連線測試失敗")
                print(f"📄 錯誤訊息: {result['message']}")
                
                if result.get('tests_performed'):
                    print(f"🔍 執行的測試:")
                    for test in result['tests_performed']:
                        print(f"  - {test}")
                
                # 提供解決建議
                print(f"\n💡 解決建議:")
                if "401" in result['message'] or "認證失敗" in result['message']:
                    print("  1. 檢查 config.py 中的 GERRIT_USER 和 GERRIT_PW")
                    print("  2. 確認 Gerrit 帳號密碼正確")
                    print("  3. 檢查是否需要 SSH 金鑰設定")
                elif "403" in result['message'] or "權限" in result['message']:
                    print("  1. 確認帳號有存取 Gerrit 的權限")
                    print("  2. 檢查是否為 Gerrit 註冊用戶")
                    print("  3. 聯絡 Gerrit 管理員確認權限")
                elif "網路" in result['message'] or "連線" in result['message']:
                    print("  1. 檢查網路連線")
                    print("  2. 確認 Gerrit 伺服器位址正確")
                    print("  3. 檢查 VPN 或防火牆設定")
                else:
                    print("  1. 檢查 config.py 中的所有 Gerrit 設定")
                    print("  2. 確認 Gerrit 伺服器狀態正常")
                
        except Exception as e:
            print(f"❌ Gerrit 連線測試發生錯誤: {str(e)}")
            print(f"\n💡 可能原因:")
            print("  1. 缺少必要的 Python 套件 (requests)")
            print("  2. config.py 設定有誤")
            print("  3. 網路連線問題")
        
        input("\n按 Enter 繼續...")
    
    def _system_settings(self):
        """系統設定"""
        while True:
            print("\n" + "="*50)
            print("  ⚙️ 系統設定")
            print("="*50)
            print("  [1] 檢視目前設定")
            print("  [2] 修改 JIRA 設定")
            print("  [3] 修改 Gerrit 設定") 
            print("  [4] 重設所有設定")
            print("  [0] 返回上層選單")
            print("="*50)
            
            choice = input("請選擇功能: ").strip()
            
            if choice == '0':
                break
            elif choice == '1':
                self._view_current_settings()
            elif choice == '2':
                self._modify_jira_settings()
            elif choice == '3':
                self._modify_gerrit_settings()
            elif choice == '4':
                self._reset_all_settings()
            else:
                print(f"❌ 無效的選項: {choice}")
                input("按 Enter 繼續...")
    
    def _view_current_settings(self):
        """檢視目前設定"""
        print("\n📋 目前系統設定:")
        
        try:
            import config
            print("\n🔸 JIRA 設定:")
            print(f"  Site: {getattr(config, 'JIRA_SITE', 'N/A')}")
            print(f"  User: {getattr(config, 'JIRA_USER', 'N/A')}")
            print(f"  Password: {'*' * len(getattr(config, 'JIRA_PASSWORD', ''))}")
            print(f"  Token: {getattr(config, 'JIRA_TOKEN', 'N/A')[:10]}...")
            
            print("\n🔸 Gerrit 設定:")
            print(f"  Base URL: {getattr(config, 'GERRIT_BASE', 'N/A')}")
            print(f"  API Prefix: {getattr(config, 'GERRIT_API_PREFIX', 'N/A')}")
            print(f"  User: {getattr(config, 'GERRIT_USER', 'N/A')}")
            print(f"  Password: {'*' * len(getattr(config, 'GERRIT_PW', ''))}")
            
        except ImportError:
            print("❌ 無法載入 config 模組")
            print("\n🔸 環境變數設定:")
            print(f"  JIRA_SITE: {os.environ.get('JIRA_SITE', 'N/A')}")
            print(f"  JIRA_USER: {os.environ.get('JIRA_USER', 'N/A')}")
            print(f"  JIRA_PASSWORD: {'*' * len(os.environ.get('JIRA_PASSWORD', ''))}")
            print(f"  JIRA_TOKEN: {os.environ.get('JIRA_TOKEN', 'N/A')[:10]}...")
            
            print(f"  GERRIT_BASE: {os.environ.get('GERRIT_BASE', 'N/A')}")
            print(f"  GERRIT_USER: {os.environ.get('GERRIT_USER', 'N/A')}")
            print(f"  GERRIT_PW: {'*' * len(os.environ.get('GERRIT_PW', ''))}")
        
        input("\n按 Enter 繼續...")
    
    def _modify_jira_settings(self):
        """修改 JIRA 設定"""
        print("\n✏️  修改 JIRA 設定")
        print("⚠️  此功能尚未實作")
        input("按 Enter 繼續...")
    
    def _modify_gerrit_settings(self):
        """修改 Gerrit 設定"""
        print("\n✏️  修改 Gerrit 設定")
        print("⚠️  此功能尚未實作") 
        input("按 Enter 繼續...")
    
    def _reset_all_settings(self):
        """重設所有設定"""
        print("\n🔄 重設所有設定")
        if self._get_yes_no_input("確定要重設所有設定嗎？", False):
            try:
                # 重新載入設定
                success = utils.setup_config()
                if success:
                    print("✅ 設定已重設為 config.py 中的預設值")
                else:
                    print("⚠️  設定重設過程中發生警告，請檢查 config.py")
            except Exception as e:
                print(f"❌ 設定重設失敗: {str(e)}")
        else:
            print("❌ 已取消重設")
        input("按 Enter 繼續...")


def main():
    """主函數"""
    try:
        app = MainApplication()
        app.run()
    except Exception as e:
        print(f"程式啟動失敗: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()