#!/usr/bin/env python3
"""
Manifest Pinning Tool - 自動化定版工具
用於從 SFTP 下載 manifest 檔案並執行 repo 定版操作

Author: Your Name
Date: 2025-01-17
Version: 1.0.0
"""

import os
import sys
import argparse
import pandas as pd
import paramiko
import subprocess
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import time
import logging
from dataclasses import dataclass, field, asdict

# =====================================
# ===== 使用者設定區塊 =====
# =====================================

# SFTP 連線設定
SFTP_CONFIG = {
    'host': 'mmsftpx.realtek.com',
    'port': 22,
    'username': 'lgwar_user',
    'password': 'Ab!123456',
    'timeout': 30,
    'retry_count': 3,
    'retry_delay': 5  # 秒
}

# JIRA 設定（用於取得 source code 資訊）
JIRA_CONFIG = {
    'site': 'jira.realtek.com',
    'username': 'vince_lin',
    'password': 'Amon200!Amon200!',  # 請填入密碼
    'api_url': 'https://jira.realtek.com/rest/api/2'
}

# 路徑設定
PATH_CONFIG = {
    'default_output_dir': './pinning_output',
    'default_mapping_table': './all_chip_mapping_table.xlsx',
    'manifest_pattern': r'manifest_(\d+)\.xml',  # manifest 檔案命名模式
    'report_filename': 'pinning_report.xlsx'
}

# Repo 指令設定
REPO_CONFIG = {
    'repo_command': 'repo',  # repo 指令路徑
    'sync_jobs': 8,  # repo sync 的並行數
    'sync_retry': 2,  # repo sync 失敗重試次數
    'init_timeout': 60,  # repo init 超時時間（秒）
    'sync_timeout': 3600  # repo sync 超時時間（秒）
}

# 平行處理設定
PARALLEL_CONFIG = {
    'max_workers': 4,  # 最大並行處理 DB 數量
    'enable_parallel': True,  # 是否啟用平行處理
}

# 日誌設定
LOG_CONFIG = {
    'level': logging.INFO,
    'format': '%(asctime)s - [%(levelname)s] - %(name)s - %(message)s',
    'date_format': '%Y-%m-%d %H:%M:%S'
}

# =====================================
# ===== 資料結構定義 =====
# =====================================

class MappingTableReader:
    """讀取和解析 mapping table 的類別"""
    
    def __init__(self):
        self.logger = setup_logger(self.__class__.__name__)
        self.df = None
        
    def load_excel(self, file_path: str) -> bool:
        """載入 Excel 檔案"""
        try:
            self.df = pd.read_excel(file_path)
            self.logger.info(f"成功載入 {len(self.df)} 筆資料")
            
            # 檢查必要欄位
            required_columns = ['SN', 'Module', 'DB_Type', 'DB_Info', 'SftpPath']
            missing_columns = [col for col in required_columns if col not in self.df.columns]
            
            if missing_columns:
                self.logger.error(f"缺少必要欄位: {missing_columns}")
                return False
                
            return True
            
        except Exception as e:
            self.logger.error(f"載入 Excel 失敗: {str(e)}")
            return False
    
    def get_db_info_list(self, db_type: str = 'all') -> List[DBInfo]:
        """
        取得 DB 資訊列表
        
        Args:
            db_type: 'all', 'master', 'premp', 'mp', 'mpbackup'
        """
        db_list = []
        
        if self.df is None:
            return db_list
        
        # 處理不同的 DB 類型
        type_columns = {
            'master': ('DB_Type', 'DB_Info', 'DB_Folder', 'SftpPath'),
            'premp': ('premp_DB_Type', 'premp_DB_Info', 'premp_DB_Folder', 'premp_SftpPath'),
            'mp': ('mp_DB_Type', 'mp_DB_Info', 'mp_DB_Folder', 'mp_SftpPath'),
            'mpbackup': ('mpbackup_DB_Type', 'mpbackup_DB_Info', 'mpbackup_DB_Folder', 'mpbackup_SftpPath')
        }
        
        # 選擇要處理的類型
        if db_type == 'all':
            types_to_process = type_columns.keys()
        else:
            types_to_process = [db_type] if db_type in type_columns else []
        
        for idx, row in self.df.iterrows():
            for dtype in types_to_process:
                cols = type_columns[dtype]
                
                # 檢查該類型的欄位是否存在且有值
                if all(col in row and pd.notna(row[col]) for col in cols[1:2]):  # 至少檢查 DB_Info
                    db_info = DBInfo(
                        sn=row['SN'],
                        module=row['Module'],
                        db_type=dtype,
                        db_info=str(row[cols[1]]),  # DB_Info
                        db_folder=str(row[cols[2]]) if cols[2] in row and pd.notna(row[cols[2]]) else '',
                        sftp_path=str(row[cols[3]]) if cols[3] in row and pd.notna(row[cols[3]]) else ''
                    )
                    db_list.append(db_info)
        
        return db_list
    
    def get_db_by_name(self, db_name: str) -> Optional[DBInfo]:
        """根據 DB 名稱取得資訊"""
        all_dbs = self.get_db_info_list('all')
        
        for db in all_dbs:
            if db.db_info == db_name:
                return db
        
        return None
    
@dataclass
class DBInfo:
    """DB 資訊資料結構（修改版）"""
    sn: int
    module: str
    db_type: str  # master, premp, mp, mpbackup
    db_info: str  # DB編號，如 DB2302
    db_folder: str  # 資料夾名稱
    sftp_path: str  # 從 Excel 讀取的完整 SFTP 路徑
    version: Optional[str] = None  # 使用者指定的版本號
    jira_link: Optional[str] = None
    source_command: Optional[str] = None
    manifest_file: Optional[str] = None
    local_path: Optional[str] = None
    status: str = "pending"
    error_message: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    def to_dict(self) -> Dict:
        """轉換為字典格式"""
        data = asdict(self)
        # 轉換 datetime 物件為字串
        if data['start_time']:
            data['start_time'] = data['start_time'].strftime('%Y-%m-%d %H:%M:%S')
        if data['end_time']:
            data['end_time'] = data['end_time'].strftime('%Y-%m-%d %H:%M:%S')
        return data

