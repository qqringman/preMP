"""
SFTP 下載模組（增強版）
處理從 SFTP 伺服器下載檔案的功能
支援雙路徑 Excel 格式（SftpPath 和 compare_SftpPath）
"""
import os
import stat
import paramiko
from typing import List, Dict, Any, Optional, Tuple
import pandas as pd
import utils
import config
from excel_handler import ExcelHandler

logger = utils.setup_logger(__name__)

class SFTPDownloader:
    """SFTP 下載器類別"""
    
    def __init__(self, host: str = None, port: int = None, 
                 username: str = None, password: str = None):
        """
        初始化 SFTP 下載器
        
        Args:
            host: SFTP 伺服器位址
            port: SFTP 連接埠
            username: 使用者名稱
            password: 密碼
        """
        self.host = host or config.SFTP_HOST
        self.port = port or config.SFTP_PORT
        self.username = username or config.SFTP_USERNAME
        self.password = password or config.SFTP_PASSWORD
        self.logger = logger
        self.excel_handler = ExcelHandler()
        self._sftp = None
        self._transport = None
        
    def connect(self) -> None:
        """建立 SFTP 連線"""
        try:
            self.logger.info(f"正在連線到 SFTP 伺服器: {self.host}:{self.port}")
            
            # 建立 Transport
            self._transport = paramiko.Transport((self.host, self.port))
            self._transport.connect(username=self.username, password=self.password)
            
            # 建立 SFTP 客戶端
            self._sftp = paramiko.SFTPClient.from_transport(self._transport)
            
            self.logger.info("SFTP 連線成功")
            
        except Exception as e:
            self.logger.error(f"SFTP 連線失敗: {str(e)}")
            raise
            
    def disconnect(self) -> None:
        """關閉 SFTP 連線"""
        try:
            if self._sftp:
                self._sftp.close()
            if self._transport:
                self._transport.close()
            self.logger.info("SFTP 連線已關閉")
        except Exception as e:
            self.logger.error(f"關閉 SFTP 連線時發生錯誤: {str(e)}")
            
    def _find_file_case_insensitive(self, remote_path: str, filename: str) -> Optional[str]:
        """
        在遠端目錄中不區分大小寫地尋找檔案
        
        Args:
            remote_path: 遠端目錄路徑
            filename: 要尋找的檔案名稱
            
        Returns:
            找到的檔案名稱，或 None
        """
        try:
            files = self._sftp.listdir(remote_path)
            filename_lower = filename.lower()
            
            for file in files:
                if file.lower() == filename_lower:
                    return file
                    
            return None
            
        except Exception as e:
            self.logger.error(f"列出遠端目錄失敗 {remote_path}: {str(e)}")
            return None
            
    def _find_file_recursive(self, remote_path: str, filename: str, max_depth: int = 3, current_depth: int = 0) -> Optional[Tuple[str, str]]:
        """
        遞迴搜尋檔案（不區分大小寫）
        
        Args:
            remote_path: 遠端目錄路徑
            filename: 要尋找的檔案名稱
            max_depth: 最大搜尋深度
            current_depth: 當前深度
            
        Returns:
            (檔案完整路徑, 實際檔案名稱) 或 None
        """
        if current_depth > max_depth:
            return None
            
        try:
            # 先在當前目錄尋找
            actual_filename = self._find_file_case_insensitive(remote_path, filename)
            if actual_filename:
                full_path = os.path.join(remote_path, actual_filename).replace('\\', '/')
                return (full_path, actual_filename)
            
            # 如果沒找到，遞迴搜尋子目錄
            try:
                items = self._sftp.listdir_attr(remote_path)
                for item in items:
                    # 只處理目錄
                    if item.st_mode is not None and stat.S_ISDIR(item.st_mode):
                        subdir_path = os.path.join(remote_path, item.filename).replace('\\', '/')
                        self.logger.debug(f"搜尋子目錄: {subdir_path}")
                        
                        result = self._find_file_recursive(subdir_path, filename, max_depth, current_depth + 1)
                        if result:
                            return result
            except Exception as e:
                self.logger.debug(f"無法列出子目錄 {remote_path}: {str(e)}")
                
            return None
            
        except Exception as e:
            self.logger.error(f"遞迴搜尋失敗 {remote_path}: {str(e)}")
            return None
            
    def download_files(self, ftp_path: str, local_dir: str) -> Tuple[List[str], Dict[str, str]]:
        """
        從 FTP 路徑下載指定的檔案
        
        Args:
            ftp_path: FTP 路徑
            local_dir: 本地目錄
            
        Returns:
            (成功下載的檔案列表, 檔案路徑映射)
        """
        downloaded_files = []
        file_paths = {}  # 記錄每個檔案的實際路徑
        
        try:
            # 確保本地目錄存在
            utils.create_directory(local_dir)
            
            # 判斷檔案格式類型
            is_rddb_format = '/DailyBuild/PrebuildFW' in ftp_path  # RDDB 格式
            is_db_format = '/DailyBuild/' in ftp_path and '/PrebuildFW' not in ftp_path  # DB 格式
            version_number = None
            
            if is_db_format:
                # DB 格式：從路徑中提取版本號
                path_parts = ftp_path.rstrip('/').split('/')
                if path_parts:
                    last_part = path_parts[-1]
                    # 檢查最後一部分是否符合 "版本號_xxx" 的格式
                    if '_' in last_part:
                        first_part = last_part.split('_')[0]
                        if first_part.isdigit():
                            version_number = first_part
                            self.logger.info(f"檢測到 DB 格式，版本號: {version_number}")
            
            # 準備要下載的檔案列表
            target_files = []
            file_mapping = {}  # 映射標準檔名到實際檔名
            
            for target_file in config.TARGET_FILES:
                if is_db_format and version_number:
                    # DB 格式：使用帶版本號的檔名
                    if target_file.lower() == 'manifest.xml':
                        actual_file = f'manifest_{version_number}.xml'
                        target_files.append(actual_file)
                        file_mapping[target_file] = actual_file
                    elif target_file.lower() == 'version.txt':
                        actual_file = f'Version_{version_number}.txt'
                        target_files.append(actual_file)
                        file_mapping[target_file] = actual_file
                    elif target_file.lower() == 'f_version.txt':
                        # F_Version.txt 在 DB 格式中可能不存在或不需要版本號
                        target_files.append(target_file)
                        file_mapping[target_file] = target_file
                else:
                    # RDDB 格式或其他：使用標準檔名
                    target_files.append(target_file)
                    file_mapping[target_file] = target_file
            
            # 下載每個目標檔案
            for original_file, actual_file in file_mapping.items():
                try:
                    # 檢查本地是否已存在該檔案（使用原始檔名）
                    local_file = os.path.join(local_dir, original_file)
                    if os.path.exists(local_file) and config.SKIP_EXISTING_FILES:
                        self.logger.info(f"檔案已存在，跳過下載: {local_file}")
                        downloaded_files.append(original_file)
                        file_paths[original_file] = "已存在"
                        continue
                    
                    # 遞迴尋找檔案（使用實際檔名）
                    self.logger.debug(f"搜尋檔案: {actual_file} in {ftp_path}")
                    result = self._find_file_recursive(ftp_path, actual_file, config.MAX_SEARCH_DEPTH)
                    
                    if result:
                        remote_file, actual_filename = result
                        
                        # 記錄相對路徑
                        relative_path = remote_file.replace(ftp_path, '').lstrip('/')
                        if relative_path != actual_filename:
                            self.logger.info(f"找到檔案 {actual_file} 在子目錄: {os.path.dirname(relative_path)}")
                        
                        # 下載檔案（儲存為原始檔名）
                        self.logger.info(f"下載檔案: {remote_file} -> {local_file}")
                        self._sftp.get(remote_file, local_file)
                        downloaded_files.append(original_file)
                        
                        file_paths[original_file] = relative_path
                    else:
                        # 如果是 DB 格式但找不到帶版本號的檔案，嘗試原始檔名
                        if is_db_format and actual_file != original_file:
                            self.logger.info(f"找不到 {actual_file}，嘗試尋找 {original_file}")
                            result = self._find_file_recursive(ftp_path, original_file, config.MAX_SEARCH_DEPTH)
                            
                            if result:
                                remote_file, actual_filename = result
                                relative_path = remote_file.replace(ftp_path, '').lstrip('/')
                                
                                self.logger.info(f"下載檔案: {remote_file} -> {local_file}")
                                self._sftp.get(remote_file, local_file)
                                downloaded_files.append(original_file)
                                file_paths[original_file] = relative_path
                            else:
                                self.logger.warning(f"找不到檔案: {original_file} 或 {actual_file} in {ftp_path}")
                        else:
                            self.logger.warning(f"找不到檔案: {actual_file} in {ftp_path}")
                            
                except Exception as e:
                    self.logger.error(f"下載檔案失敗 {original_file}: {str(e)}")
                    
        except Exception as e:
            self.logger.error(f"下載過程發生錯誤: {str(e)}")
            
        return downloaded_files, file_paths
        
    def download_from_excel(self, excel_path: str, output_dir: str = None) -> str:
        """
        從 Excel 檔案讀取 FTP 路徑並下載檔案
        支援兩種格式：
        1. 單一路徑格式（ftp path 或 SftpURL）
        2. 雙路徑格式（SftpPath 和 compare_SftpPath）
        
        Args:
            excel_path: Excel 檔案路徑
            output_dir: 輸出目錄
            
        Returns:
            報表檔案路徑
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
                return self._download_from_dual_path_excel(df, output_dir, excel_path)
            else:
                # 單一路徑格式（原有邏輯）
                return self._download_from_single_path_excel(df, output_dir, excel_path)
                
        except Exception as e:
            self.logger.error(f"下載過程發生錯誤: {str(e)}")
            raise
            
        finally:
            self.disconnect()
            
    def _download_from_dual_path_excel(self, df: pd.DataFrame, output_dir: str, excel_path: str) -> str:
        """
        處理雙路徑格式的 Excel 下載
        
        Args:
            df: Excel DataFrame
            output_dir: 輸出目錄
            excel_path: Excel 檔案路徑
            
        Returns:
            報表檔案路徑
        """
        # 建立連線
        self.connect()
        
        # 初始化統計
        if hasattr(self, 'stats'):
            pass  # WebDownloader 已初始化
        else:
            stats = {
                'total': len(df) * 2 * len(config.TARGET_FILES),  # 雙路徑所以 x2
                'downloaded': 0,
                'skipped': 0,
                'failed': 0
            }
        
        # 處理每一筆資料
        report_data = []
        
        for idx, row in df.iterrows():
            # 處理兩個路徑
            paths_to_process = [
                ('SftpPath', 'DB_Folder', 'Module', False),  # 主路徑
                ('compare_SftpPath', 'compare_DB_Folder', 'Module', True)  # 比較路徑
            ]
            
            for path_col, folder_col, module_col, is_compare in paths_to_process:
                ftp_path = row.get(path_col, '')
                db_folder = row.get(folder_col, '')
                module = row.get(module_col, '')
                
                # 檢查空值或 NotFound
                if pd.isna(ftp_path) or str(ftp_path).strip() == '' or \
                   str(ftp_path).strip().lower() in ['notfound', 'sftpnotfound']:
                    self.logger.warning(f"第 {idx + 1} 筆資料的 {path_col} 為空或 NotFound")
                    
                    # 更新統計
                    if hasattr(self, 'stats'):
                        for file in config.TARGET_FILES:
                            self.stats['failed'] += 1
                            if hasattr(self, 'failed_files_list'):
                                self.failed_files_list.append({
                                    'name': file,
                                    'path': '',
                                    'reason': f'{path_col} 為空或 NotFound',
                                    'ftp_path': str(ftp_path) if not pd.isna(ftp_path) else '空值'
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
                    # 使用 DB_Folder 作為資料夾名稱
                    if module:
                        # 如果有 Module，建立 Module/DB_Folder 結構
                        local_dir = os.path.join(output_dir, module, db_folder)
                        local_folder_display = f"{module}/{db_folder}"
                    else:
                        # 否則直接使用 DB_Folder
                        local_dir = os.path.join(output_dir, db_folder)
                        local_folder_display = db_folder
                else:
                    # 如果沒有 DB_Folder，使用原有邏輯解析路徑
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
                        # 無法解析，使用預設名稱
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
                
                # 加入報表資料（每個路徑一筆）
                report_data.append({
                    'SN': f"{idx + 1}-{1 if not is_compare else 2}",
                    '模組': module if module else '未知',
                    '路徑類型': '主路徑' if not is_compare else '比較路徑',
                    'FTP路徑': original_path,
                    '本地資料夾': local_folder_display,
                    '版本資訊檔案': ', '.join(file_info) if file_info else '無'
                })
        
        # 寫入報表
        report_path = self.excel_handler.write_download_report(
            report_data, output_dir, excel_path
        )
        
        return report_path
        
    def _download_from_single_path_excel(self, df: pd.DataFrame, output_dir: str, excel_path: str) -> str:
        """
        處理單一路徑格式的 Excel 下載（原有邏輯）
        
        Args:
            df: Excel DataFrame
            output_dir: 輸出目錄
            excel_path: Excel 檔案路徑
            
        Returns:
            報表檔案路徑
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
        
        # 初始化統計
        if hasattr(self, 'stats'):
            pass  # WebDownloader 已初始化
        else:
            stats = {
                'total': len(df) * len(config.TARGET_FILES),
                'downloaded': 0,
                'skipped': 0,
                'failed': 0
            }
        
        # 處理每一筆資料
        report_data = []
        for idx, row in df.iterrows():
            ftp_path = row[ftp_column]
            
            # 檢查空值或 NotFound
            if pd.isna(ftp_path) or str(ftp_path).strip() == '' or \
               str(ftp_path).strip().lower() in ['notfound', 'sftpnotfound']:
                self.logger.warning(f"第 {idx + 1} 筆資料的 FTP 路徑為空或 NotFound")
                
                # 更新統計
                if hasattr(self, 'stats'):
                    for file in config.TARGET_FILES:
                        self.stats['failed'] += 1
                        if hasattr(self, 'failed_files_list'):
                            self.failed_files_list.append({
                                'name': file,
                                'path': '',
                                'reason': 'FTP 路徑為空或 NotFound',
                                'ftp_path': str(ftp_path) if not pd.isna(ftp_path) else '空值'
                            })
                
                # 加入報表資料
                report_data.append({
                    'SN': idx + 1,
                    '模組': '未知',
                    ftp_column: str(ftp_path) if not pd.isna(ftp_path) else '空值',
                    '本地資料夾': 'N/A',
                    '版本資訊檔案': 'FTP 路徑為空或 NotFound'
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
            
            if module:
                # 根據路徑類型決定頂層目錄
                if '/DailyBuild/PrebuildFW' in ftp_path:
                    top_dir = 'PrebuildFW'
                    is_prebuild = True
                else:
                    top_dir = 'DailyBuild'
                    is_prebuild = False
                
                # 檢查路徑中的關鍵字並決定資料夾後綴
                folder_suffix = ""
                
                if is_prebuild:
                    # PrebuildFW 的關鍵字規則
                    if "mp.google-refplus.wave.backup" in ftp_path:
                        folder_suffix = "-wave.backup"
                    elif "mp.google-refplus.wave" in ftp_path:
                        folder_suffix = "-wave"
                    elif "premp.google-refplus" in ftp_path:
                        folder_suffix = "-premp"
                else:
                    # DailyBuild 的關鍵字規則
                    ftp_path_upper = ftp_path.upper()
                    if "WAVE_BACKUP" in ftp_path_upper or "WAVEBACKUP" in ftp_path_upper:
                        folder_suffix = "-wave.backup"
                    elif "WAVE" in ftp_path_upper and "BACKUP" not in ftp_path_upper:
                        folder_suffix = "-wave"
                    elif "PREMP" in ftp_path_upper:
                        folder_suffix = "-premp"
                
                if jira_id:  # RDDB 格式
                    folder_name = f"{jira_id}{folder_suffix}"
                    local_dir = os.path.join(output_dir, top_dir, module, folder_name)
                    local_folder_display = f"{top_dir}/{module}/{folder_name}"
                else:
                    # DB 格式
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
            
    def test_connection(self) -> bool:
        """
        測試 SFTP 連線
        
        Returns:
            連線是否成功
        """
        try:
            self.connect()
            self.disconnect()
            return True
        except Exception:
            return False