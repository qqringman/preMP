"""
功能二：透過 manifest.xml 建立分支映射表 - 增強版
建立一張 mapping 的 branch table (manifest_projects.xlsx) 並建立相關 branch (可選)
新增：支援 refs/tags/ 的 Tag 處理邏輯
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
    """功能二：建立分支映射表 - 增強版 (支援 Tag)"""
    
    def __init__(self):
        self.logger = logger
        self.excel_handler = ExcelHandler()
        self.gerrit_manager = GerritManager()
    
    def process(self, input_file: str, process_type: str, output_file: str, 
            remove_duplicates: bool = False, create_branches: bool = False,
            check_branch_exists: bool = False, output_folder: str = None) -> bool:
        """
        處理功能二的主要邏輯 - 增強版
        
        Args:
            input_file: 輸入的 manifest.xml
            process_type: 處理類型 (master_vs_premp, premp_vs_mp, mp_vs_mpbackup)
            output_file: 輸出檔案名稱
            remove_duplicates: 是否去除重複
            create_branches: 是否建立分支
            check_branch_exists: 是否檢查分支存在性
            output_folder: 輸出資料夾路徑
            
        Returns:
            是否處理成功
        """
        try:
            self.logger.info("=== 開始執行功能二：建立分支映射表 (增強版) ===")
            self.logger.info(f"輸入檔案: {input_file}")
            self.logger.info(f"處理類型: {process_type}")
            self.logger.info(f"輸出檔案: {output_file}")
            self.logger.info(f"輸出資料夾: {output_folder or '預設'}")
            self.logger.info(f"檢查分支存在性: {'是' if check_branch_exists else '否'}")
            
            # 解析 manifest.xml
            projects = self._parse_manifest(input_file)
            if not projects:
                self.logger.error("無法解析 manifest 檔案或檔案為空")
                return False
            
            self.logger.info(f"成功解析 {len(projects)} 個專案")
            
            # 轉換分支名稱
            converted_projects = self._convert_projects(projects, process_type, check_branch_exists)
            
            # 處理重複資料
            final_projects, duplicate_projects = self._handle_duplicates(
                converted_projects, remove_duplicates
            )
            
            # 寫入 Excel
            self._write_excel(final_projects, duplicate_projects, output_file, output_folder)
            
            # 建立分支（如果需要，但跳過 Tag 類型）
            if create_branches:
                self._create_branches(final_projects, output_file, output_folder)
            
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
    
    def _write_excel(self, projects: List[Dict], duplicate_projects: List[Dict], 
                output_file: str, output_folder: str = None):
        """寫入 Excel 檔案 - 增強版 (新增 target_type 欄位)"""
        try:
            # 處理輸出檔案路徑
            if not output_file:
                raise ValueError("輸出檔案名稱不能為空")
            
            # 處理輸出資料夾
            if output_folder:
                # 確保輸出資料夾存在
                utils.ensure_dir(output_folder)
                # 組合完整路徑
                full_output_path = os.path.join(output_folder, output_file)
            else:
                # 如果沒有指定資料夾，檢查檔案名稱是否包含路徑
                output_dir = os.path.dirname(output_file)
                if not output_dir:
                    output_file = os.path.join('.', output_file)
                    output_dir = '.'
                
                # 確保輸出目錄存在
                utils.ensure_dir(output_dir)
                full_output_path = output_file
            
            self.logger.info(f"寫入 Excel 檔案: {full_output_path}")
            
            with pd.ExcelWriter(full_output_path, engine='openpyxl') as writer:
                # 主要資料頁籤
                if projects:
                    df_main = pd.DataFrame(projects)
                    # 確保欄位順序（包含新欄位 target_type）
                    column_order = ['SN', 'name', 'revision', 'upstream', 'dest-branch', 
                                'target_branch', 'target_type', 'target_branch_exists', 'target_branch_revision']
                    if 'groups' in df_main.columns:
                        column_order.append('groups')
                    if 'path' in df_main.columns:
                        column_order.append('path')
                    
                    # 只保留存在的欄位
                    column_order = [col for col in column_order if col in df_main.columns]
                    df_main = df_main[column_order]
                else:
                    df_main = pd.DataFrame(columns=['SN', 'name', 'revision', 'upstream', 'dest-branch', 
                                                'target_branch', 'target_type', 'target_branch_exists', 'target_branch_revision'])
                
                df_main.to_excel(writer, sheet_name='專案列表', index=False)
                
                # 重複資料頁籤（只有在有重複資料時才建立）
                if duplicate_projects:
                    df_dup = pd.DataFrame(duplicate_projects)
                    if 'SN' in df_dup.columns:
                        df_dup['SN'] = range(1, len(df_dup) + 1)
                    
                    # 確保重複頁籤也有相同的欄位順序
                    dup_column_order = ['SN', 'name', 'revision', 'upstream', 'dest-branch', 
                                    'target_branch', 'target_type', 'target_branch_exists', 'target_branch_revision']
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
            
            self.logger.info(f"成功寫入 Excel 檔案: {full_output_path}")
            self.logger.info(f"建立的頁籤: {', '.join(created_sheets)}")
            
        except Exception as e:
            self.logger.error(f"寫入 Excel 檔案失敗: {str(e)}")
            raise

    def _format_target_branch_columns(self, worksheet):
        """格式化目標分支相關欄位 - 增強版 (包含 target_type)"""
        try:
            from openpyxl.styles import PatternFill, Font
            from openpyxl.utils import get_column_letter
            
            # 標頭樣式：綠色底白字
            green_fill = PatternFill(start_color="00B050", end_color="00B050", fill_type="solid")
            white_font = Font(color="FFFFFF", bold=True)
            
            # 內容樣式
            green_font = Font(color="00B050", bold=True)  # Y 的綠字
            red_font = Font(color="FF0000", bold=True)    # N 的紅字
            blue_font = Font(color="0070C0", bold=True)   # Tag 的藍字
            purple_font = Font(color="7030A0", bold=True) # Branch 的紫字
            black_font = Font(color="000000")             # 一般文字
            
            # 找到目標欄位的位置
            target_columns = {}
            for col_num, cell in enumerate(worksheet[1], 1):  # 第一列（標題列）
                if cell.value in ['target_branch', 'target_type', 'target_branch_exists', 'target_branch_revision']:
                    target_columns[cell.value] = col_num
            
            # 格式化標頭（綠色底白字）
            for col_name, col_num in target_columns.items():
                col_letter = get_column_letter(col_num)
                header_cell = worksheet[f"{col_letter}1"]
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
        """在 Excel 檔案中加入分支建立狀態頁籤 - 增強版 (包含 Target_Type)"""
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
                        'SN', 'Project', 'Target_Branch', 'Target_Type', 'Revision', 'Status', 'Message', 'Already_Exists'
                    ])
                
                df_branch.to_excel(writer, sheet_name='Branch 建立狀態', index=False)
                
                # 格式化所有工作表
                for sheet_name in writer.sheets:
                    worksheet = writer.sheets[sheet_name]
                    self.excel_handler._format_worksheet(worksheet)
                    
                    # 特別格式化 Branch 建立狀態頁籤
                    if sheet_name == 'Branch 建立狀態':
                        self._format_branch_status_column(worksheet)
            
            self.logger.info("成功加入分支建立狀態頁籤")
            
        except Exception as e:
            self.logger.error(f"加入分支狀態頁籤失敗: {str(e)}")

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