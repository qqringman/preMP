"""
SFTP 管理模組
處理 SFTP 連線和版本資訊獲取
"""
import os
import sys
import re
from typing import List, Optional, Tuple
import paramiko

# 將上層目錄加入 Python 路徑
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import utils
import config

logger = utils.setup_logger(__name__)

class SFTPManager:
    """SFTP 管理器"""
    
    def __init__(self):
        self.logger = logger
        self._sftp = None
        self._transport = None
        
    def connect(self) -> None:
        """建立 SFTP 連線"""
        try:
            self.logger.info(f"連線到 SFTP: {config.SFTP_HOST}:{config.SFTP_PORT}")
            self._transport = paramiko.Transport((config.SFTP_HOST, config.SFTP_PORT))
            self._transport.connect(username=config.SFTP_USERNAME, password=config.SFTP_PASSWORD)
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
            
    def get_latest_version(self, sftp_path: str) -> Tuple[str, str, str]:
        """
        取得最新版本資訊（版號最大的）
        
        Args:
            sftp_path: SFTP 路徑
            
        Returns:
            (db_folder, db_version, full_path)
        """
        try:
            # 從路徑中提取基礎資訊
            path_parts = sftp_path.rstrip('/').split('/')
            db_folder = path_parts[-1] if path_parts else ''
            
            # 列出目錄內容
            try:
                items = self._sftp.listdir(sftp_path)
            except:
                self.logger.warning(f"無法列出目錄: {sftp_path}")
                return db_folder, '', sftp_path
            
            # 過濾版本資料夾（格式: 數字開頭，如 536_all_202507312300）
            version_folders = []
            for item in items:
                # 檢查是否為版本資料夾格式
                match = re.match(r'^(\d+)', item)
                if match:
                    version_num = int(match.group(1))
                    version_folders.append((version_num, item))
            
            if not version_folders:
                self.logger.warning(f"找不到版本資料夾: {sftp_path}")
                return db_folder, '', sftp_path
            
            # 按版本號排序，取最大的（最新的）
            version_folders.sort(key=lambda x: x[0], reverse=True)
            latest_version = version_folders[0][1]
            full_path = f"{sftp_path}/{latest_version}"
            
            self.logger.info(f"找到最新版本: {latest_version} (版號: {version_folders[0][0]}) in {sftp_path}")
            return db_folder, latest_version, full_path
            
        except Exception as e:
            self.logger.error(f"取得版本資訊失敗: {str(e)}")
            return '', '', sftp_path
            
    def get_specific_version(self, sftp_path: str, db_info: str) -> Tuple[str, str, str]:
        """
        取得特定版本資訊
        
        Args:
            sftp_path: SFTP 基礎路徑
            db_info: DB資訊 (格式: DB2302#196)
            
        Returns:
            (db_folder, db_version, full_path)
        """
        try:
            # 解析 db_info
            if '#' not in db_info:
                self.logger.warning(f"DB資訊格式錯誤: {db_info}")
                return self.get_latest_version(sftp_path)
            
            db_number, version_prefix = db_info.split('#')
            
            # 列出目錄找到對應的 DB 資料夾
            parent_path = '/'.join(sftp_path.rstrip('/').split('/')[:-1])
            items = self._sftp.listdir(parent_path)
            
            db_folder = None
            for item in items:
                if item.startswith(f"{db_number}_"):
                    db_folder = item
                    break
            
            if not db_folder:
                self.logger.warning(f"找不到 DB 資料夾: {db_number}")
                return '', '', sftp_path
            
            # 建構完整路徑
            db_path = f"{parent_path}/{db_folder}"
            
            # 列出版本資料夾
            version_items = self._sftp.listdir(db_path)
            
            # 找到對應版本
            for version_item in version_items:
                if version_item.startswith(f"{version_prefix}_"):
                    full_path = f"{db_path}/{version_item}"
                    self.logger.info(f"找到指定版本: {version_item}")
                    return db_folder, version_item, full_path
            
            self.logger.warning(f"找不到指定版本: {version_prefix}")
            return db_folder, '', db_path
            
        except Exception as e:
            self.logger.error(f"取得特定版本失敗: {str(e)}")
            return '', '', sftp_path