@dataclass
class PinningReport:
    """定版報告資料結構"""
    total_dbs: int = 0
    successful_dbs: int = 0
    failed_dbs: int = 0
    skipped_dbs: int = 0
    db_details: List[DBInfo] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    
    def add_db(self, db_info: DBInfo):
        """新增 DB 處理結果"""
        self.db_details.append(db_info)
        if db_info.status == 'success':
            self.successful_dbs += 1
        elif db_info.status == 'failed':
            self.failed_dbs += 1
        elif db_info.status == 'skipped':
            self.skipped_dbs += 1
    
    def finalize(self):
        """完成報告"""
        self.end_time = datetime.now()
        self.total_dbs = len(self.db_details)

# =====================================
# ===== 日誌設定 =====
# =====================================

def setup_logger(name: str = __name__) -> logging.Logger:
    """設定日誌記錄器"""
    logger = logging.getLogger(name)
    logger.setLevel(LOG_CONFIG['level'])
    
    if not logger.handlers:
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(LOG_CONFIG['level'])
        
        # Formatter
        formatter = logging.Formatter(
            LOG_CONFIG['format'],
            datefmt=LOG_CONFIG['date_format']
        )
        console_handler.setFormatter(formatter)
        
        logger.addHandler(console_handler)
    
    return logger

logger = setup_logger(__name__)

# =====================================
# ===== SFTP 管理類別 =====
# =====================================

