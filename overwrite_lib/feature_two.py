"""
功能二：透過 manifest.xml 建立分支映射表 - 修正版 (統一建立分支報告格式)
🔥 修正：統一建立分支與不建立分支時的報告格式，確保表頭顏色和公式一致
🔥 修正：Branch 建立狀態頁籤的欄位名稱改為小寫，與專案列表頁籤一致
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
    """功能二：建立分支映射表 - 修正版 (統一建立分支報告格式)"""
    
    def __init__(self):
        self.logger = logger
        self.excel_handler = ExcelHandler()
        self.gerrit_manager = GerritManager()
    
    def process(self, input_file: str, process_type: str, output_filename: str, 
                remove_duplicates: bool, create_branches: bool, check_branch_exists: bool,
                output_folder: str = './output', force_update_branches: bool = False) -> bool:
        """
        處理功能二的主要邏輯 - 修正版（統一報告格式）
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
            self.logger.info(f"🆕 強制更新分支: {force_update_branches}")
            
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
            
            # 步驟 3: 添加連結資訊
            projects_with_links = self._add_links_to_projects(converted_projects)
            
            # 步驟 4: 處理重複資料
            unique_projects, duplicate_projects = self._handle_duplicates(projects_with_links, remove_duplicates)
            
            # 步驟 4.5: 重新編號 SN（避免跳號）
            unique_projects = self._renumber_projects(unique_projects)
            duplicate_projects = self._renumber_projects(duplicate_projects)
            
            self.logger.info(f"處理完成: {len(unique_projects)} 個專案, {len(duplicate_projects)} 個重複")
            
            # 🔥 步驟 5: 統一生成基本 Excel 報告（無論是否建立分支都使用相同邏輯）
            self._write_excel_unified_basic(unique_projects, duplicate_projects, output_filename, output_folder)
            
            # 🔥 步驟 6: 如果選擇建立分支，執行分支建立並添加狀態頁籤
            if create_branches:
                self.logger.info("🚀 開始執行分支建立流程...")
                branch_results = self._create_branches(unique_projects, output_filename, output_folder, force_update_branches)
                # 添加分支建立狀態頁籤
                self._add_branch_status_sheet_with_revision(output_filename, output_folder, branch_results)
                self.logger.info("✅ 分支建立流程完成")
            else:
                self.logger.info("⏭️ 跳過分支建立流程")
            
            excel_path = os.path.join(output_folder, output_filename)
            self.logger.info(f"=== 功能二執行完成，Excel 檔案：{excel_path} ===")
            return True
            
        except Exception as e:
            self.logger.error(f"功能二執行失敗: {str(e)}")
            return False

    def _add_branch_status_sheet_with_revision(self, output_file: str, output_folder: str, branch_results: List[Dict]):
        """
        🔥 修正方法：添加分支建立狀態頁籤 - 使用 openpyxl 保留公式
        """
        try:
            from openpyxl import load_workbook
            from openpyxl.utils.dataframe import dataframe_to_rows
            
            full_output_path = os.path.join(output_folder, output_file)
            
            self.logger.info(f"🔧 使用 openpyxl 添加分支狀態頁籤（保留公式）: {full_output_path}")
            
            # 🔥 使用 openpyxl 載入現有工作簿（保留公式）
            workbook = load_workbook(full_output_path)
            
            # 🔥 加入分支建立狀態頁籤
            if branch_results:
                df_branch = pd.DataFrame(branch_results)
                
                # 🔥 調整欄位順序，在 Project 右邊添加 revision
                column_order = [
                    'SN', 'Project', 'revision',  # 🔥 新添加 revision 欄位
                    'target_branch',        # 🔥 改為小寫，綠底白字
                    'target_type',          # 🔥 改為小寫，綠底白字
                    'target_branch_link',   # 🔥 綠底白字
                    'target_branch_revision',  # 🔥 改名並改為小寫，綠底白字
                    'Status', 'Message', 'Already_Exists', 'Force_Update',
                    'Remote', 'Gerrit_Server'
                ]
                
                # 🔥 映射原始欄位名稱到新的欄位名稱
                if 'Target_Branch' in df_branch.columns:
                    df_branch = df_branch.rename(columns={'Target_Branch': 'target_branch'})
                if 'Target_Type' in df_branch.columns:
                    df_branch = df_branch.rename(columns={'Target_Type': 'target_type'})
                if 'Revision' in df_branch.columns:
                    df_branch = df_branch.rename(columns={'Revision': 'target_branch_revision'})
                
                # 只保留存在的欄位
                column_order = [col for col in column_order if col in df_branch.columns]
                df_branch = df_branch[column_order]
            else:
                # 🔥 空的 DataFrame 結構（包含 revision 欄位）
                df_branch = pd.DataFrame(columns=[
                    'SN', 'Project', 'revision', 'target_branch', 'target_type', 'target_branch_link', 
                    'target_branch_revision', 'Status', 'Message', 'Already_Exists', 'Force_Update',
                    'Remote', 'Gerrit_Server'
                ])
            
            # 🔥 創建新的工作表
            branch_sheet = workbook.create_sheet('Branch 建立狀態')
            
            # 🔥 寫入資料到新工作表
            for r in dataframe_to_rows(df_branch, index=False, header=True):
                branch_sheet.append(r)
            
            # 🔥 格式化新的分支狀態頁籤
            self._format_branch_status_sheet_in_workbook(workbook, 'Branch 建立狀態')
            
            # 🔥 保存工作簿（保留原有公式）
            workbook.save(full_output_path)
            workbook.close()
            
            self.logger.info("✅ 成功加入包含 revision 欄位的分支建立狀態頁籤（保留公式）")
            
        except Exception as e:
            self.logger.error(f"加入分支狀態頁籤失敗: {str(e)}")

    def _format_branch_status_sheet_in_workbook(self, workbook, sheet_name):
        """
        🔥 新方法：在 workbook 中格式化分支建立狀態頁籤
        """
        try:
            from openpyxl.styles import PatternFill, Font
            from openpyxl.utils import get_column_letter
            
            if sheet_name not in workbook.sheetnames:
                self.logger.warning(f"⚠️ 工作表 '{sheet_name}' 不存在")
                return
                
            worksheet = workbook[sheet_name]
            
            # 定義顏色
            blue_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
            green_fill = PatternFill(start_color="00B050", end_color="00B050", fill_type="solid")
            orange_fill = PatternFill(start_color="ED7D31", end_color="ED7D31", fill_type="solid")
            purple_fill = PatternFill(start_color="7030A0", end_color="7030A0", fill_type="solid")
            white_font = Font(color="FFFFFF", bold=True)
            
            # 基本格式化
            self.excel_handler._format_worksheet(worksheet)
            
            # 分支建立狀態頁籤：特殊格式（包含 revision 欄位）
            self._format_branch_status_sheet_with_revision(worksheet, green_fill, purple_fill, orange_fill, white_font)
            
            self.logger.info(f"✅ 已格式化分支狀態頁籤: {sheet_name}")
            
        except Exception as e:
            self.logger.error(f"格式化分支狀態頁籤失敗: {str(e)}")

    def _format_branch_status_sheet_with_revision(self, worksheet, green_fill, purple_fill, orange_fill, white_font):
        """
        🔥 新方法：格式化分支建立狀態頁籤 - 包含 revision 欄位格式
        """
        try:
            from openpyxl.styles import Font, PatternFill
            from openpyxl.utils import get_column_letter
            
            # 內容樣式
            green_font = Font(color="00B050", bold=True)
            red_font = Font(color="FF0000", bold=True)
            blue_font = Font(color="0070C0", bold=True)
            purple_font = Font(color="7030A0", bold=True)
            orange_font = Font(color="FFC000", bold=True)
            black_font = Font(color="000000")
            
            # 🔥 綠底白字欄位（與專案列表頁籤一致）
            green_header_columns = [
                'target_branch', 'target_type', 'target_branch_link', 'target_branch_revision'
            ]
            
            # 🔥 紫底白字欄位
            purple_header_columns = ['Remote', 'Gerrit_Server']
            
            # 🔥 橘底白字欄位
            orange_header_columns = ['Force_Update']
            
            # 🔥 藍底白字欄位（新增 revision）
            blue_header_columns = ['revision']
            
            # 狀態顏色設定
            status_colors = {
                '成功': {'fill': PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid"),
                        'font': Font(color="006100", bold=True)},
                '失敗': {'fill': PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid"),
                        'font': Font(color="9C0006", bold=True)},
                '跳過': {'fill': PatternFill(start_color="DDEBF7", end_color="DDEBF7", fill_type="solid"),
                        'font': Font(color="0070C0", bold=True)}
            }
            
            # 找到所有欄位位置並設定格式
            for col_num, cell in enumerate(worksheet[1], 1):
                col_letter = get_column_letter(col_num)
                header_value = str(cell.value) if cell.value else ''
                
                # 🔥 綠底白字標頭（與專案列表一致）
                if header_value in green_header_columns:
                    cell.fill = green_fill
                    cell.font = white_font
                    
                    # 🔥 設定內容格式
                    if header_value == 'target_type':
                        for row_num in range(2, worksheet.max_row + 1):
                            content_cell = worksheet[f"{col_letter}{row_num}"]
                            if content_cell.value == 'Tag':
                                content_cell.font = blue_font
                            elif content_cell.value == 'Branch':
                                content_cell.font = purple_font
                            else:
                                content_cell.font = black_font
                                
                    elif header_value == 'target_branch_link':
                        # 設定較寬的欄寬
                        worksheet.column_dimensions[col_letter].width = 60
                        
                    else:
                        # 其他綠底欄位使用黑字內容
                        for row_num in range(2, worksheet.max_row + 1):
                            content_cell = worksheet[f"{col_letter}{row_num}"]
                            content_cell.font = black_font
                
                # 🔥 藍底白字標頭（新增的 revision 欄位）
                elif header_value in blue_header_columns:
                    cell.fill = blue_fill
                    cell.font = white_font
                    
                    # 設定 revision 欄位寬度
                    worksheet.column_dimensions[col_letter].width = 25
                    
                    # revision 欄位內容使用黑字
                    for row_num in range(2, worksheet.max_row + 1):
                        content_cell = worksheet[f"{col_letter}{row_num}"]
                        content_cell.font = black_font
                
                # 🔥 紫底白字標頭
                elif header_value in purple_header_columns:
                    cell.fill = purple_fill
                    cell.font = white_font
                    
                    if header_value == 'Remote':
                        # Remote 欄位：rtk-prebuilt 用紫字
                        for row_num in range(2, worksheet.max_row + 1):
                            content_cell = worksheet[f"{col_letter}{row_num}"]
                            if content_cell.value == 'rtk-prebuilt':
                                content_cell.font = purple_font
                            else:
                                content_cell.font = black_font
                                
                    elif header_value == 'Gerrit_Server':
                        # 設定較寬欄寬
                        worksheet.column_dimensions[col_letter].width = 40
                        # mm2sd-git2 用紫字
                        for row_num in range(2, worksheet.max_row + 1):
                            content_cell = worksheet[f"{col_letter}{row_num}"]
                            if 'mm2sd-git2' in str(content_cell.value):
                                content_cell.font = purple_font
                            else:
                                content_cell.font = black_font
                
                # 🔥 橘底白字標頭
                elif header_value in orange_header_columns:
                    cell.fill = orange_fill
                    cell.font = white_font
                    
                    # Force_Update 欄位："是" 用橘字
                    for row_num in range(2, worksheet.max_row + 1):
                        content_cell = worksheet[f"{col_letter}{row_num}"]
                        if content_cell.value == '是':
                            content_cell.font = orange_font
                        else:
                            content_cell.font = black_font
                
                # 🔥 Status 欄位特殊格式
                elif header_value == 'Status':
                    for row_num in range(2, worksheet.max_row + 1):
                        content_cell = worksheet[f"{col_letter}{row_num}"]
                        status = str(content_cell.value) if content_cell.value else ''
                        
                        if status in status_colors:
                            content_cell.fill = status_colors[status]['fill']
                            content_cell.font = status_colors[status]['font']
            
            self.logger.info("✅ 已設定包含 revision 欄位的分支建立狀態頁籤格式")
            
        except Exception as e:
            self.logger.error(f"格式化分支建立狀態頁籤失敗: {str(e)}")

    def _write_excel_unified_basic(self, projects: List[Dict], duplicate_projects: List[Dict], 
                              output_file: str, output_folder: str = None):
        """
        🔥 新方法：統一的基本 Excel 寫入 - 無論是否建立分支都使用相同格式
        """
        try:
            # 處理輸出檔案路徑
            if not output_file:
                raise ValueError("輸出檔案名稱不能為空")
            
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
            
            self.logger.info(f"寫入統一格式 Excel 檔案: {full_output_path}")
            
            with pd.ExcelWriter(full_output_path, engine='openpyxl') as writer:
                # 🔥 頁籤 1: 專案列表（統一格式）
                if projects:
                    # 🔥 重要：移除任何可能存在的 revision_diff 值
                    clean_projects = []
                    for project in projects:
                        clean_project = project.copy()
                        # 強制移除 revision_diff 欄位，避免覆蓋公式
                        if 'revision_diff' in clean_project:
                            del clean_project['revision_diff']
                        clean_projects.append(clean_project)
                    
                    df_main = pd.DataFrame(clean_projects)
                    
                    # 🔥 統一欄位順序（無論是否建立分支都相同）
                    main_column_order = [
                        'SN', 'name', 'revision', 'upstream', 'dest-branch',
                        'target_branch', 
                        'target_type', 
                        'target_branch_exists', 
                        'target_branch_revision',
                        'target_branch_link'  # 🔥 綠底白字
                    ]
                    
                    # 添加其他可能存在的欄位（groups, path, source_type 等）
                    # 🔥 排除不需要匯出的欄位
                    excluded_columns = ['branch_link', 'effective_revision']
                    for col in df_main.columns:
                        if col not in main_column_order and col not in excluded_columns:
                            main_column_order.append(col)
                    
                    # 最後加上 branch_link
                    main_column_order.append('branch_link')  # 🔥 藍底白字移到最後
                    
                    # 只保留存在的欄位
                    main_column_order = [col for col in main_column_order if col in df_main.columns]
                    df_main = df_main[main_column_order]
                    
                    # 🔥 在寫入前添加空的 revision_diff 欄位（用於公式）
                    revision_diff_position = main_column_order.index('target_branch_revision') + 1
                    df_main.insert(revision_diff_position, 'revision_diff', None)
                else:
                    # 空的 DataFrame 結構
                    df_main = pd.DataFrame(columns=[
                        'SN', 'name', 'revision', 'upstream', 'dest-branch',
                        'target_branch', 'target_type', 'target_branch_exists', 
                        'target_branch_revision', 'revision_diff', 'target_branch_link', 'branch_link'
                    ])
                
                df_main.to_excel(writer, sheet_name='專案列表', index=False)
                self.logger.info(f"✅ 專案列表頁籤寫入完成，共 {len(projects)} 筆資料")
                
                # 🔥 頁籤 2: 重複專案（統一格式）
                if duplicate_projects:
                    # 🔥 重要：移除任何可能存在的 revision_diff 值
                    clean_duplicates = []
                    for project in duplicate_projects:
                        clean_project = project.copy()
                        # 強制移除 revision_diff 欄位，避免覆蓋公式
                        if 'revision_diff' in clean_project:
                            del clean_project['revision_diff']
                        clean_duplicates.append(clean_project)
                    
                    df_dup = pd.DataFrame(clean_duplicates)
                    
                    # 🔥 重複頁籤也使用相同的欄位順序
                    dup_column_order = [
                        'SN', 'name', 'revision', 'upstream', 'dest-branch',
                        'target_branch',
                        'target_type',
                        'target_branch_exists',
                        'target_branch_revision',
                        'target_branch_link'  # 🔥 綠底白字
                    ]
                    
                    # 添加其他欄位
                    # 🔥 排除不需要匯出的欄位
                    excluded_columns = ['branch_link', 'effective_revision']
                    for col in df_dup.columns:
                        if col not in dup_column_order and col not in excluded_columns:
                            dup_column_order.append(col)
                    
                    # 最後加上 branch_link
                    dup_column_order.append('branch_link')  # 🔥 藍底白字移到最後
                    
                    dup_column_order = [col for col in dup_column_order if col in df_dup.columns]
                    df_dup = df_dup[dup_column_order]
                    
                    # 🔥 在寫入前添加空的 revision_diff 欄位（用於公式）
                    revision_diff_position = dup_column_order.index('target_branch_revision') + 1
                    df_dup.insert(revision_diff_position, 'revision_diff', None)
                    
                    df_dup.to_excel(writer, sheet_name='重覆', index=False)
                    self.logger.info(f"建立 '重覆' 頁籤，共 {len(duplicate_projects)} 筆資料")
                
                self.logger.info("📋 DataFrame 寫入完成，開始設定公式...")
                
            # 🔥 重要：在 writer 關閉後重新開啟來設定公式
            self._add_formulas_to_existing_excel(full_output_path)
            
            # 🔥 格式化 Excel
            self._format_existing_excel(full_output_path)
            
            self.logger.info(f"✅ 統一格式 Excel 檔案寫入完成: {full_output_path}")
            
        except Exception as e:
            self.logger.error(f"寫入統一格式 Excel 檔案失敗: {str(e)}")
            raise

    def _format_existing_excel(self, excel_path: str):
        """
        🔥 新方法：格式化現有 Excel 檔案
        """
        try:
            from openpyxl import load_workbook
            from openpyxl.styles import PatternFill, Font
            
            self.logger.info(f"🎨 開始格式化 Excel 檔案: {excel_path}")
            
            # 載入現有的 Excel 檔案
            workbook = load_workbook(excel_path)
            
            # 定義顏色
            blue_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")    # 藍底
            green_fill = PatternFill(start_color="00B050", end_color="00B050", fill_type="solid")   # 綠底
            orange_fill = PatternFill(start_color="ED7D31", end_color="ED7D31", fill_type="solid")  # 橘底
            white_font = Font(color="FFFFFF", bold=True)  # 白字
            
            for sheet_name in workbook.sheetnames:
                if sheet_name in ['專案列表', '重覆']:
                    worksheet = workbook[sheet_name]
                    
                    # 基本格式化
                    self.excel_handler._format_worksheet(worksheet)
                    
                    # 統一格式化連結欄位
                    self._format_link_columns_unified(worksheet, blue_fill, green_fill, white_font)
                    
                    # 統一格式化 revision_diff 欄位
                    self._format_revision_diff_column_unified(worksheet, orange_fill, white_font)
                    
                    # 統一格式化目標分支欄位
                    self._format_target_branch_columns_unified(worksheet, green_fill, white_font)
            
            # 保存檔案
            workbook.save(excel_path)
            workbook.close()
            self.logger.info(f"✅ 格式化完成並已保存: {excel_path}")
            
        except Exception as e:
            self.logger.error(f"格式化 Excel 失敗: {str(e)}")
            import traceback
            self.logger.error(f"錯誤詳情: {traceback.format_exc()}")
            
    def _add_formulas_to_existing_excel(self, excel_path: str):
        """
        🔥 新方法：在現有 Excel 檔案中添加公式
        """
        try:
            from openpyxl import load_workbook
            from openpyxl.utils import get_column_letter
            
            self.logger.info(f"🔧 開始為 Excel 檔案添加公式: {excel_path}")
            
            # 載入現有的 Excel 檔案
            workbook = load_workbook(excel_path)
            
            for sheet_name in ['專案列表', '重覆']:
                if sheet_name not in workbook.sheetnames:
                    self.logger.warning(f"⚠️ 工作表 '{sheet_name}' 不存在")
                    continue
                    
                worksheet = workbook[sheet_name]
                self.logger.info(f"🔧 開始為 '{sheet_name}' 頁籤設定 revision_diff 公式...")
                
                # 找到各欄位的位置
                revision_col = None
                target_revision_col = None
                revision_diff_col = None
                
                # 打印所有標頭以便調試
                headers = []
                for col_num, cell in enumerate(worksheet[1], 1):
                    header = str(cell.value) if cell.value else ''
                    headers.append(f"{get_column_letter(col_num)}:{header}")
                    
                    if header == 'revision':
                        revision_col = col_num
                        self.logger.debug(f"找到 revision 欄位: {get_column_letter(col_num)} (第{col_num}欄)")
                    elif header == 'target_branch_revision':
                        target_revision_col = col_num
                        self.logger.debug(f"找到 target_branch_revision 欄位: {get_column_letter(col_num)} (第{col_num}欄)")
                    elif header == 'revision_diff':
                        revision_diff_col = col_num
                        self.logger.debug(f"找到 revision_diff 欄位: {get_column_letter(col_num)} (第{col_num}欄)")
                
                self.logger.debug(f"'{sheet_name}' 所有標頭: {', '.join(headers)}")
                
                if revision_col and target_revision_col and revision_diff_col:
                    revision_letter = get_column_letter(revision_col)
                    target_letter = get_column_letter(target_revision_col)
                    diff_letter = get_column_letter(revision_diff_col)
                    
                    self.logger.info(f"📍 欄位對應: revision={revision_letter}, target_branch_revision={target_letter}, revision_diff={diff_letter}")
                    
                    # 🔥 為每一行設定公式（從第2行開始到最後一行）
                    formula_count = 0
                    for row_num in range(2, worksheet.max_row + 1):
                        # 🔥 修正公式：比對 revision 和 target_branch_revision 的前8碼
                        formula = (
                            f'=IF(OR({target_letter}{row_num}="-", '
                            f'{target_letter}{row_num}="", '
                            f'{revision_letter}{row_num}=""), '
                            f'"Y", '
                            f'IF(LEFT({revision_letter}{row_num},8)=LEFT({target_letter}{row_num},8), '
                            f'"N", "Y"))'
                        )
                        
                        # 設定公式到儲存格
                        cell = worksheet[f"{diff_letter}{row_num}"]
                        cell.value = formula
                        formula_count += 1
                        
                        # 每10行記錄一次進度
                        if row_num % 50 == 0 or row_num == 2:
                            self.logger.debug(f"設定公式 {sheet_name} {diff_letter}{row_num}: {formula}")
                    
                    self.logger.info(f"✅ 已為 '{sheet_name}' 頁籤設定 {formula_count} 個 revision_diff 公式")
                    
                    # 🔥 驗證公式設定
                    sample_cell = worksheet[f"{diff_letter}2"]
                    sample_formula = sample_cell.value if sample_cell.value else "無"
                    self.logger.info(f"🔍 第2行公式範例: {sample_formula}")
                    
                else:
                    missing_cols = []
                    if not revision_col:
                        missing_cols.append("revision")
                    if not target_revision_col:
                        missing_cols.append("target_branch_revision")
                    if not revision_diff_col:
                        missing_cols.append("revision_diff")
                        
                    self.logger.error(f"❌ 無法為 '{sheet_name}' 頁籤設定公式，缺少欄位: {', '.join(missing_cols)}")
            
            # 保存檔案
            workbook.save(excel_path)
            workbook.close()
            self.logger.info(f"✅ 公式設定完成並已保存: {excel_path}")
            
        except Exception as e:
            self.logger.error(f"添加公式失敗: {str(e)}")
            import traceback
            self.logger.error(f"錯誤詳情: {traceback.format_exc()}")
            
    def _format_excel_unified_basic(self, writer):
        """
        🔥 新方法：統一格式化基本 Excel 工作表
        """
        try:
            from openpyxl.styles import PatternFill, Font, Alignment
            from openpyxl.utils import get_column_letter
            
            # 定義顏色
            blue_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")    # 藍底
            green_fill = PatternFill(start_color="00B050", end_color="00B050", fill_type="solid")   # 綠底
            orange_fill = PatternFill(start_color="ED7D31", end_color="ED7D31", fill_type="solid")  # 橘底
            white_font = Font(color="FFFFFF", bold=True)  # 白字
            
            for sheet_name in writer.sheets:
                worksheet = writer.sheets[sheet_name]
                
                # 先執行基本格式化
                self.excel_handler._format_worksheet(worksheet)
                
                # 🔥 統一格式化連結欄位
                self._format_link_columns_unified(worksheet, blue_fill, green_fill, white_font)
                
                # 🔥 統一格式化 revision_diff 欄位
                self._format_revision_diff_column_unified(worksheet, orange_fill, white_font)
                
                # 🔥 統一格式化目標分支欄位
                self._format_target_branch_columns_unified(worksheet, green_fill, white_font)
                
        except Exception as e:
            self.logger.error(f"Excel 統一格式化失敗: {str(e)}")

    # ============================================
    # 🔥 新增：統一的 Excel 寫入方法
    # ============================================

    def _write_excel_with_unified_format(self, projects: List[Dict], duplicate_projects: List[Dict], 
                                        output_file: str, output_folder: str = None):
        """
        🔥 新方法：寫入 Excel 檔案 - 統一格式版本
        無論是否建立分支，都使用相同的格式和公式
        """
        try:
            # 處理輸出檔案路徑
            if not output_file:
                raise ValueError("輸出檔案名稱不能為空")
            
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
                # 🔥 頁籤 1: 專案列表（統一格式）
                if projects:
                    df_main = pd.DataFrame(projects)
                    
                    # 🔥 統一欄位順序（無論是否建立分支都相同）
                    main_column_order = [
                        'SN', 'name', 'revision', 'upstream', 'dest-branch',
                        'target_branch', 
                        'target_type', 
                        'target_branch_exists', 
                        'target_branch_revision',
                        'revision_diff',  # 🔥 橘底白字，使用公式比對
                        'target_branch_link'  # 🔥 綠底白字
                    ]
                    
                    # 添加其他可能存在的欄位（groups, path, source_type 等）
                    # 🔥 排除不需要匯出的欄位
                    excluded_columns = ['branch_link', 'effective_revision']
                    for col in df_main.columns:
                        if col not in main_column_order and col not in excluded_columns:
                            main_column_order.append(col)
                    
                    # 最後加上 branch_link
                    main_column_order.append('branch_link')  # 🔥 藍底白字移到最後
                    
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
                
                # 🔥 頁籤 2: 重複專案（統一格式）
                if duplicate_projects:
                    df_dup = pd.DataFrame(duplicate_projects)
                    
                    # 🔥 重複頁籤也使用相同的欄位順序
                    dup_column_order = [
                        'SN', 'name', 'revision', 'upstream', 'dest-branch',
                        'target_branch',
                        'target_type',
                        'target_branch_exists',
                        'target_branch_revision',
                        'revision_diff',  # 🔥 橘底白字，使用公式比對
                        'target_branch_link'  # 🔥 綠底白字
                    ]
                    
                    # 添加其他欄位
                    # 🔥 排除不需要匯出的欄位
                    excluded_columns = ['branch_link', 'effective_revision']
                    for col in df_dup.columns:
                        if col not in dup_column_order and col not in excluded_columns:
                            dup_column_order.append(col)
                    
                    # 最後加上 branch_link
                    dup_column_order.append('branch_link')  # 🔥 藍底白字移到最後
                    
                    dup_column_order = [col for col in dup_column_order if col in df_dup.columns]
                    df_dup = df_dup[dup_column_order]
                    
                    df_dup.to_excel(writer, sheet_name='重覆', index=False)
                    self.logger.info(f"建立 '重覆' 頁籤，共 {len(duplicate_projects)} 筆資料")
                
                # 🔥 設定 revision_diff 欄位的 Excel 公式
                self._set_revision_diff_formulas(writer)
                
                # 🔥 格式化所有工作表，使用統一格式
                self._format_excel_with_unified_style(writer)
            
            self.logger.info(f"成功寫入 Excel 檔案: {full_output_path}")
            
        except Exception as e:
            self.logger.error(f"寫入 Excel 檔案失敗: {str(e)}")
            raise

    def _format_excel_with_unified_style(self, writer):
        """
        🔥 新方法：格式化 Excel 工作表，使用統一樣式
        確保無論是否建立分支，格式都一致
        """
        try:
            from openpyxl.styles import PatternFill, Font, Alignment
            from openpyxl.utils import get_column_letter
            
            # 定義顏色
            blue_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")    # 藍底
            green_fill = PatternFill(start_color="00B050", end_color="00B050", fill_type="solid")   # 綠底
            orange_fill = PatternFill(start_color="ED7D31", end_color="ED7D31", fill_type="solid")  # 橘底
            white_font = Font(color="FFFFFF", bold=True)  # 白字
            
            for sheet_name in writer.sheets:
                worksheet = writer.sheets[sheet_name]
                
                # 先執行基本格式化
                self.excel_handler._format_worksheet(worksheet)
                
                # 🔥 統一格式化連結欄位
                self._format_link_columns_unified(worksheet, blue_fill, green_fill, white_font)
                
                # 🔥 統一格式化 revision_diff 欄位
                self._format_revision_diff_column_unified(worksheet, orange_fill, white_font)
                
                # 🔥 統一格式化目標分支欄位
                self._format_target_branch_columns_unified(worksheet, green_fill, white_font)
                
        except Exception as e:
            self.logger.error(f"Excel 格式化失敗: {str(e)}")

    def _format_target_branch_columns_unified(self, worksheet, green_fill, white_font):
        """
        🔥 新方法：統一格式化目標分支相關欄位
        確保所有目標分支欄位都有綠底白字
        """
        try:
            from openpyxl.styles import Font
            from openpyxl.utils import get_column_letter
            
            # 內容樣式
            green_font = Font(color="00B050", bold=True)  # Y 的綠字
            red_font = Font(color="FF0000", bold=True)    # N 的紅字
            blue_font = Font(color="0070C0", bold=True)   # Tag 的藍字
            purple_font = Font(color="7030A0", bold=True) # Branch 的紫字
            black_font = Font(color="000000")             # 一般文字
            
            # 🔥 所有需要綠底白字的目標分支欄位
            target_green_columns = [
                'target_branch', 'target_type', 'target_branch_exists', 
                'target_branch_revision', 'target_branch_link'
            ]
            
            # 找到目標欄位的位置
            target_columns = {}
            for col_num, cell in enumerate(worksheet[1], 1):
                header_value = str(cell.value) if cell.value else ''
                if header_value in target_green_columns:
                    target_columns[header_value] = col_num
            
            # 🔥 統一設定綠底白字標頭
            for col_name, col_num in target_columns.items():
                col_letter = get_column_letter(col_num)
                header_cell = worksheet[f"{col_letter}1"]
                header_cell.fill = green_fill
                header_cell.font = white_font
                
                # 🔥 根據欄位類型設定內容格式
                if col_name == 'target_type':
                    # target_type 欄位：Tag用藍字，Branch用紫字
                    for row_num in range(2, worksheet.max_row + 1):
                        cell = worksheet[f"{col_letter}{row_num}"]
                        if cell.value == 'Tag':
                            cell.font = blue_font
                        elif cell.value == 'Branch':
                            cell.font = purple_font
                        else:
                            cell.font = black_font
                            
                elif col_name == 'target_branch_exists':
                    # target_branch_exists 欄位：Y用綠字，N用紅字
                    for row_num in range(2, worksheet.max_row + 1):
                        cell = worksheet[f"{col_letter}{row_num}"]
                        if cell.value == 'Y':
                            cell.font = green_font
                        elif cell.value == 'N':
                            cell.font = red_font
                        else:
                            cell.font = black_font
                            
                elif col_name == 'target_branch_link':
                    # target_branch_link 欄位：設定較寬欄寬
                    worksheet.column_dimensions[col_letter].width = 60
                    
                else:
                    # 其他欄位：使用黑字
                    for row_num in range(2, worksheet.max_row + 1):
                        cell = worksheet[f"{col_letter}{row_num}"]
                        cell.font = black_font
            
            self.logger.info("已設定統一的目標分支欄位格式：全部綠底白字標頭")
                
        except Exception as e:
            self.logger.error(f"格式化目標分支欄位失敗: {str(e)}")

    def _format_link_columns_unified(self, worksheet, blue_fill, green_fill, white_font):
        """
        🔥 新方法：統一格式化連結欄位
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
                
                # 調整欄寬
                worksheet.column_dimensions[col_letter].width = 60
                
            # 格式化 target_branch_link 欄位 (綠底白字)
            if 'target_branch_link' in link_columns:
                col_num = link_columns['target_branch_link']
                col_letter = get_column_letter(col_num)
                
                header_cell = worksheet[f"{col_letter}1"]
                header_cell.fill = green_fill
                header_cell.font = white_font
                
                # 調整欄寬
                worksheet.column_dimensions[col_letter].width = 60
                
            self.logger.info("已完成統一連結欄位格式化")
            
        except Exception as e:
            self.logger.error(f"格式化連結欄位失敗: {str(e)}")

    def _format_revision_diff_column_unified(self, worksheet, orange_fill, white_font):
        """
        🔥 新方法：統一格式化 revision_diff 欄位（橘底白字，N綠字/Y紅字）
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
                
                # 🔥 格式化標題（橘底白字）
                header_cell = worksheet[f"{col_letter}1"]
                header_cell.fill = orange_fill
                header_cell.font = white_font
                
                # 設定欄寬
                worksheet.column_dimensions[col_letter].width = 12
                
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
                
                self.logger.info("已設定統一 revision_diff 欄位格式：標頭橘底白字，N綠字/Y紅字")
                
        except Exception as e:
            self.logger.error(f"格式化 revision_diff 欄位失敗: {str(e)}")

    # ============================================
    # 🔥 修正：統一的分支狀態頁籤方法
    # ============================================

    def _add_branch_status_sheet_unified(self, output_file: str, output_folder: str, branch_results: List[Dict]):
        """
        🔥 新方法：在 Excel 檔案中加入分支建立狀態頁籤 - 統一格式版本
        使用與專案列表頁籤相同的欄位名稱和格式
        """
        try:
            full_output_path = os.path.join(output_folder, output_file)
            
            # 讀取現有的 Excel 檔案
            with pd.ExcelFile(full_output_path) as xls:
                existing_sheets = {}
                for sheet_name in xls.sheet_names:
                    existing_sheets[sheet_name] = pd.read_excel(xls, sheet_name=sheet_name)
            
            # 重新寫入，加上新的頁籤
            with pd.ExcelWriter(full_output_path, engine='openpyxl') as writer:
                # 寫入現有頁籤
                for sheet_name, df in existing_sheets.items():
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
                
                # 🔥 加入分支建立狀態頁籤（使用統一欄位名稱）
                if branch_results:
                    df_branch = pd.DataFrame(branch_results)
                    
                    # 🔥 調整欄位順序（使用小寫欄位名稱，與專案列表頁籤一致）
                    column_order = [
                        'SN', 'Project', 
                        'target_branch',        # 🔥 改為小寫，綠底白字
                        'target_type',          # 🔥 改為小寫，綠底白字
                        'target_branch_link',   # 🔥 綠底白字
                        'target_branch_revision',  # 🔥 改名並改為小寫，綠底白字
                        'Status', 'Message', 'Already_Exists', 'Force_Update',
                        'Remote', 'Gerrit_Server'
                    ]
                    
                    # 🔥 映射原始欄位名稱到新的欄位名稱
                    if 'Target_Branch' in df_branch.columns:
                        df_branch = df_branch.rename(columns={'Target_Branch': 'target_branch'})
                    if 'Target_Type' in df_branch.columns:
                        df_branch = df_branch.rename(columns={'Target_Type': 'target_type'})
                    if 'Revision' in df_branch.columns:
                        df_branch = df_branch.rename(columns={'Revision': 'target_branch_revision'})
                    
                    # 只保留存在的欄位
                    column_order = [col for col in column_order if col in df_branch.columns]
                    df_branch = df_branch[column_order]
                else:
                    # 🔥 空的 DataFrame 結構（使用統一欄位名稱）
                    df_branch = pd.DataFrame(columns=[
                        'SN', 'Project', 'target_branch', 'target_type', 'target_branch_link', 
                        'target_branch_revision', 'Status', 'Message', 'Already_Exists', 'Force_Update',
                        'Remote', 'Gerrit_Server'
                    ])
                
                df_branch.to_excel(writer, sheet_name='Branch 建立狀態', index=False)
                
                # 🔥 重新格式化所有工作表（包括新的分支狀態頁籤）
                self._format_all_sheets_unified(writer)
            
            self.logger.info("成功加入統一格式的分支建立狀態頁籤")
            
        except Exception as e:
            self.logger.error(f"加入分支狀態頁籤失敗: {str(e)}")

    def _format_all_sheets_unified(self, writer):
        """
        🔥 新方法：格式化所有工作表，包括分支狀態頁籤
        """
        try:
            from openpyxl.styles import PatternFill, Font
            from openpyxl.utils import get_column_letter
            
            # 定義顏色
            blue_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
            green_fill = PatternFill(start_color="00B050", end_color="00B050", fill_type="solid")
            orange_fill = PatternFill(start_color="ED7D31", end_color="ED7D31", fill_type="solid")
            purple_fill = PatternFill(start_color="7030A0", end_color="7030A0", fill_type="solid")
            white_font = Font(color="FFFFFF", bold=True)
            
            for sheet_name in writer.sheets:
                worksheet = writer.sheets[sheet_name]
                
                # 基本格式化
                self.excel_handler._format_worksheet(worksheet)
                
                if sheet_name in ['專案列表', '重覆']:
                    # 🔥 專案列表和重覆頁籤：統一格式
                    self._format_link_columns_unified(worksheet, blue_fill, green_fill, white_font)
                    self._format_revision_diff_column_unified(worksheet, orange_fill, white_font)
                    self._format_target_branch_columns_unified(worksheet, green_fill, white_font)
                    
                elif sheet_name == 'Branch 建立狀態':
                    # 🔥 分支建立狀態頁籤：特殊格式
                    self._format_branch_status_sheet_unified(worksheet, green_fill, purple_fill, orange_fill, white_font)
                
        except Exception as e:
            self.logger.error(f"格式化所有工作表失敗: {str(e)}")

    def _format_branch_status_sheet_unified(self, worksheet, green_fill, purple_fill, orange_fill, white_font):
        """
        🔥 新方法：格式化分支建立狀態頁籤 - 統一格式版本
        """
        try:
            from openpyxl.styles import Font, PatternFill
            from openpyxl.utils import get_column_letter
            
            # 內容樣式
            green_font = Font(color="00B050", bold=True)
            red_font = Font(color="FF0000", bold=True)
            blue_font = Font(color="0070C0", bold=True)
            purple_font = Font(color="7030A0", bold=True)
            orange_font = Font(color="FFC000", bold=True)
            black_font = Font(color="000000")
            
            # 🔥 綠底白字欄位（與專案列表頁籤一致）
            green_header_columns = [
                'target_branch', 'target_type', 'target_branch_link', 'target_branch_revision'
            ]
            
            # 🔥 紫底白字欄位
            purple_header_columns = ['Remote', 'Gerrit_Server']
            
            # 🔥 橘底白字欄位
            orange_header_columns = ['Force_Update']
            
            # 狀態顏色設定
            status_colors = {
                '成功': {'fill': PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid"),
                        'font': Font(color="006100", bold=True)},
                '失敗': {'fill': PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid"),
                        'font': Font(color="9C0006", bold=True)},
                '跳過': {'fill': PatternFill(start_color="DDEBF7", end_color="DDEBF7", fill_type="solid"),
                        'font': Font(color="0070C0", bold=True)}
            }
            
            # 找到所有欄位位置並設定格式
            for col_num, cell in enumerate(worksheet[1], 1):
                col_letter = get_column_letter(col_num)
                header_value = str(cell.value) if cell.value else ''
                
                # 🔥 綠底白字標頭（與專案列表一致）
                if header_value in green_header_columns:
                    cell.fill = green_fill
                    cell.font = white_font
                    
                    # 🔥 設定內容格式
                    if header_value == 'target_type':
                        for row_num in range(2, worksheet.max_row + 1):
                            content_cell = worksheet[f"{col_letter}{row_num}"]
                            if content_cell.value == 'Tag':
                                content_cell.font = blue_font
                            elif content_cell.value == 'Branch':
                                content_cell.font = purple_font
                            else:
                                content_cell.font = black_font
                                
                    elif header_value == 'target_branch_link':
                        # 設定較寬的欄寬
                        worksheet.column_dimensions[col_letter].width = 60
                        
                    else:
                        # 其他綠底欄位使用黑字內容
                        for row_num in range(2, worksheet.max_row + 1):
                            content_cell = worksheet[f"{col_letter}{row_num}"]
                            content_cell.font = black_font
                
                # 🔥 紫底白字標頭
                elif header_value in purple_header_columns:
                    cell.fill = purple_fill
                    cell.font = white_font
                    
                    if header_value == 'Remote':
                        # Remote 欄位：rtk-prebuilt 用紫字
                        for row_num in range(2, worksheet.max_row + 1):
                            content_cell = worksheet[f"{col_letter}{row_num}"]
                            if content_cell.value == 'rtk-prebuilt':
                                content_cell.font = purple_font
                            else:
                                content_cell.font = black_font
                                
                    elif header_value == 'Gerrit_Server':
                        # 設定較寬欄寬
                        worksheet.column_dimensions[col_letter].width = 40
                        # mm2sd-git2 用紫字
                        for row_num in range(2, worksheet.max_row + 1):
                            content_cell = worksheet[f"{col_letter}{row_num}"]
                            if 'mm2sd-git2' in str(content_cell.value):
                                content_cell.font = purple_font
                            else:
                                content_cell.font = black_font
                
                # 🔥 橘底白字標頭
                elif header_value in orange_header_columns:
                    cell.fill = orange_fill
                    cell.font = white_font
                    
                    # Force_Update 欄位："是" 用橘字
                    for row_num in range(2, worksheet.max_row + 1):
                        content_cell = worksheet[f"{col_letter}{row_num}"]
                        if content_cell.value == '是':
                            content_cell.font = orange_font
                        else:
                            content_cell.font = black_font
                
                # 🔥 Status 欄位特殊格式
                elif header_value == 'Status':
                    for row_num in range(2, worksheet.max_row + 1):
                        content_cell = worksheet[f"{col_letter}{row_num}"]
                        status = str(content_cell.value) if content_cell.value else ''
                        
                        if status in status_colors:
                            content_cell.fill = status_colors[status]['fill']
                            content_cell.font = status_colors[status]['font']
            
            self.logger.info("已設定統一的分支建立狀態頁籤格式")
            
        except Exception as e:
            self.logger.error(f"格式化分支建立狀態頁籤失敗: {str(e)}")

    # ============================================
    # 🔥 修正：分支建立方法，返回結果供狀態頁籤使用
    # ============================================

    def _create_branches(self, projects: List[Dict], output_file: str, output_folder: str = None, 
                        force_update: bool = False) -> List[Dict]:
        """
        建立分支並返回結果 - 修正版 (🔥 增加 revision 欄位)
        """
        try:
            self.logger.info("開始建立分支...")
            self.logger.info("🎯 建立邏輯：從原始 revision 創建目標 target_branch 分支")
            self.logger.info(f"🆕 強制更新模式: {'啟用' if force_update else '停用'}")
            
            branch_results = []
            skipped_tags = 0
            prebuilt_count = 0
            normal_count = 0
            
            for project in projects:
                project_name = project.get('name', '')
                target_branch = project.get('target_branch', '')
                target_type = project.get('target_type', 'Branch')
                revision = project.get('revision', '')  # 🔥 來源 revision
                
                # 🔥 使用項目中已設定的 remote（由 _convert_projects 自動偵測）
                remote = project.get('remote', '')
                if not remote:
                    # 如果還是沒有，再次自動偵測
                    remote = self._auto_detect_remote(project)
                    self.logger.debug(f"分支建立時自動偵測 remote: {project_name} -> {remote}")
                
                # 檢查必要資訊
                if not all([project_name, target_branch, revision]):
                    self.logger.debug(f"跳過專案 {project_name}：缺少必要資訊")
                    continue
                
                # 跳過 Tag 類型的專案
                if target_type == 'Tag' or self._is_tag_reference(target_branch):
                    skipped_tags += 1
                    # 🔥 使用統一的欄位名稱，添加 revision 欄位
                    branch_result = {
                        'SN': len(branch_results) + 1,
                        'Project': project_name,
                        'revision': revision,                # 🔥 新增：來源 revision
                        'target_branch': target_branch,      # 🔥 小寫
                        'target_type': 'Tag',               # 🔥 小寫
                        'target_branch_link': project.get('target_branch_link', ''),
                        'target_branch_revision': revision,  # 🔥 改名
                        'Status': '跳過',
                        'Message': 'Tag 類型不建立分支',
                        'Already_Exists': '-',
                        'Force_Update': '-',
                        'Remote': remote,
                        'Gerrit_Server': self._get_gerrit_base_url(remote)
                    }
                    branch_results.append(branch_result)
                    continue
                
                # 根據 remote 選擇正確的 GerritManager
                if remote == 'rtk-prebuilt':
                    temp_gerrit = self._get_prebuilt_gerrit_manager()
                    prebuilt_count += 1
                    gerrit_server = self._get_gerrit_base_url('rtk-prebuilt')
                else:
                    temp_gerrit = self.gerrit_manager
                    normal_count += 1
                    gerrit_server = self._get_gerrit_base_url('')
                
                # 檢查分支是否已存在（如果不是強制更新模式）
                branch_exists = False
                existing_revision = ''
                
                if not force_update:
                    exists_info = self._check_target_branch_exists(project_name, target_branch, remote)
                    branch_exists = exists_info['exists_status'] == 'Y'
                    existing_revision = exists_info['revision']
                    
                    if branch_exists:
                        # 🔥 使用統一的欄位名稱，添加 revision 欄位
                        branch_result = {
                            'SN': len(branch_results) + 1,
                            'Project': project_name,
                            'revision': revision,                # 🔥 新增：來源 revision
                            'target_branch': target_branch,      # 🔥 小寫
                            'target_type': 'Branch',             # 🔥 小寫
                            'target_branch_link': project.get('target_branch_link', ''),
                            'target_branch_revision': existing_revision,  # 🔥 改名
                            'Status': '成功',
                            'Message': f"分支已存在，無需建立 (當前 revision: {existing_revision})",
                            'Already_Exists': '是',
                            'Force_Update': '否',
                            'Remote': remote,
                            'Gerrit_Server': gerrit_server
                        }
                        branch_results.append(branch_result)
                        continue
                
                # 執行分支建立/更新
                result = temp_gerrit.create_branch(project_name, target_branch, revision)
                
                # 分析結果
                success = result.get('success', False)
                message = result.get('message', '')
                already_exists = result.get('exists', False)
                
                # 根據結果判斷狀態
                if success:
                    if already_exists and not force_update:
                        status = '成功'
                        final_message = f"分支已存在且正確：{message}"
                    elif already_exists and force_update:
                        status = '成功'
                        final_message = f"分支已存在，已強制更新：{message}"
                    else:
                        status = '成功'
                        final_message = f"成功建立分支：{message}"
                else:
                    if not force_update and ("已存在" in message or "already exists" in message.lower()):
                        status = '成功'
                        final_message = f"分支已存在，無需建立：{message}"
                        already_exists = True
                    else:
                        status = '失敗'
                        final_message = f"建立失敗：{message}"
                
                # 🔥 使用統一的欄位名稱記錄結果，添加 revision 欄位
                branch_result = {
                    'SN': len(branch_results) + 1,
                    'Project': project_name,
                    'revision': revision,                    # 🔥 新增：來源 revision
                    'target_branch': target_branch,          # 🔥 小寫
                    'target_type': 'Branch',                 # 🔥 小寫
                    'target_branch_link': project.get('target_branch_link', ''),
                    'target_branch_revision': revision,      # 🔥 改名（這是用來建立分支的revision）
                    'Status': status,
                    'Message': final_message,
                    'Already_Exists': '是' if already_exists else '否',
                    'Force_Update': '是' if force_update else '否',
                    'Remote': remote,
                    'Gerrit_Server': gerrit_server
                }
                branch_results.append(branch_result)
                
                # 進度報告
                if len(branch_results) % 10 == 0:
                    success_count = len([r for r in branch_results if r['Status'] == '成功'])
                    self.logger.info(f"已處理 {len(branch_results)} 個分支，成功 {success_count} 個")
            
            # 最終統計
            success_count = len([r for r in branch_results if r['Status'] == '成功'])
            failure_count = len([r for r in branch_results if r['Status'] == '失敗'])
            
            self.logger.info(f"🎉 分支建立完成，共處理 {len(branch_results)} 個專案")
            self.logger.info(f"  - ✅ 成功: {success_count} 個")
            self.logger.info(f"  - ❌ 失敗: {failure_count} 個")
            self.logger.info(f"  - ⏭️ 跳過 Tag: {skipped_tags} 個")
            
            # 🔥 返回結果供狀態頁籤使用
            return branch_results
            
        except Exception as e:
            self.logger.error(f"建立分支失敗: {str(e)}")
            return []

    # ============================================
    # 以下方法保持不變...
    # ============================================

    def _is_revision_hash(self, revision: str) -> bool:
        """判斷 revision 是否為 commit hash"""
        if not revision:
            return False
        
        revision = revision.strip()
        
        # Hash 特徵：40 字符的十六進制字符串
        if len(revision) == 40 and all(c in '0123456789abcdefABCDEF' for c in revision):
            return True
        
        # Branch name 特徵：包含斜線和可讀名稱
        if '/' in revision and any(c.isalpha() for c in revision):
            return False
        
        # 其他情況當作 branch name 處理
        return False

    def _get_effective_revision_for_conversion(self, project: Dict) -> str:
        """取得用於轉換的有效 revision"""
        revision = project.get('revision', '')
        upstream = project.get('upstream', '')
        remote = project.get('remote', '')
        
        # 如果 revision 是 hash，使用 upstream
        if self._is_revision_hash(revision):
            if upstream:
                self.logger.debug(f"專案 {project.get('name', '')} revision 是 hash，使用 upstream: {upstream}")
                return upstream
            else:
                self.logger.warning(f"專案 {project.get('name', '')} revision 是 hash 但沒有 upstream")
                return ''
        
        # 如果 revision 是 branch name，直接使用
        if revision:
            self.logger.debug(f"專案 {project.get('name', '')} revision 是 branch name: {revision}")
            return revision
        
        # 如果沒有 revision，返回空字串
        self.logger.debug(f"專案 {project.get('name', '')} 沒有 revision")
        return ''

    def _get_effective_revision_for_link(self, project: Dict) -> str:
        """取得用於建立連結的有效 revision"""
        return self._get_effective_revision_for_conversion(project)

    def _should_skip_revision_conversion(self, revision: str) -> bool:
        """判斷是否應該跳過 revision 轉換"""
        if not revision:
            return True
        
        # 跳過 Google 開頭的項目
        if revision.startswith('google/'):
            return True
        
        # 跳過 refs/tags/
        if revision.startswith('refs/tags/'):
            return True
        
        return False

    def _smart_conversion_fallback(self, revision: str) -> str:
        """智能轉換備案"""
        # 如果包含 mp.google-refplus，嘗試替換為 premp.google-refplus
        if 'mp.google-refplus' in revision:
            result = revision.replace('mp.google-refplus', 'premp.google-refplus')
            self.logger.debug(f"智能替換 mp→premp: {revision} → {result}")
            return result
        
        # 如果是 master 但沒有匹配到特定規則，使用預設轉換
        if '/master' in revision and 'realtek/' in revision:
            import re
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
        """master → premp 轉換規則 - 從 feature_three.py 完全移植"""
        if not revision:
            return revision
        
        original_revision = revision.strip()
        
        # 跳過 Google 開頭的項目
        if original_revision.startswith('google/'):
            self.logger.debug(f"跳過 Google 項目: {original_revision}")
            return original_revision
        
        # 跳過特殊項目
        if self._should_skip_revision_conversion(original_revision):
            return original_revision
        
        # 精確匹配轉換規則
        exact_mappings = {
            'realtek/master': 'realtek/android-14/premp.google-refplus',
            'realtek/gaia': 'realtek/android-14/premp.google-refplus',
            'realtek/gki/master': 'realtek/android-14/premp.google-refplus',
            'realtek/android-14/master': 'realtek/android-14/premp.google-refplus',
            'realtek/linux-5.15/android-14/master': 'realtek/linux-5.15/android-14/premp.google-refplus',
            'realtek/linux-4.14/android-14/master': 'realtek/linux-4.14/android-14/premp.google-refplus',
            'realtek/linux-5.4/android-14/master': 'realtek/linux-5.4/android-14/premp.google-refplus',
            'realtek/linux-5.10/android-14/master': 'realtek/linux-5.10/android-14/premp.google-refplus',
            'realtek/linux-6.1/android-14/master': 'realtek/linux-6.1/android-14/premp.google-refplus',
            'realtek/mp.google-refplus': 'realtek/android-14/premp.google-refplus',
            'realtek/android-14/mp.google-refplus': 'realtek/android-14/premp.google-refplus',
        }
        
        # 檢查精確匹配
        if original_revision in exact_mappings:
            self.logger.debug(f"精確匹配轉換: {original_revision} → {exact_mappings[original_revision]}")
            return exact_mappings[original_revision]
        
        # 模式匹配轉換規則
        import re
        
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
        
        # 規則 3: linux-X.X/master → linux-X.X/android-14/premp.google-refplus
        pattern3 = r'realtek/linux-([\d.]+)/master$'
        match3 = re.match(pattern3, original_revision)
        if match3:
            linux_ver = match3.group(1)
            result = f'realtek/linux-{linux_ver}/android-14/premp.google-refplus'
            self.logger.debug(f"模式3轉換: {original_revision} → {result}")
            return result
        
        # 更多規則...（其他轉換規則保持不變）
        
        # 如果沒有匹配的規則，使用智能轉換
        smart_result = self._smart_conversion_fallback(original_revision)
        self.logger.debug(f"智能轉換: {original_revision} → {smart_result}")
        return smart_result

    def _convert_premp_to_mp(self, revision: str) -> str:
        """premp → mp 轉換規則"""
        return revision.replace('premp.google-refplus', 'mp.google-refplus.wave')
    
    def _convert_mp_to_mpbackup(self, revision: str) -> str:
        """mp → mpbackup 轉換規則"""
        return revision.replace('mp.google-refplus.wave', 'mp.google-refplus.wave.backup')

    def _convert_projects(self, projects: List[Dict], process_type: str, check_branch_exists: bool = False) -> List[Dict]:
        """轉換專案的分支名稱 - 修正版（🔥 使用確定的 remote 進行分支檢查）"""
        converted_projects = []
        tag_count = 0
        branch_count = 0
        hash_revision_count = 0
        branch_revision_count = 0
        
        self.logger.info(f"🔄 開始轉換專案分支，處理類型: {process_type}")
        
        for i, project in enumerate(projects, 1):
            converted_project = project.copy()
            converted_project['SN'] = i
            
            # 🔥 只在沒有 remote 時才自動偵測，否則保留原始值
            original_remote = project.get('remote', '')
            if not original_remote:
                auto_remote = self._auto_detect_remote(project)
                converted_project['remote'] = auto_remote
                self.logger.debug(f"專案 {project.get('name', '')} 自動偵測 remote: {auto_remote}")
            else:
                converted_project['remote'] = original_remote
                self.logger.debug(f"專案 {project.get('name', '')} 保留原始 remote: {original_remote}")
            
            # 使用新邏輯取得用於轉換的 revision
            effective_revision = self._get_effective_revision_for_conversion(converted_project)
            
            # 統計 revision 類型
            original_revision = project.get('revision', '')
            if self._is_revision_hash(original_revision):
                hash_revision_count += 1
            elif original_revision:
                branch_revision_count += 1
            
            # 如果沒有有效的 revision，跳過轉換
            if not effective_revision:
                target_branch = ''
                self.logger.debug(f"專案 {project.get('name', '')} 沒有有效的 revision，跳過轉換")
            else:
                # 根據處理類型進行轉換
                target_branch = self._convert_revision_by_type(effective_revision, process_type)
                
                if target_branch != effective_revision:
                    self.logger.debug(f"專案 {project.get('name', '')} 轉換: {effective_revision} → {target_branch}")
            
            converted_project['target_branch'] = target_branch
            converted_project['effective_revision'] = effective_revision
            
            # 判斷目標是 Tag 還是 Branch
            is_tag = self._is_tag_reference(target_branch)
            converted_project['target_type'] = 'Tag' if is_tag else 'Branch'
            
            if is_tag:
                tag_count += 1
            else:
                branch_count += 1
            
            # 🔥 修正：根據參數決定是否檢查存在性，使用最終確定的 remote
            if check_branch_exists and target_branch:
                final_remote = converted_project['remote']
                
                if is_tag:
                    exists_info = self._check_target_tag_exists(project.get('name', ''), target_branch, final_remote)
                else:
                    # 🔥 修正：直接傳入確定的 remote，不再測試兩種可能性
                    exists_info = self._check_target_branch_exists(project.get('name', ''), target_branch, final_remote)
                
                converted_project['target_branch_exists'] = exists_info['exists_status']
                converted_project['target_branch_revision'] = exists_info['revision']
                
                # 🔥 記錄分支檢查結果
                if exists_info['exists_status'] == 'Y':
                    self.logger.debug(f"✅ 專案 {project.get('name', '')} 分支檢查成功:")
                    self.logger.debug(f"  目標分支: {target_branch}")
                    self.logger.debug(f"  使用 remote: {final_remote}")
                    self.logger.debug(f"  分支 revision: {exists_info['revision']}")
                else:
                    self.logger.debug(f"❌ 專案 {project.get('name', '')} 分支檢查失敗:")
                    self.logger.debug(f"  目標分支: {target_branch}")
                    self.logger.debug(f"  使用 remote: {final_remote}")
                    
            else:
                converted_project['target_branch_exists'] = '-'
                converted_project['target_branch_revision'] = '-'
            
            converted_projects.append(converted_project)
            
            # 每100個項目顯示進度
            if check_branch_exists and i % 100 == 0:
                self.logger.info(f"已處理 {i}/{len(projects)} 個專案的存在性檢查")
        
        self.logger.info(f"轉換完成 - Branch: {branch_count}, Tag: {tag_count}")
        self.logger.info(f"📊 Revision 類型統計:")
        self.logger.info(f"  - 🔸 Hash revision: {hash_revision_count} 個")
        self.logger.info(f"  - 🔹 Branch revision: {branch_revision_count} 個")
        
        # 🔥 統計 remote 分布
        remote_stats = {}
        auto_detected_count = 0
        
        for proj in converted_projects:
            remote = proj.get('remote', 'unknown')
            remote_stats[remote] = remote_stats.get(remote, 0) + 1
            
            # 統計自動偵測的數量
            original_remote = proj.get('name', '')  # 使用原始資料檢查
            original_project = next((p for p in projects if p.get('name') == original_remote), {})
            if not original_project.get('remote', ''):
                auto_detected_count += 1
        
        self.logger.info(f"📊 Remote 分布統計:")
        for remote, count in remote_stats.items():
            self.logger.info(f"  - {remote}: {count} 個專案")
        
        if auto_detected_count > 0:
            self.logger.info(f"📊 自動偵測 remote: {auto_detected_count} 個專案")
        
        # 🔥 分支檢查統計
        if check_branch_exists:
            branch_check_stats = {'Y': 0, 'N': 0, '-': 0}
            for proj in converted_projects:
                status = proj.get('target_branch_exists', '-')
                branch_check_stats[status] = branch_check_stats.get(status, 0) + 1
            
            self.logger.info(f"📊 分支檢查統計:")
            self.logger.info(f"  - ✅ 分支存在: {branch_check_stats['Y']} 個")
            self.logger.info(f"  - ❌ 分支不存在: {branch_check_stats['N']} 個")
            self.logger.info(f"  - ⏭️ 未檢查: {branch_check_stats['-']} 個")
        
        return converted_projects

    def _convert_revision_by_type(self, revision: str, process_type: str) -> str:
        """根據處理類型轉換 revision"""
        try:
            if not revision:
                return ''
            
            # 如果是 Tag 參考，直接返回不做轉換
            if self._is_tag_reference(revision):
                self.logger.debug(f"檢測到 Tag 參考，保持原樣: {revision}")
                return revision
            
            # 根據處理類型進行轉換
            if process_type == 'master_vs_premp':
                return self._convert_master_to_premp(revision)
            elif process_type == 'premp_vs_mp':
                return self._convert_premp_to_mp(revision)
            elif process_type == 'mp_vs_mpbackup':
                return self._convert_mp_to_mpbackup(revision)
            
            # 如果沒有匹配的處理類型，返回原值
            return revision
            
        except Exception as e:
            self.logger.error(f"轉換 revision 失敗: {revision}, 錯誤: {str(e)}")
            return revision

    def _get_gerrit_base_url(self, remote: str) -> str:
        """根據 remote 取得對應的 Gerrit base URL"""
        try:
            if remote == 'rtk-prebuilt':
                return getattr(config, 'GERRIT_PREBUILT_URL', 'https://mm2sd-git2.rtkbf.com')
            else:
                return getattr(config, 'GERRIT_SORUCE_URL', 'https://mm2sd.rtkbf.com')
        except:
            if remote == 'rtk-prebuilt':
                return 'https://mm2sd-git2.rtkbf.com'
            else:
                return 'https://mm2sd.rtkbf.com'
    
    def _build_gerrit_link_from_dest_branch(self, project_name: str, dest_branch: str, remote: str = '') -> str:
        """根據 dest-branch 建立 Gerrit branch/tag 連結"""
        try:
            if not project_name or not dest_branch:
                return ""
            
            # 根據 remote 決定 base URL
            gerrit_base = self._get_gerrit_base_url(remote)
            base_url = f"{gerrit_base}/gerrit/plugins/gitiles"
            
            # 判斷是 tag 還是 branch
            if dest_branch.startswith('refs/tags/'):
                link = f"{base_url}/{project_name}/+/{dest_branch}"
            elif dest_branch.startswith('refs/heads/'):
                link = f"{base_url}/{project_name}/+/{dest_branch}"
            else:
                link = f"{base_url}/{project_name}/+/refs/heads/{dest_branch}"
            
            self.logger.debug(f"建立 branch_link: {project_name} + {dest_branch} -> {link} (remote: {remote})")
            return link
            
        except Exception as e:
            self.logger.error(f"建立 Gerrit 連結失敗 {project_name}: {str(e)}")
            return ""
    
    def _build_gerrit_link(self, project_name: str, revision: str, target_type: str, remote: str = '') -> str:
        """建立 Gerrit branch/tag 連結"""
        try:
            if not project_name or not revision:
                return ""
            
            # 根據 remote 決定 base URL
            gerrit_base = self._get_gerrit_base_url(remote)
            base_url = f"{gerrit_base}/gerrit/plugins/gitiles"
            
            # 處理 refs/tags/ 或 refs/heads/ 前綴
            clean_revision = revision
            if revision.startswith('refs/tags/'):
                clean_revision = revision[10:]
                target_type = 'tag'
            elif revision.startswith('refs/heads/'):
                clean_revision = revision[11:]
                target_type = 'branch'
            
            if target_type.lower() == 'tag':
                link = f"{base_url}/{project_name}/+/refs/tags/{clean_revision}"
            else:
                link = f"{base_url}/{project_name}/+/refs/heads/{clean_revision}"
            
            self.logger.debug(f"建立 {target_type} 連結: {project_name} -> {link} (remote: {remote})")
            return link
            
        except Exception as e:
            self.logger.error(f"建立 Gerrit 連結失敗 {project_name}: {str(e)}")
            return ""
    
    def _determine_revision_type(self, revision: str) -> str:
        """判斷 revision 是 branch 還是 tag"""
        if not revision:
            return 'Branch'
        
        # 如果以 refs/tags/ 開頭，直接判斷為 Tag
        if revision.startswith('refs/tags/'):
            return 'Tag'
        
        revision_lower = revision.lower()
        
        # 常見的 tag 關鍵字
        tag_keywords = [
            'release', 'tag', 'v1.', 'v2.', 'v3.', 'v4.', 'v5.',
            'stable', 'final', 'rc', 'beta', 'alpha',
            'aosp-', 'platform-',
            '.release', '-release', '_release'
        ]
        
        # 檢查是否包含 tag 關鍵字
        for keyword in tag_keywords:
            if keyword in revision_lower:
                return 'Tag'
        
        # Android tag 版本號格式檢查
        import re
        android_tag_patterns = [
            r'android-\d+\.\d+\.\d+',
            r'android-\d+-.*-release',
            r'android-\d+-.*-beta',
            r'android-\d+-.*-rc',
            r'android-\d+\.\d+\.\d+_r\d+',
        ]
        
        for pattern in android_tag_patterns:
            if re.search(pattern, revision_lower):
                return 'Tag'
        
        # 分支格式檢查
        if '/' in revision:
            branch_indicators = [
                '/master', '/main', '/develop', '/dev',
                '/premp', '/mp', '/wave', '/backup',
                'realtek/', 'refs/heads/'
            ]
            
            for indicator in branch_indicators:
                if indicator in revision_lower:
                    return 'Branch'
        
        # 檢查版本號格式
        version_patterns = [
            r'^v?\d+\.\d+$',
            r'^v?\d+\.\d+\.\d+$',
            r'^api-\d+$',
        ]
        
        for pattern in version_patterns:
            if re.match(pattern, revision_lower):
                return 'Tag'
        
        return 'Branch'

    def _renumber_projects(self, projects: List[Dict]) -> List[Dict]:
        """重新編號專案列表的 SN"""
        for i, project in enumerate(projects, 1):
            project['SN'] = i
        return projects
    
    def _add_links_to_projects(self, projects: List[Dict]) -> List[Dict]:
        """為專案添加 branch/tag 連結資訊"""
        projects_with_links = []
        
        revision_count = 0
        dest_branch_count = 0
        hash_revision_count = 0
        branch_revision_count = 0
        upstream_used_count = 0
        
        for project in projects:
            enhanced_project = project.copy()
            
            project_name = project.get('name', '')
            remote = project.get('remote', '')
            
            # 統計原始資料
            revision = project.get('revision', '')
            dest_branch = project.get('dest-branch', '')
            upstream = project.get('upstream', '')
            
            if revision:
                revision_count += 1
                if self._is_revision_hash(revision):
                    hash_revision_count += 1
                else:
                    branch_revision_count += 1
            if dest_branch:
                dest_branch_count += 1
            
            # 使用新邏輯取得用於建立連結的 revision
            link_revision = self._get_effective_revision_for_link(project)
            
            # 記錄是否使用了 upstream
            if self._is_revision_hash(revision) and upstream:
                upstream_used_count += 1
            
            # 建立 branch_link
            if link_revision:
                revision_type = self._determine_revision_type(link_revision)
                branch_link = self._build_gerrit_link(project_name, link_revision, revision_type, remote)
                self.logger.debug(f"為專案 {project_name} 建立 branch_link: {link_revision} -> {revision_type} -> {branch_link[:50]}...")
            else:
                branch_link = ""
                self.logger.debug(f"專案 {project_name} 沒有有效 revision，branch_link 為空")
            
            # 目標 branch 資訊
            target_branch = project.get('target_branch', '')
            target_type = project.get('target_type', 'Branch')
            
            # 建立 target_branch_link
            target_branch_link = self._build_gerrit_link(project_name, target_branch, target_type, remote)
            
            # revision_diff 欄位將使用 Excel 公式
            revision_diff = ''
            
            # 添加所有欄位
            enhanced_project['branch_link'] = branch_link
            enhanced_project['target_branch_link'] = target_branch_link
            
            projects_with_links.append(enhanced_project)
        
        self.logger.info(f"已為 {len(projects_with_links)} 個專案添加連結資訊")
        self.logger.info(f"🔗 branch_link 邏輯: Hash revision 使用 upstream，Branch revision 使用 revision")
        self.logger.info(f"📊 欄位統計:")
        self.logger.info(f"  - revision 欄位有值: {revision_count}")
        self.logger.info(f"  - dest-branch 欄位有值: {dest_branch_count}")
        self.logger.info(f"  - 🔸 Hash revision: {hash_revision_count}")
        self.logger.info(f"  - 🔹 Branch revision: {branch_revision_count}")
        self.logger.info(f"  - ⬆️ 使用 upstream 建立連結: {upstream_used_count}")
        
        return projects_with_links

    def _set_revision_diff_formulas(self, writer):
        """設定 revision_diff 欄位的 Excel 公式"""
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
                    
                    # 設定欄寬
                    worksheet.column_dimensions[diff_letter].width = 12
                    
                    for row_num in range(2, worksheet.max_row + 1):
                        # 比對 revision 前8碼
                        formula = (
                            f'=IF(OR({target_letter}{row_num}="-", '
                            f'{target_letter}{row_num}="", '
                            f'{revision_letter}{row_num}=""), '
                            f'"Y", '
                            f'IF(LEFT({revision_letter}{row_num},8)={target_letter}{row_num}, '
                            f'"N", "Y"))'
                        )
                        
                        worksheet[f"{diff_letter}{row_num}"].value = formula
                    
                    self.logger.info(f"已為 '{sheet_name}' 頁籤設定 revision_diff 公式")
                else:
                    self.logger.warning(f"無法為 '{sheet_name}' 頁籤設定公式，缺少必要欄位")
                    
        except Exception as e:
            self.logger.error(f"設定 revision_diff 公式失敗: {str(e)}")

    def _parse_manifest(self, input_file: str) -> List[Dict]:
        """解析 manifest.xml 檔案"""
        try:
            tree = ET.parse(input_file)
            root = tree.getroot()
            
            # 讀取 default 標籤的 remote 和 revision 屬性
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
                # 取得專案的 remote
                project_remote = project.get('remote', '')
                if not project_remote and default_remote:
                    project_remote = default_remote
                
                # 取得專案的 revision
                project_revision = project.get('revision', '')
                if not project_revision and project_remote == 'rtk' and default_revision:
                    project_revision = default_revision
                    applied_default_revision_count += 1
                
                project_data = {
                    'name': project.get('name', ''),
                    'path': project.get('path', ''),
                    'revision': project_revision,
                    'upstream': project.get('upstream', ''),
                    'dest-branch': project.get('dest-branch', ''),
                    'groups': project.get('groups', ''),
                    'clone-depth': project.get('clone-depth', ''),
                    'remote': project_remote
                }
                projects.append(project_data)
            
            self.logger.info(f"解析完成，共 {len(projects)} 個專案")
            
            if applied_default_revision_count > 0:
                self.logger.info(f"✅ 已為 {applied_default_revision_count} 個 rtk remote 專案應用預設 revision")
            
            return projects
            
        except Exception as e:
            self.logger.error(f"解析 manifest 檔案失敗: {str(e)}")
            return []

    def _is_tag_reference(self, reference: str) -> bool:
        """判斷參考是否為 Tag"""
        if not reference:
            return False
        return reference.startswith('refs/tags/')

    def _auto_detect_remote(self, project: Dict) -> str:
        """
        🔥 修正版：自動偵測專案的 remote
        ⚠️  注意：不能只看專案名稱，要考慮多種因素
        
        Args:
            project: 專案字典
            
        Returns:
            偵測到的 remote 類型
        """
        try:
            project_name = project.get('name', '')
            remote = project.get('remote', '')
            
            # 如果已經有 remote，直接使用（這是最可靠的）
            if remote:
                self.logger.debug(f"專案 {project_name} 已有 remote: {remote}")
                return remote
            
            # 🔥 檢查 revision、upstream、dest-branch 等欄位的線索
            # 這些比專案名稱更可靠
            for field in ['revision', 'upstream', 'dest-branch']:
                value = project.get(field, '')
                if value:
                    # 如果包含明顯的 prebuilt 路徑或標識
                    if '/prebuilt/' in value.lower() or value.startswith('refs/heads/prebuilt/'):
                        detected_remote = 'rtk-prebuilt'
                        self.logger.debug(f"根據 {field} 偵測 remote: {value} -> {detected_remote}")
                        return detected_remote
            
            # 🔥 保守的專案名稱判斷（降低優先級）
            # 只有在沒有其他線索時才使用專案名稱
            if 'prebuilt' in project_name.lower():
                # 但要更嚴格的判斷條件
                if '/prebuilt/' in project_name or project_name.endswith('_prebuilt'):
                    detected_remote = 'rtk-prebuilt'
                    self.logger.debug(f"根據專案名稱格式偵測 remote: {project_name} -> {detected_remote}")
                    return detected_remote
            
            # 🔥 預設為 rtk（大多數專案都是這個）
            detected_remote = 'rtk'
            self.logger.debug(f"預設 remote: {project_name} -> {detected_remote}")
            return detected_remote
            
        except Exception as e:
            self.logger.warning(f"自動偵測 remote 失敗: {str(e)}")
            return 'rtk'  # 預設值
        """取得或建立 rtk-prebuilt 專用的 GerritManager"""
        if not hasattr(self, '_prebuilt_gerrit_manager'):
            from gerrit_manager import GerritManager
            self._prebuilt_gerrit_manager = GerritManager()
            
            prebuilt_base = self._get_gerrit_base_url('rtk-prebuilt')
            self._prebuilt_gerrit_manager.base_url = prebuilt_base
            self._prebuilt_gerrit_manager.api_url = f"{prebuilt_base}/a"
            
            self.logger.info(f"建立 rtk-prebuilt 專用 GerritManager: {prebuilt_base}")
        
        return self._prebuilt_gerrit_manager
    
    def _check_target_tag_exists(self, project_name: str, target_tag: str, remote: str = '') -> Dict[str, str]:
        """檢查目標 Tag 是否存在"""
        result = {
            'exists_status': 'N',
            'revision': ''
        }
        
        try:
            if not project_name or not target_tag:
                return result
            
            tag_name = target_tag
            if tag_name.startswith('refs/tags/'):
                tag_name = tag_name[10:]
            
            # 根據 remote 選擇 GerritManager
            if remote == 'rtk-prebuilt':
                temp_gerrit = self._get_prebuilt_gerrit_manager()
            else:
                temp_gerrit = self.gerrit_manager
            
            tag_info = temp_gerrit.query_tag(project_name, tag_name)
            
            if tag_info['exists']:
                result['exists_status'] = 'Y'
                result['revision'] = tag_info['revision']
            
        except Exception as e:
            self.logger.debug(f"檢查 Tag 失敗: {project_name} - {target_tag}: {str(e)}")
        
        return result

    def _get_prebuilt_gerrit_manager(self):
        """取得或建立 rtk-prebuilt 專用的 GerritManager"""
        if not hasattr(self, '_prebuilt_gerrit_manager'):
            from gerrit_manager import GerritManager
            self._prebuilt_gerrit_manager = GerritManager()
            
            prebuilt_base = self._get_gerrit_base_url('rtk-prebuilt')
            self._prebuilt_gerrit_manager.base_url = prebuilt_base
            self._prebuilt_gerrit_manager.api_url = f"{prebuilt_base}/a"
            
            self.logger.info(f"建立 rtk-prebuilt 專用 GerritManager: {prebuilt_base}")
        
        return self._prebuilt_gerrit_manager

    def _check_target_branch_exists(self, project_name: str, target_branch: str, remote: str = '') -> Dict[str, str]:
        """
        🔥 修正版：檢查目標分支是否存在 - 根據 remote 欄位直接決定 Gerrit 服務器
        """
        result = {
            'exists_status': 'N',
            'revision': ''
        }
        
        try:
            if not project_name or not target_branch:
                self.logger.debug(f"參數不完整: project_name={project_name}, target_branch={target_branch}")
                return result
            
            # 🔥 修正：根據 remote 欄位直接決定使用哪個 Gerrit 服務器
            if remote == 'rtk-prebuilt':
                # 使用 rtk-prebuilt Gerrit 服務器
                gerrit_server = self._get_gerrit_base_url('rtk-prebuilt')
                self.logger.debug(f"使用 rtk-prebuilt Gerrit 服務器: {gerrit_server}")
                branch_result = self._test_branch_with_remote(project_name, target_branch, 'rtk-prebuilt')
                
                if branch_result['exists']:
                    self.logger.debug(f"✅ 在 rtk-prebuilt 找到分支: {project_name}/{target_branch}")
                    return {
                        'exists_status': 'Y',
                        'revision': branch_result['revision']
                    }
                else:
                    self.logger.debug(f"❌ 在 rtk-prebuilt 未找到分支: {project_name}/{target_branch}")
                    self.logger.debug(f"  錯誤: {branch_result.get('error', '未知')}")
                    return result
            
            else:
                # 使用預設 rtk Gerrit 服務器（包括 remote='' 或 remote='rtk' 的情況）
                gerrit_server = self._get_gerrit_base_url('')
                self.logger.debug(f"使用 rtk Gerrit 服務器: {gerrit_server}")
                branch_result = self._test_branch_with_remote(project_name, target_branch, 'rtk')
                
                if branch_result['exists']:
                    self.logger.debug(f"✅ 在 rtk 找到分支: {project_name}/{target_branch}")
                    return {
                        'exists_status': 'Y',
                        'revision': branch_result['revision']
                    }
                else:
                    self.logger.debug(f"❌ 在 rtk 未找到分支: {project_name}/{target_branch}")
                    self.logger.debug(f"  錯誤: {branch_result.get('error', '未知')}")
                    return result
            
        except Exception as e:
            self.logger.warning(f"檢查分支存在性異常: {project_name}/{target_branch}: {str(e)}")
            import traceback
            self.logger.debug(f"異常詳情: {traceback.format_exc()}")
        
        return result

    def _test_branch_with_remote(self, project_name: str, target_branch: str, remote: str) -> Dict[str, Any]:
        """
        🔥 修正版：使用指定的 remote 測試分支存在性
        
        Args:
            project_name: 專案名稱
            target_branch: 目標分支
            remote: remote 類型 ('rtk' 或 'rtk-prebuilt')
            
        Returns:
            測試結果
        """
        try:
            gerrit_server = self._get_gerrit_base_url(remote)
            self.logger.debug(f"測試分支 {project_name}/{target_branch} 在 {remote}: {gerrit_server}")
            
            # 使用增強版查詢方法
            branch_info = self._query_branch_direct_enhanced(project_name, target_branch, remote)
            
            return branch_info
            
        except Exception as e:
            self.logger.debug(f"測試 remote {remote} 時發生異常: {str(e)}")
            return {
                'exists': False,
                'revision': '',
                'server': remote,
                'error': f'測試 {remote} 異常: {str(e)}'
            }

    def _query_branch_direct_enhanced(self, project_name: str, branch_name: str, remote: str = '') -> Dict[str, Any]:
        """
        🔥 新方法：增強版直接查詢分支 - 根據 remote 選擇正確的 Gerrit 服務器
        """
        try:
            import urllib.parse
            
            encoded_project = urllib.parse.quote(project_name, safe='')
            encoded_branch = urllib.parse.quote(f"refs/heads/{branch_name}", safe='')
            
            # 🔥 根據 remote 選擇對應的 Gerrit 服務器和 GerritManager
            if remote == 'rtk-prebuilt':
                temp_gerrit = self._get_prebuilt_gerrit_manager()
                gerrit_base = self._get_gerrit_base_url('rtk-prebuilt')
                server_type = 'rtk-prebuilt'
            else:
                temp_gerrit = self.gerrit_manager
                gerrit_base = self._get_gerrit_base_url('')
                server_type = 'rtk'
            
            api_url = f"{gerrit_base}/gerrit/a/projects/{encoded_project}/branches/{encoded_branch}"
            
            self.logger.debug(f"查詢分支: {project_name}/{branch_name} 在 {server_type} 服務器")
            self.logger.debug(f"API URL: {api_url}")
            
            response = temp_gerrit._make_request(api_url, timeout=10)
            
            if response.status_code == 200:
                content = response.text
                if content.startswith(")]}'\n"):
                    content = content[5:]
                
                import json
                branch_info = json.loads(content)
                revision = branch_info.get('revision', '')
                
                self.logger.debug(f"✅ 分支查詢成功: {project_name}/{branch_name} -> {revision[:8]}")
                
                return {
                    'exists': True,
                    'revision': revision[:8] if revision else 'Unknown',
                    'server': server_type,
                    'full_revision': revision
                }
            elif response.status_code == 404:
                self.logger.debug(f"❌ 分支不存在: {project_name}/{branch_name} 在 {server_type}")
                return {
                    'exists': False, 
                    'revision': '',
                    'server': server_type,
                    'error': f'分支不存在於 {server_type} 服務器'
                }
            else:
                error_msg = f"HTTP {response.status_code}: {response.text[:100]}"
                self.logger.debug(f"❌ 查詢失敗: {project_name}/{branch_name} - {error_msg}")
                return {
                    'exists': False, 
                    'revision': '',
                    'server': server_type,
                    'error': error_msg
                }
                
        except Exception as e:
            self.logger.debug(f"❌ 查詢分支異常: {project_name}/{branch_name} - {str(e)}")
            return {
                'exists': False, 
                'revision': '',
                'server': remote or 'unknown',
                'error': f'查詢異常: {str(e)}'
            }

    def _query_branch_direct(self, project_name: str, branch_name: str, remote: str = '') -> Dict[str, Any]:
        """直接查詢分支"""
        try:
            import urllib.parse
            
            encoded_project = urllib.parse.quote(project_name, safe='')
            encoded_branch = urllib.parse.quote(f"refs/heads/{branch_name}", safe='')
            
            # 根據 remote 選擇 GerritManager
            if remote == 'rtk-prebuilt':
                temp_gerrit = self._get_prebuilt_gerrit_manager()
                gerrit_base = self._get_gerrit_base_url('rtk-prebuilt')
            else:
                temp_gerrit = self.gerrit_manager
                gerrit_base = self._get_gerrit_base_url('')
            
            api_url = f"{gerrit_base}/gerrit/a/projects/{encoded_project}/branches/{encoded_branch}"
            
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
                return {'exists': False, 'revision': ''}
                
        except Exception as e:
            self.logger.debug(f"查詢分支異常: {str(e)}")
            return {'exists': False, 'revision': ''}
        
    def _determine_source_type(self, project: Dict) -> str:
        """判斷專案的來源分支類型"""
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
            return projects, []
        
        check_fields = ['name', 'revision', 'upstream', 'dest-branch', 'target_branch']
        
        seen = set()
        unique_projects = []
        duplicate_projects = []
        
        for project in projects:
            check_values = tuple(project.get(field, '') for field in check_fields)
            
            if check_values in seen:
                duplicate_projects.append(project)
            else:
                seen.add(check_values)
                unique_projects.append(project)
        
        self.logger.info(f"去重複後：保留 {len(unique_projects)} 個，重複 {len(duplicate_projects)} 個")
        
        return unique_projects, duplicate_projects