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
            'init_timeout': 300,
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
        """提取 repo init 命令 - 優先選擇有 -m 參數的指令"""
        if not text or 'repo init' not in text:
            return None
        
        lines = text.split('\n')
        found_commands = []
        
        for line in lines:
            line = line.strip()
            
            # 尋找包含 repo init 的行
            if 'repo init' in line:
                repo_start = line.find('repo init')
                if repo_start != -1:
                    cmd = line[repo_start:].strip()
                    cmd = self._clean_command(cmd)
                    if self._is_valid_repo_command(cmd):
                        found_commands.append(cmd)
        
        if not found_commands:
            return None
        
        # 🔥 優先選擇有 "-m" 參數的指令
        commands_with_m = [cmd for cmd in found_commands if '-m ' in cmd]
        if commands_with_m:
            # 如果有多個，取第一個
            return commands_with_m[0]
        
        # 如果沒有 -m 參數的，返回第一個有效的
        return found_commands[0]

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
        """執行 repo init - 增強清理和錯誤恢復"""
        # 🔥 徹底清理可能存在的舊 .repo 目錄和相關檔案
        repo_dir = os.path.join(work_dir, '.repo')
        if os.path.exists(repo_dir):
            self.logger.info(f"發現舊的 .repo 目錄，執行徹底清理: {repo_dir}")
            import shutil
            try:
                # 先嘗試正常刪除
                shutil.rmtree(repo_dir)
                self.logger.info("✅ 舊 .repo 目錄清理成功")
            except Exception as e:
                self.logger.warning(f"正常清理失敗，嘗試強制清理: {e}")
                # 強制清理
                try:
                    import subprocess
                    if os.name == 'posix':  # Linux/Unix
                        subprocess.run(['rm', '-rf', repo_dir], check=True)
                        self.logger.info("✅ 強制清理成功")
                    else:
                        raise Exception("無法強制清理")
                except Exception as e2:
                    self.logger.error(f"❌ 強制清理也失敗: {e2}")
                    return False
        
        # 🔥 清理可能存在的其他相關檔案
        cleanup_patterns = [
            '.repo_*',
            'repo_*',
            '.repopickle_*'
        ]
        
        for pattern in cleanup_patterns:
            try:
                import glob
                for item in glob.glob(os.path.join(work_dir, pattern)):
                    if os.path.isfile(item):
                        os.remove(item)
                    elif os.path.isdir(item):
                        shutil.rmtree(item)
                    self.logger.debug(f"清理: {item}")
            except Exception as e:
                self.logger.debug(f"清理 {pattern} 時發生錯誤: {e}")
        
        # 🔥 增加重試機制和更長的超時時間
        max_retries = 3
        timeout_values = [180, 300, 600]  # 3分鐘、5分鐘、10分鐘
        for attempt in range(max_retries):
            timeout = timeout_values[attempt]
            self.logger.info(f"執行 repo init (嘗試 {attempt + 1}/{max_retries}，超時: {timeout}秒): {init_cmd}")
            
            success, output = self.run_command(
                init_cmd,
                cwd=work_dir,
                timeout=timeout
            )
            
            if success:
                self.logger.info("✅ Repo init 執行成功")
                return True
            else:
                self.logger.warning(f"❌ Repo init 嘗試 {attempt + 1} 失敗: {output}")
                
                # 如果不是最後一次嘗試，清理並重試
                if attempt < max_retries - 1:
                    self.logger.info(f"準備重試，先清理環境...")
                    repo_dir = os.path.join(work_dir, '.repo')
                    if os.path.exists(repo_dir):
                        try:
                            import shutil
                            shutil.rmtree(repo_dir)
                        except:
                            pass
                    time.sleep(15)  # 等待 15 秒後重試
        
        self.logger.error("❌ Repo init 所有重試都失敗")
        return False
    
    def apply_manifest(self, work_dir: str, manifest_file: str) -> bool:
        """應用 manifest 檔案 - 改進版本"""
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
            
            # 🔥 修改：增加超時時間並添加重試機制
            switch_cmd = f"{config_manager.repo_config['repo_command']} init -m {manifest_name}"
            self.logger.info(f"切換 manifest: {switch_cmd}")
            
            # 🔥 嘗試多次，增加超時時間
            max_attempts = 3
            timeout_values = [120, 180, 300]  # 2分鐘、3分鐘、5分鐘
            
            for attempt in range(max_attempts):
                timeout = timeout_values[attempt]
                self.logger.info(f"嘗試 {attempt + 1}/{max_attempts}，超時設定: {timeout}秒")
                
                success, output = self.run_command(
                    switch_cmd,
                    cwd=work_dir,
                    timeout=timeout
                )
                
                if success:
                    self.logger.info(f"✅ 成功切換到 manifest: {manifest_name}")
                    return True
                else:
                    self.logger.warning(f"❌ 嘗試 {attempt + 1} 失敗: {output}")
                    
                    # 如果不是最後一次，等待一下再重試
                    if attempt < max_attempts - 1:
                        import time
                        wait_time = 10 * (attempt + 1)  # 10秒、20秒
                        self.logger.info(f"等待 {wait_time} 秒後重試...")
                        time.sleep(wait_time)
            
            self.logger.error(f"❌ 所有嘗試都失敗，無法切換 manifest")
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
        """導出 manifest - 增加超時時間"""
        cmd = f"{config_manager.repo_config['repo_command']} manifest -r -o {output_file}"
        self.logger.info(f"導出 manifest: {cmd}")
        
        # 🔥 增加超時時間到 5 分鐘，並添加重試機制
        max_attempts = 3
        timeout_values = [180, 300, 600]  # 3分鐘、5分鐘、10分鐘
        
        for attempt in range(max_attempts):
            timeout = timeout_values[attempt]
            self.logger.info(f"導出 manifest 嘗試 {attempt + 1}/{max_attempts}，超時設定: {timeout}秒")
            
            success, output = self.run_command(cmd, cwd=work_dir, timeout=timeout)
            
            if success:
                output_path = os.path.join(work_dir, output_file)
                if os.path.exists(output_path):
                    file_size = os.path.getsize(output_path)
                    self.logger.info(f"✅ 成功導出 manifest: {output_path} ({file_size} bytes)")
                    return True
                else:
                    self.logger.warning(f"❌ 導出檔案不存在: {output_path}")
            else:
                self.logger.warning(f"❌ 導出嘗試 {attempt + 1} 失敗: {output}")
                
                # 如果不是最後一次，等待後重試
                if attempt < max_attempts - 1:
                    wait_time = 10 * (attempt + 1)
                    self.logger.info(f"等待 {wait_time} 秒後重試...")
                    time.sleep(wait_time)
        
        self.logger.error(f"❌ 所有導出嘗試都失敗")
        return False

# =====================================
# ===== 主要處理類別 =====
# =====================================

