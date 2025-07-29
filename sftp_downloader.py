"""
SFTP 下載模組
處理從 SFTP 伺服器下載檔案的功能
"""
import os
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
            
    def download_files(self, ftp_path: str, local_dir: str) -> List[str]:
        """
        從 FTP 路徑下載指定的檔案
        
        Args:
            ftp_path: FTP 路徑
            local_dir: 本地目錄
            
        Returns:
            成功下載的檔案列表
        """
        downloaded_files = []
        
        try:
            # 確保本地目錄存在
            utils.create_directory(local_dir)
            
            # 下載每個目標檔案
            for target_file in config.TARGET_FILES:
                try:
                    # 尋找檔案（不區分大小寫）
                    actual_filename = self._find_file_case_insensitive(ftp_path, target_file)
                    
                    if actual_filename:
                        remote_file = os.path.join(ftp_path, actual_filename).replace('\\', '/')
                        local_file = os.path.join(local_dir, target_file)
                        
                        self.logger.info(f"下載檔案: {remote_file} -> {local_file}")
                        self._sftp.get(remote_file, local_file)
                        downloaded_files.append(target_file)
                    else:
                        self.logger.warning(f"檔案不存在: {ftp_path}/{target_file}")
                        
                except Exception as e:
                    self.logger.error(f"下載檔案失敗 {target_file}: {str(e)}")
                    
        except Exception as e:
            self.logger.error(f"下載過程發生錯誤: {str(e)}")
            
        return downloaded_files
        
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
                
                if module and jira_id:
                    # 建立本地目錄
                    local_dir = os.path.join(output_dir, module, jira_id)
                    
                    # 下載檔案
                    downloaded_files = self.download_files(ftp_path, local_dir)
                    
                    # 加入報表資料
                    report_data.append({
                        'SN': idx + 1,
                        '模組': module,
                        'sftp 路徑': ftp_path,
                        '版本資訊檔案': ', '.join(downloaded_files) if downloaded_files else '無'
                    })
                else:
                    self.logger.warning(f"無法解析 FTP 路徑: {ftp_path}")
                    report_data.append({
                        'SN': idx + 1,
                        '模組': '未知',
                        'sftp 路徑': ftp_path,
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