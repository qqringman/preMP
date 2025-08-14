"""
main.py - 主程式 - 互動式選單系統 (模組化重構版)
整合所有功能模組，提供使用者友善的操作介面
已移除未實作功能，採用模組化架構但集中在同一檔案
"""
import os
import sys
from typing import Optional, Dict, Any
import utils
from feature_one import FeatureOne
from feature_two import FeatureTwo
from feature_three import FeatureThree
import subprocess
import tempfile
import shutil

logger = utils.setup_logger(__name__)


class MenuManager:
    """選單管理類別"""
    
    def __init__(self):
        pass
    
    def show_main_menu(self):
        """顯示主選單"""
        print("\n" + "="*60)
        print("     🔧 JIRA/Gerrit 整合工具系統")
        print("="*60)
        print()
        print("📋 主要功能群組:")
        print()
        print("  📊 [1] 晶片映射表處理")
        print("      └─ 1-1. 擴充晶片映射表 (功能一)")
        print()
        print("  🌿 [2] 分支管理工具")
        print("      ├─ 2-1. 建立分支映射表 (功能二)")
        print("      ├─ 🆕 支援強制更新已存在分支")
        print("      ├─ 智能跳過已存在分支")
        print("      └─ 詳細分支建立狀態報告")
        print()
        print("  📄 [3] Manifest 處理工具")
        print("      ├─ 3-1. Manifest 轉換工具 (功能三) 🚀")
        print("      ├─ 3-2. 比較 manifest 差異")
        print("      └─ 3-3. 下載 Gerrit manifest")
        print()
        print("  ⚙️  [4] 系統工具")
        print("      ├─ 4-1. 測試 JIRA 連線")
        print("      ├─ 4-2. 測試 Gerrit 連線")
        print("      ├─ 4-3. 系統設定")
        print("      └─ 4-4. 診斷連線問題")
        print()
        print("  ❌ [0] 離開程式")
        print()
        print("="*60)
    
    def show_chip_mapping_menu(self):
        """晶片映射表處理選單"""
        print("\n" + "="*50)
        print("  📊 晶片映射表處理")
        print("="*50)
        print("  [1] 擴充晶片映射表 (功能一)")
        print("  [0] 返回主選單")
        print("="*50)
    
    def show_branch_management_menu(self):
        """分支管理工具選單"""
        print("\n" + "="*50)
        print("  🌿 分支管理工具")
        print("="*50)
        print("  [1] 建立分支映射表 (功能二)")
        print("      ├─ 支援強制更新已存在分支")
        print("      ├─ 智能跳過已存在分支")
        print("      └─ 詳細分支建立狀態報告")
        print("  [0] 返回主選單")
        print("="*50)
    
    def show_manifest_tools_menu(self):
        """Manifest 處理工具選單"""
        print("\n" + "="*50)
        print("  📄 Manifest 處理工具")
        print("="*50)
        print("  [1] Manifest 轉換工具 (功能三) 🚀")
        print("  [2] 比較 manifest 差異")
        print("  [3] 下載 Gerrit manifest")
        print("  [0] 返回主選單")
        print("="*50)
    
    def show_system_tools_menu(self):
        """系統工具選單"""
        print("\n" + "="*50)
        print("  ⚙️ 系統工具")
        print("="*50)
        print("  [1] 測試 JIRA 連線")
        print("  [2] 測試 Gerrit 連線")
        print("  [3] 系統設定")
        print("  [4] 診斷連線問題")
        print("  [0] 返回主選單")
        print("="*50)
    
    def show_system_settings_menu(self):
        """系統設定選單"""
        print("\n" + "="*50)
        print("  ⚙️ 系統設定")
        print("="*50)
        print("  [1] 檢視目前設定")
        print("  [2] 重設所有設定")
        print("  [0] 返回上層選單")
        print("="*50)


class InputValidator:
    """輸入驗證類別"""
    
    def __init__(self):
        pass
    
    def get_input_file(self, prompt: str) -> Optional[str]:
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
    
    def get_output_folder(self, prompt: str, default: str = "./output") -> str:
        """取得輸出資料夾路徑"""
        output_folder = input(f"{prompt} (預設: {default}): ").strip()
        if not output_folder:
            output_folder = default
            print(f"使用預設輸出路徑: {output_folder}")
        
        # 確保資料夾存在
        utils.ensure_dir(output_folder)
        return output_folder
    
    def get_yes_no_input(self, prompt: str, default: bool = False) -> bool:
        """取得是/否輸入"""
        default_text = "Y/n" if default else "y/N"
        while True:
            response = input(f"{prompt} ({default_text}): ").strip().lower()
            if not response:
                result = default
                print(f"使用預設值: {'是' if result else '否'}")
                return result
            elif response in ['y', 'yes', '是']:
                print("選擇: 是")
                return True
            elif response in ['n', 'no', '否']:
                print("選擇: 否")
                return False
            else:
                print("❌ 請輸入 y/n、是/否，或直接按 Enter 使用預設值")
    
    def get_choice_input(self, prompt: str, valid_choices: list) -> str:
        """取得選擇輸入"""
        while True:
            choice = input(f"{prompt}: ").strip()
            if choice in valid_choices:
                return choice
            else:
                print(f"❌ 無效的選項，請選擇: {', '.join(valid_choices)}")
    
    def select_process_type(self) -> Optional[str]:
        """選擇處理類型"""
        types = {
            '1': 'master_vs_premp',
            '2': 'premp_vs_mp', 
            '3': 'mp_vs_mpbackup'
        }
        
        print("\n請選擇處理類型:")
        print("  [1] master_vs_premp (master → premp)")
        print("  [2] premp_vs_mp (premp → mp)")
        print("  [3] mp_vs_mpbackup (mp → mpbackup)")
        print("  [0] 返回上層選單")
        
        while True:
            choice = input("請選擇 (1-3): ").strip()
            if choice in types:
                selected_type = types[choice]
                print(f"已選擇: {selected_type}")
                return selected_type
            elif choice == '0':
                return None
            else:
                print("❌ 請輸入 1-3 之間的數字，或輸入 0 返回")
    
    def confirm_execution(self) -> bool:
        """確認執行"""
        return self.get_yes_no_input("\n是否確認執行？", True)


class SystemManager:
    """系統管理類別"""
    
    def __init__(self):
        self.logger = utils.setup_logger(__name__)
    
    def test_jira_connection(self):
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
            
            print(f"\n📄 執行連線測試...")
            
            # 原本的連線測試
            result = jira.test_connection()
            
            if result['success']:
                print("✅ JIRA 連線測試成功")
                details = result.get('details', {})
                if 'name' in details:
                    print(f"  登入用戶: {details['name']}")
                if 'username' in details:
                    print(f"  用戶名: {details['username']}")
                if 'email' in details:
                    print(f"  電子郵件: {details['email']}")
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
                self._show_jira_troubleshooting()
                
        except Exception as e:
            print(f"❌ JIRA 連線測試發生錯誤: {str(e)}")
            self._show_jira_troubleshooting()
    
    def test_gerrit_connection(self):
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
            
            print(f"\n📄 執行連線測試...")
            
            # 使用新的連線測試方法
            result = gerrit.test_connection()
            
            if result['success']:
                print("✅ Gerrit 連線測試成功")
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
                
                self._show_gerrit_troubleshooting()
                
        except Exception as e:
            print(f"❌ Gerrit 連線測試發生錯誤: {str(e)}")
            self._show_gerrit_troubleshooting()
    
    def diagnose_connection_issues(self):
        """診斷連線問題"""
        print("\n🔍 診斷連線問題")
        print("=" * 50)
        
        try:
            import config
            
            print("📋 目前設定檢查:")
            print(f"\n📸 JIRA 設定:")
            print(f"  Site: {getattr(config, 'JIRA_SITE', 'N/A')}")
            print(f"  User: {getattr(config, 'JIRA_USER', 'N/A')}")
            print(f"  Password 長度: {len(getattr(config, 'JIRA_PASSWORD', ''))}")
            print(f"  Token 長度: {len(getattr(config, 'JIRA_TOKEN', ''))}")
            
            print(f"\n📸 Gerrit 設定:")
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
            
            self._show_common_solutions()
            
        except ImportError:
            print("❌ 無法載入 config 模組")
            self._show_environment_settings()
    
    def view_current_settings(self):
        """檢視目前設定"""
        print("\n📋 目前系統設定:")
        
        try:
            import config
            print("\n📸 JIRA 設定:")
            print(f"  Site: {getattr(config, 'JIRA_SITE', 'N/A')}")
            print(f"  User: {getattr(config, 'JIRA_USER', 'N/A')}")
            print(f"  Password: {'*' * len(getattr(config, 'JIRA_PASSWORD', ''))}")
            print(f"  Token: {getattr(config, 'JIRA_TOKEN', 'N/A')[:10]}...")
            
            print("\n📸 Gerrit 設定:")
            print(f"  Base URL: {getattr(config, 'GERRIT_BASE', 'N/A')}")
            print(f"  API Prefix: {getattr(config, 'GERRIT_API_PREFIX', 'N/A')}")
            print(f"  User: {getattr(config, 'GERRIT_USER', 'N/A')}")
            print(f"  Password: {'*' * len(getattr(config, 'GERRIT_PW', ''))}")
            
        except ImportError:
            print("❌ 無法載入 config 模組")
            self._show_environment_settings()
    
    def reset_all_settings(self):
        """重設所有設定"""
        print("\n🔄 重設所有設定")
        
        validator = InputValidator()
        
        if validator.get_yes_no_input("確定要重設所有設定嗎？", False):
            try:
                success = utils.setup_config()
                if success:
                    print("✅ 設定已重設為 config.py 中的預設值")
                else:
                    print("⚠️  設定重設過程中發生警告，請檢查 config.py")
            except Exception as e:
                print(f"❌ 設定重設失敗: {str(e)}")
        else:
            print("❌ 已取消重設")
    
    def _show_environment_settings(self):
        """顯示環境變數設定"""
        print("\n📸 環境變數設定:")
        print(f"  JIRA_SITE: {os.environ.get('JIRA_SITE', 'N/A')}")
        print(f"  JIRA_USER: {os.environ.get('JIRA_USER', 'N/A')}")
        print(f"  JIRA_PASSWORD: {'*' * len(os.environ.get('JIRA_PASSWORD', ''))}")
        print(f"  JIRA_TOKEN: {os.environ.get('JIRA_TOKEN', 'N/A')[:10]}...")
        
        print(f"  GERRIT_BASE: {os.environ.get('GERRIT_BASE', 'N/A')}")
        print(f"  GERRIT_USER: {os.environ.get('GERRIT_USER', 'N/A')}")
        print(f"  GERRIT_PW: {'*' * len(os.environ.get('GERRIT_PW', ''))}")
    
    def _show_common_solutions(self):
        """顯示常見解決方案"""
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
    
    def _show_jira_troubleshooting(self):
        """顯示 JIRA 故障排除"""
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
    
    def _show_gerrit_troubleshooting(self):
        """顯示 Gerrit 故障排除"""
        print(f"\n💡 Gerrit 故障排除:")
        print("  1. 檢查 config.py 中的 Gerrit 設定")
        print("  2. 確認 VPN 連線")
        print("  3. 檢查 SSH 金鑰設定")
        print("  4. 確認帳號權限")
        print("  5. 測試網路連線")


