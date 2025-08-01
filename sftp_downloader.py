"""
SFTP 下載模組
處理從 SFTP 伺服器下載檔案的功能
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
                # 例如：/DailyBuild/MacArthur7P/DB1857_Mac7p_FW_Android12_Ref_Design_Cert/904_all_202507300838
                # 或：/DailyBuild/Merlin7/DB2857_Merlin7_32Bit_FW_Android14_Ref_Plus_PreMP_GoogleGMS/69_202507292300
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
                        # 先嘗試原始名稱
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
                                self.logger.warning(f"找不到檔案: {original_file} 或 {actual_file} in {ftp_path} (包含子目錄)")
                        else:
                            self.logger.warning(f"找不到檔案: {actual_file} in {ftp_path} (包含子目錄)")
                            
                except Exception as e:
                    self.logger.error(f"下載檔案失敗 {original_file}: {str(e)}")
                    
        except Exception as e:
            self.logger.error(f"下載過程發生錯誤: {str(e)}")
            
        return downloaded_files, file_paths
        
    def download_from_excel(self, excel_path: str, output_dir: str = None) -> str:
        """
        從 Excel 檔案讀取 FTP 路徑並下載檔案
        
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
            
            # 驗證必要欄位
            if not utils.validate_excel_columns(df, [config.FTP_PATH_COLUMN]):
                raise ValueError(f"Excel 必須包含 '{config.FTP_PATH_COLUMN}' 欄位")
                
            # 建立連線
            self.connect()
            
            # 處理每一筆資料
            report_data = []
            for idx, row in df.iterrows():
                ftp_path = row[config.FTP_PATH_COLUMN]
                
                if pd.isna(ftp_path):
                    self.logger.warning(f"第 {idx + 1} 筆資料的 FTP 路徑為空")
                    continue
                    
                # 解析模組和 JIRA ID
                module, jira_id = utils.parse_module_and_jira(ftp_path)
                
                if module:
                    # 根據路徑類型決定頂層目錄
                    if '/DailyBuild/PrebuildFW' in ftp_path:
                        # RDDB 格式：PrebuildFW/模組/RDDB-XXX
                        top_dir = 'PrebuildFW'
                        is_prebuild = True
                    else:
                        # DB 格式：DailyBuild/平台/DBXXXX
                        top_dir = 'DailyBuild'
                        is_prebuild = False
                    
                    # 檢查路徑中的關鍵字並決定資料夾後綴
                    folder_suffix = ""
                    
                    if is_prebuild:
                        # PrebuildFW 的關鍵字規則（原有邏輯）
                        if "mp.google-refplus.wave.backup" in ftp_path:
                            folder_suffix = "-wave.backup"
                        elif "mp.google-refplus.wave" in ftp_path:
                            folder_suffix = "-wave"
                        elif "premp.google-refplus" in ftp_path:
                            folder_suffix = "-premp"
                    else:
                        # DailyBuild 的關鍵字規則（新邏輯）
                        # 不區分大小寫的檢查
                        ftp_path_upper = ftp_path.upper()
                        if "WAVE_BACKUP" in ftp_path_upper or "WAVEBACKUP" in ftp_path_upper:
                            folder_suffix = "-wave.backup"
                        elif "WAVE" in ftp_path_upper and "BACKUP" not in ftp_path_upper:
                            folder_suffix = "-wave"
                        elif "PREMP" in ftp_path_upper:
                            folder_suffix = "-premp"
                    
                    if jira_id:  # RDDB 格式（有 JIRA ID）
                        # 建立本地目錄結構：PrebuildFW/模組/RDDB-XXX-後綴
                        folder_name = f"{jira_id}{folder_suffix}"
                        local_dir = os.path.join(output_dir, top_dir, module, folder_name)
                        
                        # 用於報表顯示的路徑
                        local_folder_display = f"{top_dir}/{module}/{folder_name}"
                    else:
                        # DB 格式（如 Merlin7/DB2302）
                        # module 格式為 "Merlin7/DB2302"，需要分解
                        if '/' in module:
                            platform, db_number = module.split('/', 1)
                            # 建立本地目錄結構：DailyBuild/平台/DBXXXX-後綴
                            folder_name = f"{db_number}{folder_suffix}"
                            local_dir = os.path.join(output_dir, top_dir, platform, folder_name)
                            
                            # 用於報表顯示的路徑
                            local_folder_display = f"{top_dir}/{platform}/{folder_name}"
                        else:
                            # 備用處理
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
                        '模組': module.split('/')[0] if '/' in module else module,  # 對於 Merlin7/DB2302，只顯示 Merlin7
                        'sftp 路徑': ftp_path,
                        '本地資料夾': local_folder_display,
                        '版本資訊檔案': ', '.join(file_info) if file_info else '無'
                    })
                else:
                    self.logger.warning(f"無法解析 FTP 路徑: {ftp_path}")
                    report_data.append({
                        'SN': idx + 1,
                        '模組': '未知',
                        'sftp 路徑': ftp_path,
                        '本地資料夾': '解析失敗',
                        '版本資訊檔案': '解析失敗'
                    })
                    
            # 寫入報表
            report_path = self.excel_handler.write_download_report(
                report_data, output_dir, excel_path
            )
            
            return report_path
            
        except Exception as e:
            self.logger.error(f"下載過程發生錯誤: {str(e)}")
            raise
            
        finally:
            self.disconnect()
            
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