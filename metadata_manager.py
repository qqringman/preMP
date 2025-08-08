"""
元資料管理模組
集中管理 Excel 檔案的元資料，避免全域變數問題
"""
import os
import json
from typing import Dict, Optional
import utils

logger = utils.setup_logger(__name__)

class MetadataManager:
    """元資料管理器"""
    
    def __init__(self):
        self.metadata_cache = {}
        self.logger = logger
        
    def store_metadata(self, filepath: str, metadata: Dict) -> None:
        """
        儲存檔案元資料
        
        Args:
            filepath: 檔案路徑
            metadata: 元資料字典
        """
        # 使用絕對路徑作為 key
        abs_path = os.path.abspath(filepath)
        self.metadata_cache[abs_path] = metadata
        
        # 也儲存相對路徑版本
        self.metadata_cache[filepath] = metadata
        
        self.logger.info(f"儲存元資料: {filepath}")
        self.logger.debug(f"元資料內容: {metadata}")
        
    def get_metadata(self, filepath: str) -> Optional[Dict]:
        """
        獲取檔案元資料
        
        Args:
            filepath: 檔案路徑
            
        Returns:
            元資料字典，如果不存在則返回 None
        """
        # 嘗試絕對路徑
        abs_path = os.path.abspath(filepath)
        if abs_path in self.metadata_cache:
            return self.metadata_cache[abs_path]
            
        # 嘗試相對路徑
        if filepath in self.metadata_cache:
            return self.metadata_cache[filepath]
            
        self.logger.warning(f"找不到元資料: {filepath}")
        return None
        
    def clear_metadata(self, filepath: str = None) -> None:
        """
        清除元資料
        
        Args:
            filepath: 要清除的檔案路徑，如果為 None 則清除全部
        """
        if filepath:
            abs_path = os.path.abspath(filepath)
            self.metadata_cache.pop(abs_path, None)
            self.metadata_cache.pop(filepath, None)
            self.logger.info(f"清除元資料: {filepath}")
        else:
            self.metadata_cache.clear()
            self.logger.info("清除所有元資料")
            
    def list_metadata(self) -> Dict:
        """
        列出所有元資料
        
        Returns:
            所有元資料的字典
        """
        return self.metadata_cache.copy()

# 建立全域實例
metadata_manager = MetadataManager()