class ManifestPinningTool:
    """Manifest 定版工具（改進版 + 零失敗機制）"""

    def __init__(self):
        self.logger = setup_logger(self.__class__.__name__)
        self.repo_manager = RepoManager()
        self.mapping_reader = MappingTableReader()
        self.source_cmd_manager = SourceCommandManager()
        self.report = PinningReport()
        self.output_dir = config_manager.path_config['default_output_dir']
        self.dry_run = False
        self.zero_fail_mode = False  # 🔥 零失敗模式開關
        
        # 線程安全鎖
        self._sftp_lock = threading.Lock()

    def _monitor_failure_rate_and_auto_enable_zero_fail(self, active_syncs: List[DBInfo]):
        """監控失敗率並自動啟用零失敗模式"""
        if self.zero_fail_mode:
            return  # 已經啟用了
        
        total_dbs = len(active_syncs)
        failed_dbs = sum(1 for db in active_syncs if db.status == DBStatus.FAILED)
        
        if total_dbs > 0:
            failure_rate = (failed_dbs / total_dbs) * 100
            
            # 🔥 當失敗率超過 30% 時自動啟用零失敗模式
            if failure_rate >= 30.0:
                self.logger.warning(f"🚨 失敗率達到 {failure_rate:.1f}%，自動啟用零失敗模式")
                self._enable_zero_fail_mode_dynamically()
                
                # 立即處理所有失敗的 DB
                self._rescue_failed_dbs_immediately(active_syncs)
                
                return True
        
        return False
        
    def _enable_zero_fail_mode_dynamically(self):
        """運行時動態啟用零失敗模式"""
        if not self.zero_fail_mode:
            self.zero_fail_mode = True
            self.logger.warning("🎯 零失敗模式已動態啟用 - 不允許任何 repo sync 失敗")
            
            # 通知零失敗模式已啟用
            print("\n" + "="*80)
            print("🚨 零失敗模式已動態啟用")
            print("📋 接下來將執行以下策略：")
            print("   • 自動修復所有失敗的項目")
            print("   • 使用多層救援策略")
            print("   • 必要時執行核武級重建")
            print("   • 不允許任何 DB 最終失敗")
            print("="*80)
    
    def _notify_zero_fail_mode_enabled(self):
        """通知零失敗模式已啟用"""
        print("\n" + "="*60)
        print("🚨 零失敗模式已動態啟用")
        print("📋 接下來將執行以下策略：")
        print("   • 自動修復所有失敗的項目")
        print("   • 使用多層救援策略")
        print("   • 必要時執行核武級重建")
        print("   • 不允許任何 DB 最終失敗")
        print("="*60)
    
    def _rescue_failed_dbs_immediately(self, active_syncs: List[DBInfo]):
        """立即搶救所有失敗的 DB"""
        failed_dbs = [db for db in active_syncs if db.status == DBStatus.FAILED]
        
        if failed_dbs:
            self.logger.warning(f"🚨 立即搶救 {len(failed_dbs)} 個失敗的 DB")
            
            for db_info in failed_dbs:
                self.logger.info(f"{db_info.db_info}: 🛠️ 開始零失敗救援")
                
                # 分析失敗原因並修復
                success_rate, failed_projects = self._analyze_sync_result(db_info)
                if failed_projects:
                    if self._enhanced_repair_failed_projects_zero_tolerance(db_info, failed_projects):
                        db_info.status = DBStatus.SUCCESS
                        db_info.end_time = datetime.now()
                        self.logger.info(f"{db_info.db_info}: ✅ 零失敗救援成功")
                    else:
                        self.logger.warning(f"{db_info.db_info}: ⚠️ 標準救援失敗，準備核武級重建")
                            
    def enable_zero_fail_mode(self):
        """啟用零失敗模式"""
        self.zero_fail_mode = True
        self.logger.info("🎯 零失敗模式已啟用 - 不允許任何 repo sync 失敗")

    def load_mapping_table(self, file_path: str) -> bool:
        """載入 mapping table"""
        return self.mapping_reader.load_excel(file_path)

    def get_all_dbs(self, db_type: str = 'all') -> List[DBInfo]:
        """取得所有 DB 資訊"""
        return self.mapping_reader.get_db_info_list(db_type)

    def process_db_phase1(self, db_info: DBInfo) -> DBInfo:
        """改進版 Phase 1 處理 - 線程安全"""
        db_info.start_time = datetime.now()
        local_sftp_manager = None
        
        try:
            self.logger.info(f"開始處理 {db_info.db_info} (Phase 1)")
            
            # 建立本地目錄
            local_path = os.path.join(self.output_dir, db_info.module, db_info.db_info)
            os.makedirs(local_path, exist_ok=True)
            db_info.local_path = local_path
            
            # 檢查磁碟空間（至少需要 15GB，因為超時問題可能是空間不足）
            import shutil
            free_space = shutil.disk_usage(local_path).free
            required_space = 15 * 1024 * 1024 * 1024  # 15GB
            
            if free_space < required_space:
                raise Exception(f"磁碟空間不足: 可用 {free_space/1024/1024/1024:.1f}GB，建議至少 15GB")
            
            self.logger.debug(f"{db_info.db_info}: 磁碟空間檢查通過 ({free_space/1024/1024/1024:.1f}GB 可用)")
            
            # Step 1: SFTP 操作
            with self._sftp_lock:
                self.logger.info(f"{db_info.db_info}: 快速搜尋 manifest (線程安全)")
                
                local_sftp_manager = SFTPManager()
                
                if not local_sftp_manager.connect():
                    raise Exception("無法建立 SFTP 連線")
                
                target_version = db_info.version
                result = local_sftp_manager.find_latest_manifest(
                    db_info.sftp_path, 
                    db_info.db_info,
                    target_version
                )
                
                if not result:
                    raise Exception("找不到 manifest 檔案")
                
                manifest_full_path, manifest_name = result
                db_info.manifest_full_path = manifest_full_path
                db_info.manifest_file = manifest_name
                
                if not db_info.version:
                    match = re.match(r'manifest_(\d+)\.xml', manifest_name)
                    if match:
                        db_info.version = match.group(1)
                        self.logger.info(f"{db_info.db_info}: 檢測到版本 {db_info.version}")
                
                local_manifest = os.path.join(local_path, manifest_name)
                if not local_sftp_manager.download_file(manifest_full_path, local_manifest):
                    raise Exception("下載 manifest 失敗")
                
                self.logger.info(f"{db_info.db_info}: manifest 下載完成: {manifest_name}")
                
                local_sftp_manager.disconnect()
                self.logger.info(f"{db_info.db_info}: ✅ SFTP 連線已立即斷開")
                local_sftp_manager = None
            
            # Step 2: 檢查 repo 狀態
            db_info.has_existing_repo = self.repo_manager.check_repo_exists(local_path)
            
            # Step 3: 獲取 source command
            self.logger.info(f"{db_info.db_info}: 獲取 source command")
            source_cmd = self.source_cmd_manager.get_source_command(db_info, self.mapping_reader.df)
            if not source_cmd:
                raise Exception("無法取得 source command")
            
            db_info.actual_source_cmd = source_cmd
            self.logger.info(f"{db_info.db_info}: source command 獲取成功")
            
            # Step 4: 執行 repo init（如果需要）
            self.logger.info(f"{db_info.db_info}: 執行 repo 初始化")
            if not db_info.has_existing_repo:
                self.logger.info(f"{db_info.db_info}: .repo 目錄不存在，執行完整 repo init")
                if not self.repo_manager.repo_init(local_path, source_cmd):
                    raise Exception("Repo init 失敗")
            else:
                self.logger.info(f"{db_info.db_info}: .repo 目錄存在，跳過 repo init")
            
            # 🔥 Step 5: 應用 manifest（這是關鍵步驟）
            self.logger.info(f"{db_info.db_info}: 開始應用 manifest（可能需要較長時間）")
            if not self.repo_manager.apply_manifest(local_path, local_manifest):
                raise Exception("套用 manifest 失敗")
            
            self.logger.info(f"{db_info.db_info}: ✅ repo 初始化完成")
            
            # Step 6: 啟動 repo sync
            if not self.dry_run:
                self.logger.info(f"{db_info.db_info}: 啟動 repo sync")
                process = self.repo_manager.start_repo_sync_async(local_path, db_info.db_info)
                if not process:
                    raise Exception("啟動 repo sync 失敗")
                
                db_info.sync_process = process
                self.logger.info(f"{db_info.db_info}: repo sync 已啟動 (PID: {process.pid})")
            else:
                db_info.status = DBStatus.SKIPPED
                db_info.end_time = datetime.now()
                self.logger.info(f"{db_info.db_info}: 測試模式 - 跳過 repo sync")
            
            self.logger.info(f"{db_info.db_info}: ✅ Phase 1 完成")
            
        except Exception as e:
            db_info.status = DBStatus.FAILED
            db_info.error_message = str(e)
            db_info.end_time = datetime.now()
            self.logger.error(f"{db_info.db_info}: ❌ Phase 1 失敗 - {str(e)}")
        finally:
            # 確保 SFTP 連線一定會被斷開
            if local_sftp_manager:
                try:
                    local_sftp_manager.disconnect()
                    self.logger.debug(f"{db_info.db_info}: 確保 SFTP 連線已斷開")
                except:
                    pass
        
        return db_info

    def process_db_phase2(self, db_info: DBInfo) -> DBInfo:
        """處理 DB 的第二階段：完成工作 - 支援部分成功"""
        if self.zero_fail_mode:
            return self.process_db_phase2_zero_fail(db_info)
        
        try:
            self.logger.info(f"{db_info.db_info}: 開始 Phase 2")
            
            if self.dry_run:
                db_info.status = DBStatus.SKIPPED
                db_info.end_time = datetime.now()
                self.logger.info(f"{db_info.db_info}: 測試模式完成")
                return db_info
            
            # 檢查 sync 進程狀態
            sync_result = None
            if db_info.sync_process:
                poll = self.repo_manager.check_process_status(
                    db_info.db_info, 
                    db_info.sync_process
                )
                
                if poll is None:
                    self.logger.debug(f"{db_info.db_info}: repo sync 仍在執行中")
                    return db_info  # 還在執行中
                
                sync_result = poll
                
                # 記錄 sync log 路徑
                if hasattr(db_info.sync_process, '_log_file_path'):
                    db_info.sync_log_path = db_info.sync_process._log_file_path
            
            # 🔥 智能判斷：檢查是否為部分成功
            if sync_result == 1:  # 返回碼 1 可能是部分失敗
                success_rate, failed_projects = self._analyze_sync_result(db_info)
                
                if success_rate >= 95.0:  # 🔥 95% 以上成功率就算成功
                    db_info.status = DBStatus.SUCCESS
                    db_info.end_time = datetime.now()
                    
                    warning_msg = f"部分成功 ({success_rate:.1f}%)，失敗項目: {len(failed_projects)} 個"
                    if failed_projects:
                        warning_msg += f" - {', '.join(failed_projects[:3])}"
                        if len(failed_projects) > 3:
                            warning_msg += f" 等 {len(failed_projects)} 個"
                    
                    db_info.error_message = warning_msg
                    
                    elapsed = db_info.end_time - db_info.start_time
                    self.logger.info(f"{db_info.db_info}: ✅ 部分成功完成 ({success_rate:.1f}%) (耗時: {elapsed})")
                    
                    # 嘗試導出 manifest
                    self.logger.info(f"{db_info.db_info}: 嘗試導出版本資訊...")
                    export_success = self.repo_manager.export_manifest(db_info.local_path)
                    
                    if not export_success:
                        self.logger.warning(f"{db_info.db_info}: ⚠️ manifest 導出失敗，但 sync 部分成功")
                    
                    return db_info
                else:
                    # 成功率太低，算失敗
                    raise Exception(f"同步成功率太低 ({success_rate:.1f}%)，失敗項目: {len(failed_projects)} 個")
            
            elif sync_result == 0:
                # 完全成功
                db_info.status = DBStatus.SUCCESS
                db_info.end_time = datetime.now()
                
                elapsed = db_info.end_time - db_info.start_time
                self.logger.info(f"{db_info.db_info}: ✅ 完全成功 (耗時: {elapsed})")
                
                # 嘗試導出 manifest
                self.logger.info(f"{db_info.db_info}: 嘗試導出版本資訊...")
                export_success = self.repo_manager.export_manifest(db_info.local_path)
                
                if not export_success:
                    self.logger.warning(f"{db_info.db_info}: ⚠️ manifest 導出失敗，但 sync 已成功")
                    if not db_info.error_message:
                        db_info.error_message = "Sync 成功但 manifest 導出失敗"
            
            else:
                # 其他錯誤碼，算失敗
                raise Exception(f"Repo sync 失敗 (返回碼: {sync_result})")
            
        except Exception as e:
            db_info.status = DBStatus.FAILED
            db_info.error_message = str(e)
            db_info.end_time = datetime.now()
            self.logger.error(f"{db_info.db_info}: Phase 2 失敗 - {str(e)}")
        
        return db_info

    def process_db_phase2_zero_fail(self, db_info: DBInfo) -> DBInfo:
        """零失敗的 Phase 2 處理"""
        try:
            self.logger.info(f"{db_info.db_info}: 開始零失敗 Phase 2")
            
            if self.dry_run:
                db_info.status = DBStatus.SKIPPED
                db_info.end_time = datetime.now()
                return db_info
            
            # 檢查 sync 進程狀態
            sync_result = None
            if db_info.sync_process:
                poll = self.repo_manager.check_process_status(
                    db_info.db_info, 
                    db_info.sync_process
                )
                
                if poll is None:
                    return db_info  # 還在執行中
                
                sync_result = poll
                
                if hasattr(db_info.sync_process, '_log_file_path'):
                    db_info.sync_log_path = db_info.sync_process._log_file_path
            
            # 🔥 零容忍：無論返回碼如何，都要檢查實際結果
            success_rate, failed_projects = self._analyze_sync_result(db_info)
            
            if failed_projects:
                # 有失敗項目，必須救援
                self.logger.warning(f"{db_info.db_info}: 🚨 檢測到 {len(failed_projects)} 個失敗項目，啟動零容忍救援")
                
                if self._enhanced_repair_failed_projects_zero_tolerance(db_info, failed_projects):
                    db_info.status = DBStatus.SUCCESS
                    db_info.end_time = datetime.now()
                    
                    elapsed = db_info.end_time - db_info.start_time
                    self.logger.info(f"{db_info.db_info}: ✅ 零容忍救援成功，達到100% (耗時: {elapsed})")
                else:
                    db_info.status = DBStatus.FAILED
                    db_info.error_message = f"零容忍救援失敗，無法處理 {len(failed_projects)} 個失敗項目"
                    db_info.end_time = datetime.now()
                    
                    elapsed = db_info.end_time - db_info.start_time
                    self.logger.error(f"{db_info.db_info}: ❌ 零容忍救援失敗 (耗時: {elapsed})")
            else:
                # 沒有失敗項目，真正的成功
                db_info.status = DBStatus.SUCCESS
                db_info.end_time = datetime.now()
                
                elapsed = db_info.end_time - db_info.start_time
                self.logger.info(f"{db_info.db_info}: ✅ 完美完成，無失敗項目 (耗時: {elapsed})")
            
            # 嘗試導出 manifest
            if db_info.status == DBStatus.SUCCESS:
                self.logger.info(f"{db_info.db_info}: 導出版本資訊...")
                export_success = self.repo_manager.export_manifest(db_info.local_path)
                
                if not export_success:
                    self.logger.warning(f"{db_info.db_info}: ⚠️ manifest 導出失敗，但 sync 已成功")
            
        except Exception as e:
            db_info.status = DBStatus.FAILED
            db_info.error_message = str(e)
            db_info.end_time = datetime.now()
            self.logger.error(f"{db_info.db_info}: Phase 2 異常 - {str(e)}")
        
        return db_info

    def _analyze_sync_result(self, db_info: DBInfo) -> tuple:
        """分析 sync 結果，精確提取失敗項目 - 清理版本"""
        try:
            log_file = db_info.sync_log_path
            if not log_file:
                log_file = self._get_sync_log_file(db_info)
            
            if not log_file or not os.path.exists(log_file):
                return 0.0, []
            
            total_projects = 0
            failed_projects = set()
            
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
                # 🔥 先清理 ANSI 轉義字符
                import re
                clean_content = re.sub(r'\x1b\[[0-9;]*[mK]', '', content)
                
                # 提取同步統計
                sync_pattern = r'Syncing:\s*\d+%\s*\((\d+)/(\d+)\)'
                matches = re.findall(sync_pattern, clean_content)
                
                if matches:
                    last_match = matches[-1]
                    completed = int(last_match[0])
                    total_projects = int(last_match[1])
                    self.logger.debug(f"{db_info.db_info}: 同步統計 - 完成 {completed}/{total_projects}")
                
                # 🔥 精確提取失敗項目 - 只從特定錯誤部分提取
                
                # 方式1：從 "The following projects failed" 到下一個錯誤部分
                failed_section_match = re.search(
                    r'The following projects failed[^:]*:\s*(.*?)(?=\n\s*error:|$)', 
                    clean_content, 
                    re.DOTALL | re.IGNORECASE
                )
                
                if failed_section_match:
                    failed_text = failed_section_match.group(1)
                    # 提取有效的項目路徑
                    project_lines = [line.strip() for line in failed_text.split('\n') if line.strip()]
                    for line in project_lines:
                        # 只接受以 kernel/ 開頭的有效路徑
                        if line.startswith('kernel/') and '/' in line and len(line) > 10:
                            # 清理可能的尾部字符
                            clean_project = re.sub(r'[^\w/\-_.].*$', '', line)
                            if clean_project and clean_project.count('/') >= 2:  # 至少包含 kernel/xxx/yyy
                                failed_projects.add(clean_project)
                
                # 方式2：從具體的 GitCommandError 消息中提取
                git_error_pattern = r"GitCommandError:.*?on\s+(kernel/[^\s'\"]+)\s+failed"
                git_errors = re.findall(git_error_pattern, clean_content, re.IGNORECASE)
                for project in git_errors:
                    # 清理項目路徑
                    clean_project = re.sub(r'[^\w/\-_.].*$', '', project)
                    if clean_project and clean_project.count('/') >= 2:
                        failed_projects.add(clean_project)
                
                # 方式3：從 "fatal: not a git repository" 錯誤推斷項目
                repo_error_pattern = r"fatal: not a git repository.*?/([^/\s'\"]+)\.git"
                repo_errors = re.findall(repo_error_pattern, clean_content)
                
                # 根據項目名稱推斷完整路徑
                known_project_mappings = {
                    'vts': 'kernel/android/U/test/vts',
                    'hal': 'kernel/android/U/test/vts-testcase/hal',
                    'hal-trace': 'kernel/android/U/test/vts-testcase/hal-trace'
                }
                
                for project_name in repo_errors:
                    if project_name in known_project_mappings:
                        failed_projects.add(known_project_mappings[project_name])
            
            # 🔥 清理和驗證失敗項目列表
            valid_failed_projects = []
            for project in failed_projects:
                # 驗證項目路徑格式
                if (project.startswith('kernel/') and 
                    project.count('/') >= 2 and 
                    len(project) > 10 and
                    not any(char in project for char in ['\x1b', '"', "'", ':', ' ']) and
                    re.match(r'^kernel/[a-zA-Z0-9_\-/]+$', project)):
                    valid_failed_projects.append(project)
            
            # 去重並排序
            valid_failed_projects = sorted(list(set(valid_failed_projects)))
            
            # 計算成功率
            if total_projects > 0:
                success_count = total_projects - len(valid_failed_projects)
                success_rate = (success_count / total_projects) * 100
                
                self.logger.info(f"{db_info.db_info}: 清理後分析 - 總計:{total_projects}, 成功:{success_count}, 失敗:{len(valid_failed_projects)}, 成功率:{success_rate:.1f}%")
                self.logger.info(f"{db_info.db_info}: 有效失敗項目: {valid_failed_projects}")
                
                return success_rate, valid_failed_projects
            
            return 0.0, []
            
        except Exception as e:
            self.logger.debug(f"分析同步結果失敗: {e}")
            return 0.0, []

    def _get_sync_log_file(self, db_info: DBInfo) -> str:
        """獲取 sync 日誌文件路徑 - 優先使用 unbuffer 版本"""
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

    # ========================================
    # 🔥 零失敗救援機制
    # ========================================

    def _enhanced_repair_failed_projects_zero_tolerance(self, db_info: DBInfo, failed_projects: list) -> bool:
        """零容忍修復失敗項目 - 必須達到100%成功"""
        if not failed_projects:
            return True
        
        self.logger.warning(f"{db_info.db_info}: 🚨 檢測到 {len(failed_projects)} 個失敗項目，啟動零容忍救援")
        
        # 🔥 多層救援策略
        rescue_strategies = [
            ("基礎修復", self._basic_repair_strategy),
            ("網路重置修復", self._network_reset_strategy), 
            ("完全重建修復", self._complete_rebuild_strategy),
            ("終極救援", self._ultimate_rescue_strategy)
        ]
        
        for strategy_name, strategy_func in rescue_strategies:
            self.logger.info(f"{db_info.db_info}: 🔧 執行 {strategy_name}...")
            
            if strategy_func(db_info, failed_projects):
                # 驗證修復結果
                remaining_failures = self._verify_repair_result(db_info)
                if not remaining_failures:
                    self.logger.info(f"{db_info.db_info}: ✅ {strategy_name} 成功，達到100%完成")
                    return True
                else:
                    self.logger.warning(f"{db_info.db_info}: ⚠️ {strategy_name} 後仍有 {len(remaining_failures)} 個失敗")
                    failed_projects = remaining_failures  # 更新失敗列表
            else:
                self.logger.warning(f"{db_info.db_info}: ❌ {strategy_name} 失敗，嘗試下一個策略")
        
        # 如果所有策略都失敗，記錄詳細錯誤並強制重來
        self.logger.error(f"{db_info.db_info}: 💥 所有救援策略失敗，執行最後的核武級重建")
        return self._nuclear_rebuild(db_info)

    def _basic_repair_strategy(self, db_info: DBInfo, failed_projects: list) -> bool:
        """基礎修復策略：清理並重新同步"""
        try:
            self.logger.info(f"{db_info.db_info}: 🔧 基礎修復：清理 {len(failed_projects)} 個失敗項目")
            
            # 逐個清理失敗項目
            for project in failed_projects:
                self._thorough_cleanup_project(db_info, project)
            
            # 單線程重新同步
            projects_str = ' '.join([f'"{project}"' for project in failed_projects])
            sync_cmd = f"{config_manager.repo_config['repo_command']} sync -j1 --force-sync --no-clone-bundle {projects_str}"
            
            success, output = self.repo_manager.run_command(
                sync_cmd,
                cwd=db_info.local_path,
                timeout=1800  # 30分鐘
            )
            
            if success:
                self.logger.info(f"{db_info.db_info}: ✅ 基礎修復完成")
                return True
            else:
                self.logger.warning(f"{db_info.db_info}: ⚠️ 基礎修復失敗: {output[-500:]}")
                return False
                
        except Exception as e:
            self.logger.error(f"{db_info.db_info}: ❌ 基礎修復異常: {e}")
            return False

    def _network_reset_strategy(self, db_info: DBInfo, failed_projects: list) -> bool:
        """網路重置策略：重置網路並換源重試"""
        try:
            self.logger.info(f"{db_info.db_info}: 🌐 網路重置修復")
            
            # 🔥 清理網路相關快取
            cache_cleanup_commands = [
                "git config --global --unset http.proxy 2>/dev/null || true",
                "git config --global --unset https.proxy 2>/dev/null || true", 
                "git config --global http.postBuffer 524288000",
                "git config --global http.maxRequestBuffer 100M",
                "git config --global core.compression 0",
            ]
            
            for cmd in cache_cleanup_commands:
                os.system(cmd)
            
            # 🔥 逐個項目深度修復
            for project in failed_projects:
                self.logger.info(f"{db_info.db_info}: 🔄 深度修復項目: {project}")
                
                # 完全清理項目
                self._thorough_cleanup_project(db_info, project)
                
                # 單獨同步這個項目（更激進的參數）
                repair_commands = [
                    f"repo sync -j1 --force-sync --no-clone-bundle --current-branch {project}",
                    f"repo sync -j1 --force-sync --no-tags {project}",
                    f"repo sync -j1 --force-broken {project}",
                ]
                
                for cmd in repair_commands:
                    full_cmd = f"{config_manager.repo_config['repo_command']} " + cmd.replace("repo ", "")
                    
                    success, output = self.repo_manager.run_command(
                        full_cmd,
                        cwd=db_info.local_path,
                        timeout=900  # 15分鐘每個項目
                    )
                    
                    if success:
                        self.logger.info(f"{db_info.db_info}: ✅ 項目 {project} 修復成功")
                        break
                    else:
                        self.logger.debug(f"{db_info.db_info}: 嘗試下一個命令: {output[-200:]}")
                else:
                    self.logger.warning(f"{db_info.db_info}: ⚠️ 項目 {project} 所有命令都失敗")
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"{db_info.db_info}: ❌ 網路重置策略異常: {e}")
            return False

    def _complete_rebuild_strategy(self, db_info: DBInfo, failed_projects: list) -> bool:
        """完全重建策略：重建失敗項目的 git 庫"""
        try:
            self.logger.info(f"{db_info.db_info}: 🏗️ 完全重建策略")
            
            # 🔥 核武級清理：移除所有相關的 .repo 數據
            for project in failed_projects:
                self.logger.info(f"{db_info.db_info}: 💣 核武級清理項目: {project}")
                
                # 找到所有可能的項目相關目錄
                cleanup_patterns = [
                    os.path.join(db_info.local_path, '.repo', 'projects', f"{project}.git"),
                    os.path.join(db_info.local_path, '.repo', 'project-objects', f"{project}.git"),
                    os.path.join(db_info.local_path, '.repo', 'projects', project),
                    os.path.join(db_info.local_path, '.repo', 'project-objects', project),
                    os.path.join(db_info.local_path, project),
                ]
                
                # 還要清理可能的符號連結和引用
                for pattern in cleanup_patterns:
                    if os.path.exists(pattern):
                        try:
                            import shutil
                            if os.path.islink(pattern):
                                os.unlink(pattern)
                            elif os.path.isdir(pattern):
                                shutil.rmtree(pattern)
                            else:
                                os.remove(pattern)
                            self.logger.debug(f"清理: {pattern}")
                        except Exception as e:
                            # 強制清理
                            self.logger.debug(f"強制清理: {pattern}")
                            os.system(f'rm -rf "{pattern}" 2>/dev/null || true')
            
            # 🔥 重建 project 映射
            self.logger.info(f"{db_info.db_info}: 🔄 重建項目映射")
            
            # 強制重新初始化這些項目
            init_cmd = f"{config_manager.repo_config['repo_command']} sync --force-sync -j1 " + " ".join([f'"{project}"' for project in failed_projects])
            
            success, output = self.repo_manager.run_command(
                init_cmd,
                cwd=db_info.local_path,
                timeout=2400  # 40分鐘
            )
            
            if success:
                self.logger.info(f"{db_info.db_info}: ✅ 完全重建成功")
                return True
            else:
                self.logger.warning(f"{db_info.db_info}: ⚠️ 完全重建失敗: {output[-500:]}")
                return False
                
        except Exception as e:
            self.logger.error(f"{db_info.db_info}: ❌ 完全重建策略異常: {e}")
            return False

    def _ultimate_rescue_strategy(self, db_info: DBInfo, failed_projects: list) -> bool:
        """終極救援策略：手動 git clone 失敗的項目"""
        try:
            self.logger.warning(f"{db_info.db_info}: 🆘 終極救援：手動克隆失敗項目")
            
            # 🔥 解析 manifest 獲取項目的真實 git URL
            manifest_path = os.path.join(db_info.local_path, db_info.manifest_file)
            if not os.path.exists(manifest_path):
                self.logger.error(f"{db_info.db_info}: ❌ Manifest 文件不存在")
                return False
            
            project_urls = self._extract_project_urls_from_manifest(manifest_path, failed_projects)
            
            for project in failed_projects:
                if project not in project_urls:
                    self.logger.warning(f"{db_info.db_info}: ⚠️ 無法找到項目 {project} 的 URL")
                    continue
                
                git_url = project_urls[project]
                project_dir = os.path.join(db_info.local_path, project)
                
                self.logger.info(f"{db_info.db_info}: 🔄 手動克隆: {project}")
                
                # 確保目錄不存在
                if os.path.exists(project_dir):
                    import shutil
                    shutil.rmtree(project_dir)
                
                # 手動 git clone
                clone_cmd = f"git clone --depth 1 {git_url} {project_dir}"
                
                success, output = self.repo_manager.run_command(
                    clone_cmd,
                    cwd=db_info.local_path,
                    timeout=600  # 10分鐘每個項目
                )
                
                if not success:
                    self.logger.error(f"{db_info.db_info}: ❌ 手動克隆 {project} 失敗: {output}")
                    return False
                
                self.logger.info(f"{db_info.db_info}: ✅ 手動克隆 {project} 成功")
            
            return True
            
        except Exception as e:
            self.logger.error(f"{db_info.db_info}: ❌ 終極救援異常: {e}")
            return False

    def _nuclear_rebuild(self, db_info: DBInfo) -> bool:
        """核武級重建：完全從頭開始"""
        try:
            self.logger.warning(f"{db_info.db_info}: ☢️ 執行核武級重建 - 完全從頭開始")
            
            # 🔥 保存重要文件
            manifest_backup = None
            if db_info.manifest_file:
                src = os.path.join(db_info.local_path, db_info.manifest_file)
                if os.path.exists(src):
                    import tempfile
                    manifest_backup = tempfile.mktemp(suffix='.xml')
                    import shutil
                    shutil.copy2(src, manifest_backup)
            
            # 🔥 徹底摧毀並重建
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_path = f"{db_info.local_path}_NUCLEAR_BACKUP_{timestamp}"
            
            try:
                os.rename(db_info.local_path, backup_path)
                self.logger.info(f"{db_info.db_info}: 🗂️ 備份舊目錄: {backup_path}")
            except:
                import shutil
                shutil.rmtree(db_info.local_path)
            
            # 重建目錄
            os.makedirs(db_info.local_path, exist_ok=True)
            
            # 恢復 manifest
            if manifest_backup and os.path.exists(manifest_backup):
                dest = os.path.join(db_info.local_path, db_info.manifest_file)
                shutil.copy2(manifest_backup, dest)
                os.remove(manifest_backup)
            
            # 🔥 完全重新執行初始化流程
            if not db_info.actual_source_cmd:
                self.logger.error(f"{db_info.db_info}: ❌ 缺少 source command，無法重建")
                return False
            
            # 重新 repo init
            if not self.repo_manager.repo_init(db_info.local_path, db_info.actual_source_cmd):
                self.logger.error(f"{db_info.db_info}: ❌ 核武級 repo init 失敗")
                return False
            
            # 重新應用 manifest
            manifest_path = os.path.join(db_info.local_path, db_info.manifest_file)
            if not self.repo_manager.apply_manifest(db_info.local_path, manifest_path):
                self.logger.error(f"{db_info.db_info}: ❌ 核武級 apply manifest 失敗")
                return False
            
            # 🔥 使用最保守的同步策略
            nuclear_sync_cmd = f"{config_manager.repo_config['repo_command']} sync -j1 --force-sync --force-broken --no-clone-bundle"
            
            success, output = self.repo_manager.run_command(
                nuclear_sync_cmd,
                cwd=db_info.local_path,
                timeout=7200  # 2小時
            )
            
            if success:
                self.logger.info(f"{db_info.db_info}: ✅ 核武級重建成功！")
                
                # 背景刪除備份
                delete_cmd = f"nohup rm -rf '{backup_path}' >/dev/null 2>&1 &"
                os.system(delete_cmd)
                
                return True
            else:
                self.logger.error(f"{db_info.db_info}: ❌ 核武級重建也失敗了: {output}")
                return False
            
        except Exception as e:
            self.logger.error(f"{db_info.db_info}: 💥 核武級重建異常: {e}")
            return False

    def _thorough_cleanup_project(self, db_info: DBInfo, project: str):
        """徹底清理單個項目的所有相關文件"""
        cleanup_paths = [
            os.path.join(db_info.local_path, '.repo', 'projects', f"{project}.git"),
            os.path.join(db_info.local_path, '.repo', 'project-objects', f"{project}.git"),
            os.path.join(db_info.local_path, '.repo', 'projects', project),
            os.path.join(db_info.local_path, '.repo', 'project-objects', project),
            os.path.join(db_info.local_path, project),
        ]
        
        for path in cleanup_paths:
            if os.path.exists(path):
                try:
                    import shutil
                    if os.path.islink(path):
                        os.unlink(path)
                    elif os.path.isdir(path):
                        shutil.rmtree(path)
                    else:
                        os.remove(path)
                except:
                    # 強制清理
                    os.system(f'chmod -R 777 "{path}" 2>/dev/null || true')
                    os.system(f'rm -rf "{path}" 2>/dev/null || true')

    def _verify_repair_result(self, db_info: DBInfo) -> list:
        """驗證修復結果，返回仍然失敗的項目列表"""
        try:
            # 執行 repo status 檢查
            status_cmd = f"{config_manager.repo_config['repo_command']} status"
            success, output = self.repo_manager.run_command(
                status_cmd,
                cwd=db_info.local_path,
                timeout=300
            )
            
            if not success:
                self.logger.warning(f"{db_info.db_info}: repo status 檢查失敗")
                return []
            
            # 檢查是否還有錯誤
            if 'fatal:' in output or 'error:' in output:
                # 解析仍然失敗的項目
                remaining_failures = []
                for line in output.split('\n'):
                    if 'fatal:' in line or 'error:' in line:
                        # 嘗試提取項目名稱
                        project_match = re.search(r'(kernel/[^\s]+)', line)
                        if project_match:
                            remaining_failures.append(project_match.group(1))
                
                return list(set(remaining_failures))
            
            return []
            
        except Exception as e:
            self.logger.debug(f"驗證修復結果時異常: {e}")
            return []

    def _extract_project_urls_from_manifest(self, manifest_path: str, projects: list) -> dict:
        """從 manifest 文件提取項目的 git URL"""
        project_urls = {}
        
        try:
            import xml.etree.ElementTree as ET
            tree = ET.parse(manifest_path)
            root = tree.getroot()
            
            # 找到 remote 定義
            remotes = {}
            for remote in root.findall('remote'):
                name = remote.get('name')
                fetch = remote.get('fetch')
                if name and fetch:
                    remotes[name] = fetch
            
            # 找到項目定義
            for project_elem in root.findall('project'):
                path = project_elem.get('path')
                name = project_elem.get('name')
                remote = project_elem.get('remote', 'origin')
                
                if path in projects and remote in remotes:
                    base_url = remotes[remote].rstrip('/')
                    project_url = f"{base_url}/{name}"
                    project_urls[path] = project_url
                    
        except Exception as e:
            self.logger.debug(f"解析 manifest 失敗: {e}")
        
        return project_urls

    # ========================================
    # 主要處理函數
    # ========================================

    def process_dbs_async(self, db_list: List[str], db_versions: Dict[str, str] = None):
        """異步處理多個 DB - 根據模式選擇處理方式"""
        if self.zero_fail_mode:
            return self.process_dbs_async_zero_fail(db_list, db_versions)
        else:
            return self.process_dbs_async_standard(db_list, db_versions)

    def process_dbs_async_standard(self, db_list: List[str], db_versions: Dict[str, str] = None):
        """標準異步處理多個 DB - 徹底避免 SFTP 衝突"""
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
                        db_info.end_time = datetime.now()
                        phase1_results.append(db_info)
            
            # 等待所有 sync 完成（增強版監控）
            if not self.dry_run:
                self.logger.info("等待所有 repo sync 完成...（增強版進度監控）")
                self._wait_for_all_syncs_enhanced(phase1_results)
                # 🔥 狀態已在 _wait_for_all_syncs_enhanced 中更新，不需重複更新
            
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
                        db_info.end_time = datetime.now()
                        self.report.add_db(db_info)
            
            self.logger.info("所有 DB 處理完成")
            
        except Exception as e:
            self.logger.error(f"處理過程發生錯誤: {e}")

    def process_dbs_async_zero_fail(self, db_list: List[str], db_versions: Dict[str, str] = None):
        """零失敗容忍的異步處理多個 DB"""
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

        self.logger.info(f"🎯 零失敗模式處理 {len(db_infos)} 個 DB")
        
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
                        db_info.end_time = datetime.now()
                        phase1_results.append(db_info)
            
            # 🔥 使用零失敗監控等待所有 sync 完成
            if not self.dry_run:
                self.logger.info("🎯 啟動零失敗監控，等待所有 repo sync 達到100%...")
                self._wait_for_all_syncs_enhanced_zero_fail(phase1_results)
            
            # Phase 2: 最終檢查和清理（使用零失敗版本）
            self.logger.info("執行 Phase 2: 零失敗最終檢查")
            
            with ThreadPoolExecutor(max_workers=config_manager.parallel_config['max_workers']) as executor:
                futures = {executor.submit(self.process_db_phase2_zero_fail, db_info): db_info for db_info in phase1_results}
                
                for future in as_completed(futures):
                    try:
                        result = future.result(timeout=60)
                        self.report.add_db(result)
                    except Exception as e:
                        db_info = futures[future]
                        self.logger.error(f"{db_info.db_info}: Phase 2 異常 - {e}")
                        db_info.status = DBStatus.FAILED
                        db_info.error_message = str(e)
                        db_info.end_time = datetime.now()
                        self.report.add_db(db_info)
            
            # 🔥 零失敗最終驗證
            self._final_zero_fail_verification()
            
            self.logger.info("所有 DB 處理完成")
            
        except Exception as e:
            self.logger.error(f"處理過程發生錯誤: {e}")

    def _wait_for_all_syncs_enhanced(self, db_results: List[DBInfo]):
        """完整版進度監控 - 包含動態零失敗模式啟用"""
        max_wait_time = config_manager.repo_config['sync_timeout']
        start_wait = time.time()
        
        active_syncs = [db for db in db_results if db.sync_process and db.status != DBStatus.FAILED]
        self.logger.info(f"監控 {len(active_syncs)} 個活躍的 repo sync 進程")
        
        # 🔥 零失敗模式動態控制變數
        auto_zero_fail_triggered = False
        failure_threshold = 2  # 失敗數量閾值
        failure_rate_threshold = 30.0  # 失敗率閾值 (%)
        last_failure_check = time.time()
        
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
                'error_count': 0,
                'critical_errors': []  # 🔥 記錄嚴重錯誤
            }
        
        check_interval = 30  # 30秒檢查一次
        
        while True:
            all_complete = True
            elapsed = int(time.time() - start_wait)
            current_time = time.time()
            
            # 🔥 每分鐘檢查一次失敗率，決定是否啟用零失敗模式
            if current_time - last_failure_check > 60:  # 每分鐘檢查
                if self._check_and_enable_zero_fail_mode(active_syncs, auto_zero_fail_triggered):
                    auto_zero_fail_triggered = True
                    # 切換到零失敗監控模式
                    self.logger.info("🎯 切換到零失敗監控模式")
                    self._wait_for_all_syncs_enhanced_zero_fail(active_syncs)
                    return
                last_failure_check = current_time
            
            print("\n" + "="*100)
            print(f"📊 Repo Sync 進度監控 - 已等待 {elapsed}s")
            if not self.zero_fail_mode and not auto_zero_fail_triggered:
                print("🔍 智能失敗檢測模式 (自動切換零失敗)")
            print("="*100)
            
            current_failed_count = 0
            current_running_count = 0
            current_completed_count = 0
            
            for db_info in active_syncs:
                if db_info.status == DBStatus.FAILED:
                    current_failed_count += 1
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
                            current_running_count += 1
                            
                            # 🔥 檢查嚴重錯誤，可能觸發零失敗模式
                            critical_error = self._check_for_critical_errors(db_info, tracker)
                            if critical_error and not auto_zero_fail_triggered:
                                self.logger.warning(f"🚨 {db_name}: 檢測到嚴重錯誤: {critical_error}")
                                tracker['critical_errors'].append(critical_error)
                                
                                # 如果嚴重錯誤累積或者是致命錯誤，立即啟用零失敗模式
                                if len(tracker['critical_errors']) >= 2 or "FATAL" in critical_error:
                                    self.logger.warning(f"🎯 因嚴重錯誤立即啟用零失敗模式")
                                    self._enable_zero_fail_mode_dynamically()
                                    auto_zero_fail_triggered = True
                                    
                                    # 立即切換到零失敗監控
                                    self._wait_for_all_syncs_enhanced_zero_fail(active_syncs)
                                    return
                            
                            # 更新進度信息
                            self._update_progress_info(db_info, tracker)
                            
                            runtime = datetime.now() - tracker['start_time']
                            runtime_str = f"{int(runtime.total_seconds()//60)}:{int(runtime.total_seconds()%60):02d}"
                            
                            progress = tracker['estimated_progress']
                            bar_length = 20
                            filled = int(bar_length * progress / 100)
                            bar = "█" * filled + "░" * (bar_length - filled)
                            
                            activity = tracker.get('current_project', '').split('/')[-1] or tracker.get('current_activity', '同步中')
                            if len(activity) > 15:
                                activity = activity[:12] + "..."
                            
                            # 🔥 顯示錯誤狀態
                            status_info = ""
                            if tracker['critical_errors']:
                                status_info = f" ⚠️{len(tracker['critical_errors'])}"
                            
                            print(f"🔄 {display_name:30s} │{bar}│ {progress:3d}% │ {runtime_str} │ {activity}{status_info}")
                            
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
                                current_failed_count += 1
                                print(f"⏰ {display_name:30s} │ 超時終止")
                                
                        elif poll == 0:  # 成功完成
                            current_completed_count += 1
                            runtime = datetime.now() - tracker['start_time']
                            runtime_str = f"{int(runtime.total_seconds()//60)}:{int(runtime.total_seconds()%60):02d}"
                            
                            bar = "█" * 20
                            print(f"✅ {display_name:30s} │{bar}│ 100% │ {runtime_str} │ 完成")
                            
                        else:  # 失敗 (poll != 0)
                            current_failed_count += 1
                            runtime = datetime.now() - tracker['start_time']
                            runtime_str = f"{int(runtime.total_seconds()//60)}:{int(runtime.total_seconds()%60):02d}"
                            
                            # 🔥 分析失敗原因
                            error_msg = f"Sync 失敗 (返回碼: {poll})"
                            
                            # 檢查是否需要立即啟用零失敗模式
                            if poll == 1:  # 部分失敗，可能可以救援
                                success_rate, failed_projects = self._analyze_sync_result(db_info)
                                if failed_projects:
                                    error_msg += f" - {len(failed_projects)} 個項目失敗"
                                    
                                    # 🔥 如果失敗項目很多，考慮啟用零失敗模式
                                    if len(failed_projects) > 10 and not auto_zero_fail_triggered:
                                        self.logger.warning(f"🚨 {db_name}: 大量項目失敗 ({len(failed_projects)} 個)，建議啟用零失敗模式")
                            
                            db_info.status = DBStatus.FAILED
                            db_info.error_message = error_msg
                            print(f"❌ {display_name:30s} │{'':20s}│   0% │ {runtime_str} │ {error_msg[:30]}")
                            
                    except Exception as e:
                        self.logger.error(f"{db_name}: 檢查進程狀態失敗: {e}")
                        db_info.status = DBStatus.FAILED
                        db_info.error_message = f"進程監控失敗: {e}"
                        current_failed_count += 1
                        print(f"⚠️  {display_name:30s} │ 監控錯誤 │   0% │ {str(e)[:30]}")
            
            # 🔥 實時失敗率檢查
            total_processed = current_failed_count + current_completed_count
            if total_processed > 0:
                failure_rate = (current_failed_count / total_processed) * 100
                
                # 如果失敗率過高且還有運行中的進程，考慮啟用零失敗模式
                if (failure_rate >= failure_rate_threshold and 
                    current_running_count > 0 and 
                    not auto_zero_fail_triggered and
                    current_failed_count >= failure_threshold):
                    
                    self.logger.warning(f"🚨 失敗率達到 {failure_rate:.1f}% ({current_failed_count}/{total_processed})，自動啟用零失敗模式")
                    self._enable_zero_fail_mode_dynamically()
                    auto_zero_fail_triggered = True
                    
                    # 立即救援已失敗的 DB
                    self._rescue_failed_dbs_immediately(active_syncs)
                    
                    # 切換到零失敗監控
                    self._wait_for_all_syncs_enhanced_zero_fail(active_syncs)
                    return
            
            # 顯示總體統計
            print("-"*100)
            print(f"📈 總計: 運行中 {current_running_count} | 完成 {current_completed_count} | 失敗 {current_failed_count}")
            
            if current_failed_count > 0:
                total_dbs = len(active_syncs)
                failure_rate = (current_failed_count / total_dbs) * 100
                print(f"📊 失敗率: {failure_rate:.1f}% ({current_failed_count}/{total_dbs})")
                
                if failure_rate >= failure_rate_threshold * 0.7:  # 70% of threshold
                    print(f"⚠️  接近零失敗模式觸發閾值 ({failure_rate_threshold}%)")
            
            # 🔥 零失敗模式提示
            if not self.zero_fail_mode and not auto_zero_fail_triggered:
                if current_failed_count >= failure_threshold - 1:
                    print(f"🎯 智能提示: 再有 {failure_threshold - current_failed_count} 個失敗將自動啟用零失敗模式")
            
            if all_complete or (time.time() - start_wait) > max_wait_time:
                break
            
            # 等待下次檢查
            time.sleep(check_interval)
        
        # 最終統計
        completed = sum(1 for db in active_syncs if db.sync_process and db.sync_process.poll() == 0)
        failed = sum(1 for db in active_syncs if db.status == DBStatus.FAILED)
        
        print(f"\n📋 Repo sync 最終統計:")
        print(f"   ✅ 成功: {completed}")
        print(f"   ❌ 失敗: {failed}")
        
        # 🔥 如果最終還有失敗且未啟用零失敗模式，詢問是否啟用
        if failed > 0 and not self.zero_fail_mode and not auto_zero_fail_triggered:
            print(f"\n🤔 檢測到 {failed} 個失敗的 DB")
            if hasattr(sys, 'stdin') and sys.stdin.isatty():
                response = input("是否要啟用零失敗模式進行救援? (y/N): ").strip().lower()
                if response == 'y':
                    self.logger.info("🎯 用戶手動啟用零失敗模式")
                    self._enable_zero_fail_mode_dynamically()
                    self._rescue_failed_dbs_immediately(active_syncs)
        
        self.logger.info(f"📋 Repo sync 完成統計: 成功 {completed}, 失敗 {failed}")

    def _check_for_critical_errors(self, db_info: DBInfo, tracker: dict) -> str:
        """檢查嚴重錯誤，可能觸發零失敗模式"""
        try:
            log_file = tracker.get('log_file', '')
            
            if not log_file or not os.path.exists(log_file):
                return ""
            
            current_size = os.path.getsize(log_file)
            
            # 只讀取最後 2KB 的內容
            try:
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    read_size = min(current_size, 2048)
                    f.seek(max(0, current_size - read_size))
                    recent_content = f.read()
                    
                    # 🔥 分級錯誤檢測
                    fatal_errors = [
                        'fatal: not a git repository',
                        'fatal: unable to access',
                        'fatal: repository',
                    ]
                    
                    critical_errors = [
                        'error: Unable to fully sync the tree',
                        'error: Downloading network changes failed',
                        'GitCommandError',
                        'Repo command failed',
                    ]
                    
                    warning_errors = [
                        'error: Checking out local projects failed',
                        'Cannot checkout',
                        'timeout',
                    ]
                    
                    # 檢查致命錯誤
                    for error in fatal_errors:
                        if error in recent_content:
                            return f"FATAL:{error}"
                    
                    # 檢查嚴重錯誤
                    for error in critical_errors:
                        if error in recent_content:
                            return f"CRITICAL:{error}"
                    
                    # 檢查警告級錯誤
                    for error in warning_errors:
                        if error in recent_content:
                            return f"WARNING:{error}"
                            
            except Exception as e:
                self.logger.debug(f"檢查嚴重錯誤時讀取日誌失敗: {e}")
            
            return ""
            
        except Exception as e:
            self.logger.debug(f"嚴重錯誤檢查異常: {e}")
            return ""
            
    def _check_and_enable_zero_fail_mode(self, active_syncs: List[DBInfo], auto_triggered: bool) -> bool:
        """檢查是否應該啟用零失敗模式"""
        if self.zero_fail_mode or auto_triggered:
            return False
        
        failed_count = sum(1 for db in active_syncs if db.status == DBStatus.FAILED)
        total_count = len(active_syncs)
        
        if total_count == 0:
            return False
        
        failure_rate = (failed_count / total_count) * 100
        
        # 觸發條件：
        # 1. 失敗數量 >= 2 個
        # 2. 失敗率 >= 30%
        # 3. 或者失敗數量 >= 總數的一半
        should_trigger = (
            failed_count >= 2 or
            failure_rate >= 30.0 or
            failed_count >= total_count // 2
        )
        
        if should_trigger:
            self.logger.warning(f"🚨 觸發零失敗模式條件: 失敗 {failed_count}/{total_count} ({failure_rate:.1f}%)")
            self._enable_zero_fail_mode_dynamically()
            return True
        
        return False
        
    def _wait_for_all_syncs_enhanced_zero_fail(self, db_results: List[DBInfo]):
        """零失敗容忍的進度監控"""
        max_wait_time = config_manager.repo_config['sync_timeout']
        start_wait = time.time()
        
        active_syncs = [db for db in db_results if db.sync_process and db.status != DBStatus.FAILED]
        self.logger.info(f"🔍 零失敗監控 {len(active_syncs)} 個活躍的 repo sync 進程")
        
        if not active_syncs:
            return
        
        # 初始化進度追蹤
        progress_tracker = {}
        for db_info in active_syncs:
            progress_tracker[db_info.db_info] = {
                'start_time': db_info.start_time or datetime.now(),
                'log_file': self._get_sync_log_file(db_info),
                'error_count': 0,
                'estimated_progress': 0,
                'current_activity': '初始化中...',
                'rescue_attempts': 0,  # 🔥 新增：救援嘗試次數
                'last_rescue_time': None,  # 🔥 新增：最後救援時間
            }
        
        check_interval = 3
        rescue_interval = 30  # 🔥 每30秒檢查一次是否需要救援
        
        while True:
            all_complete = True
            elapsed = int(time.time() - start_wait)
            current_time = datetime.now()
            
            print("\033[2J\033[H")
            print(f"🔄 零失敗 Repo Sync 監控 - {elapsed//60:02d}:{elapsed%60:02d}")
            print("="*80)
            
            completed_count = 0
            failed_count = 0
            
            for db_info in active_syncs:
                if db_info.status == DBStatus.FAILED:
                    failed_count += 1
                    continue
                
                db_name = db_info.db_info
                tracker = progress_tracker[db_name]
                
                display_name = f"{db_name} v{db_info.version}" if db_info.version else db_name
                
                if db_info.sync_process:
                    poll = db_info.sync_process.poll()
                    
                    if poll is None:  # 仍在運行
                        all_complete = False
                        
                        # 🔥 定期檢查是否需要救援
                        should_rescue = (
                            (current_time - tracker.get('last_rescue_time', tracker['start_time'])).total_seconds() > rescue_interval and
                            tracker['rescue_attempts'] < 5  # 最多5次救援嘗試
                        )
                        
                        if should_rescue:
                            tracker['log_file'] = self._get_sync_log_file(db_info)
                            error_detected = self._check_for_sync_errors(db_info, tracker)
                            
                            if error_detected or self._is_sync_stuck(db_info, tracker):
                                tracker['rescue_attempts'] += 1
                                tracker['last_rescue_time'] = current_time
                                
                                self.logger.warning(f"{db_name}: 🚨 第 {tracker['rescue_attempts']} 次救援 - {error_detected or '進度停滯'}")
                                
                                if self._immediate_rescue(db_info, error_detected or '進度停滯'):
                                    tracker['current_activity'] = f"救援 #{tracker['rescue_attempts']} 成功，重新開始..."
                                    tracker['log_file'] = self._get_sync_log_file(db_info)
                                else:
                                    self.logger.error(f"{db_name}: ❌ 第 {tracker['rescue_attempts']} 次救援失敗")
                                    if tracker['rescue_attempts'] >= 5:
                                        db_info.status = DBStatus.FAILED
                                        db_info.error_message = f"經過 {tracker['rescue_attempts']} 次救援仍然失敗"
                                        failed_count += 1
                                        continue
                        
                        # 更新進度
                        self._update_progress_info(db_info, tracker)
                        
                        runtime = datetime.now() - tracker['start_time']
                        runtime_str = f"{int(runtime.total_seconds()//60)}:{int(runtime.total_seconds()%60):02d}"
                        
                        progress = tracker['estimated_progress']
                        bar_length = 20
                        filled = int(bar_length * progress / 100)
                        bar = "█" * filled + "░" * (bar_length - filled)
                        
                        activity = tracker.get('current_activity', '同步中')
                        
                        # 顯示救援狀態
                        status_info = ""
                        if tracker['rescue_attempts'] > 0:
                            status_info += f" R{tracker['rescue_attempts']}"
                        
                        print(f"🔄 {display_name:20s} │{bar}│ {progress:3d}% │ {runtime_str} │ {activity}{status_info}")
                        
                    elif poll == 0:  # 成功完成
                        # 🔥 零容忍：即使返回碼是0，也要檢查是否真的100%成功
                        success_rate, failed_projects = self._analyze_sync_result(db_info)
                        
                        if failed_projects:
                            self.logger.warning(f"{db_name}: 🚨 即使返回碼0，仍有失敗項目，啟動救援")
                            
                            if self._enhanced_repair_failed_projects_zero_tolerance(db_info, failed_projects):
                                completed_count += 1
                                db_info.status = DBStatus.SUCCESS
                                db_info.end_time = datetime.now()
                                
                                runtime = datetime.now() - tracker['start_time']
                                runtime_str = f"{int(runtime.total_seconds()//60)}:{int(runtime.total_seconds()%60):02d}"
                                bar = "█" * 20
                                print(f"✅ {display_name:20s} │{bar}│ 100% │ {runtime_str} │ 救援成功達到100%")
                            else:
                                # 救援失敗，標記為失敗
                                failed_count += 1
                                db_info.status = DBStatus.FAILED
                                db_info.error_message = f"完成後檢測到失敗項目且救援失敗: {len(failed_projects)} 個"
                                
                                runtime = datetime.now() - tracker['start_time']
                                runtime_str = f"{int(runtime.total_seconds()//60)}:{int(runtime.total_seconds()%60):02d}"
                                print(f"❌ {display_name:20s} │{'':20s}│   0% │ {runtime_str} │ 救援失敗")
                                continue
                        else:
                            # 真正的100%成功
                            completed_count += 1
                            db_info.status = DBStatus.SUCCESS
                            db_info.end_time = datetime.now()
                            
                            runtime = datetime.now() - tracker['start_time']
                            runtime_str = f"{int(runtime.total_seconds()//60)}:{int(runtime.total_seconds()%60):02d}"
                            bar = "█" * 20
                            print(f"✅ {display_name:20s} │{bar}│ 100% │ {runtime_str} │ 完美完成")
                    
                    elif poll == 1:  # 🔥 返回碼1 - 立即啟動救援
                        success_rate, failed_projects = self._analyze_sync_result(db_info)
                        
                        self.logger.warning(f"{db_name}: 🚨 返回碼1，成功率 {success_rate:.1f}%，{len(failed_projects)} 個失敗項目")
                        
                        if self._enhanced_repair_failed_projects_zero_tolerance(db_info, failed_projects):
                            completed_count += 1
                            db_info.status = DBStatus.SUCCESS
                            db_info.end_time = datetime.now()
                            
                            runtime = datetime.now() - tracker['start_time']
                            runtime_str = f"{int(runtime.total_seconds()//60)}:{int(runtime.total_seconds()%60):02d}"
                            bar = "█" * 20
                            print(f"✅ {display_name:20s} │{bar}│ 100% │ {runtime_str} │ 零容忍救援成功")
                        else:
                            failed_count += 1
                            db_info.status = DBStatus.FAILED
                            db_info.error_message = f"零容忍救援失敗，無法達到100%"
                            
                            runtime = datetime.now() - tracker['start_time']
                            runtime_str = f"{int(runtime.total_seconds()//60)}:{int(runtime.total_seconds()%60):02d}"
                            print(f"❌ {display_name:20s} │{'':20s}│   0% │ {runtime_str} │ 零容忍救援失敗")
                    
                    else:  # 其他錯誤碼
                        self.logger.error(f"{db_name}: 🚨 嚴重錯誤 (返回碼: {poll})，啟動核武級救援")
                        
                        if self._nuclear_rebuild(db_info):
                            # 核武級救援成功，重新開始監控
                            all_complete = False
                            tracker['rescue_attempts'] += 1
                            tracker['current_activity'] = "核武級救援重新開始..."
                            tracker['log_file'] = self._get_sync_log_file(db_info)
                            
                            runtime = datetime.now() - tracker['start_time']
                            runtime_str = f"{int(runtime.total_seconds()//60)}:{int(runtime.total_seconds()%60):02d}"
                            print(f"☢️ {display_name:20s} │{'░'*20}│   0% │ {runtime_str} │ 核武級救援中...")
                        else:
                            failed_count += 1
                            db_info.status = DBStatus.FAILED
                            db_info.error_message = f"核武級救援也失敗 (原返回碼: {poll})"
                            
                            runtime = datetime.now() - tracker['start_time']
                            runtime_str = f"{int(runtime.total_seconds()//60)}:{int(runtime.total_seconds()%60):02d}"
                            print(f"💀 {display_name:20s} │{'':20s}│   0% │ {runtime_str} │ 無法救援")
            
            # 統計信息
            running_count = len(active_syncs) - completed_count - failed_count
            
            print("-" * 80)
            print(f"📊 運行:{running_count} │ 完成:{completed_count} │ 失敗:{failed_count}")
            
            if all_complete or elapsed > max_wait_time:
                break
            
            time.sleep(check_interval)
        
        # 最終統計
        self._display_final_summary_zero_fail(active_syncs, elapsed, progress_tracker)

    def _check_for_sync_errors(self, db_info: DBInfo, tracker: dict) -> str:
        """簡化的錯誤檢測 - 專門針對 fatal 錯誤"""
        try:
            log_file = tracker.get('log_file', '')
            
            if not log_file or not os.path.exists(log_file):
                return ""
            
            # 讀取最後 4KB 的內容
            current_size = os.path.getsize(log_file)
            try:
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    read_size = min(current_size, 4096)
                    f.seek(max(0, current_size - read_size))
                    recent_content = f.read()
                    
                    # 🔥 檢測嚴重錯誤，自動啟用零失敗模式
                    critical_errors = [
                        'fatal: not a git repository',
                        'error: Unable to fully sync the tree',
                        'GitCommandError'
                    ]
                    
                    for keyword in critical_errors:
                        if keyword in recent_content:
                            self.logger.error(f"{db_info.db_info}: 🚨 檢測到關鍵錯誤: {keyword}")
                            
                            # 🔥 自動啟用零失敗模式
                            if not self.zero_fail_mode:
                                self.logger.warning(f"🎯 因嚴重錯誤自動啟用零失敗模式")
                                self._enable_zero_fail_mode_dynamically()
                            
                            return f"CRITICAL:Git 錯誤 - {keyword}"
                            
            except Exception as e:
                self.logger.debug(f"檢查錯誤時讀取日誌失敗: {e}")
            
            return ""
            
        except Exception as e:
            self.logger.debug(f"錯誤檢查異常: {e}")
            return ""

    def _is_sync_stuck(self, db_info: DBInfo, tracker: dict) -> bool:
        """檢查同步是否卡住（進度長時間沒變化）"""
        try:
            current_progress = tracker.get('estimated_progress', 0)
            last_check_time = tracker.get('last_progress_check_time')
            last_progress = tracker.get('last_progress_value', 0)
            
            current_time = datetime.now()
            
            if last_check_time:
                time_diff = (current_time - last_check_time).total_seconds()
                progress_diff = current_progress - last_progress
                
                # 如果5分鐘內進度變化少於1%，認為卡住了
                if time_diff > 300 and progress_diff < 1:
                    return True
            
            # 更新檢查點
            tracker['last_progress_check_time'] = current_time
            tracker['last_progress_value'] = current_progress
            
            return False
            
        except Exception:
            return False

    def _immediate_rescue(self, db_info: DBInfo, error_msg: str) -> bool:
        """立即救援（不等待進程結束）"""
        try:
            self.logger.warning(f"{db_info.db_info}: 🚨 立即救援: {error_msg}")
            
            # 強制終止當前進程
            if db_info.sync_process:
                try:
                    if db_info.sync_process.poll() is None:
                        db_info.sync_process.kill()
                        time.sleep(3)
                except:
                    pass
                finally:
                    resource_manager.unregister_process(db_info.db_info)
            
            # 快速重啟
            process = self.repo_manager.start_repo_sync_async(
                db_info.local_path, 
                db_info.db_info
            )
            
            if process:
                db_info.sync_process = process
                self.logger.info(f"{db_info.db_info}: ✅ 立即救援重啟成功 (PID: {process.pid})")
                return True
            else:
                self.logger.error(f"{db_info.db_info}: ❌ 立即救援重啟失敗")
                return False
                
        except Exception as e:
            self.logger.error(f"{db_info.db_info}: 💥 立即救援異常: {e}")
            return False

    def _display_final_summary_zero_fail(self, active_syncs: list, elapsed: int, progress_tracker: dict):
        """顯示零失敗最終摘要"""
        completed = sum(1 for db in active_syncs if db.status == DBStatus.SUCCESS)
        failed = sum(1 for db in active_syncs if db.status == DBStatus.FAILED)
        total_rescues = sum(progress_tracker.get(db.db_info, {}).get('rescue_attempts', 0) for db in active_syncs)
        
        print(f"\n🏁 零失敗 Repo Sync 最終報告")
        print("=" * 60)
        print(f"⏱️  總用時: {elapsed//60:02d}:{elapsed%60:02d}")
        print(f"✅ 成功: {completed}")
        print(f"❌ 失敗: {failed}")
        print(f"🚨 總救援次數: {total_rescues}")
        
        if failed > 0:
            print(f"\n💀 零容忍救援也無法挽救的DB:")
            for db in active_syncs:
                if db.status == DBStatus.FAILED:
                    rescues = progress_tracker.get(db.db_info, {}).get('rescue_attempts', 0)
                    print(f"  - {db.db_info}: {db.error_message} (救援嘗試: {rescues})")
        
        success_rate = (completed / (completed + failed) * 100) if (completed + failed) > 0 else 0
        print(f"🎯 零失敗達成率: {success_rate:.1f}%")
        
        if success_rate == 100.0:
            print("🎉 恭喜！達到零失敗目標！")
        else:
            print("😞 未能達到零失敗目標，需要檢查失敗原因")
        
        print("=" * 60)

    def _final_zero_fail_verification(self):
        """零失敗最終驗證"""
        self.logger.info("🔍 執行零失敗最終驗證...")
        
        failed_dbs = [db for db in self.report.db_details if db.status == DBStatus.FAILED]
        
        if failed_dbs:
            self.logger.error(f"💀 零失敗驗證失敗！仍有 {len(failed_dbs)} 個 DB 失敗:")
            for db in failed_dbs:
                self.logger.error(f"  - {db.db_info}: {db.error_message}")
        
        # 重新統計
        final_failed = sum(1 for db in self.report.db_details if db.status == DBStatus.FAILED)
        final_success = sum(1 for db in self.report.db_details if db.status == DBStatus.SUCCESS)
        
        if final_failed == 0:
            self.logger.info("🎉 零失敗驗證通過！所有 DB 都成功了！")
        else:
            self.logger.error(f"💀 零失敗目標未達成，最終仍有 {final_failed} 個失敗")

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
                                    # 尋找包含項目路徑的部分
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
                
                # 🔥 更新追踪信息
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
        """產生改進版報告 - 修正統計邏輯"""
        self.report.finalize()
        
        if not output_file:
            output_file = os.path.join(
                self.output_dir, 
                config_manager.path_config['report_filename']
            )
        
        try:
            self.logger.info("開始產生 Excel 報告")
            
            report_data = []
            for i, db in enumerate(self.report.db_details, 1):
                # 手動構建字典，確保所有欄位正確
                db_dict = {
                    'sn': i,
                    'module': db.module,
                    'db_type': db.db_type,
                    'db_info': db.db_info,
                    'status': db.status.value if hasattr(db.status, 'value') else str(db.status),
                    'version': db.version or '未指定',
                    'start_time': db.start_time.strftime('%Y-%m-%d %H:%M:%S') if db.start_time else '',
                    'end_time': db.end_time.strftime('%Y-%m-%d %H:%M:%S') if db.end_time else '',
                    'error_message': db.error_message or '',
                    'sync_log_path': db.sync_log_path or '',
                    'sftp_path': db.sftp_path,
                    'local_path': db.local_path or '',
                    'has_existing_repo': '是' if db.has_existing_repo else '否',
                    'jira_link': db.jira_link or '未找到',
                }
                
                # 重新命名欄位
                db_dict['完整_JIRA_連結'] = db.jira_link or '未找到'
                db_dict['完整_repo_init_指令'] = db.actual_source_cmd or '未記錄'
                db_dict['manifest_版本'] = db.version or '未指定'
                
                report_data.append(db_dict)
            
            df = pd.DataFrame(report_data)
            
            # 重新排列欄位順序
            important_columns = [
                'sn', 'module', 'db_type', 'db_info', 'status',
                'manifest_版本', '完整_JIRA_連結', '完整_repo_init_指令',
                'start_time', 'end_time', 'sync_log_path', 'error_message'
            ]
            
            existing_columns = [col for col in important_columns if col in df.columns]
            other_columns = [col for col in df.columns if col not in important_columns]
            df = df[existing_columns + other_columns]
            
            # 🔥 修正：重新計算統計，基於實際的 status 值
            status_counts = df['status'].value_counts()
            successful_count = status_counts.get('✅ 完成', 0)
            failed_count = status_counts.get('❌ 失敗', 0)
            skipped_count = status_counts.get('⭐️ 跳過', 0)
            
            self.logger.info(f"報告統計: 成功 {successful_count}, 失敗 {failed_count}, 跳過 {skipped_count}")
            
            # 建立摘要
            summary = {
                '項目': ['總 DB 數', '成功', '失敗', '跳過', '執行時間'],
                '數值': [
                    len(self.report.db_details),
                    successful_count,
                    failed_count,
                    skipped_count,
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
            import traceback
            traceback.print_exc()

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
            from openpyxl.styles import Font, PatternFill, Alignment
            from openpyxl.utils import get_column_letter
            
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