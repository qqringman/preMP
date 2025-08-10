"""
功能二：透過 manifest.xml 建立分支映射表
建立一張 mapping 的 branch table (manifest_projects.xlsx) 並建立相關 branch (可選)
"""
import os
import xml.etree.ElementTree as ET
import pandas as pd
from typing import Dict, List, Any, Optional
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
    """功能二：建立分支映射表"""
    
    def __init__(self):
        self.logger = logger
        self.excel_handler = ExcelHandler()
        self.gerrit_manager = GerritManager()
    
    def process(self, input_file: str, process_type: str, output_file: str, 
                remove_duplicates: bool = False, create_branches: bool = False) -> bool:
        """
        處理功能二的主要邏輯
        
        Args:
            input_file: 輸入的 manifest.xml
            process_type: 處理類型 (master_vs_premp, premp_vs_mp, mp_vs_mpbackup)
            output_file: 輸出檔案名稱
            remove_duplicates: 是否去除重複
            create_branches: 是否建立分支
            
        Returns:
            是否處理成功
        """
        try:
            self.logger.info("=== 開始執行功能二：建立分支映射表 ===")
            self.logger.info(f"輸入檔案: {input_file}")
            self.logger.info(f"處理類型: {process_type}")
            self.logger.info(f"輸出檔案: {output_file}")
            
            # 解析 manifest.xml
            projects = self._parse_manifest(input_file)
            if not projects:
                self.logger.error("無法解析 manifest 檔案或檔案為空")
                return False
            
            self.logger.info(f"成功解析 {len(projects)} 個專案")
            
            # 轉換分支名稱
            converted_projects = self._convert_projects(projects, process_type)
            
            # 處理重複資料
            final_projects, duplicate_projects = self._handle_duplicates(
                converted_projects, remove_duplicates
            )
            
            # 寫入 Excel
            self._write_excel(final_projects, duplicate_projects, output_file)
            
            # 建立分支（如果需要）
            if create_branches:
                self._create_branches(final_projects, output_file)
            
            self.logger.info(f"=== 功能二執行完成，輸出檔案：{output_file} ===")
            return True
            
        except Exception as e:
            self.logger.error(f"功能二執行失敗: {str(e)}")
            return False
    
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
                    'groups': project.get('groups', '')
                }
                projects.append(project_data)
            
            self.logger.info(f"解析完成，共 {len(projects)} 個專案")
            return projects
            
        except Exception as e:
            self.logger.error(f"解析 manifest 檔案失敗: {str(e)}")
            return []
    
    def _convert_projects(self, projects: List[Dict], process_type: str) -> List[Dict]:
        """轉換專案的分支名稱"""
        converted_projects = []
        
        for i, project in enumerate(projects, 1):
            converted_project = project.copy()
            converted_project['SN'] = i
            
            # 判斷來源分支類型
            source_type = self._determine_source_type(project)
            
            # 根據處理類型轉換目標分支
            target_branch = self._convert_branch_by_type(project, process_type)
            converted_project['target_branch'] = target_branch
            
            # 檢查目標分支是否存在並取得 revision
            if target_branch:
                exists_info = self._check_target_branch_exists(project.get('name', ''), target_branch)
                converted_project['target_branch_exists'] = exists_info['exists_status']
                converted_project['target_branch_revision'] = exists_info['revision']
            else:
                converted_project['target_branch_exists'] = 'N'
                converted_project['target_branch_revision'] = ''
            
            converted_projects.append(converted_project)
        
        return converted_projects

    def _check_target_branch_exists(self, project_name: str, target_branch: str) -> Dict[str, str]:
        """檢查目標分支是否存在並取得 revision - 改進版"""
        result = {
            'exists_status': 'N',
            'revision': ''
        }
        
        try:
            if not project_name or not target_branch:
                return result
            
            # 使用新的檢查方法
            branch_info = self.gerrit_manager.check_branch_exists_and_get_revision(project_name, target_branch)
            
            if branch_info['exists']:
                result['exists_status'] = 'Y'
                result['revision'] = branch_info['revision'] if branch_info['revision'] else 'Unknown'
                
                self.logger.debug(f"分支存在: {project_name} - {target_branch} ({result['revision']}) via {branch_info['method']}")
            else:
                self.logger.debug(f"分支不存在: {project_name} - {target_branch}")
                
        except Exception as e:
            self.logger.warning(f"檢查分支存在性失敗: {project_name} - {target_branch}: {str(e)}")
            result['exists_status'] = 'N'
        
        return result

    def _get_branch_revision(self, project_name: str, branch_name: str) -> str:
        """取得分支的 revision"""
        try:
            import urllib.parse
            
            # URL 編碼
            encoded_project = urllib.parse.quote(project_name, safe='')
            encoded_branch = urllib.parse.quote(f"refs/heads/{branch_name}", safe='')
            
            # 嘗試多個 API 路徑
            api_paths = [
                f"{self.gerrit_manager.api_url}/projects/{encoded_project}/branches/{encoded_branch}",
                f"{self.gerrit_manager.base_url}/a/projects/{encoded_project}/branches/{encoded_branch}",
                f"{self.gerrit_manager.base_url}/gerrit/a/projects/{encoded_project}/branches/{encoded_branch}"
            ]
            
            for api_path in api_paths:
                try:
                    response = self.gerrit_manager._make_request(api_path, timeout=10)
                    
                    if response.status_code == 200:
                        content = response.text
                        if content.startswith(")]}'\n"):
                            content = content[5:]
                        
                        import json
                        branch_info = json.loads(content)
                        revision = branch_info.get('revision', '')
                        
                        if revision:
                            return revision[:8]  # 只取前8個字符 
                except Exception:
                    continue
            return ''
        except Exception as e:
            self.logger.warning(f"取得分支 revision 失敗: {str(e)}")
            return ''
            
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
        """根據處理類型轉換分支名稱"""
        try:
            # 優先使用 dest-branch，其次使用 upstream
            source_branch = project.get('dest-branch') or project.get('upstream', '')
            
            if not source_branch:
                return ''
            
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
    
    def _write_excel(self, projects: List[Dict], duplicate_projects: List[Dict], output_file: str):
        """寫入 Excel 檔案"""
        try:
            # 處理輸出檔案路徑
            if not output_file:
                raise ValueError("輸出檔案名稱不能為空")
            
            # 如果沒有指定目錄，使用當前目錄
            output_dir = os.path.dirname(output_file)
            if not output_dir:
                output_file = os.path.join('.', output_file)
                output_dir = '.'
            
            # 確保輸出目錄存在
            utils.ensure_dir(output_dir)
            
            self.logger.info(f"寫入 Excel 檔案: {output_file}")
            
            with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
                # 主要資料頁籤
                if projects:
                    df_main = pd.DataFrame(projects)
                    # 確保欄位順序（包含新欄位）
                    column_order = ['SN', 'name', 'revision', 'upstream', 'dest-branch', 
                                'target_branch', 'target_branch_exists', 'target_branch_revision']
                    if 'groups' in df_main.columns:
                        column_order.append('groups')
                    if 'path' in df_main.columns:
                        column_order.append('path')
                    
                    # 只保留存在的欄位
                    column_order = [col for col in column_order if col in df_main.columns]
                    df_main = df_main[column_order]
                else:
                    df_main = pd.DataFrame(columns=['SN', 'name', 'revision', 'upstream', 'dest-branch', 
                                                'target_branch', 'target_branch_exists', 'target_branch_revision'])
                
                df_main.to_excel(writer, sheet_name='專案列表', index=False)
                
                # 重複資料頁籤（只有在有重複資料時才建立）
                if duplicate_projects:
                    df_dup = pd.DataFrame(duplicate_projects)
                    if 'SN' in df_dup.columns:
                        df_dup['SN'] = range(1, len(df_dup) + 1)
                    
                    # 確保重複頁籤也有相同的欄位順序
                    dup_column_order = ['SN', 'name', 'revision', 'upstream', 'dest-branch', 
                                    'target_branch', 'target_branch_exists', 'target_branch_revision']
                    if 'groups' in df_dup.columns:
                        dup_column_order.append('groups')
                    if 'path' in df_dup.columns:
                        dup_column_order.append('path')
                    
                    dup_column_order = [col for col in dup_column_order if col in df_dup.columns]
                    df_dup = df_dup[dup_column_order]
                    
                    df_dup.to_excel(writer, sheet_name='重覆', index=False)
                    self.logger.info(f"建立 '重覆' 頁籤，共 {len(duplicate_projects)} 筆資料")
                else:
                    self.logger.info("沒有重複資料，跳過 '重覆' 頁籤")
                
                # 格式化所有工作表
                for sheet_name in writer.sheets:
                    worksheet = writer.sheets[sheet_name]
                    self.excel_handler._format_worksheet(worksheet)
                    
                    # 特別處理目標分支相關欄位的樣式
                    self._format_target_branch_columns(worksheet)
            
            # 統計頁籤資訊
            created_sheets = ['專案列表']
            if duplicate_projects:
                created_sheets.append('重覆')
            
            self.logger.info(f"成功寫入 Excel 檔案: {output_file}")
            self.logger.info(f"建立的頁籤: {', '.join(created_sheets)}")
            
        except Exception as e:
            self.logger.error(f"寫入 Excel 檔案失敗: {str(e)}")
            raise

    def _format_target_branch_columns(self, worksheet):
        """格式化目標分支相關欄位"""
        try:
            from openpyxl.styles import PatternFill, Font
            from openpyxl.utils import get_column_letter
            
            # 綠色底白字樣式（用於三個目標分支欄位）
            green_fill = PatternFill(start_color="00B050", end_color="00B050", fill_type="solid")
            white_font = Font(color="FFFFFF", bold=True)
            
            # Y 的綠字樣式
            green_font = Font(color="00B050", bold=True)
            
            # N 的紅字樣式  
            red_font = Font(color="FF0000", bold=True)
            
            # 找到目標欄位的位置
            target_columns = {}
            for col_num, cell in enumerate(worksheet[1], 1):  # 第一列（標題列）
                if cell.value in ['target_branch', 'target_branch_exists', 'target_branch_revision']:
                    target_columns[cell.value] = col_num
            
            # 格式化 target_branch 和 target_branch_revision 欄位（綠色底白字）
            for col_name in ['target_branch', 'target_branch_revision']:
                if col_name in target_columns:
                    col_letter = get_column_letter(target_columns[col_name])
                    
                    for row_num in range(1, worksheet.max_row + 1):
                        cell = worksheet[f"{col_letter}{row_num}"]
                        cell.fill = green_fill
                        cell.font = white_font
                    
                    self.logger.info(f"已將 {col_name} 欄位 ({col_letter}) 設定為綠色底白字")
            
            # 特別格式化 target_branch_exists 欄位
            if 'target_branch_exists' in target_columns:
                col_letter = get_column_letter(target_columns['target_branch_exists'])
                
                # 標題列：綠色底白字
                header_cell = worksheet[f"{col_letter}1"]
                header_cell.fill = green_fill
                header_cell.font = white_font
                
                # 資料列：根據 Y/N 設定不同顏色
                for row_num in range(2, worksheet.max_row + 1):
                    cell = worksheet[f"{col_letter}{row_num}"]
                    cell.fill = green_fill  # 背景還是綠色
                    
                    if cell.value == 'Y':
                        cell.font = Font(color="FFFFFF", bold=True)  # Y 用白字
                    elif cell.value == 'N':
                        cell.font = Font(color="FFFF00", bold=True)   # N 用黃字（在綠底上比較明顯）
                    else:
                        cell.font = white_font
                
                self.logger.info(f"已將 target_branch_exists 欄位 ({col_letter}) 設定特殊格式")
                
        except Exception as e:
            self.logger.error(f"格式化目標分支欄位失敗: {str(e)}")
                
    def _create_branches(self, projects: List[Dict], output_file: str):
        """建立分支並記錄結果"""
        try:
            self.logger.info("開始建立分支...")
            
            branch_results = []
            
            for project in projects:
                project_name = project.get('name', '')
                target_branch = project.get('target_branch', '')
                revision = project.get('revision', '')
                
                if not all([project_name, target_branch, revision]):
                    continue
                
                # 建立分支
                result = self.gerrit_manager.create_branch(project_name, target_branch, revision)
                
                # 記錄結果
                branch_result = {
                    'SN': len(branch_results) + 1,
                    'Project': project_name,
                    'Target_Branch': target_branch,
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
            self._add_branch_status_sheet(output_file, branch_results)
            
            self.logger.info(f"分支建立完成，共處理 {len(branch_results)} 個分支")
            
        except Exception as e:
            self.logger.error(f"建立分支失敗: {str(e)}")
    
    def _add_branch_status_sheet(self, excel_file: str, branch_results: List[Dict]):
        """在 Excel 檔案中加入分支建立狀態頁籤"""
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
                        'SN', 'Project', 'Target_Branch', 'Revision', 'Status', 'Message', 'Already_Exists'
                    ])
                
                df_branch.to_excel(writer, sheet_name='Branch 建立狀態', index=False)
                
                # 格式化所有工作表
                for sheet_name in writer.sheets:
                    worksheet = writer.sheets[sheet_name]
                    self.excel_handler._format_worksheet(worksheet)
            
            self.logger.info("成功加入分支建立狀態頁籤")
            
        except Exception as e:
            self.logger.error(f"加入分支狀態頁籤失敗: {str(e)}")