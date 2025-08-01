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
        self.progress_callback = None

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
        
    def download_from_excel(self, excel_file, download_dir, progress_callback=None):
        """從 Excel 檔案下載檔案"""
        self.progress_callback = progress_callback
        
        # 讀取 Excel 檔案
        df = pd.read_excel(excel_file)
        total_files = len(df)
        
        # 建立下載目錄
        if not os.path.exists(download_dir):
            os.makedirs(download_dir)
            
        # 下載結果記錄
        results = []
        
        for idx, row in df.iterrows():
            # 獲取檔案資訊
            ftp_path = row.get('ftp_path', '')
            file_name = os.path.basename(ftp_path)
            
            # 更新進度
            if self.progress_callback:
                self.progress_callback(idx + 1, total_files, f"下載 {file_name}")
            
            try:
                # 下載檔案邏輯
                local_path = os.path.join(download_dir, file_name)
                
                # 檢查是否跳過
                if self.skip_existing and os.path.exists(local_path):
                    results.append({
                        'file': file_name,
                        'status': 'skipped',
                        'message': '檔案已存在'
                    })
                    continue
                
                # 執行下載
                self._download_file(ftp_path, local_path)
                
                results.append({
                    'file': file_name,
                    'status': 'downloaded',
                    'message': '下載成功'
                })
                
            except Exception as e:
                results.append({
                    'file': file_name,
                    'status': 'failed',
                    'message': str(e)
                })
        
        # 生成報告
        report_path = os.path.join(download_dir, 'download_report.xlsx')
        pd.DataFrame(results).to_excel(report_path, index=False)
        
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