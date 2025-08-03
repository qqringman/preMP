"""
Excel 處理模組
處理所有 Excel 和 CSV 檔案的讀寫操作
"""
import os
import pandas as pd
from typing import List, Dict, Any
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows
from openpyxl.styles import PatternFill, Font, Alignment
import utils

logger = utils.setup_logger(__name__)

class ExcelHandler:
    """Excel 檔案處理類別"""
    
    def __init__(self):
        self.logger = logger
        
    def _format_worksheet(self, worksheet):
        """
        格式化工作表
        
        Args:
            worksheet: openpyxl 工作表物件
        """
        # 設定標題列格式
        header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        header_font = Font(color="FFFFFF", bold=True)
        
        # 格式化標題列
        for cell in worksheet[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal='center', vertical='center')
        
        # 調整欄寬
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 100)
            worksheet.column_dimensions[column_letter].width = adjusted_width
            
    def read_excel(self, file_path: str) -> pd.DataFrame:
        """
        讀取 Excel 或 CSV 檔案
        
        Args:
            file_path: Excel 或 CSV 檔案路徑
            
        Returns:
            pandas DataFrame
        """
        try:
            # 根據副檔名判斷檔案類型
            file_ext = os.path.splitext(file_path)[1].lower()
            
            if file_ext == '.csv':
                # 讀取 CSV 檔案，嘗試不同的編碼
                encodings = ['utf-8', 'utf-8-sig', 'big5', 'cp950', 'gbk', 'gb18030', 
                            'latin1', 'iso-8859-1', 'cp1252']
                
                df = None
                last_error = None
                
                for encoding in encodings:
                    try:
                        df = pd.read_csv(file_path, encoding=encoding)
                        self.logger.info(f"成功使用 {encoding} 編碼讀取 CSV 檔案: {file_path}")
                        break
                    except UnicodeDecodeError as e:
                        last_error = e
                        continue
                    except Exception as e:
                        # 其他錯誤，直接拋出
                        raise e
                
                if df is None:
                    # 如果所有編碼都失敗，嘗試使用 errors='ignore' 參數
                    try:
                        df = pd.read_csv(file_path, encoding='utf-8', errors='ignore')
                        self.logger.warning(f"使用 utf-8 編碼（忽略錯誤）讀取 CSV 檔案: {file_path}")
                    except Exception:
                        # 最後嘗試使用 python engine
                        try:
                            df = pd.read_csv(file_path, engine='python')
                            self.logger.warning(f"使用 python engine 讀取 CSV 檔案: {file_path}")
                        except Exception:
                            raise ValueError(f"無法讀取 CSV 檔案，嘗試所有編碼都失敗: {last_error}")
                
                return df
                
            elif file_ext in ['.xlsx', '.xls']:
                # 讀取 Excel 檔案
                df = pd.read_excel(file_path)
                self.logger.info(f"成功讀取 Excel 檔案: {file_path}")
                return df
                
            else:
                raise ValueError(f"不支援的檔案格式: {file_ext}。只支援 .csv, .xlsx, .xls")
                
        except Exception as e:
            self.logger.error(f"讀取檔案失敗: {file_path}, 錯誤: {str(e)}")
            raise
            
    def write_download_report(self, data: List[Dict[str, Any]], output_path: str, source_filename: str) -> str:
        """
        寫入下載報表
        
        Args:
            data: 報表資料
            output_path: 輸出路徑
            source_filename: 來源檔案名稱（用於命名）
            
        Returns:
            輸出檔案路徑
        """
        try:
            # 建立 DataFrame
            df = pd.DataFrame(data)
            
            # 確保欄位順序正確
            # 動態尋找 FTP 路徑欄位（可能是 'sftp 路徑' 或 'SftpURL'）
            ftp_columns = ['sftp 路徑', 'SftpURL', 'ftp path']
            ftp_column = None
            for col in ftp_columns:
                if col in df.columns:
                    ftp_column = col
                    break
            
            # 根據實際存在的欄位建立欄位順序
            column_order = ['SN', '模組']
            if ftp_column:
                column_order.append(ftp_column)
            if '本地資料夾' in df.columns:
                column_order.append('本地資料夾')
            column_order.append('版本資訊檔案')
            
            # 只保留存在的欄位
            column_order = [col for col in column_order if col in df.columns]
            df = df[column_order]
            
            # 建立輸出檔名（統一輸出為 .xlsx）
            base_name = os.path.splitext(os.path.basename(source_filename))[0]
            output_file = os.path.join(output_path, f"{base_name}_report.xlsx")
            
            # 寫入 Excel
            with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='下載報表', index=False)
                
                # 格式化工作表
                worksheet = writer.sheets['下載報表']
                self._format_worksheet(worksheet)
                    
            self.logger.info(f"成功寫入下載報表: {output_file}")
            return output_file
            
        except Exception as e:
            self.logger.error(f"寫入下載報表失敗: {str(e)}")
            raise
            
    def write_compare_report(self, module_name: str, different_projects: List[Dict], 
                           added_deleted_projects: List[Dict], output_dir: str) -> str:
        """
        寫入比較報表
        
        Args:
            module_name: 模組名稱
            different_projects: 不同的專案清單
            added_deleted_projects: 新增/刪除的專案清單
            output_dir: 輸出目錄
            
        Returns:
            輸出檔案路徑
        """
        try:
            output_file = os.path.join(output_dir, f"{module_name}_compare.xlsx")
            
            with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
                # 第一個頁籤：不同的 project
                if different_projects:
                    df_diff = pd.DataFrame(different_projects)
                    df_diff.to_excel(writer, sheet_name='不同的專案', index=False)
                else:
                    # 即使沒有資料也建立空的頁籤
                    pd.DataFrame(columns=['SN', 'module', 'name', 'path', 'upstream', 
                                        'dest-branch', 'revision']).to_excel(
                        writer, sheet_name='不同的專案', index=False)
                
                # 第二個頁籤：新增/刪除的項目
                if added_deleted_projects:
                    df_add_del = pd.DataFrame(added_deleted_projects)
                    df_add_del.to_excel(writer, sheet_name='新增刪除項目', index=False)
                else:
                    # 即使沒有資料也建立空的頁籤
                    pd.DataFrame(columns=['SN', '狀態', 'module', 'name', 'path', 
                                        'upstream', 'dest-branch', 'revision']).to_excel(
                        writer, sheet_name='新增刪除項目', index=False)
                
                # 格式化所有工作表
                for sheet_name in writer.sheets:
                    worksheet = writer.sheets[sheet_name]
                    self._format_worksheet(worksheet)
                        
            self.logger.info(f"成功寫入比較報表: {output_file}")
            return output_file
            
        except Exception as e:
            self.logger.error(f"寫入比較報表失敗: {str(e)}")
            raise
            
    def merge_compare_reports(self, compare_files: List[str], output_dir: str) -> str:
        """
        合併所有比較報表
        
        Args:
            compare_files: 比較報表檔案清單
            output_dir: 輸出目錄
            
        Returns:
            輸出檔案路徑
        """
        try:
            output_file = os.path.join(output_dir, "all_compare.xlsx")
            
            all_different = []
            all_added_deleted = []
            
            # 讀取所有比較報表
            for file in compare_files:
                try:
                    # 嘗試讀取不同的專案
                    try:
                        df_diff = pd.read_excel(file, sheet_name='不同的專案')
                        if not df_diff.empty:
                            all_different.append(df_diff)
                    except:
                        # 如果沒有這個頁籤，忽略
                        pass
                    
                    # 嘗試讀取新增刪除項目
                    try:
                        df_add_del = pd.read_excel(file, sheet_name='新增刪除項目')
                        if not df_add_del.empty:
                            all_added_deleted.append(df_add_del)
                    except:
                        # 如果沒有這個頁籤，忽略
                        pass
                except Exception as e:
                    self.logger.warning(f"讀取比較報表失敗: {file}, 錯誤: {str(e)}")
            
            # 寫入合併的報表
            with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
                # 合併不同的專案
                if all_different:
                    df_all_diff = pd.concat(all_different, ignore_index=True)
                    # 重新編號
                    df_all_diff['SN'] = range(1, len(df_all_diff) + 1)
                    df_all_diff.to_excel(writer, sheet_name='所有不同的專案', index=False)
                else:
                    pd.DataFrame(columns=['SN', 'module', 'name', 'path', 'upstream', 
                                        'dest-branch', 'revision']).to_excel(
                        writer, sheet_name='所有不同的專案', index=False)
                
                # 合併新增刪除項目
                if all_added_deleted:
                    df_all_add_del = pd.concat(all_added_deleted, ignore_index=True)
                    # 重新編號
                    df_all_add_del['SN'] = range(1, len(df_all_add_del) + 1)
                    df_all_add_del.to_excel(writer, sheet_name='所有新增刪除項目', index=False)
                else:
                    pd.DataFrame(columns=['SN', '狀態', 'module', 'name', 'path', 
                                        'upstream', 'dest-branch', 'revision']).to_excel(
                        writer, sheet_name='所有新增刪除項目', index=False)
                
                # 格式化所有工作表
                for sheet_name in writer.sheets:
                    worksheet = writer.sheets[sheet_name]
                    self._format_worksheet(worksheet)
                        
            self.logger.info(f"成功寫入合併報表: {output_file}")
            return output_file
            
        except Exception as e:
            self.logger.error(f"合併比較報表失敗: {str(e)}")
            raise