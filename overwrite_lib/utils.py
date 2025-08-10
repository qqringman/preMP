"""
通用工具模組
提供日誌設定和其他通用功能
"""
import logging
import os
import sys
from typing import Any

# 加入父目錄到 sys.path，以便 import config 和 excel_handler
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

def format_xml_content(xml_content: str) -> str:
    """格式化 XML 內容為多行縮排格式"""
    try:
        import xml.etree.ElementTree as ET
        from xml.dom import minidom
        
        # 解析 XML
        root = ET.fromstring(xml_content)
        
        # 轉換為格式化的字串
        rough_string = ET.tostring(root, encoding='unicode')
        reparsed = minidom.parseString(rough_string)
        
        # 格式化輸出（包含縮排和換行）
        formatted = reparsed.toprettyxml(indent="  ")
        
        # 移除多餘的空行
        lines = [line for line in formatted.split('\n') if line.strip()]
        
        return '\n'.join(lines)
        
    except Exception as e:
        # 如果格式化失敗，返回原始內容
        logger = setup_logger(__name__)
        logger.warning(f"XML 格式化失敗，使用原始內容: {str(e)}")
        return xml_content

def is_xml_file(file_path: str) -> bool:
    """判斷是否為 XML 檔案"""
    return file_path.lower().endswith(('.xml', '.XML'))

def setup_logger(name: str) -> logging.Logger:
    """設定日誌記錄器"""
    logger = logging.getLogger(name)
    
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        
        # 建立處理器
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.INFO)
        
        # 設定格式
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        
        logger.addHandler(handler)
    
    return logger

def ensure_dir(directory: str) -> None:
    """確保目錄存在"""
    if not os.path.exists(directory):
        os.makedirs(directory)

def safe_filename(filename: str) -> str:
    """確保檔案名稱安全"""
    # 移除或替換不安全的字符
    unsafe_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
    safe_name = filename
    for char in unsafe_chars:
        safe_name = safe_name.replace(char, '_')
    return safe_name

def setup_config():
    """設定系統組態和環境變數"""
    try:
        import config
        # 呼叫 config 中的環境變數設定函數
        config.setup_environment_variables()
        return True
    except ImportError as e:
        print(f"警告：無法載入 config 模組: {e}")
        return False
    except Exception as e:
        print(f"警告：設定環境變數時發生錯誤: {e}")
        return False