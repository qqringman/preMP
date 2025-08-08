"""
Excel 處理模組
處理所有 Excel 和 CSV 檔案的讀寫操作
包含檢查欄位和複製改名功能
"""
import os
import shutil
import pandas as pd
from typing import List, Dict, Any, Optional, Tuple
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
    
    def check_excel_columns(self, file_path: str) -> Dict[str, Any]:
        """
        檢查 Excel 檔案的欄位
        
        Args:
            file_path: Excel 檔案路徑
            
        Returns:
            包含檢查結果的字典
        """
        try:
            # 讀取檔案
            df = self.read_excel(file_path)
            
            # 檢查是否有 SftpPath 和 compare_SftpPath 欄位
            has_sftp_columns = ('SftpPath' in df.columns and 
                               'compare_SftpPath' in df.columns)
            
            # 檢查 RootFolder 欄位
            root_folder = None
            if 'RootFolder' in df.columns:
                # 取得第一個非空的 RootFolder 值
                root_folder_values = df['RootFolder'].dropna()
                if not root_folder_values.empty:
                    root_folder = str(root_folder_values.iloc[0])
            
            self.logger.info(f"檢查 Excel 欄位: has_sftp_columns={has_sftp_columns}, root_folder={root_folder}")
            
            return {
                'has_sftp_columns': has_sftp_columns,
                'root_folder': root_folder,
                'columns': df.columns.tolist()
            }
            
        except Exception as e:
            self.logger.error(f"檢查 Excel 欄位失敗: {str(e)}")
            return {
                'has_sftp_columns': False,
                'root_folder': None,
                'error': str(e)
            }
    
    def copy_and_rename_excel(self, 
                            original_path: str, 
                            download_folder: str,
                            original_name: str,
                            root_folder: Optional[str]) -> Optional[str]:
        """
        複製並改名 Excel 檔案到下載資料夾
        
        Args:
            original_path: 原始 Excel 檔案路徑
            download_folder: 下載資料夾路徑
            original_name: 原始檔案名稱
            root_folder: RootFolder 欄位值
            
        Returns:
            新檔案名稱，如果複製失敗則返回 None
        """
        try:
            # 決定新檔案名稱
            new_name = self._determine_new_name(original_name, root_folder)
            
            if not new_name:
                self.logger.info(f"不需要改名: root_folder={root_folder}")
                return None
            
            # 確保下載資料夾存在
            if not os.path.exists(download_folder):
                os.makedirs(download_folder, exist_ok=True)
            
            # 建立目標路徑
            target_path = os.path.join(download_folder, new_name)
            
            # 複製檔案
            shutil.copy2(original_path, target_path)
            
            self.logger.info(f"Excel 檔案已複製並改名: {original_name} -> {new_name}")
            self.logger.info(f"目標路徑: {target_path}")
            
            return new_name
            
        except Exception as e:
            self.logger.error(f"複製 Excel 檔案失敗: {str(e)}")
            return None
    
    def _determine_new_name(self, original_name: str, root_folder: Optional[str]) -> Optional[str]:
        """
        根據規則決定新檔案名稱
        
        Args:
            original_name: 原始檔案名稱
            root_folder: RootFolder 欄位值
            
        Returns:
            新檔案名稱
        """
        if not root_folder:
            return None
        
        # 將 root_folder 轉換為字串並處理
        root_folder_str = str(root_folder).strip()
        
        # 處理不同的 RootFolder 值
        if root_folder_str == 'DailyBuild':
            return 'DailyBuild_mapping.xlsx'
        elif root_folder_str == '/DailyBuild/PrebuildFW':
            return 'PrebuildFW_mapping.xlsx'
        elif root_folder_str == 'PrebuildFW':
            return 'PrebuildFW_mapping.xlsx'
        
        # 如果不符合任何規則，返回 None
        return None
    
    def process_download_complete(self, 
                                task_id: str,
                                download_folder: str,
                                excel_metadata: Optional[Dict]) -> Dict:
        """
        下載完成後處理 Excel 檔案
        
        Args:
            task_id: 任務 ID
            download_folder: 下載資料夾路徑
            excel_metadata: Excel 檔案的元資料
            
        Returns:
            處理結果
        """
        result = {
            'excel_copied': False,
            'excel_new_name': None
        }
        
        if not excel_metadata:
            self.logger.info("沒有 Excel 元資料，跳過處理")
            return result
        
        # 檢查是否需要複製和改名
        if excel_metadata.get('has_sftp_columns'):
            original_path = excel_metadata.get('filepath')
            original_name = excel_metadata.get('original_name')
            root_folder = excel_metadata.get('root_folder')
            
            self.logger.info(f"處理下載完成: has_sftp_columns=True, root_folder={root_folder}")
            
            if original_path and os.path.exists(original_path):
                new_name = self.copy_and_rename_excel(
                    original_path,
                    download_folder,
                    original_name,
                    root_folder
                )
                
                if new_name:
                    result['excel_copied'] = True
                    result['excel_new_name'] = new_name
                    self.logger.info(f"Excel 檔案處理完成: {new_name}")
                else:
                    self.logger.info("Excel 檔案不需要改名")
            else:
                self.logger.warning(f"原始檔案不存在: {original_path}")
        else:
            self.logger.info("Excel 檔案沒有必要的欄位，跳過處理")
        
        return result
            
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