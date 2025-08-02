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
        self.last_report_path = None
        self.downloaded_files_list = []  # 記錄下載的檔案詳情
        self.skipped_files_list = []     # 記錄跳過的檔案詳情
        self.failed_files_list = []      # 記錄失敗的檔案詳情
        
    def set_progress_callback(self, callback):
        """設定進度回調函數"""
        self.progress_callback = callback
        
    def download_files(self, ftp_path: str, local_dir: str) -> Tuple[List[str], Dict[str, str]]:
        """覆寫下載方法以支援進度更新"""
        # 呼叫父類方法
        downloaded_files, file_paths = super().download_files(ftp_path, local_dir)
        
        # 更新統計和檔案列表（累積，不重置）
        for file in config.TARGET_FILES:
            if file in downloaded_files:
                if file in file_paths and file_paths[file] == "已存在":
                    self.stats['skipped'] += 1
                    self.skipped_files_list.append({
                        'name': file,
                        'path': os.path.join(local_dir, file),
                        'reason': '檔案已存在',
                        'ftp_path': ftp_path
                    })
                else:
                    self.stats['downloaded'] += 1
                    self.downloaded_files_list.append({
                        'name': file,
                        'path': os.path.join(local_dir, file),
                        'ftp_path': ftp_path
                    })
            else:
                self.stats['failed'] += 1
                self.failed_files_list.append({
                    'name': file,
                    'path': os.path.join(local_dir, file),
                    'reason': '找不到檔案',
                    'ftp_path': ftp_path
                })
        
        # 計算當前進度（基於累積統計）
        processed = self.stats['downloaded'] + self.stats['skipped'] + self.stats['failed']
        
        # 觸發進度回調，包含詳細的檔案列表
        if self.progress_callback:
            progress = (processed / max(self.stats['total'], 1)) * 100
            self.progress_callback(
                progress, 
                'downloading', 
                f'已處理 {processed}/{self.stats["total"]} 個檔案',
                stats=self.stats.copy(),  # 傳送統計的副本
                files={
                    'downloaded': self.downloaded_files_list.copy(),
                    'skipped': self.skipped_files_list.copy(),
                    'failed': self.failed_files_list.copy()
                }
            )
        
        return downloaded_files, file_paths
        
        # 觸發進度回調，包含詳細的檔案列表
        if self.progress_callback:
            progress = (self.stats['downloaded'] + self.stats['skipped'] + self.stats['failed']) / max(self.stats['total'], 1) * 100
            self.progress_callback(
                progress, 
                'downloading', 
                f'已處理 {len(downloaded_files)} 個檔案',
                stats=self.stats,
                files={
                    'downloaded': self.downloaded_files_list,
                    'skipped': self.skipped_files_list,
                    'failed': self.failed_files_list
                }
            )
        
        return downloaded_files, file_paths
        
    def download_from_excel_with_progress(self, excel_path: str, output_dir: str = None):
        """從 Excel 下載並提供進度更新"""
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
        
        try:
            # 初始進度
            if self.progress_callback:
                self.progress_callback(0, 'downloading', '開始讀取 Excel 檔案...', stats=self.stats)
            
            # 讀取 Excel 來計算總數
            import pandas as pd
            df = pd.read_excel(excel_path)
            
            # 計算總檔案數（每個FTP路徑 × 目標檔案數）
            self.stats['total'] = len(df) * len(config.TARGET_FILES)
            
            # 更新初始統計
            if self.progress_callback:
                self.progress_callback(5, 'downloading', f'預計處理 {self.stats["total"]} 個檔案...', stats=self.stats)
            
            # 呼叫父類方法
            report_path = self.download_from_excel(excel_path, output_dir)
            self.last_report_path = report_path
            
            # 最終進度更新，包含完整的檔案列表
            if self.progress_callback:
                self.progress_callback(
                    100, 
                    'completed', 
                    '下載完成',
                    stats=self.stats,
                    files={
                        'downloaded': self.downloaded_files_list,
                        'skipped': self.skipped_files_list,
                        'failed': self.failed_files_list
                    }
                )
                
            return report_path
            
        except Exception as e:
            self.stats['failed'] = self.stats['total'] - self.stats['downloaded'] - self.stats['skipped']
            if self.progress_callback:
                self.progress_callback(0, 'error', f'下載失敗: {str(e)}', stats=self.stats)
            raise

    def get_download_stats(self):
        """取得下載統計資料（包含檔案列表）"""
        return {
            'stats': self.stats,
            'files': {
                'downloaded': self.downloaded_files_list,
                'skipped': self.skipped_files_list,
                'failed': self.failed_files_list
            }
        }