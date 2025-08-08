"""
SFTP Web 下載器 - 包裝原始 SFTPDownloader 以支援 Web 應用
"""
import os
import logging
from typing import List, Dict, Any, Tuple
from sftp_downloader import SFTPDownloader
import config
import utils
import pandas as pd

logger = logging.getLogger(__name__)

class SFTPWebDownloader(SFTPDownloader):
    """Web 應用專用的 SFTP 下載器"""
    
    def __init__(self, host: str = None, port: int = None, 
                 username: str = None, password: str = None):
        """初始化 Web 下載器"""
        super().__init__(host, port, username, password)
        self.stats = {
            'total': 0,
            'downloaded': 0,
            'skipped': 0,
            'failed': 0
        }
        self.progress_callback = None
        self.last_report_path = None
        self.downloaded_files_list = []
        self.skipped_files_list = []
        self.failed_files_list = []
        self.current_progress = 0
        self.invalid_paths_count = 0
        self.invalid_paths_list = []  # 記錄無效路徑詳情
        
    def set_progress_callback(self, callback):
        """設定進度回調函數"""
        self.progress_callback = callback
    
    def _is_valid_ftp_path(self, ftp_path) -> bool:
        """
        檢查是否為有效的 FTP 路徑
        
        Args:
            ftp_path: FTP 路徑
            
        Returns:
            是否為有效路徑
        """
        # 檢查空值
        if pd.isna(ftp_path) or ftp_path is None:
            return False
            
        # 轉換為字串並去除空白
        path_str = str(ftp_path).strip()
        
        # 檢查是否為空字串
        if not path_str:
            return False
            
        # 檢查是否為 NotFound 標記（不區分大小寫）
        path_lower = path_str.lower()
        invalid_markers = ['notfound', 'sftpnotfound', 'not found', 'sftp not found', 
                          'na', 'n/a', 'none', 'null', '無', '空', 'error', 'invalid']
        
        for marker in invalid_markers:
            if marker in path_lower:
                return False
            
        # 檢查是否為有效的路徑格式
        # 有效路徑應該以 / 開頭或包含路徑分隔符
        if not ('/' in path_str or '\\' in path_str):
            return False
            
        return True
    
    def download_from_excel(self, excel_path: str, output_dir: str = None) -> str:
        """
        覆寫父類方法，在處理前過濾無效路徑
        """
        output_dir = output_dir or config.DEFAULT_OUTPUT_DIR
        utils.create_directory(output_dir)
        
        try:
            # 讀取 Excel
            df = self.excel_handler.read_excel(excel_path)
            
            # 檢測 Excel 格式類型
            has_dual_paths = 'SftpPath' in df.columns and 'compare_SftpPath' in df.columns
            has_db_folder = 'DB_Folder' in df.columns and 'compare_DB_Folder' in df.columns
            
            if has_dual_paths:
                # 雙路徑格式
                self.logger.info("檢測到雙路徑格式 Excel (SftpPath + compare_SftpPath)")
                return self._download_from_dual_path_excel_filtered(df, output_dir, excel_path)
            else:
                # 單一路徑格式
                return self._download_from_single_path_excel_filtered(df, output_dir, excel_path)
                
        except Exception as e:
            self.logger.error(f"下載過程發生錯誤: {str(e)}")
            raise
        finally:
            self.disconnect()
    
    def _download_from_single_path_excel_filtered(self, df: pd.DataFrame, output_dir: str, excel_path: str) -> str:
        """
        處理單一路徑格式的 Excel 下載（過濾版本）
        """
        # 尋找可用的 FTP 路徑欄位
        ftp_column = None
        for column in config.FTP_PATH_COLUMNS:
            if column in df.columns:
                ftp_column = column
                self.logger.info(f"使用 FTP 路徑欄位: {column}")
                break
        
        if not ftp_column:
            raise ValueError(f"Excel 必須包含以下其中一個欄位: {', '.join(config.FTP_PATH_COLUMNS)}")
        
        # 建立連線
        self.connect()
        
        # 處理每一筆資料
        report_data = []
        for idx, row in df.iterrows():
            ftp_path = row[ftp_column]
            
            # 檢查是否為有效路徑
            if not self._is_valid_ftp_path(ftp_path):
                self.invalid_paths_count += 1
                self.invalid_paths_list.append({
                    'index': idx + 1,
                    'path': str(ftp_path) if not pd.isna(ftp_path) else '空值',
                    'reason': '無效路徑（NotFound 或空值）'
                })
                self.logger.info(f"第 {idx + 1} 筆資料的 FTP 路徑無效，跳過: {ftp_path}")
                
                # 加入報表資料（標記為無效）
                report_data.append({
                    'SN': idx + 1,
                    '模組': '未知',
                    ftp_column: str(ftp_path) if not pd.isna(ftp_path) else '空值',
                    '本地資料夾': 'N/A',
                    '版本資訊檔案': '路徑無效（不計入統計）'
                })
                continue
            
            # 進行路徑替換
            original_path = str(ftp_path)
            for old_path, new_path in config.PATH_REPLACEMENTS.items():
                if old_path in ftp_path:
                    ftp_path = ftp_path.replace(old_path, new_path)
                    self.logger.info(f"路徑替換: {old_path} -> {new_path}")
            
            # 解析模組和 JIRA ID
            module, jira_id = utils.parse_module_and_jira(ftp_path)
            
            # 建立本地目錄結構
            if module:
                if '/DailyBuild/PrebuildFW' in ftp_path:
                    top_dir = 'PrebuildFW'
                    is_prebuild = True
                else:
                    top_dir = 'DailyBuild'
                    is_prebuild = False
                
                # 檢查路徑中的關鍵字並決定資料夾後綴
                folder_suffix = ""
                if is_prebuild:
                    if "mp.google-refplus.wave.backup" in ftp_path:
                        folder_suffix = "-wave.backup"
                    elif "mp.google-refplus.wave" in ftp_path:
                        folder_suffix = "-wave"
                    elif "premp.google-refplus" in ftp_path:
                        folder_suffix = "-premp"
                else:
                    ftp_path_upper = ftp_path.upper()
                    if "WAVE_BACKUP" in ftp_path_upper or "WAVEBACKUP" in ftp_path_upper:
                        folder_suffix = "-wave.backup"
                    elif "WAVE" in ftp_path_upper and "BACKUP" not in ftp_path_upper:
                        folder_suffix = "-wave"
                    elif "PREMP" in ftp_path_upper:
                        folder_suffix = "-premp"
                
                if jira_id:
                    folder_name = f"{jira_id}{folder_suffix}"
                    local_dir = os.path.join(output_dir, top_dir, module, folder_name)
                    local_folder_display = f"{top_dir}/{module}/{folder_name}"
                else:
                    if '/' in module:
                        platform, db_number = module.split('/', 1)
                        folder_name = f"{db_number}{folder_suffix}"
                        local_dir = os.path.join(output_dir, top_dir, platform, folder_name)
                        local_folder_display = f"{top_dir}/{platform}/{folder_name}"
                    else:
                        local_dir = os.path.join(output_dir, top_dir, module)
                        local_folder_display = f"{top_dir}/{module}"
                
                # 下載檔案
                downloaded_files, file_paths = self.download_files(ftp_path, local_dir)
                
                # 準備檔案資訊字串
                file_info = []
                for file in downloaded_files:
                    if file in file_paths:
                        path = file_paths[file]
                        if path == "已存在":
                            file_info.append(f"{file} (已存在)")
                        elif path and path != file:
                            file_info.append(f"{file} ({path})")
                        else:
                            file_info.append(file)
                    else:
                        file_info.append(file)
                
                # 加入報表資料
                report_data.append({
                    'SN': idx + 1,
                    '模組': module.split('/')[0] if '/' in module else module,
                    ftp_column: original_path,
                    '本地資料夾': local_folder_display,
                    '版本資訊檔案': ', '.join(file_info) if file_info else '無'
                })
            else:
                self.logger.warning(f"無法解析 FTP 路徑: {ftp_path}")
                report_data.append({
                    'SN': idx + 1,
                    '模組': '未知',
                    ftp_column: original_path,
                    '本地資料夾': '解析失敗',
                    '版本資訊檔案': '解析失敗'
                })
        
        # 寫入報表
        report_path = self.excel_handler.write_download_report(
            report_data, output_dir, excel_path
        )
        
        return report_path
    
    def _download_from_dual_path_excel_filtered(self, df: pd.DataFrame, output_dir: str, excel_path: str) -> str:
        """
        處理雙路徑格式的 Excel 下載（過濾版本）
        """
        # 建立連線
        self.connect()
        
        # 處理每一筆資料
        report_data = []
        
        for idx, row in df.iterrows():
            # 處理兩個路徑
            paths_to_process = [
                ('SftpPath', 'DB_Folder', 'Module', False),
                ('compare_SftpPath', 'compare_DB_Folder', 'Module', True)
            ]
            
            for path_col, folder_col, module_col, is_compare in paths_to_process:
                ftp_path = row.get(path_col, '')
                db_folder = row.get(folder_col, '')
                module = row.get(module_col, '')
                
                # 檢查是否為有效路徑
                if not self._is_valid_ftp_path(ftp_path):
                    self.invalid_paths_count += 1
                    self.invalid_paths_list.append({
                        'index': f"{idx + 1}-{2 if is_compare else 1}",
                        'path': str(ftp_path) if not pd.isna(ftp_path) else '空值',
                        'column': path_col,
                        'reason': '無效路徑（NotFound 或空值）'
                    })
                    self.logger.info(f"第 {idx + 1} 筆資料的 {path_col} 無效，跳過: {ftp_path}")
                    
                    # 不加入任何統計或失敗列表，但加入報表
                    report_data.append({
                        'SN': f"{idx + 1}-{2 if is_compare else 1}",
                        '模組': module if module else '未知',
                        '路徑類型': '比較路徑' if is_compare else '主路徑',
                        'FTP路徑': str(ftp_path) if not pd.isna(ftp_path) else '空值',
                        '本地資料夾': 'N/A',
                        '版本資訊檔案': '路徑無效（不計入統計）'
                    })
                    continue
                
                # 進行路徑替換
                original_path = str(ftp_path)
                for old_path, new_path in config.PATH_REPLACEMENTS.items():
                    if old_path in ftp_path:
                        ftp_path = ftp_path.replace(old_path, new_path)
                        self.logger.info(f"路徑替換: {old_path} -> {new_path}")
                
                # 決定本地目錄結構
                if db_folder:
                    if module:
                        local_dir = os.path.join(output_dir, module, db_folder)
                        local_folder_display = f"{module}/{db_folder}"
                    else:
                        local_dir = os.path.join(output_dir, db_folder)
                        local_folder_display = db_folder
                else:
                    module_parsed, jira_id = utils.parse_module_and_jira(ftp_path)
                    
                    if module_parsed:
                        if '/DailyBuild/PrebuildFW' in ftp_path:
                            top_dir = 'PrebuildFW'
                        else:
                            top_dir = 'DailyBuild'
                        
                        if jira_id:
                            folder_name = jira_id
                            local_dir = os.path.join(output_dir, top_dir, module_parsed, folder_name)
                            local_folder_display = f"{top_dir}/{module_parsed}/{folder_name}"
                        else:
                            if '/' in module_parsed:
                                platform, db_number = module_parsed.split('/', 1)
                                local_dir = os.path.join(output_dir, top_dir, platform, db_number)
                                local_folder_display = f"{top_dir}/{platform}/{db_number}"
                            else:
                                local_dir = os.path.join(output_dir, top_dir, module_parsed)
                                local_folder_display = f"{top_dir}/{module_parsed}"
                    else:
                        local_dir = os.path.join(output_dir, f"unknown_{idx}_{path_col}")
                        local_folder_display = f"unknown_{idx}_{path_col}"
                
                # 下載檔案
                downloaded_files, file_paths = self.download_files(ftp_path, local_dir)
                
                # 準備檔案資訊字串
                file_info = []
                for file in downloaded_files:
                    if file in file_paths:
                        path = file_paths[file]
                        if path == "已存在":
                            file_info.append(f"{file} (已存在)")
                        elif path and path != file:
                            file_info.append(f"{file} ({path})")
                        else:
                            file_info.append(file)
                    else:
                        file_info.append(file)
                
                # 加入報表資料
                report_data.append({
                    'SN': f"{idx + 1}-{2 if is_compare else 1}",
                    '模組': module if module else '未知',
                    '路徑類型': '比較路徑' if is_compare else '主路徑',
                    'FTP路徑': original_path,
                    '本地資料夾': local_folder_display,
                    '版本資訊檔案': ', '.join(file_info) if file_info else '無'
                })
        
        # 寫入報表
        report_path = self.excel_handler.write_download_report(
            report_data, output_dir, excel_path
        )
        
        return report_path
    
    def download_files(self, ftp_path: str, local_dir: str) -> Tuple[List[str], Dict[str, str]]:
        """
        下載檔案（只處理有效路徑）
        注意：此方法應該只被有效路徑調用
        """
        # 呼叫父類方法進行下載
        try:
            downloaded_files, file_paths = super().download_files(ftp_path, local_dir)
        except Exception as e:
            self.logger.error(f"下載過程發生錯誤: {str(e)}")
            return [], {}
        
        # 統計結果
        files_found = 0
        
        for file in config.TARGET_FILES:
            if file in downloaded_files:
                files_found += 1
                
                if file in file_paths and file_paths[file] == "已存在":
                    # 本地已存在，計入跳過
                    self.stats['skipped'] += 1
                    self.skipped_files_list.append({
                        'name': file,
                        'path': os.path.join(local_dir, file),
                        'reason': '檔案已存在',
                        'ftp_path': ftp_path
                    })
                else:
                    # 成功下載
                    self.stats['downloaded'] += 1
                    self.downloaded_files_list.append({
                        'name': file,
                        'path': os.path.join(local_dir, file),
                        'ftp_path': ftp_path
                    })
        
        # 如果有效路徑但沒有找到任何檔案，計為 1 個失敗
        if files_found == 0:
            self.stats['failed'] += 1
            self.failed_files_list.append({
                'name': '路徑無檔案',
                'path': local_dir,
                'reason': '路徑存在但沒有找到任何目標檔案',
                'ftp_path': ftp_path
            })
            self.logger.warning(f"路徑存在但沒有找到任何檔案: {ftp_path}")
        
        # 更新總數
        self.stats['total'] = self.stats['downloaded'] + self.stats['skipped'] + self.stats['failed']
        
        # 更新進度
        if self.progress_callback and self.stats['total'] > 0:
            progress = min(20 + (self.stats['total'] / max(self.stats['total'], 1)) * 70, 90)
            self.current_progress = progress
            
            self.progress_callback(
                progress, 
                'downloading', 
                f'已處理 {self.stats["total"]} 個項目',
                stats=self.stats.copy(),
                files={
                    'downloaded': self.downloaded_files_list.copy(),
                    'skipped': self.skipped_files_list.copy(),
                    'failed': self.failed_files_list.copy()
                }
            )
        
        return downloaded_files, file_paths
    
    def download_from_excel_with_progress(self, excel_path: str, output_dir: str = None):
        """從 Excel 或 CSV 下載並提供進度更新"""
        # 重置統計和檔案列表
        self.stats = {
            'total': 0,
            'downloaded': 0,
            'skipped': 0,
            'failed': 0
        }
        self.downloaded_files_list = []
        self.skipped_files_list = []
        self.failed_files_list = []
        self.invalid_paths_count = 0
        self.invalid_paths_list = []
        self.current_progress = 0
        
        try:
            # 初始進度
            if self.progress_callback:
                file_type = "CSV" if excel_path.lower().endswith('.csv') else "Excel"
                self.progress_callback(
                    0, 
                    'downloading', 
                    f'開始讀取 {file_type} 檔案...', 
                    stats=self.stats.copy()
                )
            
            # 讀取 Excel 或 CSV 來計算預估
            import pandas as pd
            df = self.excel_handler.read_excel(excel_path)
            
            # 計算有效路徑數
            valid_paths = 0
            invalid_paths = 0
            
            # 檢查雙路徑格式
            has_dual_paths = 'SftpPath' in df.columns and 'compare_SftpPath' in df.columns
            
            if has_dual_paths:
                # 雙路徑格式
                for idx, row in df.iterrows():
                    for path_col in ['SftpPath', 'compare_SftpPath']:
                        path = row.get(path_col, '')
                        if self._is_valid_ftp_path(path):
                            valid_paths += 1
                        else:
                            invalid_paths += 1
            else:
                # 單路徑格式
                ftp_columns = ['ftp path', 'SftpURL']
                for col in ftp_columns:
                    if col in df.columns:
                        for val in df[col]:
                            if self._is_valid_ftp_path(val):
                                valid_paths += 1
                            else:
                                invalid_paths += 1
                        break
            
            # 更新初始訊息
            message = f'找到 {valid_paths} 個有效 FTP 路徑'
            if invalid_paths > 0:
                message += f'（{invalid_paths} 個無效路徑將被跳過）'
                
            if self.progress_callback:
                self.progress_callback(
                    5, 
                    'downloading', 
                    message, 
                    stats=self.stats.copy()
                )
            
            # 呼叫下載方法
            report_path = self.download_from_excel(excel_path, output_dir)
            self.last_report_path = report_path
            
            # 確保最終統計正確
            self.stats['total'] = self.stats['downloaded'] + self.stats['skipped'] + self.stats['failed']
            
            # 準備完成訊息
            complete_message = f'下載完成！共處理 {self.stats["total"]} 個項目'
            if self.invalid_paths_count > 0:
                complete_message += f'（跳過 {self.invalid_paths_count} 個無效路徑）'
            
            # 最終進度更新
            if self.progress_callback:
                self.progress_callback(
                    100, 
                    'completed', 
                    complete_message,
                    stats={
                        'total': self.stats['total'],
                        'downloaded': self.stats['downloaded'],
                        'skipped': self.stats['skipped'],
                        'failed': self.stats['failed']
                    },
                    files={
                        'downloaded': self.downloaded_files_list,
                        'skipped': self.skipped_files_list,
                        'failed': self.failed_files_list
                    }
                )
                
            return report_path
            
        except Exception as e:
            # 確保錯誤時也傳送統計
            if self.progress_callback:
                self.progress_callback(
                    self.current_progress, 
                    'error', 
                    f'下載失敗: {str(e)}', 
                    stats=self.stats.copy()
                )
            raise

    def get_download_stats(self):
        """取得下載統計資料（包含檔案列表）"""
        # 確保總數正確
        self.stats['total'] = self.stats['downloaded'] + self.stats['skipped'] + self.stats['failed']
        
        result = {
            'stats': self.stats.copy(),
            'files': {
                'downloaded': self.downloaded_files_list,
                'skipped': self.skipped_files_list,
                'failed': self.failed_files_list
            }
        }
        
        # 如果有無效路徑，加入額外資訊（但不影響統計）
        if self.invalid_paths_count > 0:
            result['invalid_paths'] = {
                'count': self.invalid_paths_count,
                'list': self.invalid_paths_list
            }
            
        return result