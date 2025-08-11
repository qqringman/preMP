"""
功能二：透過 manifest.xml 建立分支映射表 - 增強版
建立一張 mapping 的 branch table (manifest_projects.xlsx) 並建立相關 branch (可選)
新增：支援 refs/tags/ 的 Tag 處理邏輯 + branch/tag 連結功能
"""
import os
import xml.etree.ElementTree as ET
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple
import utils
import sys

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

logger = utils.setup_logger(__name__)

class FeatureTwo:
    """功能二：建立分支映射表 - 增強版 (支援 Tag + 連結功能)"""
    
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
            
            # 步驟 2: 轉換專案（使用原有邏輯）
            converted_projects = self._convert_projects(projects, process_type, check_branch_exists)
            
            # 步驟 3: 🆕 添加連結資訊
            projects_with_links = self._add_links_to_projects(converted_projects)
            
            # 步驟 4: 處理重複資料
            unique_projects, duplicate_projects = self._handle_duplicates(projects_with_links, remove_duplicates)
            
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

    def _build_gerrit_link(self, project_name: str, revision: str, target_type: str) -> str:
        """
        建立 Gerrit branch/tag 連結
        
        Args:
            project_name: 專案名稱
            revision: 分支或標籤名稱
            target_type: 'branch' 或 'tag'
            
        Returns:
            Gerrit 連結 URL
        """
        try:
            if not project_name or not revision:
                return ""
            
            base_url = "https://mm2sd.rtkbf.com/gerrit/plugins/gitiles"
            
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
            
            self.logger.debug(f"建立 {target_type} 連結: {project_name} -> {link}")
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
        import re
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

    def _add_links_to_projects(self, projects: List[Dict]) -> List[Dict]:
        """
        為專案添加 branch/tag 連結資訊
        
        Args:
            projects: 專案列表
            
        Returns:
            包含連結資訊的專案列表
        """
        projects_with_links = []
        
        for project in projects:
            enhanced_project = project.copy()
            
            project_name = project.get('name', '')
            
            # 來源 revision 資訊（從 revision, upstream, dest-branch 中取得）
            source_revision = project.get('revision', '') or project.get('upstream', '') or project.get('dest-branch', '')
            source_type = self._determine_revision_type(source_revision)
            
            # 目標 branch 資訊
            target_branch = project.get('target_branch', '')
            target_type = project.get('target_type', 'Branch')
            
            # 🆕 建立 branch_link (藍底白字) - 來源 revision 的連結
            branch_link = self._build_gerrit_link(project_name, source_revision, source_type)
            
            # 🆕 建立 target_branch_link (綠底白字) - 目標 branch 的連結
            target_branch_link = self._build_gerrit_link(project_name, target_branch, target_type)
            
            # 添加連結欄位
            enhanced_project['branch_link'] = branch_link
            enhanced_project['target_branch_link'] = target_branch_link
            enhanced_project['source_type'] = source_type
            
            projects_with_links.append(enhanced_project)
        
        self.logger.info(f"已為 {len(projects_with_links)} 個專案添加連結資訊")
        return projects_with_links

    def _write_excel_with_links(self, projects: List[Dict], duplicate_projects: List[Dict], 
                              output_file: str, output_folder: str = None):
        """寫入 Excel 檔案 - 包含連結功能的增強版"""
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
                    
                    # 🆕 調整欄位順序：在 target_branch 左方加入 branch_link，在 target_branch_revision 右方加入 target_branch_link
                    main_column_order = [
                        'SN', 'name', 'revision', 'upstream', 'dest-branch',
                        'branch_link',  # 🆕 藍底白字
                        'target_branch', 
                        'target_type', 
                        'target_branch_exists', 
                        'target_branch_revision',
                        'target_branch_link'  # 🆕 綠底白字
                    ]
                    
                    # 添加其他可能存在的欄位
                    for col in ['groups', 'path', 'source_type']:
                        if col in df_main.columns:
                            main_column_order.append(col)
                    
                    # 只保留存在的欄位
                    main_column_order = [col for col in main_column_order if col in df_main.columns]
                    df_main = df_main[main_column_order]
                else:
                    # 空的 DataFrame 結構
                    df_main = pd.DataFrame(columns=[
                        'SN', 'name', 'revision', 'upstream', 'dest-branch', 'branch_link',
                        'target_branch', 'target_type', 'target_branch_exists', 'target_branch_revision', 'target_branch_link'
                    ])
                
                df_main.to_excel(writer, sheet_name='專案列表', index=False)
                
                # 頁籤 2: 重複專案
                if duplicate_projects:
                    df_dup = pd.DataFrame(duplicate_projects)
                    if 'SN' in df_dup.columns:
                        df_dup['SN'] = range(1, len(df_dup) + 1)
                    
                    # 🆕 重複頁籤也使用相同的欄位順序
                    dup_column_order = [
                        'SN', 'name', 'revision', 'upstream', 'dest-branch',
                        'branch_link',  # 🆕 藍底白字
                        'target_branch',
                        'target_type',
                        'target_branch_exists',
                        'target_branch_revision',
                        'target_branch_link'  # 🆕 綠底白字
                    ]
                    
                    for col in ['groups', 'path', 'source_type']:
                        if col in df_dup.columns:
                            dup_column_order.append(col)
                    
                    dup_column_order = [col for col in dup_column_order if col in df_dup.columns]
                    df_dup = df_dup[dup_column_order]
                    
                    df_dup.to_excel(writer, sheet_name='重覆', index=False)
                    self.logger.info(f"建立 '重覆' 頁籤，共 {len(duplicate_projects)} 筆資料")
                
                # 🆕 格式化所有工作表，包含連結欄位
                self._format_excel_with_links(writer)
            
            self.logger.info(f"成功寫入 Excel 檔案: {full_output_path}")
            
        except Exception as e:
            self.logger.error(f"寫入 Excel 檔案失敗: {str(e)}")
            raise

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
            white_font = Font(color="FFFFFF", bold=True)  # 白字
            
            for sheet_name in writer.sheets:
                worksheet = writer.sheets[sheet_name]
                
                # 先執行基本格式化
                self.excel_handler._format_worksheet(worksheet)
                
                # 🆕 特別格式化連結欄位
                self._format_link_columns(worksheet, blue_fill, green_fill, white_font)
                
                # 保留原有的目標分支欄位格式化
                self._format_target_branch_columns(worksheet)
                
        except Exception as e:
            self.logger.error(f"Excel 格式化失敗: {str(e)}")

    def _format_link_columns(self, worksheet, blue_fill, green_fill, white_font):
        """
        格式化連結欄位 - 新方法
        
        Args:
            worksheet: Excel 工作表
            blue_fill: 藍底填色
            green_fill: 綠底填色
            white_font: 白字字體
        """
        try:
            from openpyxl.utils import get_column_letter
            
            # 找到連結欄位的位置
            link_columns = {}
            for col_num, cell in enumerate(worksheet[1], 1):  # 標題列
                header_value = str(cell.value) if cell.value else ''
                
                if header_value == 'branch_link':
                    link_columns['branch_link'] = col_num
                elif header_value == 'target_branch_link':
                    link_columns['target_branch_link'] = col_num
            
            # 格式化 branch_link 欄位 (藍底白字)
            if 'branch_link' in link_columns:
                col_num = link_columns['branch_link']
                col_letter = get_column_letter(col_num)
                
                # 格式化標題
                header_cell = worksheet[f"{col_letter}1"]
                header_cell.fill = blue_fill
                header_cell.font = white_font
                
                # 設定欄寬
                worksheet.column_dimensions[col_letter].width = 80
                
                self.logger.debug(f"已設定 branch_link 欄位格式: 第{col_num}欄 (藍底白字)")
            
            # 格式化 target_branch_link 欄位 (綠底白字)
            if 'target_branch_link' in link_columns:
                col_num = link_columns['target_branch_link']
                col_letter = get_column_letter(col_num)
                
                # 格式化標題
                header_cell = worksheet[f"{col_letter}1"]
                header_cell.fill = green_fill
                header_cell.font = white_font
                
                # 設定欄寬
                worksheet.column_dimensions[col_letter].width = 80
                
                self.logger.debug(f"已設定 target_branch_link 欄位格式: 第{col_num}欄 (綠底白字)")
            
            self.logger.info("已完成連結欄位格式化: branch_link (藍底白字), target_branch_link (綠底白字)")
            
        except Exception as e:
            self.logger.error(f"格式化連結欄位失敗: {str(e)}")

    # ========================
    # 以下保持原有方法不變
    # ========================

    def _parse_manifest(self, input_file: str) -> List[Dict]:
        """解析 manifest.xml 檔案"""
        try:
            tree = ET.parse(input_file)
            root = tree.getroot()
            
            projects = []
            
            for project in root.findall('project'):
                project_data = {
                    'name': project.get('name', ''),
                    'path': project.get('path', ''),
                    'revision': project.get('revision', ''),
                    'upstream': project.get('upstream', ''),
                    'dest-branch': project.get('dest-branch', ''),
                    'groups': project.get('groups', ''),
                    'clone-depth': project.get('clone-depth', ''),
                    'remote': project.get('remote', '')
                }
                projects.append(project_data)
            
            self.logger.info(f"解析完成，共 {len(projects)} 個專案")
            return projects
            
        except Exception as e:
            self.logger.error(f"解析 manifest 檔案失敗: {str(e)}")
            return []
    
    def _convert_projects(self, projects: List[Dict], process_type: str, check_branch_exists: bool = False) -> List[Dict]:
        """轉換專案的分支名稱 - 增強版 (支援 Tag)"""
        converted_projects = []
        tag_count = 0
        branch_count = 0
        
        for i, project in enumerate(projects, 1):
            converted_project = project.copy()
            converted_project['SN'] = i
            
            # 判斷來源分支類型
            source_type = self._determine_source_type(project)
            
            # 根據處理類型轉換目標分支
            target_branch = self._convert_branch_by_type(project, process_type)
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
                    # 檢查 Tag 存在性
                    exists_info = self._check_target_tag_exists(project.get('name', ''), target_branch)
                else:
                    # 檢查 Branch 存在性
                    exists_info = self._check_target_branch_exists(project.get('name', ''), target_branch)
                
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

    def _is_tag_reference(self, reference: str) -> bool:
        """判斷參考是否為 Tag (以 refs/tags/ 開頭)"""
        if not reference:
            return False
        return reference.startswith('refs/tags/')

    def _check_target_tag_exists(self, project_name: str, target_tag: str) -> Dict[str, str]:
        """檢查目標 Tag 是否存在並取得 revision"""
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
            
            # 查詢 Tag
            tag_info = self.gerrit_manager.query_tag(project_name, tag_name)
            
            if tag_info['exists']:
                result['exists_status'] = 'Y'
                result['revision'] = tag_info['revision']
            
        except Exception as e:
            self.logger.debug(f"檢查 Tag 失敗: {project_name} - {target_tag}: {str(e)}")
        
        return result

    def _check_target_branch_exists(self, project_name: str, target_branch: str) -> Dict[str, str]:
        """檢查目標分支是否存在並取得 revision - 簡化版"""
        result = {
            'exists_status': 'N',
            'revision': ''
        }
        
        try:
            if not project_name or not target_branch:
                return result
            
            # 直接使用最可靠的方法
            branch_info = self._query_branch_direct(project_name, target_branch)
            
            if branch_info['exists']:
                result['exists_status'] = 'Y'
                result['revision'] = branch_info['revision']
            
        except Exception as e:
            self.logger.debug(f"檢查分支失敗: {project_name} - {target_branch}: {str(e)}")
        
        return result

    def _query_branch_direct(self, project_name: str, branch_name: str) -> Dict[str, Any]:
        """直接查詢分支 - 使用最可靠的方法"""
        try:
            import urllib.parse
            
            # URL 編碼
            encoded_project = urllib.parse.quote(project_name, safe='')
            encoded_branch = urllib.parse.quote(f"refs/heads/{branch_name}", safe='')
            
            # 使用最成功的 API 路徑
            api_url = f"{self.gerrit_manager.base_url}/gerrit/a/projects/{encoded_project}/branches/{encoded_branch}"
            
            response = self.gerrit_manager._make_request(api_url, timeout=5)
            
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
    
    def _convert_branch_by_type(self, project: Dict, process_type: str) -> str:
        """根據處理類型轉換分支名稱 - 增強版 (保持 Tag 格式)"""
        try:
            # 優先使用 dest-branch，其次使用 upstream
            source_branch = project.get('dest-branch') or project.get('upstream', '')
            
            if not source_branch:
                return ''
            
            # 如果是 Tag 參考，直接返回不做轉換
            if self._is_tag_reference(source_branch):
                self.logger.debug(f"檢測到 Tag 參考，保持原樣: {source_branch}")
                return source_branch
            
            # 根據處理類型進行轉換
            if process_type == 'master_vs_premp':
                # master -> premp
                if 'premp' not in source_branch:
                    # 簡單的轉換邏輯：替換最後的部分為 premp.google-refplus
                    parts = source_branch.split('/')
                    if len(parts) >= 3:
                        parts[-1] = 'premp.google-refplus'
                    return '/'.join(parts)
                
            elif process_type == 'premp_vs_mp':
                # premp -> mp
                return source_branch.replace('premp.google-refplus', 'mp.google-refplus.wave')
                
            elif process_type == 'mp_vs_mpbackup':
                # mp -> mpbackup
                if 'wave' in source_branch and 'backup' not in source_branch:
                    return source_branch.replace('wave', 'wave.backup')
            
            return source_branch
            
        except Exception as e:
            self.logger.error(f"轉換分支名稱失敗: {str(e)}")
            return source_branch
    
    def _handle_duplicates(self, projects: List[Dict], remove_duplicates: bool) -> tuple:
        """處理重複資料"""
        if not remove_duplicates:
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
        
        return unique_projects, duplicate_projects

    def _format_target_branch_columns(self, worksheet):
        """格式化目標分支相關欄位 - 增強版 (包含 target_type)"""
        try:
            from openpyxl.styles import PatternFill, Font
            from openpyxl.utils import get_column_letter
            
            # 標頭樣式：綠色底白字（但不覆蓋連結欄位的格式）
            green_fill = PatternFill(start_color="00B050", end_color="00B050", fill_type="solid")
            white_font = Font(color="FFFFFF", bold=True)
            
            # 內容樣式
            green_font = Font(color="00B050", bold=True)  # Y 的綠字
            red_font = Font(color="FF0000", bold=True)    # N 的紅字
            blue_font = Font(color="0070C0", bold=True)   # Tag 的藍字
            purple_font = Font(color="7030A0", bold=True) # Branch 的紫字
            black_font = Font(color="000000")             # 一般文字
            
            # 找到目標欄位的位置（排除連結欄位，它們有自己的格式）
            target_columns = {}
            for col_num, cell in enumerate(worksheet[1], 1):  # 第一列（標題列）
                header_value = str(cell.value) if cell.value else ''
                if header_value in ['target_branch', 'target_type', 'target_branch_exists', 'target_branch_revision']:
                    # 跳過連結欄位，它們已經有專門的格式
                    if header_value not in ['branch_link', 'target_branch_link']:
                        target_columns[header_value] = col_num
            
            # 格式化標頭（但不覆蓋連結欄位）
            for col_name, col_num in target_columns.items():
                col_letter = get_column_letter(col_num)
                header_cell = worksheet[f"{col_letter}1"]
                # 只有當不是連結欄位時才設定綠底白字
                if col_name not in ['branch_link', 'target_branch_link']:
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
        """建立分支並記錄結果 - 增強版 (跳過 Tag 類型)"""
        try:
            self.logger.info("開始建立分支...")
            
            branch_results = []
            skipped_tags = 0
            
            for project in projects:
                project_name = project.get('name', '')
                target_branch = project.get('target_branch', '')
                target_type = project.get('target_type', 'Branch')
                revision = project.get('revision', '')
                
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
                        'target_branch_link': project.get('target_branch_link', ''),  # 🆕 包含連結
                        'Revision': revision,
                        'Status': '跳過',
                        'Message': 'Tag 類型不建立分支',
                        'Already_Exists': '-'
                    }
                    branch_results.append(branch_result)
                    continue
                
                # 建立分支
                result = self.gerrit_manager.create_branch(project_name, target_branch, revision)
                
                # 記錄結果
                branch_result = {
                    'SN': len(branch_results) + 1,
                    'Project': project_name,
                    'Target_Branch': target_branch,
                    'Target_Type': 'Branch',
                    'target_branch_link': project.get('target_branch_link', ''),  # 🆕 包含連結
                    'Revision': revision,
                    'Status': '成功' if result['success'] else '失敗',
                    'Message': result['message'],
                    'Already_Exists': '是' if result.get('exists', False) else '否'
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
            self.logger.info(f"跳過 {skipped_tags} 個 Tag 類型專案")
            
        except Exception as e:
            self.logger.error(f"建立分支失敗: {str(e)}")
    
    def _add_branch_status_sheet(self, excel_file: str, branch_results: List[Dict]):
        """在 Excel 檔案中加入分支建立狀態頁籤 - 增強版 (包含連結)"""
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
                else:
                    df_branch = pd.DataFrame(columns=[
                        'SN', 'Project', 'Target_Branch', 'Target_Type', 'target_branch_link', 'Revision', 'Status', 'Message', 'Already_Exists'
                    ])
                
                df_branch.to_excel(writer, sheet_name='Branch 建立狀態', index=False)
                
                # 格式化所有工作表
                for sheet_name in writer.sheets:
                    worksheet = writer.sheets[sheet_name]
                    self.excel_handler._format_worksheet(worksheet)
                    
                    # 特別格式化 Branch 建立狀態頁籤
                    if sheet_name == 'Branch 建立狀態':
                        self._format_branch_status_column(worksheet)
                        # 🆕 也格式化連結欄位
                        self._format_branch_status_links(worksheet)
            
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