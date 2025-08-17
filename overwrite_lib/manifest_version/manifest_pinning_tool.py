#!/usr/bin/env python3
"""
Manifest Pinning Tool - 自動化定版工具 (改進版)
用於從 SFTP 下載 manifest 檔案並執行 repo 定版操作
修正版本：解決邏輯缺陷並改善模組化設計
"""

from enum import Enum
import os
import sys
import argparse
import pandas as pd
import paramiko
import subprocess
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import time
import logging
from dataclasses import dataclass, field, asdict
import signal
import atexit
from contextlib import contextmanager
from collections import defaultdict
import random
import socket
from threading import Semaphore, Lock

# =====================================
# ===== 版本資訊 =====
# =====================================
__version__ = '2.0.0'
__author__ = 'Vince Lin'
__date__ = '2024-12-19'

# =====================================
# ===== 配置管理器（集中管理所有配置） =====
# =====================================

class ConfigManager:
    """配置管理器 - 統一管理所有配置的優先級和來源"""
    
    def __init__(self):
        # 基礎配置
        self.sftp_config = {
            'host': 'mmsftpx.realtek.com',
            'port': 22,
            'username': 'lgwar_user',
            'password': 'Ab!123456',
            'timeout': 45,
            'retry_count': 5,
            'retry_delay': 10
        }
        
        self.jira_config = {
            'site': 'jira.realtek.com',
            'username': 'vince_lin',
            'password': 'Amon200!Amon200!',
            'api_url': 'https://jira.realtek.com/rest/api/2'
        }
        
        self.path_config = {
            'default_output_dir': './DB-source',
            'default_mapping_table': '../all_chip_mapping_table.xlsx',
            'manifest_pattern': r'manifest_(\d+)\.xml',
            'report_filename': 'pinning_report.xlsx',
            'progress_update_interval': 1
        }
        
        self.repo_config = {
            'repo_command': 'repo',
            'sync_jobs': 8,
            'sync_retry': 2,
            'init_timeout': 60,
            'sync_timeout': 7200,
            'async_sync': True,
            'show_sync_output': False
        }
        
        self.parallel_config = {
            'max_workers': 4,
            'enable_parallel': True,
        }
        
        self.log_config = {
            'level': logging.INFO,
            'format': '%(asctime)s - [%(levelname)s] - %(name)s - %(message)s',
            'date_format': '%Y-%m-%d %H:%M:%S'
        }
        
        # 預設執行配置
        self.default_execution_config = {
            'mapping_table': os.path.join(os.path.dirname(__file__), '..', 'all_chip_mapping_table.xlsx'),
            'db_type': 'all',
            'selected_dbs': ['DB2145', 'DB2858', 'DB2575', 'DB2919'],
            'db_versions': {},
            'output_dir': './DB-source',
            'auto_confirm': False,
            'sftp_override': {}
        }
        
        # 配置優先級追蹤
        self.config_sources = {}
        
    def apply_overrides(self, overrides: Dict[str, Any], source: str = 'user'):
        """應用配置覆蓋並記錄來源"""
        for key, value in overrides.items():
            if value is not None:
                self.config_sources[key] = source
                # 根據 key 更新對應的配置
                if key.startswith('sftp_'):
                    sftp_key = key.replace('sftp_', '')
                    if sftp_key in self.sftp_config:
                        self.sftp_config[sftp_key] = value
                elif key.startswith('repo_'):
                    repo_key = key.replace('repo_', '')
                    if repo_key in self.repo_config:
                        self.repo_config[repo_key] = value
                elif key.startswith('parallel_'):
                    parallel_key = key.replace('parallel_', '')
                    if parallel_key in self.parallel_config:
                        self.parallel_config[parallel_key] = value
    
    def get_config_source(self, key: str) -> str:
        """獲取配置項的來源"""
        return self.config_sources.get(key, 'default')
    
    def validate_config(self) -> Tuple[bool, List[str]]:
        """驗證配置的完整性和合理性"""
        errors = []
        
        # 驗證 SFTP 配置
        if not self.sftp_config.get('host'):
            errors.append("SFTP host 不能為空")
        if not self.sftp_config.get('username'):
            errors.append("SFTP username 不能為空")
        
        # 驗證路徑配置
        if not self.path_config.get('default_output_dir'):
            errors.append("輸出目錄不能為空")
        
        # 驗證並行配置
        if self.parallel_config['max_workers'] < 1:
            errors.append("max_workers 必須大於 0")
        
        return len(errors) == 0, errors

# 全域配置管理器實例
config_manager = ConfigManager()

# =====================================
# ===== JIRA API 客戶端（新增） =====
# =====================================

from jira import JIRA
import requests
from urllib.parse import quote
import urllib3

