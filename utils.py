"""
共用工具函數
"""
import os
import re
import logging
from datetime import datetime
from typing import Tuple, Optional
import config

def setup_logger(name: str) -> logging.Logger:
    """設定日誌記錄器"""
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, config.LOG_LEVEL))
    
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(config.LOG_FORMAT)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    return logger

def parse_module_and_jira(ftp_path: str) -> Tuple[Optional[str], Optional[str]]:
    """
    從 FTP 路徑解析模組名稱和 JIRA ID
    
    Args:
        ftp_path: FTP 路徑
        
    Returns:
        (module, jira_id) 或 (None, None) 如果解析失敗
    """
    # RDDB 格式：/DailyBuild/PrebuildFW/模組/RDDB-XXX_...
    if '/PrebuildFW/' in ftp_path:
        match = re.search(config.MODULE_PATTERN, ftp_path)
        if match:
            return match.group(1), match.group(2)
    
    # DB 格式：/DailyBuild/平台/DBXXXX_...
    # 例如：/DailyBuild/Merlin7/DB2857_Merlin7_32Bit_FW.../版本號_日期
    elif '/DailyBuild/' in ftp_path and '/PrebuildFW/' not in ftp_path:
        # 提取平台名稱和 DB 編號
        pattern = r'/DailyBuild/([^/]+)/(DB\d+)_'
        match = re.search(pattern, ftp_path)
        if match:
            platform = match.group(1)  # 例如：Merlin7, MacArthur7P
            db_number = match.group(2)  # 例如：DB2857, DB1857
            # 返回 "平台/DB編號" 格式
            return f"{platform}/{db_number}", None
    
    return None, None

def create_directory(path: str) -> None:
    """建立目錄（如果不存在）"""
    if not os.path.exists(path):
        os.makedirs(path)
        
def get_timestamp() -> str:
    """取得時間戳記字串"""
    return datetime.now().strftime('%Y%m%d_%H%M%S')

def find_file_case_insensitive(directory: str, filename: str) -> Optional[str]:
    """
    不區分大小寫地尋找檔案
    
    Args:
        directory: 目錄路徑
        filename: 要尋找的檔案名稱
        
    Returns:
        找到的檔案完整路徑，或 None
    """
    if not os.path.exists(directory):
        return None
        
    filename_lower = filename.lower()
    for file in os.listdir(directory):
        if file.lower() == filename_lower:
            return os.path.join(directory, file)
    return None

def validate_excel_columns(df, required_columns: list) -> bool:
    """
    驗證 Excel DataFrame 是否包含必要的欄位
    支援多個可能的欄位名稱（以列表形式提供）
    
    Args:
        df: pandas DataFrame
        required_columns: 必要的欄位列表，每個元素可以是字串或字串列表
        
    Returns:
        是否包含所有必要欄位
    """
    logger = setup_logger(__name__)
    
    for required in required_columns:
        # 如果是列表，檢查是否至少有一個存在
        if isinstance(required, list):
            found = False
            for col in required:
                if col in df.columns:
                    found = True
                    break
            if not found:
                logger.error(f"Excel 缺少必要欄位，需要以下其中一個: {required}")
                return False
        # 如果是字串，直接檢查
        else:
            if required not in df.columns:
                logger.error(f"Excel 缺少必要欄位: {required}")
                return False
    return True

def clean_filename(filename: str) -> str:
    """清理檔案名稱，移除不合法的字元"""
    # 移除或替換不合法的檔案名稱字元
    illegal_chars = '<>:"|?*'
    for char in illegal_chars:
        filename = filename.replace(char, '_')
    return filename

def get_relative_path(full_path: str, base_path: str) -> str:
    """取得相對路徑"""
    return os.path.relpath(full_path, base_path)

def format_file_size(size_bytes: int) -> str:
    """格式化檔案大小"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"