class SFTPManager:
    """SFTP 連線管理器"""
    
    def __init__(self, config: Dict = None):
        self.config = config or SFTP_CONFIG
        self.client = None
        self.sftp = None
        self.logger = setup_logger(self.__class__.__name__)
    
    def connect(self) -> bool:
        """建立 SFTP 連線"""
        for attempt in range(self.config['retry_count']):
            try:
                self.logger.info(f"嘗試連線到 SFTP 伺服器 {self.config['host']}...")
                
                self.client = paramiko.SSHClient()
                self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                self.client.connect(
                    hostname=self.config['host'],
                    port=self.config['port'],
                    username=self.config['username'],
                    password=self.config['password'],
                    timeout=self.config['timeout']
                )
                self.sftp = self.client.open_sftp()
                
                self.logger.info("SFTP 連線成功")
                return True
                
            except Exception as e:
                self.logger.warning(f"連線失敗 (嘗試 {attempt + 1}/{self.config['retry_count']}): {str(e)}")
                if attempt < self.config['retry_count'] - 1:
                    time.sleep(self.config['retry_delay'])
                else:
                    self.logger.error("SFTP 連線失敗，已達最大重試次數")
                    return False
        
        return False
    
    def disconnect(self):
        """關閉 SFTP 連線"""
        if self.sftp:
            self.sftp.close()
        if self.client:
            self.client.close()
        self.logger.info("SFTP 連線已關閉")
    
    def list_manifest_files(self, remote_path: str) -> List[Tuple[str, datetime]]:
        """
        列出指定路徑下的 manifest 檔案
        返回: [(檔案名稱, 修改時間), ...]
        """
        try:
            files = []
            pattern = re.compile(PATH_CONFIG['manifest_pattern'])
            
            for file_attr in self.sftp.listdir_attr(remote_path):
                if pattern.match(file_attr.filename):
                    mod_time = datetime.fromtimestamp(file_attr.st_mtime)
                    files.append((file_attr.filename, mod_time))
            
            # 按日期排序（最新的在前）
            files.sort(key=lambda x: x[1], reverse=True)
            return files
            
        except Exception as e:
            self.logger.error(f"列出 manifest 檔案失敗: {str(e)}")
            return []
    
    def get_latest_manifest(self, remote_path: str) -> Optional[str]:
        """取得最新的 manifest 檔案名稱"""
        files = self.list_manifest_files(remote_path)
        if files:
            return files[0][0]
        return None
    
    def download_file(self, remote_file: str, local_file: str) -> bool:
        """下載檔案"""
        try:
            # 確保本地目錄存在
            os.makedirs(os.path.dirname(local_file), exist_ok=True)
            
            self.logger.info(f"下載檔案: {remote_file} -> {local_file}")
            self.sftp.get(remote_file, local_file)
            
            self.logger.info(f"檔案下載成功: {local_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"檔案下載失敗: {str(e)}")
            return False

    def list_manifest_files_from_path(self, sftp_path: str) -> List[Tuple[str, datetime]]:
        """
        從指定的 SFTP 路徑列出 manifest 檔案
        
        Args:
            sftp_path: 完整的 SFTP 路徑（從 Excel 的 SftpPath 欄位讀取）
        """
        try:
            if not sftp_path:
                self.logger.error("SFTP 路徑為空")
                return []
            
            files = []
            pattern = re.compile(PATH_CONFIG['manifest_pattern'])
            
            # 直接使用 Excel 中的完整路徑
            self.logger.info(f"掃描路徑: {sftp_path}")
            
            # 列出目錄內容
            for file_attr in self.sftp.listdir_attr(sftp_path):
                if pattern.match(file_attr.filename):
                    mod_time = datetime.fromtimestamp(file_attr.st_mtime)
                    files.append((file_attr.filename, mod_time))
                    self.logger.debug(f"找到 manifest: {file_attr.filename} ({mod_time})")
            
            # 按日期排序（最新的在前）
            files.sort(key=lambda x: x[1], reverse=True)
            
            self.logger.info(f"共找到 {len(files)} 個 manifest 檔案")
            return files
            
        except Exception as e:
            self.logger.error(f"列出 manifest 檔案失敗 ({sftp_path}): {str(e)}")
            return []

    def get_latest_manifest_from_path(self, sftp_path: str) -> Optional[str]:
        """從指定路徑取得最新的 manifest 檔案名稱"""
        files = self.list_manifest_files_from_path(sftp_path)
        if files:
            return files[0][0]
        return None
    
    def download_manifest(self, sftp_path: str, manifest_file: str, local_file: str) -> bool:
        """
        下載 manifest 檔案
        
        Args:
            sftp_path: SFTP 基礎路徑
            manifest_file: manifest 檔案名稱
            local_file: 本地儲存路徑
        """
        try:
            remote_file = f"{sftp_path}/{manifest_file}"
            return self.download_file(remote_file, local_file)
        except Exception as e:
            self.logger.error(f"下載 manifest 失敗: {str(e)}")
            return False
                
# =====================================
# ===== JIRA 管理類別 =====
# =====================================

class JiraManager:
    """JIRA 管理器（簡化版）"""
    
    def __init__(self):
        self.logger = setup_logger(self.__class__.__name__)
    
    def get_source_info(self, db_name: str, mapping_df: pd.DataFrame) -> Optional[str]:
        """
        從 mapping table 取得 source code 資訊
        這裡簡化處理，實際應該要從 JIRA API 取得
        """
        try:
            # 尋找對應的 DB
            for col in ['DB_Info', 'premp_DB_Info', 'mp_DB_Info', 'mpbackup_DB_Info']:
                if col in mapping_df.columns:
                    mask = mapping_df[col] == db_name
                    if mask.any():
                        row = mapping_df[mask].iloc[0]
                        
                        # 這裡應該要呼叫 JIRA API
                        # 目前先回傳範例指令
                        return f"repo init -u ssh://mm2sd.rtkbf.com:29418/realtek/android/manifest -b realtek/android-14/master -m atv-google-refplus-wave.xml"
            
            return None
            
        except Exception as e:
            self.logger.error(f"取得 source info 失敗: {str(e)}")
            return None

# =====================================
# ===== Repo 管理類別 =====
# =====================================

class RepoManager:
    """Repo 指令管理器"""
    
    def __init__(self):
        self.logger = setup_logger(self.__class__.__name__)
        self.lock = threading.Lock()
    
    def run_command(self, cmd: str, cwd: str = None, timeout: int = None) -> Tuple[bool, str]:
        """
        執行 shell 指令
        返回: (成功與否, 輸出訊息)
        """
        try:
            self.logger.debug(f"執行指令: {cmd}")
            self.logger.debug(f"工作目錄: {cwd}")
            
            result = subprocess.run(
                cmd,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            if result.returncode == 0:
                return True, result.stdout
            else:
                return False, result.stderr
                
        except subprocess.TimeoutExpired:
            self.logger.error(f"指令執行超時: {cmd}")
            return False, "Command timeout"
        except Exception as e:
            self.logger.error(f"指令執行失敗: {str(e)}")
            return False, str(e)
    
    def repo_init(self, work_dir: str, init_cmd: str) -> bool:
        """執行 repo init"""
        success, output = self.run_command(
            init_cmd,
            cwd=work_dir,
            timeout=REPO_CONFIG['init_timeout']
        )
        
        if success:
            self.logger.info(f"Repo init 成功: {work_dir}")
        else:
            self.logger.error(f"Repo init 失敗: {work_dir}\n{output}")
        
        return success
    
    def repo_sync(self, work_dir: str) -> bool:
        """執行 repo sync"""
        cmd = f"{REPO_CONFIG['repo_command']} sync -j{REPO_CONFIG['sync_jobs']}"
        
        for attempt in range(REPO_CONFIG['sync_retry']):
            self.logger.info(f"執行 repo sync (嘗試 {attempt + 1}/{REPO_CONFIG['sync_retry']}): {work_dir}")
            
            success, output = self.run_command(
                cmd,
                cwd=work_dir,
                timeout=REPO_CONFIG['sync_timeout']
            )
            
            if success:
                self.logger.info(f"Repo sync 成功: {work_dir}")
                return True
            else:
                self.logger.warning(f"Repo sync 失敗 (嘗試 {attempt + 1}): {work_dir}")
                if attempt < REPO_CONFIG['sync_retry'] - 1:
                    time.sleep(10)
        
        self.logger.error(f"Repo sync 失敗，已達最大重試次數: {work_dir}")
        return False
    
    def pin_manifest(self, work_dir: str, manifest_file: str) -> bool:
        """執行定版"""
        try:
            # 複製 manifest 檔案到 .repo/manifests
            manifest_dir = os.path.join(work_dir, '.repo', 'manifests')
            if not os.path.exists(manifest_dir):
                self.logger.error(f"Manifest 目錄不存在: {manifest_dir}")
                return False
            
            import shutil
            dest_file = os.path.join(manifest_dir, os.path.basename(manifest_file))
            shutil.copy2(manifest_file, dest_file)
            self.logger.info(f"複製 manifest 檔案: {manifest_file} -> {dest_file}")
            
            # 執行 repo init -m manifest_xxx.xml
            cmd = f"{REPO_CONFIG['repo_command']} init -m {os.path.basename(manifest_file)}"
            success, output = self.run_command(cmd, cwd=work_dir, timeout=REPO_CONFIG['init_timeout'])
            
            if not success:
                self.logger.error(f"定版 init 失敗: {work_dir}")
                return False
            
            # 執行 repo sync
            return self.repo_sync(work_dir)
            
        except Exception as e:
            self.logger.error(f"定版失敗: {str(e)}")
            return False
    
    def export_manifest(self, work_dir: str, output_file: str = "vp_manifest.xml") -> bool:
        """導出定版結果"""
        cmd = f"{REPO_CONFIG['repo_command']} manifest -r -o {output_file}"
        success, output = self.run_command(cmd, cwd=work_dir, timeout=60)
        
        if success:
            self.logger.info(f"成功導出 manifest: {os.path.join(work_dir, output_file)}")
        else:
            self.logger.error(f"導出 manifest 失敗: {work_dir}")
        
        return success

# =====================================
# ===== 主要處理類別 =====
# =====================================

class ManifestPinningTool:
    """Manifest 定版工具主類別"""
    
    def __init__(self):
        self.logger = setup_logger(self.__class__.__name__)
        self.sftp_manager = SFTPManager()
        self.repo_manager = RepoManager()
        self.mapping_reader = MappingTableReader()  # 新增
        self.report = PinningReport()
        self.output_dir = PATH_CONFIG['default_output_dir']
    
    def load_mapping_table(self, file_path: str) -> bool:
        """載入 mapping table"""
        return self.mapping_reader.load_excel(file_path)
    
    def get_all_dbs(self, db_type: str = 'all') -> List[DBInfo]:
        """取得所有 DB 資訊"""
        return self.mapping_reader.get_db_info_list(db_type)
    
    def parse_db_version(self, db_spec: str) -> Tuple[str, Optional[str]]:
        """
        解析 DB 版本規格
        輸入: "DB2302#3" 或 "DB2302"
        返回: (db_name, version)
        """
        if '#' in db_spec:
            parts = db_spec.split('#')
            return parts[0], parts[1]
        return db_spec, None
    
    def process_db(self, db_info: DBInfo) -> DBInfo:
        """處理單一 DB 的定版"""
        db_info.start_time = datetime.now()
        
        try:
            self.logger.info(f"開始處理 {db_info.module}/{db_info.db_info} (類型: {db_info.db_type})")
            
            # 建立本地目錄
            local_path = os.path.join(self.output_dir, db_info.module, db_info.db_info)
            os.makedirs(local_path, exist_ok=True)
            db_info.local_path = local_path
            
            # 使用 Excel 中的 SFTP 路徑
            if not db_info.sftp_path:
                raise Exception("Excel 中未定義 SFTP 路徑")
            
            self.logger.info(f"使用 SFTP 路徑: {db_info.sftp_path}")
            
            # 確定要下載的 manifest 檔案
            if db_info.version:
                manifest_file = f"manifest_{db_info.version}.xml"
                self.logger.info(f"使用指定版本: {manifest_file}")
            else:
                # 取得最新版本
                manifest_file = self.sftp_manager.get_latest_manifest_from_path(db_info.sftp_path)
                if not manifest_file:
                    raise Exception(f"在 {db_info.sftp_path} 找不到 manifest 檔案")
                
                # 從檔名提取版本號
                match = re.match(PATH_CONFIG['manifest_pattern'], manifest_file)
                if match:
                    db_info.version = match.group(1)
                
                self.logger.info(f"使用最新版本: {manifest_file}")
            
            db_info.manifest_file = manifest_file
            
            # Step 3: 下載 manifest 檔案
            local_manifest = os.path.join(local_path, manifest_file)
            if not self.sftp_manager.download_manifest(db_info.sftp_path, manifest_file, local_manifest):
                raise Exception("下載 manifest 檔案失敗")
            
            # Step 4: 從 DB_Folder 或其他來源取得 repo init 指令
            # 這裡需要根據您的實際需求來決定如何取得 source command
            # 可能需要從 JIRA 或其他地方取得
            source_cmd = self.get_source_command(db_info)
            if not source_cmd:
                raise Exception("無法取得 source command")
            db_info.source_command = source_cmd
            
            # Step 5: 執行 repo init 和 sync
            if not self.repo_manager.repo_init(local_path, source_cmd):
                raise Exception("Repo init 失敗")
            
            if not self.repo_manager.repo_sync(local_path):
                raise Exception("Repo sync 失敗")
            
            # Step 6: 執行定版
            if not self.repo_manager.pin_manifest(local_path, local_manifest):
                raise Exception("定版失敗")
            
            # Step 7: 導出定版結果
            if not self.repo_manager.export_manifest(local_path):
                raise Exception("導出 manifest 失敗")
            
            db_info.status = "success"
            self.logger.info(f"✅ 成功完成 {db_info.module}/{db_info.db_info} 的定版")
            
        except Exception as e:
            db_info.status = "failed"
            db_info.error_message = str(e)
            self.logger.error(f"❌ 處理 {db_info.module}/{db_info.db_info} 失敗: {str(e)}")
        
        finally:
            db_info.end_time = datetime.now()
        
        return db_info

    def get_source_command(self, db_info: DBInfo) -> Optional[str]:
        """
        取得 repo init 的 source command
        這個方法需要根據您的實際需求來實作
        """
        # 方法1: 從 DB_Folder 解析
        # 例如: DB2302_Merlin7_32Bit_FW_Android14_Ref_Plus_GoogleGMS
        # 可能對應到: repo init -u ssh://mm2sd.rtkbf.com:29418/realtek/android/manifest -b realtek/android-14/master -m xxx.xml
        
        # 方法2: 從 JIRA 取得（需要實作 JIRA API 呼叫）
        
        # 這裡先回傳一個範例
        return "repo init -u ssh://mm2sd.rtkbf.com:29418/realtek/android/manifest -b realtek/android-14/master -m atv-google-refplus-wave.xml"
    
    def process_selected_dbs(self, db_list: List[str], db_versions: Dict[str, str] = None) -> None:
        """處理選定的 DB 列表"""
        db_versions = db_versions or {}
        db_infos_to_process = []
        
        # 取得所有 DB 資訊
        all_db_infos = self.get_all_dbs('all')
        
        # 篩選要處理的 DB
        for db_name in db_list:
            # 解析 DB 名稱和版本
            if '#' in db_name:
                db_name, version = db_name.split('#')
            else:
                version = db_versions.get(db_name)
            
            # 尋找對應的 DB 資訊
            for db_info in all_db_infos:
                if db_info.db_info == db_name:
                    db_info.version = version
                    db_infos_to_process.append(db_info)
                    break
        
        self.logger.info(f"準備處理 {len(db_infos_to_process)} 個 DB")
        
        # 平行處理
        if PARALLEL_CONFIG['enable_parallel']:
            self._process_parallel(db_infos_to_process)
        else:
            self._process_sequential(db_infos_to_process)

    def _process_parallel(self, db_infos: List[DBInfo]):
        """平行處理 DB 列表"""
        self.logger.info(f"使用平行處理，最大 worker 數: {PARALLEL_CONFIG['max_workers']}")
        
        with ThreadPoolExecutor(max_workers=PARALLEL_CONFIG['max_workers']) as executor:
            futures = {executor.submit(self.process_db, db_info): db_info for db_info in db_infos}
            
            for future in as_completed(futures):
                db_info = futures[future]
                try:
                    result = future.result()
                    self.report.add_db(result)
                except Exception as e:
                    self.logger.error(f"處理 {db_info.db_info} 時發生異常: {str(e)}")
                    db_info.status = "failed"
                    db_info.error_message = str(e)
                    self.report.add_db(db_info)
    
    def _process_sequential(self, db_infos: List[DBInfo]):
        """循序處理 DB 列表"""
        self.logger.info("使用循序處理")
        for db_info in db_infos:
            result = self.process_db(db_info)
            self.report.add_db(result)

    def process_dbs_parallel(self, db_list: List[str], db_versions: Dict[str, str] = None) -> None:
        """平行處理多個 DB"""
        db_versions = db_versions or {}
        db_infos = []
        
        # 準備 DB 資訊
        for db_spec in db_list:
            db_name, version = self.parse_db_version(db_spec)
            
            # 如果沒有指定版本，使用 db_versions 中的設定
            if not version and db_name in db_versions:
                version = db_versions[db_name]
            
            # 找出 module 名稱
            module = self.get_module_for_db(db_name)
            if not module:
                self.logger.warning(f"找不到 {db_name} 的 module，跳過")
                continue
            
            db_info = DBInfo(
                module=module,
                db_name=db_name,
                version=version
            )
            db_infos.append(db_info)
        
        # 平行處理
        if PARALLEL_CONFIG['enable_parallel']:
            self.logger.info(f"使用平行處理，最大 worker 數: {PARALLEL_CONFIG['max_workers']}")
            
            with ThreadPoolExecutor(max_workers=PARALLEL_CONFIG['max_workers']) as executor:
                futures = {executor.submit(self.process_db, db_info): db_info for db_info in db_infos}
                
                for future in as_completed(futures):
                    db_info = futures[future]
                    try:
                        result = future.result()
                        self.report.add_db(result)
                    except Exception as e:
                        self.logger.error(f"處理 {db_info.db_name} 時發生異常: {str(e)}")
                        db_info.status = "failed"
                        db_info.error_message = str(e)
                        self.report.add_db(db_info)
        else:
            # 循序處理
            self.logger.info("使用循序處理")
            for db_info in db_infos:
                result = self.process_db(db_info)
                self.report.add_db(result)
    
    def get_module_for_db(self, db_name: str) -> Optional[str]:
        """找出 DB 對應的 module"""
        if self.mapping_df is None:
            return None
        
        for col in ['DB_Info', 'premp_DB_Info', 'mp_DB_Info', 'mpbackup_DB_Info']:
            if col in self.mapping_df.columns:
                mask = self.mapping_df[col] == db_name
                if mask.any():
                    return self.mapping_df[mask].iloc[0]['Module']
        
        return None
    
    def generate_report(self, output_file: str = None) -> None:
        """產生報告"""
        self.report.finalize()
        
        if not output_file:
            output_file = os.path.join(self.output_dir, PATH_CONFIG['report_filename'])
        
        try:
            # 建立報告 DataFrame
            report_data = []
            for db in self.report.db_details:
                report_data.append(db.to_dict())
            
            df = pd.DataFrame(report_data)
            
            # 建立摘要資訊
            summary = {
                '項目': ['總 DB 數', '成功', '失敗', '跳過', '開始時間', '結束時間', '總耗時'],
                '數值': [
                    self.report.total_dbs,
                    self.report.successful_dbs,
                    self.report.failed_dbs,
                    self.report.skipped_dbs,
                    self.report.start_time.strftime('%Y-%m-%d %H:%M:%S'),
                    self.report.end_time.strftime('%Y-%m-%d %H:%M:%S') if self.report.end_time else 'N/A',
                    str(self.report.end_time - self.report.start_time) if self.report.end_time else 'N/A'
                ]
            }
            summary_df = pd.DataFrame(summary)
            
            # 寫入 Excel
            with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
                summary_df.to_excel(writer, sheet_name='摘要', index=False)
                df.to_excel(writer, sheet_name='詳細資訊', index=False)
            
            self.logger.info(f"報告已產生: {output_file}")
            
            # 顯示摘要
            print("\n" + "="*60)
            print("定版處理結果摘要")
            print("="*60)
            for item, value in zip(summary['項目'], summary['數值']):
                print(f"{item}: {value}")
            print("="*60)
            
        except Exception as e:
            self.logger.error(f"產生報告失敗: {str(e)}")
    
    def run(self, args: argparse.Namespace) -> None:
        """執行主流程"""
        try:
            # 設定輸出目錄
            self.output_dir = args.output or PATH_CONFIG['default_output_dir']
            os.makedirs(self.output_dir, exist_ok=True)
            
            # 載入 mapping table
            mapping_file = args.mapping or PATH_CONFIG['default_mapping_table']
            if not self.load_mapping_table(mapping_file):
                raise Exception("無法載入 mapping table")
            
            # 連線到 SFTP
            if not self.sftp_manager.connect():
                raise Exception("無法連線到 SFTP")
            
            # 決定要處理的 DB 列表
            if args.dbs:
                # 使用指定的 DB
                db_list = args.dbs.split(',')
            else:
                # 使用所有 DB
                db_list = self.get_all_dbs()
            
            self.logger.info(f"準備處理 {len(db_list)} 個 DB")
            
            # 處理 DB 版本設定
            db_versions = {}
            if args.versions:
                for item in args.versions.split(','):
                    if '#' in item:
                        db, ver = item.split('#')
                        db_versions[db] = ver
            
            # 開始處理
            self.process_dbs_parallel(db_list, db_versions)
            
            # 產生報告
            self.generate_report()
            
        except Exception as e:
            self.logger.error(f"執行失敗: {str(e)}")
            
        finally:
            # 關閉 SFTP 連線
            self.sftp_manager.disconnect()

# =====================================
# ===== 互動式介面 =====
# =====================================

class InteractiveUI:
    """互動式使用者介面"""
    
    def __init__(self):
        self.tool = ManifestPinningTool()
        self.logger = setup_logger(self.__class__.__name__)
        self.selected_dbs = []
        self.db_versions = {}
    
    def display_menu(self) -> str:
        """顯示主選單"""
        print("\n" + "="*60)
        print("Manifest 定版工具 - 主選單")
        print("="*60)
        print("1. 載入 mapping table")
        print("2. 設定 SFTP 連線資訊")
        print("3. 選擇 DB 類型 (master/premp/mp/mpbackup/all)")
        print("4. 選擇要定版的 DB")
        print("5. 設定 DB 版本")
        print("6. 開始執行定版")
        print("7. 顯示目前設定")
        print("0. 結束程式")
        print("="*60)
        
        return input("請選擇功能: ").strip()

    def select_db_type(self) -> str:
        """選擇 DB 類型"""
        print("\n選擇 DB 類型:")
        print("1. All (所有類型)")
        print("2. Master")
        print("3. PreMP")
        print("4. MP")
        print("5. MP Backup")
        
        choice = input("請選擇: ").strip()
        
        type_map = {
            '1': 'all',
            '2': 'master',
            '3': 'premp',
            '4': 'mp',
            '5': 'mpbackup'
        }
        
        return type_map.get(choice, 'all')
        
    def load_mapping_table(self):
        """載入 mapping table"""
        file_path = input(f"請輸入 mapping table 路徑 [{PATH_CONFIG['default_mapping_table']}]: ").strip()
        if not file_path:
            file_path = PATH_CONFIG['default_mapping_table']
        
        if self.tool.load_mapping_table(file_path):
            print(f"✅ 成功載入 mapping table，共 {len(self.tool.mapping_df)} 筆資料")
            all_dbs = self.tool.get_all_dbs()
            print(f"   找到 {len(all_dbs)} 個 DB")
        else:
            print("❌ 載入失敗")
    
    def setup_sftp(self):
        """設定 SFTP 連線資訊"""
        print("\n目前 SFTP 設定:")
        print(f"  Host: {SFTP_CONFIG['host']}")
        print(f"  Port: {SFTP_CONFIG['port']}")
        print(f"  Username: {SFTP_CONFIG['username']}")
        
        if input("\n是否要修改設定? (y/N): ").strip().lower() == 'y':
            SFTP_CONFIG['host'] = input(f"Host [{SFTP_CONFIG['host']}]: ").strip() or SFTP_CONFIG['host']
            SFTP_CONFIG['port'] = int(input(f"Port [{SFTP_CONFIG['port']}]: ").strip() or SFTP_CONFIG['port'])
            SFTP_CONFIG['username'] = input(f"Username [{SFTP_CONFIG['username']}]: ").strip() or SFTP_CONFIG['username']
            password = input("Password (留空保持原值): ").strip()
            if password:
                SFTP_CONFIG['password'] = password
            
            print("✅ SFTP 設定已更新")
    
    def select_dbs(self, db_type: str = 'all') -> List[str]:
        """選擇要定版的 DB"""
        if not self.tool.mapping_reader.df:
            print("❌ 請先載入 mapping table")
            return []
        
        all_db_infos = self.tool.get_all_dbs(db_type)
        unique_dbs = list(set([db.db_info for db in all_db_infos]))
        
        print(f"\n找到 {len(unique_dbs)} 個不重複的 DB (類型: {db_type})")
        
        # 顯示 DB 列表
        for i, db in enumerate(unique_dbs, 1):
            print(f"{i:3d}. {db}")
        
        print("\n選擇方式:")
        print("1. 全選")
        print("2. 輸入 DB 編號列表 (逗號分隔)")
        print("3. 輸入 DB 名稱列表 (逗號分隔)")
        
        choice = input("請選擇: ").strip()
        
        if choice == '1':
            return unique_dbs
        elif choice == '2':
            indices = input("請輸入編號 (如: 1,3,5): ").strip()
            selected = []
            for idx_str in indices.split(','):
                try:
                    idx = int(idx_str.strip()) - 1
                    if 0 <= idx < len(unique_dbs):
                        selected.append(unique_dbs[idx])
                except:
                    pass
            return selected
        elif choice == '3':
            db_names = input("請輸入 DB 名稱 (如: DB2302,DB2575): ").strip()
            return [db.strip() for db in db_names.split(',')]
        else:
            return []
    
    def setup_db_versions(self, db_list: List[str]) -> Dict[str, str]:
        """設定 DB 版本"""
        versions = {}
        
        print("\n設定 DB 版本 (留空使用最新版本)")
        for db in db_list:
            version = input(f"{db} 的版本 [最新]: ").strip()
            if version:
                versions[db] = version
        
        return versions
    
    def run_interactive(self):
        """執行互動式介面"""
        db_list = []
        db_versions = {}
        
        while True:
            choice = self.display_menu()
            
            if choice == '0':
                print("結束程式")
                break
            elif choice == '1':
                self.load_mapping_table()
            elif choice == '2':
                self.setup_sftp()
            elif choice == '3':
                db_list = self.select_dbs()
                print(f"已選擇 {len(db_list)} 個 DB")
            elif choice == '4':
                if db_list:
                    db_versions = self.setup_db_versions(db_list)
                else:
                    print("請先選擇 DB")
            elif choice == '5':
                if not db_list:
                    print("❌ 請先選擇要定版的 DB")
                    continue
                
                output_dir = input(f"輸出目錄 [{PATH_CONFIG['default_output_dir']}]: ").strip()
                if not output_dir:
                    output_dir = PATH_CONFIG['default_output_dir']
                
                self.tool.output_dir = output_dir
                
                print("\n開始執行定版...")
                print(f"  DB 數量: {len(db_list)}")
                print(f"  輸出目錄: {output_dir}")
                
                if input("\n確認開始執行? (Y/n): ").strip().lower() != 'n':
                    # 連線 SFTP
                    if self.tool.sftp_manager.connect():
                        self.tool.process_dbs_parallel(db_list, db_versions)
                        self.tool.generate_report()
                        self.tool.sftp_manager.disconnect()
                    else:
                        print("❌ SFTP 連線失敗")
            elif choice == '6':
                print("\n目前設定:")
                print(f"  Mapping table: {'已載入' if self.tool.mapping_df is not None else '未載入'}")
                print(f"  選擇的 DB: {len(db_list)} 個")
                print(f"  設定版本的 DB: {len(db_versions)} 個")
                print(f"  輸出目錄: {self.tool.output_dir}")
            else:
                print("無效的選擇")

# =====================================
# ===== 主程式 =====
# =====================================

def main():
    """主程式入口（完整版）"""
    parser = argparse.ArgumentParser(
        description='Manifest 定版工具 - 自動化 repo 定版處理',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例:
  # 使用互動式介面
  python manifest_pinning_tool.py
  
  # 處理所有 DB
  python manifest_pinning_tool.py -m all_chip_mapping_table.xlsx -o ./output
  
  # 處理所有 master 類型的 DB
  python manifest_pinning_tool.py -m all_chip_mapping_table.xlsx -t master -o ./output
  
  # 處理指定的 DB
  python manifest_pinning_tool.py -m mapping.xlsx -d DB2302,DB2575 -o ./output
  
  # 指定 DB 版本（方式1：在 DB 名稱後加版本）
  python manifest_pinning_tool.py -m mapping.xlsx -d DB2302#3,DB2575#186
  
  # 指定 DB 版本（方式2：使用 -v 參數）
  python manifest_pinning_tool.py -m mapping.xlsx -d DB2302,DB2575 -v DB2302#3,DB2575#186
  
  # 混合指定（DB2302 用版本 3，DB2575 用最新版）
  python manifest_pinning_tool.py -m mapping.xlsx -d DB2302#3,DB2575
  
  # 處理特定類型的 DB
  python manifest_pinning_tool.py -m mapping.xlsx -t premp -o ./output
  
  # 使用自訂 SFTP 設定
  python manifest_pinning_tool.py -m mapping.xlsx --sftp-host 192.168.1.100 --sftp-user myuser
  
  # 設定平行處理數量
  python manifest_pinning_tool.py -m mapping.xlsx --parallel 8
  
  # 關閉平行處理（循序處理）
  python manifest_pinning_tool.py -m mapping.xlsx --no-parallel
  
  # 啟用 debug 模式
  python manifest_pinning_tool.py -m mapping.xlsx --debug
        """
    )
    
    # 基本參數
    parser.add_argument('-m', '--mapping', 
                        type=str,
                        help='Mapping table Excel 檔案路徑')
    
    parser.add_argument('-o', '--output', 
                        type=str,
                        help=f'輸出目錄 (預設: {PATH_CONFIG["default_output_dir"]})')
    
    parser.add_argument('-t', '--type',
                        choices=['all', 'master', 'premp', 'mp', 'mpbackup'],
                        default='all',
                        help='要處理的 DB 類型 (預設: all)')
    
    parser.add_argument('-d', '--dbs', 
                        type=str,
                        help='要處理的 DB 列表，逗號分隔 (可包含版本，如: DB2302#3,DB2575)')
    
    parser.add_argument('-v', '--versions', 
                        type=str,
                        help='DB 版本設定，格式: DB2302#3,DB2575#186')
    
    # SFTP 設定參數
    parser.add_argument('--sftp-host', 
                        type=str,
                        help=f'SFTP 伺服器位址 (預設: {SFTP_CONFIG["host"]})')
    
    parser.add_argument('--sftp-port', 
                        type=int,
                        help=f'SFTP 連接埠 (預設: {SFTP_CONFIG["port"]})')
    
    parser.add_argument('--sftp-user', 
                        type=str,
                        help=f'SFTP 使用者名稱 (預設: {SFTP_CONFIG["username"]})')
    
    parser.add_argument('--sftp-password', 
                        type=str,
                        help='SFTP 密碼')
    
    parser.add_argument('--sftp-timeout', 
                        type=int,
                        help=f'SFTP 連線逾時秒數 (預設: {SFTP_CONFIG["timeout"]})')
    
    # 平行處理設定
    parser.add_argument('--parallel', 
                        type=int,
                        metavar='N',
                        help=f'平行處理的 worker 數量 (預設: {PARALLEL_CONFIG["max_workers"]})')
    
    parser.add_argument('--no-parallel', 
                        action='store_true',
                        help='關閉平行處理，使用循序處理')
    
    # Repo 設定
    parser.add_argument('--repo-jobs', 
                        type=int,
                        help=f'repo sync 的並行數 (預設: {REPO_CONFIG["sync_jobs"]})')
    
    parser.add_argument('--repo-retry', 
                        type=int,
                        help=f'repo sync 失敗重試次數 (預設: {REPO_CONFIG["sync_retry"]})')
    
    # 其他選項
    parser.add_argument('--report-name', 
                        type=str,
                        help=f'報告檔案名稱 (預設: {PATH_CONFIG["report_filename"]})')
    
    parser.add_argument('--dry-run', 
                        action='store_true',
                        help='測試模式，只顯示將要執行的動作，不實際執行')
    
    parser.add_argument('--debug', 
                        action='store_true',
                        help='啟用 debug 模式，顯示詳細日誌')
    
    parser.add_argument('--version', 
                        action='version',
                        version='%(prog)s 1.0.0')
    
    # 解析參數
    args = parser.parse_args()
    
    # ===== 設定日誌等級 =====
    if args.debug:
        LOG_CONFIG['level'] = logging.DEBUG
        # 重新設定所有 logger 的等級
        logging.getLogger().setLevel(logging.DEBUG)
        for handler in logging.getLogger().handlers:
            handler.setLevel(logging.DEBUG)
        print("🔍 Debug 模式已啟用")
    
    # ===== 更新 SFTP 設定 =====
    if args.sftp_host:
        SFTP_CONFIG['host'] = args.sftp_host
        print(f"📡 SFTP 主機設定為: {args.sftp_host}")
    
    if args.sftp_port:
        SFTP_CONFIG['port'] = args.sftp_port
        print(f"📡 SFTP 連接埠設定為: {args.sftp_port}")
    
    if args.sftp_user:
        SFTP_CONFIG['username'] = args.sftp_user
        print(f"👤 SFTP 使用者設定為: {args.sftp_user}")
    
    if args.sftp_password:
        SFTP_CONFIG['password'] = args.sftp_password
        print("🔑 SFTP 密碼已更新")
    
    if args.sftp_timeout:
        SFTP_CONFIG['timeout'] = args.sftp_timeout
        print(f"⏱️ SFTP 逾時設定為: {args.sftp_timeout} 秒")
    
    # ===== 更新平行處理設定 =====
    if args.no_parallel:
        PARALLEL_CONFIG['enable_parallel'] = False
        print("🚶 已關閉平行處理，將使用循序處理")
    
    if args.parallel:
        PARALLEL_CONFIG['max_workers'] = args.parallel
        PARALLEL_CONFIG['enable_parallel'] = True
        print(f"⚡ 平行處理 worker 數設定為: {args.parallel}")
    
    # ===== 更新 Repo 設定 =====
    if args.repo_jobs:
        REPO_CONFIG['sync_jobs'] = args.repo_jobs
        print(f"🔄 Repo sync 並行數設定為: {args.repo_jobs}")
    
    if args.repo_retry:
        REPO_CONFIG['sync_retry'] = args.repo_retry
        print(f"🔁 Repo sync 重試次數設定為: {args.repo_retry}")
    
    # ===== 檢查是否為測試模式 =====
    if args.dry_run:
        print("\n" + "="*60)
        print("🧪 測試模式 (Dry Run) - 不會實際執行任何操作")
        print("="*60)
    
    # ===== 決定執行模式 =====
    if args.mapping:
        # 命令列模式
        print("\n" + "="*60)
        print("📋 Manifest 定版工具 - 命令列模式")
        print("="*60)
        
        # 建立工具實例
        tool = ManifestPinningTool()
        
        # 如果是測試模式，設定標記
        if args.dry_run:
            tool.dry_run = True
        
        try:
            # Step 1: 載入 mapping table
            print(f"\n📂 載入 mapping table: {args.mapping}")
            if not os.path.exists(args.mapping):
                print(f"❌ 檔案不存在: {args.mapping}")
                sys.exit(1)
            
            if not tool.load_mapping_table(args.mapping):
                print("❌ 無法載入 mapping table")
                sys.exit(1)
            
            print(f"✅ 成功載入 mapping table")
            
            # Step 2: 設定輸出目錄
            tool.output_dir = args.output or PATH_CONFIG['default_output_dir']
            os.makedirs(tool.output_dir, exist_ok=True)
            print(f"📁 輸出目錄: {tool.output_dir}")
            
            # Step 3: 設定報告檔名
            if args.report_name:
                PATH_CONFIG['report_filename'] = args.report_name
                print(f"📊 報告檔名: {args.report_name}")
            
            # Step 4: 連線到 SFTP
            print(f"\n🌐 連線到 SFTP 伺服器: {SFTP_CONFIG['host']}")
            if not tool.sftp_manager.connect():
                print("❌ 無法連線到 SFTP 伺服器")
                sys.exit(1)
            print("✅ SFTP 連線成功")
            
            try:
                # Step 5: 決定要處理的 DB 列表
                db_list = []
                db_versions = {}
                
                if args.dbs:
                    # 使用指定的 DB
                    db_specs = [db.strip() for db in args.dbs.split(',')]
                    
                    for db_spec in db_specs:
                        if '#' in db_spec:
                            # DB 名稱包含版本
                            db_name, version = db_spec.split('#', 1)
                            db_list.append(db_name)
                            db_versions[db_name] = version
                        else:
                            db_list.append(db_spec)
                    
                    print(f"\n📌 使用指定的 DB 列表: {', '.join(db_list)}")
                else:
                    # 使用所有指定類型的 DB
                    all_db_infos = tool.get_all_dbs(args.type)
                    db_list = list(set([db.db_info for db in all_db_infos]))
                    
                    if args.type == 'all':
                        print(f"\n📌 使用所有 DB，共 {len(db_list)} 個")
                    else:
                        print(f"\n📌 使用所有 {args.type} 類型的 DB，共 {len(db_list)} 個")
                
                # Step 6: 處理額外的版本設定
                if args.versions:
                    version_specs = [v.strip() for v in args.versions.split(',')]
                    for version_spec in version_specs:
                        if '#' in version_spec:
                            db_name, version = version_spec.split('#', 1)
                            db_versions[db_name] = version
                    
                    print(f"📌 設定了 {len(db_versions)} 個 DB 的版本")
                
                # Step 7: 確認處理資訊
                print("\n" + "-"*40)
                print("📋 準備處理以下 DB:")
                for i, db in enumerate(db_list, 1):
                    version_info = f" (版本: {db_versions[db]})" if db in db_versions else " (最新版本)"
                    print(f"  {i:3d}. {db}{version_info}")
                print("-"*40)
                
                if not db_list:
                    print("❌ 沒有找到要處理的 DB")
                    sys.exit(1)
                
                # Step 8: 詢問確認（除非是測試模式）
                if not args.dry_run:
                    if sys.stdin.isatty():  # 檢查是否在互動式環境
                        confirm = input(f"\n確認要處理 {len(db_list)} 個 DB? (Y/n): ").strip().lower()
                        if confirm == 'n':
                            print("❌ 使用者取消操作")
                            sys.exit(0)
                
                # Step 9: 開始處理
                print("\n" + "="*60)
                if args.dry_run:
                    print("🧪 開始測試執行（不會實際執行操作）")
                else:
                    print("🚀 開始執行定版處理")
                print("="*60)
                
                start_time = datetime.now()
                
                # 執行處理
                tool.process_selected_dbs(db_list, db_versions)
                
                end_time = datetime.now()
                elapsed_time = end_time - start_time
                
                # Step 10: 產生報告
                print("\n📊 產生處理報告...")
                report_path = os.path.join(tool.output_dir, PATH_CONFIG['report_filename'])
                tool.generate_report(report_path)
                
                # Step 11: 顯示結果摘要
                print("\n" + "="*60)
                print("✨ 處理完成！")
                print("="*60)
                print(f"📊 總 DB 數: {tool.report.total_dbs}")
                print(f"✅ 成功: {tool.report.successful_dbs}")
                print(f"❌ 失敗: {tool.report.failed_dbs}")
                print(f"⏭️ 跳過: {tool.report.skipped_dbs}")
                print(f"⏱️ 總耗時: {elapsed_time}")
                print(f"📁 輸出目錄: {tool.output_dir}")
                print(f"📊 報告檔案: {report_path}")
                print("="*60)
                
                # 如果有失敗的項目，顯示詳細資訊
                if tool.report.failed_dbs > 0:
                    print("\n❌ 失敗的 DB:")
                    for db in tool.report.db_details:
                        if db.status == 'failed':
                            print(f"  - {db.module}/{db.db_info}: {db.error_message}")
                
            finally:
                # 確保關閉 SFTP 連線
                print("\n🔌 關閉 SFTP 連線...")
                tool.sftp_manager.disconnect()
                
        except KeyboardInterrupt:
            print("\n\n⚠️ 使用者中斷執行")
            sys.exit(130)  # 128 + SIGINT
            
        except Exception as e:
            print(f"\n❌ 發生錯誤: {str(e)}")
            if args.debug:
                import traceback
                traceback.print_exc()
            sys.exit(1)
    
    else:
        # 互動式模式
        print("\n" + "="*60)
        print("🎮 Manifest 定版工具 - 互動式介面")
        print("="*60)
        print("提示: 使用 -h 參數查看命令列選項")
        print("="*60)
        
        try:
            # 建立並執行互動式介面
            ui = InteractiveUI()
            
            # 如果有設定參數，傳遞給 UI
            if args.output:
                ui.tool.output_dir = args.output
            
            if args.dry_run:
                ui.tool.dry_run = True
                print("🧪 測試模式已啟用")
            
            # 執行互動式介面
            ui.run_interactive()
            
        except KeyboardInterrupt:
            print("\n\n👋 再見！")
            sys.exit(0)
            
        except Exception as e:
            print(f"\n❌ 發生錯誤: {str(e)}")
            if args.debug:
                import traceback
                traceback.print_exc()
            sys.exit(1)

if __name__ == "__main__":
    main()