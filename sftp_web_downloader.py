"""
SFTP Web 下載器 - 包裝原始 SFTPDownloader 以支援 Web 應用
"""
import os
import logging
from typing import List, Dict, Any, Tuple
from sftp_downloader import SFTPDownloader
import config

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
        self.last_report_path = None  # 記錄最後的報告路徑
        
    def set_progress_callback(self, callback):
        """設定進度回調函數"""
        self.progress_callback = callback
        
    def download_files(self, ftp_path: str, local_dir: str) -> Tuple[List[str], Dict[str, str]]:
        """覆寫下載方法以支援進度更新"""
        # 更新統計
        self.stats['total'] += len(config.TARGET_FILES)
        
        # 呼叫父類方法
        downloaded_files, file_paths = super().download_files(ftp_path, local_dir)
        
        # 更新統計
        self.stats['downloaded'] += len(downloaded_files)
        self.stats['skipped'] += len([f for f in config.TARGET_FILES if f not in downloaded_files])
        
        # 觸發進度回調
        if self.progress_callback:
            progress = (self.stats['downloaded'] + self.stats['skipped']) / max(self.stats['total'], 1) * 100
            self.progress_callback(progress, 'downloading', f'已處理 {len(downloaded_files)} 個檔案')
        
        return downloaded_files, file_paths
        
    def download_from_excel_with_progress(self, excel_path: str, output_dir: str = None):
        """從 Excel 下載並提供進度更新"""
        # 重置統計
        self.stats = {
            'total': 0,
            'downloaded': 0,
            'skipped': 0,
            'failed': 0
        }
        
        try:
            # 初始進度
            if self.progress_callback:
                self.progress_callback(0, 'downloading', '開始讀取 Excel 檔案...')
            
            # 呼叫父類方法
            report_path = self.download_from_excel(excel_path, output_dir)
            self.last_report_path = report_path
            
            # 最終進度更新
            if self.progress_callback:
                self.progress_callback(100, 'completed', '下載完成')
                
            return report_path
            
        except Exception as e:
            self.stats['failed'] = self.stats['total'] - self.stats['downloaded'] - self.stats['skipped']
            if self.progress_callback:
                self.progress_callback(0, 'error', f'下載失敗: {str(e)}')
            raise

    def get_download_stats(self):
        """取得下載統計資料"""
        # 如果沒有統計資料，嘗試從報告中讀取
        if self.stats['total'] == 0 and self.last_report_path:
            try:
                import pandas as pd
                df = pd.read_excel(self.last_report_path)
                self.stats['total'] = len(df)
                
                # 嘗試從報告中提取更詳細的統計
                if '版本資訊檔案' in df.columns:
                    # 計算成功下載的數量
                    self.stats['downloaded'] = len(df[df['版本資訊檔案'] != '無'])
                    self.stats['skipped'] = len(df[df['版本資訊檔案'] == '無'])
                else:
                    # 預設都算成功
                    self.stats['downloaded'] = self.stats['total']
                    
            except Exception as e:
                logger.warning(f"無法從報告讀取統計: {e}")
                
        return self.stats