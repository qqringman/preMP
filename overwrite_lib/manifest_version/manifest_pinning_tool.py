#!/usr/bin/env python3
"""
Manifest Pinning Tool - 自動化定版工具 (改進版)
用於從 SFTP 下載 manifest 檔案並執行 repo 定版操作
改進版本：簡化 SFTP、改進報告格式、正常日誌輸出
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
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

# =====================================
# ===== 版本資訊 =====
# =====================================
__version__ = '2.1.1'
__author__ = 'Vince Lin'
__date__ = '2024-12-19'

# =====================================
# ===== 配置管理器 =====
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
            'timeout': 30,
            'retry_count': 3,
            'retry_delay': 2
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
            'report_filename': 'pinning_report.xlsx'
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
# ===== JIRA API 客戶端 =====
# =====================================

from jira import JIRA
import requests
from urllib.parse import quote
import urllib3

# 關閉 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class JiraAPIClient:
    """簡化版 JIRA API 客戶端"""
    
    def __init__(self):
        self.logger = setup_logger(self.__class__.__name__)
        self.session = None
        self._connected = False
        self.base_url = f"https://{config_manager.jira_config['site']}"
        
    def connect(self) -> bool:
        """連接到 JIRA"""
        try:
            username = config_manager.jira_config['username']
            password = config_manager.jira_config['password']
            
            self.session = requests.Session()
            self.session.auth = (username, password)
            self.session.headers.update({
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            })
            self.session.verify = False
            
            # 測試連接
            test_url = f"{self.base_url}/rest/api/2/myself"
            response = self.session.get(test_url, timeout=30)
            
            if response.status_code == 200:
                self._connected = True
                return True
            else:
                self.logger.error(f"JIRA 連接失敗: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"JIRA 連接失敗: {e}")
            return False

    def search_db_ticket(self, db_name: str, module: str = None) -> Optional[str]:
        """根據 DB 命名慣例搜尋對應的 JIRA ticket"""
        try:
            if not self._connected:
                if not self.connect():
                    return None
            
            # 根據命名慣例直接構建 ticket key
            db_number = db_name.replace('DB', '')
            possible_tickets = [
                f"MMQCDB-{db_number}",
                f"LGSWRD-{db_number}",
                f"RTK-{db_number}",
                f"DB-{db_number}",
            ]
            
            for ticket_key in possible_tickets:
                if self._check_ticket_exists(ticket_key):
                    return ticket_key
            
            return None
            
        except Exception as e:
            self.logger.error(f"搜尋 JIRA ticket 失敗: {e}")
            return None

    def _check_ticket_exists(self, ticket_key: str) -> bool:
        """檢查指定的 ticket 是否存在"""
        try:
            url = f"{self.base_url}/rest/api/2/issue/{ticket_key}"
            response = self.session.get(url, timeout=30)
            return response.status_code == 200
        except:
            return False

    def get_source_command_from_ticket(self, ticket_key: str) -> Optional[str]:
        """從 JIRA ticket 中提取 source command"""
        try:
            if not self._connected:
                if not self.connect():
                    return None
            
            url = f"{self.base_url}/rest/api/2/issue/{ticket_key}"
            response = self.session.get(url, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                fields = data.get('fields', {})
                
                # 檢查描述欄位
                description = fields.get('description', '')
                if description:
                    cmd = self._extract_repo_command(description)
                    if cmd:
                        return cmd
                
                # 檢查評論
                comments_data = fields.get('comment', {})
                comments = comments_data.get('comments', [])
                for comment in comments:
                    body = comment.get('body', '')
                    if body:
                        cmd = self._extract_repo_command(body)
                        if cmd:
                            return cmd
                
                return None
            
            return None
                
        except Exception as e:
            self.logger.error(f"從 ticket {ticket_key} 獲取 source command 失敗: {e}")
            return None

    def _extract_repo_command(self, text: str) -> Optional[str]:
        """提取 repo init 命令"""
        if not text or 'repo init' not in text:
            return None
        
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            
            # 尋找包含 repo init 的行
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
        
        cmd = cmd.rstrip('\n\r\\')
        return cmd.strip()

    def _is_valid_repo_command(self, cmd: str) -> bool:
        """驗證是否為有效的 repo init 命令"""
        if not cmd or not cmd.startswith('repo init'):
            return False
        
        required_parts = ['-u', '-b']
        return all(part in cmd for part in required_parts)

    def disconnect(self):
        """斷開 JIRA 連接"""
        self._connected = False
        if self.session:
            self.session.close()
            self.session = None

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
    """DB 資訊資料結構"""
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
    actual_source_cmd: Optional[str] = None
    sync_log_path: Optional[str] = None

    def to_dict(self) -> dict:
        """轉換為字典格式"""
        result = asdict(self)
        
        # 處理 Enum 和 datetime
        if isinstance(result['status'], DBStatus):
            result['status'] = result['status'].value
        if result['start_time']:
            result['start_time'] = result['start_time'].strftime('%Y-%m-%d %H:%M:%S')
        if result['end_time']:
            result['end_time'] = result['end_time'].strftime('%Y-%m-%d %H:%M:%S')
        
        # 移除無法序列化的物件
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
# ===== 資源管理器 =====
# =====================================

class ResourceManager:
    """統一管理所有系統資源"""
    
    def __init__(self):
        self.active_processes = {}
        self.sftp_connections = []
        self.lock = threading.Lock()
        self.logger = setup_logger(self.__class__.__name__)
        
        atexit.register(self.cleanup_all)
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """處理中斷信號"""
        print(f"\n🛑 收到中斷信號，清理所有進程...")
        
        # 原有的清理
        self.cleanup_all()
        
        # 🔥 新增：系統級強制清理
        print("🚨 執行系統級清理...")
        os.system("pkill -TERM -f 'repo sync' 2>/dev/null || true")
        os.system("pkill -TERM -f 'unbuffer.*repo' 2>/dev/null || true")
        time.sleep(2)
        os.system("pkill -KILL -f 'repo sync' 2>/dev/null || true")
        os.system("pkill -KILL -f 'unbuffer.*repo' 2>/dev/null || true")
        
        print("✅ 清理完成")
        sys.exit(0)
    
    def register_process(self, name: str, process: subprocess.Popen):
        """註冊新的子進程"""
        with self.lock:
            self.active_processes[name] = process
    
    def unregister_process(self, name: str):
        """取消註冊子進程"""
        with self.lock:
            if name in self.active_processes:
                del self.active_processes[name]
    
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
                        process.terminate()
                        process.wait(timeout=5)
                except:
                    try:
                        process.kill()
                    except:
                        pass
            
            # 關閉所有 SFTP 連線
            for conn in self.sftp_connections:
                try:
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
# ===== 改進版 SFTP 管理器（修復 Garbage packet 問題）=====
# =====================================

class SFTPManager:
    """改進版 SFTP 管理器 - 修復 type 3 unimplemented 錯誤"""
    
    def __init__(self):
        self.logger = setup_logger(self.__class__.__name__)
        self.config = config_manager.sftp_config
        self.sftp = None
        self.transport = None
        self.connected = False
        self._connection_lock = threading.Lock()
        # 快取伺服器能力
        self._server_capabilities = {
            'supports_listdir_attr': None,
            'supports_stat': None,
            'checked': False
        }
        
    def connect(self) -> bool:
        """建立 SFTP 連線"""
        with self._connection_lock:
            try:
                # 如果已連線，先清理
                if self.connected:
                    self.disconnect()
                
                self.logger.info(f"建立 SFTP 連線: {self.config['host']}:{self.config['port']}")
                
                # 重試連線
                for attempt in range(self.config['retry_count']):
                    try:
                        # 建立 Socket 連線
                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock.settimeout(self.config['timeout'])
                        
                        # 設定 socket 選項避免 Garbage packet
                        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                        
                        # 連接到伺服器
                        sock.connect((self.config['host'], self.config['port']))
                        
                        # 建立 Transport（修復 Garbage packet 的關鍵）
                        self.transport = paramiko.Transport(sock)
                        
                        # 設定較保守的參數避免協議問題
                        self.transport.set_keepalive(30)
                        self.transport.use_compression(False)  # 關閉壓縮
                        
                        # 開始 SSH 握手
                        self.transport.start_client()
                        
                        # 認證
                        self.transport.auth_password(
                            self.config['username'],
                            self.config['password']
                        )
                        
                        # 建立 SFTP 客戶端
                        self.sftp = paramiko.SFTPClient.from_transport(self.transport)
                        
                        # 測試連線並檢測伺服器能力
                        self._detect_server_capabilities()
                        
                        self.connected = True
                        resource_manager.register_sftp(self)
                        self.logger.info(f"SFTP 連線成功 (嘗試 {attempt + 1})")
                        return True
                        
                    except Exception as e:
                        self.logger.warning(f"SFTP 連線嘗試 {attempt + 1} 失敗: {e}")
                        self._cleanup_failed_connection()
                        
                        if attempt < self.config['retry_count'] - 1:
                            time.sleep(self.config['retry_delay'])
                
                self.logger.error("SFTP 連線失敗，已達最大重試次數")
                return False
                
            except Exception as e:
                self.logger.error(f"SFTP 連線過程發生錯誤: {e}")
                self._cleanup_failed_connection()
                return False
    
    def _detect_server_capabilities(self):
        """檢測 SFTP 伺服器支援的功能"""
        try:
            self.logger.debug("檢測 SFTP 伺服器能力...")
            
            # 測試基本 listdir
            try:
                self.sftp.listdir('.')
                self.logger.debug("✅ 基本 listdir 支援")
            except Exception as e:
                self.logger.warning(f"❌ 基本 listdir 不支援: {e}")
                raise Exception("伺服器不支援基本 SFTP 操作")
            
            # 測試 listdir_attr
            try:
                self.sftp.listdir_attr('.')
                self._server_capabilities['supports_listdir_attr'] = True
                self.logger.debug("✅ listdir_attr 支援")
            except Exception as e:
                self._server_capabilities['supports_listdir_attr'] = False
                self.logger.debug(f"❌ listdir_attr 不支援: {e}")
            
            # 測試 stat
            try:
                self.sftp.stat('.')
                self._server_capabilities['supports_stat'] = True
                self.logger.debug("✅ stat 支援")
            except Exception as e:
                self._server_capabilities['supports_stat'] = False
                self.logger.debug(f"❌ stat 不支援: {e}")
            
            self._server_capabilities['checked'] = True
            self.logger.info(f"伺服器能力檢測完成: listdir_attr={self._server_capabilities['supports_listdir_attr']}, stat={self._server_capabilities['supports_stat']}")
            
        except Exception as e:
            self.logger.warning(f"伺服器能力檢測失敗: {e}")
            # 設定為最保守的模式
            self._server_capabilities = {
                'supports_listdir_attr': False,
                'supports_stat': False,
                'checked': True
            }
    
    def _cleanup_failed_connection(self):
        """清理失敗的連線"""
        try:
            if self.sftp:
                self.sftp.close()
                self.sftp = None
            if self.transport:
                self.transport.close()
                self.transport = None
            self.connected = False
            self._server_capabilities['checked'] = False
        except:
            pass
    
    def disconnect(self):
        """安全斷開 SFTP 連線"""
        with self._connection_lock:
            try:
                if self.sftp:
                    self.sftp.close()
                    self.sftp = None
                if self.transport:
                    self.transport.close()
                    self.transport = None
                self.connected = False
                self._server_capabilities['checked'] = False
                self.logger.info("SFTP 連線已關閉")
            except Exception as e:
                self.logger.warning(f"關閉 SFTP 連線時發生錯誤: {e}")
    
    def _ensure_connected(self) -> bool:
        """確保連線有效"""
        if not self.connected or not self.sftp or not self.transport:
            return self.connect()
        
        # 測試連線是否仍然有效
        try:
            self.sftp.listdir('.')
            return True
        except:
            self.logger.info("SFTP 連線已斷開，重新連線...")
            return self.connect()
    
    def get_latest_version(self, sftp_path: str) -> Tuple[str, str, str]:
        """
        取得最新版本資訊（版號最大的）
        
        Args:
            sftp_path: SFTP 路徑
            
        Returns:
            (db_folder, db_version, full_path)
        """
        try:
            if not self._ensure_connected():
                raise Exception("無法建立 SFTP 連線")
            
            # 從路徑中提取基礎資訊
            path_parts = sftp_path.rstrip('/').split('/')
            db_folder = path_parts[-1] if path_parts else ''
            
            # 列出目錄內容
            try:
                items = self._safe_listdir(sftp_path)
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
            if not self._ensure_connected():
                raise Exception("無法建立 SFTP 連線")
            
            # 解析 db_info
            if '#' not in db_info:
                self.logger.warning(f"DB資訊格式錯誤: {db_info}")
                return self.get_latest_version(sftp_path)
            
            db_number, version_prefix = db_info.split('#')
            
            # 列出目錄找到對應的 DB 資料夾
            parent_path = '/'.join(sftp_path.rstrip('/').split('/')[:-1])
            items = self._safe_listdir(parent_path)
            
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
            version_items = self._safe_listdir(db_path)
            
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
    
    def find_latest_manifest(self, path: str, db_name: str = None, target_version: str = None) -> Optional[Tuple[str, str]]:
        """改進版：快速搜尋 manifest 檔案（強化錯誤處理）"""
        try:
            if not self._ensure_connected():
                raise Exception("無法建立 SFTP 連線")
            
            if target_version:
                self.logger.info(f"快速搜尋指定版本 {target_version}: {path}")
                return self._find_specific_version_manifest(path, target_version)
            else:
                self.logger.info(f"快速搜尋最新版本: {path}")
                return self._find_latest_version_manifest(path)
                
        except Exception as e:
            self.logger.error(f"搜索 manifest 失敗: {e}")
            return None

    def _find_latest_version_manifest(self, base_path: str) -> Optional[Tuple[str, str]]:
        """搜尋最新版本的 manifest - 強化 type 3 錯誤處理"""
        try:
            # 列出目錄
            version_dirs = []
            try:
                items = self._safe_listdir_with_details(base_path)
                
                for item_info in items:
                    try:
                        if item_info.get('is_dir', False):
                            dir_name = item_info['name']
                            version_num = self._extract_version_number(dir_name)
                            if version_num:
                                version_dirs.append({
                                    'name': dir_name,
                                    'version': int(version_num),
                                    'mtime': item_info.get('mtime', 0)
                                })
                    except Exception as e:
                        self.logger.debug(f"跳過問題目錄: {item_info.get('name', 'unknown')}, 錯誤: {e}")
                        continue
                        
            except Exception as e:
                self.logger.error(f"列出目錄失敗: {e}")
                return None
            
            if not version_dirs:
                raise Exception(f"在 {base_path} 中沒有找到版本目錄")
            
            # 按版本號降序排列（最新版本在前）
            version_dirs.sort(key=lambda x: (x['version'], x['mtime']), reverse=True)
            self.logger.info(f"找到 {len(version_dirs)} 個版本目錄，最新版本: {version_dirs[0]['version']}")
            
            # 只檢查前3個最新版本
            for version_dir in version_dirs[:3]:
                self.logger.info(f"檢查版本 {version_dir['version']} ({version_dir['name']})")
                manifest_path = self._try_get_manifest_from_dir(
                    base_path, 
                    version_dir['name'], 
                    str(version_dir['version'])
                )
                if manifest_path:
                    return manifest_path
            
            raise Exception("在最新版本目錄中找不到有效的 manifest")
            
        except Exception as e:
            self.logger.error(f"搜尋最新版本失敗: {e}")
            return None
        
    def _find_specific_version_manifest(self, base_path: str, version: str) -> Optional[Tuple[str, str]]:
        """搜尋指定版本的 manifest - 強化 type 3 錯誤處理"""
        try:
            self.logger.info(f"搜尋指定版本: {version}")
            
            # 嘗試列出目錄，如果失敗就用直接路徑方式
            matching_dirs = []
            try:
                items = self._safe_listdir_with_details(base_path)
                
                for item_info in items:
                    try:
                        # 檢查是否為目錄
                        if item_info.get('is_dir', False):
                            dir_name = item_info['name']
                            if self._matches_version(dir_name, version):
                                matching_dirs.append({
                                    'name': dir_name,
                                    'mtime': item_info.get('mtime', 0)
                                })
                                self.logger.debug(f"找到匹配版本目錄: {dir_name}")
                    except Exception as e:
                        self.logger.debug(f"跳過問題項目: {item_info.get('name', 'unknown')}, 錯誤: {e}")
                        continue
                        
            except Exception as e:
                self.logger.warning(f"列出目錄失敗，嘗試直接路徑: {e}")
                return self._try_direct_version_paths(base_path, version)
            
            if not matching_dirs:
                # 如果沒找到，嘗試直接構建路徑
                return self._try_direct_version_paths(base_path, version)
            
            # 按時間排序，取最新的
            matching_dirs.sort(key=lambda x: x['mtime'], reverse=True)
            
            # 嘗試每個匹配的版本目錄
            for dir_info in matching_dirs:
                manifest_path = self._try_get_manifest_from_dir(base_path, dir_info['name'], version)
                if manifest_path:
                    return manifest_path
            
            # 如果匹配目錄都失敗，嘗試直接路徑
            return self._try_direct_version_paths(base_path, version)
            
        except Exception as e:
            self.logger.error(f"搜尋指定版本失敗: {e}")
            return None

    def _safe_listdir(self, path: str) -> list:
        """最安全的列目錄方法 - 只使用基本 listdir"""
        try:
            return self.sftp.listdir(path)
        except Exception as e:
            self.logger.error(f"列出目錄失敗: {path}, 錯誤: {e}")
            raise
    
    def _safe_listdir_with_details(self, path: str) -> list:
        """安全的列出目錄內容，根據伺服器能力選擇方法"""
        try:
            result = []
            
            # 如果支援 listdir_attr，優先使用
            if self._server_capabilities.get('supports_listdir_attr', False):
                try:
                    items = self.sftp.listdir_attr(path)
                    for item in items:
                        result.append({
                            'name': item.filename,
                            'is_dir': self._is_directory_from_stat(item),
                            'mtime': getattr(item, 'st_mtime', 0),
                            'size': getattr(item, 'st_size', 0)
                        })
                    return result
                except Exception as e:
                    error_msg = str(e).lower()
                    if 'unimplemented' in error_msg or 'type 3' in error_msg:
                        self.logger.warning(f"listdir_attr 不支援，切換到基本模式: {e}")
                        self._server_capabilities['supports_listdir_attr'] = False
                    else:
                        raise
            
            # 回退到基本 listdir + 個別 stat
            self.logger.debug("使用基本 listdir 模式")
            filenames = self.sftp.listdir(path)
            
            for filename in filenames:
                item_info = {
                    'name': filename,
                    'is_dir': False,  # 預設為檔案
                    'mtime': 0,
                    'size': 0
                }
                
                # 嘗試獲取詳細資訊
                if self._server_capabilities.get('supports_stat', True):
                    try:
                        full_path = f"{path}/{filename}"
                        stat_info = self.sftp.stat(full_path)
                        item_info.update({
                            'is_dir': self._is_directory_from_stat(stat_info),
                            'mtime': getattr(stat_info, 'st_mtime', 0),
                            'size': getattr(stat_info, 'st_size', 0)
                        })
                    except Exception as e:
                        error_msg = str(e).lower()
                        if 'unimplemented' in error_msg or 'type 3' in error_msg:
                            self.logger.debug(f"stat 不支援: {filename}")
                            self._server_capabilities['supports_stat'] = False
                        else:
                            self.logger.debug(f"stat 失敗: {filename}, {e}")
                        
                        # 使用啟發式方法判斷是否為目錄
                        item_info['is_dir'] = self._guess_is_directory(filename)
                else:
                    # 使用啟發式方法
                    item_info['is_dir'] = self._guess_is_directory(filename)
                
                result.append(item_info)
            
            return result
            
        except Exception as e:
            self.logger.error(f"列出目錄詳細資訊失敗: {path}, 錯誤: {e}")
            raise
    
    def _is_directory_from_stat(self, stat_obj) -> bool:
        """從 stat 對象判斷是否為目錄"""
        try:
            return bool(stat_obj.st_mode & 0o40000)
        except:
            return False
    
    def _guess_is_directory(self, filename: str) -> bool:
        """啟發式方法猜測是否為目錄"""
        # 如果檔名包含明顯的副檔名，可能是檔案
        common_extensions = ['.xml', '.txt', '.log', '.zip', '.tar', '.gz', '.json', '.csv']
        filename_lower = filename.lower()
        
        for ext in common_extensions:
            if filename_lower.endswith(ext):
                return False
        
        # 如果看起來像版本目錄格式，假設是目錄
        if re.match(r'^\d+(_all)?(_\d{12})?(_.*)?$', filename):
            return True
        
        # 預設假設是目錄（在搜尋 manifest 的情境下比較安全）
        return True

    def _try_direct_version_paths(self, base_path: str, version: str) -> Optional[Tuple[str, str]]:
        """當找不到版本目錄時，嘗試直接構建可能的路徑"""
        try:
            import datetime
            today = datetime.datetime.now()
            
            self.logger.info(f"嘗試直接路徑搜尋版本 {version}")
            
            # 生成可能的時間戳（最近30天，每3天一個）
            for days_back in range(0, 30, 3):
                date = today - datetime.timedelta(days=days_back)
                
                # 生成多個可能的時間格式
                timestamps = [
                    date.strftime("%Y%m%d0000"),  # 202508170000
                    date.strftime("%Y%m%d1200"),  # 202508171200
                    date.strftime("%Y%m%d1800"),  # 202508171800
                    date.strftime("%Y%m%d2300"),  # 202508172300
                ]
                
                for timestamp in timestamps:
                    # 嘗試不同的目錄格式
                    possible_dirs = [
                        f"{version}_{timestamp}",
                        f"{version}_all_{timestamp}",
                        f"{version}_all_{timestamp}_no-release",
                        f"{version}_all_{timestamp}_backup",
                        f"{version}_{timestamp}_backup",
                    ]
                    
                    for dir_name in possible_dirs:
                        try:
                            manifest_path = self._try_get_manifest_from_dir(base_path, dir_name, version)
                            if manifest_path:
                                self.logger.info(f"✅ 透過直接路徑找到: {dir_name}")
                                return manifest_path
                        except Exception as e:
                            self.logger.debug(f"直接路徑失敗: {dir_name}, {e}")
                            continue
            
            return None
            
        except Exception as e:
            self.logger.debug(f"直接路徑搜尋失敗: {e}")
            return None
            
    def _try_get_manifest_from_dir(self, base_path: str, dir_name: str, version: str) -> Optional[Tuple[str, str]]:
        """嘗試從指定目錄獲取 manifest - 使用最基本的方法"""
        try:
            version_path = f"{base_path}/{dir_name}"
            
            # 直接構建可能的 manifest 檔案名
            possible_manifests = [
                f"manifest_{version}.xml",
                "manifest.xml",
                f"default_{version}.xml", 
                "default.xml",
                f"{version}.xml"
            ]
            
            for manifest_name in possible_manifests:
                manifest_full_path = f"{version_path}/{manifest_name}"
                
                try:
                    # 使用最基本的檢查方法
                    if self._file_exists_and_valid(manifest_full_path):
                        self.logger.info(f"✅ 找到有效 manifest: {manifest_name} (路徑: {dir_name})")
                        return manifest_full_path, manifest_name
                        
                except Exception as e:
                    self.logger.debug(f"檢查檔案失敗: {manifest_name}, {e}")
                    continue
            
            return None
            
        except Exception as e:
            self.logger.debug(f"檢查目錄失敗: {dir_name}, {e}")
            return None

    def _file_exists_and_valid(self, file_path: str) -> bool:
        """最基本的檔案存在性和有效性檢查"""
        try:
            # 如果 stat 可用，使用 stat
            if self._server_capabilities.get('supports_stat', True):
                try:
                    stat_info = self.sftp.stat(file_path)
                    file_size = getattr(stat_info, 'st_size', 0)
                    return file_size > 1000  # manifest 檔案應該大於 1KB
                except Exception as e:
                    error_msg = str(e).lower()
                    if 'unimplemented' in error_msg or 'type 3' in error_msg:
                        self._server_capabilities['supports_stat'] = False
                    elif 'no such file' in error_msg or 'not found' in error_msg:
                        return False
                    else:
                        raise
            
            # 如果 stat 不可用，嘗試打開檔案來檢查
            try:
                with self.sftp.open(file_path, 'r') as f:
                    # 讀取前幾個字節檢查是否像 XML
                    header = f.read(100).decode('utf-8', errors='ignore')
                    return '<?xml' in header or '<manifest' in header
            except Exception:
                return False
                
        except Exception:
            return False
                    
    def _matches_version(self, dir_name: str, target_version: str) -> bool:
        """檢查目錄名是否匹配指定版本"""
        patterns = [
            rf'^{target_version}_\d{{12}}$',                    # 5_202508170000
            rf'^{target_version}_all_\d{{12}}$',                # 702_all_202508092300  
            rf'^{target_version}_all_\d{{12}}_.*$',             # 669_all_202507142300_no-release
            rf'^{target_version}_\d{{12}}_.*$',                 # 5_202508170000_backup
        ]
        
        for pattern in patterns:
            if re.match(pattern, dir_name):
                return True
        return False
    
    def _extract_version_number(self, name: str) -> Optional[str]:
        """提取版本號"""
        patterns = [
            r'^(\d+)_all_\d{12}',      # 702_all_202508092300
            r'^(\d+)_all_\d{12}_',     # 669_all_202507142300_no-release
            r'^(\d+)_\d{12}',          # 5_202508170000
            r'^(\d+)_\d{12}_',         # 5_202508170000_backup
            r'^(\d+)$',                # 5
            r'^v(\d+)',                # v5
        ]
        
        for pattern in patterns:
            match = re.search(pattern, name)
            if match:
                return match.group(1)
        
        return None
    
    def download_file(self, remote_path: str, local_path: str) -> bool:
        """下載檔案"""
        try:
            if not self._ensure_connected():
                return False
            
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            filename = os.path.basename(remote_path)
            self.logger.info(f"開始下載: {filename}")
            
            # 獲取檔案大小（如果支援的話）
            file_size = 0
            if self._server_capabilities.get('supports_stat', True):
                try:
                    file_stat = self.sftp.stat(remote_path)
                    file_size = file_stat.st_size
                    self.logger.debug(f"檔案大小: {file_size} bytes")
                except Exception as e:
                    error_msg = str(e).lower()
                    if 'unimplemented' in error_msg or 'type 3' in error_msg:
                        self._server_capabilities['supports_stat'] = False
                        self.logger.debug("stat 不支援，跳過檔案大小檢查")
                    else:
                        self.logger.debug(f"無法獲取檔案大小: {e}")
            
            # 下載檔案
            self.sftp.get(remote_path, local_path)
            
            # 驗證下載
            if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
                actual_size = os.path.getsize(local_path)
                self.logger.info(f"下載完成: {filename} ({actual_size} bytes)")
                
                # 驗證檔案大小是否一致（如果有的話）
                if file_size > 0 and actual_size != file_size:
                    self.logger.warning(f"檔案大小不一致: 預期 {file_size}, 實際 {actual_size}")
                
                return True
            else:
                self.logger.error(f"下載的檔案無效或為空: {local_path}")
                return False
                
        except Exception as e:
            self.logger.error(f"下載檔案失敗: {e}")
            return False

# =====================================
# ===== Source Command 管理器 =====
# =====================================

class SourceCommandManager:
    """管理不同 DB 的 source command"""
    
    def __init__(self):
        self.logger = setup_logger(self.__class__.__name__)
        self.jira_client = JiraAPIClient()
        self.cache = {}
        
    def get_source_command(self, db_info: DBInfo, mapping_df: pd.DataFrame = None) -> Optional[str]:
        """根據 DB 資訊獲取對應的 source command"""
        db_name = db_info.db_info
        
        # 檢查快取
        if db_name in self.cache:
            self.logger.info(f"使用快取的 source command for {db_name}")
            return self.cache[db_name]
        
        # 從 JIRA 搜尋
        self.logger.info(f"從 JIRA 搜尋 {db_name} 的 source command")
        ticket_key = self.jira_client.search_db_ticket(db_name, db_info.module)
        if ticket_key:
            # 更新 jira_link
            db_info.jira_link = f"https://{config_manager.jira_config['site']}/browse/{ticket_key}"
            self.logger.info(f"找到 JIRA ticket: {ticket_key}")
            
            cmd = self.jira_client.get_source_command_from_ticket(ticket_key)
            if cmd:
                self.cache[db_name] = cmd
                self.logger.info(f"成功從 JIRA 獲取 source command")
                return cmd
        
        self.logger.warning(f"無法從 JIRA 獲取 {db_name} 的 source command")
        return None
    
    def clear_cache(self):
        """清除所有快取"""
        self.cache.clear()

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
            self.logger.info(f"成功載入 mapping table: {len(self.df)} 筆資料")
            return True
        except Exception as e:
            self.logger.error(f"載入 Excel 失敗: {str(e)}")
            return False
    
    def get_db_info_list(self, db_type: str = 'all') -> List[DBInfo]:
        """取得 DB 資訊列表"""
        db_list = []
        
        if self.df is None:
            return db_list
        
        type_columns = {
            'master': ('DB_Type', 'DB_Info', 'DB_Folder', 'SftpPath'),
            'premp': ('premp_DB_Type', 'premp_DB_Info', 'premp_DB_Folder', 'premp_SftpPath'),
            'mp': ('mp_DB_Type', 'mp_DB_Info', 'mp_DB_Folder', 'mp_SftpPath'),
            'mpbackup': ('mpbackup_DB_Type', 'mpbackup_DB_Info', 'mpbackup_DB_Folder', 'mpbackup_SftpPath')
        }
        
        types_to_process = type_columns.keys() if db_type == 'all' else [db_type]
        
        for idx, row in self.df.iterrows():
            for dtype in types_to_process:
                if dtype not in type_columns:
                    continue
                    
                cols = type_columns[dtype]
                db_info_col = cols[1]
                
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

# =====================================
# ===== Repo 管理器 =====
# =====================================

class RepoManager:
    """Repo 指令管理器"""
    
    def __init__(self):
        self.logger = setup_logger(self.__class__.__name__)
        self.lock = threading.Lock()
    
    def check_repo_exists(self, work_dir: str) -> bool:
        """檢查 .repo 目錄是否存在"""
        repo_dir = os.path.join(work_dir, '.repo')
        exists = os.path.exists(repo_dir)
        self.logger.info(f"檢查 .repo 目錄: {work_dir} -> {'存在' if exists else '不存在'}")
        return exists
    
    def run_command(self, cmd: str, cwd: str = None, timeout: int = None) -> Tuple[bool, str]:
        """同步執行指令"""
        try:
            self.logger.debug(f"執行指令: {cmd}")
            result = subprocess.run(
                cmd,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            if result.returncode == 0:
                self.logger.debug(f"指令執行成功")
                return True, result.stdout
            else:
                self.logger.warning(f"指令執行失敗 (返回碼: {result.returncode})")
                return False, result.stderr
                
        except subprocess.TimeoutExpired:
            self.logger.error(f"指令執行超時")
            return False, "Command timeout"
        except Exception as e:
            self.logger.error(f"指令執行異常: {e}")
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
                self.logger.debug("舊 .repo 目錄清理成功")
            except Exception as e:
                self.logger.warning(f"清理 .repo 失敗: {e}")
        
        self.logger.info(f"執行 repo init: {init_cmd}")
        success, output = self.run_command(
            init_cmd,
            cwd=work_dir,
            timeout=config_manager.repo_config['init_timeout']
        )
        
        if success:
            self.logger.info("Repo init 執行成功")
        else:
            self.logger.error(f"Repo init 失敗: {output}")
        
        return success
    
    def apply_manifest(self, work_dir: str, manifest_file: str) -> bool:
        """應用 manifest 檔案"""
        try:
            manifest_name = os.path.basename(manifest_file)
            self.logger.info(f"應用 manifest: {manifest_name}")
            
            repo_dir = os.path.join(work_dir, '.repo')
            manifests_dir = os.path.join(repo_dir, 'manifests')
            
            if not os.path.exists(manifests_dir):
                self.logger.error(f"Manifests 目錄不存在: {manifests_dir}")
                return False
            
            # 複製 manifest 檔案
            dest_file = os.path.join(manifests_dir, manifest_name)
            import shutil
            shutil.copy2(manifest_file, dest_file)
            self.logger.debug(f"複製 manifest: {manifest_file} -> {dest_file}")
            
            # 切換到指定的 manifest
            switch_cmd = f"{config_manager.repo_config['repo_command']} init -m {manifest_name}"
            self.logger.info(f"切換 manifest: {switch_cmd}")
            
            success, output = self.run_command(
                switch_cmd,
                cwd=work_dir,
                timeout=config_manager.repo_config['init_timeout']
            )
            
            if success:
                self.logger.info(f"成功切換到 manifest: {manifest_name}")
                return True
            else:
                self.logger.error(f"切換 manifest 失敗: {output}")
                return False
                
        except Exception as e:
            self.logger.error(f"應用 manifest 失敗: {str(e)}")
            return False
    
    def start_repo_sync_async(self, work_dir: str, db_name: str) -> subprocess.Popen:
        """🎯 修復版本 - 使用 unbuffer 確保實時輸出"""
        try:
            self.logger.info(f"{db_name}: 啟動 unbuffer 版本 repo sync")
            
            # 檢查工作目錄
            if not os.path.exists(os.path.join(work_dir, '.repo')):
                raise Exception(f"工作目錄沒有 .repo: {work_dir}")
            
            # 檢查 unbuffer 是否可用
            try:
                subprocess.run(['which', 'unbuffer'], check=True, capture_output=True, timeout=5)
                use_unbuffer = True
            except:
                use_unbuffer = False
                self.logger.warning(f"{db_name}: unbuffer 不可用，使用 script 方法")
            
            # 建立日誌
            log_dir = os.path.join(work_dir, 'logs')
            os.makedirs(log_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            method_name = "unbuffer" if use_unbuffer else "script"
            log_file = os.path.join(log_dir, f'repo_sync_{method_name}_{timestamp}.log')
            
            # 寫入初始信息
            with open(log_file, 'w', encoding='utf-8') as f:
                f.write(f"=== Fixed Repo Sync Log for {db_name} ===\n")
                f.write(f"開始時間: {datetime.now()}\n")
                f.write(f"工作目錄: {work_dir}\n")
                f.write(f"使用方法: {method_name}\n\n")
            
            # 準備命令
            repo_cmd = config_manager.repo_config['repo_command']
            jobs = min(config_manager.repo_config['sync_jobs'], 4)
            
            if use_unbuffer:
                # 🎯 使用 unbuffer 方法（已驗證有效）
                cmd_parts = [
                    'unbuffer',
                    repo_cmd, 'sync', 
                    f'-j{jobs}', 
                    '--verbose', 
                    '--force-sync'
                ]
                
                process = subprocess.Popen(
                    cmd_parts,
                    cwd=work_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=0,
                    preexec_fn=os.setsid
                )
            else:
                # 備用：使用 script 方法
                shell_cmd = f"""
    cd "{work_dir}"
    echo "[SCRIPT] 進程啟動，PID: $$" >> "{log_file}"
    script -fq /dev/null -c "{repo_cmd} sync -j{jobs} --verbose --force-sync" | tee -a "{log_file}"
    echo "[SCRIPT] 進程結束，時間: $(date)" >> "{log_file}"
    """
                
                process = subprocess.Popen(
                    ['bash', '-c', shell_cmd],
                    cwd=work_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
            
            # 🎯 創建實時日誌寫入線程（關鍵改進）
            def log_writer():
                try:
                    with open(log_file, 'a', encoding='utf-8', buffering=1) as f:
                        f.write(f"[UNBUFFER] 進程啟動，PID: {process.pid}\n")
                        f.write(f"[UNBUFFER] 開始時間: {datetime.now()}\n\n")
                        f.flush()
                        
                        # 🔥 進度追蹤變數
                        last_reported_progress = -1
                        last_report_time = datetime.now()
                        message_count = 0
                        
                        if use_unbuffer:
                            while True:
                                line = process.stdout.readline()
                                if line:
                                    # 📝 所有內容都寫入文件（不變）
                                    f.write(line)
                                    f.flush()
                                    
                                    # 🔥 智能過濾 console 輸出
                                    line_clean = line.strip()
                                    message_count += 1
                                    
                                    # ✅ 只報告重要的進度變化
                                    if "Syncing:" in line_clean and "%" in line_clean:
                                        import re
                                        progress_match = re.search(r'Syncing:\s*(\d+)%\s*\((\d+)/(\d+)\)', line_clean)
                                        if progress_match:
                                            current_progress = int(progress_match.group(1))
                                            current_count = int(progress_match.group(2))
                                            total_count = int(progress_match.group(3))
                                            
                                            # 🎯 只在以下情況報告進度：
                                            should_report = (
                                                last_reported_progress == -1 or  # 第一次
                                                current_progress - last_reported_progress >= 5 or  # 進度增加5%以上
                                                current_progress % 10 == 0 or  # 每10%里程碑
                                                current_progress >= 95  # 接近完成時
                                            )
                                            
                                            if should_report:
                                                # 計算速度
                                                current_time = datetime.now()
                                                elapsed = (current_time - last_report_time).total_seconds()
                                                
                                                speed_info = ""
                                                if last_reported_progress > 0 and elapsed > 0:
                                                    progress_diff = current_progress - last_reported_progress
                                                    speed = progress_diff / (elapsed / 60)  # %/分鐘
                                                    if speed > 0:
                                                        remaining_time = (100 - current_progress) / speed
                                                        speed_info = f" (預計剩餘: {remaining_time:.0f}分鐘)"
                                                
                                                # 📊 簡潔的進度報告
                                                # self.logger.info(
                                                #    f"{db_name}: {current_progress}% "
                                                #    f"({current_count}/{total_count}){speed_info}"
                                                #)
                                                
                                                last_reported_progress = current_progress
                                                last_report_time = current_time
                                    
                                    # ⚠️ 報告錯誤和警告
                                    elif any(keyword in line_clean.lower() for keyword in 
                                        ['error:', 'fatal:', 'failed', 'timeout', 'exception', 'abort']):
                                        self.logger.warning(f"{db_name}: {line_clean}")
                                    
                                    # 🎉 報告重要里程碑
                                    elif any(phrase in line_clean.lower() for phrase in
                                        ['sync has finished', 'completed successfully', 'repo sync complete']):
                                        self.logger.info(f"{db_name}: 同步完成！")
                                    
                                    # 🚫 不報告的內容：
                                    # - "Skipped fetching project"
                                    # - "fetching project" 
                                    # - "..working.."
                                    # - 重複的進度信息
                                    
                                elif process.poll() is not None:
                                    break
                        
                        return_code = process.poll()
                        f.write(f"\n[UNBUFFER] 進程結束，返回碼: {return_code}\n")
                        f.write(f"[UNBUFFER] 結束時間: {datetime.now()}\n")
                        f.write(f"[UNBUFFER] 總處理消息數: {message_count}\n")
                        f.flush()
                        
                        # 📈 最終報告
                        if return_code == 0:
                            self.logger.info(f"{db_name}: ✅ 同步成功完成")
                        else:
                            self.logger.error(f"{db_name}: ❌ 同步失敗 (返回碼: {return_code})")
                        
                except Exception as e:
                    self.logger.error(f"{db_name}: 日誌寫入錯誤: {e}")
            
            # 啟動日誌線程
            if use_unbuffer:  # 只有 unbuffer 需要日誌線程
                log_thread = threading.Thread(target=log_writer, daemon=True)
                log_thread.start()
                process._log_thread = log_thread
            
            # 驗證啟動
            time.sleep(2)
            if process.poll() is not None:
                raise Exception(f"進程立即失敗，返回碼: {process.poll()}")
            
            # 保存進程信息
            process._log_file_path = log_file
            process._db_name = db_name
            process._start_time = datetime.now()
            
            resource_manager.register_process(db_name, process)
            self.logger.info(f"{db_name}: repo sync 啟動成功 (PID: {process.pid})")
            
            return process
            
        except Exception as e:
            self.logger.error(f"{db_name}: 啟動失敗: {e}")
            return None
    
    def check_process_status(self, db_name: str, process: subprocess.Popen) -> Optional[int]:
        """改進的進程狀態檢查"""
        with self.lock:
            if process:
                try:
                    poll = process.poll()
                    
                    # 🔥 加強日誌
                    self.logger.debug(f"{db_name}: 檢查進程狀態 PID={process.pid}, poll={poll}")
                    
                    if poll is not None:
                        # 🔥 進程已結束，記錄詳細信息
                        self.logger.info(f"{db_name}: 進程已結束，返回碼={poll}")
                        
                        # 正確關閉文件句柄
                        if hasattr(process, '_log_file_handle') and process._log_file_handle:
                            try:
                                process._log_file_handle.flush()
                                process._log_file_handle.close()
                                self.logger.debug(f"{db_name}: 日誌文件句柄已關閉")
                            except Exception as e:
                                self.logger.warning(f"{db_name}: 關閉日誌句柄失敗: {e}")
                        
                        resource_manager.unregister_process(db_name)
                        
                        # 🔥 寫入完成標記到日誌
                        if hasattr(process, '_log_file_path'):
                            try:
                                with open(process._log_file_path, 'a') as f:
                                    f.write(f"\n=== 進程結束 ===\n")
                                    f.write(f"返回碼: {poll}\n")
                                    f.write(f"結束時間: {datetime.now()}\n")
                            except:
                                pass
                        
                        return poll
                    else:
                        # 🔥 進程仍在運行，但驗證 PID 是否真的存在
                        try:
                            os.kill(process.pid, 0)  # 檢查進程是否存在
                            self.logger.debug(f"{db_name}: 進程 {process.pid} 確實在運行")
                        except OSError:
                            self.logger.warning(f"{db_name}: 進程 {process.pid} 不存在但 poll() 返回 None")
                            return -1  # 進程異常消失
                    
                    return None
                    
                except Exception as e:
                    self.logger.error(f"{db_name}: 檢查進程狀態時出錯: {e}")
                    return -1
            
            return None
    
    def export_manifest(self, work_dir: str, output_file: str = "vp_manifest.xml") -> bool:
        """導出 manifest"""
        cmd = f"{config_manager.repo_config['repo_command']} manifest -r -o {output_file}"
        self.logger.info(f"導出 manifest: {cmd}")
        
        success, output = self.run_command(cmd, cwd=work_dir, timeout=60)
        
        if success:
            output_path = os.path.join(work_dir, output_file)
            if os.path.exists(output_path):
                self.logger.info(f"成功導出 manifest: {output_path}")
                return True
        
        self.logger.error(f"導出 manifest 失敗: {output}")
        return False

# =====================================
# ===== 主要處理類別 =====
# =====================================

class ManifestPinningTool:
    """Manifest 定版工具（改進版）"""

    def __init__(self):
        self.logger = setup_logger(self.__class__.__name__)
        self.sftp_manager = SFTPManager()
        self.repo_manager = RepoManager()
        self.mapping_reader = MappingTableReader()
        self.source_cmd_manager = SourceCommandManager()
        self.report = PinningReport()
        self.output_dir = config_manager.path_config['default_output_dir']
        self.dry_run = False
        
        # 線程安全鎖
        self._sftp_lock = threading.Lock()

    def load_mapping_table(self, file_path: str) -> bool:
        """載入 mapping table"""
        return self.mapping_reader.load_excel(file_path)

    def get_all_dbs(self, db_type: str = 'all') -> List[DBInfo]:
        """取得所有 DB 資訊"""
        return self.mapping_reader.get_db_info_list(db_type)

    def process_db_phase1(self, db_info: DBInfo) -> DBInfo:
        """改進版 Phase 1 處理 - 線程安全"""
        db_info.start_time = datetime.now()
        
        try:
            self.logger.info(f"開始處理 {db_info.db_info} (Phase 1)")
            
            # 建立本地目錄
            local_path = os.path.join(self.output_dir, db_info.module, db_info.db_info)
            os.makedirs(local_path, exist_ok=True)
            db_info.local_path = local_path
            
            # Step 1: 使用鎖保護所有 SFTP 操作
            with self._sftp_lock:
                self.logger.info(f"{db_info.db_info}: 快速搜尋 manifest (線程安全)")
                
                # 確保 SFTP 連線有效
                if not self.sftp_manager._ensure_connected():
                    raise Exception("無法建立 SFTP 連線")
                
                target_version = db_info.version
                result = self.sftp_manager.find_latest_manifest(
                    db_info.sftp_path, 
                    db_info.db_info,
                    target_version
                )
                
                if not result:
                    raise Exception("找不到 manifest 檔案")
                
                manifest_full_path, manifest_name = result
                db_info.manifest_full_path = manifest_full_path
                db_info.manifest_file = manifest_name
                
                # 提取版本號
                if not db_info.version:
                    match = re.match(r'manifest_(\d+)\.xml', manifest_name)
                    if match:
                        db_info.version = match.group(1)
                        self.logger.info(f"{db_info.db_info}: 檢測到版本 {db_info.version}")
                
                # 下載到本地
                local_manifest = os.path.join(local_path, manifest_name)
                if not self.sftp_manager.download_file(manifest_full_path, local_manifest):
                    raise Exception("下載 manifest 失敗")
                
                self.logger.info(f"{db_info.db_info}: manifest 下載完成: {manifest_name}")
            
            # SFTP 操作完成，鎖已釋放，其他操作可以並行
            
            # Step 2: 檢查 repo 狀態
            db_info.has_existing_repo = self.repo_manager.check_repo_exists(local_path)
            
            # Step 3: 獲取 source command
            self.logger.info(f"{db_info.db_info}: 獲取 source command")
            source_cmd = self.source_cmd_manager.get_source_command(db_info, self.mapping_reader.df)
            if not source_cmd:
                raise Exception("無法取得 source command")
            
            db_info.actual_source_cmd = source_cmd
            self.logger.info(f"{db_info.db_info}: source command 獲取成功")
            
            # Step 4: 執行 repo init
            self.logger.info(f"{db_info.db_info}: 執行 repo 初始化")
            if not db_info.has_existing_repo:
                if not self.repo_manager.repo_init(local_path, source_cmd):
                    raise Exception("Repo init 失敗")
            
            # 應用 manifest
            if not self.repo_manager.apply_manifest(local_path, local_manifest):
                raise Exception("套用 manifest 失敗")
            
            self.logger.info(f"{db_info.db_info}: repo 初始化完成")
            
            # Step 5: 啟動 repo sync
            if not self.dry_run:
                self.logger.info(f"{db_info.db_info}: 啟動 repo sync")
                process = self.repo_manager.start_repo_sync_async(local_path, db_info.db_info)
                if not process:
                    raise Exception("啟動 repo sync 失敗")
                
                db_info.sync_process = process
                self.logger.info(f"{db_info.db_info}: repo sync 已啟動 (PID: {process.pid})")
            else:
                db_info.status = DBStatus.SKIPPED
                self.logger.info(f"{db_info.db_info}: 測試模式 - 跳過 repo sync")
            
            self.logger.info(f"{db_info.db_info}: Phase 1 完成")
            
        except Exception as e:
            db_info.status = DBStatus.FAILED
            db_info.error_message = str(e)
            self.logger.error(f"{db_info.db_info}: Phase 1 失敗 - {str(e)}")
        # 🔥 新增：確保當前線程的 SFTP 操作完全結束
        finally:
            # 強制釋放 SFTP 鎖（如果當前線程持有的話）
            if hasattr(self, '_sftp_lock'):
                try:
                    # 鎖會在 with 語句結束時自動釋放，這裡只是確保
                    pass
                except:
                    pass
        
        return db_info

    def process_db_phase2(self, db_info: DBInfo) -> DBInfo:
        """處理 DB 的第二階段：完成工作"""
        try:
            self.logger.info(f"{db_info.db_info}: 開始 Phase 2")
            
            if self.dry_run:
                db_info.status = DBStatus.SKIPPED
                db_info.end_time = datetime.now()
                self.logger.info(f"{db_info.db_info}: 測試模式完成")
                return db_info
            
            # 檢查 sync 進程狀態
            if db_info.sync_process:
                poll = self.repo_manager.check_process_status(
                    db_info.db_info, 
                    db_info.sync_process
                )
                
                if poll is None:
                    self.logger.debug(f"{db_info.db_info}: repo sync 仍在執行中")
                    return db_info  # 還在執行中
                elif poll != 0:
                    raise Exception(f"Repo sync 失敗 (返回碼: {poll})")
            
            # 導出 manifest
            self.logger.info(f"{db_info.db_info}: 導出版本資訊")
            if not self.repo_manager.export_manifest(db_info.local_path):
                raise Exception("導出 manifest 失敗")
            
            # 完成
            db_info.status = DBStatus.SUCCESS
            db_info.end_time = datetime.now()
            
            elapsed = db_info.end_time - db_info.start_time
            self.logger.info(f"{db_info.db_info}: 處理完成 (耗時: {elapsed})")
            
        except Exception as e:
            db_info.status = DBStatus.FAILED
            db_info.error_message = str(e)
            db_info.end_time = datetime.now()
            self.logger.error(f"{db_info.db_info}: Phase 2 失敗 - {str(e)}")
        
        return db_info

    def process_dbs_async(self, db_list: List[str], db_versions: Dict[str, str] = None):
        """異步處理多個 DB - 徹底避免 SFTP 衝突"""
        db_versions = db_versions or {}
        db_infos = []
        
        # 準備 DB 資訊
        all_db_infos = self.get_all_dbs('all')
        
        for db_name in db_list:
            if '#' in db_name:
                db_name, version = db_name.split('#', 1)
            else:
                version = db_versions.get(db_name)
            
            for db_info in all_db_infos:
                if db_info.db_info == db_name:
                    db_info.version = version
                    db_infos.append(db_info)
                    break
        
        if not db_infos:
            self.logger.error("沒有找到要處理的 DB")
            return

        self.logger.info(f"開始處理 {len(db_infos)} 個 DB")
        
        try:
            # Phase 1: 準備和啟動 sync
            self.logger.info("執行 Phase 1: 準備工作和啟動同步")
            
            with ThreadPoolExecutor(max_workers=config_manager.parallel_config['max_workers']) as executor:
                futures = {executor.submit(self.process_db_phase1, db_info): db_info for db_info in db_infos}
                
                phase1_results = []
                for future in as_completed(futures):
                    try:
                        result = future.result(timeout=300)
                        phase1_results.append(result)
                    except Exception as e:
                        db_info = futures[future]
                        self.logger.error(f"{db_info.db_info}: Phase 1 異常 - {e}")
                        db_info.status = DBStatus.FAILED
                        db_info.error_message = str(e)
                        phase1_results.append(db_info)
            
            # 🔥 關鍵修復：Phase 1 完成後立即斷開所有 SFTP 連線
            self.logger.info("Phase 1 完成，斷開所有 SFTP 連線以避免衝突")
            try:
                if hasattr(self, 'sftp_manager') and self.sftp_manager:
                    self.sftp_manager.disconnect()
                    self.logger.debug("主 SFTP 連線已斷開")
            except Exception as e:
                self.logger.debug(f"斷開主 SFTP 連線時發生錯誤: {e}")

            # 等待所有 sync 完成（增強版監控）
            if not self.dry_run:
                self.logger.info("等待所有 repo sync 完成...（增強版進度監控）")
                self._wait_for_all_syncs_enhanced(phase1_results)  # 👈 使用新的函數
            
            with ThreadPoolExecutor(max_workers=config_manager.parallel_config['max_workers']) as executor:
                futures = {executor.submit(self.process_db_phase2, db_info): db_info for db_info in phase1_results}
                
                for future in as_completed(futures):
                    try:
                        result = future.result(timeout=60)
                        self.report.add_db(result)
                    except Exception as e:
                        db_info = futures[future]
                        self.logger.error(f"{db_info.db_info}: Phase 2 異常 - {e}")
                        db_info.status = DBStatus.FAILED
                        db_info.error_message = str(e)
                        self.report.add_db(db_info)
            
            self.logger.info("所有 DB 處理完成")
            
        except Exception as e:
            self.logger.error(f"處理過程發生錯誤: {e}")

    def _wait_for_all_syncs_safe(self, db_results: List[DBInfo]):
        """完整版進度監控 - 包含錯誤處理和重試機制"""
        max_wait_time = config_manager.repo_config['sync_timeout']
        start_wait = time.time()
        
        active_syncs = [db for db in db_results if db.sync_process and db.status != DBStatus.FAILED]
        self.logger.info(f"監控 {len(active_syncs)} 個活躍的 repo sync 進程")
        
        # 初始化進度追蹤
        progress_tracker = {}
        for db_info in active_syncs:
            progress_tracker[db_info.db_info] = {
                'start_time': db_info.start_time or datetime.now(),
                'last_log_size': 0,
                'estimated_progress': 0,
                'current_activity': '初始化中...',
                'log_file': self._get_sync_log_file(db_info),
                'last_check_time': datetime.now(),
                'error_count': 0
            }
        
        check_interval = 30  # 30秒檢查一次
        
        while True:
            all_complete = True
            elapsed = int(time.time() - start_wait)
            
            print("\n" + "="*100)
            print(f"📊 Repo Sync 進度監控 - 已等待 {elapsed}s")
            print("="*100)
            
            for db_info in active_syncs:
                if db_info.status == DBStatus.FAILED:
                    continue
                
                db_name = db_info.db_info
                tracker = progress_tracker[db_name]
                
                # 構建包含版本信息的顯示名稱
                manifest_info = ""
                if db_info.manifest_file:
                    manifest_info = f" ({db_info.manifest_file})"
                elif db_info.version:
                    manifest_info = f" (v{db_info.version})"
                
                display_name = f"{db_name}{manifest_info}"
                
                if db_info.sync_process:
                    try:
                        poll = db_info.sync_process.poll()
                        
                        if poll is None:  # 仍在運行
                            all_complete = False
                            
                            # 🔧 檢查是否有錯誤需要處理
                            error_detected = self._check_for_sync_errors(db_info, tracker)
                            
                            if error_detected:
                                # 嘗試處理錯誤
                                if self._handle_sync_failure(db_info, error_detected):
                                    tracker['current_activity'] = f"檢測到錯誤: {error_detected}，正在重試..."
                                    tracker['error_count'] += 1
                                else:
                                    # 重試失敗，標記為失敗
                                    db_info.status = DBStatus.FAILED
                                    db_info.error_message = error_detected
                                    runtime = datetime.now() - tracker['start_time']
                                    print(f"❌ {display_name:30s} | 失敗     |   0% | "
                                        f"用時 {str(runtime).split('.')[0]:8s} | {error_detected}")
                                    continue
                            
                            # 更新進度信息
                            self._update_progress_info(db_info, tracker)
                            
                            # 構建詳細的活動信息
                            activity_text = tracker['current_activity']
                            
                            # 添加當前項目信息
                            if tracker.get('current_project'):
                                project_short = tracker['current_project'].split('/')[-1]
                                activity_text = f"{activity_text} [{project_short}]"
                            
                            # 添加下載速度
                            if tracker.get('download_speed'):
                                activity_text = f"{activity_text} {tracker['download_speed']}"
                            
                            # 添加錯誤計數（如果有的話）
                            if tracker['error_count'] > 0:
                                activity_text = f"{activity_text} (重試:{tracker['error_count']})"
                            
                            # 顯示詳細狀態
                            runtime = datetime.now() - tracker['start_time']
                            print(f"🔄 {display_name:30s} | 運行中 | {tracker['estimated_progress']:3d}% | "
                                f"用時 {str(runtime).split('.')[0]:8s} | {activity_text}")
                            
                            # 檢查超時
                            if time.time() - start_wait > max_wait_time:
                                self.logger.warning(f"{db_name}: repo sync 超時，強制終止")
                                try:
                                    db_info.sync_process.terminate()
                                    db_info.sync_process.wait(timeout=5)
                                except:
                                    try:
                                        db_info.sync_process.kill()
                                    except:
                                        pass
                                db_info.status = DBStatus.FAILED
                                db_info.error_message = "Sync 超時"
                                print(f"⏰ {display_name:30s} | 超時終止")
                                
                        elif poll == 0:  # 成功完成
                            runtime = datetime.now() - tracker['start_time']
                            self.logger.info(f"{db_name}: repo sync 成功完成")
                            print(f"✅ {display_name:30s} | 完成     | 100% | "
                                f"用時 {str(runtime).split('.')[0]:8s} | Sync 成功完成")
                            
                        else:  # 失敗
                            runtime = datetime.now() - tracker['start_time']
                            error_msg = f"Sync 失敗 (返回碼: {poll})"
                            
                            # 嘗試從日誌中獲取更詳細的錯誤信息
                            detailed_error = self._extract_error_from_log(tracker.get('log_file', ''))
                            if detailed_error:
                                error_msg = f"{error_msg} - {detailed_error}"
                            
                            # 嘗試處理失敗
                            if self._handle_sync_failure(db_info, error_msg):
                                tracker['current_activity'] = "進程失敗，正在重試..."
                                tracker['error_count'] += 1
                                all_complete = False  # 還在重試中
                            else:
                                db_info.status = DBStatus.FAILED
                                db_info.error_message = error_msg
                                print(f"❌ {display_name:30s} | 失敗     |   0% | "
                                    f"用時 {str(runtime).split('.')[0]:8s} | {error_msg}")
                            
                    except Exception as e:
                        self.logger.error(f"{db_name}: 檢查進程狀態失敗: {e}")
                        db_info.status = DBStatus.FAILED
                        db_info.error_message = f"進程監控失敗: {e}"
                        print(f"⚠️  {display_name:30s} | 監控錯誤 |   0% | {str(e)[:30]}")
            
            # 顯示總體統計
            running_count = sum(1 for db in active_syncs 
                            if db.sync_process and db.sync_process.poll() is None 
                            and db.status != DBStatus.FAILED)
            completed_count = sum(1 for db in active_syncs 
                                if db.sync_process and db.sync_process.poll() == 0)
            failed_count = sum(1 for db in active_syncs if db.status == DBStatus.FAILED)
            retry_count = sum(1 for db in active_syncs 
                            if progress_tracker.get(db.db_info, {}).get('error_count', 0) > 0)
            
            print("-"*100)
            print(f"📈 總計: 運行中 {running_count} | 完成 {completed_count} | 失敗 {failed_count} | 重試中 {retry_count}")
                        
            if all_complete or (time.time() - start_wait) > max_wait_time:
                break
            
            # 等待下次檢查
            time.sleep(check_interval)
        
        # 最終統計
        completed = sum(1 for db in active_syncs if db.sync_process and db.sync_process.poll() == 0)
        failed = sum(1 for db in active_syncs if db.status == DBStatus.FAILED)
        total_retries = sum(progress_tracker.get(db.db_info, {}).get('error_count', 0) for db in active_syncs)
        
        print(f"\n🏁 Repo sync 最終統計:")
        print(f"   ✅ 成功: {completed}")
        print(f"   ❌ 失敗: {failed}")
        print(f"   🔄 總重試次數: {total_retries}")
        
        self.logger.info(f"🏁 Repo sync 完成統計: 成功 {completed}, 失敗 {failed}, 總重試 {total_retries}")

    def _handle_sync_failure(self, db_info: DBInfo, error_msg: str) -> bool:
        """處理 sync 失敗並嘗試重試"""
        self.logger.warning(f"{db_info.db_info}: Sync 錯誤 - {error_msg}")
        
        # 初始化重試計數
        if not hasattr(db_info, 'retry_count'):
            db_info.retry_count = 0
        
        # 檢查是否是可重試的錯誤
        retryable_errors = [
            'broken pipe', 'connection', 'timeout', 'network', 'temporary failure',
            'unable to connect', 'connection refused', 'connection timed out',
            'socket timeout', 'ssl error', 'certificate', 'dns'
        ]
        
        is_retryable = any(err in error_msg.lower() for err in retryable_errors)
        max_retries = 3  # 最多重試3次
        
        if is_retryable and db_info.retry_count < max_retries:
            db_info.retry_count += 1
            
            # 計算重試延遲（指數退避）
            retry_delay = min(30 * (2 ** (db_info.retry_count - 1)), 300)  # 最多等5分鐘
            
            self.logger.info(f"{db_info.db_info}: 準備重試 (第 {db_info.retry_count}/{max_retries} 次)，{retry_delay}秒後開始")
            
            try:
                # 清理舊進程
                if db_info.sync_process:
                    try:
                        if db_info.sync_process.poll() is None:
                            db_info.sync_process.terminate()
                            db_info.sync_process.wait(timeout=10)
                    except:
                        try:
                            db_info.sync_process.kill()
                        except:
                            pass
                    finally:
                        resource_manager.unregister_process(db_info.db_info)
                
                # 等待重試延遲
                import time
                time.sleep(retry_delay)
                
                # 重新啟動 repo sync
                self.logger.info(f"{db_info.db_info}: 開始第 {db_info.retry_count} 次重試")
                process = self.repo_manager.start_repo_sync_async(
                    db_info.local_path, 
                    db_info.db_info
                )
                
                if process:
                    db_info.sync_process = process
                    self.logger.info(f"{db_info.db_info}: 重試成功啟動 (PID: {process.pid})")
                    return True
                else:
                    self.logger.error(f"{db_info.db_info}: 重試啟動失敗")
                    
            except Exception as e:
                self.logger.error(f"{db_info.db_info}: 重試過程中發生異常: {e}")
        
        # 重試失敗或不可重試
        if db_info.retry_count >= max_retries:
            self.logger.error(f"{db_info.db_info}: 已達最大重試次數 ({max_retries})，標記為失敗")
        else:
            self.logger.error(f"{db_info.db_info}: 錯誤不可重試，標記為失敗")
        
        return False

    def _check_for_sync_errors(self, db_info: DBInfo, tracker: dict) -> str:
        """檢查 sync 過程中的錯誤"""
        try:
            log_file = tracker.get('log_file', '')
            
            if not log_file or not os.path.exists(log_file):
                return ""
            
            current_size = os.path.getsize(log_file)
            last_size = tracker.get('last_log_size', 0)
            
            if current_size <= last_size:
                # 日誌沒有增長，檢查是否卡住
                last_check = tracker.get('last_check_time', datetime.now())
                if (datetime.now() - last_check).total_seconds() > 300:  # 5分鐘沒有日誌更新
                    return "日誌停止更新，可能進程卡住"
            
            tracker['last_log_size'] = current_size
            tracker['last_check_time'] = datetime.now()
            
            # 讀取新增的日誌內容
            try:
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    f.seek(last_size)
                    new_content = f.read()
                    
                    # 檢查各種錯誤模式
                    error_patterns = [
                        (r'brokenpipeerror|broken pipe', 'Broken pipe error'),
                        (r'connection.*refused', 'Connection refused'),
                        (r'connection.*timeout|timeout.*connection', 'Connection timeout'),
                        (r'ssl.*error|certificate.*error', 'SSL/Certificate error'),
                        (r'unable to connect', 'Unable to connect'),
                        (r'network.*unreachable', 'Network unreachable'),
                        (r'temporary failure', 'Temporary failure'),
                        (r'fatal:.*clone', 'Clone failed'),
                        (r'error:.*fetch', 'Fetch failed'),
                    ]
                    
                    for pattern, error_type in error_patterns:
                        if re.search(pattern, new_content, re.IGNORECASE):
                            return error_type
                            
            except Exception as e:
                self.logger.debug(f"檢查錯誤時讀取日誌失敗: {e}")
            
            return ""
            
        except Exception as e:
            self.logger.debug(f"錯誤檢查異常: {e}")
            return ""

    def _extract_error_from_log(self, log_file: str) -> str:
        """從日誌文件中提取詳細錯誤信息"""
        try:
            if not log_file or not os.path.exists(log_file):
                return ""
            
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lines = content.split('\n')
                
                # 查找錯誤行
                error_lines = []
                for line in lines[-50:]:  # 檢查最後50行
                    if any(keyword in line.lower() for keyword in ['error:', 'fatal:', 'exception:', 'failed:']):
                        error_lines.append(line.strip())
                
                if error_lines:
                    return error_lines[-1]  # 返回最後一個錯誤
                    
        except Exception as e:
            self.logger.debug(f"提取錯誤信息失敗: {e}")
        
        return ""

    def _get_sync_log_file(self, db_info: DBInfo) -> str:
        """獲取 sync 日誌文件路径 - 優先使用 unbuffer 版本"""
        try:
            log_dir = os.path.join(db_info.local_path, 'logs')
            if os.path.exists(log_dir):
                # 尋找最新的日誌文件，優先選擇 unbuffer 版本
                log_files = []
                for f in os.listdir(log_dir):
                    if f.startswith('repo_sync_') and f.endswith('.log'):
                        file_path = os.path.join(log_dir, f)
                        mtime = os.path.getmtime(file_path)
                        
                        # 🔥 給不同類型的日誌不同優先級
                        priority = 0
                        if 'unbuffer' in f:
                            priority = 100  # 最高優先級
                        elif 'script' in f:
                            priority = 50
                        elif 'hotfix' in f or 'fixed' in f:
                            priority = 25
                        # 舊版本的日誌優先級為 0
                        
                        log_files.append((priority, mtime, file_path))
                
                if log_files:
                    # 按優先級和修改時間排序
                    log_files.sort(key=lambda x: (x[0], x[1]), reverse=True)
                    latest_log = log_files[0][2]
                    self.logger.debug(f"{db_info.db_info}: 使用日誌文件: {os.path.basename(latest_log)}")
                    return latest_log
            
            self.logger.debug(f"{db_info.db_info}: 日誌目錄不存在: {log_dir}")
        except Exception as e:
            self.logger.debug(f"{db_info.db_info}: 獲取日誌文件失敗: {e}")
        
        return ""

    def _update_progress_info(self, db_info: DBInfo, tracker: dict):
        """更新進度信息 - 專門優化 unbuffer 輸出解析"""
        try:
            log_file = tracker.get('log_file')
            
            # 🔥 每次都重新獲取日誌文件，確保使用最新的 unbuffer 日誌
            current_log_file = self._get_sync_log_file(db_info)
            if current_log_file and current_log_file != log_file:
                tracker['log_file'] = current_log_file
                log_file = current_log_file
                self.logger.debug(f"{db_info.db_info}: 切換到新日誌文件: {os.path.basename(log_file)}")
            
            if not log_file or not os.path.exists(log_file):
                tracker['current_activity'] = '等待日誌...'
                tracker['estimated_progress'] = self._get_time_based_progress(tracker)
                return
            
            # 🔥 優化的日誌解析 - 專門處理 unbuffer 格式
            try:
                file_size = os.path.getsize(log_file)
                
                # 只讀取最後 2KB 避免處理大文件
                read_size = min(file_size, 2048)
                
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    f.seek(max(0, file_size - read_size))
                    content = f.read()
                    lines = content.split('\n')[-15:]  # 最後15行
                
                # 解析最新的同步狀態
                latest_progress = 0
                latest_activity = "同步中..."
                current_project = ""
                total_projects = 0
                current_count = 0
                
                # 🔥 重點：解析 unbuffer 輸出的特定格式
                for line in reversed(lines):
                    line = line.strip()
                    if not line:
                        continue
                    
                    # 解析 "Syncing: X% (current/total) time | jobs | project" 格式
                    if "Syncing:" in line and "%" in line:
                        import re
                        
                        # 匹配進度百分比和計數
                        progress_match = re.search(r'Syncing:\s*(\d+)%\s*\((\d+)/(\d+)\)', line)
                        if progress_match:
                            latest_progress = int(progress_match.group(1))
                            current_count = int(progress_match.group(2))
                            total_projects = int(progress_match.group(3))
                            
                            # 提取當前處理的項目
                            # 格式通常是: "... | X jobs | time project_path @ ..."
                            if '|' in line:
                                parts = line.split('|')
                                for part in parts:
                                    part = part.strip()
                                    # 尋找包含項目路径的部分
                                    if '@' in part:
                                        project_info = part.split('@')[-1].strip()
                                    elif '/' in part and 'job' not in part and ':' not in part:
                                        project_info = part
                                    else:
                                        continue
                                    
                                    # 提取項目名稱
                                    if '/' in project_info:
                                        current_project = project_info.split('/')[-1]
                                    else:
                                        current_project = project_info
                                    break
                            
                            # 構建活動描述
                            latest_activity = f"同步: {current_count}/{total_projects}"
                            if current_project:
                                # 限制項目名稱長度
                                project_name = current_project[:20] + "..." if len(current_project) > 20 else current_project
                                latest_activity += f" - {project_name}"
                            
                            break
                    
                    # 🔥 解析其他狀態信息
                    elif "Fetching project" in line:
                        project_match = re.search(r'Fetching project\s+([^\s]+)', line)
                        if project_match:
                            project_path = project_match.group(1)
                            current_project = project_path.split('/')[-1]
                            latest_activity = f"獲取: {current_project}"
                    
                    elif "Skipped fetching project" in line:
                        project_match = re.search(r'Skipped fetching project\s+([^\s]+)', line)
                        if project_match:
                            project_path = project_match.group(1)
                            current_project = project_path.split('/')[-1]
                            latest_activity = f"跳過: {current_project}"
                
                # 🔥 更新追蹤信息
                if latest_progress > 0:
                    tracker['estimated_progress'] = latest_progress
                else:
                    # 如果沒有解析到進度，使用時間估算
                    tracker['estimated_progress'] = self._get_time_based_progress(tracker)
                
                tracker['current_activity'] = latest_activity
                tracker['current_project'] = current_project
                tracker['total_projects'] = total_projects
                tracker['current_count'] = current_count
                tracker['last_update'] = datetime.now()
                
                # 🔥 調試信息（可選）
                if latest_progress > 0:
                    self.logger.debug(f"{db_info.db_info}: 解析成功 - {latest_progress}% ({current_count}/{total_projects}) {current_project}")
                    
            except Exception as e:
                self.logger.debug(f"{db_info.db_info}: 解析日誌失敗: {e}")
                tracker['current_activity'] = '解析失敗'
                tracker['estimated_progress'] = self._get_time_based_progress(tracker)
                
        except Exception as e:
            self.logger.debug(f"{db_info.db_info}: 進度更新失敗: {e}")
            tracker['current_activity'] = '更新失敗'
            tracker['estimated_progress'] = self._get_time_based_progress(tracker)

    def _get_time_based_progress(self, tracker: dict) -> int:
        """基於時間的進度估算"""
        runtime_minutes = (datetime.now() - tracker['start_time']).total_seconds() / 60
        # 每分鐘約1.5%的進度，最多95%
        return min(int(runtime_minutes * 1.5), 95)

    def _extract_progress_from_lines(self, lines: list) -> int:
        """從日誌行中提取進度百分比"""
        for line in reversed(lines):
            # 尋找百分比
            match = re.search(r'(\d+)%', line)
            if match:
                percent = int(match.group(1))
                if 0 <= percent <= 100:
                    return percent
        return None

    def _extract_project_from_lines(self, lines: list) -> str:
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
                
            # 🔥 改進的模式，包含更多 repo sync 的實際輸出
            project_patterns = [
                # 標準模式
                r'Fetching project\s+([^\s]+)',
                r'Skipped fetching project\s+([^\s]+)',
                r'Checking out project\s+([^\s]+)',
                
                # Git 相關輸出
                r'remote:\s+.*?([a-zA-Z0-9_/\-\.]+/[a-zA-Z0-9_/\-\.]+)',
                r'From\s+.*?:([a-zA-Z0-9_/\-\.]+)',
                
                # 🔥 新增：處理 heads, refs 等
                r'refs/heads/\S*\s+([a-zA-Z0-9_/\-\.]+)',
                r'Updating\s+references:\s*([a-zA-Z0-9_/\-\.]+)',
                
                # 🔥 通用項目路徑（更寬鬆）
                r'([a-zA-Z][a-zA-Z0-9_]*(?:/[a-zA-Z0-9_\-\.]+){2,})',
            ]
            
            for pattern in project_patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    project = match.group(1).strip()
                    if len(project) > 5 and '/' in project:  # 基本驗證
                        return self._simplify_project_name(project)
        
        return ""

    def _simplify_project_name(self, project: str) -> str:
        """簡化項目名稱顯示"""
        # 移除常見的前綴
        prefixes_to_remove = [
            'platform/',
            'device/',
            'vendor/',
            'external/',
            'hardware/',
            'frameworks/',
            'system/',
        ]
        
        simplified = project
        for prefix in prefixes_to_remove:
            if simplified.startswith(prefix):
                simplified = simplified[len(prefix):]
                break
        
        # 如果還是太長，只取最後兩個部分
        parts = simplified.split('/')
        if len(parts) > 2:
            simplified = '/'.join(parts[-2:])
        
        # 限制長度
        if len(simplified) > 20:
            simplified = simplified[:17] + "..."
        
        return simplified

    def _is_valid_project_name(self, project: str) -> bool:
        """檢查是否為有效的項目名稱"""
        # 過濾條件
        invalid_patterns = [
            r'^\d+$',  # 純數字
            r'^[^a-zA-Z]',  # 不以字母開頭
            r'\.(log|txt|xml)$',  # 文件擴展名
            r'^(http|https|ftp)://',  # URL
        ]
        
        for pattern in invalid_patterns:
            if re.match(pattern, project, re.IGNORECASE):
                return False
        
        # 長度檢查
        if len(project) < 3 or len(project) > 50:
            return False
        
        # 必須包含路徑分隔符或特定關鍵字
        valid_keywords = ['platform', 'vendor', 'device', 'hardware', 'external', 
                        'frameworks', 'system', 'kernel', 'bootable']
        
        if '/' in project or any(keyword in project.lower() for keyword in valid_keywords):
            return True
        
        return False

    def _wait_for_all_syncs_enhanced(self, db_results: List[DBInfo]):
        """增強版進度監控 - 更精美的顯示格式"""
        max_wait_time = config_manager.repo_config['sync_timeout']
        start_wait = time.time()
        
        active_syncs = [db for db in db_results if db.sync_process and db.status != DBStatus.FAILED]
        self.logger.info(f"🔍 監控 {len(active_syncs)} 個活躍的 repo sync 進程")
        
        # 初始化進度追踪
        progress_tracker = {}
        for db_info in active_syncs:
            progress_tracker[db_info.db_info] = {
                'start_time': db_info.start_time or datetime.now(),
                'log_file': self._get_sync_log_file(db_info),
                'error_count': 0,
                'estimated_progress': 0,
                'current_activity': '初始化中...',
                'current_project': '',
                'last_update': datetime.now()
            }
        
        check_interval = 15  # 15秒檢查一次
        
        while True:
            all_complete = True
            elapsed = int(time.time() - start_wait)
            
            # 清屏並顯示標題
            print("\033[2J\033[H")  # 清屏
            print(f"🔄 Repo Sync 監控 - {elapsed//60:02d}:{elapsed%60:02d}")
            print("="*80)
            
            completed_count = 0
            failed_count = 0
            
            for db_info in active_syncs:
                if db_info.status == DBStatus.FAILED:
                    failed_count += 1
                    continue
                
                db_name = db_info.db_info
                tracker = progress_tracker[db_name]
                
                # 簡化的顯示名稱
                if db_info.version:
                    display_name = f"{db_name} v{db_info.version}"
                else:
                    display_name = db_name
                
                if db_info.sync_process:
                    poll = db_info.sync_process.poll()
                    
                    if poll is None:  # 仍在運行
                        all_complete = False
                        self._update_progress_info(db_info, tracker)
                        
                        runtime = datetime.now() - tracker['start_time']
                        runtime_str = f"{int(runtime.total_seconds()//60)}:{int(runtime.total_seconds()%60):02d}"
                        
                        # 簡化的進度條
                        progress = tracker['estimated_progress']
                        bar_length = 20
                        filled = int(bar_length * progress / 100)
                        bar = "█" * filled + "░" * (bar_length - filled)
                        
                        # 簡化的活動信息
                        activity = tracker.get('current_project', '').split('/')[-1] or '同步中'
                        if len(activity) > 15:
                            activity = activity[:12] + "..."
                        
                        print(f"🔄 {display_name:20s} │{bar}│ {progress:3d}% │ {runtime_str} │ {activity}")
                        
                    elif poll == 0:  # 成功完成
                        completed_count += 1
                        runtime = datetime.now() - tracker['start_time']
                        runtime_str = f"{int(runtime.total_seconds()//60)}:{int(runtime.total_seconds()%60):02d}"
                        
                        bar = "█" * 20
                        print(f"✅ {display_name:20s} │{bar}│ 100% │ {runtime_str} │ 完成")
                        
                    else:  # 失敗
                        failed_count += 1
                        db_info.status = DBStatus.FAILED
                        print(f"❌ {display_name:20s} │{'':20s}│   0% │      │ 失敗")
            
            # 簡化的統計信息
            running_count = len(active_syncs) - completed_count - failed_count
            total_progress = sum(progress_tracker[db.db_info]['estimated_progress'] 
                            for db in active_syncs if db.status != DBStatus.FAILED)
            avg_progress = total_progress / max(len(active_syncs) - failed_count, 1)
            
            print("-" * 80)
            print(f"📊 運行:{running_count} │ 完成:{completed_count} │ 失敗:{failed_count} │ 總進度:{avg_progress:.1f}%")
            
            if all_complete or elapsed > max_wait_time:
                break
            
            time.sleep(check_interval)  # 15秒更新一次
        
        # 🏁 最終統計
        self._display_final_summary(active_syncs, elapsed, progress_tracker)

    def _create_progress_bar(self, percentage: int, width: int = 20) -> str:
        """創建可視化進度條"""
        filled = int(width * percentage / 100)
        bar = "█" * filled + "░" * (width - filled)
        return f"{bar} {percentage:3d}%"

    def _build_display_name(self, db_info: DBInfo) -> str:
        """構建更詳細的顯示名稱"""
        name = db_info.db_info
        if db_info.version:
            name += f" v{db_info.version}"
        elif db_info.manifest_file:
            # 從 manifest 文件名提取版本
            match = re.search(r'manifest_(\d+)\.xml', db_info.manifest_file)
            if match:
                name += f" v{match.group(1)}"
        return name

    def enhanced_monitor_display(self, active_syncs: list, elapsed: int, progress_tracker: dict):
        """增強版進度顯示"""
        print("\033[2J\033[H")  # 清屏
        print(f"🔄 Repo Sync 實時監控 - {elapsed//60:02d}:{elapsed%60:02d}")
        print("="*80)
        
        completed_count = 0
        failed_count = 0
        total_progress = 0
        
        for db_info in active_syncs:
            if db_info.status == DBStatus.FAILED:
                failed_count += 1
                continue
            
            db_name = db_info.db_info
            tracker = progress_tracker.get(db_name, {})
            
            # 構建顯示名稱
            display_name = self._build_display_name(db_info)
            
            if db_info.sync_process:
                poll = db_info.sync_process.poll()
                
                if poll is None:  # 仍在運行
                    self._update_progress_info(db_info, tracker)
                    
                    progress = tracker.get('estimated_progress', 0)
                    activity = tracker.get('current_activity', '同步中')
                    current_count = tracker.get('current_count', 0)
                    total_projects = tracker.get('total_projects', 0)
                    
                    total_progress += progress
                    
                    # 進度條
                    bar_length = 20
                    filled = int(bar_length * progress / 100)
                    bar = "█" * filled + "░" * (bar_length - filled)
                    
                    # 項目信息
                    project_info = ""
                    if total_projects > 0:
                        project_info = f" ({current_count}/{total_projects})"
                    
                    # 運行時間
                    runtime = datetime.now() - tracker.get('start_time', datetime.now())
                    runtime_str = f"{int(runtime.total_seconds()//60)}:{int(runtime.total_seconds()%60):02d}"
                    
                    print(f"🔄 {display_name:20s} │{bar}│ {progress:3d}% │ {runtime_str} │ {activity[:30]}{project_info}")
                    
                elif poll == 0:  # 成功完成
                    completed_count += 1
                    runtime = datetime.now() - tracker.get('start_time', datetime.now())
                    runtime_str = f"{int(runtime.total_seconds()//60)}:{int(runtime.total_seconds()%60):02d}"
                    
                    bar = "█" * 20
                    print(f"✅ {display_name:20s} │{bar}│ 100% │ {runtime_str} │ 完成")
                    
                else:  # 失敗
                    failed_count += 1
                    print(f"❌ {display_name:20s} │{'':20s}│   0% │      │ 失敗")
        
        # 總體統計
        running_count = len(active_syncs) - completed_count - failed_count
        avg_progress = total_progress / max(len(active_syncs) - failed_count, 1)
        
        print("-" * 80)
        print(f"📊 運行:{running_count} │ 完成:{completed_count} │ 失敗:{failed_count} │ 平均進度:{avg_progress:.1f}%")
        
    def _display_final_summary(self, active_syncs: list, elapsed: int, progress_tracker: dict):
        """顯示最終摘要"""
        completed = sum(1 for db in active_syncs if db.sync_process and db.sync_process.poll() == 0)
        failed = sum(1 for db in active_syncs if db.status == DBStatus.FAILED)
        total_retries = sum(progress_tracker.get(db.db_info, {}).get('error_count', 0) for db in active_syncs)
        
        print(f"\n🏁 Repo Sync 最終報告")
        print("=" * 60)
        print(f"⏱️  總用時: {elapsed//60:02d}:{elapsed%60:02d}")
        print(f"✅ 成功: {completed}")
        print(f"❌ 失敗: {failed}")
        print(f"🔄 總重試次數: {total_retries}")
        print(f"📊 成功率: {(completed/(completed+failed)*100):.1f}%" if (completed+failed) > 0 else "0.0%")
        print("=" * 60)
        
        self.logger.info(f"🏁 Repo sync 完成統計: 成功 {completed}, 失敗 {failed}, 總重試 {total_retries}")
                
    def _combine_progress_info(self, log_progress: dict, fs_progress: dict, tracker: dict) -> dict:
        """智能結合多種進度信息源"""
        runtime_minutes = (datetime.now() - tracker['start_time']).total_seconds() / 60
        
        # 確定最可靠的進度百分比
        if log_progress.get('log_valid') and log_progress['percentage'] > 0:
            # 日誌解析有效，優先使用
            percentage = log_progress['percentage']
            primary_source = 'log'
        elif fs_progress.get('fs_valid') and fs_progress['percentage'] > 0:
            # 文件系統檢查有效
            percentage = fs_progress['percentage']
            primary_source = 'filesystem'
        else:
            # 使用時間估算
            percentage = min(int(runtime_minutes * 2), 95)  # 每分鐘約2%，最多95%
            primary_source = 'time_based'
        
        # 構建活動描述
        activity_parts = []
        
        # 項目信息
        if log_progress.get('current_project'):
            project_short = log_progress['current_project'].split('/')[-1]
            activity_parts.append(f"📁 {project_short}")
        elif fs_progress.get('project_count', 0) > 0:
            activity_parts.append(f"📁 {fs_progress['project_count']} 個項目")
        
        # 階段信息
        if log_progress.get('sync_phase') and log_progress['sync_phase'] != 'unknown':
            phase_emoji = {
                'initializing': '🔄',
                'downloading': '⬇️',
                'resolving': '🔧',
                'syncing': '⚡',
                'updating': '📝',
                'finalizing': '✅'
            }
            emoji = phase_emoji.get(log_progress['sync_phase'], '⚙️')
            activity_parts.append(f"{emoji} {log_progress.get('current_activity', '處理中')}")
        
        # 速度信息
        if log_progress.get('download_speed'):
            activity_parts.append(f"🚀 {log_progress['download_speed']}")
        
        # 文件進度
        if log_progress.get('files_progress'):
            activity_parts.append(f"📊 {log_progress['files_progress']}")
        
        # 如果沒有詳細信息，使用基本描述
        if not activity_parts:
            phase_desc = log_progress.get('current_activity') or fs_progress.get('activity') or '同步中...'
            activity_parts.append(phase_desc)
        
        # 添加數據源標記（調試用）
        source_emoji = {'log': '📝', 'filesystem': '💾', 'time_based': '⏱️'}
        activity_parts.append(f"{source_emoji.get(primary_source, '❓')}")
        
        # 時間估算
        estimated_remaining = ''
        if percentage > 5 and runtime_minutes > 1:
            estimated_total_time = runtime_minutes * (100 / percentage)
            remaining_time = max(0, estimated_total_time - runtime_minutes)
            if remaining_time > 1:
                estimated_remaining = f" (預計剩餘: {remaining_time:.0f}分)"
        
        return {
            'estimated_progress': percentage,
            'current_activity': ' | '.join(activity_parts) + estimated_remaining,
            'current_project': log_progress.get('current_project', ''),
            'download_speed': log_progress.get('download_speed', ''),
            'files_progress': log_progress.get('files_progress', ''),
            'sync_phase': log_progress.get('sync_phase', 'processing'),
            'data_source': primary_source,
            'runtime_minutes': runtime_minutes
        }

    def _check_filesystem_progress(self, db_info: DBInfo, tracker: dict) -> dict:
        """檢查文件系統實際進度 - 修正計算邏輯"""
        fs_progress = {
            'percentage': 0,
            'activity': '檢查中...',
            'project_count': 0,
            'fs_valid': False
        }
        
        try:
            # 簡化的進度計算 - 避免異常值
            runtime_minutes = (datetime.now() - tracker['start_time']).total_seconds() / 60
            
            # 檢查實際的項目目錄
            git_count = 0
            for root, dirs, files in os.walk(db_info.local_path):
                if '.git' in dirs and '/.repo/' not in root:
                    git_count += 1
            
            # 基於時間的保守估算（每分鐘約1-2%）
            time_based_progress = min(runtime_minutes * 1.5, 95)
            
            # 如果有實際項目，使用混合估算
            if git_count > 0:
                # 假設總共需要50-100個項目（根據實際情況調整）
                estimated_total = max(50, git_count * 2)
                project_progress = min((git_count / estimated_total) * 100, 95)
                # 取時間估算和項目估算的平均值
                final_progress = min((time_based_progress + project_progress) / 2, 95)
            else:
                final_progress = time_based_progress
            
            fs_progress.update({
                'percentage': max(1, int(final_progress)),  # 確保至少1%
                'activity': f'{git_count}項目' if git_count > 0 else '初始化',
                'project_count': git_count,
                'fs_valid': True
            })
            
        except Exception as e:
            # 備用估算
            runtime_minutes = (datetime.now() - tracker['start_time']).total_seconds() / 60
            fs_progress.update({
                'percentage': max(1, min(int(runtime_minutes * 1.5), 95)),
                'activity': '同步中',
                'fs_valid': False
            })
        
        return fs_progress

    def _parse_repo_sync_progress_enhanced(self, log_file: str) -> dict:
        """增強版日誌解析 - 更智能的模式匹配"""
        progress_info = {
            'percentage': 0,
            'current_activity': '',
            'current_project': '',
            'download_speed': '',
            'files_progress': '',
            'sync_phase': 'unknown',
            'log_valid': False
        }
        
        if not log_file or not os.path.exists(log_file):
            return progress_info
        
        try:
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                # 讀取最後 10KB 的內容以獲取最新狀態
                f.seek(max(0, os.path.getsize(log_file) - 10240))
                recent_content = f.read()
                recent_lines = recent_content.split('\n')[-30:]  # 最後30行
            
            # 🎯 智能解析各種 repo sync 階段
            current_phase = self._detect_sync_phase(recent_lines)
            progress_info['sync_phase'] = current_phase
            
            for line in reversed(recent_lines):  # 從最新的行開始解析
                line = line.strip()
                if not line:
                    continue
                
                # 📊 Project 信息解析 (優先級最高)
                project_info = self._extract_project_info(line)
                if project_info:
                    progress_info['current_project'] = project_info
                    progress_info['current_activity'] = f"處理項目: {project_info}"
                    progress_info['log_valid'] = True
                
                # 📈 百分比進度解析
                percentage = self._extract_percentage(line)
                if percentage is not None:
                    progress_info['percentage'] = percentage
                    progress_info['log_valid'] = True
                
                # 🚀 下載速度解析
                speed = self._extract_download_speed(line)
                if speed:
                    progress_info['download_speed'] = speed
                    progress_info['log_valid'] = True
                
                # 📁 文件進度解析
                file_progress = self._extract_file_progress(line)
                if file_progress:
                    progress_info['files_progress'] = file_progress
                    progress_info['log_valid'] = True
                
                # 如果已經獲得足夠信息，停止解析
                if (progress_info['current_project'] and 
                    progress_info['percentage'] > 0):
                    break
            
            # 根據階段調整活動描述
            if not progress_info['current_activity']:
                progress_info['current_activity'] = self._get_phase_description(current_phase)
                
        except Exception as e:
            self.logger.debug(f"日誌解析失敗: {e}")
        
        return progress_info

    def _get_phase_description(self, phase: str) -> str:
        """根據階段獲取描述"""
        phase_descriptions = {
            'initializing': '初始化連接...',
            'downloading': '下載源代碼...',
            'resolving': '解析和解壓...',
            'syncing': '同步工作樹...',
            'updating': '更新文件...',
            'finalizing': '完成同步...',
            'processing': '處理中...'
        }
        
        return phase_descriptions.get(phase, '同步中...')

    def _extract_file_progress(self, line: str) -> str:
        """提取文件進度信息"""
        file_patterns = [
            r'\((\d+/\d+)\)',
            r'(\d+)\s+of\s+(\d+)',
            r'files:\s*(\d+/\d+)',
        ]
        
        for pattern in file_patterns:
            match = re.search(pattern, line)
            if match:
                if len(match.groups()) == 1:
                    return match.group(1)
                else:
                    return f"{match.group(1)}/{match.group(2)}"
        
        return ''

    def _extract_download_speed(self, line: str) -> str:
        """提取下載速度"""
        speed_patterns = [
            r'([\d.]+\s*[KMG]?B/s)',
            r'@\s*([\d.]+\s*[KMG]?B/s)',
            r'speed:\s*([\d.]+\s*[KMG]?B/s)',
        ]
        
        for pattern in speed_patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return ''

    def _extract_percentage(self, line: str) -> int:
        """提取百分比進度"""
        # 匹配各種百分比格式
        percentage_patterns = [
            r'(\d+)%',
            r'(\d+)\s*percent',
            r'progress:\s*(\d+)',
        ]
        
        for pattern in percentage_patterns:
            match = re.search(pattern, line)
            if match:
                percentage = int(match.group(1))
                if 0 <= percentage <= 100:
                    return percentage
        
        return None

    def _extract_project_info(self, line: str) -> str:
        """提取當前處理的項目信息"""
        # 🎯 更精確的項目名稱匹配
        project_patterns = [
            r'Fetching project\s+(.+?)(?:\s|$)',
            r'project\s+([^\s]+(?:/[^\s]+)*)',
            r'Syncing\s+(.+?)(?:\s|$)',
            r'Updating\s+(.+?)(?:\s|$)',
            r'Checking out\s+(.+?)(?:\s|$)',
        ]
        
        for pattern in project_patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                project = match.group(1).strip()
                # 清理項目名稱
                project = re.sub(r'[^\w/\-_.]', '', project)
                if len(project) > 3:  # 過濾太短的匹配
                    return project
        
        return ''

    def _detect_sync_phase(self, lines: list) -> str:
        """檢測當前 sync 階段"""
        recent_text = ' '.join(lines[-10:]).lower()
        
        phase_patterns = [
            ('initializing', ['remote: counting', 'remote: enumerating']),
            ('downloading', ['receiving objects', 'downloading', 'fetching']),
            ('resolving', ['resolving deltas', 'unpacking objects']),
            ('syncing', ['syncing work tree', 'checking out']),
            ('updating', ['updating files', 'updating references']),
            ('finalizing', ['done', 'completed'])
        ]
        
        for phase, patterns in phase_patterns:
            if any(pattern in recent_text for pattern in patterns):
                return phase
        
        return 'processing'

    def _fallback_progress_estimation(self, db_info: DBInfo, tracker: dict):
        """備用進度估算方法"""
        runtime_minutes = (datetime.now() - tracker['start_time']).total_seconds() / 60
        
        if runtime_minutes < 2:
            tracker['estimated_progress'] = min(int(runtime_minutes * 15), 30)
            tracker['current_activity'] = "初始化 repo 同步..."
        elif runtime_minutes < 10:
            tracker['estimated_progress'] = min(30 + int((runtime_minutes - 2) * 5), 70)
            tracker['current_activity'] = "下載項目和源代碼..."
        else:
            tracker['estimated_progress'] = min(70 + int((runtime_minutes - 10) * 2), 95)
            tracker['current_activity'] = "完成同步和檢出..."
            
    def _parse_repo_sync_progress(self, log_lines: list) -> dict:
        """解析 repo sync 日誌中的詳細進度信息"""
        progress_info = {
            'percentage': 0,
            'current_activity': '',
            'current_project': '',
            'download_speed': '',
            'files_progress': ''
        }
        
        for line in log_lines:
            line = line.strip()
            if not line:
                continue
                
            # 🔍 解析各種進度模式
            
            # 1. 項目獲取進度: "Fetching project platform/build"
            if 'Fetching project' in line:
                project_match = re.search(r'Fetching project\s+(.+)', line)
                if project_match:
                    project_name = project_match.group(1)
                    progress_info['current_project'] = project_name
                    progress_info['current_activity'] = f"正在獲取項目: {project_name}"
            
            # 2. 同步進度: "Syncing work tree: 45% (123/456)"
            elif 'Syncing work tree:' in line:
                sync_match = re.search(r'Syncing work tree:\s*(\d+)%\s*\((\d+)/(\d+)\)', line)
                if sync_match:
                    percentage = int(sync_match.group(1))
                    current = sync_match.group(2)
                    total = sync_match.group(3)
                    progress_info['percentage'] = percentage
                    progress_info['files_progress'] = f"{current}/{total}"
                    progress_info['current_activity'] = f"同步工作樹: {percentage}% ({current}/{total})"
            
            # 3. 檢出進度: "Checking out files: 67% (234/567)"
            elif 'Checking out files:' in line:
                checkout_match = re.search(r'Checking out files:\s*(\d+)%\s*\((\d+)/(\d+)\)', line)
                if checkout_match:
                    percentage = int(checkout_match.group(1))
                    current = checkout_match.group(2)
                    total = checkout_match.group(3)
                    progress_info['percentage'] = percentage
                    progress_info['files_progress'] = f"{current}/{total}"
                    progress_info['current_activity'] = f"檢出文件: {percentage}% ({current}/{total})"
            
            # 4. Git 操作: "remote: Counting objects: 12345"
            elif 'remote: Counting objects:' in line:
                objects_match = re.search(r'remote: Counting objects:\s*(\d+)', line)
                if objects_match:
                    count = objects_match.group(1)
                    progress_info['current_activity'] = f"計算對象: {count} 個"
            
            # 5. Git 接收: "remote: Compressing objects: 100% (456/456)"
            elif 'remote: Compressing objects:' in line:
                compress_match = re.search(r'remote: Compressing objects:\s*(\d+)%\s*\((\d+)/(\d+)\)', line)
                if compress_match:
                    percentage = int(compress_match.group(1))
                    current = compress_match.group(2)
                    total = compress_match.group(3)
                    progress_info['current_activity'] = f"壓縮對象: {percentage}% ({current}/{total})"
            
            # 6. 接收對象: "Receiving objects: 78% (1234/5678), 12.34 MiB | 1.23 MiB/s"
            elif 'Receiving objects:' in line:
                receive_match = re.search(r'Receiving objects:\s*(\d+)%\s*\((\d+)/(\d+)\)(?:,\s*[\d.]+\s*\w+\s*\|\s*([\d.]+\s*\w+/s))?', line)
                if receive_match:
                    percentage = int(receive_match.group(1))
                    current = receive_match.group(2)
                    total = receive_match.group(3)
                    speed = receive_match.group(4) if receive_match.group(4) else ""
                    
                    progress_info['percentage'] = percentage
                    progress_info['files_progress'] = f"{current}/{total}"
                    progress_info['download_speed'] = speed
                    
                    speed_text = f" @ {speed}" if speed else ""
                    progress_info['current_activity'] = f"接收對象: {percentage}% ({current}/{total}){speed_text}"
            
            # 7. 解析對象: "Resolving deltas: 89% (456/789)"
            elif 'Resolving deltas:' in line:
                delta_match = re.search(r'Resolving deltas:\s*(\d+)%\s*\((\d+)/(\d+)\)', line)
                if delta_match:
                    percentage = int(delta_match.group(1))
                    current = delta_match.group(2)
                    total = delta_match.group(3)
                    progress_info['current_activity'] = f"解析增量: {percentage}% ({current}/{total})"
            
            # 8. 項目同步完成: "project platform/build/"
            elif 'project ' in line and '/' in line and not 'Fetching' in line:
                project_match = re.search(r'project\s+([^\s]+)', line)
                if project_match:
                    project_name = project_match.group(1)
                    progress_info['current_project'] = project_name
                    progress_info['current_activity'] = f"處理項目: {project_name}"
            
            # 9. 錯誤信息
            elif 'error:' in line.lower() or 'warning:' in line.lower():
                if 'error:' in line.lower():
                    progress_info['current_activity'] = "⚠️ 遇到錯誤，正在重試..."
                else:
                    progress_info['current_activity'] = "⚠️ 警告信息，繼續處理..."
        
        return progress_info
        
    def process_selected_dbs(self, db_list: List[str], db_versions: Dict[str, str] = None):
        """處理選定的 DB"""
        if config_manager.repo_config['async_sync'] and not self.dry_run:
            self.process_dbs_async(db_list, db_versions)
        else:
            # 同步處理邏輯
            for db_name in db_list:
                if '#' in db_name:
                    db_name, version = db_name.split('#', 1)
                else:
                    version = db_versions.get(db_name) if db_versions else None
                
                for db_info in self.get_all_dbs('all'):
                    if db_info.db_info == db_name:
                        db_info.version = version
                        
                        db_info = self.process_db_phase1(db_info)
                        
                        if not self.dry_run and db_info.sync_process:
                            self.logger.info(f"等待 {db_name} sync 完成...")
                            db_info.sync_process.wait()
                        
                        db_info = self.process_db_phase2(db_info)
                        self.report.add_db(db_info)
                        break

    def generate_report(self, output_file: str = None):
        """產生改進版報告"""
        self.report.finalize()
        
        if not output_file:
            output_file = os.path.join(
                self.output_dir, 
                config_manager.path_config['report_filename']
            )
        
        try:
            self.logger.info("開始產生 Excel 報告")
            
            report_data = []
            for db in self.report.db_details:
                db_dict = db.to_dict()
                # 新增欄位
                db_dict['完整_JIRA_連結'] = db.jira_link or '未找到'
                db_dict['完整_repo_init_指令'] = db.actual_source_cmd or '未記錄'
                db_dict['manifest_版本'] = db.version or '未指定'
                db_dict['manifest_檔案'] = db.manifest_file or '未下載'
                report_data.append(db_dict)
            
            df = pd.DataFrame(report_data)
            
            # 重新排列欄位順序，把重要欄位放前面
            important_columns = [
                'sn', 'module', 'db_type', 'db_info', 'status',
                'manifest_版本', 'manifest_檔案', '完整_JIRA_連結', '完整_repo_init_指令',
                'start_time', 'end_time', 'error_message'
            ]
            
            # 確保所有欄位都存在，並重新排序
            existing_columns = [col for col in important_columns if col in df.columns]
            other_columns = [col for col in df.columns if col not in important_columns]
            df = df[existing_columns + other_columns]
            
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
            
            # 寫入改進版 Excel
            self._write_enhanced_excel(df, summary_df, output_file)
            
            self.logger.info(f"Excel 報告已產生: {output_file}")
            print(f"\n📊 Excel 報告已產生: {output_file}")
            
        except Exception as e:
            self.logger.error(f"產生報告失敗: {str(e)}")

    def _write_enhanced_excel(self, main_df: pd.DataFrame, summary_df: pd.DataFrame, output_file: str):
        """寫入改進版 Excel（自動適寬、表頭藍底白字）"""
        try:
            with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
                # 寫入主要資料
                main_df.to_excel(writer, sheet_name='詳細資訊', index=False)
                summary_df.to_excel(writer, sheet_name='摘要', index=False)
                
                # 格式化工作表
                for sheet_name in ['詳細資訊', '摘要']:
                    worksheet = writer.sheets[sheet_name]
                    self._format_worksheet_enhanced(worksheet)
            
            self.logger.info(f"成功寫入增強版 Excel 檔案: {output_file}")
            
        except Exception as e:
            self.logger.error(f"寫入 Excel 檔案失敗: {str(e)}")
            raise

    def _format_worksheet_enhanced(self, worksheet):
        """格式化工作表（自動適寬、表頭藍底白字）"""
        try:
            # 設定表頭格式（藍底白字）
            header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
            header_font = Font(color="FFFFFF", bold=True)
            header_alignment = Alignment(horizontal="center", vertical="center")
            
            # 應用到第一行（表頭）
            for cell in worksheet[1]:
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = header_alignment
            
            # 自動調整欄寬
            for column in worksheet.columns:
                max_length = 0
                column_letter = get_column_letter(column[0].column)
                
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                
                # 設定最小寬度和最大寬度
                adjusted_width = min(max(max_length + 2, 10), 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width
            
            # 設定行高
            for row in worksheet.iter_rows():
                worksheet.row_dimensions[row[0].row].height = 20
            
            # 凍結第一行
            worksheet.freeze_panes = 'A2'
            
        except Exception as e:
            self.logger.warning(f"格式化工作表時發生錯誤: {e}")

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
        self.selected_db_type = 'all'
        
        self._load_default_config()
    
    def _load_default_config(self):
        """載入預設配置"""
        if config_manager.default_execution_config.get('sftp_override'):
            config_manager.apply_overrides(
                config_manager.default_execution_config['sftp_override'],
                source='default_config'
            )
        
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
        """載入 mapping table"""
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
            
            if config_manager.default_execution_config.get('db_type'):
                self.selected_db_type = config_manager.default_execution_config['db_type']
                print(f"   📌 使用預設 DB 類型: {self.selected_db_type}")
        else:
            print("❌ 載入失敗")
    
    def select_db_type(self):
        """選擇 DB 類型"""
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
        """選擇要定版的 DB"""
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
        
        # 檢查預設 DB 列表
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
        
        # 顯示 DB 列表和選擇邏輯
        print(f"\n找到 {len(db_list)} 個不重複的 DB (類型: {self.selected_db_type})")
        
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
        """設定 DB 版本"""
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
        """執行定版"""
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
        
        # 詢問輸出目錄
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
        
        # 確認執行
        if config_manager.default_execution_config.get('auto_confirm'):
            print("📌 自動確認執行（根據預設配置）")
        else:
            if input("\n確認開始執行? (Y/n): ").strip().lower() == 'n':
                print("❌ 使用者取消操作")
                return
        
        print("\n🚀 開始執行定版...")
        
        print("🌐 準備 SFTP 連線（每個 DB 使用獨立連線）...")
        
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
            resource_manager.cleanup_all()
    
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
        """測試 JIRA 連線"""
        print("\n測試 JIRA 連線...")
        
        if not hasattr(self.tool, 'source_cmd_manager'):
            self.tool.source_cmd_manager = SourceCommandManager()
        
        if self.tool.source_cmd_manager.jira_client.connect():
            print("✅ JIRA 連線成功！")
            
            if input("\n是否要測試查詢 DB 的 source command? (y/N): ").strip().lower() == 'y':
                db_name = input("請輸入 DB 名稱 (例如: DB2302): ").strip()
                if db_name:
                    print(f"\n查詢 {db_name} 的 source command...")
                    
                    test_db_info = DBInfo(
                        sn=0,
                        module="Test",
                        db_type="master",
                        db_info=db_name,
                        db_folder="",
                        sftp_path=""
                    )
                    
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
    
    def test_sftp_connection(self):
        """測試 SFTP 連線"""
        print("\n測試 SFTP 連線...")
        print(f"伺服器: {config_manager.sftp_config['host']}:{config_manager.sftp_config['port']}")
        print(f"用戶: {config_manager.sftp_config['username']}")
        
        # 創建臨時 SFTP 管理器進行測試
        test_sftp_manager = SFTPManager()
        
        if test_sftp_manager.connect():
            print("✅ SFTP 連線成功！")
            
            if input("\n是否要測試路徑存取? (y/N): ").strip().lower() == 'y':
                path = input("請輸入要測試的路徑: ").strip()
                if path:
                    try:
                        result = test_sftp_manager.find_latest_manifest(path)
                        if result:
                            print(f"✅ 找到 manifest: {result[1]}")
                        else:
                            print("❌ 沒有找到 manifest")
                    except Exception as e:
                        print(f"❌ 測試失敗: {e}")
            
            test_sftp_manager.disconnect()
        else:
            print("❌ SFTP 連線失敗！")
    
    def display_menu(self) -> str:
        """顯示主選單"""
        print("\n" + "="*60)
        print("Manifest 定版工具 - 主選單 (改進版)")
        
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
        print("9. 測試 JIRA 連線")
        print("10. 測試 SFTP 連線")
        print("0. 結束程式")
        print("="*60)
        
        return input("請選擇功能: ").strip()
    
    def run_interactive(self):
        """執行互動式介面"""
        print("\n歡迎使用 Manifest 定版工具！")
        print(f"版本: {__version__} (改進版)")
        print("改進內容: 修復 SFTP Garbage packet 問題、改善日誌輸出")
        
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
                    self.test_jira_connection()
                elif choice == '10':
                    self.test_sftp_connection()
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
        
        resource_manager.cleanup_all()

# =====================================
# ===== 主程式 =====
# =====================================

def main():
    """主程式入口"""
    parser = argparse.ArgumentParser(
        description='Manifest 定版工具 - 自動化 repo 定版處理 (改進版)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
版本: {__version__}
作者: {__author__}
日期: {__date__}

改進內容:
- 修復 SFTP "Garbage packet received" 錯誤
- 改為正常順序日誌輸出，便於 debug
- 改進 Excel 報告格式（自動適寬、表頭藍底白字）
- 記錄完整 repo init 指令和 JIRA 連結

範例:
  # 使用互動式介面
  python {sys.argv[0]}
  
  # 處理指定的 DB
  python {sys.argv[0]} -m mapping.xlsx -d DB2302,DB2575 -o ./output
  
  # 測試模式
  python {sys.argv[0]} -m mapping.xlsx --dry-run
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
    
    # 設定日誌等級
    if args.debug:
        config_manager.log_config['level'] = logging.DEBUG
        logging.getLogger().setLevel(logging.DEBUG)
        for handler in logging.getLogger().handlers:
            handler.setLevel(logging.DEBUG)
        print("🔍 Debug 模式已啟用")
    
    # 檢查是否為測試模式
    if args.dry_run:
        print("\n" + "="*60)
        print("🧪 測試模式 (Dry Run) - 不會實際執行任何操作")
        print("="*60)
    
    # 決定執行模式
    if args.mapping:
        # 命令列模式
        print("\n" + "="*60)
        print(f"📋 Manifest 定版工具 v{__version__} - 命令列模式 (改進版)")
        print("="*60)
        
        tool = ManifestPinningTool()
        
        if args.dry_run:
            tool.dry_run = True
        
        try:
            # 載入 mapping table
            print(f"\n📂 載入 mapping table: {args.mapping}")
            if not os.path.exists(args.mapping):
                print(f"❌ 檔案不存在: {args.mapping}")
                sys.exit(1)
            
            if not tool.load_mapping_table(args.mapping):
                print("❌ 無法載入 mapping table")
                sys.exit(1)
            
            print(f"✅ 成功載入 mapping table")
            
            # 設定輸出目錄
            tool.output_dir = args.output or config_manager.path_config['default_output_dir']
            os.makedirs(tool.output_dir, exist_ok=True)
            print(f"📁 輸出目錄: {tool.output_dir}")

            print(f"\n🌐 準備 SFTP 連線: {config_manager.sftp_config['host']}")
            print("ℹ️  每個 DB 將使用獨立的 SFTP 連線")

            try:
                # 決定要處理的 DB 列表
                db_list = []
                db_versions = {}
                
                if args.dbs:
                    db_specs = [db.strip() for db in args.dbs.split(',')]
                    
                    for db_spec in db_specs:
                        if '#' in db_spec:
                            db_name, version = db_spec.split('#', 1)
                            db_list.append(db_name)
                            db_versions[db_name] = version
                        else:
                            db_list.append(db_spec)
                    
                    print(f"\n📌 使用指定的 DB 列表: {', '.join(db_list)}")
                else:
                    all_db_infos = tool.get_all_dbs(args.type)
                    db_list = list(set([db.db_info for db in all_db_infos]))
                    
                    if args.type == 'all':
                        print(f"\n📌 使用所有 DB，共 {len(db_list)} 個")
                    else:
                        print(f"\n📌 使用所有 {args.type} 類型的 DB，共 {len(db_list)} 個")
                
                # 處理額外的版本設定
                if args.versions:
                    version_specs = [v.strip() for v in args.versions.split(',')]
                    for version_spec in version_specs:
                        if '#' in version_spec:
                            db_name, version = version_spec.split('#', 1)
                            db_versions[db_name] = version
                    
                    print(f"📌 設定了 {len(db_versions)} 個 DB 的版本")
                
                # 確認處理資訊
                print("\n" + "-"*40)
                print("📋 準備處理以下 DB:")
                for i, db in enumerate(db_list, 1):
                    version_info = f" (版本: {db_versions[db]})" if db in db_versions else " (最新版本)"
                    print(f"  {i:3d}. {db}{version_info}")
                print("-"*40)
                
                if not db_list:
                    print("❌ 沒有找到要處理的 DB")
                    sys.exit(1)
                
                # 詢問確認（除非是測試模式）
                if not args.dry_run:
                    if sys.stdin.isatty():
                        confirm = input(f"\n確認要處理 {len(db_list)} 個 DB? (Y/n): ").strip().lower()
                        if confirm == 'n':
                            print("❌ 使用者取消操作")
                            sys.exit(0)
                
                # 開始處理
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
                
                # 產生報告
                if not args.dry_run:
                    print("\n📊 產生處理報告...")
                    report_path = os.path.join(
                        tool.output_dir, 
                        config_manager.path_config['report_filename']
                    )
                    tool.generate_report(report_path)
                
                # 顯示結果摘要
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
                print("\n📌 清理資源...")
                resource_manager.cleanup_all()
                
        except KeyboardInterrupt:
            print("\n🛑 收到 Ctrl+C，清理所有進程...")
            resource_manager.cleanup_all()
            sys.exit(0)
            
        except Exception as e:
            print(f"\n❌ 發生錯誤: {str(e)}")
            if args.debug:
                import traceback
                traceback.print_exc()
            sys.exit(1)
        
        finally:
            resource_manager.cleanup_all()
    
    else:
        # 互動式模式
        print("\n" + "="*60)
        print(f"🎮 Manifest 定版工具 v{__version__} - 互動式介面 (改進版)")
        print("="*60)
        print("改進內容: 修復 SFTP Garbage packet 問題、改善日誌輸出")
        print("提示: 使用 -h 參數查看命令列選項")
        print("="*60)
        
        try:
            ui = InteractiveUI()
            
            if args.output:
                ui.tool.output_dir = args.output
            
            if args.dry_run:
                ui.tool.dry_run = True
                print("🧪 測試模式已啟用")
            
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
            resource_manager.cleanup_all()

# 在你的程式中添加這個測試函數
def test_sftp_connection():
    """測試 SFTP 連線和伺服器能力"""
    print("="*50)
    print("SFTP 連線和能力測試")
    print("="*50)
    
    sftp_mgr = SFTPManager()
    
    try:
        # 測試連線
        print("1. 測試 SFTP 連線...")
        if sftp_mgr.connect():
            print("✅ SFTP 連線成功")
            
            # 顯示伺服器能力
            print("\n2. 伺服器能力檢測結果:")
            capabilities = sftp_mgr._server_capabilities
            print(f"   listdir_attr 支援: {'✅' if capabilities['supports_listdir_attr'] else '❌'}")
            print(f"   stat 支援: {'✅' if capabilities['supports_stat'] else '❌'}")
            
            # 測試基本操作
            print("\n3. 測試基本操作...")
            try:
                items = sftp_mgr._safe_listdir('.')
                print(f"✅ 基本 listdir 成功，找到 {len(items)} 個項目")
            except Exception as e:
                print(f"❌ 基本 listdir 失敗: {e}")
            
            # 測試詳細列表
            print("\n4. 測試詳細列表...")
            try:
                items = sftp_mgr._safe_listdir_with_details('.')
                print(f"✅ 詳細列表成功，找到 {len(items)} 個項目")
                for item in items[:3]:  # 只顯示前3個
                    print(f"   - {item['name']} ({'目錄' if item['is_dir'] else '檔案'})")
            except Exception as e:
                print(f"❌ 詳細列表失敗: {e}")
            
            sftp_mgr.disconnect()
            print("\n✅ 測試完成")
            
        else:
            print("❌ SFTP 連線失敗")
    
    except Exception as e:
        print(f"❌ 測試過程發生錯誤: {e}")
        import traceback
        traceback.print_exc()

def test_manifest_search():
    """測試實際的 manifest 搜尋功能"""
    print("="*60)
    print("進階 Manifest 搜尋測試")
    print("="*60)
    
    sftp_mgr = SFTPManager()
    
    try:
        # 連線
        print("1. 建立 SFTP 連線...")
        if not sftp_mgr.connect():
            print("❌ SFTP 連線失敗")
            return
        print("✅ SFTP 連線成功")
        
        # 測試路徑（使用 DB2145 的實際路徑）
        test_paths = [
            "/DailyBuild/Merlin8/DB2145_Merlin8_FW_Android14_Ref_Plus_GoogleGMS",
            "/DailyBuild/Merlin8",  # 上層目錄測試
        ]
        
        for test_path in test_paths:
            print(f"\n2. 測試路徑: {test_path}")
            
            # 測試基本列目錄
            try:
                print(f"   2.1 測試基本 listdir...")
                items = sftp_mgr._safe_listdir(test_path)
                print(f"   ✅ 找到 {len(items)} 個項目")
                
                # 顯示前幾個項目
                for i, item in enumerate(items[:5]):
                    print(f"      - {item}")
                if len(items) > 5:
                    print(f"      ... 還有 {len(items) - 5} 個項目")
                    
            except Exception as e:
                print(f"   ❌ 基本 listdir 失敗: {e}")
                continue
            
            # 測試詳細列目錄
            try:
                print(f"   2.2 測試詳細 listdir...")
                items = sftp_mgr._safe_listdir_with_details(test_path)
                print(f"   ✅ 找到 {len(items)} 個詳細項目")
                
                # 分析目錄結構
                dirs = [item for item in items if item['is_dir']]
                files = [item for item in items if not item['is_dir']]
                
                print(f"      目錄: {len(dirs)} 個")
                print(f"      檔案: {len(files)} 個")
                
                # 顯示版本目錄
                version_dirs = []
                for item in dirs:
                    version_num = sftp_mgr._extract_version_number(item['name'])
                    if version_num:
                        version_dirs.append((int(version_num), item['name']))
                
                if version_dirs:
                    version_dirs.sort(reverse=True)
                    print(f"      版本目錄: {len(version_dirs)} 個")
                    for ver_num, ver_name in version_dirs[:3]:
                        print(f"         版本 {ver_num}: {ver_name}")
                    
            except Exception as e:
                print(f"   ❌ 詳細 listdir 失敗: {e}")
                continue
            
            # 測試 manifest 搜尋
            try:
                print(f"   2.3 測試 manifest 搜尋...")
                result = sftp_mgr.find_latest_manifest(test_path)
                
                if result:
                    manifest_path, manifest_name = result
                    print(f"   ✅ 找到 manifest: {manifest_name}")
                    print(f"      完整路徑: {manifest_path}")
                    
                    # 測試檔案存在性
                    print(f"   2.4 驗證 manifest 檔案...")
                    if sftp_mgr._file_exists_and_valid(manifest_path):
                        print(f"   ✅ Manifest 檔案有效")
                    else:
                        print(f"   ❌ Manifest 檔案無效")
                else:
                    print(f"   ❌ 未找到 manifest")
                    
            except Exception as e:
                print(f"   ❌ Manifest 搜尋失敗: {e}")
                import traceback
                traceback.print_exc()
        
        # 測試特定版本搜尋（如果用戶有特定版本需求）
        print(f"\n3. 測試特定版本搜尋...")
        test_version = "709"  # DB2145 的版本
        test_path = "/DailyBuild/Merlin8/DB2145_Merlin8_FW_Android14_Ref_Plus_GoogleGMS"
        
        try:
            result = sftp_mgr.find_latest_manifest(test_path, target_version=test_version)
            if result:
                manifest_path, manifest_name = result
                print(f"✅ 找到版本 {test_version} 的 manifest: {manifest_name}")
            else:
                print(f"❌ 未找到版本 {test_version} 的 manifest")
        except Exception as e:
            print(f"❌ 特定版本搜尋失敗: {e}")
        
        sftp_mgr.disconnect()
        print("\n✅ 進階測試完成")
        
    except Exception as e:
        print(f"❌ 測試過程發生錯誤: {e}")
        import traceback
        traceback.print_exc()
        
        if sftp_mgr.connected:
            sftp_mgr.disconnect()

if __name__ == "__main__":
    # test_sftp_connection()
    # test_manifest_search()
    main()