class FeatureManager:
    """功能管理類別"""
    
    def __init__(self, feature_one, feature_two, feature_three):
        self.logger = utils.setup_logger(__name__)
        self.feature_one = feature_one
        self.feature_two = feature_two
        self.feature_three = feature_three
        self.validator = InputValidator()
    
    def execute_feature_one(self):
        """執行功能一：擴充晶片映射表"""
        print("\n" + "="*60)
        print("  📊 功能一：擴充晶片映射表")
        print("="*60)
        
        try:
            # 取得輸入檔案
            input_file = self.validator.get_input_file("請輸入 all_chip_mapping_table.xlsx 檔案路徑")
            if not input_file:
                return
            
            # 取得輸出資料夾
            output_folder = self.validator.get_output_folder("請輸入輸出資料夾路徑")
            if not output_folder:
                return
            
            print(f"\n📋 處理參數:")
            print(f"  輸入檔案: {input_file}")
            print(f"  輸出資料夾: {output_folder}")
            
            if not self.validator.confirm_execution():
                return
            
            print("\n📄 開始處理...")
            success = self.feature_one.process(input_file, output_folder)
            
            if success:
                print("\n✅ 功能一執行成功！")
                print(f"📁 結果檔案位於: {output_folder}")
            else:
                print("\n❌ 功能一執行失敗")
                
        except Exception as e:
            print(f"\n❌ 執行過程發生錯誤: {str(e)}")
            self.logger.error(f"功能一執行失敗: {str(e)}")
    
    def execute_feature_two(self):
        """執行功能二：建立分支映射表"""
        print("\n" + "="*60)
        print("  🌿 功能二：建立分支映射表")
        print("="*60)
        
        try:
            # 1. 取得輸入檔案
            input_file = self.validator.get_input_file("請輸入 manifest.xml 檔案路徑")
            if not input_file:
                return
            
            # 2. 取得輸出資料夾
            output_folder = self.validator.get_output_folder("請輸入輸出資料夾路徑")
            if not output_folder:
                return
            
            # 3. 選擇處理類型
            process_type = self.validator.select_process_type()
            if not process_type:
                return
            
            # 4. 取得輸出檔案名稱
            default_output = f"manifest_{process_type}.xlsx"
            output_file = input(f"請輸入輸出檔案名稱 (預設: {default_output}): ").strip()
            if not output_file:
                output_file = default_output
            
            # 5. 是否去除重複資料
            remove_duplicates = self.validator.get_yes_no_input("是否去除重複資料？", False)
            
            # 6. 是否建立分支
            create_branches = self.validator.get_yes_no_input("是否建立分支？", False)
            
            # 6.5. 強制更新分支選項
            force_update_branches = False
            if create_branches:
                force_update_branches = self._get_force_update_option()
            
            # 7. 是否檢查分支存在性
            check_branch_exists = self.validator.get_yes_no_input("是否檢查分支存在性？(會比較慢)", False)
            
            # 顯示所有參數供確認
            self._show_feature_two_parameters(
                input_file, output_folder, process_type, output_file,
                remove_duplicates, create_branches, force_update_branches, check_branch_exists
            )
            
            if not self.validator.confirm_execution():
                return
            
            print("\n📄 開始處理...")
            
            success = self.feature_two.process(
                input_file, process_type, output_file, 
                remove_duplicates, create_branches, check_branch_exists, output_folder,
                force_update_branches
            )
            
            if success:
                print("\n✅ 功能二執行成功！")
                print(f"📁 結果檔案: {os.path.join(output_folder, output_file)}")
                self._show_feature_two_results(create_branches, force_update_branches, check_branch_exists)
            else:
                print("\n❌ 功能二執行失敗")
                
        except Exception as e:
            print(f"\n❌ 執行過程發生錯誤: {str(e)}")
            self.logger.error(f"功能二執行失敗: {str(e)}")
    
    def execute_feature_three(self):
        """執行功能三：Manifest 轉換工具"""
        print("\n" + "="*70)
        print("  📄 功能三：Manifest 轉換工具 🚀 (支援 Gerrit 推送)")
        print("="*70)
        print("說明：從 Gerrit 下載源檔案，進行 revision 轉換，並可選擇推送到 Gerrit")
        
        try:
            # 取得輸出資料夾
            output_folder = self.validator.get_output_folder("請輸入輸出資料夾路徑")
            if not output_folder:
                return
            
            # 選擇轉換類型
            overwrite_type = self._get_overwrite_type()
            if not overwrite_type:
                return
            
            # 自定義 Excel 檔名
            excel_filename = input("請輸入 Excel 檔名 (可選，按 Enter 使用預設): ").strip()
            if not excel_filename:
                excel_filename = None
            
            # 是否推送到 Gerrit
            push_to_gerrit = self._get_gerrit_push_option()
            
            self._show_feature_three_parameters(overwrite_type, output_folder, excel_filename, push_to_gerrit)
            self._show_processing_flow(overwrite_type, push_to_gerrit)
            
            if not self.validator.confirm_execution():
                return
            
            print("\n📄 開始處理...")
            print("⬇️ 正在從 Gerrit 下載源檔案...")
            
            success = self.feature_three.process(
                overwrite_type=overwrite_type,
                output_folder=output_folder,
                excel_filename=excel_filename,
                push_to_gerrit=push_to_gerrit
            )
            
            if success:
                print("\n✅ 功能三執行成功！")
                self._show_feature_three_results(output_folder, push_to_gerrit)
            else:
                print("\n❌ 功能三執行失敗")
                self._show_feature_three_troubleshooting()
                
        except Exception as e:
            print(f"\n❌ 執行過程發生錯誤: {str(e)}")
            self.logger.error(f"功能三執行失敗: {str(e)}")
    
    def _get_force_update_option(self):
        """取得強制更新分支選項"""
        print("\n" + "="*50)
        print("  📄 分支建立模式設定")
        print("="*50)
        print("分支處理邏輯說明：")
        print("• 預設模式：如果分支已存在，視為成功並跳過建立")
        print("• 強制更新模式：如果分支已存在，強制更新到新的 revision")
        print()
        print("⚠️  強制更新注意事項：")
        print("• 會覆蓋現有分支的 revision")
        print("• 可能會影響其他開發者的工作")
        print("• 建議在確認無人使用該分支時才使用")
        print()
        
        force_update_branches = self.validator.get_yes_no_input(
            "是否強制更新已存在的分支？", False
        )
        
        if force_update_branches:
            print("⚠️  已啟用強制更新模式")
            confirm_force = self.validator.get_yes_no_input(
                "確定要強制更新已存在的分支嗎？(這會覆蓋現有分支)", False
            )
            if not confirm_force:
                force_update_branches = False
                print("✅ 已改為預設模式（跳過已存在的分支）")
        else:
            print("✅ 使用預設模式（已存在的分支視為成功並跳過）")
        
        return force_update_branches
    
    def _show_feature_two_parameters(self, input_file, output_folder, process_type, output_file,
                                   remove_duplicates, create_branches, force_update_branches, check_branch_exists):
        """顯示功能二參數"""
        print(f"\n📋 處理參數:")
        print(f"  輸入檔案: {input_file}")
        print(f"  輸出資料夾: {output_folder}")
        print(f"  處理類型: {process_type}")
        print(f"  輸出檔案: {output_file}")
        print(f"  去除重複: {'是' if remove_duplicates else '否'}")
        print(f"  建立分支: {'是' if create_branches else '否'}")
        if create_branches:
            print(f"  🆕 強制更新分支: {'是' if force_update_branches else '否'}")
            if force_update_branches:
                print(f"      ⚠️  將覆蓋已存在分支的 revision")
            else:
                print(f"      ✅ 已存在分支將被跳過（視為成功）")
        print(f"  檢查分支存在性: {'是' if check_branch_exists else '否'}")
    
    def _show_feature_two_results(self, create_branches, force_update_branches, check_branch_exists):
        """顯示功能二結果"""
        if create_branches:
            print("🌿 分支建立狀態已記錄在 Excel 的 'Branch 建立狀態' 頁籤")
            if force_update_branches:
                print("📄 強制更新模式：已存在的分支已被更新到新的 revision")
            else:
                print("✅ 預設模式：已存在的分支被視為成功並跳過")
            print("💡 提示：查看 'Force_Update' 欄位了解各分支的處理方式")
        if check_branch_exists:
            print("🔍 分支存在性檢查結果已記錄在 'target_branch_exists' 欄位")
    
    def _get_overwrite_type(self):
        """取得轉換類型"""
        overwrite_types = {
            '1': 'master_to_premp',
            '2': 'premp_to_mp', 
            '3': 'mp_to_mpbackup'
        }
        
        print("\n請選擇轉換類型:")
        print("  [1] master_to_premp (Master → PreMP)")
        print("      源檔案: atv-google-refplus.xml")
        print("      輸出: atv-google-refplus-premp.xml")
        print()
        print("  [2] premp_to_mp (PreMP → MP)")
        print("      源檔案: atv-google-refplus-premp.xml")
        print("      輸出: atv-google-refplus-wave.xml")
        print()
        print("  [3] mp_to_mpbackup (MP → MP Backup)")
        print("      源檔案: atv-google-refplus-wave.xml")
        print("      輸出: atv-google-refplus-wave-backup.xml")
        print()
        
        while True:
            choice = input("請選擇 (1-3): ").strip()
            if choice in overwrite_types:
                return overwrite_types[choice]
            else:
                print("❌ 請輸入 1-3 之間的數字")
    
    def _get_gerrit_push_option(self):
        """取得 Gerrit 推送選項"""
        print("\n" + "="*50)
        print("  🚀 Gerrit 推送設定")
        print("="*50)
        print("推送功能說明：")
        print("• 自動判斷是否需要推送 (目標檔案不存在或內容不同)")
        print("• 執行 Git clone, commit, push 操作")
        print("• 推送到 refs/for/branch (等待 Code Review)")
        print("• 提供 Gerrit Review URL")
        print()
        print("⚠️  推送需求：")
        print("• 系統已安裝 Git")
        print("• SSH 認證到 mm2sd.rtkbf.com:29418")
        print("• Git 用戶名和郵箱已設定")
        print()
        
        push_to_gerrit = self.validator.get_yes_no_input(
            "是否要將轉換結果推送到 Gerrit 伺服器？", False
        )
        
        if push_to_gerrit:
            git_check = self._check_git_requirements()
            if not git_check['valid']:
                print(f"\n❌ Git 設定檢查失敗:")
                for issue in git_check['issues']:
                    print(f"  • {issue}")
                print("\n💡 建議：")
                for suggestion in git_check['suggestions']:
                    print(f"  • {suggestion}")
                
                continue_anyway = self.validator.get_yes_no_input(
                    "\n仍要繼續推送嗎？(可能會失敗)", False
                )
                if not continue_anyway:
                    push_to_gerrit = False
                    print("✅ 已取消 Gerrit 推送，僅執行轉換")
            else:
                print(f"\n✅ Git 設定檢查通過")
                for check in git_check['checks']:
                    print(f"  ✓ {check}")
        
        return push_to_gerrit
    
    def _check_git_requirements(self):
        """檢查 Git 環境需求"""
        result = {
            'valid': True,
            'issues': [],
            'suggestions': [],
            'checks': []
        }
        
        try:
            # 檢查 Git 是否安裝
            try:
                git_version = subprocess.run(['git', '--version'], capture_output=True, text=True, timeout=5)
                if git_version.returncode == 0:
                    result['checks'].append(f"Git 已安裝: {git_version.stdout.strip()}")
                else:
                    result['valid'] = False
                    result['issues'].append("Git 未安裝或無法執行")
                    result['suggestions'].append("請安裝 Git: https://git-scm.com/")
            except (subprocess.TimeoutExpired, FileNotFoundError):
                result['valid'] = False
                result['issues'].append("Git 未安裝或無法執行")
                result['suggestions'].append("請安裝 Git: https://git-scm.com/")
                return result
            
            # 檢查 Git 用戶設定
            try:
                user_name = subprocess.run(['git', 'config', '--global', 'user.name'], 
                                        capture_output=True, text=True, timeout=5)
                user_email = subprocess.run(['git', 'config', '--global', 'user.email'], 
                                        capture_output=True, text=True, timeout=5)
                
                if user_name.returncode == 0 and user_name.stdout.strip():
                    result['checks'].append(f"Git 用戶名: {user_name.stdout.strip()}")
                else:
                    result['issues'].append("Git 用戶名未設定")
                    result['suggestions'].append("執行: git config --global user.name 'Your Name'")
                
                if user_email.returncode == 0 and user_email.stdout.strip():
                    result['checks'].append(f"Git 郵箱: {user_email.stdout.strip()}")
                else:
                    result['issues'].append("Git 郵箱未設定")
                    result['suggestions'].append("執行: git config --global user.email 'your@email.com'")
                    
            except subprocess.TimeoutExpired:
                result['issues'].append("Git 設定檢查逾時")
            
            # 如果有任何 issues，標記為無效
            if result['issues']:
                result['valid'] = False
            
        except Exception as e:
            result['valid'] = False
            result['issues'].append(f"Git 檢查過程發生錯誤: {str(e)}")
        
        return result
    
    def _show_feature_three_parameters(self, overwrite_type, output_folder, excel_filename, push_to_gerrit):
        """顯示功能三參數"""
        print(f"\n📋 處理參數:")
        print(f"  轉換類型: {overwrite_type}")
        print(f"  輸出資料夾: {output_folder}")
        print(f"  Excel 檔名: {excel_filename or '使用預設'}")
        print(f"  推送到 Gerrit: {'✅ 是' if push_to_gerrit else '❌ 否'}")
    
    def _show_processing_flow(self, overwrite_type, push_to_gerrit):
        """顯示處理流程"""
        print(f"\n📄 處理流程:")
        if overwrite_type == 'master_to_premp':
            print(f"  1. 從 Gerrit 下載: atv-google-refplus.xml")
            print(f"  2. 轉換 revision: master → premp.google-refplus")
            print(f"  3. 輸出檔案: atv-google-refplus-premp.xml")
            print(f"  4. 與 Gerrit 上的 atv-google-refplus-premp.xml 比較差異")
        elif overwrite_type == 'premp_to_mp':
            print(f"  1. 從 Gerrit 下載: atv-google-refplus-premp.xml")
            print(f"  2. 轉換 revision: premp.google-refplus → mp.google-refplus.wave")
            print(f"  3. 輸出檔案: atv-google-refplus-wave.xml")
            print(f"  4. 與 Gerrit 上的 atv-google-refplus-wave.xml 比較差異")
        elif overwrite_type == 'mp_to_mpbackup':
            print(f"  1. 從 Gerrit 下載: atv-google-refplus-wave.xml")
            print(f"  2. 轉換 revision: mp.google-refplus.wave → mp.google-refplus.wave.backup")
            print(f"  3. 輸出檔案: atv-google-refplus-wave-backup.xml")
            print(f"  4. 與 Gerrit 上的 atv-google-refplus-wave-backup.xml 比較差異")
        
        if push_to_gerrit:
            print(f"  5. 🚀 推送到 Gerrit (如需要)")
            print(f"     • Git clone ssh://mm2sd.rtkbf.com:29418/realtek/android/manifest")
            print(f"     • Git commit & push to refs/for/realtek/android-14/master")
            print(f"     • 建立 Code Review")
    
    def _show_feature_three_results(self, output_folder, push_to_gerrit):
        """顯示功能三結果"""
        print(f"📁 結果檔案位於: {output_folder}")
        print(f"📊 詳細報告請查看 Excel 檔案")
        
        print(f"\n📋 處理結果:")
        print(f"  ✅ 已從 Gerrit 下載源檔案")
        print(f"  ✅ 已完成 revision 轉換")
        print(f"  ✅ 已保存轉換後檔案")
        print(f"  ✅ 已嘗試下載目標檔案進行比較")
        print(f"  ✅ 已產生詳細分析報告")
        
        if push_to_gerrit:
            print(f"  🚀 已執行 Gerrit 推送流程")
            print(f"     查看 Excel 報告中的推送結果和 Review URL")
        
        print(f"\n💡 提示:")
        print(f"  📄 查看 '轉換摘要' 頁籤了解整體情況")
        print(f"  📋 查看 '轉換後專案' 頁籤檢視所有專案")
        if push_to_gerrit:
            print(f"  🚀 查看推送狀態和 Gerrit Review URL")
    
    def _show_feature_three_troubleshooting(self):
        """顯示功能三故障排除"""
        print(f"💡 故障排除:")
        print(f"  1. 檢查網路連線")
        print(f"  2. 確認 Gerrit 認證設定")
        print(f"  3. 檢查輸出資料夾權限")
        print(f"  4. 查看 Excel 錯誤報告了解詳細原因")