# 關閉 SSL 警告（如果 JIRA 使用自簽憑證）
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class JiraAPIClient:
    """改善後的 JIRA API 客戶端 - 針對 DB 命名慣例和 manifest 提取"""
    
    def __init__(self):
        self.logger = setup_logger(self.__class__.__name__)
        self.jira = None
        self.session = None
        self._connected = False
        self.base_url = f"https://{config_manager.jira_config['site']}"
        
    def _setup_logger(self):
        """設定專用的 logger"""
        logger = logging.getLogger(self.__class__.__name__)
        logger.setLevel(config_manager.log_config['level'])
        return logger
        
    def connect(self) -> bool:
        """連接到 JIRA"""
        try:
            username = config_manager.jira_config['username']
            password = config_manager.jira_config['password']
            
            self.logger.info(f"連接到 JIRA: {self.base_url}")
            
            # 建立 session
            self.session = requests.Session()
            self.session.auth = (username, password)
            self.session.headers.update({
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            })
            self.session.verify = False  # 如果有 SSL 問題
            
            # 測試連接
            test_url = f"{self.base_url}/rest/api/2/myself"
            response = self.session.get(test_url)
            
            if response.status_code == 200:
                self._connected = True
                user_info = response.json()
                self.logger.info(f"JIRA 連接成功，用戶: {user_info.get('displayName', username)}")
                return True
            elif response.status_code == 401:
                self.logger.error("JIRA 認證失敗，請檢查用戶名和密碼")
                return False
            else:
                self.logger.error(f"JIRA 連接失敗: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"JIRA 連接失敗: {e}")
            return False

    def search_db_ticket(self, db_name: str, module: str = None) -> Optional[str]:
        """
        根據 DB 命名慣例搜尋對應的 JIRA ticket
        
        Args:
            db_name: DB 名稱 (例如: DB2302)
            module: 模組名稱 (例如: Phoenix)
        
        Returns:
            找到的 ticket key (例如: MMQCDB-2302)
        """
        try:
            if not self._connected:
                if not self.connect():
                    return None
            
            # 策略 1: 根據 DB 命名慣例直接構建 ticket key
            ticket = self._search_by_naming_convention(db_name)
            if ticket:
                return ticket
            
            # 策略 2: 如果命名慣例不適用，使用傳統搜尋
            ticket = self._search_by_text(db_name, module)
            if ticket:
                return ticket
            
            self.logger.warning(f"未找到 {db_name} 相關的 JIRA ticket")
            return None
            
        except Exception as e:
            self.logger.error(f"搜尋 JIRA ticket 失敗: {e}")
            return None

    def _search_by_naming_convention(self, db_name: str) -> Optional[str]:
        """根據 DB 命名慣例直接構建 ticket key"""
        try:
            # 解析 DB 名稱，例如 DB2302 -> 2302
            db_number = db_name.replace('DB', '')
            
            # 根據命名慣例構建可能的 ticket key
            possible_tickets = [
                f"MMQCDB-{db_number}",  # 主要慣例：MMQCDB-2302
                f"LGSWRD-{db_number}",  # 備用慣例
                f"RTK-{db_number}",     # 備用慣例
                f"DB-{db_number}",      # 備用慣例
            ]
            
            for ticket_key in possible_tickets:
                self.logger.debug(f"檢查 ticket 是否存在: {ticket_key}")
                if self._check_ticket_exists(ticket_key):
                    self.logger.info(f"根據命名慣例找到 ticket: {ticket_key}")
                    return ticket_key
            
            self.logger.debug(f"命名慣例搜尋未找到 {db_name} 對應的 ticket")
            return None
            
        except Exception as e:
            self.logger.debug(f"命名慣例搜尋失敗: {e}")
            return None

    def _check_ticket_exists(self, ticket_key: str) -> bool:
        """檢查指定的 ticket 是否存在"""
        try:
            url = f"{self.base_url}/rest/api/2/issue/{ticket_key}"
            response = self.session.get(url)
            
            if response.status_code == 200:
                return True
            elif response.status_code == 404:
                return False
            else:
                self.logger.debug(f"檢查 ticket {ticket_key} 時發生錯誤: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.debug(f"檢查 ticket {ticket_key} 存在性時發生異常: {e}")
            return False

    def _search_by_text(self, db_name: str, module: str = None) -> Optional[str]:
        """傳統文字搜尋方式"""
        try:
            jql = f'text ~ "{db_name}"'
            
            if module:
                jql += f' AND text ~ "{module}"'
            
            jql += ' ORDER BY updated DESC'
            
            url = f"{self.base_url}/rest/api/2/search"
            params = {
                'jql': jql,
                'maxResults': 5,
                'fields': 'key,summary,description'
            }
            
            response = self.session.get(url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                issues = data.get('issues', [])
                
                if issues:
                    ticket_key = issues[0]['key']
                    self.logger.info(f"透過文字搜尋找到 {db_name} 的 JIRA ticket: {ticket_key}")
                    return ticket_key
            
            return None
            
        except Exception as e:
            self.logger.error(f"文字搜尋失敗: {e}")
            return None

    def get_source_command_from_ticket(self, ticket_key: str) -> Optional[str]:
        """
        從 JIRA ticket 中提取 source command
        專門針對包含 "-m" 參數或 [Latest] 的 repo init 命令
        
        Args:
            ticket_key: JIRA ticket key (例如: MMQCDB-2302)
        
        Returns:
            找到的 repo init 命令
        """
        try:
            if not self._connected:
                if not self.connect():
                    return None
            
            url = f"{self.base_url}/rest/api/2/issue/{ticket_key}"
            response = self.session.get(url)
            
            if response.status_code == 200:
                data = response.json()
                fields = data.get('fields', {})
                
                # 檢查描述欄位
                description = fields.get('description', '')
                if description:
                    self.logger.debug(f"檢查 {ticket_key} 的描述欄位...")
                    
                    # 1. 優先尋找 [Latest] 命令
                    cmd = self._extract_latest_repo_command(description)
                    if cmd:
                        self.logger.info(f"從 {ticket_key} 的描述中找到 [Latest] source command")
                        return cmd
                    
                    # 2. 尋找帶 "-m" 參數的命令
                    cmd = self._extract_repo_command_with_manifest(description)
                    if cmd:
                        self.logger.info(f"從 {ticket_key} 的描述中找到帶 -m 參數的 source command")
                        return cmd
                    
                    # 3. 尋找任何 repo init 命令
                    cmd = self._extract_any_repo_command(description)
                    if cmd:
                        self.logger.info(f"從 {ticket_key} 的描述中找到 source command")
                        return cmd
                
                # 檢查評論
                comments_data = fields.get('comment', {})
                comments = comments_data.get('comments', [])
                for comment in comments:
                    body = comment.get('body', '')
                    if body:
                        cmd = self._extract_latest_repo_command(body)
                        if cmd:
                            self.logger.info(f"從 {ticket_key} 的評論中找到 [Latest] source command")
                            return cmd
                        
                        cmd = self._extract_repo_command_with_manifest(body)
                        if cmd:
                            self.logger.info(f"從 {ticket_key} 的評論中找到帶 -m 參數的 source command")
                            return cmd
                
                self.logger.warning(f"在 ticket {ticket_key} 中未找到 source command")
                return None
            
            elif response.status_code == 404:
                self.logger.warning(f"Ticket {ticket_key} 不存在")
                return None
            else:
                self.logger.error(f"獲取 ticket {ticket_key} 失敗: HTTP {response.status_code}")
                return None
                
        except Exception as e:
            self.logger.error(f"從 ticket {ticket_key} 獲取 source command 失敗: {e}")
            return None

    def _extract_latest_repo_command(self, text: str) -> Optional[str]:
        """
        提取以 [Latest] 開頭的 repo init 命令
        例如：=> [Latest] repo init -u ssh://mm2sd.rtkbf.com:29418/realtek/android/manifest -b realtek/android-14/master -m atv-google-refplus.xml
        """
        if not text or 'repo init' not in text:
            return None
        
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            
            # 尋找包含 [Latest] 和 repo init 的行
            if '[Latest]' in line and 'repo init' in line:
                # 提取 repo init 命令部分
                repo_start = line.find('repo init')
                if repo_start != -1:
                    cmd = line[repo_start:].strip()
                    # 清理可能的尾隨字符
                    cmd = self._clean_command(cmd)
                    if self._is_valid_repo_command(cmd):
                        return cmd
        
        return None

    def _extract_repo_command_with_manifest(self, text: str) -> Optional[str]:
        """
        提取包含 "-m" 參數的 repo init 命令
        """
        if not text or 'repo init' not in text:
            return None
        
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            
            # 尋找包含 repo init 和 -m 參數的行
            if line.startswith('repo init') and ' -m ' in line:
                cmd = self._clean_command(line)
                if self._is_valid_repo_command(cmd):
                    return cmd
            
            # 處理可能的前綴（如 $, >, # 等）
            if 'repo init' in line and ' -m ' in line:
                repo_start = line.find('repo init')
                if repo_start != -1:
                    cmd = line[repo_start:].strip()
                    cmd = self._clean_command(cmd)
                    if self._is_valid_repo_command(cmd):
                        return cmd
        
        return None

    def _extract_any_repo_command(self, text: str) -> Optional[str]:
        """
        提取任何 repo init 命令
        """
        if not text or 'repo init' not in text:
            return None
        
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            
            if 'repo init' in line:
                repo_start = line.find('repo init')
                if repo_start != -1:
                    cmd = line[repo_start:].strip()
                    cmd = self._clean_command(cmd)
                    if self._is_valid_repo_command(cmd):
                        return cmd
        
        return None

    def _clean_command(self, cmd: str) -> str:
        """清理命令字符串"""
        # 移除常見的前綴
        prefixes = ['$', '>', '#', '//', '*', '-', '=>']
        for prefix in prefixes:
            if cmd.startswith(prefix):
                cmd = cmd[len(prefix):].strip()
        
        # 移除尾隨的換行符和特殊字符
        cmd = cmd.rstrip('\n\r\\')
        
        return cmd.strip()

    def _is_valid_repo_command(self, cmd: str) -> bool:
        """驗證是否為有效的 repo init 命令"""
        if not cmd or not cmd.startswith('repo init'):
            return False
        
        # 檢查是否包含必要的參數
        required_parts = ['-u', '-b']
        return all(part in cmd for part in required_parts)

    def disconnect(self):
        """斷開 JIRA 連接"""
        self._connected = False
        if self.session:
            self.session.close()
            self.session = None
        self.logger.info("JIRA 連接已關閉")

# =====================================
# ===== 日誌設定函式 =====
# =====================================

def setup_logger(name: str = __name__) -> logging.Logger:
    """設定日誌記錄器"""
    logger = logging.getLogger(name)
    logger.setLevel(config_manager.log_config['level'])
    
    if not logger.handlers:
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(config_manager.log_config['level'])
        
        # Formatter
        formatter = logging.Formatter(
            config_manager.log_config['format'],
            datefmt=config_manager.log_config['date_format']
        )
        console_handler.setFormatter(formatter)
        
        logger.addHandler(console_handler)
    
    return logger

logger = setup_logger(__name__)

# =====================================
# ===== 進度狀態定義 =====
# =====================================

class DBStatus(Enum):
    """DB 處理狀態"""
    PENDING = "等待中"
    DOWNLOADING_MANIFEST = "下載 manifest"
    CHECKING_REPO = "檢查 repo 狀態"
    REPO_INIT = "執行 repo init"
    REPO_SYNC = "執行 repo sync"
    EXPORTING = "導出版本"
    SUCCESS = "✅ 完成"
    FAILED = "❌ 失敗"
    SKIPPED = "⭐️ 跳過"
    
# =====================================
# ===== 資料結構定義 =====
# =====================================

@dataclass
class DBInfo:
    """DB 資訊資料結構（增強版）"""
    sn: int
    module: str
    db_type: str
    db_info: str
    db_folder: str
    sftp_path: str
    version: Optional[str] = None
    jira_link: Optional[str] = None
    source_command: Optional[str] = None
    manifest_file: Optional[str] = None
    manifest_full_path: Optional[str] = None
    local_path: Optional[str] = None
    has_existing_repo: bool = False
    status: DBStatus = DBStatus.PENDING
    error_message: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    sync_process: Optional[subprocess.Popen] = None
    # 新增：記錄實際使用的 source command
    actual_source_cmd: Optional[str] = None
    # 新增：記錄 sync 日誌路徑
    sync_log_path: Optional[str] = None

    def to_dict(self) -> dict:
        """轉換為字典格式（完整版）"""
        result = asdict(self)
        
        # 處理 Enum 和 datetime
        if isinstance(result['status'], DBStatus):
            result['status'] = result['status'].value
        if result['start_time']:
            result['start_time'] = result['start_time'].strftime('%Y-%m-%d %H:%M:%S')
        if result['end_time']:
            result['end_time'] = result['end_time'].strftime('%Y-%m-%d %H:%M:%S')
        
        # 新增：確保包含所有重要欄位
        result['source_command_used'] = self.actual_source_cmd or '未記錄'
        result['manifest_version'] = self.version or '最新'
        result['manifest_filename'] = self.manifest_file or '未下載'
        
        # 移除 Popen 物件（無法序列化）
        result.pop('sync_process', None)
        
        return result

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
        self.db_details.append(db_info)
        if db_info.status == DBStatus.SUCCESS:
            self.successful_dbs += 1
        elif db_info.status == DBStatus.FAILED:
            self.failed_dbs += 1
        elif db_info.status == DBStatus.SKIPPED:
            self.skipped_dbs += 1
    
    def finalize(self):
        """完成報告"""
        self.end_time = datetime.now()
        self.total_dbs = len(self.db_details)

# =====================================
# ===== 資源管理器（改善資源洩漏問題） =====
# =====================================

class ResourceManager:
    """統一管理所有系統資源，確保正確清理"""
    
    def __init__(self):
        self.active_processes = {}
        self.sftp_connections = []
        self.lock = threading.Lock()
        self.logger = setup_logger(self.__class__.__name__)
        
        # 註冊清理函式
        atexit.register(self.cleanup_all)
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """處理中斷信號"""
        self.logger.warning(f"收到信號 {signum}，開始清理資源...")
        self.cleanup_all()
        sys.exit(1)
    
    def register_process(self, name: str, process: subprocess.Popen):
        """註冊新的子進程"""
        with self.lock:
            self.active_processes[name] = process
            self.logger.debug(f"註冊進程 {name} (PID: {process.pid})")
    
    def unregister_process(self, name: str):
        """取消註冊子進程"""
        with self.lock:
            if name in self.active_processes:
                del self.active_processes[name]
                self.logger.debug(f"取消註冊進程 {name}")
    
    def register_sftp(self, connection):
        """註冊 SFTP 連線"""
        with self.lock:
            self.sftp_connections.append(connection)
    
    def cleanup_all(self):
        """清理所有資源"""
        with self.lock:
            # 終止所有子進程
            for name, process in self.active_processes.items():
                try:
                    if process.poll() is None:
                        self.logger.info(f"終止進程 {name} (PID: {process.pid})")
                        process.terminate()
                        process.wait(timeout=5)
                except Exception as e:
                    self.logger.error(f"終止進程 {name} 失敗: {e}")
                    try:
                        process.kill()
                    except:
                        pass
            
            # 關閉所有 SFTP 連線
            for conn in self.sftp_connections:
                try:
                    # 應該檢查是否有 disconnect 方法
                    if hasattr(conn, 'disconnect'):
                        conn.disconnect()
                    elif hasattr(conn, 'close'):
                        conn.close()
                except:
                    pass
            
            self.active_processes.clear()
            self.sftp_connections.clear()

# 全域資源管理器
resource_manager = ResourceManager()

# =====================================
# ===== 進度管理器 =====
# =====================================

class ProgressManager:
    """管理所有 DB 的處理進度（完整版）"""
    
    def __init__(self):
        self.db_status = {}  # {db_name: (status, message)}
        self.db_sync_progress = {}  # {db_name: sync_progress_info}
        self.db_info_cache = {}  # {db_name: DBInfo} - 緩存 DB 信息
        self.lock = threading.Lock()
        self.start_time = datetime.now()
        self.completed_count = 0
        self.total_count = 0
        self.sync_progress_parser = RepoSyncProgress()
        self.logger = setup_logger(self.__class__.__name__)
        
    def init_db(self, db_name: str, db_info: DBInfo = None):
        """初始化 DB 狀態"""
        with self.lock:
            self.db_status[db_name] = (DBStatus.PENDING, "")
            self.db_sync_progress[db_name] = None
            if db_info:
                self.db_info_cache[db_name] = db_info
            self.total_count += 1
    
    def update_status(self, db_name: str, status: DBStatus, message: str = ""):
        """更新 DB 狀態"""
        with self.lock:
            self.db_status[db_name] = (status, message)
            if status in [DBStatus.SUCCESS, DBStatus.FAILED, DBStatus.SKIPPED]:
                self.completed_count += 1
    
    def update_sync_progress(self, db_name: str, log_file: str):
        """更新 repo sync 進度"""
        try:
            progress_info = self.sync_progress_parser.parse_sync_log(log_file)
            
            with self.lock:
                self.db_sync_progress[db_name] = progress_info
                db_info = self.db_info_cache.get(db_name)
                
                # 根據 sync 狀態更新整體狀態
                if progress_info['status'] == 'completed':
                    self.db_status[db_name] = (DBStatus.REPO_SYNC, "✅ 同步完成，準備導出")
                elif progress_info['status'] == 'failed':
                    error_msg = progress_info['errors'][0] if progress_info['errors'] else "同步失敗"
                    self.db_status[db_name] = (DBStatus.FAILED, f"❌ {error_msg}")
                else:
                    # 構建進度消息
                    progress_msg = self._build_sync_progress_message(progress_info, db_info)
                    self.db_status[db_name] = (DBStatus.REPO_SYNC, progress_msg)
                    
        except Exception as e:
            self.logger.error(f"更新 {db_name} sync 進度失敗: {e}")
    
    def _build_sync_progress_message(self, progress_info: Dict, db_info: DBInfo = None) -> str:
        """構建 sync 進度消息（增強版）"""
        parts = []
        
        # 版本信息
        if db_info and db_info.version:
            parts.append(f"📋 v{db_info.version}")
        
        # 整體進度
        if progress_info['overall_progress'] != '0%':
            parts.append(f"🔄 {progress_info['overall_progress']}")
            
            # 項目計數
            if progress_info['total_projects'] > 0:
                parts.append(f"({progress_info['current_projects']}/{progress_info['total_projects']})")
        else:
            parts.append("🔄 同步中...")
        
        # 當前 repository
        if progress_info['current_repo']:
            repo_short = progress_info['current_repo'].split('/')[-1] if '/' in progress_info['current_repo'] else progress_info['current_repo']
            if len(repo_short) > 15:
                repo_short = repo_short[:12] + "..."
            parts.append(f"📦 {repo_short}")
        
        # 下載速度
        if progress_info['speed']:
            parts.append(f"⚡ {progress_info['speed']}")
        
        return " ".join(parts)
    
    def get_progress_display(self) -> str:
        """取得進度顯示字串（完整版 - 包含詳細信息）"""
        with self.lock:
            lines = []
            lines.append("\n" + "="*100)
            lines.append(f"📊 Manifest 定版進度 - {datetime.now().strftime('%H:%M:%S')}")
            lines.append(f"   完成: {self.completed_count}/{self.total_count}")
            
            elapsed = datetime.now() - self.start_time
            lines.append(f"   耗時: {str(elapsed).split('.')[0]}")
            
            # 計算預估剩餘時間
            if self.completed_count > 0:
                avg_time = elapsed.total_seconds() / self.completed_count
                remaining = (self.total_count - self.completed_count) * avg_time
                lines.append(f"   預估剩餘: {str(timedelta(seconds=int(remaining)))}")
            
            lines.append("="*100)
            
            # 分組顯示不同狀態的 DB - 增強版
            for status in DBStatus:
                dbs_in_status = [(name, msg) for name, (s, msg) in self.db_status.items() if s == status]
                if dbs_in_status:
                    lines.append(f"\n{status.value}:")
                    for name, msg in dbs_in_status:
                        db_info = self.db_info_cache.get(name)
                        
                        # 構建完整的顯示信息
                        display_parts = [f"  • {name}:"]
                        
                        # 添加版本信息
                        if db_info and db_info.version:
                            display_parts.append(f"[v{db_info.version}]")
                        
                        # 添加狀態消息
                        if msg:
                            display_parts.append(msg)
                        
                        # 如果是 sync 狀態，添加 source command 信息
                        if status == DBStatus.REPO_SYNC and db_info and db_info.actual_source_cmd:
                            # 簡化 source command 顯示
                            cmd_short = self._simplify_source_command(db_info.actual_source_cmd)
                            display_parts.append(f"📝 {cmd_short}")
                        
                        lines.append(" ".join(display_parts))
            
            lines.append("="*100)
            return "\n".join(lines)
    
    def _simplify_source_command(self, source_cmd: str) -> str:
        """簡化 source command 顯示"""
        if not source_cmd:
            return ""
        
        # 提取關鍵信息：主機和分支
        try:
            # 提取 -u 後的主機信息
            u_match = re.search(r'-u\s+(\S+)', source_cmd)
            host_info = ""
            if u_match:
                url = u_match.group(1)
                if "mm2sd" in url:
                    host_info = "mm2sd"
                elif "ssh://" in url:
                    host_info = url.split("://")[1].split("/")[0].split(".")[0]
                else:
                    host_info = "repo"
            
            # 提取 -b 後的分支信息
            b_match = re.search(r'-b\s+(\S+)', source_cmd)
            branch_info = ""
            if b_match:
                branch = b_match.group(1)
                if "android-14" in branch:
                    branch_info = "android-14"
                elif "android" in branch:
                    branch_info = branch.split("/")[-1] if "/" in branch else branch
                else:
                    branch_info = branch.split("/")[-1] if "/" in branch else branch
            
            # 提取 -m 後的 manifest 信息
            m_match = re.search(r'-m\s+(\S+)', source_cmd)
            manifest_info = ""
            if m_match:
                manifest = m_match.group(1)
                manifest_info = manifest.replace('.xml', '').replace('atv-', '').replace('google-', '')
            
            # 組合簡化信息
            parts = []
            if host_info:
                parts.append(host_info)
            if branch_info:
                parts.append(branch_info)
            if manifest_info:
                parts.append(manifest_info)
            
            return "/".join(parts) if parts else "repo"
            
        except Exception:
            # 如果解析失敗，返回前 30 個字符
            return source_cmd[:30] + "..." if len(source_cmd) > 30 else source_cmd

    def display_progress(self, clear_screen: bool = True):
        """顯示進度（可選清屏）"""
        try:
            if clear_screen:
                os.system('cls' if os.name == 'nt' else 'clear')
            print(self.get_progress_display())
        except Exception as e:
            self.logger.error(f"顯示進度失敗: {e}")
            print(f"進度更新錯誤: {e}")

# =====================================
# ===== Source Command 管理器（解決固定命令問題） =====
# =====================================

# =====================================
# ===== Source Command 管理器（使用 JIRA API） =====
# =====================================

class SourceCommandManager:
    """管理不同 DB 的 source command - 從 JIRA 即時獲取"""
    
    def __init__(self):
        self.logger = setup_logger(self.__class__.__name__)
        self.jira_client = JiraAPIClient()
        self.cache = {}  # 快取查詢結果，避免重複查詢
        
    def get_source_command(self, db_info: DBInfo, mapping_df: pd.DataFrame = None) -> Optional[str]:
        """
        根據 DB 資訊獲取對應的 source command
        優先級：
        1. 快取結果
        2. 從 mapping table 中的 JIRA ticket 獲取
        3. 從 JIRA 搜尋 DB 相關 ticket
        4. 最終備用命令
        """
        db_name = db_info.db_info
        
        # 1. 檢查快取
        if db_name in self.cache:
            self.logger.info(f"使用快取的 source command for {db_name}")
            return self.cache[db_name]
        
        # 2. 嘗試從 mapping table 獲取
        if mapping_df is not None:
            cmd = self._get_from_jira_or_mapping(db_info, mapping_df)
            if cmd:
                self.cache[db_name] = cmd
                return cmd
        
        # 3. 直接從 JIRA 搜尋
        self.logger.info(f"從 JIRA 搜尋 {db_name} 相關 ticket...")
        ticket_key = self.jira_client.search_db_ticket(db_name, db_info.module)
        if ticket_key:
            cmd = self.jira_client.get_source_command_from_ticket(ticket_key)
            if cmd:
                self.cache[db_name] = cmd
                return cmd
        
        # 4. 最終備用
        self.logger.warning(f"無法從 JIRA 獲取 {db_name} 的 source command，使用備用命令")
        self.logger.warning("建議：請在 JIRA 中建立相關 ticket 並記錄 source command")
        return None
    
    def _get_from_jira_or_mapping(self, db_info: DBInfo, mapping_df: pd.DataFrame) -> Optional[str]:
        """
        從 JIRA 或 mapping table 獲取 source command
        完整實作版本
        """
        try:
            db_name = db_info.db_info
            
            # 根據 DB 類型查找對應的欄位
            type_column_map = {
                'master': 'DB_Info',
                'premp': 'premp_DB_Info',
                'mp': 'mp_DB_Info',
                'mpbackup': 'mpbackup_DB_Info'
            }
            
            col = type_column_map.get(db_info.db_type)
            if not col or col not in mapping_df.columns:
                return None
            
            # 找到對應的行
            mask = mapping_df[col] == db_name
            if not mask.any():
                return None
            
            row = mapping_df[mask].iloc[0]
            
            # 1. 首先檢查是否有 source_command 欄位直接記錄
            source_cmd_columns = ['source_command', 'Source_Command', 'SOURCE_COMMAND', 'SourceCmd']
            for cmd_col in source_cmd_columns:
                if cmd_col in row and pd.notna(row[cmd_col]):
                    cmd = str(row[cmd_col]).strip()
                    if cmd and 'repo init' in cmd:
                        self.logger.info(f"從 mapping table 的 {cmd_col} 欄位獲取 source command")
                        return cmd
            
            # 2. 檢查是否有 JIRA ticket 欄位
            jira_columns = ['jira_ticket', 'JIRA_Ticket', 'JiraTicket', 'Jira', 'JIRA', 'ticket', 'Ticket']
            jira_ticket = None
            
            for jira_col in jira_columns:
                if jira_col in row and pd.notna(row[jira_col]):
                    jira_ticket = str(row[jira_col]).strip()
                    if jira_ticket:
                        self.logger.info(f"從 mapping table 找到 JIRA ticket: {jira_ticket}")
                        break
            
            # 3. 如果有 JIRA ticket，從 JIRA 獲取
            if jira_ticket:
                # 確保 JIRA 客戶端已連接
                if not self.jira_client._connected:
                    if not self.jira_client.connect():
                        self.logger.error("無法連接到 JIRA")
                        return None
                
                # 從 JIRA ticket 獲取 source command
                cmd = self.jira_client.get_source_command_from_ticket(jira_ticket)
                if cmd:
                    self.logger.info(f"成功從 JIRA ticket {jira_ticket} 獲取 source command")
                    return cmd
                else:
                    self.logger.warning(f"JIRA ticket {jira_ticket} 中未找到 source command")
            
            # 4. 如果沒有 JIRA ticket，嘗試用 DB 名稱搜尋 JIRA
            if not jira_ticket:
                self.logger.info(f"mapping table 中沒有 JIRA ticket，嘗試搜尋 {db_name}")
                
                # 確保 JIRA 客戶端已連接
                if not self.jira_client._connected:
                    if not self.jira_client.connect():
                        return None
                
                # 搜尋相關 ticket
                found_ticket = self.jira_client.search_db_ticket(db_name, db_info.module)
                if found_ticket:
                    cmd = self.jira_client.get_source_command_from_ticket(found_ticket)
                    if cmd:
                        self.logger.info(f"從搜尋到的 ticket {found_ticket} 獲取 source command")
                        # 可以考慮將找到的 ticket 更新回 mapping table
                        return cmd
            
            return None
            
        except Exception as e:
            self.logger.error(f"_get_from_jira_or_mapping 失敗: {e}")
            return None
    
    def update_source_command(self, db_name: str, command: str):
        """更新特定 DB 的 source command 快取"""
        self.cache[db_name] = command
        self.logger.info(f"更新 {db_name} 的 source command 快取")
    
    def clear_cache(self):
        """清除所有快取"""
        self.cache.clear()
        self.logger.info("已清除所有 source command 快取")
    
    def test_jira_connection(self) -> bool:
        """測試 JIRA 連接"""
        try:
            if self.jira_client.connect():
                self.logger.info("JIRA 連接測試成功")
                return True
            else:
                self.logger.error("JIRA 連接測試失敗")
                return False
        except Exception as e:
            self.logger.error(f"JIRA 連接測試異常: {e}")
            return False
        
# =====================================
# ===== Mapping Table 讀取器 =====
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
            required_columns = ['SN', 'Module', 'DB_Type', 'DB_Info']
            missing_columns = [col for col in required_columns if col not in self.df.columns]
            
            if missing_columns:
                self.logger.warning(f"缺少欄位: {missing_columns}")
                
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
                db_info_col = cols[1]  # DB_Info 欄位
                if db_info_col in row and pd.notna(row[db_info_col]):
                    db_info = DBInfo(
                        sn=row['SN'] if 'SN' in row else idx + 1,
                        module=row['Module'] if 'Module' in row else '',
                        db_type=dtype,
                        db_info=str(row[db_info_col]),
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

# =====================================
# ===== SFTP 管理器（改善路徑處理） =====
# =====================================

class ThreadSafeSFTPManager:
    """執行緒安全的 SFTP 管理器（完整增強版 - 解決連線問題）"""
    
    def __init__(self, config: Dict = None):
        self.config = config or config_manager.sftp_config
        self.logger = setup_logger(self.__class__.__name__)
        self._local = threading.local()
        self._main_connected = False
        self.progress_callback = None
        
        # 連線池管理 - 解決併發連線問題
        self._connection_semaphore = Semaphore(2)  # 限制最大併發連線數為 2
        self._connection_lock = Lock()
        self._failed_connections = 0
        self._last_failure_time = 0
        self._backoff_time = 0
        
        # 連線重試配置
        self.retry_config = {
            'max_retries': 5,
            'base_delay': 2.0,
            'max_delay': 60.0,
            'exponential_base': 2.0,
            'jitter_range': 0.5
        }
    
    def set_progress_callback(self, callback):
        """設置進度回調函數"""
        self.progress_callback = callback
    
    def _update_progress(self, db_name: str, status: str, message: str):
        """更新進度（如果有回調函數）"""
        if self.progress_callback:
            self.progress_callback(db_name, status, message)
    
    def _calculate_backoff_delay(self, attempt: int) -> float:
        """計算退避延遲時間"""
        base_delay = self.retry_config['base_delay']
        max_delay = self.retry_config['max_delay']
        exponential_base = self.retry_config['exponential_base']
        jitter_range = self.retry_config['jitter_range']
        
        # 指數退避
        delay = base_delay * (exponential_base ** attempt)
        delay = min(delay, max_delay)
        
        # 添加隨機抖動避免雷群效應
        jitter = random.uniform(-jitter_range, jitter_range) * delay
        delay = max(0.1, delay + jitter)
        
        return delay
    
    def _should_apply_global_backoff(self) -> bool:
        """檢查是否需要全域退避"""
        current_time = time.time()
        
        with self._connection_lock:
            # 如果最近失敗太多，實施全域退避
            if self._failed_connections >= 3:
                time_since_failure = current_time - self._last_failure_time
                if time_since_failure < self._backoff_time:
                    return True
                else:
                    # 重置失敗計數
                    self._failed_connections = 0
                    self._backoff_time = 0
        
        return False
    
    def _record_connection_failure(self):
        """記錄連線失敗"""
        current_time = time.time()
        
        with self._connection_lock:
            self._failed_connections += 1
            self._last_failure_time = current_time
            # 根據失敗次數增加退避時間
            self._backoff_time = min(30.0, self._failed_connections * 5.0)
            
            self.logger.warning(f"記錄連線失敗，總失敗次數: {self._failed_connections}, 退避時間: {self._backoff_time}s")
    
    def _record_connection_success(self):
        """記錄連線成功"""
        with self._connection_lock:
            # 成功連線後，重置部分失敗計數
            if self._failed_connections > 0:
                self._failed_connections = max(0, self._failed_connections - 1)
                self.logger.info(f"連線成功，調整失敗計數: {self._failed_connections}")
    
    def connect(self) -> bool:
        """建立主連線（用於測試和驗證）- 增強版"""
        thread_name = threading.current_thread().name
        
        # 檢查全域退避
        if self._should_apply_global_backoff():
            backoff_remaining = self._backoff_time - (time.time() - self._last_failure_time)
            self.logger.warning(f"[{thread_name}] 因全域退避而跳過連線測試，剩餘 {backoff_remaining:.1f}s")
            return False
        
        # 獲取連線信號量
        if not self._connection_semaphore.acquire(blocking=False):
            self.logger.warning(f"[{thread_name}] 達到最大併發連線數，等待...")
            if not self._connection_semaphore.acquire(timeout=30):
                self.logger.error(f"[{thread_name}] 獲取連線信號量超時")
                return False
        
        try:
            for attempt in range(self.retry_config['max_retries']):
                try:
                    self.logger.info(f"[{thread_name}] 嘗試連接到 SFTP: {self.config['host']}:{self.config['port']} (嘗試 {attempt + 1})")
                    
                    # 建立 transport 連線，增加更詳細的配置
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(self.config.get('timeout', 30))
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                    
                    try:
                        sock.connect((self.config['host'], self.config['port']))
                        self.logger.debug(f"[{thread_name}] Socket 連線成功")
                    except socket.timeout:
                        sock.close()
                        raise Exception("Socket 連線超時")
                    except socket.error as e:
                        sock.close()
                        raise Exception(f"Socket 連線失敗: {e}")
                    
                    transport = paramiko.Transport(sock)
                    transport.set_keepalive(30)
                    
                    # 設置更寬鬆的連線參數
                    transport.banner_timeout = 45
                    transport.handshake_timeout = 45
                    transport.auth_timeout = 30
                    
                    # 修復：移除 timeout 參數
                    transport.connect(
                        username=self.config['username'],
                        password=self.config['password']
                    )
                    
                    sftp = paramiko.SFTPClient.from_transport(transport)
                    
                    # 測試連線
                    sftp.listdir('.')
                    
                    # 清理測試連線
                    sftp.close()
                    transport.close()
                    
                    self._main_connected = True
                    self._record_connection_success()
                    self.logger.info(f"[{thread_name}] SFTP 連線測試成功")
                    return True
                    
                except Exception as e:
                    self.logger.warning(f"[{thread_name}] SFTP 連線嘗試 {attempt + 1} 失敗: {e}")
                    
                    if attempt < self.retry_config['max_retries'] - 1:
                        delay = self._calculate_backoff_delay(attempt)
                        self.logger.info(f"[{thread_name}] 等待 {delay:.1f} 秒後重試...")
                        time.sleep(delay)
                    else:
                        self._record_connection_failure()
                        self.logger.error(f"[{thread_name}] SFTP 連線失敗，已達最大重試次數")
            
            self._main_connected = False
            return False
            
        finally:
            self._connection_semaphore.release()
    
    def disconnect(self):
        """斷開連線 - 增強版"""
        try:
            # 清理本地連線
            if hasattr(self._local, 'sftp') and self._local.sftp:
                try:
                    self._local.sftp.close()
                except:
                    pass
            if hasattr(self._local, 'transport') and self._local.transport:
                try:
                    self._local.transport.close()
                except:
                    pass
            if hasattr(self._local, 'connected'):
                self._local.connected = False
                
            self._main_connected = False
            self.logger.info("SFTP 連線已關閉")
            
        except Exception as e:
            self.logger.warning(f"關閉 SFTP 連線時發生錯誤: {e}")
    
    def _get_connection(self) -> Tuple[Optional[paramiko.SFTPClient], Optional[paramiko.Transport]]:
        """為當前線程獲取或建立 SFTP 連線 - 增強版"""
        thread_name = threading.current_thread().name
        
        if not hasattr(self._local, 'connected') or not self._local.connected:
            # 檢查全域退避
            if self._should_apply_global_backoff():
                backoff_remaining = self._backoff_time - (time.time() - self._last_failure_time)
                self.logger.warning(f"[{thread_name}] 全域退避中，剩餘 {backoff_remaining:.1f} 秒")
                return None, None
            
            # 獲取連線信號量
            if not self._connection_semaphore.acquire(blocking=False):
                self.logger.warning(f"[{thread_name}] 等待連線信號量...")
                if not self._connection_semaphore.acquire(timeout=60):
                    self.logger.error(f"[{thread_name}] 獲取連線信號量超時")
                    return None, None
            
            try:
                for attempt in range(self.retry_config['max_retries']):
                    try:
                        self.logger.debug(f"[{thread_name}] 建立新的 SFTP 連線 (嘗試 {attempt + 1})")
                        
                        # 建立 socket 連線
                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock.settimeout(self.config.get('timeout', 30))
                        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                        
                        try:
                            sock.connect((self.config['host'], self.config['port']))
                        except socket.timeout:
                            sock.close()
                            raise Exception("Socket 連線超時")
                        except socket.error as e:
                            sock.close()
                            raise Exception(f"Socket 連線失敗: {e}")
                        
                        transport = paramiko.Transport(sock)
                        transport.set_keepalive(30)
                        transport.banner_timeout = 45  # 增加 banner 超時時間
                        transport.handshake_timeout = 45  # 增加握手超時時間
                        transport.auth_timeout = 30
                        
                        # 修復：移除 timeout 參數
                        transport.connect(
                            username=self.config['username'],
                            password=self.config['password']
                        )
                        
                        sftp = paramiko.SFTPClient.from_transport(transport)
                        
                        self._local.transport = transport
                        self._local.sftp = sftp
                        self._local.connected = True
                        
                        # 註冊到資源管理器
                        resource_manager.register_sftp(self)
                        
                        self._record_connection_success()
                        self.logger.debug(f"[{thread_name}] SFTP 連線建立成功")
                        break
                        
                    except Exception as e:
                        self.logger.warning(f"[{thread_name}] SFTP 連線嘗試 {attempt + 1} 失敗: {e}")
                        
                        if attempt < self.retry_config['max_retries'] - 1:
                            delay = self._calculate_backoff_delay(attempt)
                            self.logger.info(f"[{thread_name}] 等待 {delay:.1f} 秒後重試...")
                            time.sleep(delay)
                        else:
                            self._record_connection_failure()
                            self._local.connected = False
                            return None, None
                            
            finally:
                self._connection_semaphore.release()
        
        return getattr(self._local, 'sftp', None), getattr(self._local, 'transport', None)
    
    def _is_version_directory(self, dir_name: str) -> bool:
        """檢查是否為版本目錄（專門支援4種格式）"""
        patterns = [
            # 主要格式：數字_all_12位時間戳
            r'^\d+_all_\d{12}$',          # 206_all_202507100000
            r'^\d+_all_\d{12}_.*$',       # 465_all_202502170030_NG_uboot_fail (帶後綴)
            
            # 次要格式：數字_12位時間戳
            r'^\d+_\d{12}$',              # 204_202507081101
            r'^\d+_\d{12}_.*$',           # 466_202502171018_NG_uboot_fail (帶後綴)
            
            # 保留簡單格式以防萬一
            r'^\d+$',                     # 純數字：206, 204
            r'^v\d+$',                   # v + 數字：v206
        ]
        
        for pattern in patterns:
            if re.match(pattern, dir_name, re.IGNORECASE):
                return True
        return False
    
    def _extract_version_number_flexible(self, dir_name: str) -> Optional[str]:
        """提取版本號（開頭的數字）"""
        patterns = [
            r'^(\d+)_all_\d{12}',         # 206_all_202507100000 -> 206
            r'^(\d+)_all_\d{12}_',        # 465_all_202502170030_NG_uboot_fail -> 465
            r'^(\d+)_\d{12}',             # 204_202507081101 -> 204  
            r'^(\d+)_\d{12}_',            # 466_202502171018_NG_uboot_fail -> 466
            r'^(\d+)$',                   # 206 -> 206
            r'^v(\d+)',                   # v206 -> 206
            r'^(\d+)',                    # 任何開頭數字
        ]
        
        for pattern in patterns:
            match = re.search(pattern, dir_name, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    def _parse_version_directory(self, dir_name: str, mtime: float) -> Optional[Dict]:
        """解析版本目錄的詳細信息"""
        try:
            version_info = {
                'dir_name': dir_name,
                'version': self._extract_version_number_flexible(dir_name),
                'version_number': None,
                'timestamp': None,
                'format_type': 'unknown',
                'mtime': mtime,
                'has_suffix': False,
                'suffix': ''
            }
            
            # 識別具體格式
            if re.match(r'^\d+_all_\d{12}_.*$', dir_name):
                # 格式：465_all_202502170030_NG_uboot_fail
                parts = dir_name.split('_', 3)  # 分成4部分
                version_info.update({
                    'version_number': parts[0],
                    'timestamp': int(parts[2]) if parts[2].isdigit() else 0,
                    'format_type': 'version_all_timestamp_suffix',
                    'has_suffix': True,
                    'suffix': parts[3] if len(parts) > 3 else ''
                })
                
            elif re.match(r'^\d+_all_\d{12}$', dir_name):
                # 格式：206_all_202507100000
                parts = dir_name.split('_')
                version_info.update({
                    'version_number': parts[0],
                    'timestamp': int(parts[2]) if parts[2].isdigit() else 0,
                    'format_type': 'version_all_timestamp'
                })
                
            elif re.match(r'^\d+_\d{12}_.*$', dir_name):
                # 格式：466_202502171018_NG_uboot_fail
                parts = dir_name.split('_', 2)  # 分成3部分
                version_info.update({
                    'version_number': parts[0],
                    'timestamp': int(parts[1]) if parts[1].isdigit() else 0,
                    'format_type': 'version_timestamp_suffix',
                    'has_suffix': True,
                    'suffix': parts[2] if len(parts) > 2 else ''
                })
                
            elif re.match(r'^\d+_\d{12}$', dir_name):
                # 格式：204_202507081101
                parts = dir_name.split('_')
                version_info.update({
                    'version_number': parts[0],
                    'timestamp': int(parts[1]) if parts[1].isdigit() else 0,
                    'format_type': 'version_timestamp'
                })
                
            elif re.match(r'^\d+$', dir_name):
                # 格式：純數字
                version_info.update({
                    'version_number': dir_name,
                    'timestamp': 0,
                    'format_type': 'simple_number'
                })
                
            elif re.match(r'^v\d+$', dir_name):
                # 格式：v206
                version_info.update({
                    'version_number': dir_name[1:],
                    'timestamp': 0,
                    'format_type': 'v_number'
                })
            
            # 確保版本號是字符串
            if version_info['version_number']:
                version_info['version_number'] = str(version_info['version_number'])
            
            return version_info
            
        except Exception as e:
            self.logger.debug(f"解析版本目錄失敗 {dir_name}: {e}")
            return None
    
    def _parse_and_sort_version_directories(self, items: List) -> List[Dict]:
        """解析和排序版本目錄"""
        version_dirs = []
        
        for item in items:
            if item.st_mode & 0o40000:  # 是目錄
                if self._is_version_directory(item.filename):
                    version_info = self._parse_version_directory(item.filename, item.st_mtime)
                    if version_info:
                        version_dirs.append(version_info)
        
        # 排序邏輯：版本號（數字）降序 -> 時間戳降序 -> 修改時間降序
        # 帶後綴的版本優先級較低（通常是失敗的建置）
        def sort_key(x):
            version_num = 0
            try:
                if x['version_number'] and x['version_number'].isdigit():
                    version_num = int(x['version_number'])
            except:
                pass
            
            timestamp = x.get('timestamp', 0) or 0
            mtime = x.get('mtime', 0) or 0
            has_suffix = x.get('has_suffix', False)
            
            # 有後綴的版本排在後面（優先級較低）
            suffix_penalty = 1 if has_suffix else 0
            
            return (version_num, -suffix_penalty, timestamp, mtime)
        
        version_dirs.sort(key=sort_key, reverse=True)
        
        return version_dirs
    
    def _calculate_manifest_priority(self, filename: str, version_num: str) -> int:
        """計算 manifest 文件的優先級"""
        priority = 0
        
        # 文件名包含 manifest 得分
        if 'manifest' in filename.lower():
            priority += 100
        
        # 包含版本號得分
        if version_num and version_num in filename:
            priority += 50
        
        # 特定命名模式得分
        if filename.startswith('manifest_'):
            priority += 30
        
        # XML 文件得分
        if filename.endswith('.xml'):
            priority += 20
        
        # 特殊命名模式的優先級
        special_patterns = [
            'atv-google-refplus',  # Android TV Google Reference Plus
            'tv-google',           # TV Google
            'android-tv',          # Android TV
            'refplus',            # Reference Plus
            'master',             # Master manifest
            'default',            # Default manifest
        ]
        
        filename_lower = filename.lower()
        for pattern in special_patterns:
            if pattern in filename_lower:
                priority += 10
        
        return priority
    
    def find_latest_manifest(self, base_path: str, db_name: str = None) -> Optional[Tuple[str, str]]:
        """尋找最新的 manifest 檔案（優化版 - 只檢查最新版本）"""
        thread_name = threading.current_thread().name
        
        try:
            sftp, client = self._get_connection()
            if not sftp:
                error_msg = "❌ 無法建立 SFTP 連線"
                self._update_progress(db_name, "DOWNLOADING_MANIFEST", error_msg)
                raise Exception(error_msg)
            
            # Step 1: 快速掃描目錄
            # self._update_progress(db_name, "DOWNLOADING_MANIFEST", f"🔍 掃描目錄: {os.path.basename(base_path)}")
            self.logger.info(f"[{thread_name}] 🔍 搜索路徑: {base_path}")
            
            try:
                start_scan = time.time()
                items = sftp.listdir_attr(base_path)
                scan_time = time.time() - start_scan
                
                self._update_progress(
                    db_name, 
                    "DOWNLOADING_MANIFEST", 
                    f"✅ 找到 {len(items)} 個項目 ({scan_time:.1f}s)"
                )
                self.logger.info(f"[{thread_name}] ✅ 找到 {len(items)} 個項目")
                
            except FileNotFoundError:
                error_msg = f"❌ 路徑不存在: {base_path}"
                self._update_progress(db_name, "DOWNLOADING_MANIFEST", error_msg)
                raise Exception(error_msg)
            except PermissionError:
                error_msg = f"🚫 權限被拒絕: {base_path}"
                self._update_progress(db_name, "DOWNLOADING_MANIFEST", error_msg)
                raise Exception(error_msg)
            except Exception as e:
                error_msg = f"❌ 訪問路徑失敗: {str(e)}"
                self._update_progress(db_name, "DOWNLOADING_MANIFEST", error_msg)
                raise Exception(error_msg)
            
            # Step 2: 快速解析並排序版本目錄
            self._update_progress(db_name, "DOWNLOADING_MANIFEST", f"🔍 解析版本目錄...")
            
            version_dirs = self._parse_and_sort_version_directories(items)
            
            if not version_dirs:
                all_dirs = [item.filename for item in items if item.st_mode & 0o40000]
                if all_dirs:
                    sample_dirs = all_dirs[:5]
                    error_msg = f"📂 找到 {len(all_dirs)} 個目錄但無法識別版本格式。樣本: {', '.join(sample_dirs)}"
                else:
                    error_msg = f"📂 路徑為空目錄"
                
                self._update_progress(db_name, "DOWNLOADING_MANIFEST", error_msg)
                raise Exception(error_msg)
            
            # Step 3: 只檢查最新的版本目錄（第一個）
            latest_version = version_dirs[0]  # 已經按版本號和時間排序，第一個就是最新的
            version_dir = latest_version['dir_name']
            version_num = latest_version['version_number'] or latest_version['version']
            version_path = f"{base_path}/{version_dir}"
            
            # 顯示版本狀態
            status_info = ""
            if latest_version.get('has_suffix'):
                status_info = f" (⚠️ {latest_version['suffix']})"
            
            self._update_progress(
                db_name, 
                "DOWNLOADING_MANIFEST", 
                f"🎯 檢查最新版本 {version_num}: {version_dir[:40]}...{status_info}"
            )
            
            self.logger.info(f"[{thread_name}] 🎯 檢查最新版本: {version_dir} (版本號: {version_num})")
            
            try:
                # 列出版本目錄中的檔案
                start_list = time.time()
                version_files = sftp.listdir(version_path)
                list_time = time.time() - start_list
                
                self._update_progress(
                    db_name, 
                    "DOWNLOADING_MANIFEST", 
                    f"🔍 最新版本包含 {len(version_files)} 個檔案 ({list_time:.1f}s)"
                )
                
                # 尋找最佳的 manifest 檔案
                manifest_candidates = []
                
                for filename in version_files:
                    if filename.endswith('.xml') and 'manifest' in filename.lower():
                        full_path = f"{version_path}/{filename}"
                        
                        try:
                            # 檢查檔案大小
                            file_stat = sftp.stat(full_path)
                            file_size = file_stat.st_size
                            
                            if file_size > 100000:  # 大於 100KB 才是有效的 manifest
                                manifest_candidates.append({
                                    'filename': filename,
                                    'path': full_path,
                                    'size': file_size,
                                    'priority': self._calculate_manifest_priority(filename, version_num)
                                })
                                
                                self.logger.info(f"[{thread_name}] 🎯 找到候選 manifest: {filename} ({file_size} bytes)")
                            
                        except Exception as e:
                            self.logger.debug(f"[{thread_name}] 檢查檔案失敗: {filename}, {e}")
                            continue
                
                # 選擇最佳的 manifest
                if manifest_candidates:
                    # 按優先級排序
                    manifest_candidates.sort(key=lambda x: x['priority'], reverse=True)
                    best_manifest = manifest_candidates[0]
                    
                    self._update_progress(
                        db_name, 
                        "DOWNLOADING_MANIFEST", 
                        f"🎯 選定: {best_manifest['filename']} ({best_manifest['size']//1024} KB)"
                    )
                    
                    self.logger.info(f"[{thread_name}] ✅ 選擇最佳 manifest: {best_manifest['filename']}")
                    return best_manifest['path'], best_manifest['filename']
                else:
                    error_msg = f"❌ 最新版本 {version_num} 中沒有有效的 manifest"
                    self._update_progress(db_name, "DOWNLOADING_MANIFEST", error_msg)
                    raise Exception(error_msg)
                    
            except FileNotFoundError:
                error_msg = f"🔍 版本目錄不存在: {version_path}"
                self._update_progress(db_name, "DOWNLOADING_MANIFEST", error_msg)
                raise Exception(error_msg)
            except PermissionError:
                error_msg = f"🔐 無權限訪問版本目錄: {version_path}"
                self._update_progress(db_name, "DOWNLOADING_MANIFEST", error_msg)
                raise Exception(error_msg)
            except Exception as e:
                error_msg = f"❌ 檢查版本目錄失敗: {str(e)}"
                self._update_progress(db_name, "DOWNLOADING_MANIFEST", error_msg)
                raise Exception(error_msg)
            
        except Exception as e:
            # 最終錯誤處理
            final_error = str(e)
            if not any(prefix in final_error for prefix in ["❌", "🚫", "🔍", "🔐", "⏰", "📂", "📋", "🔌", "❓"]):
                final_error = f"❓ 未預期的錯誤: {final_error}"
            
            self._update_progress(db_name, "DOWNLOADING_MANIFEST", final_error)
            self.logger.error(f"[{thread_name}] ❌ 搜索失敗: {final_error}")
            return None
    
    def find_specific_manifest(self, base_path: str, version: str) -> Optional[Tuple[str, str]]:
        """尋找特定版本的 manifest 文件"""
        thread_name = threading.current_thread().name
        
        try:
            sftp, client = self._get_connection()
            if not sftp:
                raise Exception("無法建立 SFTP 連線")
            
            self.logger.info(f"[{thread_name}] 尋找版本 {version} 的 manifest: {base_path}")
            
            # 嘗試直接在版本目錄中尋找
            version_patterns = [
                f"{version}_all_*",
                f"{version}_*",
                version,
                f"v{version}",
                f"version_{version}"
            ]
            
            items = sftp.listdir_attr(base_path)
            
            for item in items:
                if item.st_mode & 0o40000:  # 是目錄
                    # 檢查是否符合版本模式
                    extracted_version = self._extract_version_number_flexible(item.filename)
                    if extracted_version == version:
                        version_path = f"{base_path}/{item.filename}"
                        
                        try:
                            # 在版本目錄中尋找 manifest
                            version_files = sftp.listdir(version_path)
                            
                            for filename in version_files:
                                if filename.endswith('.xml') and 'manifest' in filename.lower():
                                    full_path = f"{version_path}/{filename}"
                                    
                                    # 檢查文件大小
                                    file_stat = sftp.stat(full_path)
                                    if file_stat.st_size > 100000:  # 大於 100KB
                                        self.logger.info(f"[{thread_name}] 找到指定版本的 manifest: {filename}")
                                        return full_path, filename
                        
                        except Exception as e:
                            self.logger.debug(f"[{thread_name}] 檢查版本目錄失敗: {item.filename}, {e}")
                            continue
            
            raise Exception(f"未找到版本 {version} 的 manifest")
            
        except Exception as e:
            self.logger.error(f"[{thread_name}] 尋找特定版本 manifest 失敗: {e}")
            return None
    
    def download_file_with_progress(self, remote_file: str, local_file: str, db_name: str = None) -> bool:
        """下載檔案並顯示進度"""
        thread_name = threading.current_thread().name
        
        try:
            sftp, client = self._get_connection()
            if not sftp:
                return False
            
            os.makedirs(os.path.dirname(local_file), exist_ok=True)
            filename = os.path.basename(remote_file)
            
            # 獲取檔案大小
            try:
                file_stat = sftp.stat(remote_file)
                file_size = file_stat.st_size
                file_size_mb = file_size / (1024 * 1024)
                
                self._update_progress(
                    db_name, 
                    "DOWNLOADING_MANIFEST", 
                    f"⬇️ 開始下載: {filename} ({file_size_mb:.1f} MB)"
                )
            except:
                file_size = 0
                self._update_progress(
                    db_name, 
                    "DOWNLOADING_MANIFEST", 
                    f"⬇️ 開始下載: {filename}"
                )
            
            self.logger.info(f"[{thread_name}] ⬇️ 下載: {filename}")
            
            # 開始下載
            start_download = time.time()
            
            # 使用回調函數顯示下載進度（如果檔案較大）
            if file_size > 1024 * 1024:  # 大於 1MB 的檔案顯示進度
                downloaded = 0
                last_update = 0
                
                def progress_callback(transferred, total):
                    nonlocal downloaded, last_update
                    downloaded = transferred
                    current_time = time.time()
                    
                    # 每 2 秒更新一次進度，避免過於頻繁
                    if current_time - last_update >= 2.0:
                        if total > 0:
                            progress_percent = (transferred / total) * 100
                            elapsed = current_time - start_download
                            speed_mbps = (transferred / (1024 * 1024)) / max(elapsed, 0.1)
                            
                            self._update_progress(
                                db_name, 
                                "DOWNLOADING_MANIFEST", 
                                f"⬇️ {filename}: {progress_percent:.1f}% ({speed_mbps:.1f} MB/s)"
                            )
                        last_update = current_time
                
                # 註：paramiko 的 get 方法支援 callback 參數
                try:
                    sftp.get(remote_file, local_file, callback=progress_callback)
                except TypeError:
                    # 如果不支援 callback，使用普通下載
                    sftp.get(remote_file, local_file)
            else:
                # 小檔案直接下載
                sftp.get(remote_file, local_file)
            
            download_time = time.time() - start_download
            
            # 驗證下載的檔案
            if os.path.exists(local_file) and os.path.getsize(local_file) > 0:
                actual_size = os.path.getsize(local_file)
                speed_mbps = (actual_size / (1024 * 1024)) / max(download_time, 0.1)
                
                self._update_progress(
                    db_name, 
                    "DOWNLOADING_MANIFEST", 
                    f"✅ 下載完成: {filename} ({actual_size//1024} KB, {speed_mbps:.1f} MB/s)"
                )
                
                self.logger.info(f"[{thread_name}] ✅ 下載完成: {filename} ({download_time:.1f}s)")
                return True
            else:
                self._update_progress(
                    db_name, 
                    "DOWNLOADING_MANIFEST", 
                    f"❌ 下載失敗: {filename} (檔案無效)"
                )
                self.logger.error(f"[{thread_name}] 下載的檔案無效或為空")
                return False
                
        except Exception as e:
            self._update_progress(
                db_name, 
                "DOWNLOADING_MANIFEST", 
                f"❌ 下載失敗: {os.path.basename(remote_file)} - {str(e)[:30]}..."
            )
            self.logger.error(f"[{thread_name}] 下載失敗: {str(e)}")
            return False
    
    def detect_version_directory_patterns(self, base_path: str, db_name: str = None) -> Dict[str, List[str]]:
        """檢測目錄中的版本目錄命名模式"""
        try:
            sftp, client = self._get_connection()
            if not sftp:
                return {}
            
            items = sftp.listdir_attr(base_path)
            patterns = {
                'version_all_timestamp': [],         # 206_all_202507100000
                'version_all_timestamp_suffix': [],  # 465_all_202502170030_NG_uboot_fail
                'version_timestamp': [],             # 204_202507081101
                'version_timestamp_suffix': [],      # 466_202502171018_NG_uboot_fail
                'simple_number': [],                 # 206, 204
                'v_number': [],                      # v206, v204
                'unknown': []                        # 其他格式
            }
            
            for item in items:
                if item.st_mode & 0o40000:  # 是目錄
                    dir_name = item.filename
                    
                    if re.match(r'^\d+_all_\d{12}_.*$', dir_name):
                        patterns['version_all_timestamp_suffix'].append(dir_name)
                    elif re.match(r'^\d+_all_\d{12}$', dir_name):
                        patterns['version_all_timestamp'].append(dir_name)
                    elif re.match(r'^\d+_\d{12}_.*$', dir_name):
                        patterns['version_timestamp_suffix'].append(dir_name)
                    elif re.match(r'^\d+_\d{12}$', dir_name):
                        patterns['version_timestamp'].append(dir_name)
                    elif re.match(r'^\d+$', dir_name):
                        patterns['simple_number'].append(dir_name)
                    elif re.match(r'^v\d+$', dir_name):
                        patterns['v_number'].append(dir_name)
                    elif any(char.isdigit() for char in dir_name):
                        patterns['unknown'].append(dir_name)
            
            # 只返回有內容的模式
            return {k: v for k, v in patterns.items() if v}
            
        except Exception as e:
            self.logger.error(f"檢測版本目錄模式失敗: {e}")
            return {}

# =====================================
# ===== Repo 管理器（改善並發安全） =====
# =====================================

class RepoSyncProgress:
    """Repo sync 進度解析器（增強版 - 包含磁碟空間錯誤檢測）"""
    
    def parse_sync_log(self, log_file: str) -> Dict[str, Any]:
        """解析 repo sync 日誌，提取進度信息（增強版）"""
        if not os.path.exists(log_file):
            return self._default_progress()
        
        try:
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            if not lines:
                return self._default_progress()
            
            # 解析最後 100 行
            recent_lines = lines[-100:] if len(lines) > 100 else lines
            
            progress_info = {
                'status': 'syncing',
                'overall_progress': '0%',
                'current_projects': 0,
                'total_projects': 0,
                'current_repo': '',
                'last_activity': '',
                'speed': '',
                'errors': [],
                'error_type': '',
                'disk_space_error': False  # 新增：磁碟空間錯誤標記
            }
            
            for line in recent_lines:
                line = line.strip()
                if not line:
                    continue
                
                # 解析整體進度
                progress_match = re.search(r'Fetching projects:\s*(\d+)%\s*\((\d+)/(\d+)\)', line)
                if progress_match:
                    progress_info['overall_progress'] = f"{progress_match.group(1)}%"
                    progress_info['current_projects'] = int(progress_match.group(2))
                    progress_info['total_projects'] = int(progress_match.group(3))
                    continue
                
                # 解析當前處理的 repository
                repo_patterns = [
                    r'Fetching project (.+)',
                    r'Fetching (.+?)\.\.\.', 
                    r'remote: Counting objects.*?(\S+)',
                    r'Receiving objects.*?(\S+)'
                ]
                
                for pattern in repo_patterns:
                    repo_match = re.search(pattern, line)
                    if repo_match:
                        progress_info['current_repo'] = repo_match.group(1).strip()
                        break
                
                # 解析下載速度
                speed_patterns = [
                    r'(\d+(?:\.\d+)?\s*[KM]B/s)',
                    r'(\d+(?:\.\d+)?\s*[KM]iB/s)'
                ]
                
                for pattern in speed_patterns:
                    speed_match = re.search(pattern, line)
                    if speed_match:
                        progress_info['speed'] = speed_match.group(1)
                        break
                
                # 檢查完成狀態
                completion_keywords = ['repo sync has finished', 'sync completed', 'success']
                if any(keyword in line.lower() for keyword in completion_keywords):
                    progress_info['status'] = 'completed'
                    progress_info['overall_progress'] = '100%'
                    continue
                
                # 檢查錯誤並分析類型
                error_keywords = ['error', 'failed', 'fatal', 'cannot']
                if any(keyword in line.lower() for keyword in error_keywords):
                    if len(progress_info['errors']) < 3:
                        progress_info['errors'].append(line[:120])
                    
                    line_lower = line.lower()
                    
                    # 磁碟空間相關錯誤
                    disk_keywords = ['no space left', 'disk full', 'out of space', 'enospc']
                    if any(keyword in line_lower for keyword in disk_keywords):
                        progress_info['error_type'] = 'disk_space_error'
                        progress_info['disk_space_error'] = True
                        progress_info['status'] = 'failed'
                        
                        # 在 console 顯示磁碟空間錯誤
                        print("\n" + "🚨" * 50)
                        print("⚠️  檢測到磁碟空間不足錯誤！")
                        print("🚨" * 50)
                        print(f"錯誤詳情: {line[:100]}")
                        print("💡 請立即清理磁碟空間後重新執行")
                        print("🚨" * 50 + "\n")
                        
                    # 其他錯誤類型
                    elif 'cannot checkout' in line_lower:
                        progress_info['error_type'] = 'checkout_error'
                        progress_info['status'] = 'failed'
                    elif 'cannot initialize' in line_lower:
                        progress_info['error_type'] = 'init_error'
                        progress_info['status'] = 'failed'
                    elif any(net_keyword in line_lower for net_keyword in ['network', 'connection', 'timeout', 'unreachable']):
                        progress_info['error_type'] = 'network_error'
                    elif 'permission' in line_lower:
                        progress_info['error_type'] = 'permission_error'
                        progress_info['status'] = 'failed'
                
                # 更新最後活動時間
                time_patterns = [
                    r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})',
                    r'(\d{2}:\d{2}:\d{2})'
                ]
                
                for pattern in time_patterns:
                    time_match = re.search(pattern, line)
                    if time_match:
                        progress_info['last_activity'] = time_match.group(1)
                        break
            
            return progress_info
            
        except Exception as e:
            self.logger.error(f"解析 sync 日誌失敗: {e}")
            return self._default_progress()
 
class RepoManager:
    """Repo 指令管理器（完整版）"""
    
    def __init__(self):
        self.logger = setup_logger(self.__class__.__name__)
        self.lock = threading.Lock()
        self.source_cmd_manager = SourceCommandManager()
    
    def check_repo_exists(self, work_dir: str) -> bool:
        """檢查 .repo 目錄是否存在"""
        repo_dir = os.path.join(work_dir, '.repo')
        exists = os.path.exists(repo_dir)
        self.logger.info(f"檢查 .repo 是否存在於 {work_dir}: {exists}")
        return exists
    
    def run_command(self, cmd: str, cwd: str = None, timeout: int = None) -> Tuple[bool, str]:
        """同步執行指令"""
        try:
            self.logger.debug(f"執行: {cmd}")
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
            return False, "Command timeout"
        except Exception as e:
            return False, str(e)
    
    def repo_init(self, work_dir: str, init_cmd: str) -> bool:
        """執行 repo init"""
        # 清理可能存在的舊 .repo 目錄
        repo_dir = os.path.join(work_dir, '.repo')
        if os.path.exists(repo_dir):
            self.logger.info(f"清理舊的 .repo 目錄: {repo_dir}")
            import shutil
            try:
                shutil.rmtree(repo_dir)
            except Exception as e:
                self.logger.warning(f"清理 .repo 失敗: {e}")
        
        success, output = self.run_command(
            init_cmd,
            cwd=work_dir,
            timeout=config_manager.repo_config['init_timeout']
        )
        
        if success:
            self.logger.info(f"Repo init 成功: {work_dir}")
        else:
            self.logger.error(f"Repo init 失敗: {output}")
        
        return success
    
    def apply_manifest(self, work_dir: str, manifest_file: str) -> bool:
        """
        應用 manifest 檔案（改善版 - 處理版本切換和清理問題）
        """
        try:
            manifest_name = os.path.basename(manifest_file)
            self.logger.info(f"準備應用 manifest: {manifest_name}")
            
            # 1. 檢查 .repo 目錄狀態
            repo_dir = os.path.join(work_dir, '.repo')
            manifests_dir = os.path.join(repo_dir, 'manifests')
            
            if not os.path.exists(manifests_dir):
                self.logger.error(f"Manifests 目錄不存在: {manifests_dir}")
                return False
            
            # 2. 清理可能的殘留狀態（重要：處理本地修改和衝突）
            if not self._cleanup_repo_state(work_dir):
                self.logger.warning("清理 repo 狀態時遇到問題，但繼續處理")
            
            # 3. 複製新的 manifest 文件
            dest_file = os.path.join(manifests_dir, manifest_name)
            
            # 如果目標文件已存在且內容相同，跳過複製
            if os.path.exists(dest_file):
                if self._compare_files(manifest_file, dest_file):
                    self.logger.info(f"Manifest 文件已存在且相同: {manifest_name}")
                else:
                    self.logger.info(f"更新 manifest 文件: {manifest_name}")
                    import shutil
                    shutil.copy2(manifest_file, dest_file)
            else:
                import shutil
                shutil.copy2(manifest_file, dest_file)
                self.logger.info(f"複製 manifest: {manifest_file} -> {dest_file}")
            
            # 4. 檢查並處理 repo 版本兼容性
            if not self._check_repo_compatibility(work_dir, manifest_name):
                self.logger.warning("Repo 版本可能過舊，嘗試更新...")
                self._update_repo_metadata(work_dir)
            
            # 5. 切換到指定的 manifest
            success = self._switch_to_manifest(work_dir, manifest_name)
            
            if success:
                self.logger.info(f"成功切換到 manifest: {manifest_name}")
                
                # 6. 驗證切換結果
                if self._verify_manifest_switch(work_dir, manifest_name):
                    return True
                else:
                    self.logger.error("Manifest 切換驗證失敗")
                    return False
            else:
                self.logger.error(f"切換 manifest 失敗")
                return False
                
        except Exception as e:
            self.logger.error(f"應用 manifest 失敗: {str(e)}")
            return False
    
    def _cleanup_repo_state(self, work_dir: str) -> bool:
        """
        清理 repo 狀態 - 處理殘留 diff 和本地修改
        """
        try:
            self.logger.info("清理 repo 狀態中...")
            
            # 1. 重置所有本地修改（處理殘留 diff）
            reset_cmd = "repo forall -c 'git reset --hard HEAD 2>/dev/null || true'"
            success, output = self.run_command(reset_cmd, cwd=work_dir, timeout=120)
            if not success:
                self.logger.warning(f"重置本地修改警告: {output}")
            
            # 2. 清理未追蹤的文件
            clean_cmd = "repo forall -c 'git clean -fd 2>/dev/null || true'"
            success, output = self.run_command(clean_cmd, cwd=work_dir, timeout=120)
            if not success:
                self.logger.warning(f"清理未追蹤文件警告: {output}")
            
            # 3. 清理可能損壞的 git 狀態
            stash_cmd = "repo forall -c 'git stash clear 2>/dev/null || true'"
            self.run_command(stash_cmd, cwd=work_dir, timeout=60)
            
            # 4. 檢查並清理損壞的 .repo/project-objects
            project_objects_dir = os.path.join(work_dir, '.repo', 'project-objects')
            if os.path.exists(project_objects_dir):
                # 檢查是否有損壞的物件
                self._check_and_repair_git_objects(project_objects_dir)
            
            self.logger.info("Repo 狀態清理完成")
            return True
            
        except Exception as e:
            self.logger.error(f"清理 repo 狀態失敗: {e}")
            return False
    
    def _check_repo_compatibility(self, work_dir: str, manifest_name: str) -> bool:
        """
        檢查 repo 版本兼容性（處理本地 repo 太舊的問題）
        """
        try:
            # 1. 檢查 repo 版本
            version_cmd = f"{config_manager.repo_config['repo_command']} version"
            success, output = self.run_command(version_cmd, cwd=work_dir, timeout=30)
            
            if success:
                self.logger.debug(f"Repo 版本信息: {output}")
                
                # 檢查是否為舊版本（簡單檢查）
                if "repo launcher version" in output.lower():
                    version_line = [line for line in output.split('\n') if 'repo launcher version' in line.lower()]
                    if version_line:
                        self.logger.info(f"當前 repo 版本: {version_line[0]}")
            
            # 2. 檢查 .repo/repo 目錄的狀態
            repo_repo_dir = os.path.join(work_dir, '.repo', 'repo')
            if os.path.exists(repo_repo_dir):
                # 檢查 repo 工具是否太舊
                repo_git_cmd = "git log --oneline -1"
                success, output = self.run_command(repo_git_cmd, cwd=repo_repo_dir, timeout=30)
                if success:
                    self.logger.debug(f"Repo 工具最新提交: {output}")
                else:
                    self.logger.warning("無法獲取 repo 工具版本信息")
                    return False
            
            # 3. 檢查 manifests 目錄的 git 狀態
            manifests_dir = os.path.join(work_dir, '.repo', 'manifests')
            if os.path.exists(manifests_dir):
                status_cmd = "git status --porcelain"
                success, output = self.run_command(status_cmd, cwd=manifests_dir, timeout=30)
                if success and output.strip():
                    self.logger.warning(f"Manifests 目錄有未提交的修改: {output}")
                    # 清理 manifests 目錄的修改
                    self.run_command("git reset --hard HEAD", cwd=manifests_dir, timeout=30)
                    self.run_command("git clean -fd", cwd=manifests_dir, timeout=30)
            
            return True
            
        except Exception as e:
            self.logger.warning(f"檢查 repo 兼容性失敗: {e}")
            return False
    
    def _update_repo_metadata(self, work_dir: str) -> bool:
        """
        更新 repo 元數據（處理舊版本問題）
        """
        try:
            self.logger.info("更新 repo 元數據...")
            
            # 1. 更新 repo 工具本身
            repo_sync_cmd = f"{config_manager.repo_config['repo_command']} selfupdate"
            success, output = self.run_command(repo_sync_cmd, cwd=work_dir, timeout=120)
            
            if success:
                self.logger.info("Repo 工具更新成功")
            else:
                self.logger.warning(f"Repo 工具更新失敗，但繼續處理: {output}")
            
            # 2. 同步 manifests 倉庫
            manifests_dir = os.path.join(work_dir, '.repo', 'manifests')
            if os.path.exists(manifests_dir):
                fetch_cmd = "git fetch origin"
                success, output = self.run_command(fetch_cmd, cwd=manifests_dir, timeout=120)
                if success:
                    self.logger.info("Manifests 倉庫更新成功")
                else:
                    self.logger.warning(f"Manifests 倉庫更新失敗: {output}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"更新 repo 元數據失敗: {e}")
            return False
    
    def _switch_to_manifest(self, work_dir: str, manifest_name: str) -> bool:
        """
        切換到指定的 manifest（改進版本）
        """
        try:
            # 1. 首先嘗試簡單的切換
            simple_cmd = f"{config_manager.repo_config['repo_command']} init -m {manifest_name}"
            success, output = self.run_command(
                simple_cmd,
                cwd=work_dir,
                timeout=config_manager.repo_config['init_timeout']
            )
            
            if success:
                self.logger.info(f"簡單切換成功: {manifest_name}")
                return True
            
            # 2. 如果簡單切換失敗，嘗試更完整的方法
            self.logger.warning(f"簡單切換失敗，嘗試完整重新初始化: {output}")
            
            # 獲取原始的 repo init 參數
            repo_dir = os.path.join(work_dir, '.repo')
            manifest_xml = os.path.join(repo_dir, 'manifest.xml')
            
            if os.path.exists(manifest_xml):
                # 讀取當前的 repo 配置
                manifest_repo_dir = os.path.join(repo_dir, 'manifests')
                if os.path.exists(manifest_repo_dir):
                    # 獲取 remote URL
                    remote_cmd = "git remote get-url origin"
                    success, remote_url = self.run_command(remote_cmd, cwd=manifest_repo_dir, timeout=30)
                    
                    if success and remote_url.strip():
                        # 獲取當前分支
                        branch_cmd = "git rev-parse --abbrev-ref HEAD"
                        success, branch = self.run_command(branch_cmd, cwd=manifest_repo_dir, timeout=30)
                        
                        if success and branch.strip():
                            # 重新初始化
                            full_cmd = f"{config_manager.repo_config['repo_command']} init -u {remote_url.strip()} -b {branch.strip()} -m {manifest_name}"
                            success, output = self.run_command(
                                full_cmd,
                                cwd=work_dir,
                                timeout=config_manager.repo_config['init_timeout']
                            )
                            
                            if success:
                                self.logger.info(f"完整重新初始化成功: {manifest_name}")
                                return True
                            else:
                                self.logger.error(f"完整重新初始化失敗: {full_cmd}")
            
            return False
            
        except Exception as e:
            self.logger.error(f"切換 manifest 失敗: {e}")
            return False
    
    def _verify_manifest_switch(self, work_dir: str, expected_manifest: str) -> bool:
        """
        驗證 manifest 切換是否成功
        """
        try:
            # 檢查當前使用的 manifest
            manifest_link = os.path.join(work_dir, '.repo', 'manifest.xml')
            
            if os.path.islink(manifest_link):
                # 如果是符號連結，檢查指向的文件
                target = os.readlink(manifest_link)
                if expected_manifest in target:
                    self.logger.info(f"Manifest 切換驗證成功: {target}")
                    return True
                else:
                    self.logger.error(f"Manifest 切換驗證失敗: 期望 {expected_manifest}, 實際 {target}")
                    return False
            elif os.path.exists(manifest_link):
                # 如果是實際文件，檢查內容或文件名
                self.logger.info("Manifest 文件存在，切換可能成功")
                return True
            else:
                self.logger.error("Manifest 文件不存在")
                return False
            
        except Exception as e:
            self.logger.warning(f"驗證 manifest 切換失敗: {e}")
            return True  # 驗證失敗時假設成功，讓後續流程繼續
    
    def _check_and_repair_git_objects(self, objects_dir: str):
        """
        檢查並修復損壞的 git 物件
        """
        try:
            # 簡單檢查：遍歷所有 .git 目錄並運行 git fsck
            for root, dirs, files in os.walk(objects_dir):
                if '.git' in dirs:
                    git_dir = os.path.join(root, '.git')
                    parent_dir = root
                    
                    # 運行 git fsck 檢查
                    fsck_cmd = "git fsck --full 2>/dev/null || true"
                    self.run_command(fsck_cmd, cwd=parent_dir, timeout=60)
                    
                    # 如果有問題，嘗試修復
                    gc_cmd = "git gc --aggressive 2>/dev/null || true"
                    self.run_command(gc_cmd, cwd=parent_dir, timeout=120)
                    
        except Exception as e:
            self.logger.warning(f"檢查 git 物件時發生錯誤: {e}")
    
    def _compare_files(self, file1: str, file2: str) -> bool:
        """
        比較兩個文件是否相同
        """
        try:
            import filecmp
            return filecmp.cmp(file1, file2, shallow=False)
        except Exception:
            return False
    
    def start_repo_sync_async(self, work_dir: str, db_name: str, force_sync: bool = False) -> subprocess.Popen:
        """啟動異步 repo sync（基礎版）"""
        try:
            # 構建 sync 命令
            sync_cmd_parts = [
                config_manager.repo_config['repo_command'],
                'sync'
            ]
            
            # 並行數
            sync_cmd_parts.extend(['-j', str(config_manager.repo_config['sync_jobs'])])
            
            # 重試次數
            if config_manager.repo_config['sync_retry'] > 0:
                sync_cmd_parts.extend(['--retry-fetches', str(config_manager.repo_config['sync_retry'])])
            
            # 如果是修復模式，加入更強力的參數
            if force_sync:
                sync_cmd_parts.extend([
                    '--force-sync',      # 強制同步
                    '--force-remove-dirty',  # 強制移除髒數據
                    '--no-clone-bundle'  # 不使用 clone bundle（有時會有問題）
                ])
                self.logger.info(f"{db_name} 使用強制同步模式")
            
            cmd = ' '.join(sync_cmd_parts)
            
            self.logger.info(f"{db_name} 啟動異步命令: {cmd}")
            
            # 建立日誌檔案
            log_dir = os.path.join(work_dir, 'logs')
            os.makedirs(log_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            retry_suffix = "_retry" if force_sync else ""
            log_file = os.path.join(log_dir, f'repo_sync_{timestamp}{retry_suffix}.log')
            
            with open(log_file, 'w') as f:
                f.write(f"開始時間: {datetime.now()}\n")
                f.write(f"命令: {cmd}\n")
                f.write(f"工作目錄: {work_dir}\n")
                f.write("="*50 + "\n")
                f.flush()
                
                process = subprocess.Popen(
                    cmd,
                    shell=True,
                    cwd=work_dir,
                    stdout=f,
                    stderr=subprocess.STDOUT,
                    text=True
                )
            
            # 註冊到資源管理器
            resource_manager.register_process(db_name, process)
            
            self.logger.info(f"{db_name} 異步進程已啟動 (PID: {process.pid}), 日誌: {log_file}")
            return process
            
        except Exception as e:
            self.logger.error(f"{db_name} 啟動異步指令失敗: {str(e)}")
            return None
    
    def start_repo_sync_async_with_retry(self, work_dir: str, db_name: str, max_retries: int = 3) -> subprocess.Popen:
        """啟動異步 repo sync 並包含重試機制（增強版）"""
        try:
            # 首先檢查磁碟空間
            if not self._check_disk_space_with_alert(work_dir, db_name, min_gb=15.0):
                self.logger.error(f"{db_name} 因磁碟空間不足而停止")
                return None
            
            # 第一次嘗試正常 sync
            process = self.start_repo_sync_async(work_dir, db_name)
            if process:
                return process
            
            # 如果第一次失敗，嘗試修復後重新 sync
            print(f"⚠️  {db_name} 初始 sync 失敗，嘗試修復...")
            self.logger.warning(f"{db_name} 初始 sync 失敗，嘗試修復...")
            
            for retry in range(max_retries):
                print(f"🔄 {db_name} 重試 sync (第 {retry + 1}/{max_retries} 次)")
                self.logger.info(f"{db_name} 重試 sync (第 {retry + 1}/{max_retries} 次)")
                
                # 再次檢查磁碟空間
                if not self._check_disk_space_with_alert(work_dir, db_name, min_gb=10.0):
                    print(f"❌ {db_name} 重試失敗：磁碟空間不足")
                    return None
                
                # 嘗試修復
                if self._repair_repo(work_dir, db_name):
                    # 修復成功後重新 sync
                    process = self.start_repo_sync_async(work_dir, db_name, force_sync=True)
                    if process:
                        print(f"✅ {db_name} 重試成功，繼續同步...")
                        return process
                
                time.sleep(5 * (retry + 1))  # 逐漸增加延遲
            
            print(f"❌ {db_name} 所有重試都失敗")
            self.logger.error(f"{db_name} 所有重試都失敗")
            return None
            
        except Exception as e:
            print(f"❌ {db_name} sync 重試機制失敗: {e}")
            self.logger.error(f"{db_name} sync 重試機制失敗: {e}")
            return None
    
    def check_process_status(self, db_name: str, process: subprocess.Popen) -> Optional[int]:
        """檢查進程狀態（線程安全）"""
        with self.lock:
            if process:
                poll = process.poll()
                if poll is not None:
                    # 進程已結束，從資源管理器移除
                    resource_manager.unregister_process(db_name)
                return poll
        return None
    
    def export_manifest(self, work_dir: str, output_file: str = "vp_manifest.xml") -> bool:
        """導出 manifest"""
        cmd = f"{config_manager.repo_config['repo_command']} manifest -r -o {output_file}"
        success, output = self.run_command(cmd, cwd=work_dir, timeout=60)
        
        if success:
            output_path = os.path.join(work_dir, output_file)
            if os.path.exists(output_path):
                self.logger.info(f"成功導出 manifest: {output_path}")
                return True
            else:
                self.logger.error(f"導出的 manifest 檔案不存在")
                return False
        else:
            self.logger.error(f"導出 manifest 失敗: {output}")
            return False
    
    def _check_disk_space_with_alert(self, path: str, db_name: str, min_gb: float = 10.0) -> bool:
        """檢查磁碟空間並在 console 顯示警告"""
        try:
            import shutil
            total, used, free = shutil.disk_usage(path)
            free_gb = free / (1024**3)
            total_gb = total / (1024**3)
            used_gb = used / (1024**3)
            
            self.logger.info(f"{db_name} 磁碟空間檢查:")
            self.logger.info(f"  總空間: {total_gb:.2f} GB")
            self.logger.info(f"  已使用: {used_gb:.2f} GB")
            self.logger.info(f"  可用空間: {free_gb:.2f} GB")
            
            if free_gb < min_gb:
                # 在 console 顯示醒目的警告
                print("\n" + "🚨" * 50)
                print("⚠️  磁碟空間不足警告！")
                print("🚨" * 50)
                print(f"📁 路徑: {path}")
                print(f"💾 可用空間: {free_gb:.2f} GB")
                print(f"📋 需要空間: {min_gb} GB")
                print(f"❌ 不足: {min_gb - free_gb:.2f} GB")
                print()
                print("💡 建議解決方案:")
                print("   1. 清理不需要的檔案")
                print("   2. 移動其他大檔案到別處")
                print("   3. 使用 'du -sh * | sort -hr' 查看大檔案")
                print("   4. 考慮使用外接硬碟或更大的磁碟")
                print("🚨" * 50)
                print()
                
                self.logger.error(f"{db_name} 磁碟空間不足：需要 {min_gb} GB，只有 {free_gb:.2f} GB")
                return False
            
            # 如果空間充足但接近警告線（< 20GB），給予提醒
            elif free_gb < 20.0:
                print(f"⚠️  {db_name} 磁碟空間警告：剩餘 {free_gb:.2f} GB （建議保持 20GB 以上）")
                self.logger.warning(f"{db_name} 磁碟空間偏低: {free_gb:.2f} GB")
            
            return True
            
        except Exception as e:
            self.logger.warning(f"{db_name} 檢查磁碟空間失敗: {e}")
            return True  # 檢查失敗時假設空間足夠 
    
    def _repair_repo(self, work_dir: str, db_name: str) -> bool:
        """嘗試修復損壞的 repo（增強版）"""
        try:
            print(f"🔧 {db_name} 開始修復 repo...")
            self.logger.info(f"{db_name} 開始修復 repo...")
            
            # 1. 再次檢查磁碟空間
            if not self._check_disk_space_with_alert(work_dir, db_name, min_gb=5.0):
                return False
            
            # 2. 清理可能損壞的檔案
            cleanup_paths = [
                os.path.join(work_dir, '.repo', 'project-objects'),
                os.path.join(work_dir, '.repo', 'projects'),
            ]
            
            for cleanup_path in cleanup_paths:
                if os.path.exists(cleanup_path):
                    print(f"🗑️  {db_name} 清理 {os.path.basename(cleanup_path)}...")
                    self.logger.info(f"{db_name} 清理 {cleanup_path}...")
                    import shutil
                    try:
                        shutil.rmtree(cleanup_path)
                        print(f"✅ {db_name} {os.path.basename(cleanup_path)} 清理完成")
                    except Exception as e:
                        print(f"⚠️  {db_name} 清理 {os.path.basename(cleanup_path)} 失敗: {e}")
                        self.logger.warning(f"{db_name} 清理 {cleanup_path} 失敗: {e}")
            
            # 3. 執行 repo forall 清理
            print(f"🧹 {db_name} 執行 Git 清理...")
            cleanup_cmd = "repo forall -c 'git reset --hard HEAD; git clean -fd' 2>/dev/null || true"
            self.logger.info(f"{db_name} 執行清理命令...")
            
            result = subprocess.run(
                cleanup_cmd,
                shell=True,
                cwd=work_dir,
                capture_output=True,
                text=True,
                timeout=300  # 5分鐘超時
            )
            
            if result.returncode == 0:
                print(f"✅ {db_name} repo 清理成功")
                self.logger.info(f"{db_name} repo 清理成功")
                return True
            else:
                print(f"⚠️  {db_name} repo 清理有警告，但繼續嘗試")
                self.logger.warning(f"{db_name} repo 清理警告: {result.stderr}")
                return True  # 即使有警告也繼續
                
        except subprocess.TimeoutExpired:
            print(f"❌ {db_name} repo 清理超時")
            self.logger.error(f"{db_name} repo 清理超時")
            return False
        except Exception as e:
            print(f"❌ {db_name} repo 修復失敗: {e}")
            self.logger.error(f"{db_name} repo 修復失敗: {e}")
            return False

# =====================================
# ===== 主要處理類別（改善版） =====
# =====================================

class ManifestPinningTool:
    """Manifest 定版工具（改善版）"""

    def __init__(self):
        self.logger = setup_logger(self.__class__.__name__)
        self.sftp_manager = ThreadSafeSFTPManager()
        self.repo_manager = RepoManager()
        self.mapping_reader = MappingTableReader()
        self.progress_manager = ProgressManager()  # 確保這行存在
        self.source_cmd_manager = SourceCommandManager()
        self.report = PinningReport()
        self.output_dir = config_manager.path_config['default_output_dir']
        self.dry_run = False

    def process_db_phase1(self, db_info: DBInfo) -> DBInfo:
        """處理 DB 的第一階段：準備工作（詳細進度版）"""
        db_info.start_time = datetime.now()
        
        try:
            # 設置 SFTP 管理器的進度回調
            def progress_callback(db_name, status, message):
                if hasattr(DBStatus, status):
                    status_enum = getattr(DBStatus, status)
                    self.progress_manager.update_status(db_name, status_enum, message)
            
            self.sftp_manager.set_progress_callback(progress_callback)
            
            # 初始狀態顯示 SFTP 路徑
            self.progress_manager.update_status(
                db_info.db_info, 
                DBStatus.DOWNLOADING_MANIFEST,
                f"🔍 準備搜尋: {os.path.basename(db_info.sftp_path)}"
            )
            
            # 建立本地目錄
            local_path = os.path.join(self.output_dir, db_info.module, db_info.db_info)
            os.makedirs(local_path, exist_ok=True)
            db_info.local_path = local_path
            
            # Step 1: 從 SFTP 尋找並下載 manifest
            start_search = time.time()
            
            if db_info.version:
                self.progress_manager.update_status(
                    db_info.db_info,
                    DBStatus.DOWNLOADING_MANIFEST,
                    f"🎯 尋找指定版本 {db_info.version}"
                )
                result = self.sftp_manager.find_specific_manifest(db_info.sftp_path, db_info.version)
            else:
                result = self.sftp_manager.find_latest_manifest(db_info.sftp_path, db_info.db_info)
            
            search_time = time.time() - start_search
            
            if not result:
                raise Exception(f"在 {db_info.sftp_path} 找不到 manifest 檔案 (搜尋時間: {search_time:.1f}s)")
            
            manifest_full_path, manifest_name = result
            db_info.manifest_full_path = manifest_full_path
            db_info.manifest_file = manifest_name
            
            # 提取版本號
            match = re.match(config_manager.path_config['manifest_pattern'], manifest_name)
            if match:
                db_info.version = match.group(1)
            
            # 下載 manifest 到本地
            local_manifest = os.path.join(local_path, manifest_name)
            
            if not self.sftp_manager.download_file_with_progress(
                manifest_full_path, 
                local_manifest, 
                db_info.db_info
            ):
                raise Exception(f"下載 manifest 失敗: {manifest_full_path}")
            
            download_time = time.time() - start_search
            file_size = os.path.getsize(local_manifest) if os.path.exists(local_manifest) else 0
            
            # 下載完成後更新狀態
            self.progress_manager.update_status(
                db_info.db_info,
                DBStatus.DOWNLOADING_MANIFEST,
                f"✅ {manifest_name} (v{db_info.version or '最新'}, {file_size//1024} KB, {download_time:.1f}s)"
            )
            
            # Step 2: 檢查是否已有 .repo
            self.progress_manager.update_status(
                db_info.db_info,
                DBStatus.CHECKING_REPO,
                f"🔍 檢查 {local_path}/.repo"
            )
            
            db_info.has_existing_repo = self.repo_manager.check_repo_exists(local_path)
            
            if db_info.has_existing_repo:
                self.progress_manager.update_status(
                    db_info.db_info,
                    DBStatus.CHECKING_REPO,
                    f"✅ 找到現有 .repo 目錄"
                )
            else:
                self.progress_manager.update_status(
                    db_info.db_info,
                    DBStatus.CHECKING_REPO,
                    f"📝 需要初始化新的 repo"
                )
            
            # Step 3: 處理 repo init（改善版）
            if not db_info.has_existing_repo:
                self.progress_manager.update_status(
                    db_info.db_info,
                    DBStatus.REPO_INIT,
                    f"🔍 獲取 source command from JIRA..."
                )
                
                # 獲取 source command（使用改善的管理器）
                start_jira = time.time()
                source_cmd = self.source_cmd_manager.get_source_command(
                    db_info, 
                    self.mapping_reader.df
                )
                jira_time = time.time() - start_jira
                
                if not source_cmd:
                    raise Exception(f"無法取得 source command (JIRA 查詢時間: {jira_time:.1f}s)")
                
                db_info.actual_source_cmd = source_cmd
                
                # 顯示將要執行的命令
                cmd_display = source_cmd[:80] + "..." if len(source_cmd) > 80 else source_cmd
                self.progress_manager.update_status(
                    db_info.db_info,
                    DBStatus.REPO_INIT,
                    f"⚙️ 初始化 repo: {cmd_display}"
                )
                
                # 執行初始 repo init
                start_init = time.time()
                if not self.repo_manager.repo_init(local_path, source_cmd):
                    raise Exception("Repo init 失敗")
                init_time = time.time() - start_init
                
                # 應用 manifest（不重複 init）
                self.progress_manager.update_status(
                    db_info.db_info,
                    DBStatus.REPO_INIT,
                    f"📄 套用 {manifest_name} (init: {init_time:.1f}s)"
                )
                
                start_apply = time.time()
                if not self.repo_manager.apply_manifest(local_path, local_manifest):
                    raise Exception("套用 manifest 失敗")
                apply_time = time.time() - start_apply
                
                self.progress_manager.update_status(
                    db_info.db_info,
                    DBStatus.REPO_INIT,
                    f"✅ Repo 初始化完成 (套用: {apply_time:.1f}s)"
                )
                
            else:
                # 如果已有 .repo，只需切換 manifest
                self.progress_manager.update_status(
                    db_info.db_info,
                    DBStatus.REPO_INIT,
                    f"🔄 切換到 {manifest_name}"
                )
                
                start_apply = time.time()
                if not self.repo_manager.apply_manifest(local_path, local_manifest):
                    raise Exception("切換 manifest 失敗")
                apply_time = time.time() - start_apply
                
                self.progress_manager.update_status(
                    db_info.db_info,
                    DBStatus.REPO_INIT,
                    f"✅ Manifest 切換完成 ({apply_time:.1f}s)"
                )
                
            # Step 4: 啟動異步 repo sync（使用增強的重試機制）
            if not self.dry_run:
                self.progress_manager.update_status(
                    db_info.db_info,
                    DBStatus.REPO_SYNC,
                    f"🚀 檢查磁碟空間並準備同步..."
                )
                
                start_sync_init = time.time()
                
                # 使用增強的 sync 方法（包含磁碟空間檢查）
                process = self.repo_manager.start_repo_sync_async_with_retry(
                    local_path, 
                    db_info.db_info,
                    max_retries=2
                )
                
                if not process:
                    # 檢查是否為磁碟空間問題
                    if not self.repo_manager._check_disk_space_with_alert(local_path, db_info.db_info, 5.0):
                        raise Exception("❌ 磁碟空間不足！請清理空間後重試")
                    else:
                        raise Exception("啟動 repo sync 失敗（包含重試）")
                
                sync_init_time = time.time() - start_sync_init
                db_info.sync_process = process
                
                # 記錄 sync 日誌路徑
                log_dir = os.path.join(local_path, 'logs')
                if os.path.exists(log_dir):
                    log_files = sorted([f for f in os.listdir(log_dir) if f.startswith('repo_sync_')])
                    if log_files:
                        db_info.sync_log_path = os.path.join(log_dir, log_files[-1])
                
                # 更新狀態顯示 sync 進行中
                self.progress_manager.update_status(
                    db_info.db_info,
                    DBStatus.REPO_SYNC,
                    f"🔄 同步中... (PID: {process.pid})"
                )
            else:
                self.logger.info(f"[Dry Run] 跳過 repo sync for {db_info.db_info}")
                db_info.status = DBStatus.SKIPPED
                self.progress_manager.update_status(
                    db_info.db_info,
                    DBStatus.SKIPPED,
                    f"🧪 測試模式 - 已跳過 sync"
                )
            
            total_time = time.time() - db_info.start_time.timestamp()
            self.logger.info(f"✅ {db_info.db_info} 第一階段完成，總時間: {total_time:.1f}s")
            
        except Exception as e:
            total_time = time.time() - db_info.start_time.timestamp() if db_info.start_time else 0
            db_info.status = DBStatus.FAILED
            db_info.error_message = str(e)
            
            # 如果是磁碟空間錯誤，在狀態中特別標記
            if "磁碟空間" in str(e) or "disk" in str(e).lower():
                status_msg = f"💾 {str(e)}"
            else:
                status_msg = f"❌ {str(e)}"
            
            self.progress_manager.update_status(
                db_info.db_info,
                DBStatus.FAILED,
                f"{status_msg} (總時間: {total_time:.1f}s)"
            )
            self.logger.error(f"❌ {db_info.db_info} 處理失敗: {str(e)}")
        
        return db_info  

    def find_specific_manifest(self, base_path: str, version: str) -> Optional[Tuple[str, str]]:
        """尋找特定版本的 manifest 文件"""
        try:
            sftp, client = self._get_connection()
            if not sftp:
                raise Exception("無法建立 SFTP 連線")
            
            self.logger.info(f"尋找版本 {version} 的 manifest: {base_path}")
            
            # 嘗試直接在版本目錄中尋找
            version_patterns = [
                version,
                f"v{version}",
                f"version_{version}",
                f"ver{version}"
            ]
            
            items = sftp.listdir_attr(base_path)
            
            for pattern in version_patterns:
                version_path = f"{base_path}/{pattern}"
                
                try:
                    # 檢查版本目錄是否存在
                    version_files = sftp.listdir(version_path)
                    
                    # 在版本目錄中尋找 manifest
                    for filename in version_files:
                        if filename.endswith('.xml') and 'manifest' in filename.lower():
                            full_path = f"{version_path}/{filename}"
                            
                            # 檢查文件大小
                            file_stat = sftp.stat(full_path)
                            if file_stat.st_size > 100000:  # 大於 100KB
                                self.logger.info(f"找到指定版本的 manifest: {filename}")
                                return full_path, filename
                
                except Exception as e:
                    self.logger.debug(f"檢查版本目錄失敗: {pattern}, {e}")
                    continue
            
            raise Exception(f"未找到版本 {version} 的 manifest")
            
        except Exception as e:
            self.logger.error(f"尋找特定版本 manifest 失敗: {e}")
            return None
        
    def process_db_phase2(self, db_info: DBInfo) -> DBInfo:
        """
        處理 DB 的第二階段：完成工作（改善版）
        """
        try:
            if self.dry_run:
                db_info.status = DBStatus.SKIPPED
                db_info.end_time = datetime.now()
                return db_info
            
            # 檢查 sync 進程狀態（線程安全）
            if db_info.sync_process:
                poll = self.repo_manager.check_process_status(
                    db_info.db_info, 
                    db_info.sync_process
                )
                
                if poll is None:
                    # 還在執行中
                    return db_info
                elif poll != 0:
                    # sync 失敗，嘗試讀取錯誤日誌
                    error_msg = f"Repo sync 失敗 (返回碼: {poll})"
                    if db_info.sync_log_path and os.path.exists(db_info.sync_log_path):
                        try:
                            with open(db_info.sync_log_path, 'r', encoding='utf-8', errors='ignore') as f:
                                lines = f.readlines()
                                # 取最後 10 行作為錯誤訊息
                                last_lines = lines[-10:] if len(lines) > 10 else lines
                                error_detail = ''.join(last_lines)
                                error_msg += f"\n最後日誌:\n{error_detail}"
                        except:
                            pass
                    raise Exception(error_msg)
            
            # 導出 manifest
            self.progress_manager.update_status(
                db_info.db_info,
                DBStatus.EXPORTING,
                "導出版本資訊"
            )
            
            if not self.repo_manager.export_manifest(db_info.local_path):
                raise Exception("導出 manifest 失敗")
            
            # 完成
            db_info.status = DBStatus.SUCCESS
            db_info.end_time = datetime.now()
            
            self.progress_manager.update_status(
                db_info.db_info,
                DBStatus.SUCCESS,
                f"版本 {db_info.version}"
            )
            
            self.logger.info(f"✅ {db_info.db_info} 定版完成")
            
        except Exception as e:
            db_info.status = DBStatus.FAILED
            db_info.error_message = str(e)
            db_info.end_time = datetime.now()
            
            self.progress_manager.update_status(
                db_info.db_info,
                DBStatus.FAILED,
                str(e)
            )
            
            self.logger.error(f"❌ {db_info.db_info} 第二階段失敗: {str(e)}")
        
        return db_info

    def process_dbs_async(self, db_list: List[str], db_versions: Dict[str, str] = None):
        """異步處理多個 DB（完整版 - 包含詳細進度監控）"""
        db_versions = db_versions or {}
        db_infos = []
        
        # 準備 DB 資訊
        all_db_infos = self.get_all_dbs('all')
        
        for db_name in db_list:
            # 解析版本
            if '#' in db_name:
                db_name, version = db_name.split('#', 1)
            else:
                version = db_versions.get(db_name)
            
            # 找到對應的 DB 資訊
            for db_info in all_db_infos:
                if db_info.db_info == db_name:
                    db_info.version = version
                    db_infos.append(db_info)
                    self.progress_manager.init_db(db_name, db_info)  # 傳遞 db_info
                    break
        
        if not db_infos:
            self.logger.error("沒有找到要處理的 DB")
            return

        self.logger.info(f"開始異步處理 {len(db_infos)} 個 DB")
        
        # 建立進度顯示執行緒
        stop_progress = threading.Event()
        
        def display_progress_thread():
            while not stop_progress.is_set():
                try:
                    self.progress_manager.display_progress()
                    time.sleep(config_manager.path_config['progress_update_interval'])
                except Exception as e:
                    self.logger.debug(f"進度顯示錯誤: {e}")

        # 建立 sync 進度監控執行緒
        def sync_monitor_thread():
            self.logger.info("啟動 sync 進度監控線程")
            while not stop_progress.is_set():
                try:
                    for db_info in db_infos:
                        # 檢查是否有 sync 日誌檔案且正在 sync
                        current_status = self.progress_manager.db_status.get(db_info.db_info, (None, ""))[0]
                        
                        if (current_status == DBStatus.REPO_SYNC and 
                            db_info.sync_log_path and 
                            os.path.exists(db_info.sync_log_path)):
                            
                            # 檢查日誌檔案是否有新內容
                            try:
                                file_size = os.path.getsize(db_info.sync_log_path)
                                if file_size > 0:
                                    self.progress_manager.update_sync_progress(
                                        db_info.db_info, 
                                        db_info.sync_log_path
                                    )
                            except Exception as e:
                                self.logger.debug(f"檢查日誌檔案 {db_info.sync_log_path} 失敗: {e}")
                    
                    time.sleep(3)  # 每 3 秒更新一次 sync 進度
                except Exception as e:
                    self.logger.debug(f"Sync 監控錯誤: {e}")
                    time.sleep(3)
        
        progress_thread = threading.Thread(target=display_progress_thread, daemon=True)
        sync_monitor_thread_obj = threading.Thread(target=sync_monitor_thread, daemon=True)
        
        progress_thread.start()
        sync_monitor_thread_obj.start()
        
        try:
            # Phase 1: 準備和啟動 sync
            with ThreadPoolExecutor(
                max_workers=config_manager.parallel_config['max_workers']
            ) as executor:
                futures = {
                    executor.submit(self.process_db_phase1, db_info): db_info 
                    for db_info in db_infos
                }
                
                phase1_results = []
                for future in as_completed(futures):
                    try:
                        result = future.result(timeout=300)
                        phase1_results.append(result)
                        
                        # 確保 progress_manager 有最新的 db_info
                        self.progress_manager.db_info_cache[result.db_info] = result
                        
                    except Exception as e:
                        db_info = futures[future]
                        self.logger.error(f"Phase 1 異常 ({db_info.db_info}): {str(e)}")
                        db_info.status = DBStatus.FAILED
                        db_info.error_message = str(e)
                        phase1_results.append(db_info)
            
            # 等待所有 sync 完成
            self.logger.info("等待所有 repo sync 完成...")
            
            max_wait_time = config_manager.repo_config['sync_timeout']
            start_wait = time.time()
            
            while True:
                all_complete = True
                
                for db_info in phase1_results:
                    if db_info.status == DBStatus.FAILED:
                        continue
                    
                    if db_info.sync_process:
                        poll = self.repo_manager.check_process_status(
                            db_info.db_info,
                            db_info.sync_process
                        )
                        if poll is None:
                            # 還在執行
                            all_complete = False
                            
                            # 檢查是否超時
                            elapsed = time.time() - start_wait
                            if elapsed > max_wait_time:
                                self.logger.warning(f"{db_info.db_info} sync 超時，強制終止")
                                try:
                                    db_info.sync_process.terminate()
                                    db_info.sync_process.wait(timeout=5)
                                except:
                                    db_info.sync_process.kill()
                                db_info.status = DBStatus.FAILED
                                db_info.error_message = "Sync 超時"
                                self.progress_manager.update_status(
                                    db_info.db_info,
                                    DBStatus.FAILED,
                                    "❌ Sync 超時"
                                )
                        elif poll == 0:
                            # 成功完成
                            self.progress_manager.update_status(
                                db_info.db_info,
                                DBStatus.REPO_SYNC,
                                "✅ 同步完成，準備導出"
                            )
                        else:
                            # 失敗
                            db_info.status = DBStatus.FAILED
                            db_info.error_message = f"Sync 失敗 (返回碼: {poll})"
                            self.progress_manager.update_status(
                                db_info.db_info,
                                DBStatus.FAILED,
                                f"❌ Sync 失敗 (返回碼: {poll})"
                            )
                
                if all_complete or (time.time() - start_wait) > max_wait_time:
                    break
                
                time.sleep(5)
            
            # Phase 2: 完成處理
            self.logger.info("執行第二階段處理...")
            
            with ThreadPoolExecutor(
                max_workers=config_manager.parallel_config['max_workers']
            ) as executor:
                futures = {
                    executor.submit(self.process_db_phase2, db_info): db_info 
                    for db_info in phase1_results
                }
                
                for future in as_completed(futures):
                    try:
                        result = future.result(timeout=60)
                        self.report.add_db(result)
                    except Exception as e:
                        db_info = futures[future]
                        self.logger.error(f"Phase 2 異常 ({db_info.db_info}): {str(e)}")
                        db_info.status = DBStatus.FAILED
                        db_info.error_message = str(e)
                        self.report.add_db(db_info)
            
        finally:
            # 停止進度顯示
            stop_progress.set()
            progress_thread.join(timeout=2)
            sync_monitor_thread_obj.join(timeout=2)
            
            # 顯示最終結果
            self.progress_manager.display_progress(clear_screen=False)

    def load_mapping_table(self, file_path: str) -> bool:
        """載入 mapping table"""
        return self.mapping_reader.load_excel(file_path)

    def get_all_dbs(self, db_type: str = 'all') -> List[DBInfo]:
        """取得所有 DB 資訊"""
        return self.mapping_reader.get_db_info_list(db_type)

    def process_selected_dbs(self, db_list: List[str], db_versions: Dict[str, str] = None):
        """處理選定的 DB"""
        if config_manager.repo_config['async_sync'] and not self.dry_run:
            self.process_dbs_async(db_list, db_versions)
        else:
            # 同步處理或 dry run 模式
            self.logger.info("使用同步處理模式")
            for db_name in db_list:
                if '#' in db_name:
                    db_name, version = db_name.split('#', 1)
                else:
                    version = db_versions.get(db_name) if db_versions else None
                
                # 找到對應的 DB 資訊
                for db_info in self.get_all_dbs('all'):
                    if db_info.db_info == db_name:
                        db_info.version = version
                        self.progress_manager.init_db(db_name)
                        
                        # Phase 1
                        db_info = self.process_db_phase1(db_info)
                        
                        if not self.dry_run and db_info.sync_process:
                            # 等待 sync 完成
                            self.logger.info(f"等待 {db_name} sync 完成...")
                            db_info.sync_process.wait()
                        
                        # Phase 2
                        db_info = self.process_db_phase2(db_info)
                        self.report.add_db(db_info)
                        break

    def generate_report(self, output_file: str = None):
        """產生報告（增強版）"""
        self.report.finalize()
        
        if not output_file:
            output_file = os.path.join(
                self.output_dir, 
                config_manager.path_config['report_filename']
            )
        
        try:
            report_data = []
            for db in self.report.db_details:
                db_dict = db.to_dict()
                # 確保包含所有重要資訊
                db_dict['source_command'] = db.actual_source_cmd or '未記錄'
                db_dict['manifest_version'] = db.version or '未指定'
                db_dict['manifest_file'] = db.manifest_file or '未下載'
                report_data.append(db_dict)
            
            df = pd.DataFrame(report_data)
            
            # 建立摘要
            summary = {
                '項目': ['總 DB 數', '成功', '失敗', '跳過', '執行時間'],
                '數值': [
                    self.report.total_dbs,
                    self.report.successful_dbs,
                    self.report.failed_dbs,
                    self.report.skipped_dbs,
                    str(self.report.end_time - self.report.start_time) if self.report.end_time else 'N/A'
                ]
            }
            summary_df = pd.DataFrame(summary)
            
            # 寫入 Excel，包含更多資訊
            with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
                summary_df.to_excel(writer, sheet_name='摘要', index=False)
                df.to_excel(writer, sheet_name='詳細資訊', index=False)
                
                # 新增處理記錄表
                process_log = []
                for db in self.report.db_details:
                    process_log.append({
                        'DB名稱': db.db_info,
                        '模組': db.module,
                        '類型': db.db_type,
                        'Source Command': db.actual_source_cmd or '未記錄',
                        'Manifest版本': db.version or '最新',
                        'Manifest檔案': db.manifest_file or '未下載',
                        '狀態': db.status.value if isinstance(db.status, DBStatus) else db.status,
                        '開始時間': db.start_time.strftime('%Y-%m-%d %H:%M:%S') if db.start_time else '',
                        '結束時間': db.end_time.strftime('%Y-%m-%d %H:%M:%S') if db.end_time else '',
                        '錯誤訊息': db.error_message or ''
                    })
                
                process_df = pd.DataFrame(process_log)
                process_df.to_excel(writer, sheet_name='處理記錄', index=False)
            
            self.logger.info(f"報告已產生: {output_file}")
            
        except Exception as e:
            self.logger.error(f"產生報告失敗: {str(e)}")

# =====================================
# ===== 互動式介面（改善版） =====
# =====================================

class InteractiveUI:
    """互動式使用者介面（改善版）"""
    
    def __init__(self):
        self.tool = ManifestPinningTool()
        self.logger = setup_logger(self.__class__.__name__)
        self.selected_dbs = []
        self.db_versions = {}
        self.selected_db_type = 'all'
        
        # 載入預設配置
        self._load_default_config()
    
    def _load_default_config(self):
        """載入預設配置"""
        # 如果有預設的 SFTP 設定，覆蓋全域設定
        if config_manager.default_execution_config.get('sftp_override'):
            config_manager.apply_overrides(
                config_manager.default_execution_config['sftp_override'],
                source='default_config'
            )
        
        # 如果有預設的輸出目錄
        if config_manager.default_execution_config.get('output_dir'):
            self.tool.output_dir = config_manager.default_execution_config['output_dir']
    
    def setup_sftp(self):
        """設定 SFTP 連線資訊"""
        print("\n目前 SFTP 設定:")
        print(f"  Host: {config_manager.sftp_config['host']}")
        print(f"  Port: {config_manager.sftp_config['port']}")
        print(f"  Username: {config_manager.sftp_config['username']}")
        
        if input("\n是否要修改設定? (y/N): ").strip().lower() == 'y':
            host = input(f"Host [{config_manager.sftp_config['host']}]: ").strip()
            if host:
                config_manager.sftp_config['host'] = host
                
            port = input(f"Port [{config_manager.sftp_config['port']}]: ").strip()
            if port:
                config_manager.sftp_config['port'] = int(port)
                
            username = input(f"Username [{config_manager.sftp_config['username']}]: ").strip()
            if username:
                config_manager.sftp_config['username'] = username
                
            password = input("Password (留空保持原值): ").strip()
            if password:
                config_manager.sftp_config['password'] = password
            
            print("✅ SFTP 設定已更新")
            
            # 重新建立 SFTP 管理器
            self.tool.sftp_manager = ThreadSafeSFTPManager()
    
    def display_current_settings(self):
        """顯示目前設定"""
        print("\n目前設定:")
        print(f"  Mapping table: {'已載入' if self.tool.mapping_reader.df is not None else '未載入'}")
        print(f"  DB 類型: {self.selected_db_type}")
        print(f"  選擇的 DB: {len(self.selected_dbs)} 個")
        print(f"  設定版本的 DB: {len(self.db_versions)} 個")
        print(f"  輸出目錄: {self.tool.output_dir}")
        print(f"  平行處理: {'啟用' if config_manager.parallel_config['enable_parallel'] else '關閉'}")
        print(f"  Worker 數量: {config_manager.parallel_config['max_workers']}")
    
    def load_mapping_table(self):
        """載入 mapping table（支援預設值）"""
        default_mapping = config_manager.default_execution_config.get('mapping_table')
        
        if default_mapping and os.path.exists(default_mapping):
            print(f"\n📌 找到預設 mapping table: {default_mapping}")
            if input("是否使用預設檔案? (Y/n): ").strip().lower() != 'n':
                file_path = default_mapping
            else:
                file_path = input(
                    f"請輸入 mapping table 路徑 [{config_manager.path_config['default_mapping_table']}]: "
                ).strip()
                if not file_path:
                    file_path = config_manager.path_config['default_mapping_table']
        else:
            default_path = config_manager.path_config['default_mapping_table']
            file_path = input(f"請輸入 mapping table 路徑 [{default_path}]: ").strip()
            if not file_path:
                file_path = default_path
        
        if not os.path.exists(file_path):
            print(f"❌ 檔案不存在: {file_path}")
            return
        
        if self.tool.load_mapping_table(file_path):
            print(f"✅ 成功載入 mapping table，共 {len(self.tool.mapping_reader.df)} 筆資料")
            all_dbs = self.tool.get_all_dbs()
            unique_db_names = list(set([db.db_info for db in all_dbs]))
            print(f"   找到 {len(unique_db_names)} 個不重複的 DB")
            
            # 如果有預設的 DB 類型，自動設定
            if config_manager.default_execution_config.get('db_type'):
                self.selected_db_type = config_manager.default_execution_config['db_type']
                print(f"   📌 使用預設 DB 類型: {self.selected_db_type}")
        else:
            print("❌ 載入失敗")
    
    def select_db_type(self):
        """選擇 DB 類型（支援預設值）"""
        default_type = config_manager.default_execution_config.get('db_type')
        
        if default_type and default_type in ['all', 'master', 'premp', 'mp', 'mpbackup']:
            print(f"\n📌 找到預設 DB 類型: {default_type}")
            if input("是否使用預設值? (Y/n): ").strip().lower() != 'n':
                self.selected_db_type = default_type
                print(f"✅ 已選擇 DB 類型: {self.selected_db_type}")
                return self.selected_db_type
        
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
        
        self.selected_db_type = type_map.get(choice, 'all')
        print(f"✅ 已選擇 DB 類型: {self.selected_db_type}")
        return self.selected_db_type
    
    def select_dbs(self):
        """選擇要定版的 DB（支援預設值）"""
        if not self.tool.mapping_reader or self.tool.mapping_reader.df is None:
            print("❌ 請先載入 mapping table")
            return []
        
        all_db_infos = self.tool.get_all_dbs(self.selected_db_type)
        if not all_db_infos:
            print(f"❌ 沒有找到 {self.selected_db_type} 類型的 DB")
            return []
        
        # 取得不重複的 DB 列表
        unique_dbs = {}
        for db_info in all_db_infos:
            if db_info.db_info not in unique_dbs:
                unique_dbs[db_info.db_info] = db_info
        
        db_list = list(unique_dbs.keys())
        db_list.sort()
        
        # 檢查是否有預設的 DB 列表
        default_dbs = config_manager.default_execution_config.get('selected_dbs')
        
        if default_dbs:
            if default_dbs in ['all', '*']:
                print(f"\n📌 預設配置為選擇所有 {self.selected_db_type} 類型的 DB")
                if input(f"是否選擇全部 {len(db_list)} 個 DB? (Y/n): ").strip().lower() != 'n':
                    self.selected_dbs = db_list
                    print(f"✅ 已選擇所有 {len(db_list)} 個 DB")
                    return db_list
            
            elif isinstance(default_dbs, list) and len(default_dbs) > 0:
                parsed_dbs = []
                for db_spec in default_dbs:
                    if '#' in db_spec:
                        db_name, version = db_spec.split('#', 1)
                        if db_name in db_list:
                            parsed_dbs.append(db_name)
                            self.db_versions[db_name] = version
                    else:
                        if db_spec in db_list:
                            parsed_dbs.append(db_spec)
                
                if parsed_dbs:
                    print(f"\n📌 找到預設 DB 列表: {', '.join(default_dbs)}")
                    print(f"   其中 {len(parsed_dbs)} 個 DB 存在於當前 mapping table")
                    if input("是否使用預設 DB 列表? (Y/n): ").strip().lower() != 'n':
                        self.selected_dbs = parsed_dbs
                        print(f"✅ 已選擇 {len(parsed_dbs)} 個 DB")
                        return parsed_dbs
        
        # 顯示 DB 列表和原本的選擇邏輯
        print(f"\n找到 {len(db_list)} 個不重複的 DB (類型: {self.selected_db_type})")
        
        # 顯示 DB 列表
        print("\nDB 列表:")
        for i, db in enumerate(db_list, 1):
            db_info = unique_dbs[db]
            print(f"{i:3d}. {db:10s} - {db_info.module:10s} ({db_info.db_type})")
        
        print("\n選擇方式:")
        print("1. 全選")
        print("2. 輸入編號範圍 (如: 1-5,7,9-12)")
        print("3. 輸入 DB 名稱列表 (逗號分隔)")
        
        choice = input("請選擇: ").strip()
        
        selected = []
        
        if choice == '1':
            selected = db_list
        elif choice == '2':
            indices_input = input("請輸入編號範圍: ").strip()
            try:
                indices = self._parse_number_range(indices_input, len(db_list))
                selected = [db_list[i-1] for i in indices if 1 <= i <= len(db_list)]
            except Exception as e:
                print(f"❌ 無效的編號範圍: {e}")
                return []
        elif choice == '3':
            db_names = input("請輸入 DB 名稱 (如: DB2302,DB2575): ").strip()
            input_dbs = [db.strip() for db in db_names.split(',')]
            for db in input_dbs:
                if db in db_list:
                    selected.append(db)
                else:
                    print(f"⚠️ DB {db} 不存在，已跳過")
        
        self.selected_dbs = selected
        print(f"✅ 已選擇 {len(selected)} 個 DB")
        return selected
    
    def _parse_number_range(self, range_str: str, max_num: int) -> List[int]:
        """解析數字範圍字串"""
        result = []
        parts = range_str.split(',')
        
        for part in parts:
            part = part.strip()
            if '-' in part:
                start, end = part.split('-', 1)
                start = int(start.strip())
                end = int(end.strip())
                
                if start > end:
                    start, end = end, start
                
                for i in range(start, min(end + 1, max_num + 1)):
                    if i > 0:
                        result.append(i)
            else:
                num = int(part)
                if 1 <= num <= max_num:
                    result.append(num)
        
        return sorted(list(set(result)))
    
    def setup_db_versions(self):
        """設定 DB 版本（支援預設值）"""
        if not self.selected_dbs:
            print("❌ 請先選擇 DB")
            return
        
        default_versions = config_manager.default_execution_config.get('db_versions', {})
        
        if default_versions:
            applicable_versions = {
                db: ver for db, ver in default_versions.items() 
                if db in self.selected_dbs
            }
            
            if applicable_versions:
                print(f"\n📌 找到預設版本設定:")
                for db, ver in applicable_versions.items():
                    print(f"   {db}: 版本 {ver}")
                
                if input("是否使用預設版本設定? (Y/n): ").strip().lower() != 'n':
                    self.db_versions.update(applicable_versions)
                    print(f"✅ 已套用 {len(applicable_versions)} 個 DB 的預設版本")
                    
                    unset_dbs = [db for db in self.selected_dbs if db not in self.db_versions]
                    if unset_dbs:
                        print(f"\n還有 {len(unset_dbs)} 個 DB 未設定版本:")
                        for db in unset_dbs:
                            version = input(f"{db} 的版本 [最新]: ").strip()
                            if version:
                                self.db_versions[db] = version
                    return
        
        print("\n設定 DB 版本 (留空使用最新版本)")
        print("提示: 可以輸入具體版本號，如 206, 204 等")
        print("支援格式:")
        print("  ✅ 206_all_202507100000  (version_all_timestamp)")
        print("  ✅ 204_202507081101      (version_timestamp)")
        print("  ✅ 465_all_202502170030_NG_uboot_fail (帶後綴)")
        print("  ✅ 466_202502171018_NG_uboot_fail (帶後綴)")
        
        for db in self.selected_dbs:
            if db in self.db_versions:
                print(f"{db}: 已設定版本 {self.db_versions[db]}")
                continue
            
            version = input(f"{db} 的版本 [最新]: ").strip()
            if version:
                self.db_versions[db] = version
        
        if self.db_versions:
            print(f"✅ 已設定 {len(self.db_versions)} 個 DB 的版本")
    
    def execute_pinning(self):
        """執行定版（支援預設配置）"""
        if not self.selected_dbs:
            print("❌ 請先選擇要定版的 DB")
            return
        
        if not self.tool.mapping_reader or self.tool.mapping_reader.df is None:
            print("❌ 請先載入 mapping table")
            return
        
        print("\n" + "="*60)
        print("準備執行定版")
        print("="*60)
        print(f"📌 DB 數量: {len(self.selected_dbs)}")
        print(f"🔍 輸出目錄: {self.tool.output_dir}")
        
        # 詢問輸出目錄（檢查預設值）
        default_output = config_manager.default_execution_config.get('output_dir')
        if default_output:
            print(f"📌 找到預設輸出目錄: {default_output}")
            if input("是否使用預設輸出目錄? (Y/n): ").strip().lower() != 'n':
                self.tool.output_dir = default_output
            else:
                output_dir = input(f"輸出目錄 [{self.tool.output_dir}]: ").strip()
                if output_dir:
                    self.tool.output_dir = output_dir
        else:
            output_dir = input(f"輸出目錄 [{self.tool.output_dir}]: ").strip()
            if output_dir:
                self.tool.output_dir = output_dir
        
        # 確認執行（檢查自動確認設定）
        if config_manager.default_execution_config.get('auto_confirm'):
            print("📌 自動確認執行（根據預設配置）")
        else:
            if input("\n確認開始執行? (Y/n): ").strip().lower() == 'n':
                print("❌ 使用者取消操作")
                return
        
        print("\n🚀 開始執行定版...")
        
        # 連線 SFTP
        print("🌐 連線到 SFTP 伺服器...")
        if not self.tool.sftp_manager.connect():
            print("❌ SFTP 連線失敗")
            return
        
        try:
            # 執行定版
            self.tool.process_selected_dbs(self.selected_dbs, self.db_versions)
            
            # 產生報告
            print("\n📊 產生報告...")
            report_path = os.path.join(
                self.tool.output_dir, 
                config_manager.path_config['report_filename']
            )
            self.tool.generate_report(report_path)
            
            print("\n✨ 定版完成！")
            
        finally:
            # 關閉 SFTP 連線
            self.tool.sftp_manager.disconnect()
            # 清理所有資源
            resource_manager.cleanup_all()
    
    def display_menu(self) -> str:
        """顯示主選單（顯示預設配置狀態）"""
        print("\n" + "="*60)
        print("Manifest 定版工具 - 主選單")
        
        # 如果有預設配置，顯示提示
        has_defaults = any([
            config_manager.default_execution_config.get('mapping_table'),
            config_manager.default_execution_config.get('db_type'),
            config_manager.default_execution_config.get('selected_dbs'),
            config_manager.default_execution_config.get('db_versions'),
            config_manager.default_execution_config.get('output_dir')
        ])
        
        if has_defaults:
            print("(📌 已載入預設配置)")
        
        print("="*60)
        print("1. 載入 mapping table")
        print("2. 設定 SFTP 連線資訊")
        print("3. 選擇 DB 類型 (master/premp/mp/mpbackup/all)")
        print("4. 選擇要定版的 DB")
        print("5. 設定 DB 版本")
        print("6. 開始執行定版")
        print("7. 顯示目前設定")
        print("8. 快速執行（使用所有預設值）")
        print("9. 設定進階選項")
        print("10. 測試 JIRA 連線")
        print("11. 測試 SFTP 連線和路徑")
        print("12. 測試版本目錄識別")
        print("0. 結束程式")
        print("="*60)
        
        return input("請選擇功能: ").strip()
    
    def setup_advanced_options(self):
        """設定進階選項"""
        print("\n進階選項設定:")
        print("1. 平行處理設定")
        print("2. Repo 設定")
        print("3. 日誌等級設定")
        print("4. JIRA 設定")
        print("5. 返回主選單")
        
        choice = input("請選擇: ").strip()
        
        if choice == '1':
            # 平行處理設定
            enable = input(f"啟用平行處理? (Y/n) [{config_manager.parallel_config['enable_parallel']}]: ").strip().lower()
            if enable == 'n':
                config_manager.parallel_config['enable_parallel'] = False
            elif enable == 'y':
                config_manager.parallel_config['enable_parallel'] = True
            
            if config_manager.parallel_config['enable_parallel']:
                workers = input(f"Worker 數量 [{config_manager.parallel_config['max_workers']}]: ").strip()
                if workers.isdigit():
                    config_manager.parallel_config['max_workers'] = int(workers)
            
            print("✅ 平行處理設定已更新")
            
        elif choice == '2':
            # Repo 設定
            sync_jobs = input(f"Repo sync 並行數 [{config_manager.repo_config['sync_jobs']}]: ").strip()
            if sync_jobs.isdigit():
                config_manager.repo_config['sync_jobs'] = int(sync_jobs)
            
            sync_retry = input(f"Sync 重試次數 [{config_manager.repo_config['sync_retry']}]: ").strip()
            if sync_retry.isdigit():
                config_manager.repo_config['sync_retry'] = int(sync_retry)
            
            sync_timeout = input(f"Sync 超時秒數 [{config_manager.repo_config['sync_timeout']}]: ").strip()
            if sync_timeout.isdigit():
                config_manager.repo_config['sync_timeout'] = int(sync_timeout)
            
            print("✅ Repo 設定已更新")
            
        elif choice == '3':
            # 日誌等級設定
            print("日誌等級:")
            print("1. DEBUG")
            print("2. INFO")
            print("3. WARNING")
            print("4. ERROR")
            
            level_choice = input("請選擇: ").strip()
            level_map = {
                '1': logging.DEBUG,
                '2': logging.INFO,
                '3': logging.WARNING,
                '4': logging.ERROR
            }
            
            if level_choice in level_map:
                config_manager.log_config['level'] = level_map[level_choice]
                # 更新所有 logger
                for handler in logging.getLogger().handlers:
                    handler.setLevel(config_manager.log_config['level'])
                print("✅ 日誌等級已更新")
                
        elif choice == '4':
            # JIRA 設定
            print("\n目前 JIRA 設定:")
            print(f"  網址: https://{config_manager.jira_config['site']}")
            print(f"  用戶: {config_manager.jira_config['username']}")
            print(f"  API URL: {config_manager.jira_config['api_url']}")
            
            if input("\n是否要修改設定? (y/N): ").strip().lower() == 'y':
                site = input(f"JIRA 網站 [{config_manager.jira_config['site']}]: ").strip()
                if site:
                    config_manager.jira_config['site'] = site
                    config_manager.jira_config['api_url'] = f"https://{site}/rest/api/2"
                
                username = input(f"用戶名 [{config_manager.jira_config['username']}]: ").strip()
                if username:
                    config_manager.jira_config['username'] = username
                
                password = input("密碼 (留空保持原值): ").strip()
                if password:
                    config_manager.jira_config['password'] = password
                
                print("✅ JIRA 設定已更新")
                
                # 清除快取
                if hasattr(self.tool, 'source_cmd_manager'):
                    self.tool.source_cmd_manager.clear_cache()
    
    def quick_execute_with_defaults(self):
        """使用預設配置快速執行"""
        print("\n" + "="*60)
        print("快速執行模式 - 使用預設配置")
        print("="*60)
        
        # 自動載入 mapping table
        if config_manager.default_execution_config.get('mapping_table'):
            file_path = config_manager.default_execution_config['mapping_table']
            if os.path.exists(file_path):
                print(f"📌 載入預設 mapping table: {file_path}")
                if self.tool.load_mapping_table(file_path):
                    print(f"✅ 成功載入")
                else:
                    print("❌ 載入失敗")
                    return
            else:
                print(f"❌ 預設 mapping table 不存在: {file_path}")
                return
        else:
            print("❌ 未設定預設 mapping table")
            return
        
        # 設定 DB 類型
        if config_manager.default_execution_config.get('db_type'):
            self.selected_db_type = config_manager.default_execution_config['db_type']
            print(f"📌 使用預設 DB 類型: {self.selected_db_type}")
        
        # 選擇 DB
        default_dbs = config_manager.default_execution_config.get('selected_dbs')
        all_db_infos = self.tool.get_all_dbs(self.selected_db_type)
        
        if default_dbs:
            if default_dbs in ['all', '*']:
                unique_dbs = list(set([db.db_info for db in all_db_infos]))
                self.selected_dbs = unique_dbs
                print(f"📌 選擇所有 {self.selected_db_type} 類型的 DB: {len(unique_dbs)} 個")
            
            elif isinstance(default_dbs, list) and len(default_dbs) > 0:
                parsed_dbs = []
                for db_spec in default_dbs:
                    if '#' in db_spec:
                        db_name, version = db_spec.split('#', 1)
                        parsed_dbs.append(db_name)
                        self.db_versions[db_name] = version
                    else:
                        parsed_dbs.append(db_spec)
                self.selected_dbs = parsed_dbs
                print(f"📌 使用預設 DB 列表: {len(parsed_dbs)} 個")
        else:
            print("⚠️ 預設配置未指定 DB 列表，無法自動執行")
            return
        
        # 設定版本
        if config_manager.default_execution_config.get('db_versions'):
            self.db_versions.update(config_manager.default_execution_config['db_versions'])
            print(f"📌 套用預設版本設定: {len(self.db_versions)} 個")
        
        # 設定輸出目錄
        if config_manager.default_execution_config.get('output_dir'):
            self.tool.output_dir = config_manager.default_execution_config['output_dir']
            print(f"📌 使用預設輸出目錄: {self.tool.output_dir}")
        
        # 顯示摘要
        print("\n執行摘要:")
        print(f"  DB 類型: {self.selected_db_type}")
        print(f"  DB 數量: {len(self.selected_dbs)}")
        print(f"  設定版本: {len(self.db_versions)} 個")
        print(f"  輸出目錄: {self.tool.output_dir}")
        
        # 確認執行
        if not config_manager.default_execution_config.get('auto_confirm'):
            if input("\n確認執行? (Y/n): ").strip().lower() == 'n':
                print("❌ 使用者取消")
                return
        
        # 執行定版
        self.execute_pinning()
    
    def test_jira_connection(self):
        """測試 JIRA 連線並顯示範例查詢"""
        print("\n測試 JIRA 連線...")
        
        # 建立 source command 管理器（如果還沒有）
        if not hasattr(self.tool, 'source_cmd_manager'):
            self.tool.source_cmd_manager = SourceCommandManager()
        
        # 測試連線
        if self.tool.source_cmd_manager.test_jira_connection():
            print("✅ JIRA 連線成功！")
            
            # 詢問是否要測試查詢
            if input("\n是否要測試查詢 DB 的 source command? (y/N): ").strip().lower() == 'y':
                db_name = input("請輸入 DB 名稱 (例如: DB2302): ").strip()
                if db_name:
                    print(f"\n查詢 {db_name} 的 source command...")
                    
                    # 建立臨時 DBInfo
                    test_db_info = DBInfo(
                        sn=0,
                        module="Test",
                        db_type="master",
                        db_info=db_name,
                        db_folder="",
                        sftp_path=""
                    )
                    
                    # 查詢
                    cmd = self.tool.source_cmd_manager.get_source_command(
                        test_db_info,
                        self.tool.mapping_reader.df if self.tool.mapping_reader else None
                    )
                    
                    if cmd:
                        print(f"\n找到的 source command:")
                        print(f"  {cmd}")
                    else:
                        print(f"\n未找到 {db_name} 的 source command")
        else:
            print("❌ JIRA 連線失敗！")
            print("\n請檢查：")
            print("1. JIRA 網址是否正確")
            print("2. 用戶名和密碼是否正確")
            print("3. 網路連線是否正常")
            print("4. 是否需要 VPN 連線")
    
    def test_sftp_connection(self):
        """測試 SFTP 連線和路徑診斷"""
        print("\n🔍 SFTP 連線和路徑測試")
        print("="*50)
        
        # 首先測試基本連線
        print("🌐 測試 SFTP 基本連線...")
        print(f"   伺服器: {config_manager.sftp_config['host']}:{config_manager.sftp_config['port']}")
        print(f"   用戶: {config_manager.sftp_config['username']}")
        
        if not self.tool.sftp_manager.connect():
            print("❌ SFTP 基本連線失敗")
            print("\n可能的原因:")
            print("1. 網路連線問題")
            print("2. SFTP 伺服器無法訪問") 
            print("3. 用戶名或密碼錯誤")
            print("4. 防火牆阻擋連線")
            return
        
        print("✅ SFTP 基本連線成功！")
        
        # 詢問測試模式
        print("\n選擇測試模式:")
        print("1. 測試單個路徑 (手動輸入)")
        print("2. 測試 mapping table 中的 DB 路徑")
        print("3. 測試失敗的 DB 路徑 (DB2858, DB2575, DB2919)")
        print("4. 快速測試常用路徑")
        
        choice = input("請選擇 (1-4): ").strip()
        
        try:
            if choice == '1':
                self._test_single_path()
            elif choice == '2':
                self._test_mapping_table_paths()
            elif choice == '3':
                self._test_failed_db_paths()
            elif choice == '4':
                self._test_common_paths()
            else:
                print("❌ 無效選擇")
        
        finally:
            self.tool.sftp_manager.disconnect()
            print("\n🔌 SFTP 連線已關閉")
    
    def _test_single_path(self):
        """測試單個路徑"""
        path = input("\n請輸入要測試的 SFTP 路徑: ").strip()
        if not path:
            print("❌ 未輸入路徑")
            return
        
        db_name = input("請輸入 DB 名稱 (可選): ").strip() or "Manual_Test"
        
        print(f"\n🔍 測試路徑: {path}")
        self._diagnose_sftp_path(path, db_name)
    
    def _test_mapping_table_paths(self):
        """測試 mapping table 中的路徑"""
        if not self.tool.mapping_reader or self.tool.mapping_reader.df is None:
            print("❌ 請先載入 mapping table")
            return
        
        all_db_infos = self.tool.get_all_dbs('all')
        if not all_db_infos:
            print("❌ mapping table 中沒有找到 DB 資料")
            return
        
        # 顯示可用的 DB
        unique_dbs = {}
        for db_info in all_db_infos:
            if db_info.db_info not in unique_dbs:
                unique_dbs[db_info.db_info] = db_info
        
        db_list = list(unique_dbs.keys())[:10]  # 只顯示前 10 個
        
        print(f"\n📋 可測試的 DB (前10個):")
        for i, db_name in enumerate(db_list, 1):
            db_info = unique_dbs[db_name]
            print(f"  {i:2d}. {db_name:12s} - {db_info.module:15s} ({db_info.db_type})")
        
        try:
            selection = input(f"\n請選擇要測試的 DB (1-{len(db_list)}) 或輸入 DB 名稱: ").strip()
            
            if selection.isdigit():
                idx = int(selection) - 1
                if 0 <= idx < len(db_list):
                    db_name = db_list[idx]
                    db_info = unique_dbs[db_name]
                else:
                    print("❌ 無效的編號")
                    return
            else:
                db_name = selection
                db_info = unique_dbs.get(db_name)
                if not db_info:
                    print(f"❌ 找不到 DB: {db_name}")
                    return
            
            print(f"\n🎯 測試 {db_info.db_info}")
            print(f"   路徑: {db_info.sftp_path}")
            print(f"   模組: {db_info.module}")
            print(f"   類型: {db_info.db_type}")
            
            self._diagnose_sftp_path(db_info.sftp_path, db_info.db_info)
            
        except ValueError:
            print("❌ 無效的輸入")
    
    def _test_failed_db_paths(self):
        """測試失敗的 DB 路徑"""
        failed_dbs = {
            'DB2858': '/DailyBuild/Merlin8/DB2858_Merlin8_FW_Android14_Ref_Plus_PreMP_GoogleGMS',
            'DB2575': '/DailyBuild/Merlin8/DB2575_Merlin8_FW_Android14_Google_Refplus_Wave_GoogleGMS',
            'DB2919': '/DailyBuild/Merlin8/DB2919_Merlin8_64Bit_Android14_Ref_Plus_Wave_Backup_GoogleGMS'
        }
        
        print(f"\n🔍 測試失敗的 DB 路徑")
        
        for db_name, path in failed_dbs.items():
            print(f"\n{'='*60}")
            print(f"🎯 測試 {db_name}")
            print(f"📍 路徑: {path}")
            print(f"{'='*60}")
            
            self._diagnose_sftp_path(path, db_name)
            
            # 詢問是否繼續下一個
            if db_name != list(failed_dbs.keys())[-1]:  # 不是最後一個
                if input(f"\n繼續測試下一個 DB? (Y/n): ").strip().lower() == 'n':
                    break
    
    def _test_common_paths(self):
        """測試常用路徑"""
        common_paths = [
            ('/DailyBuild/Merlin8/', 'Merlin8 建置根目錄'),
            ('/DailyBuild/', '建置根目錄'),
            ('/DailyBuild/Merlin8/DB2145_Merlin8_FW_Android14_Ref_Plus_GoogleGMS', 'DB2145 (已知可用)'),
        ]
        
        print(f"\n🔍 測試常用路徑")
        
        for path, description in common_paths:
            print(f"\n{'='*60}")
            print(f"🎯 測試: {description}")
            print(f"📍 路徑: {path}")
            print(f"{'='*60}")
            
            self._diagnose_sftp_path(path, description.split()[0])
    
    def _diagnose_sftp_path(self, path: str, db_name: str):
        """診斷單個 SFTP 路徑的詳細函數"""
        try:
            sftp = self.tool.sftp_manager._get_connection()[0]
            if not sftp:
                print("❌ 無法獲取 SFTP 連線")
                return
            
            # 檢查路徑是否存在
            try:
                print(f"📁 檢查路徑是否可訪問...")
                items = sftp.listdir_attr(path)
                print(f"✅ 路徑可訪問，包含 {len(items)} 個項目")
                
                # 分析內容
                directories = []
                files = []
                
                for item in items:
                    if item.st_mode & 0o40000:  # 是目錄
                        directories.append({
                            'name': item.filename,
                            'modified': datetime.fromtimestamp(item.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                        })
                    else:
                        files.append({
                            'name': item.filename,
                            'size': item.st_size,
                            'modified': datetime.fromtimestamp(item.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                        })
                
                print(f"📊 內容統計: {len(directories)} 個目錄, {len(files)} 個檔案")
                
                # 顯示目錄
                if directories:
                    print(f"\n📂 目錄列表 (前10個):")
                    for i, dir_info in enumerate(directories[:10]):
                        # 檢查是否符合版本格式
                        is_version = self.tool.sftp_manager._is_version_directory(dir_info['name'])
                        status = "✅" if is_version else "❌"
                        print(f"  {status} {i+1:2d}. {dir_info['name']:<40} ({dir_info['modified']})")
                    if len(directories) > 10:
                        print(f"      ... 還有 {len(directories)-10} 個目錄")
                
                # 檢查版本目錄
                version_dirs = []
                for dir_info in directories:
                    if self.tool.sftp_manager._is_version_directory(dir_info['name']):
                        version_dirs.append(dir_info)
                
                if version_dirs:
                    print(f"\n🎯 找到 {len(version_dirs)} 個版本目錄:")
                    for i, ver_dir in enumerate(version_dirs[:5]):
                        version_num = self.tool.sftp_manager._extract_version_number_flexible(ver_dir['name'])
                        print(f"  {i+1:2d}. {ver_dir['name']:<30} (版本: {version_num}, {ver_dir['modified']})")
                        
                        # 檢查版本目錄內容
                        try:
                            version_path = f"{path.rstrip('/')}/{ver_dir['name']}"
                            version_files = sftp.listdir(version_path)
                            
                            # 找 manifest 檔案
                            manifest_files = [f for f in version_files 
                                            if f.endswith('.xml') and 'manifest' in f.lower()]
                            xml_files = [f for f in version_files if f.endswith('.xml')]
                            
                            if manifest_files:
                                print(f"      ✅ 包含 {len(manifest_files)} 個 manifest 檔案:")
                                for mf in manifest_files[:3]:  # 最多顯示3個
                                    try:
                                        manifest_path = f"{version_path}/{mf}"
                                        file_stat = sftp.stat(manifest_path)
                                        size_kb = file_stat.st_size / 1024
                                        valid = "✅" if file_stat.st_size > 100000 else "⚠️"
                                        print(f"         {valid} {mf} ({size_kb:.1f} KB)")
                                    except:
                                        print(f"         ❓ {mf} (無法取得大小)")
                            elif xml_files:
                                print(f"      ⚠️  有 {len(xml_files)} 個 XML 檔案但沒有 manifest:")
                                for xf in xml_files[:3]:
                                    print(f"         - {xf}")
                            else:
                                print(f"      ❌ 沒有 XML 檔案 (共 {len(version_files)} 個檔案)")
                                # 顯示一些檔案樣本
                                sample_files = version_files[:5]
                                if sample_files:
                                    print(f"         檔案樣本: {', '.join(sample_files)}")
                        
                        except PermissionError:
                            print(f"      🚫 無權限訪問版本目錄")
                        except Exception as e:
                            print(f"      ❌ 檢查版本目錄失敗: {e}")
                else:
                    print(f"\n❌ 沒有找到版本目錄")
                    if directories:
                        print(f"   提示: 找到的目錄似乎不符合版本目錄的命名模式")
                        print(f"   支援的格式: 206_all_202507100000, 204_202507081101")
                        print(f"   前5個目錄: {', '.join([d['name'] for d in directories[:5]])}")
                
                # 顯示檔案（如果有）
                if files:
                    print(f"\n📄 檔案列表 (前5個):")
                    for i, file_info in enumerate(files[:5]):
                        size_mb = file_info['size'] / (1024*1024)
                        print(f"  {i+1:2d}. {file_info['name']:<30} ({size_mb:.1f} MB)")
            
            except FileNotFoundError:
                print(f"❌ 路徑不存在: {path}")
                self._suggest_alternative_paths(sftp, path, db_name)
            
            except PermissionError:
                print(f"🚫 權限被拒絕: {path}")
            
            except Exception as e:
                error_type = type(e).__name__
                print(f"❌ 檢查路徑時發生錯誤 ({error_type}): {e}")
        
        except Exception as e:
            print(f"❌ 診斷過程發生錯誤: {e}")
    
    def _suggest_alternative_paths(self, sftp, original_path: str, db_name: str):
        """建議替代路徑"""
        print(f"\n🔍 搜尋替代路徑...")
        
        try:
            # 檢查父目錄
            parent_path = os.path.dirname(original_path.rstrip('/'))
            print(f"   檢查父目錄: {parent_path}")
            
            parent_items = sftp.listdir_attr(parent_path)
            similar_dirs = []
            
            # 提取 DB 名稱進行模糊匹配
            db_base = db_name.replace('DB', '').lower() if 'DB' in db_name else db_name.lower()
            
            for item in parent_items:
                if item.st_mode & 0o40000:  # 是目錄
                    dir_name_lower = item.filename.lower()
                    if (db_name.lower() in dir_name_lower or 
                        db_base in dir_name_lower):
                        similar_dirs.append({
                            'name': item.filename,
                            'modified': datetime.fromtimestamp(item.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                        })
            
            if similar_dirs:
                print(f"🎯 在父目錄中找到 {len(similar_dirs)} 個可能的替代路徑:")
                for i, dir_info in enumerate(similar_dirs[:5]):
                    full_path = f"{parent_path}/{dir_info['name']}"
                    print(f"  {i+1}. {full_path}")
                    print(f"     (修改時間: {dir_info['modified']})")
            else:
                print(f"❌ 在父目錄中沒有找到類似的路徑")
                
                # 顯示父目錄中的所有目錄供參考
                all_dirs = [item.filename for item in parent_items if item.st_mode & 0o40000]
                if all_dirs:
                    print(f"   父目錄包含的所有目錄 (前10個):")
                    for dir_name in all_dirs[:10]:
                        print(f"     - {dir_name}")
                    if len(all_dirs) > 10:
                        print(f"     ... 還有 {len(all_dirs)-10} 個目錄")
        
        except Exception as e:
            print(f"❌ 搜尋替代路徑時發生錯誤: {e}")
    
    def test_version_detection(self):
        """測試版本目錄識別功能"""
        print("\n🔍 版本目錄識別測試 (支援新格式)")
        print("="*60)
        print("支援的格式:")
        print("  ✅ 206_all_202507100000  (version_all_timestamp)")
        print("  ✅ 204_202507081101      (version_timestamp)")
        print("  ✅ 465_all_202502170030_NG_uboot_fail (帶後綴)")
        print("  ✅ 466_202502171018_NG_uboot_fail (帶後綴)")
        print("="*60)
        
        # 測試模式選擇
        print("\n選擇測試模式:")
        print("1. 測試單個路徑的版本目錄")
        print("2. 測試失敗 DB 的版本目錄識別")
        print("3. 測試版本目錄格式檢測")
        print("4. 測試版本號提取邏輯")
        
        choice = input("請選擇 (1-4): ").strip()
        
        if choice == '1':
            self._test_single_path_versions()
        elif choice == '2':
            self._test_failed_db_versions()
        elif choice == '3':
            self._test_version_pattern_detection()
        elif choice == '4':
            self._test_version_extraction_logic()
        else:
            print("❌ 無效選擇")
    
    def _test_single_path_versions(self):
        """測試單個路徑的版本目錄"""
        path = input("\n請輸入要測試的 SFTP 路徑: ").strip()
        if not path:
            # 使用失敗的 DB 作為預設
            path = "/DailyBuild/Merlin8/DB2575_Merlin8_FW_Android14_Google_Refplus_Wave_GoogleGMS"
            print(f"使用預設路徑: {path}")
        
        print(f"\n🔍 測試路徑: {path}")
        
        # 連線到 SFTP
        if not self.tool.sftp_manager.connect():
            print("❌ SFTP 連線失敗")
            return
        
        try:
            self._analyze_version_directories(path)
        finally:
            self.tool.sftp_manager.disconnect()
    
    def _test_failed_db_versions(self):
        """測試失敗 DB 的版本目錄識別"""
        failed_dbs = {
            'DB2575': '/DailyBuild/Merlin8/DB2575_Merlin8_FW_Android14_Google_Refplus_Wave_GoogleGMS',
            'DB2858': '/DailyBuild/Merlin8/DB2858_Merlin8_FW_Android14_Ref_Plus_PreMP_GoogleGMS',
            'DB2919': '/DailyBuild/Merlin8/DB2919_Merlin8_64Bit_Android14_Ref_Plus_Wave_Backup_GoogleGMS'
        }
        
        print(f"\n🔍 測試失敗 DB 的版本目錄識別")
        
        # 連線到 SFTP
        if not self.tool.sftp_manager.connect():
            print("❌ SFTP 連線失敗")
            return
        
        try:
            for db_name, path in failed_dbs.items():
                print(f"\n{'='*60}")
                print(f"🎯 測試 {db_name}")
                print(f"📍 路徑: {path}")
                print(f"{'='*60}")
                
                self._analyze_version_directories(path)
                
                # 詢問是否繼續
                if db_name != list(failed_dbs.keys())[-1]:
                    if input(f"\n繼續測試下一個 DB? (Y/n): ").strip().lower() == 'n':
                        break
        finally:
            self.tool.sftp_manager.disconnect()
    
    def _test_version_pattern_detection(self):
        """測試版本目錄格式檢測"""
        path = input("\n請輸入要檢測的 SFTP 路徑: ").strip()
        if not path:
            path = "/DailyBuild/Merlin8/DB2575_Merlin8_FW_Android14_Google_Refplus_Wave_GoogleGMS"
            print(f"使用預設路徑: {path}")
        
        # 連線到 SFTP
        if not self.tool.sftp_manager.connect():
            print("❌ SFTP 連線失敗")
            return
        
        try:
            patterns = self.tool.sftp_manager.detect_version_directory_patterns(path)
            
            print(f"\n📊 版本目錄格式檢測結果:")
            if patterns:
                for pattern_type, directories in patterns.items():
                    print(f"\n🎯 {pattern_type} 格式 ({len(directories)} 個):")
                    for i, dir_name in enumerate(directories[:10]):  # 最多顯示10個
                        version_num = self.tool.sftp_manager._extract_version_number_flexible(dir_name)
                        print(f"  {i+1:2d}. {dir_name:<30} (版本: {version_num})")
                    if len(directories) > 10:
                        print(f"      ... 還有 {len(directories)-10} 個")
            else:
                print("❌ 沒有檢測到版本目錄格式")
        
        except Exception as e:
            print(f"❌ 檢測失敗: {e}")
        finally:
            self.tool.sftp_manager.disconnect()
    
    def _test_version_extraction_logic(self):
        """測試版本號提取邏輯"""
        print(f"\n🔍 測試版本號提取邏輯（專用格式）")
        
        # 測試案例（專門針對你提到的格式）
        test_cases = [
            # 主要的實際格式
            "206_all_202507100000",           # 格式1：version_all_timestamp
            "204_202507081101",               # 格式2：version_timestamp
            "465_all_202502170030_NG_uboot_fail",  # 格式1 + 後綴
            "466_202502171018_NG_uboot_fail",      # 格式2 + 後綴
            
            # 其他可能的變體
            "150_all_202501150000",
            "99_202412251030",
            "300_all_202508200000_FAIL",
            "101_202507050900_SUCCESS",
            
            # 簡單格式
            "206",                            # 純數字
            "v204",                           # v + 數字
            
            # 應該失敗的案例
            "invalid_206",                    # 字母開頭
            "206_invalid",                    # 不符合時間戳格式
            "abc_def_ghi",                    # 無數字
        ]
        
        print(f"\n📋 測試案例 (專門針對您的格式):")
        
        sftp_manager = self.tool.sftp_manager
        
        success_count = 0
        total_count = len(test_cases)
        
        for i, test_case in enumerate(test_cases, 1):
            is_version = sftp_manager._is_version_directory(test_case)
            version_num = sftp_manager._extract_version_number_flexible(test_case)
            
            if is_version and version_num:
                status = "✅"
                success_count += 1
            elif "invalid" in test_case.lower():
                status = "✅"  # 這個應該要失敗
                success_count += 1
            else:
                status = "❌"
            
            version_str = f"版本號: {version_num}" if version_num else "無法提取"
            expected = "(應該失敗)" if "invalid" in test_case.lower() else ""
            
            print(f"  {i:2d}. {status} {test_case:<35} → {version_str} {expected}")
        
        print(f"\n📊 測試結果: {success_count}/{total_count} 通過")
        
        if success_count == total_count:
            print("🎉 所有測試通過！版本識別邏輯正常運作")
        else:
            print("⚠️ 部分測試失敗，可能需要調整識別邏輯")
        
        # 測試版本解析
        print(f"\n🔍 測試版本目錄詳細解析:")
        detailed_test_cases = [
            ("206_all_202507100000", 1720627200),
            ("204_202507081101", 1720430460), 
            ("465_all_202502170030_NG_uboot_fail", 1739235000),
            ("466_202502171018_NG_uboot_fail", 1739239080),
            ("150", 1720000000),
        ]
        
        for dir_name, mtime in detailed_test_cases:
            parsed = sftp_manager._parse_version_directory(dir_name, mtime)
            if parsed:
                print(f"  ✅ {dir_name}:")
                print(f"     版本號: {parsed['version_number']}")
                print(f"     時間戳: {parsed.get('timestamp', 'N/A')}")
                print(f"     格式類型: {parsed['format_type']}")
                if parsed.get('has_suffix'):
                    print(f"     後綴: {parsed.get('suffix', 'N/A')}")
            else:
                print(f"  ❌ {dir_name}: 解析失敗")
    
    def _analyze_version_directories(self, path: str):
        """分析路徑中的版本目錄"""
        try:
            sftp = self.tool.sftp_manager._get_connection()[0]
            if not sftp:
                print("❌ 無法獲取 SFTP 連線")
                return
            
            # 檢查路徑是否存在
            try:
                items = sftp.listdir_attr(path)
                print(f"✅ 路徑可訪問，包含 {len(items)} 個項目")
            except FileNotFoundError:
                print(f"❌ 路徑不存在: {path}")
                return
            except Exception as e:
                print(f"❌ 訪問路徑失敗: {e}")
                return
            
            # 找出所有目錄
            all_dirs = [item for item in items if item.st_mode & 0o40000]
            print(f"📂 包含 {len(all_dirs)} 個目錄")
            
            if not all_dirs:
                print("❌ 沒有找到任何目錄")
                return
            
            # 顯示所有目錄（前10個）
            print(f"\n📋 所有目錄 (前10個):")
            for i, item in enumerate(all_dirs[:10]):
                modified = datetime.fromtimestamp(item.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                # 檢查是否符合版本格式
                is_version = self.tool.sftp_manager._is_version_directory(item.filename)
                status = "✅" if is_version else "❌"
                print(f"  {status} {i+1:2d}. {item.filename:<40} ({modified})")
            
            if len(all_dirs) > 10:
                print(f"      ... 還有 {len(all_dirs)-10} 個目錄")
            
            # 使用改進的版本識別邏輯
            sftp_manager = self.tool.sftp_manager
            version_dirs = sftp_manager._parse_and_sort_version_directories(items)
            
            if version_dirs:
                print(f"\n🎯 識別到 {len(version_dirs)} 個版本目錄 (按版本號和時間排序):")
                for i, ver_info in enumerate(version_dirs):
                    suffix_info = f" (⚠️ {ver_info['suffix']})" if ver_info.get('has_suffix') else ""
                    print(f"  {i+1:2d}. {ver_info['dir_name']:<40}{suffix_info}")
                    print(f"      版本號: {ver_info['version_number']}")
                    print(f"      格式類型: {ver_info['format_type']}")
                    if ver_info.get('timestamp'):
                        print(f"      時間戳: {ver_info['timestamp']}")
                    modified = datetime.fromtimestamp(ver_info['mtime']).strftime('%Y-%m-%d %H:%M:%S')
                    print(f"      修改時間: {modified}")
                    print()
                
                # 測試 manifest 搜尋 - 檢查前3個版本
                print(f"🔍 測試前3個版本的 manifest 搜尋:")
                for idx, ver_info in enumerate(version_dirs[:3]):
                    suffix_note = f" (⚠️ 注意: {ver_info['suffix']})" if ver_info.get('has_suffix') else ""
                    print(f"\n   版本 {idx+1}: {ver_info['dir_name']} (版本號: {ver_info['version_number']}){suffix_note}")
                    
                    version_path = f"{path}/{ver_info['dir_name']}"
                    try:
                        version_files = sftp.listdir(version_path)
                        manifest_files = [f for f in version_files if f.endswith('.xml') and 'manifest' in f.lower()]
                        
                        print(f"     版本目錄包含 {len(version_files)} 個檔案")
                        if manifest_files:
                            print(f"     ✅ 找到 {len(manifest_files)} 個 manifest 檔案:")
                            for mf in manifest_files:
                                try:
                                    manifest_path = f"{version_path}/{mf}"
                                    file_stat = sftp.stat(manifest_path)
                                    size_kb = file_stat.st_size / 1024
                                    valid = "✅" if file_stat.st_size > 100000 else "⚠️"
                                    print(f"        {valid} {mf} ({size_kb:.1f} KB)")
                                except:
                                    print(f"        ❓ {mf} (無法取得大小)")
                        else:
                            xml_files = [f for f in version_files if f.endswith('.xml')]
                            if xml_files:
                                print(f"     ⚠️ 有 {len(xml_files)} 個 XML 檔案但沒有 manifest")
                            else:
                                print(f"     ❌ 沒有找到 XML 檔案")
                    
                    except Exception as e:
                        print(f"     ❌ 檢查版本目錄內容失敗: {e}")
            
            else:
                print(f"\n❌ 沒有識別到版本目錄")
                print(f"   支援的格式:")
                print(f"   - 206_all_202507100000 (version_all_timestamp)")
                print(f"   - 204_202507081101 (version_timestamp)")  
                print(f"   - 465_all_202502170030_NG_uboot_fail (帶後綴)")
                print(f"   - 466_202502171018_NG_uboot_fail (帶後綴)")
                print(f"   目錄命名分析:")
                
                # 詳細分析為什麼沒有識別到
                recognized_count = 0
                for i, item in enumerate(all_dirs[:10]):
                    dir_name = item.filename
                    
                    if re.match(r'^\d+_all_\d{12}', dir_name):
                        recognized_count += 1
                        print(f"   ✅ {dir_name} → 符合 version_all_timestamp 格式")
                    elif re.match(r'^\d+_\d{12}', dir_name):
                        recognized_count += 1
                        print(f"   ✅ {dir_name} → 符合 version_timestamp 格式")
                    elif re.match(r'^\d+$', dir_name):
                        recognized_count += 1
                        print(f"   ✅ {dir_name} → 純數字格式")
                    else:
                        print(f"   ❌ {dir_name} → 不符合支援的版本格式")
                
                if recognized_count > 0:
                    print(f"\n💡 建議: 發現 {recognized_count} 個符合版本格式的目錄")
                    print(f"   這些應該會被新的識別邏輯正確識別")
        
        except Exception as e:
            print(f"❌ 分析版本目錄失敗: {e}")
    
    def run_interactive(self):
        """執行互動式介面"""
        print("\n歡迎使用 Manifest 定版工具！")
        print(f"版本: {__version__}")
        
        # 檢查是否有預設配置
        has_complete_defaults = all([
            config_manager.default_execution_config.get('mapping_table'),
            os.path.exists(config_manager.default_execution_config.get('mapping_table', ''))
        ])
        
        if has_complete_defaults:
            print("\n📌 偵測到完整的預設配置")
            if input("是否要使用預設配置快速執行? (y/N): ").strip().lower() == 'y':
                self.quick_execute_with_defaults()
                return
        
        while True:
            try:
                choice = self.display_menu()
                
                if choice == '0':
                    print("\n👋 再見！")
                    break
                elif choice == '1':
                    self.load_mapping_table()
                elif choice == '2':
                    self.setup_sftp()
                elif choice == '3':
                    self.select_db_type()
                elif choice == '4':
                    self.select_dbs()
                elif choice == '5':
                    self.setup_db_versions()
                elif choice == '6':
                    self.execute_pinning()
                elif choice == '7':
                    self.display_current_settings()
                elif choice == '8':
                    self.quick_execute_with_defaults()
                elif choice == '9':
                    self.setup_advanced_options()
                elif choice == '10':
                    self.test_jira_connection()
                elif choice == '11':
                    self.test_sftp_connection()
                elif choice == '12':
                    self.test_version_detection()
                else:
                    print("❌ 無效的選擇，請重新輸入")
                    
            except KeyboardInterrupt:
                print("\n\n⚠️ 使用者中斷")
                if input("確定要結束程式嗎? (Y/n): ").strip().lower() != 'n':
                    break
            except Exception as e:
                self.logger.error(f"發生錯誤: {str(e)}")
                print(f"❌ 發生錯誤: {str(e)}")
                if input("是否繼續? (Y/n): ").strip().lower() == 'n':
                    break
        
        # 清理資源
        resource_manager.cleanup_all()

# =====================================
# ===== 主程式 =====
# =====================================

def main():
    """主程式入口（改善版）"""
    parser = argparse.ArgumentParser(
        description='Manifest 定版工具 - 自動化 repo 定版處理',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
版本: {__version__}
作者: {__author__}
日期: {__date__}

範例:
  # 使用互動式介面
  python {sys.argv[0]}
  
  # 處理所有 DB
  python {sys.argv[0]} -m all_chip_mapping_table.xlsx -o ./output
  
  # 處理所有 master 類型的 DB
  python {sys.argv[0]} -m all_chip_mapping_table.xlsx -t master -o ./output
  
  # 處理指定的 DB
  python {sys.argv[0]} -m mapping.xlsx -d DB2302,DB2575 -o ./output
  
  # 指定 DB 版本
  python {sys.argv[0]} -m mapping.xlsx -d DB2302#3,DB2575#186
  
  # 測試模式（不實際執行）
  python {sys.argv[0]} -m mapping.xlsx --dry-run
  
  # 啟用 debug 模式
  python {sys.argv[0]} -m mapping.xlsx --debug
        """
    )
    
    # 基本參數
    parser.add_argument('-m', '--mapping', 
                        type=str,
                        help='Mapping table Excel 檔案路徑')
    
    parser.add_argument('-o', '--output', 
                        type=str,
                        help=f'輸出目錄 (預設: {config_manager.path_config["default_output_dir"]})')
    
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
                        help=f'SFTP 伺服器位址')
    
    parser.add_argument('--sftp-port', 
                        type=int,
                        help=f'SFTP 連接埠')
    
    parser.add_argument('--sftp-user', 
                        type=str,
                        help=f'SFTP 使用者名稱')
    
    parser.add_argument('--sftp-password', 
                        type=str,
                        help='SFTP 密碼')
    
    parser.add_argument('--sftp-timeout', 
                        type=int,
                        help=f'SFTP 連線逾時秒數')
    
    # 平行處理設定
    parser.add_argument('--parallel', 
                        type=int,
                        metavar='N',
                        help=f'平行處理的 worker 數量')
    
    parser.add_argument('--no-parallel', 
                        action='store_true',
                        help='關閉平行處理，使用循序處理')
    
    # Repo 設定
    parser.add_argument('--repo-jobs', 
                        type=int,
                        help=f'repo sync 的並行數')
    
    parser.add_argument('--repo-retry', 
                        type=int,
                        help=f'repo sync 失敗重試次數')
    
    # 其他選項
    parser.add_argument('--report-name', 
                        type=str,
                        help=f'報告檔案名稱')
    
    parser.add_argument('--dry-run', 
                        action='store_true',
                        help='測試模式，只顯示將要執行的動作，不實際執行')
    
    parser.add_argument('--debug', 
                        action='store_true',
                        help='啟用 debug 模式，顯示詳細日誌')
    
    parser.add_argument('--version', 
                        action='version',
                        version=f'%(prog)s {__version__}')
    
    # 解析參數
    args = parser.parse_args()
    
    # ===== 設定日誌等級 =====
    if args.debug:
        config_manager.log_config['level'] = logging.DEBUG
        logging.getLogger().setLevel(logging.DEBUG)
        for handler in logging.getLogger().handlers:
            handler.setLevel(logging.DEBUG)
        print("🔍 Debug 模式已啟用")
    
    # ===== 更新配置 =====
    overrides = {}
    
    if args.sftp_host:
        overrides['sftp_host'] = args.sftp_host
    if args.sftp_port:
        overrides['sftp_port'] = args.sftp_port
    if args.sftp_user:
        overrides['sftp_username'] = args.sftp_user
    if args.sftp_password:
        overrides['sftp_password'] = args.sftp_password
    if args.sftp_timeout:
        overrides['sftp_timeout'] = args.sftp_timeout
    
    if args.no_parallel:
        overrides['parallel_enable_parallel'] = False
    if args.parallel:
        overrides['parallel_max_workers'] = args.parallel
        overrides['parallel_enable_parallel'] = True
    
    if args.repo_jobs:
        overrides['repo_sync_jobs'] = args.repo_jobs
    if args.repo_retry:
        overrides['repo_sync_retry'] = args.repo_retry
    
    if overrides:
        config_manager.apply_overrides(overrides, source='command_line')
    
    if args.report_name:
        config_manager.path_config['report_filename'] = args.report_name
    
    # ===== 驗證配置 =====
    valid, errors = config_manager.validate_config()
    if not valid:
        print("❌ 配置驗證失敗:")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)
    
    # ===== 檢查是否為測試模式 =====
    if args.dry_run:
        print("\n" + "="*60)
        print("🧪 測試模式 (Dry Run) - 不會實際執行任何操作")
        print("="*60)
    
    # ===== 決定執行模式 =====
    if args.mapping:
        # 命令列模式
        print("\n" + "="*60)
        print(f"📋 Manifest 定版工具 v{__version__} - 命令列模式")
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
            tool.output_dir = args.output or config_manager.path_config['default_output_dir']
            os.makedirs(tool.output_dir, exist_ok=True)
            print(f"📁 輸出目錄: {tool.output_dir}")
            
            # Step 3: 連線到 SFTP
            print(f"\n🌐 連線到 SFTP 伺服器: {config_manager.sftp_config['host']}")
            if not tool.sftp_manager.connect():
                print("❌ 無法連線到 SFTP 伺服器")
                sys.exit(1)
            print("✅ SFTP 連線成功")
            
            try:
                # Step 4: 決定要處理的 DB 列表
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
                
                # Step 5: 處理額外的版本設定
                if args.versions:
                    version_specs = [v.strip() for v in args.versions.split(',')]
                    for version_spec in version_specs:
                        if '#' in version_spec:
                            db_name, version = version_spec.split('#', 1)
                            db_versions[db_name] = version
                    
                    print(f"📌 設定了 {len(db_versions)} 個 DB 的版本")
                
                # Step 6: 確認處理資訊
                print("\n" + "-"*40)
                print("📋 準備處理以下 DB:")
                for i, db in enumerate(db_list, 1):
                    version_info = f" (版本: {db_versions[db]})" if db in db_versions else " (最新版本)"
                    print(f"  {i:3d}. {db}{version_info}")
                print("-"*40)
                
                if not db_list:
                    print("❌ 沒有找到要處理的 DB")
                    sys.exit(1)
                
                # Step 7: 詢問確認（除非是測試模式）
                if not args.dry_run:
                    if sys.stdin.isatty():  # 檢查是否在互動式環境
                        confirm = input(f"\n確認要處理 {len(db_list)} 個 DB? (Y/n): ").strip().lower()
                        if confirm == 'n':
                            print("❌ 使用者取消操作")
                            sys.exit(0)
                
                # Step 8: 開始處理
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
                
                # Step 9: 產生報告
                if not args.dry_run:
                    print("\n📊 產生處理報告...")
                    report_path = os.path.join(
                        tool.output_dir, 
                        config_manager.path_config['report_filename']
                    )
                    tool.generate_report(report_path)
                
                # Step 10: 顯示結果摘要
                print("\n" + "="*60)
                print("✨ 處理完成！")
                print("="*60)
                print(f"📊 總 DB 數: {tool.report.total_dbs}")
                print(f"✅ 成功: {tool.report.successful_dbs}")
                print(f"❌ 失敗: {tool.report.failed_dbs}")
                print(f"⭐️ 跳過: {tool.report.skipped_dbs}")
                print(f"⏱️ 總耗時: {elapsed_time}")
                print(f"📁 輸出目錄: {tool.output_dir}")
                if not args.dry_run:
                    print(f"📊 報告檔案: {report_path}")
                print("="*60)
                
                # 如果有失敗的項目，顯示詳細資訊
                if tool.report.failed_dbs > 0:
                    print("\n❌ 失敗的 DB:")
                    for db in tool.report.db_details:
                        if db.status == DBStatus.FAILED:
                            print(f"  - {db.module}/{db.db_info}: {db.error_message}")
                
            finally:
                # 確保關閉 SFTP 連線
                print("\n📌 關閉 SFTP 連線...")
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
        
        finally:
            # 清理所有資源
            resource_manager.cleanup_all()
    
    else:
        # 互動式模式
        print("\n" + "="*60)
        print(f"🎮 Manifest 定版工具 v{__version__} - 互動式介面")
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
        
        finally:
            # 清理所有資源
            resource_manager.cleanup_all()

if __name__ == "__main__":
    main()