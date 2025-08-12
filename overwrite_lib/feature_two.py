"""
功能二：透過 manifest.xml 建立分支映射表 - 增強版
建立一張 mapping 的 branch table (manifest_projects.xlsx) 並建立相關 branch (可選)
新增：支援 refs/tags/ 的 Tag 處理邏輯 + branch/tag 連結功能
修正：branch_link 使用 dest-branch 欄位並移到最後一欄
🔥 修正：master_vs_premp 使用 feature_three.py 的完整轉換邏輯
🔥 修正：當 revision 為空且 remote=rtk 時，使用 default revision
⚠️  重要：feature_three.py 也需要同步相同的 default revision 處理邏輯！
"""
import os
import xml.etree.ElementTree as ET
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple
import utils
import sys
import re

# 加入上一層目錄到路徑
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
    
# 載入模組 (處理 import 路徑)
try:
    from excel_handler import ExcelHandler
except ImportError:
    # 如果無法直接導入，可能路徑不對，嘗試處理
    import sys
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
    from excel_handler import ExcelHandler

from gerrit_manager import GerritManager
import config

logger = utils.setup_logger(__name__)

class FeatureTwo:
    """功能二：建立分支映射表 - 增強版 (支援 Tag + 連結功能 + 完整 master_to_premp 轉換邏輯)"""
    
    def __init__(self):
        self.logger = logger
        self.excel_handler = ExcelHandler()
        self.gerrit_manager = GerritManager()
    
    def process(self, input_file: str, process_type: str, output_filename: str, 
                remove_duplicates: bool, create_branches: bool, check_branch_exists: bool,
                output_folder: str = './output') -> bool:
        """
        處理功能二的主要邏輯 - 修改版本（包含連結生成）
        
        Args:
            input_file: 輸入的 manifest.xml 檔案路徑
            process_type: 處理類型 (master_vs_premp, premp_vs_mp, mp_vs_mpbackup)
            output_filename: 輸出檔案名稱
            remove_duplicates: 是否去除重複資料
            create_branches: 是否建立分支
            check_branch_exists: 是否檢查分支存在性
            output_folder: 輸出資料夾路徑
            
        Returns:
            是否處理成功
        """
        try:
            self.logger.info("=== 開始執行功能二：建立分支映射表 ===")
            self.logger.info(f"輸入檔案: {input_file}")
            self.logger.info(f"處理類型: {process_type}")
            self.logger.info(f"輸出檔案: {output_filename}")
            self.logger.info(f"去除重複: {remove_duplicates}")
            self.logger.info(f"建立分支: {create_branches}")
            self.logger.info(f"檢查分支存在性: {check_branch_exists}")
            self.logger.info(f"輸出資料夾: {output_folder}")
            
            # 確保輸出資料夾存在
            utils.ensure_dir(output_folder)
            
            # 步驟 1: 解析 manifest.xml
            projects = self._parse_manifest(input_file)
            if not projects:
                self.logger.error("無法解析 manifest.xml 或檔案為空")
                return False
            
            self.logger.info(f"成功解析 {len(projects)} 個專案")
            
            # 步驟 2: 轉換專案（使用新的邏輯）
            converted_projects = self._convert_projects(projects, process_type, check_branch_exists)
            
            # 步驟 3: 🆕 添加連結資訊
            projects_with_links = self._add_links_to_projects(converted_projects)
            
            # 步驟 4: 處理重複資料
            unique_projects, duplicate_projects = self._handle_duplicates(projects_with_links, remove_duplicates)
            
            # 🆕 步驟 4.5: 重新編號 SN（避免跳號）
            unique_projects = self._renumber_projects(unique_projects)
            duplicate_projects = self._renumber_projects(duplicate_projects)
            
            self.logger.info(f"處理完成: {len(unique_projects)} 個專案, {len(duplicate_projects)} 個重複")
            
            # 步驟 5: 生成 Excel 報告（使用新的方法）
            self._write_excel_with_links(unique_projects, duplicate_projects, output_filename, output_folder)
            
            # 步驟 6: 建立分支（如果需要）
            if create_branches:
                self._create_branches(unique_projects, output_filename, output_folder)
            
            excel_path = os.path.join(output_folder, output_filename)
            self.logger.info(f"=== 功能二執行完成，Excel 檔案：{excel_path} ===")
            return True
            
        except Exception as e:
            self.logger.error(f"功能二執行失敗: {str(e)}")
            return False

    # ============================================
    # 🔥 新增：從 feature_three.py 移植的轉換邏輯
    # ============================================

    def _should_skip_revision_conversion(self, revision: str) -> bool:
        """
        判斷是否應該跳過 revision 轉換 - 與 feature_three.py 完全同步
        
        Args:
            revision: 原始 revision
            
        Returns:
            是否應該跳過轉換
        """
        if not revision:
            return True
        
        # 🆕 跳過 Google 開頭的項目
        if revision.startswith('google/'):
            return True
        
        # 跳過 refs/tags/
        if revision.startswith('refs/tags/'):
            return True
        
        return False

    def _smart_conversion_fallback(self, revision: str) -> str:
        """
        智能轉換備案 - 當沒有精確規則時使用 - 與 feature_three.py 完全同步
        
        Args:
            revision: 原始 revision
            
        Returns:
            轉換後的 revision
        """
        # 如果包含 mp.google-refplus，嘗試替換為 premp.google-refplus
        if 'mp.google-refplus' in revision:
            # 保留原始路徑，只替換關鍵字
            result = revision.replace('mp.google-refplus', 'premp.google-refplus')
            self.logger.debug(f"智能替換 mp→premp: {revision} → {result}")
            return result
        
        # 如果是 master 但沒有匹配到特定規則，使用預設轉換
        if '/master' in revision and 'realtek/' in revision:
            # 提取 android 版本（如果有）
            android_match = re.search(r'android-(\d+)', revision)
            if android_match:
                android_ver = android_match.group(1)
                result = f'realtek/android-{android_ver}/premp.google-refplus'
                self.logger.debug(f"智能Android版本轉換: {revision} → {result}")
                return result
            else:
                result = 'realtek/android-14/premp.google-refplus'
                self.logger.debug(f"智能預設轉換: {revision} → {result}")
                return result
        
        # 如果完全沒有匹配，返回預設值
        result = 'realtek/android-14/premp.google-refplus'
        self.logger.debug(f"備案預設轉換: {revision} → {result}")
        return result

    def _convert_master_to_premp(self, revision: str) -> str:
        """
        master → premp 轉換規則 - 從 feature_three.py 完全移植
        
        Args:
            revision: 原始 revision
            
        Returns:
            轉換後的 revision
        """
        if not revision:
            return revision
        
        original_revision = revision.strip()
        
        # 🆕 跳過 Google 開頭的項目（如 google/u-tv-keystone-rtk-refplus-wave4-release）
        if original_revision.startswith('google/'):
            self.logger.debug(f"跳過 Google 項目: {original_revision}")
            return original_revision
        
        # 🆕 跳過特殊項目
        if self._should_skip_revision_conversion(original_revision):
            return original_revision
        
        # 🆕 精確匹配轉換規則（優先級最高）
        exact_mappings = {
            # 基本 master 分支轉換
            'realtek/master': 'realtek/android-14/premp.google-refplus',
            'realtek/gaia': 'realtek/android-14/premp.google-refplus',
            'realtek/gki/master': 'realtek/android-14/premp.google-refplus',
            
            # Android 14 主要分支
            'realtek/android-14/master': 'realtek/android-14/premp.google-refplus',
            
            # 🔥 修正：Linux kernel android master 分支轉換（保留 linux 路徑）
            'realtek/linux-5.15/android-14/master': 'realtek/linux-5.15/android-14/premp.google-refplus',
            'realtek/linux-4.14/android-14/master': 'realtek/linux-4.14/android-14/premp.google-refplus',
            'realtek/linux-5.4/android-14/master': 'realtek/linux-5.4/android-14/premp.google-refplus',
            'realtek/linux-5.10/android-14/master': 'realtek/linux-5.10/android-14/premp.google-refplus',
            'realtek/linux-6.1/android-14/master': 'realtek/linux-6.1/android-14/premp.google-refplus',
            
            # 🔥 修正：直接的 mp.google-refplus 轉換（需要加上 android-14）
            'realtek/mp.google-refplus': 'realtek/android-14/premp.google-refplus',
            
            # 其他常見的轉換
            'realtek/android-14/mp.google-refplus': 'realtek/android-14/premp.google-refplus',
        }
        
        # 檢查精確匹配
        if original_revision in exact_mappings:
            self.logger.debug(f"精確匹配轉換: {original_revision} → {exact_mappings[original_revision]}")
            return exact_mappings[original_revision]
        
        # 🆕 模式匹配轉換規則（使用正規表達式）
        
        # 規則 1: mp.google-refplus.upgrade-11.rtdXXXX → premp.google-refplus.upgrade-11.rtdXXXX
        pattern1 = r'realtek/android-(\d+)/mp\.google-refplus\.upgrade-(\d+)\.(rtd\w+)'
        match1 = re.match(pattern1, original_revision)
        if match1:
            android_ver, upgrade_ver, rtd_chip = match1.groups()
            result = f'realtek/android-{android_ver}/premp.google-refplus.upgrade-{upgrade_ver}.{rtd_chip}'
            self.logger.debug(f"模式1轉換: {original_revision} → {result}")
            return result
        
        # 規則 2: mp.google-refplus.upgrade-11 → premp.google-refplus.upgrade-11
        pattern2 = r'realtek/android-(\d+)/mp\.google-refplus\.upgrade-(\d+)$'
        match2 = re.match(pattern2, original_revision)
        if match2:
            android_ver, upgrade_ver = match2.groups()
            result = f'realtek/android-{android_ver}/premp.google-refplus.upgrade-{upgrade_ver}'
            self.logger.debug(f"模式2轉換: {original_revision} → {result}")
            return result
        
        # 🔥 規則 3: linux-X.X/master → linux-X.X/android-14/premp.google-refplus（修正版）
        pattern3 = r'realtek/linux-([\d.]+)/master$'
        match3 = re.match(pattern3, original_revision)
        if match3:
            linux_ver = match3.group(1)
            result = f'realtek/linux-{linux_ver}/android-14/premp.google-refplus'
            self.logger.debug(f"模式3轉換（Linux master）: {original_revision} → {result}")
            return result
        
        # 🔥 規則 4: linux-X.X/android-Y/master → linux-X.X/android-Y/premp.google-refplus（修正版）
        pattern4 = r'realtek/linux-([\d.]+)/android-(\d+)/master$'
        match4 = re.match(pattern4, original_revision)
        if match4:
            linux_ver, android_ver = match4.groups()
            result = f'realtek/linux-{linux_ver}/android-{android_ver}/premp.google-refplus'
            self.logger.debug(f"模式4轉換（Linux Android master）: {original_revision} → {result}")
            return result
        
        # 規則 5: linux-X.X/android-Y/mp.google-refplus → linux-X.X/android-Y/premp.google-refplus
        pattern5 = r'realtek/linux-([\d.]+)/android-(\d+)/mp\.google-refplus$'
        match5 = re.match(pattern5, original_revision)
        if match5:
            linux_ver, android_ver = match5.groups()
            result = f'realtek/linux-{linux_ver}/android-{android_ver}/premp.google-refplus'
            self.logger.debug(f"模式5轉換: {original_revision} → {result}")
            return result
        
        # 規則 6: linux-X.X/android-Y/mp.google-refplus.rtdXXXX → linux-X.X/android-Y/premp.google-refplus.rtdXXXX
        pattern6 = r'realtek/linux-([\d.]+)/android-(\d+)/mp\.google-refplus\.(rtd\w+)'
        match6 = re.match(pattern6, original_revision)
        if match6:
            linux_ver, android_ver, rtd_chip = match6.groups()
            result = f'realtek/linux-{linux_ver}/android-{android_ver}/premp.google-refplus.{rtd_chip}'
            self.logger.debug(f"模式6轉換: {original_revision} → {result}")
            return result
        
        # 規則 7: android-Y/mp.google-refplus → android-Y/premp.google-refplus
        pattern7 = r'realtek/android-(\d+)/mp\.google-refplus$'
        match7 = re.match(pattern7, original_revision)
        if match7:
            android_ver = match7.group(1)
            result = f'realtek/android-{android_ver}/premp.google-refplus'
            self.logger.debug(f"模式7轉換: {original_revision} → {result}")
            return result
        
        # 規則 8: android-Y/mp.google-refplus.rtdXXXX → android-Y/premp.google-refplus.rtdXXXX
        pattern8 = r'realtek/android-(\d+)/mp\.google-refplus\.(rtd\w+)'
        match8 = re.match(pattern8, original_revision)
        if match8:
            android_ver, rtd_chip = match8.groups()
            result = f'realtek/android-{android_ver}/premp.google-refplus.{rtd_chip}'
            self.logger.debug(f"模式8轉換: {original_revision} → {result}")
            return result
        
        # 規則 9: 晶片特定的 master 分支 → premp.google-refplus.rtdXXXX
        chip_mappings = getattr(config, 'CHIP_TO_RTD_MAPPING', {
            'mac7p': 'rtd2851a',
            'mac8q': 'rtd2851f', 
            'mac9p': 'rtd2895p',
            'merlin7': 'rtd6748',
            'merlin8': 'rtd2885p',
            'merlin8p': 'rtd2885q',
            'merlin9': 'rtd2875q',
        })
        
        for chip, rtd_model in chip_mappings.items():
            if f'realtek/{chip}/master' == original_revision:
                result = f'realtek/android-14/premp.google-refplus.{rtd_model}'
                self.logger.debug(f"晶片轉換: {original_revision} → {result}")
                return result
        
        # 規則 10: v3.16 版本轉換
        pattern10 = r'realtek/v3\.16/mp\.google-refplus$'
        if re.match(pattern10, original_revision):
            result = 'realtek/v3.16/premp.google-refplus'
            self.logger.debug(f"v3.16轉換: {original_revision} → {result}")
            return result
        
        # 🆕 如果沒有匹配的規則，根據關鍵字進行智能轉換
        smart_result = self._smart_conversion_fallback(original_revision)
        self.logger.debug(f"智能轉換: {original_revision} → {smart_result}")
        return smart_result

    def _convert_premp_to_mp(self, revision: str) -> str:
        """premp → mp 轉換規則"""
        # 將 premp.google-refplus 關鍵字替換為 mp.google-refplus.wave
        return revision.replace('premp.google-refplus', 'mp.google-refplus.wave')
    
    def _convert_mp_to_mpbackup(self, revision: str) -> str:
        """mp → mpbackup 轉換規則"""
        # 將 mp.google-refplus.wave 關鍵字替換為 mp.google-refplus.wave.backup
        return revision.replace('mp.google-refplus.wave', 'mp.google-refplus.wave.backup')

    # ============================================
    # 🔥 修改的轉換邏輯
    # ============================================

    def _convert_projects(self, projects: List[Dict], process_type: str, check_branch_exists: bool = False) -> List[Dict]:
        """轉換專案的分支名稱 - 增強版 (支援 Tag 和 remote 判斷 + 完整 master_to_premp 轉換邏輯)"""
        converted_projects = []
        tag_count = 0
        branch_count = 0
        
        self.logger.info(f"🔄 開始轉換專案分支，處理類型: {process_type}")
        
        for i, project in enumerate(projects, 1):
            converted_project = project.copy()
            converted_project['SN'] = i
            
            # 🆕 取得 remote 資訊
            remote = project.get('remote', '')
            
            # 🔥 修正：使用 revision 進行轉換，而不是 dest-branch 或 upstream
            source_revision = project.get('revision', '')
            
            # 如果沒有 revision，跳過轉換
            if not source_revision:
                target_branch = ''
                self.logger.debug(f"專案 {project.get('name', '')} 沒有 revision，跳過轉換")
            else:
                # 🔥 根據處理類型進行轉換
                target_branch = self._convert_revision_by_type(source_revision, process_type)
                
                if target_branch != source_revision:
                    self.logger.debug(f"專案 {project.get('name', '')} 轉換: {source_revision} → {target_branch}")
            
            converted_project['target_branch'] = target_branch
            
            # 判斷目標是 Tag 還是 Branch
            is_tag = self._is_tag_reference(target_branch)
            converted_project['target_type'] = 'Tag' if is_tag else 'Branch'
            
            if is_tag:
                tag_count += 1
            else:
                branch_count += 1
            
            # 根據參數決定是否檢查存在性
            if check_branch_exists and target_branch:
                if is_tag:
                    # 檢查 Tag 存在性（傳入 remote）
                    exists_info = self._check_target_tag_exists(project.get('name', ''), target_branch, remote)
                else:
                    # 檢查 Branch 存在性（傳入 remote）
                    exists_info = self._check_target_branch_exists(project.get('name', ''), target_branch, remote)
                
                converted_project['target_branch_exists'] = exists_info['exists_status']
                converted_project['target_branch_revision'] = exists_info['revision']
            else:
                converted_project['target_branch_exists'] = '-'  # 未檢查
                converted_project['target_branch_revision'] = '-'  # 未檢查
            
            converted_projects.append(converted_project)
            
            # 每100個項目顯示進度
            if check_branch_exists and i % 100 == 0:
                self.logger.info(f"已處理 {i}/{len(projects)} 個專案的存在性檢查")
        
        self.logger.info(f"轉換完成 - Branch: {branch_count}, Tag: {tag_count}")
        return converted_projects

    def _convert_revision_by_type(self, revision: str, process_type: str) -> str:
        """
        🔥 新版本：根據處理類型轉換 revision - 使用完整的轉換邏輯
        
        Args:
            revision: 原始 revision
            process_type: 處理類型
            
        Returns:
            轉換後的 revision
        """
        try:
            if not revision:
                return ''
            
            # 如果是 Tag 參考，直接返回不做轉換
            if self._is_tag_reference(revision):
                self.logger.debug(f"檢測到 Tag 參考，保持原樣: {revision}")
                return revision
            
            # 🔥 根據處理類型進行轉換，使用完整的轉換邏輯
            if process_type == 'master_vs_premp':
                # 使用完整的 master → premp 轉換邏輯
                return self._convert_master_to_premp(revision)
                
            elif process_type == 'premp_vs_mp':
                # premp → mp
                return self._convert_premp_to_mp(revision)
                
            elif process_type == 'mp_vs_mpbackup':
                # mp → mpbackup
                return self._convert_mp_to_mpbackup(revision)
            
            # 如果沒有匹配的處理類型，返回原值
            return revision
            
        except Exception as e:
            self.logger.error(f"轉換 revision 失敗: {revision}, 錯誤: {str(e)}")
            return revision

    def _convert_branch_by_type(self, project: Dict, process_type: str) -> str:
        """
        🔥 保留舊版方法但重定向到新的轉換邏輯
        
        Args:
            project: 專案字典
            process_type: 處理類型
            
        Returns:
            轉換後的分支名稱
        """
        # 取得 revision 進行轉換
        revision = project.get('revision', '')
        return self._convert_revision_by_type(revision, process_type)

    # ============================================
    # 以下方法保持不變，只是為了完整性而包含
    # ============================================

    def _get_gerrit_base_url(self, remote: str) -> str:
        """
        🆕 根據 remote 取得對應的 Gerrit base URL
        
        Args:
            remote: remote 欄位值
            
        Returns:
            對應的 Gerrit base URL
        """
        try:
            if remote == 'rtk-prebuilt':
                # 使用 prebuilt 專用的 Gerrit 伺服器
                return getattr(config, 'GERRIT_PREBUILT_URL', 'https://mm2sd-git2.rtkbf.com')
            else:
                # 使用一般的 Gerrit 伺服器
                return getattr(config, 'GERRIT_SORUCE_URL', 'https://mm2sd.rtkbf.com')
        except:
            # 如果無法載入 config，使用預設值
            if remote == 'rtk-prebuilt':
                return 'https://mm2sd-git2.rtkbf.com'
            else:
                return 'https://mm2sd.rtkbf.com'
    
    def _build_gerrit_link_from_dest_branch(self, project_name: str, dest_branch: str, remote: str = '') -> str:
        """
        🆕 修正版：根據 dest-branch 建立 Gerrit branch/tag 連結（支援 remote 判斷）
        
        Args:
            project_name: 專案名稱
            dest_branch: dest-branch 欄位值
            remote: remote 欄位值（用於判斷使用哪個 Gerrit）
            
        Returns:
            Gerrit 連結 URL
        """
        try:
            if not project_name or not dest_branch:
                return ""
            
            # 🆕 根據 remote 決定 base URL
            gerrit_base = self._get_gerrit_base_url(remote)
            base_url = f"{gerrit_base}/gerrit/plugins/gitiles"
            
            # 判斷是 tag 還是 branch
            if dest_branch.startswith('refs/tags/'):
                # Tag: 直接使用完整的 refs/tags/xxx
                link = f"{base_url}/{project_name}/+/{dest_branch}"
            elif dest_branch.startswith('refs/heads/'):
                # Branch: 已經有 refs/heads/ 前綴，直接使用
                link = f"{base_url}/{project_name}/+/{dest_branch}"
            else:
                # 沒有前綴的情況，當作 branch 處理，加上 refs/heads/
                link = f"{base_url}/{project_name}/+/refs/heads/{dest_branch}"
            
            self.logger.debug(f"建立 branch_link: {project_name} + {dest_branch} -> {link} (remote: {remote})")
            return link
            
        except Exception as e:
            self.logger.error(f"建立 Gerrit 連結失敗 {project_name}: {str(e)}")
            return ""
    
    def _build_gerrit_link(self, project_name: str, revision: str, target_type: str, remote: str = '') -> str:
        """
        建立 Gerrit branch/tag 連結（用於 target_branch_link）（支援 remote 判斷）
        
        Args:
            project_name: 專案名稱
            revision: 分支或標籤名稱
            target_type: 'branch' 或 'tag'
            remote: remote 欄位值（用於判斷使用哪個 Gerrit）
            
        Returns:
            Gerrit 連結 URL
        """
        try:
            if not project_name or not revision:
                return ""
            
            # 🆕 根據 remote 決定 base URL
            gerrit_base = self._get_gerrit_base_url(remote)
            base_url = f"{gerrit_base}/gerrit/plugins/gitiles"
            
            # 處理 refs/tags/ 或 refs/heads/ 前綴
            clean_revision = revision
            if revision.startswith('refs/tags/'):
                clean_revision = revision[10:]  # 移除 'refs/tags/'
                target_type = 'tag'
            elif revision.startswith('refs/heads/'):
                clean_revision = revision[11:]  # 移除 'refs/heads/'
                target_type = 'branch'
            
            if target_type.lower() == 'tag':
                # tag link: /+/refs/tags/{tag_name}
                link = f"{base_url}/{project_name}/+/refs/tags/{clean_revision}"
            else:
                # branch link: /+/refs/heads/{branch_name}
                link = f"{base_url}/{project_name}/+/refs/heads/{clean_revision}"
            
            self.logger.debug(f"建立 {target_type} 連結: {project_name} -> {link} (remote: {remote})")
            return link
            
        except Exception as e:
            self.logger.error(f"建立 Gerrit 連結失敗 {project_name}: {str(e)}")
            return ""
    
    def _determine_revision_type(self, revision: str) -> str:
        """
        判斷 revision 是 branch 還是 tag
        
        Args:
            revision: revision 字串
            
        Returns:
            'Branch' 或 'Tag'
        """
        if not revision:
            return 'Branch'  # 預設為 Branch
        
        # 如果以 refs/tags/ 開頭，直接判斷為 Tag
        if revision.startswith('refs/tags/'):
            return 'Tag'
        
        # 常見的 tag 關鍵字
        tag_keywords = [
            'release', 'tag', 'v1.', 'v2.', 'v3.', 'v4.', 'v5.',
            'stable', 'final', 'rc', 'beta', 'alpha',
            'android-', 'aosp-', 'platform-',
            '.release', '-release', '_release'
        ]
        
        revision_lower = revision.lower()
        
        # 檢查是否包含 tag 關鍵字
        for keyword in tag_keywords:
            if keyword in revision_lower:
                return 'Tag'
        
        # 檢查版本號格式 (如 v1.0.0, 12.0.1)
        version_patterns = [
            r'v?\d+\.\d+',  # v1.0, 1.0
            r'v?\d+\.\d+\.\d+',  # v1.0.0, 1.0.0
            r'android-\d+',  # android-12
            r'api-\d+',  # api-30
        ]
        
        for pattern in version_patterns:
            if re.search(pattern, revision_lower):
                return 'Tag'
        
        return 'Branch'  # 預設為 Branch

    def _renumber_projects(self, projects: List[Dict]) -> List[Dict]:
        """
        🆕 重新編號專案列表的 SN，確保連續不跳號
        
        Args:
            projects: 專案列表
            
        Returns:
            重新編號後的專案列表
        """
        for i, project in enumerate(projects, 1):
            project['SN'] = i
        return projects
    
    def _add_links_to_projects(self, projects: List[Dict]) -> List[Dict]:
        """
        為專案添加 branch/tag 連結資訊
        🔥 修正：branch_link 使用 revision 欄位（因為很多專案沒有 dest-branch）
        🆕 新增：revision_diff 欄位（將使用 Excel 公式）
        🆕 新增：根據 remote 判斷 Gerrit 伺服器
        
        Args:
            projects: 專案列表
            
        Returns:
            包含連結資訊的專案列表
        """
        projects_with_links = []
        
        # 🔥 調試資訊：統計欄位使用情況
        revision_count = 0
        dest_branch_count = 0
        
        for project in projects:
            enhanced_project = project.copy()
            
            project_name = project.get('name', '')
            
            # 🆕 取得 remote 資訊
            remote = project.get('remote', '')
            
            # 🔥 修正：branch_link 使用 revision 欄位（原始分支），因為 dest-branch 經常是空的
            revision = project.get('revision', '')
            dest_branch = project.get('dest-branch', '')
            
            # 🔥 統計欄位使用情況
            if revision:
                revision_count += 1
            if dest_branch:
                dest_branch_count += 1
            
            # 🔥 建立 branch_link - 使用 revision（原始分支的連結）
            if revision:
                # 判斷 revision 類型
                revision_type = self._determine_revision_type(revision)
                branch_link = self._build_gerrit_link(project_name, revision, revision_type, remote)
                self.logger.debug(f"為專案 {project_name} 建立 branch_link: {revision} -> {branch_link[:50]}...")
            else:
                branch_link = ""
                self.logger.debug(f"專案 {project_name} 沒有 revision，branch_link 為空")
            
            # 目標 branch 資訊（保持不變）
            target_branch = project.get('target_branch', '')
            target_type = project.get('target_type', 'Branch')
            
            # 建立 target_branch_link (綠底白字) - 目標 branch 的連結（傳入 remote）
            target_branch_link = self._build_gerrit_link(project_name, target_branch, target_type, remote)
            
            # 🆕 revision_diff 欄位將使用 Excel 公式，這裡只是佔位符
            # 實際公式會在 _write_excel_with_links 中設定
            revision_diff = ''  # 佔位符，將被 Excel 公式取代
            
            # 添加所有欄位
            enhanced_project['branch_link'] = branch_link
            enhanced_project['target_branch_link'] = target_branch_link
            enhanced_project['revision_diff'] = revision_diff
            
            projects_with_links.append(enhanced_project)
        
        self.logger.info(f"已為 {len(projects_with_links)} 個專案添加連結資訊")
        self.logger.info(f"🔗 branch_link 使用 revision 欄位，target_branch_link 使用轉換後的 target_branch")
        self.logger.info(f"📊 欄位統計: revision 欄位有值: {revision_count}, dest-branch 欄位有值: {dest_branch_count}")
        if revision_count > dest_branch_count:
            self.logger.info(f"✅ 修正說明: 使用 revision 而非 dest-branch 可以避免大部分 branch_link 為空的問題")
        return projects_with_links

    def _write_excel_with_links(self, projects: List[Dict], duplicate_projects: List[Dict], 
                              output_file: str, output_folder: str = None):
        """
        寫入 Excel 檔案 - 包含連結功能的增強版
        🔥 修正：branch_link 使用 revision 欄位避免空值問題
        🆕 功能：revision_diff 使用 Excel 公式自動比對
        """
        try:
            # 處理輸出檔案路徑
            if not output_file:
                raise ValueError("輸出檔案名稱不能為空")
            
            # 處理輸出資料夾
            if output_folder:
                utils.ensure_dir(output_folder)
                full_output_path = os.path.join(output_folder, output_file)
            else:
                output_dir = os.path.dirname(output_file)
                if not output_dir:
                    output_file = os.path.join('.', output_file)
                    output_dir = '.'
                utils.ensure_dir(output_dir)
                full_output_path = output_file
            
            self.logger.info(f"寫入 Excel 檔案: {full_output_path}")
            
            with pd.ExcelWriter(full_output_path, engine='openpyxl') as writer:
                # 頁籤 1: 專案列表
                if projects:
                    df_main = pd.DataFrame(projects)
                    
                    # 🆕 調整欄位順序：
                    # - revision: 原始分支
                    # - target_branch: 轉換後分支 
                    # - revision_diff: 比對結果（橘底白字，使用公式比對 revision）
                    # - target_branch_link: 轉換後分支連結（綠底白字）
                    # - branch_link: 原始分支連結（藍底白字，移到最後）
                    main_column_order = [
                        'SN', 'name', 'revision', 'upstream', 'dest-branch',
                        'target_branch', 
                        'target_type', 
                        'target_branch_exists', 
                        'target_branch_revision',
                        'revision_diff',  # 🆕 橘底白字，使用公式比對 revision
                        'target_branch_link'  # 綠底白字
                    ]
                    
                    # 添加其他可能存在的欄位（groups, path, source_type 等）
                    for col in df_main.columns:
                        if col not in main_column_order and col != 'branch_link':
                            main_column_order.append(col)
                    
                    # 最後加上 branch_link
                    main_column_order.append('branch_link')  # 🆕 藍底白字移到最後
                    
                    # 只保留存在的欄位
                    main_column_order = [col for col in main_column_order if col in df_main.columns]
                    df_main = df_main[main_column_order]
                else:
                    # 空的 DataFrame 結構
                    df_main = pd.DataFrame(columns=[
                        'SN', 'name', 'revision', 'upstream', 'dest-branch',
                        'target_branch', 'target_type', 'target_branch_exists', 
                        'target_branch_revision', 'revision_diff', 'target_branch_link', 'branch_link'
                    ])
                
                df_main.to_excel(writer, sheet_name='專案列表', index=False)
                
                # 頁籤 2: 重複專案
                if duplicate_projects:
                    df_dup = pd.DataFrame(duplicate_projects)
                    # 🆕 移除這裡的重新編號，因為已經在 _renumber_projects 處理過了
                    
                    # 🆕 重複頁籤也使用相同的欄位順序
                    # - branch_link（原始分支連結）在最後
                    # - target_branch_link（轉換後分支連結）在 revision_diff 右邊
                    dup_column_order = [
                        'SN', 'name', 'revision', 'upstream', 'dest-branch',
                        'target_branch',
                        'target_type',
                        'target_branch_exists',
                        'target_branch_revision',
                        'revision_diff',  # 🆕 橘底白字，使用公式比對 revision
                        'target_branch_link'  # 綠底白字
                    ]
                    
                    # 添加其他欄位
                    for col in df_dup.columns:
                        if col not in dup_column_order and col != 'branch_link':
                            dup_column_order.append(col)
                    
                    # 最後加上 branch_link
                    dup_column_order.append('branch_link')  # 🆕 藍底白字移到最後
                    
                    dup_column_order = [col for col in dup_column_order if col in df_dup.columns]
                    df_dup = df_dup[dup_column_order]
                    
                    df_dup.to_excel(writer, sheet_name='重覆', index=False)
                    self.logger.info(f"建立 '重覆' 頁籤，共 {len(duplicate_projects)} 筆資料")
                
                # 🆕 設定 revision_diff 欄位的 Excel 公式
                self._set_revision_diff_formulas(writer)
                
                # 🆕 格式化所有工作表，包含連結欄位
                self._format_excel_with_links(writer)
            
            self.logger.info(f"成功寫入 Excel 檔案: {full_output_path}")
            
        except Exception as e:
            self.logger.error(f"寫入 Excel 檔案失敗: {str(e)}")
            raise

    def _set_revision_diff_formulas(self, writer):
        """
        設定 revision_diff 欄位的 Excel 公式
        公式邏輯：比對 revision 前8碼與 target_branch_revision
        - 相同顯示 "N" (綠色)
        - 不同顯示 "Y" (紅色)
        - 任一為空或 "-" 顯示 "Y" (紅色)
        """
        try:
            from openpyxl.utils import get_column_letter
            
            for sheet_name in ['專案列表', '重覆']:
                if sheet_name not in writer.sheets:
                    continue
                    
                worksheet = writer.sheets[sheet_name]
                
                # 找到各欄位的位置
                revision_col = None
                target_revision_col = None
                revision_diff_col = None
                
                for col_num, cell in enumerate(worksheet[1], 1):
                    header = str(cell.value) if cell.value else ''
                    if header == 'revision':
                        revision_col = col_num
                    elif header == 'target_branch_revision':
                        target_revision_col = col_num
                    elif header == 'revision_diff':
                        revision_diff_col = col_num
                
                if revision_col and target_revision_col and revision_diff_col:
                    revision_letter = get_column_letter(revision_col)
                    target_letter = get_column_letter(target_revision_col)
                    diff_letter = get_column_letter(revision_diff_col)
                    
                    # 設定欄寬 - 縮小 revision_diff 欄位寬度
                    worksheet.column_dimensions[diff_letter].width = 12  # 縮小寬度
                    
                    for row_num in range(2, worksheet.max_row + 1):
                        # 修改公式邏輯：相同顯示 "N"，不同或空值顯示 "Y"
                        formula = (
                            f'=IF(OR({target_letter}{row_num}="-", '
                            f'{target_letter}{row_num}="", '
                            f'{revision_letter}{row_num}=""), '
                            f'"Y", '  # 空值顯示 Y
                            f'IF(LEFT({revision_letter}{row_num},8)={target_letter}{row_num}, '
                            f'"N", "Y"))'  # 相同顯示 N，不同顯示 Y
                        )
                        
                        worksheet[f"{diff_letter}{row_num}"].value = formula
                    
                    self.logger.info(f"已為 '{sheet_name}' 頁籤設定 revision_diff 公式")
                    
        except Exception as e:
            self.logger.error(f"設定 revision_diff 公式失敗: {str(e)}")
    
    def _format_excel_with_links(self, writer):
        """
        格式化 Excel 工作表，包含新的連結欄位格式
        """
        try:
            from openpyxl.styles import PatternFill, Font, Alignment
            from openpyxl.utils import get_column_letter
            
            # 定義顏色
            blue_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")    # 藍底
            green_fill = PatternFill(start_color="00B050", end_color="00B050", fill_type="solid")   # 綠底
            orange_fill = PatternFill(start_color="ED7D31", end_color="ED7D31", fill_type="solid")  # 🆕 橘底
            white_font = Font(color="FFFFFF", bold=True)  # 白字
            
            for sheet_name in writer.sheets:
                worksheet = writer.sheets[sheet_name]
                
                # 先執行基本格式化
                self.excel_handler._format_worksheet(worksheet)
                
                # 🆕 特別格式化連結欄位
                self._format_link_columns(worksheet, blue_fill, green_fill, white_font)
                
                # 🆕 格式化 revision_diff 欄位
                self._format_revision_diff_column(worksheet, orange_fill, white_font)
                
                # 保留原有的目標分支欄位格式化
                self._format_target_branch_columns(worksheet)
                
        except Exception as e:
            self.logger.error(f"Excel 格式化失敗: {str(e)}")

    def _format_revision_diff_column(self, worksheet, orange_fill, white_font):
        """
        格式化 revision_diff 欄位（橘底白字，N綠字/Y紅字）
        使用條件格式化處理公式結果
        """
        try:
            from openpyxl.styles import Font
            from openpyxl.utils import get_column_letter
            from openpyxl.formatting.rule import CellIsRule
            
            # 內容樣式
            green_font = Font(color="00B050", bold=True)  # N 的綠字
            red_font = Font(color="FF0000", bold=True)    # Y 的紅字
            
            # 找到 revision_diff 欄位的位置
            revision_diff_col = None
            for col_num, cell in enumerate(worksheet[1], 1):
                header_value = str(cell.value) if cell.value else ''
                if header_value == 'revision_diff':
                    revision_diff_col = col_num
                    break
            
            if revision_diff_col:
                col_letter = get_column_letter(revision_diff_col)
                
                # 格式化標題（橘底白字）
                header_cell = worksheet[f"{col_letter}1"]
                header_cell.fill = orange_fill
                header_cell.font = white_font
                
                # 設定欄寬 - 縮小寬度
                worksheet.column_dimensions[col_letter].width = 12  # 從預設寬度改為 12
                
                # 定義資料範圍
                data_range = f"{col_letter}2:{col_letter}{worksheet.max_row}"
                
                # 條件格式規則 1: 當值為 "N" 時使用綠字（相同）
                rule_n = CellIsRule(
                    operator='equal',
                    formula=['"N"'],
                    font=green_font
                )
                worksheet.conditional_formatting.add(data_range, rule_n)
                
                # 條件格式規則 2: 當值為 "Y" 時使用紅字（不同或空值）
                rule_y = CellIsRule(
                    operator='equal',
                    formula=['"Y"'],
                    font=red_font
                )
                worksheet.conditional_formatting.add(data_range, rule_y)
                
                self.logger.info("已設定 revision_diff 欄位格式：標頭橘底白字，N綠字/Y紅字")
                
        except Exception as e:
            self.logger.error(f"格式化 revision_diff 欄位失敗: {str(e)}")

    def _format_link_columns(self, worksheet, blue_fill, green_fill, white_font):
        """
        格式化連結欄位 - 調整欄寬
        """
        try:
            from openpyxl.utils import get_column_letter
            
            # 找到連結欄位的位置
            link_columns = {}
            for col_num, cell in enumerate(worksheet[1], 1):
                header_value = str(cell.value) if cell.value else ''
                
                if header_value == 'branch_link':
                    link_columns['branch_link'] = col_num
                elif header_value == 'target_branch_link':
                    link_columns['target_branch_link'] = col_num
            
            # 格式化 branch_link 欄位 (藍底白字)
            if 'branch_link' in link_columns:
                col_num = link_columns['branch_link']
                col_letter = get_column_letter(col_num)
                
                header_cell = worksheet[f"{col_letter}1"]
                header_cell.fill = blue_fill
                header_cell.font = white_font
                
                # 調整欄寬 - 略微縮小
                worksheet.column_dimensions[col_letter].width = 60  # 從 80 改為 60
                
            # 格式化 target_branch_link 欄位 (綠底白字)
            if 'target_branch_link' in link_columns:
                col_num = link_columns['target_branch_link']
                col_letter = get_column_letter(col_num)
                
                header_cell = worksheet[f"{col_letter}1"]
                header_cell.fill = green_fill
                header_cell.font = white_font
                
                # 調整欄寬 - 略微縮小
                worksheet.column_dimensions[col_letter].width = 60  # 從 80 改為 60
                
            self.logger.info("已完成連結欄位格式化並調整欄寬")
            
        except Exception as e:
            self.logger.error(f"格式化連結欄位失敗: {str(e)}")

    # ========================
    # 以下保持原有方法不變
    # ========================

    def _parse_manifest(self, input_file: str) -> List[Dict]:
        """
        解析 manifest.xml 檔案 - 增強版（支援 default remote 和 revision）
        🔥 新增：當專案 revision 為空且 remote=rtk 時，使用 default 的 revision
        """
        try:
            tree = ET.parse(input_file)
            root = tree.getroot()
            
            # 🔥 讀取 default 標籤的 remote 和 revision 屬性
            default_remote = ''
            default_revision = ''
            default_element = root.find('default')
            if default_element is not None:
                default_remote = default_element.get('remote', '')
                default_revision = default_element.get('revision', '')
                self.logger.info(f"找到預設 remote: {default_remote}")
                self.logger.info(f"找到預設 revision: {default_revision}")
            
            projects = []
            applied_default_revision_count = 0
            
            for project in root.findall('project'):
                # 取得專案的 remote，如果為空則使用 default_remote
                project_remote = project.get('remote', '')
                if not project_remote and default_remote:
                    project_remote = default_remote
                    self.logger.debug(f"專案 {project.get('name', '')} 使用預設 remote: {default_remote}")
                
                # 🔥 取得專案的 revision，如果為空且 remote=rtk 則使用 default_revision
                project_revision = project.get('revision', '')
                if not project_revision and project_remote == 'rtk' and default_revision:
                    project_revision = default_revision
                    applied_default_revision_count += 1
                    self.logger.debug(f"專案 {project.get('name', '')} 使用預設 revision: {default_revision}")
                
                project_data = {
                    'name': project.get('name', ''),
                    'path': project.get('path', ''),
                    'revision': project_revision,  # 🔥 使用處理後的 revision 值
                    'upstream': project.get('upstream', ''),
                    'dest-branch': project.get('dest-branch', ''),
                    'groups': project.get('groups', ''),
                    'clone-depth': project.get('clone-depth', ''),
                    'remote': project_remote  # 使用處理後的 remote 值
                }
                projects.append(project_data)
            
            self.logger.info(f"解析完成，共 {len(projects)} 個專案")
            
            # 🔥 統計應用預設 revision 的專案數量
            if applied_default_revision_count > 0:
                self.logger.info(f"✅ 已為 {applied_default_revision_count} 個 rtk remote 專案應用預設 revision")
            
            # 統計 remote 使用情況
            remote_stats = {}
            revision_stats = {'有revision': 0, '無revision': 0}
            for p in projects:
                remote_val = p.get('remote', 'no-remote')
                remote_stats[remote_val] = remote_stats.get(remote_val, 0) + 1
                
                if p.get('revision', ''):
                    revision_stats['有revision'] += 1
                else:
                    revision_stats['無revision'] += 1
            
            self.logger.info(f"Remote 統計: {remote_stats}")
            self.logger.info(f"Revision 統計: {revision_stats}")
            
            return projects
            
        except Exception as e:
            self.logger.error(f"解析 manifest 檔案失敗: {str(e)}")
            return []

    def _is_tag_reference(self, reference: str) -> bool:
        """判斷參考是否為 Tag (以 refs/tags/ 開頭)"""
        if not reference:
            return False
        return reference.startswith('refs/tags/')

    def _get_prebuilt_gerrit_manager(self) -> 'GerritManager':
        """
        🆕 取得或建立 rtk-prebuilt 專用的 GerritManager
        
        Returns:
            設定好的 GerritManager 實例
        """
        # 如果還沒有建立 prebuilt 專用的 manager，建立一個
        if not hasattr(self, '_prebuilt_gerrit_manager'):
            from gerrit_manager import GerritManager
            self._prebuilt_gerrit_manager = GerritManager()
            
            # 設定 prebuilt 專用的 URL
            prebuilt_base = self._get_gerrit_base_url('rtk-prebuilt')
            self._prebuilt_gerrit_manager.base_url = prebuilt_base
            self._prebuilt_gerrit_manager.api_url = f"{prebuilt_base}/a"
            
            # 更新 session 的基礎 URL
            if hasattr(self._prebuilt_gerrit_manager, 'session'):
                # session 會使用相同的認證資訊
                pass
            
            self.logger.info(f"建立 rtk-prebuilt 專用 GerritManager: {prebuilt_base}")
        
        return self._prebuilt_gerrit_manager
    
    def _check_target_tag_exists(self, project_name: str, target_tag: str, remote: str = '') -> Dict[str, str]:
        """檢查目標 Tag 是否存在並取得 revision（支援 remote 判斷）"""
        result = {
            'exists_status': 'N',
            'revision': ''
        }
        
        try:
            if not project_name or not target_tag:
                return result
            
            # 移除 refs/tags/ 前綴，只保留 tag 名稱
            tag_name = target_tag
            if tag_name.startswith('refs/tags/'):
                tag_name = tag_name[10:]  # 移除 'refs/tags/'
            
            # 🆕 根據 remote 建立或選擇正確的 GerritManager
            if remote == 'rtk-prebuilt':
                # 使用 prebuilt 的 Gerrit 伺服器
                temp_gerrit = self._get_prebuilt_gerrit_manager()
                self.logger.debug(f"使用 rtk-prebuilt Gerrit 檢查 Tag: {project_name}")
            else:
                # 使用預設的 GerritManager
                temp_gerrit = self.gerrit_manager
                self.logger.debug(f"使用預設 Gerrit 檢查 Tag: {project_name}")
            
            # 查詢 Tag
            tag_info = temp_gerrit.query_tag(project_name, tag_name)
            
            if tag_info['exists']:
                result['exists_status'] = 'Y'
                result['revision'] = tag_info['revision']
                self.logger.debug(f"Tag 存在: {project_name}/{tag_name} - {result['revision']}")
            
        except Exception as e:
            self.logger.debug(f"檢查 Tag 失敗: {project_name} - {target_tag}: {str(e)}")
        
        return result

    def _check_target_branch_exists(self, project_name: str, target_branch: str, remote: str = '') -> Dict[str, str]:
        """檢查目標分支是否存在並取得 revision - 簡化版（支援 remote 判斷）"""
        result = {
            'exists_status': 'N',
            'revision': ''
        }
        
        try:
            if not project_name or not target_branch:
                return result
            
            # 🆕 根據 remote 選擇正確的 GerritManager
            if remote == 'rtk-prebuilt':
                self.logger.debug(f"使用 rtk-prebuilt Gerrit 檢查分支: {project_name}/{target_branch}")
            else:
                self.logger.debug(f"使用預設 Gerrit 檢查分支: {project_name}/{target_branch}")
            
            # 直接使用最可靠的方法（傳入 remote）
            branch_info = self._query_branch_direct(project_name, target_branch, remote)
            
            if branch_info['exists']:
                result['exists_status'] = 'Y'
                result['revision'] = branch_info['revision']
                self.logger.debug(f"分支存在: {project_name}/{target_branch} - {result['revision']}")
            
        except Exception as e:
            self.logger.debug(f"檢查分支失敗: {project_name} - {target_branch}: {str(e)}")
        
        return result

    def _query_branch_direct(self, project_name: str, branch_name: str, remote: str = '') -> Dict[str, Any]:
        """直接查詢分支 - 使用最可靠的方法（支援 remote 判斷）"""
        try:
            import urllib.parse
            
            # URL 編碼
            encoded_project = urllib.parse.quote(project_name, safe='')
            encoded_branch = urllib.parse.quote(f"refs/heads/{branch_name}", safe='')
            
            # 🆕 根據 remote 選擇正確的 GerritManager
            if remote == 'rtk-prebuilt':
                # 使用 prebuilt 的 Gerrit
                temp_gerrit = self._get_prebuilt_gerrit_manager()
                gerrit_base = self._get_gerrit_base_url('rtk-prebuilt')
            else:
                # 使用預設的 Gerrit
                temp_gerrit = self.gerrit_manager
                gerrit_base = self._get_gerrit_base_url('')
            
            # 建立 API URL
            api_url = f"{gerrit_base}/gerrit/a/projects/{encoded_project}/branches/{encoded_branch}"
            
            self.logger.debug(f"查詢分支 API: {api_url}")
            
            # 使用對應的 GerritManager 發送請求
            response = temp_gerrit._make_request(api_url, timeout=5)
            
            if response.status_code == 200:
                content = response.text
                if content.startswith(")]}'\n"):
                    content = content[5:]
                
                import json
                branch_info = json.loads(content)
                revision = branch_info.get('revision', '')
                
                return {
                    'exists': True,
                    'revision': revision[:8] if revision else 'Unknown'
                }
            else:
                self.logger.debug(f"分支不存在或無法存取: HTTP {response.status_code}")
                return {'exists': False, 'revision': ''}
                
        except Exception as e:
            self.logger.debug(f"查詢分支異常: {str(e)}")
            return {'exists': False, 'revision': ''}
        
    def _determine_source_type(self, project: Dict) -> str:
        """判斷專案的來源分支類型"""
        # 檢查 upstream 和 dest-branch
        for field in ['upstream', 'dest-branch']:
            branch_name = project.get(field, '').lower()
            if not branch_name:
                continue
            
            if 'premp' in branch_name:
                return 'premp'
            elif 'wave.backup' in branch_name or ('wave' in branch_name and 'backup' in branch_name):
                return 'mpbackup'
            elif 'wave' in branch_name and 'backup' not in branch_name:
                return 'mp'
        
        return 'master'
    
    def _handle_duplicates(self, projects: List[Dict], remove_duplicates: bool) -> tuple:
        """處理重複資料"""
        if not remove_duplicates:
            # 如果不去重複，直接返回所有專案和空的重複列表
            return projects, []
        
        # 用於檢查重複的欄位
        check_fields = ['name', 'revision', 'upstream', 'dest-branch', 'target_branch']
        
        seen = set()
        unique_projects = []
        duplicate_projects = []
        
        for project in projects:
            # 建立檢查 key
            check_values = tuple(project.get(field, '') for field in check_fields)
            
            if check_values in seen:
                duplicate_projects.append(project)
            else:
                seen.add(check_values)
                unique_projects.append(project)
        
        self.logger.info(f"去重複後：保留 {len(unique_projects)} 個，重複 {len(duplicate_projects)} 個")
        
        # 🆕 注意：這裡不重新編號，交給上層的 _renumber_projects 處理
        return unique_projects, duplicate_projects

    def _format_target_branch_columns(self, worksheet):
        """格式化目標分支相關欄位 - 增強版 (包含 target_type)"""
        try:
            from openpyxl.styles import PatternFill, Font
            from openpyxl.utils import get_column_letter
            
            # 標頭樣式：綠色底白字（但不覆蓋連結欄位和revision_diff的格式）
            green_fill = PatternFill(start_color="00B050", end_color="00B050", fill_type="solid")
            white_font = Font(color="FFFFFF", bold=True)
            
            # 內容樣式
            green_font = Font(color="00B050", bold=True)  # Y 的綠字
            red_font = Font(color="FF0000", bold=True)    # N 的紅字
            blue_font = Font(color="0070C0", bold=True)   # Tag 的藍字
            purple_font = Font(color="7030A0", bold=True) # Branch 的紫字
            black_font = Font(color="000000")             # 一般文字
            
            # 找到目標欄位的位置（排除連結欄位和revision_diff，它們有自己的格式）
            target_columns = {}
            for col_num, cell in enumerate(worksheet[1], 1):  # 第一列（標題列）
                header_value = str(cell.value) if cell.value else ''
                if header_value in ['target_branch', 'target_type', 'target_branch_exists', 'target_branch_revision']:
                    # 跳過連結欄位和revision_diff，它們已經有專門的格式
                    if header_value not in ['branch_link', 'target_branch_link', 'revision_diff']:
                        target_columns[header_value] = col_num
            
            # 格式化標頭（但不覆蓋連結欄位和revision_diff）
            for col_name, col_num in target_columns.items():
                col_letter = get_column_letter(col_num)
                header_cell = worksheet[f"{col_letter}1"]
                # 只有當不是連結欄位和revision_diff時才設定綠底白字
                if col_name not in ['branch_link', 'target_branch_link', 'revision_diff']:
                    header_cell.fill = green_fill
                    header_cell.font = white_font
            
            # 特別處理 target_type 欄位的內容
            if 'target_type' in target_columns:
                col_letter = get_column_letter(target_columns['target_type'])
                
                # 資料列：根據 Tag/Branch 設定不同顏色
                for row_num in range(2, worksheet.max_row + 1):
                    cell = worksheet[f"{col_letter}{row_num}"]
                    
                    if cell.value == 'Tag':
                        cell.font = blue_font    # Tag 用藍字
                    elif cell.value == 'Branch':
                        cell.font = purple_font  # Branch 用紫字
                    else:
                        cell.font = black_font   # 其他用黑字
            
            # 特別處理 target_branch_exists 欄位的內容
            if 'target_branch_exists' in target_columns:
                col_letter = get_column_letter(target_columns['target_branch_exists'])
                
                # 資料列：根據 Y/N 設定不同顏色
                for row_num in range(2, worksheet.max_row + 1):
                    cell = worksheet[f"{col_letter}{row_num}"]
                    
                    if cell.value == 'Y':
                        cell.font = green_font  # Y 用綠字
                    elif cell.value == 'N':
                        cell.font = red_font    # N 用紅字
                    else:
                        cell.font = black_font  # 其他用黑字（如 '-'）
            
            # 其他兩個欄位的內容保持黑字
            for col_name in ['target_branch', 'target_branch_revision']:
                if col_name in target_columns:
                    col_letter = get_column_letter(target_columns[col_name])
                    
                    for row_num in range(2, worksheet.max_row + 1):
                        cell = worksheet[f"{col_letter}{row_num}"]
                        cell.font = black_font
            
            self.logger.info("已設定目標分支欄位格式：標頭綠底白字，內容依值設定顏色")
                
        except Exception as e:
            self.logger.error(f"格式化目標分支欄位失敗: {str(e)}")
                
    def _create_branches(self, projects: List[Dict], output_file: str, output_folder: str = None):
        """建立分支並記錄結果 - 增強版 (跳過 Tag 類型，支援 remote 判斷)"""
        try:
            self.logger.info("開始建立分支...")
            
            branch_results = []
            skipped_tags = 0
            prebuilt_count = 0
            normal_count = 0
            
            for project in projects:
                project_name = project.get('name', '')
                target_branch = project.get('target_branch', '')
                target_type = project.get('target_type', 'Branch')
                revision = project.get('revision', '')
                
                # 🆕 取得 remote 資訊
                remote = project.get('remote', '')
                
                if not all([project_name, target_branch, revision]):
                    continue
                
                # 跳過 Tag 類型的專案
                if target_type == 'Tag' or self._is_tag_reference(target_branch):
                    skipped_tags += 1
                    branch_result = {
                        'SN': len(branch_results) + 1,
                        'Project': project_name,
                        'Target_Branch': target_branch,
                        'Target_Type': 'Tag',
                        'target_branch_link': project.get('target_branch_link', ''),
                        'Revision': revision,
                        'Status': '跳過',
                        'Message': 'Tag 類型不建立分支',
                        'Already_Exists': '-',
                        'Remote': remote,
                        'Gerrit_Server': self._get_gerrit_base_url(remote)  # 🆕 記錄使用的伺服器
                    }
                    branch_results.append(branch_result)
                    continue
                
                # 🆕 根據 remote 選擇正確的 GerritManager
                if remote == 'rtk-prebuilt':
                    # 使用 prebuilt 的 Gerrit 伺服器
                    temp_gerrit = self._get_prebuilt_gerrit_manager()
                    prebuilt_count += 1
                    self.logger.debug(f"使用 rtk-prebuilt Gerrit 建立分支: {project_name}")
                else:
                    # 使用預設的 GerritManager
                    temp_gerrit = self.gerrit_manager
                    normal_count += 1
                    self.logger.debug(f"使用預設 Gerrit 建立分支: {project_name}")
                
                # 建立分支
                result = temp_gerrit.create_branch(project_name, target_branch, revision)
                
                # 記錄結果
                branch_result = {
                    'SN': len(branch_results) + 1,
                    'Project': project_name,
                    'Target_Branch': target_branch,
                    'Target_Type': 'Branch',
                    'target_branch_link': project.get('target_branch_link', ''),
                    'Revision': revision,
                    'Status': '成功' if result['success'] else '失敗',
                    'Message': result['message'],
                    'Already_Exists': '是' if result.get('exists', False) else '否',
                    'Remote': remote,
                    'Gerrit_Server': self._get_gerrit_base_url(remote)  # 🆕 記錄使用的伺服器
                }
                branch_results.append(branch_result)
                
                # 每處理 10 個專案輸出進度
                if len(branch_results) % 10 == 0:
                    self.logger.info(f"已處理 {len(branch_results)} 個分支建立")
            
            # 更新 Excel 檔案，加入分支建立狀態頁籤
            if output_folder:
                full_output_path = os.path.join(output_folder, output_file)
            else:
                full_output_path = output_file
                
            self._add_branch_status_sheet(full_output_path, branch_results)
            
            self.logger.info(f"分支建立完成，共處理 {len(branch_results)} 個專案")
            self.logger.info(f"  - 跳過 {skipped_tags} 個 Tag 類型專案")
            self.logger.info(f"  - 在 rtk-prebuilt Gerrit 處理 {prebuilt_count} 個專案")
            self.logger.info(f"  - 在預設 Gerrit 處理 {normal_count} 個專案")
            
        except Exception as e:
            self.logger.error(f"建立分支失敗: {str(e)}")
    
    def _add_branch_status_sheet(self, excel_file: str, branch_results: List[Dict]):
        """在 Excel 檔案中加入分支建立狀態頁籤 - 增強版 (包含連結、remote 和 Gerrit 伺服器)"""
        try:
            # 讀取現有的 Excel 檔案
            with pd.ExcelFile(excel_file) as xls:
                existing_sheets = {}
                for sheet_name in xls.sheet_names:
                    existing_sheets[sheet_name] = pd.read_excel(xls, sheet_name=sheet_name)
            
            # 重新寫入，加上新的頁籤
            with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
                # 寫入現有頁籤
                for sheet_name, df in existing_sheets.items():
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
                
                # 加入分支建立狀態頁籤
                if branch_results:
                    df_branch = pd.DataFrame(branch_results)
                    # 調整欄位順序
                    column_order = [
                        'SN', 'Project', 'Target_Branch', 'Target_Type', 'target_branch_link', 
                        'Revision', 'Status', 'Message', 'Already_Exists', 'Remote', 'Gerrit_Server'
                    ]
                    # 只保留存在的欄位
                    column_order = [col for col in column_order if col in df_branch.columns]
                    df_branch = df_branch[column_order]
                else:
                    df_branch = pd.DataFrame(columns=[
                        'SN', 'Project', 'Target_Branch', 'Target_Type', 'target_branch_link', 
                        'Revision', 'Status', 'Message', 'Already_Exists', 'Remote', 'Gerrit_Server'
                    ])
                
                df_branch.to_excel(writer, sheet_name='Branch 建立狀態', index=False)
                
                # 格式化所有工作表
                for sheet_name in writer.sheets:
                    worksheet = writer.sheets[sheet_name]
                    self.excel_handler._format_worksheet(worksheet)
                    
                    # 特別格式化 Branch 建立狀態頁籤
                    if sheet_name == 'Branch 建立狀態':
                        self._format_branch_status_column(worksheet)
                        # 也格式化連結欄位
                        self._format_branch_status_links(worksheet)
                        # 🆕 格式化 Remote 和 Gerrit_Server 欄位
                        self._format_remote_columns(worksheet)
            
            self.logger.info("成功加入分支建立狀態頁籤")
            
        except Exception as e:
            self.logger.error(f"加入分支狀態頁籤失敗: {str(e)}")

    def _format_branch_status_links(self, worksheet):
        """格式化分支建立狀態頁籤中的連結欄位"""
        try:
            from openpyxl.styles import PatternFill, Font
            from openpyxl.utils import get_column_letter
            
            green_fill = PatternFill(start_color="00B050", end_color="00B050", fill_type="solid")
            white_font = Font(color="FFFFFF", bold=True)
            
            # 找到 target_branch_link 欄位
            for col_num, cell in enumerate(worksheet[1], 1):
                if str(cell.value) == 'target_branch_link':
                    col_letter = get_column_letter(col_num)
                    
                    # 格式化標題
                    header_cell = worksheet[f"{col_letter}1"]
                    header_cell.fill = green_fill
                    header_cell.font = white_font
                    
                    # 設定欄寬
                    worksheet.column_dimensions[col_letter].width = 80
                    
                    self.logger.debug(f"已設定 Branch 建立狀態頁籤的連結欄位格式")
                    break
                    
        except Exception as e:
            self.logger.error(f"格式化分支狀態連結欄位失敗: {str(e)}")

    def _format_remote_columns(self, worksheet):
        """
        🆕 格式化 Remote 和 Gerrit_Server 欄位
        
        Args:
            worksheet: Excel 工作表
        """
        try:
            from openpyxl.styles import PatternFill, Font
            from openpyxl.utils import get_column_letter
            
            # 定義顏色
            purple_fill = PatternFill(start_color="7030A0", end_color="7030A0", fill_type="solid")  # 紫底
            white_font = Font(color="FFFFFF", bold=True)  # 白字
            purple_font = Font(color="7030A0", bold=True)  # 紫字（用於 rtk-prebuilt）
            black_font = Font(color="000000")  # 黑字（用於其他）
            
            # 找到 Remote 和 Gerrit_Server 欄位的位置
            remote_col = None
            server_col = None
            
            for col_num, cell in enumerate(worksheet[1], 1):  # 標題列
                header_value = str(cell.value) if cell.value else ''
                if header_value == 'Remote':
                    remote_col = col_num
                elif header_value == 'Gerrit_Server':
                    server_col = col_num
            
            # 格式化 Remote 欄位（紫底白字標題）
            if remote_col:
                col_letter = get_column_letter(remote_col)
                
                # 格式化標題
                header_cell = worksheet[f"{col_letter}1"]
                header_cell.fill = purple_fill
                header_cell.font = white_font
                
                # 格式化資料列（rtk-prebuilt 用紫字，其他用黑字）
                for row_num in range(2, worksheet.max_row + 1):
                    cell = worksheet[f"{col_letter}{row_num}"]
                    cell_value = str(cell.value) if cell.value else ''
                    
                    if cell_value == 'rtk-prebuilt':
                        cell.font = purple_font  # rtk-prebuilt 用紫字
                    else:
                        cell.font = black_font   # 其他用黑字
            
            # 格式化 Gerrit_Server 欄位
            if server_col:
                col_letter = get_column_letter(server_col)
                
                # 設定欄寬（URL 較長）
                worksheet.column_dimensions[col_letter].width = 40
                
                # 格式化資料列（包含 mm2sd-git2 的用紫字）
                for row_num in range(2, worksheet.max_row + 1):
                    cell = worksheet[f"{col_letter}{row_num}"]
                    cell_value = str(cell.value) if cell.value else ''
                    
                    if 'mm2sd-git2' in cell_value:
                        cell.font = purple_font  # mm2sd-git2 用紫字
                    else:
                        cell.font = black_font   # 其他用黑字
            
            self.logger.debug("已設定 Remote 和 Gerrit_Server 欄位格式")
            
        except Exception as e:
            self.logger.error(f"格式化 Remote 欄位失敗: {str(e)}")

    def _format_branch_status_column(self, worksheet):
        """格式化分支建立狀態欄位"""
        try:
            from openpyxl.styles import PatternFill, Font
            from openpyxl.utils import get_column_letter
            
            # 狀態顏色設定
            status_colors = {
                '成功': {'fill': PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid"),
                        'font': Font(color="006100", bold=True)},
                '失敗': {'fill': PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid"),
                        'font': Font(color="9C0006", bold=True)},
                '跳過': {'fill': PatternFill(start_color="DDEBF7", end_color="DDEBF7", fill_type="solid"),
                        'font': Font(color="0070C0", bold=True)}
            }
            
            # 找到 Status 欄位
            status_col = None
            for col_num, cell in enumerate(worksheet[1], 1):
                if cell.value == 'Status':
                    status_col = col_num
                    break
            
            if status_col:
                col_letter = get_column_letter(status_col)
                
                # 格式化資料列
                for row_num in range(2, worksheet.max_row + 1):
                    cell = worksheet[f"{col_letter}{row_num}"]
                    status = str(cell.value) if cell.value else ''
                    
                    if status in status_colors:
                        cell.fill = status_colors[status]['fill']
                        cell.font = status_colors[status]['font']
                
                self.logger.info("已設定分支建立狀態欄位格式")
            
        except Exception as e:
            self.logger.error(f"格式化分支建立狀態欄位失敗: {str(e)}")