class MainApplication:
    def __init__(self):
        self.logger = logger
        
        # 🔧 添加 excel_handler（如果還沒有）
        try:
            from excel_handler import ExcelHandler
            self.excel_handler = ExcelHandler()
        except ImportError:
            self.excel_handler = None
            print("⚠️ 無法載入 ExcelHandler，將使用簡化格式")
        
        # 初始化功能模組
        self.feature_one = FeatureOne()
        self.feature_two = FeatureTwo()
        self.feature_three = FeatureThree()
        
        # 初始化管理模組
        self.menu_manager = MenuManager()
        self.input_validator = InputValidator()
        self.system_manager = SystemManager()
        self.feature_manager = FeatureManager(
            self.feature_one, self.feature_two, self.feature_three
        )
        
        # 初始化系統設定
        self._setup_system()
    
    def _setup_system(self):
        """初始化系統設定"""
        try:
            success = utils.setup_config()
            if success:
                self.logger.info("系統設定載入成功")
            else:
                self.logger.warning("系統設定載入失敗，使用預設值")
        except Exception as e:
            self.logger.error(f"系統設定初始化錯誤: {str(e)}")
    
    def run(self):
        """執行主程式"""
        try:
            self.logger.info("系統啟動")
            
            while True:
                self.menu_manager.show_main_menu()
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
                    self.feature_manager.execute_feature_one()
                elif choice in ['2-1', '21']:
                    self.feature_manager.execute_feature_two()
                elif choice in ['3-1', '31']:
                    self.feature_manager.execute_feature_three()
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
            self.menu_manager.show_chip_mapping_menu()
            choice = input("請選擇功能: ").strip()
            
            if choice == '0':
                break
            elif choice == '1':
                self.feature_manager.execute_feature_one()
            else:
                print(f"❌ 無效的選項: {choice}")
                input("按 Enter 繼續...")
    
    def _branch_management_menu(self):
        """分支管理工具選單"""
        while True:
            self.menu_manager.show_branch_management_menu()
            choice = input("請選擇功能: ").strip()
            
            if choice == '0':
                break
            elif choice == '1':
                self.feature_manager.execute_feature_two()
            else:
                print(f"❌ 無效的選項: {choice}")
                input("按 Enter 繼續...")
    
    def _manifest_tools_menu(self):
        """Manifest 處理工具選單"""
        while True:
            self.menu_manager.show_manifest_tools_menu()
            choice = input("請選擇功能: ").strip()
            
            if choice == '0':
                break
            elif choice == '1':
                self.feature_manager.execute_feature_three()
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
            self.menu_manager.show_system_tools_menu()
            choice = input("請選擇功能: ").strip()
            
            if choice == '0':
                break
            elif choice == '1':
                self.system_manager.test_jira_connection()
                input("\n按 Enter 繼續...")
            elif choice == '2':
                self.system_manager.test_gerrit_connection()
                input("\n按 Enter 繼續...")
            elif choice == '3':
                self._system_settings_menu()
            elif choice == '4':
                self.system_manager.diagnose_connection_issues()
                input("\n按 Enter 繼續...")
            else:
                print(f"❌ 無效的選項: {choice}")
                input("按 Enter 繼續...")
    
    def _system_settings_menu(self):
        """系統設定選單"""
        while True:
            self.menu_manager.show_system_settings_menu()
            choice = input("請選擇功能: ").strip()
            
            if choice == '0':
                break
            elif choice == '1':
                self.system_manager.view_current_settings()
                input("\n按 Enter 繼續...")
            elif choice == '2':
                self.system_manager.reset_all_settings()
                input("\n按 Enter 繼續...")
            else:
                print(f"❌ 無效的選項: {choice}")
                input("按 Enter 繼續...")
    
    def _confirm_exit(self):
        """確認離開"""
        if self.input_validator.get_yes_no_input("確定要離開程式嗎？", False):
            return
        else:
            print("繼續使用程式...")
    
    def _compare_manifest_diff(self):
        """比較 manifest 差異 - 完全重新設計的選單和邏輯"""
        print("\n" + "="*60)
        print("  📄 比較 Manifest 差異")
        print("="*60)
        print("功能說明：本地檔案與 Gerrit manifest 或本地檔案間的比較")
        print("🔧 使用邏輯：完全基於 feature_three.py（不執行轉換，純比對）")
        print("📋 Excel 格式：與 feature_three.py 完全一致")
        
        try:
            # 顯示新的選單選項
            choice = self._get_compare_mode_new()
            if choice == '0':
                return
            
            # 根據選擇執行不同的比較模式
            if choice in ['1', '2', '3', '4']:
                # 本地檔案與 Gerrit 比較
                self._execute_local_vs_gerrit_comparison(choice)
            elif choice == '5':
                # 本地檔案比較
                self._execute_local_files_comparison()
            else:
                print("❌ 無效的選項")
                return
            
        except Exception as e:
            print(f"\n❌ 比較過程發生錯誤: {str(e)}")
            import traceback
            self.logger.error(f"比較 manifest 差異失敗: {str(e)}")
            self.logger.debug(f"錯誤詳情:\n{traceback.format_exc()}")
        
        input("\n按 Enter 繼續...")

    def _execute_local_files_comparison(self):
        """執行本地檔案比較"""
        print(f"\n📋 本地檔案比較")
        print("="*50)
        print("💡 提示：可以選擇任意兩個 manifest.xml 檔案進行比較")
        print("🔧 處理引擎：ManifestComparator（基於 feature_three.py 邏輯）")
        print("📄 處理模式：純比對（不執行轉換）")
        
        # 選擇第一個檔案
        file1 = self.input_validator.get_input_file("請輸入第一個 manifest.xml 檔案路徑")
        if not file1:
            return
        
        print(f"✅ 已選擇第一個檔案: {os.path.basename(file1)}")
        
        # 選擇第二個檔案
        file2 = self.input_validator.get_input_file("請輸入第二個 manifest.xml 檔案路徑")
        if not file2:
            return
        
        print(f"✅ 已選擇第二個檔案: {os.path.basename(file2)}")
        
        # 取得輸出資料夾和檔案名
        output_folder = self.input_validator.get_output_folder("請輸入輸出資料夾路徑")
        output_file = "local_files_comparison.xlsx"
        output_path = os.path.join(output_folder, output_file)
        
        # 確認檔案選擇
        print(f"\n📋 檔案比較配對:")
        print(f"  📄 檔案1: {os.path.basename(file1)}")
        print(f"     → 將處理為: local_{os.path.basename(file1)}")
        print(f"  📄 檔案2: {os.path.basename(file2)}")
        print(f"     → 將處理為: local_{os.path.basename(file2)}")
        print(f"  📊 輸出報告: {output_file}")
        print(f"  🔧 比較引擎: ManifestComparator（feature_three.py 邏輯）")
        print(f"  📄 處理模式: 純比對（不執行轉換）")
        
        if not self.input_validator.get_yes_no_input("確認使用這兩個檔案進行比較？", True):
            print("❌ 已取消比較")
            return
        
        print(f"\n📄 開始比較分析...")
        
        # 使用新的 ManifestComparator
        import sys
        manifest_compare_path = os.path.join(os.path.dirname(__file__), 'manifest_compare')
        if manifest_compare_path not in sys.path:
            sys.path.insert(0, manifest_compare_path)
        
        from manifest_conversion import ManifestComparator
        
        comparator = ManifestComparator()
        success = comparator.compare_local_files(file1, file2, output_path)
        
        # 顯示結果
        self._show_local_files_results(comparator, success, output_path)

    def _show_local_files_results(self, comparator, success, output_path):
        """顯示本地檔案比較結果"""
        print("\n" + "="*60)
        print(f"📊 本地檔案比較結果摘要")
        print("="*60)
        
        print(f"📈 處理說明:")
        print(f"  🔧 使用邏輯: 完全基於 feature_three.py")
        print(f"  📄 處理模式: 純比對（不執行轉換）")
        print(f"  📊 差異分析: 使用 feature_three._analyze_differences()")
        print(f"  📋 Excel 生成: 使用 feature_three._generate_excel_report_safe()")
        print(f"  🗂️ 檔案處理: 保留使用者原始檔案名稱")
        print(f"  📄 特殊處理: 已移除 '轉換後的 manifest' 頁籤（比較模式不需要）")
        print(f"  🔥 未轉換專案: 改進的原因判斷（區分 hash 和非 hash revision）")
        
        # 顯示結果
        if success:
            print(f"\n✅ 本地檔案比較完成！")
            print(f"📄 所有處理步驟成功執行")
        else:
            print(f"\n❌ 本地檔案比較過程中發生問題")
            print(f"📄 請查看詳細報告了解具體情況")
        
        print(f"\n📊 詳細分析報告: {output_path}")
        print(f"💡 Excel 報告頁籤（比較模式優化）:")
        print(f"  📋 轉換摘要 - 整體統計和檔案資訊")
        print(f"  🔍 轉換後專案 - 所有專案的比較狀態")
        print(f"  ❌ 轉換後與 Gerrit manifest 的差異 - 詳細差異對照")
        print(f"  📄 未轉換專案 - 區分 hash 和非 hash revision 的原因說明")
        print(f"  📄 來源的 manifest - 保留原始檔案名稱")
        print(f"  📄 gerrit 上的 manifest - 正確的檔案名稱")
        print(f"  🚫 已移除: '轉換後的 manifest'（比較模式不需要）")
        
        # 詢問是否開啟報告
        if self.input_validator.get_yes_no_input("\n是否要開啟比較報告？", False):
            self._open_file(output_path)

    def _execute_local_vs_gerrit_comparison(self, choice):
        """執行本地檔案與 Gerrit 比較"""
        # 映射選擇到 Gerrit 類型
        gerrit_type_mapping = {
            '1': ('master', 'Master'),
            '2': ('premp', 'PreMP'),
            '3': ('mp', 'MP'),
            '4': ('mp_backup', 'MP Backup')
        }
        
        gerrit_type, gerrit_name = gerrit_type_mapping[choice]
        
        print(f"\n📋 本地檔案與 {gerrit_name} 比較")
        print("="*50)
        
        # 取得本地檔案
        local_file = self.input_validator.get_input_file(f"請輸入本地 manifest.xml 檔案路徑")
        if not local_file:
            return
        
        # 取得輸出資料夾和檔案名
        output_folder = self.input_validator.get_output_folder("請輸入輸出資料夾路徑")
        output_file = f"local_vs_{gerrit_type}_comparison.xlsx"
        output_path = os.path.join(output_folder, output_file)
        
        print(f"\n📋 比較參數:")
        print(f"  本地檔案: {os.path.basename(local_file)}")
        print(f"  Gerrit 類型: {gerrit_name}")
        print(f"  輸出報告: {output_file}")
        print(f"  報告路徑: {output_path}")
        print(f"  🔧 比較引擎: ManifestComparator（基於 feature_three.py）")
        print(f"  📄 處理模式: 純比對（不執行轉換）")
        print(f"  🗂️ 檔案處理: 自動下載並保存 Gerrit 檔案（gerrit_ 前綴）")
        print(f"  🔍 include 處理: 自動檢測 Gerrit 檔案並展開")
        
        if not self.input_validator.confirm_execution():
            return
        
        print(f"\n📄 開始比較分析...")
        print(f"⬇️ 正在從 Gerrit 下載 {gerrit_name} manifest...")
        
        # 使用新的 ManifestComparator
        import sys
        manifest_compare_path = os.path.join(os.path.dirname(__file__), 'manifest_compare')
        if manifest_compare_path not in sys.path:
            sys.path.insert(0, manifest_compare_path)
        
        from manifest_conversion import ManifestComparator
        
        comparator = ManifestComparator()
        success = comparator.compare_local_with_gerrit(local_file, gerrit_type, output_path)
        
        # 顯示結果
        self._show_local_vs_gerrit_results(comparator, success, output_path, gerrit_name)

    def _get_compare_mode_new(self):
        """取得新的比較模式選擇"""
        print("\n請選擇比較模式:")
        print("  [1] 本地檔案與 Master 比較 (自動下載 Master)")
        print("      從 Gerrit 自動下載 Master 和本地檔案進行比較")
        print("      測試本地檔案與 Master 是否相等")
        print()
        print("  [2] 本地檔案與 PreMP 比較 (自動下載 PreMP)")
        print("      從 Gerrit 自動下載 PreMP 和本地檔案進行比較")
        print("      測試本地檔案與 PreMP 是否相等")
        print()
        print("  [3] 本地檔案與 MP 比較 (自動下載 MP)")
        print("      從 Gerrit 自動下載 MP 和本地檔案進行比較")
        print("      測試本地檔案與 MP 是否相等")
        print()
        print("  [4] 本地檔案與 MP Backup 比較 (自動下載 MP Backup)")
        print("      從 Gerrit 自動下載 MP Backup 和本地檔案進行比較")
        print("      測試本地檔案與 MP Backup 是否相等")
        print()
        print("  [5] 使用本地檔案比較")
        print("      選擇任意兩個本地 manifest 檔案進行比較")
        print("      不限定特定類型，可用於自定義比較")
        print()
        print("  [0] 返回上層選單")
        
        return input("\n請選擇 (1-5): ").strip()

    def _show_local_vs_gerrit_results(self, comparator, success, output_path, gerrit_name):
        """顯示本地檔案與 Gerrit 比較結果"""
        print("\n" + "="*60)
        print(f"📊 本地檔案與 {gerrit_name} 比較結果摘要")
        print("="*60)
        
        print(f"📈 處理說明:")
        print(f"  🔧 使用邏輯: 完全基於 feature_three.py")
        print(f"  📄 處理模式: 純比對（不執行轉換）")
        print(f"  📊 差異分析: 使用 feature_three._analyze_differences()")
        print(f"  📋 Excel 生成: 使用 feature_three._generate_excel_report_safe()")
        print(f"  🗂️ 檔案處理: 自動下載並保存 Gerrit 檔案")
        print(f"  📄 特殊處理: 已移除 '轉換後的 manifest' 頁籤（比較模式不需要）")
        print(f"  🔥 檔案命名: 保留使用者原始檔案名稱")
        
        if hasattr(comparator, 'use_expanded') and comparator.use_expanded:
            print(f"  ✅ include 展開: 已成功展開 Gerrit 檔案")
            if hasattr(comparator, 'expanded_file_path') and comparator.expanded_file_path:
                print(f"  📄 展開檔案: {os.path.basename(comparator.expanded_file_path)}")
        else:
            print(f"  ℹ️ include 展開: 未檢測到 include 標籤或展開失敗")
        
        # 顯示結果
        if success:
            print(f"\n✅ 本地檔案與 {gerrit_name} 比較完成！")
            print(f"📄 所有處理步驟成功執行")
        else:
            print(f"\n❌ 本地檔案與 {gerrit_name} 比較過程中發生問題")
            print(f"📄 請查看詳細報告了解具體情況")
        
        print(f"\n📊 詳細分析報告: {output_path}")
        print(f"💡 Excel 報告頁籤（比較模式優化）:")
        print(f"  📋 轉換摘要 - 整體統計和檔案資訊")
        print(f"  🔍 轉換後專案 - 所有專案的比較狀態（含 hash 判斷）")
        print(f"  ❌ 轉換後與 Gerrit manifest 的差異 - 詳細差異對照")
        print(f"  📄 未轉換專案 - 改進的原因判斷（區分 hash 和非 hash）")
        print(f"  📄 來源的 manifest - 保留原始檔案名稱")
        print(f"  📄 gerrit 上的 manifest - 正確的 Gerrit 檔案名稱")
        print(f"  🚫 已移除: '轉換後的 manifest'（比較模式不需要）")
        
        # 詢問是否開啟報告
        if self.input_validator.get_yes_no_input("\n是否要開啟比較報告？", False):
            self._open_file(output_path)

    def _get_local_manifest_files(self):
        """取得本地 manifest 檔案 - 更新版本，不限定檔案類型"""
        print("\n📁 請選擇本地 manifest 檔案...")
        print("💡 提示：可以選擇任意兩個 manifest.xml 檔案進行比較")
        
        # 選擇第一個檔案
        file1 = self.input_validator.get_input_file("請輸入第一個 manifest.xml 檔案路徑")
        if not file1:
            return None, None
        
        print(f"✅ 已選擇第一個檔案: {os.path.basename(file1)}")
        
        # 選擇第二個檔案
        file2 = self.input_validator.get_input_file("請輸入第二個 manifest.xml 檔案路徑")
        if not file2:
            return None, None
        
        print(f"✅ 已選擇第二個檔案: {os.path.basename(file2)}")
        
        # 確認檔案選擇
        print(f"\n📋 檔案比較配對:")
        print(f"  📄 檔案1: {os.path.basename(file1)}")
        print(f"  📄 檔案2: {os.path.basename(file2)}")
        
        if not self.input_validator.get_yes_no_input("確認使用這兩個檔案進行比較？", True):
            print("❌ 已取消比較")
            return None, None
        
        return file1, file2
            
    def _download_gerrit_manifest(self):
        """下載 Gerrit manifest - 修正版"""
        print("\n" + "="*60)
        print("  ⬇️ 下載 Gerrit Manifest")
        print("="*60)
        print("功能說明：從 Gerrit 伺服器下載不同類型的 manifest 檔案")
        
        try:
            # 定義下載類型和對應的資訊
            download_types = self._get_download_types()
            
            while True:
                choice = self._show_download_options()
                
                if choice == '0':
                    return
                elif choice == '5':
                    self._download_custom_url()
                    continue
                elif choice == '6':
                    self._open_gerrit_browser()
                    continue
                elif choice in download_types:
                    download_info = download_types[choice]
                    break
                else:
                    print("❌ 無效的選項，請重新選擇")
            
            # 執行下載
            self._execute_download(download_info)
            
        except Exception as e:
            print(f"\n❌ 下載過程發生錯誤: {str(e)}")
            import traceback
            self.logger.error(f"下載 Gerrit manifest 失敗: {str(e)}")
            self.logger.debug(f"錯誤詳情:\n{traceback.format_exc()}")
        
        input("\n按 Enter 繼續...")
    
    # 輔助方法實作
    def _get_compare_mode(self):
        """取得比較模式選擇 - 更新版本"""
        print("\n請選擇比較模式:")
        print("  [1] 自動下載並比較 (Master vs PreMP)")
        print("      從 Gerrit 自動下載 Master 和 PreMP manifest 進行比較")
        print("      測試 master_to_premp 轉換規則正確性")
        print()
        print("  [2] 自動下載並比較 (PreMP vs MP)")
        print("      從 Gerrit 自動下載 PreMP 和 MP manifest 進行比較")
        print("      測試 premp_to_mp 轉換規則正確性")
        print()
        print("  [3] 自動下載並比較 (MP vs MP Backup)")
        print("      從 Gerrit 自動下載 MP 和 MP Backup manifest 進行比較")
        print("      測試 mp_to_mpbackup 轉換規則正確性")
        print()
        print("  [4] 使用本地檔案比較")
        print("      選擇任意兩個本地 manifest 檔案進行比較")
        print("      不限定特定類型，可用於自定義比較")
        print()
        print("  [0] 返回上層選單")
        
        return input("\n請選擇 (1-4): ").strip()
    
    def _auto_download_manifests(self, temp_dir, comparison_type):
        """自動下載 manifest 檔案 - 🔥 特別處理 master_vs_premp 的 include 展開"""
        print(f"\n📄 從 Gerrit 自動下載 manifest 檔案...")
        
        from gerrit_manager import GerritManager
        gerrit = GerritManager()
        
        # 定義不同比較類型的檔案配置
        comparison_configs = {
            'master_vs_premp': {
                'file1': {
                    'name': 'Master',
                    'filename': 'atv-google-refplus.xml',
                    'url': 'https://mm2sd.rtkbf.com/gerrit/plugins/gitiles/realtek/android/manifest/+/refs/heads/realtek/android-14/master/atv-google-refplus.xml',
                    'local_name': 'master_manifest.xml',
                    'need_expand_check': True  # 🔥 標記需要檢查 include
                },
                'file2': {
                    'name': 'PreMP',
                    'filename': 'atv-google-refplus-premp.xml',
                    'url': 'https://mm2sd.rtkbf.com/gerrit/plugins/gitiles/realtek/android/manifest/+/refs/heads/realtek/android-14/master/atv-google-refplus-premp.xml',
                    'local_name': 'premp_manifest.xml',
                    'need_expand_check': False
                }
            },
            'premp_vs_mp': {
                'file1': {
                    'name': 'PreMP',
                    'filename': 'atv-google-refplus-premp.xml',
                    'url': 'https://mm2sd.rtkbf.com/gerrit/plugins/gitiles/realtek/android/manifest/+/refs/heads/realtek/android-14/master/atv-google-refplus-premp.xml',
                    'local_name': 'premp_manifest.xml',
                    'need_expand_check': False
                },
                'file2': {
                    'name': 'MP Wave',
                    'filename': 'atv-google-refplus-wave.xml',
                    'url': 'https://mm2sd.rtkbf.com/gerrit/plugins/gitiles/realtek/android/manifest/+/refs/heads/realtek/android-14/master/atv-google-refplus-wave.xml',
                    'local_name': 'mp_manifest.xml',
                    'need_expand_check': False
                }
            },
            'mp_vs_mpbackup': {
                'file1': {
                    'name': 'MP Wave',
                    'filename': 'atv-google-refplus-wave.xml',
                    'url': 'https://mm2sd.rtkbf.com/gerrit/plugins/gitiles/realtek/android/manifest/+/refs/heads/realtek/android-14/master/atv-google-refplus-wave.xml',
                    'local_name': 'mp_manifest.xml',
                    'need_expand_check': False
                },
                'file2': {
                    'name': 'MP Backup',
                    'filename': 'atv-google-refplus-wave-backup.xml',
                    'url': 'https://mm2sd.rtkbf.com/gerrit/plugins/gitiles/realtek/android/manifest/+/refs/heads/realtek/android-14/master/atv-google-refplus-wave-backup.xml',
                    'local_name': 'mp_backup_manifest.xml',
                    'need_expand_check': False
                }
            }
        }
        
        if comparison_type not in comparison_configs:
            print(f"❌ 不支援的比較類型: {comparison_type}")
            return None, None
        
        config = comparison_configs[comparison_type]
        
        # 下載第一個檔案
        file1_config = config['file1']
        file1_path = os.path.join(temp_dir, file1_config['local_name'])
        
        print(f"⬇️ 正在下載 {file1_config['name']} manifest...")
        print(f"   檔案: {file1_config['filename']}")
        
        if not gerrit.download_file_from_link(file1_config['url'], file1_path):
            print(f"❌ 下載 {file1_config['name']} manifest 失敗")
            return None, None
        print(f"✅ {file1_config['name']} manifest 下載完成")
        
        # 🔥 特殊處理：檢查第一個檔案是否需要展開（主要針對 master_vs_premp）
        if file1_config.get('need_expand_check', False):
            print(f"🔍 檢查 {file1_config['name']} manifest 是否包含 include 標籤...")
            
            try:
                with open(file1_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # 使用 feature_three 的邏輯檢查 include 標籤
                from overwrite_lib.feature_three import FeatureThree
                feature_three = FeatureThree()
                
                if feature_three._has_include_tags(content):
                    print(f"📄 檢測到 include 標籤，比較工具會自動處理展開")
                    print(f"💡 ManifestComparator 會在比較時自動展開 include")
                else:
                    print(f"ℹ️ 未檢測到 include 標籤，使用原始檔案")
            except Exception as e:
                print(f"⚠️ 檢查 include 標籤時發生錯誤: {str(e)}")
                print(f"⚠️ 將繼續使用原始檔案進行比較")
        
        # 下載第二個檔案
        file2_config = config['file2']
        file2_path = os.path.join(temp_dir, file2_config['local_name'])
        
        print(f"⬇️ 正在下載 {file2_config['name']} manifest...")
        print(f"   檔案: {file2_config['filename']}")
        
        if not gerrit.download_file_from_link(file2_config['url'], file2_path):
            print(f"❌ 下載 {file2_config['name']} manifest 失敗")
            # 如果第二個檔案下載失敗，但第一個成功，可以選擇繼續或停止
            choice = input(f"\n⚠️ {file2_config['name']} manifest 下載失敗，是否繼續？(y/N): ").strip().lower()
            if choice != 'y':
                return None, None
            else:
                print(f"⚠️ 將跳過 {file2_config['name']} manifest 的比較")
                return file1_path, None
        print(f"✅ {file2_config['name']} manifest 下載完成")
        
        # 顯示下載總結
        print(f"\n📊 下載總結:")
        print(f"  📄 {file1_config['name']}: {os.path.basename(file1_path)}")
        if file1_config.get('need_expand_check', False):
            print(f"    💡 將由 ManifestComparator 自動處理 include 展開")
        print(f"  📄 {file2_config['name']}: {os.path.basename(file2_path)}")
        print(f"  📁 位置: {temp_dir}")
        print(f"  🔧 比較引擎: ManifestComparator（基於 feature_three.py）")
        
        return file1_path, file2_path
    
    def _perform_manifest_comparison(self, file1, file2, comparison_type=None):
        """
        執行 manifest 比較分析 - 🔥 完全使用新的 ManifestComparator（基於 feature_three.py）
        """
        from datetime import datetime
        
        # 處理其中一個檔案為 None 的情況
        if not file1:
            print("❌ 第一個檔案無效，無法進行比較")
            return
        
        if not file2:
            print("⚠️ 第二個檔案無效，將只分析第一個檔案")
            return
        
        # 如果沒有傳入比較類型，才進行檢測
        if not comparison_type:
            comparison_type = self._detect_comparison_type(file1, file2)
        
        # 生成輸出檔案名稱 - 使用新的命名規則
        output_file_mapping = {
            'master_vs_premp': 'auto_master_vs_premp_manifest_compare.xlsx',
            'premp_vs_mp': 'auto_premp_vs_mp_manifest_compare.xlsx',
            'mp_vs_mpbackup': 'auto_mp_vs_mpbackup_manifest_compare.xlsx',
            'custom': 'custom_manifest_compare.xlsx'
        }
        
        output_file = output_file_mapping.get(comparison_type, 'custom_manifest_compare.xlsx')
        
        # 取得輸出資料夾
        output_folder = self.input_validator.get_output_folder("請輸入輸出資料夾路徑")
        output_path = os.path.join(output_folder, output_file)
        
        print(f"\n📋 比較參數:")
        print(f"  檔案1: {os.path.basename(file1)}")
        print(f"  檔案2: {os.path.basename(file2)}")
        print(f"  比較類型: {comparison_type or '自定義比較'}")
        print(f"  輸出報告: {output_file}")
        print(f"  報告路徑: {output_path}")
        
        if not self.input_validator.confirm_execution():
            return
        
        print("\n📄 開始比較分析...")
        
        # 🔥 使用新的 ManifestComparator（基於 feature_three.py）
        import sys
        manifest_compare_path = os.path.join(os.path.dirname(__file__), 'manifest_compare')
        if manifest_compare_path not in sys.path:
            sys.path.insert(0, manifest_compare_path)
        
        from manifest_conversion import ManifestComparator
        
        # 🔥 使用新的 ManifestComparator，完全基於 feature_three.py 邏輯
        comparator = ManifestComparator()
        success = comparator.compare_manifests(file1, file2, output_path, comparison_type)
        
        # 顯示結果
        self._show_unified_comparison_results(comparator, success, output_path, comparison_type)

    def _show_unified_comparison_results(self, comparator, success, output_path, comparison_type):
        """🔥 顯示統一格式的比較結果（使用 ManifestComparator 的統計）"""
        print("\n" + "="*60)
        print(f"📊 {comparison_type} 比較結果摘要（基於 feature_three.py 邏輯）")
        print("="*60)
        
        # 顯示基本資訊
        source_name, target_name = self._get_comparison_names_for_display(comparison_type)
        
        print(f"📈 比較說明:")
        print(f"  🔧 使用邏輯: 完全基於 feature_three.py")
        print(f"  📋 Excel 格式: 與 feature_three.py 完全一致")
        
        if comparison_type == 'master_vs_premp':
            print(f"  🔍 特殊處理: 自動檢測並展開 include 標籤")
            print(f"  📄 展開邏輯: 使用 feature_three._expand_manifest_with_repo_fixed()")
        
        print(f"  📊 比較對象: {source_name} vs {target_name}")
        
        # 顯示結果
        if success:
            print(f"\n✅ {comparison_type} 比較完成！")
            print(f"📄 所有比較處理成功")
        else:
            print(f"\n❌ {comparison_type} 比較過程中發生問題")
            print(f"📄 請查看詳細報告了解具體情況")
        
        print(f"\n📊 詳細分析報告: {output_path}")
        print(f"💡 報告頁籤說明:")
        print(f"  📋 轉換摘要 - 整體統計和設定資訊")
        print(f"  🔍 轉換後專案 - 所有專案的比較狀態")
        print(f"  ❌ 轉換後與 Gerrit manifest 的差異 - 詳細差異對照")
        print(f"  📄 其他頁籤 - 依據 feature_three.py 格式")
        
        # 詢問是否開啟報告
        if self.input_validator.get_yes_no_input("\n是否要開啟比較報告？", False):
            self._open_file(output_path)

    def _get_comparison_names_for_display(self, comparison_type):
        """取得用於顯示的比較名稱"""
        mapping = {
            'master_vs_premp': ('Master', 'PreMP'),
            'premp_vs_mp': ('PreMP', 'MP'),
            'mp_vs_mpbackup': ('MP', 'MP Backup'),
            'custom': ('檔案1', '檔案2')
        }
        return mapping.get(comparison_type, ('源檔案', '目標檔案'))
        
    def _show_generic_comparison_results(self, success, output_path, comparison_type):
        """顯示通用比較結果"""
        print("\n" + "="*60)
        print("📊 比較結果摘要")
        print("="*60)
        
        if success:
            print(f"✅ {comparison_type} 比較完成！")
        else:
            print(f"❌ {comparison_type} 比較失敗")
        
        print(f"\n📊 詳細分析報告: {output_path}")
        
        # 詢問是否開啟報告
        if self.input_validator.get_yes_no_input("\n是否要開啟比較報告？", False):
            self._open_file(output_path)

    def _detect_comparison_type(self, file1, file2):
        """檢測比較類型"""
        file1_name = os.path.basename(file1).lower()
        file2_name = os.path.basename(file2).lower()
        
        # 檢測檔案名稱模式
        if ('master' in file1_name or 'atv-google-refplus.xml' == file1_name) and 'premp' in file2_name:
            return 'master_vs_premp'
        elif 'premp' in file1_name and ('wave.xml' in file2_name and 'backup' not in file2_name):
            return 'premp_vs_mp'
        elif ('wave.xml' in file1_name and 'backup' not in file1_name) and 'backup' in file2_name:
            return 'mp_vs_mpbackup'
        else:
            return 'custom'

    def _format_generic_comparison_sheet(self, worksheet, colors):
        """格式化通用比較頁籤"""
        for row in range(2, worksheet.max_row + 1):
            # 找到狀態相關欄位
            status_cell = None
            result_cell = None
            
            for col in range(1, worksheet.max_column + 1):
                header = worksheet.cell(row=1, column=col).value
                if header:
                    header_str = str(header)
                    if '比較狀態' in header_str or '狀態說明' in header_str:
                        status_cell = worksheet.cell(row=row, column=col)
                    elif '結果' in header_str and '圖示' not in header_str:
                        result_cell = worksheet.cell(row=row, column=col)
            
            # 根據狀態設定顏色
            if status_cell and status_cell.value:
                status_value = str(status_cell.value)
                fill_color = None
                
                if '不同' in status_value or '❌' in status_value:
                    fill_color = colors['mismatch']
                elif '相同' in status_value or '✅' in status_value:
                    fill_color = colors['match']
                elif '僅存在於' in status_value or '🔶' in status_value:
                    fill_color = colors['not_found']
                
                # 套用背景色到整行
                if fill_color:
                    for col in range(1, worksheet.max_column + 1):
                        worksheet.cell(row=row, column=col).fill = fill_color

    def _get_comparison_names_for_generic(self, comparison_type):
        """取得通用比較的名稱"""
        mapping = {
            'master_vs_premp': ('Master', 'PreMP'),
            'premp_vs_mp': ('PreMP', 'MP'),
            'mp_vs_mpbackup': ('MP', 'MP Backup'),
            'custom': ('檔案1', '檔案2')
        }
        return mapping.get(comparison_type, ('檔案1', '檔案2'))

    def _show_comparison_results(self, tester, success, output_path):
        """顯示比較結果"""
        print("\n" + "="*60)
        print("📊 比較結果摘要")
        print("="*60)
        
        # 顯示統計結果
        stats = tester.stats
        print(f"📈 轉換統計:")
        print(f"  總專案數: {stats['total_projects']}")
        print(f"  🔵 參與轉換專案: {stats['revision_projects']}")
        print(f"  ⚪ 無revision專案: {stats['no_revision_projects']} (跳過轉換)")
        print(f"  🟢 原始相同專案: {stats['same_revision_projects']} (Master=PreMP)")
        print(f"  🟣 跳過特殊專案: {stats['skipped_special_projects']}")
        print(f"  ✅ 轉換匹配: {stats['matched']}")
        print(f"  ❌ 轉換不匹配: {stats['mismatched']}")
        print(f"  ⚠️ PreMP中不存在: {stats['not_found_in_premp']}")
        print(f"  🔶 僅存在於PreMP: {stats['extra_in_premp']}")
        
        # 計算成功率
        if stats['revision_projects'] > 0:
            success_rate = (stats['matched'] / stats['revision_projects'] * 100)
            print(f"  📊 轉換成功率: {success_rate:.2f}%")
        
        # 顯示結果
        if success:
            print(f"\n✅ 轉換規則測試通過！")
            print(f"📄 所有參與轉換的專案規則都正確")
        else:
            print(f"\n⚠️ 發現轉換差異")
            print(f"📄 請查看詳細報告分析問題")
        
        print(f"\n📊 詳細分析報告: {output_path}")
        
        # 詢問是否開啟報告
        if self.input_validator.get_yes_no_input("\n是否要開啟測試報告？", False):
            self._open_file(output_path)
    
    def _get_download_types(self):
        """取得下載類型定義"""
        return {
            '1': {
                'name': 'Master',
                'filename': 'atv-google-refplus.xml',
                'url': 'https://mm2sd.rtkbf.com/gerrit/plugins/gitiles/realtek/android/manifest/+/refs/heads/realtek/android-14/master/atv-google-refplus.xml',
                'description': '原始 master manifest',
                'need_expand': True
            },
            '2': {
                'name': 'PreMP',
                'filename': 'atv-google-refplus-premp.xml',
                'url': 'https://mm2sd.rtkbf.com/gerrit/plugins/gitiles/realtek/android/manifest/+/refs/heads/realtek/android-14/master/atv-google-refplus-premp.xml',
                'description': 'PreMP 轉換後 manifest',
                'need_expand': False
            },
            '3': {
                'name': 'MP Wave',
                'filename': 'atv-google-refplus-wave.xml',
                'url': 'https://mm2sd.rtkbf.com/gerrit/plugins/gitiles/realtek/android/manifest/+/refs/heads/realtek/android-14/master/atv-google-refplus-wave.xml',
                'description': 'MP Wave manifest',
                'need_expand': False
            },
            '4': {
                'name': 'MP Backup',
                'filename': 'atv-google-refplus-wave-backup.xml',
                'url': 'https://mm2sd.rtkbf.com/gerrit/plugins/gitiles/realtek/android/manifest/+/refs/heads/realtek/android-14/master/atv-google-refplus-wave-backup.xml',
                'description': 'MP Wave Backup manifest',
                'need_expand': False
            }
        }
    
    def _show_download_options(self):
        """顯示下載選項"""
        print("\n請選擇下載類型:")
        print("  [1] Master (atv-google-refplus.xml)")
        print("      ├─ 原始檔案")
        print("      └─ 展開版本 (repo init + repo manifest)")
        print("  [2] PreMP (atv-google-refplus-premp.xml)")
        print("  [3] MP Wave (atv-google-refplus-wave.xml)")
        print("  [4] MP Backup (atv-google-refplus-wave-backup.xml)")
        print("  [5] 自定義 URL 下載")
        print("  [6] 瀏覽 Gerrit 查看可用檔案")
        print("  [0] 返回上層選單")
        
        return input("\n請選擇 (1-6): ").strip()
    
    def _execute_download(self, download_info):
        """執行下載"""
        # 取得輸出資料夾
        output_folder = self.input_validator.get_output_folder("請輸入輸出資料夾路徑", "./downloads")
        
        print(f"\n📋 下載參數:")
        print(f"  類型: {download_info['name']}")
        print(f"  說明: {download_info['description']}")
        print(f"  檔案: {download_info['filename']}")
        print(f"  輸出: {os.path.join(output_folder, download_info['filename'])}")
        if download_info['need_expand']:
            print(f"  特殊處理: 會檢查 include 標籤並使用 repo 展開")
        
        if not self.input_validator.confirm_execution():
            return
        
        print(f"\n📄 開始下載...")
        
        # 執行下載
        from gerrit_manager import GerritManager
        gerrit = GerritManager()
        
        output_file = os.path.join(output_folder, download_info['filename'])
        
        print(f"⬇️ 正在下載 {download_info['name']} manifest...")
        success = gerrit.download_file_from_link(download_info['url'], output_file)
        
        if success:
            print(f"✅ {download_info['name']} manifest 下載完成")
            self._show_download_results(output_file, download_info, output_folder)
        else:
            print(f"❌ 下載失敗")
            self._show_download_troubleshooting()
    
    def _show_download_results(self, output_file, download_info, output_folder):
        """顯示下載結果"""
        print(f"📁 檔案位置: {output_file}")
        
        # 顯示檔案資訊
        self._show_manifest_file_info(output_file)
        
        # 特殊處理：Master 類型需要檢查並展開
        if download_info['need_expand']:
            print(f"\n📄 檢查是否需要展開...")
            expanded_file = self._expand_manifest_default_revision(output_file, output_folder)
            
            if expanded_file:
                print(f"✅ 展開版本產生完成")
                print(f"📁 展開檔案: {expanded_file}")
        
        print(f"\n✅ 下載完成！")
        print(f"📁 所有檔案位於: {output_folder}")
        
        # 詢問是否下載其他類型
        if self.input_validator.get_yes_no_input("\n是否要下載其他類型的 manifest？", False):
            self._download_gerrit_manifest()  # 遞歸調用
    
    def _show_download_troubleshooting(self):
        """顯示下載故障排除"""
        print(f"💡 可能原因:")
        print(f"  1. 網路連線問題")
        print(f"  2. Gerrit 認證設定錯誤")
        print(f"  3. 檔案權限問題")
        print(f"  4. 檔案暫時不可用")
    
    def _show_manifest_file_info(self, file_path: str):
        """顯示 manifest 檔案資訊"""
        try:
            file_size = os.path.getsize(file_path)
            print(f"\n📊 檔案資訊:")
            print(f"  檔案大小: {file_size:,} bytes ({file_size/1024:.1f} KB)")
            
            # 簡單分析 manifest 內容
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                project_count = content.count('<project ')
                default_count = content.count('<default ')
                remote_count = content.count('<remote ')
                
                print(f"  專案數量: {project_count}")
                print(f"  預設設定: {default_count}")
                print(f"  遠端設定: {remote_count}")
                
                # 檢查是否有特殊 revision 格式
                revision_patterns = {
                    'refs/tags/': content.count('refs/tags/'),
                    'realtek/master': content.count('realtek/master'),
                    'premp.google-refplus': content.count('premp.google-refplus'),
                    'mp.google-refplus.wave': content.count('mp.google-refplus.wave'),
                    'mp.google-refplus.wave.backup': content.count('mp.google-refplus.wave.backup'),
                }
                
                print(f"  📋 Revision 分析:")
                for pattern, count in revision_patterns.items():
                    if count > 0:
                        print(f"    {pattern}: {count} 個")
                        
        except Exception as e:
            print(f"⚠️ 無法讀取檔案資訊: {str(e)}")
    
    def _expand_manifest_default_revision(self, input_file: str, output_folder: str) -> Optional[str]:
        """展開 manifest 的 default revision - 正確版本（參考 feature_three.py）"""
        try:
            self.logger.info(f"🔍 檢查是否需要展開 manifest: {input_file}")
            
            # 讀取檔案內容，檢查是否有 include 標籤
            with open(input_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 檢查是否包含 include 標籤
            if not self._has_include_tags(content):
                self.logger.info("ℹ️ 未檢測到 include 標籤，跳過展開處理")
                return None
            
            self.logger.info("🔍 檢測到 include 標籤，開始展開 manifest...")
            
            # 使用 feature_three.py 風格的展開邏輯
            expanded_content, expanded_file_path = self._expand_manifest_with_repo(
                input_file, output_folder
            )
            
            if expanded_content and expanded_file_path:
                self.logger.info(f"✅ Manifest 展開成功: {expanded_file_path}")
                return expanded_file_path
            else:
                self.logger.warning("⚠️ Manifest 展開失敗")
                return None
                
        except Exception as e:
            self.logger.error(f"展開 manifest 失敗: {str(e)}")
            return None
    
    def _has_include_tags(self, xml_content: str) -> bool:
        """檢查 XML 內容是否包含 include 標籤"""
        try:
            import re
            
            # 使用正則表達式檢查 include 標籤
            include_pattern = r'<include\s+name\s*=\s*["\'][^"\']*["\'][^>]*/?>'
            matches = re.findall(include_pattern, xml_content, re.IGNORECASE)
            
            if matches:
                self.logger.info(f"🔍 發現 {len(matches)} 個 include 標籤:")
                for i, match in enumerate(matches, 1):
                    self.logger.info(f"  {i}. {match}")
                return True
            else:
                self.logger.info("ℹ️ 未發現 include 標籤")
                return False
                
        except Exception as e:
            self.logger.error(f"檢查 include 標籤時發生錯誤: {str(e)}")
            return False
    
    def _expand_manifest_with_repo(self, input_file: str, output_folder: str) -> tuple:
        """使用 repo 命令展開包含 include 的 manifest"""
        try:
            # 從輸入檔案名生成展開檔案名
            input_filename = os.path.basename(input_file)
            expanded_filename = input_filename.replace('.xml', '_expand.xml')
            final_expanded_path = os.path.abspath(os.path.join(output_folder, expanded_filename))
            
            # Gerrit 設定
            repo_url = "ssh://mm2sd.rtkbf.com:29418/realtek/android/manifest"
            branch = "realtek/android-14/master"
            
            self.logger.info(f"🎯 準備展開 manifest...")
            self.logger.info(f"🎯 源檔案: {input_filename}")
            self.logger.info(f"🎯 展開檔案名: {expanded_filename}")
            self.logger.info(f"🎯 目標絕對路徑: {final_expanded_path}")
            
            # 確保輸出資料夾存在
            utils.ensure_dir(output_folder)
            
            # 檢查 repo 命令是否可用
            try:
                repo_check = subprocess.run(
                    ["repo", "--version"], 
                    capture_output=True, 
                    text=True, 
                    timeout=10
                )
                if repo_check.returncode == 0:
                    self.logger.info(f"✅ repo 工具可用: {repo_check.stdout.strip()}")
                else:
                    self.logger.error(f"❌ repo 工具檢查失敗: {repo_check.stderr}")
                    return None, None
            except FileNotFoundError:
                self.logger.error("❌ repo 命令未找到，請確認已安裝 repo 工具")
                return None, None
            
            # 建立臨時工作目錄
            temp_work_dir = tempfile.mkdtemp(prefix='repo_expand_')
            original_cwd = os.getcwd()
            
            try:
                # 切換到臨時目錄
                os.chdir(temp_work_dir)
                
                # 步驟 1: repo init
                init_cmd = [
                    "repo", "init", 
                    "-u", repo_url,
                    "-b", branch,
                    "-m", input_filename
                ]
                
                init_result = subprocess.run(
                    init_cmd,
                    capture_output=True,
                    text=True,
                    timeout=120
                )
                
                if init_result.returncode != 0:
                    self.logger.error(f"❌ repo init 失敗")
                    return None, None
                
                # 步驟 2: repo manifest 展開
                manifest_result = subprocess.run(
                    ["repo", "manifest"],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                
                if manifest_result.returncode != 0:
                    self.logger.error(f"❌ repo manifest 失敗")
                    return None, None
                
                expanded_content = manifest_result.stdout
                
                if not expanded_content.strip():
                    self.logger.error("❌ repo manifest 返回空內容")
                    return None, None
                
                # 步驟 3: 保存展開檔案到輸出資料夾
                with open(final_expanded_path, 'w', encoding='utf-8') as f:
                    f.write(expanded_content)
                
                # 驗證檔案是否成功保存
                if os.path.exists(final_expanded_path):
                    file_size = os.path.getsize(final_expanded_path)
                    self.logger.info(f"✅ 展開檔案已成功保存: {final_expanded_path}")
                    self.logger.info(f"✅ 檔案大小: {file_size} bytes")
                    return expanded_content, final_expanded_path
                else:
                    self.logger.error(f"❌ 展開檔案保存失敗")
                    return None, None
                    
            finally:
                # 恢復原始工作目錄
                os.chdir(original_cwd)
                
                # 清理臨時目錄
                try:
                    shutil.rmtree(temp_work_dir)
                except Exception as e:
                    self.logger.warning(f"⚠️ 清理臨時目錄失敗: {str(e)}")
            
        except Exception as e:
            self.logger.error(f"❌ 展開 manifest 時發生錯誤: {str(e)}")
            return None, None
    
    def _download_custom_url(self):
        """自定義 URL 下載"""
        print(f"\n📥 自定義 URL 下載")
        print(f"請輸入完整的 Gerrit manifest URL")
        print(f"範例: https://mm2sd.rtkbf.com/gerrit/plugins/gitiles/realtek/android/manifest/+/refs/heads/realtek/android-14/master/your-file.xml")
        
        custom_url = input(f"\nURL: ").strip()
        if not custom_url:
            print(f"❌ 未輸入 URL")
            return
        
        # 從 URL 提取檔案名稱
        filename = custom_url.split('/')[-1]
        if not filename.endswith('.xml'):
            filename = input(f"請輸入檔案名稱 (包含 .xml): ").strip()
            if not filename:
                print(f"❌ 未輸入檔案名稱")
                return
        
        output_folder = self.input_validator.get_output_folder("輸出資料夾", "./downloads")
        
        print(f"\n📋 下載參數:")
        print(f"  URL: {custom_url}")
        print(f"  檔案: {filename}")
        print(f"  輸出: {os.path.join(output_folder, filename)}")
        
        if self.input_validator.confirm_execution():
            from gerrit_manager import GerritManager
            gerrit = GerritManager()
            output_file = os.path.join(output_folder, filename)
            
            print(f"\n⬇️ 正在下載: {filename}")
            success = gerrit.download_file_from_link(custom_url, output_file)
            
            if success:
                print(f"✅ 自定義下載成功: {output_file}")
                self._show_manifest_file_info(output_file)
            else:
                print(f"❌ 自定義下載失敗: {filename}")
    
    def _open_gerrit_browser(self):
        """開啟 Gerrit 瀏覽器查看可用檔案"""
        browse_url = "https://mm2sd.rtkbf.com/gerrit/plugins/gitiles/realtek/android/manifest/+/refs/heads/realtek/android-14/master/"
        
        print(f"\n🌐 開啟 Gerrit 瀏覽器")
        print(f"URL: {browse_url}")
        print(f"\n📋 已知的可用檔案:")
        print(f"  ✅ atv-google-refplus.xml (Master)")
        print(f"  ✅ atv-google-refplus-premp.xml (PreMP)")
        print(f"  ✅ atv-google-refplus-wave.xml (MP Wave)")
        print(f"  ✅ atv-google-refplus-wave-backup.xml (MP Backup)")
        
        try:
            import platform
            
            if platform.system() == 'Windows':
                subprocess.run(['start', browse_url], shell=True)
            elif platform.system() == 'Darwin':  # macOS
                subprocess.call(['open', browse_url])
            else:  # Linux
                subprocess.call(['xdg-open', browse_url])
            print(f"\n✅ 正在開啟瀏覽器...")
            print(f"💡 在瀏覽器中可以查看所有可用的檔案")
        except Exception as e:
            print(f"❌ 無法開啟瀏覽器: {str(e)}")
            print(f"請手動開啟: {browse_url}")
    
    def _open_file(self, file_path):
        """開啟檔案"""
        try:
            import platform
            
            if platform.system() == 'Windows':
                os.startfile(file_path)
            elif platform.system() == 'Darwin':  # macOS
                subprocess.call(['open', file_path])
            else:  # Linux
                subprocess.call(['xdg-open', file_path])
            print("📄 正在開啟檔案...")
        except Exception as e:
            print(f"⚠️ 無法自動開啟檔案: {str(e)}")
            print(f"請手動開啟: {file_path}")


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