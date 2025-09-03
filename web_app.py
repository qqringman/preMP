"""
SFTP 下載與比較系統 - Flask Web 應用程式 (完整更新版)
"""
import os
import shutil
import sys
import json
import threading
import time
import asyncio
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, send_file, session, url_for, redirect
from flask_socketio import SocketIO, emit, join_room, leave_room
from werkzeug.utils import secure_filename
import pandas as pd
import config
from sftp_downloader import SFTPDownloader
from file_comparator import FileComparator
from zip_packager import ZipPackager
import utils
from flask import make_response
import utils
import openpyxl
from copy import copy
import io
from excel_handler import ExcelHandler
from metadata_manager import metadata_manager
from functools import wraps

# 初始化 Flask 應用
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'  # 請更改為安全的密鑰
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB 最大檔案大小

# 設定 session 密鑰
app.secret_key = getattr(config, 'SECRET_KEY', 'your-secret-key-change-this-in-production')

# 設定 session 過期時間
app.permanent_session_lifetime = getattr(config, 'SESSION_TIMEOUT', 3600)

# 在檔案開頭的 import 區段加入
from admin_routes import admin_bp

# 在建立 app 之後，註冊 blueprint
app.register_blueprint(admin_bp)

# 初始化 SocketIO
socketio = SocketIO(app, cors_allowed_origins="*")

# 初始化 Excel 處理器（在 app 初始化後）
excel_handler = ExcelHandler()

# 儲存上傳檔案的元資料
uploaded_excel_metadata = {}

# 確保必要的目錄存在
for folder in ['uploads', 'downloads', 'compare_results', 'zip_output', 'logs']:
    if not os.path.exists(folder):
        os.makedirs(folder)

# 全域變數存儲處理進度和歷史記錄
processing_status = {}
recent_activities = []
recent_comparisons = []
task_results = {}  # 儲存任務結果以供樞紐分析

class WebProcessor:
    """Web 處理器類別"""
    
    def __init__(self, task_id):
        self.task_id = task_id
        self.downloader = None
        self.comparator = FileComparator()
        self.packager = ZipPackager()
        self.progress = 0
        self.status = 'idle'
        self.message = ''
        self.results = {}
        self.logger = utils.setup_logger(f'WebProcessor_{task_id}')  # 添加 logger

    def update_progress(self, progress, status, message, stats=None, files=None):
        """更新處理進度"""
        self.progress = progress
        self.status = status
        self.message = message
        
        update_data = {
            'progress': progress,
            'status': status,
            'message': message,
            'results': self.results
        }
        
        if stats:
            update_data['stats'] = stats
            
        if files:
            update_data['files'] = files
            
        processing_status[self.task_id] = update_data
        
        # 透過 SocketIO 發送即時更新
        socketio.emit('progress_update', {
            'task_id': self.task_id,
            **update_data
        }, room=self.task_id)
        
    def process_one_step(self, excel_file, sftp_config):
        """執行一步到位處理 - 修正檔案資料保存"""
        try:
            # 步驟 1：下載
            self.update_progress(10, 'downloading', '正在連接 SFTP 伺服器...')
            
            # 使用新的 Web 下載器
            from sftp_web_downloader import SFTPWebDownloader
            
            self.downloader = SFTPWebDownloader(
                sftp_config.get('host', config.SFTP_HOST),
                sftp_config.get('port', config.SFTP_PORT),
                sftp_config.get('username', config.SFTP_USERNAME),
                sftp_config.get('password', config.SFTP_PASSWORD)
            )
            
            # 設定進度回調
            def progress_callback(progress, status, message, stats=None, files=None):
                if stats:
                    self.update_progress(
                        int(progress * 0.4),  # 下載佔總進度的 40%
                        status, 
                        message, 
                        stats=stats,
                        files=files
                    )
                else:
                    self.update_progress(int(progress * 0.4), status, message)
            
            self.downloader.set_progress_callback(progress_callback)
            
            self.update_progress(20, 'downloading', '開始下載檔案...')
            
            # 建立下載目錄
            download_dir = os.path.join('downloads', self.task_id)
            
            # 執行下載
            report_path = self.downloader.download_from_excel_with_progress(
                excel_file, download_dir
            )
            
            # 取得統計資料和檔案列表
            download_data = self.downloader.get_download_stats()
            stats = download_data['stats']
            files = download_data['files']
            
            # 儲存下載結果
            self.results['download_report'] = report_path
            self.results['stats'] = stats
            self.results['files'] = files
            self.results['download_results'] = {
                'stats': stats,
                'files': files,
                'report_path': report_path
            }
            
            self.update_progress(40, 'downloaded', '下載完成！', stats, files)
            
            # 處理 Excel 檔案複製改名
            global excel_handler
            if excel_file in uploaded_excel_metadata:
                excel_metadata = uploaded_excel_metadata[excel_file]
                excel_result = excel_handler.process_download_complete(
                    self.task_id,
                    download_dir,
                    excel_metadata
                )
                if excel_result['excel_copied']:
                    self.results['excel_copied'] = True
                    self.results['excel_new_name'] = excel_result['excel_new_name']
            else:
                # 🔥 新增：如果沒有元資料，直接複製原始 Excel 檔案到下載目錄
                try:
                    import shutil
                    if os.path.exists(excel_file):
                        original_filename = os.path.basename(excel_file)
                        target_path = os.path.join(download_dir, original_filename)
                        shutil.copy2(excel_file, target_path)
                        self.logger.info(f"已複製原始 Excel 檔案到下載目錄: {target_path}")
                    else:
                        self.logger.warning(f"找不到原始 Excel 檔案: {excel_file}")
                except Exception as e:
                    self.logger.error(f"複製 Excel 檔案失敗: {str(e)}")
            
            # 步驟 2：比較
            self.update_progress(50, 'comparing', '正在執行所有比對...')
            compare_dir = os.path.join('compare_results', self.task_id)
            
            if not os.path.exists(compare_dir):
                os.makedirs(compare_dir)
                
            all_results = self.comparator.compare_all_scenarios(download_dir, compare_dir)
            
            self.results['compare_results'] = all_results
            self.update_progress(80, 'compared', '比對完成！')
            
            # 步驟 3：打包
            self.update_progress(90, 'packaging', '正在打包結果...')
            timestamp = utils.get_timestamp()
            zip_name = f"all_results_{timestamp}.zip"
            zip_path = os.path.join('zip_output', self.task_id, zip_name)
            
            # 建立臨時目錄來整合所有內容
            import tempfile
            import shutil
            
            with tempfile.TemporaryDirectory() as temp_dir:
                # 複製下載的檔案
                if os.path.exists(download_dir):
                    dest_downloads = os.path.join(temp_dir, 'downloads')
                    shutil.copytree(download_dir, dest_downloads)
                
                # 複製比對結果
                if os.path.exists(compare_dir):
                    dest_compare = os.path.join(temp_dir, 'compare_results')
                    shutil.copytree(compare_dir, dest_compare)
                
                # 確保 ZIP 輸出目錄存在
                zip_output_dir = os.path.dirname(zip_path)
                if not os.path.exists(zip_output_dir):
                    os.makedirs(zip_output_dir)
                
                # 打包
                zip_path = self.packager.create_zip(temp_dir, zip_path)
            
            self.results['zip_file'] = zip_path
            
            # 確保最終更新包含完整的檔案資料
            final_update_data = {
                'progress': 100,
                'status': 'completed',
                'message': '所有處理完成！',
                'results': self.results,
                'stats': stats,
                'files': files
            }
            
            processing_status[self.task_id] = final_update_data
            
            # 透過 SocketIO 發送最終更新
            socketio.emit('progress_update', {
                'task_id': self.task_id,
                **final_update_data
            }, room=self.task_id)
            
            # 記錄到最近活動
            add_activity('完成一步到位處理', 'success', 
                        f'下載 {stats["downloaded"]} 個檔案，完成 3 個比對情境，任務 {self.task_id}')
            
            # 同時記錄到最近比對記錄
            add_comparison(self.task_id, '完成一步到位處理', 'completed', stats["downloaded"])
            
            # 儲存結果供樞紐分析使用
            save_task_results(self.task_id, self.results)
            
        except Exception as e:
            self.logger.error(f"One-step processing error: {str(e)}")
            self.update_progress(0, 'error', f'處理失敗：{str(e)}')
            
            # 記錄失敗到最近活動
            add_activity('一步到位處理失敗', 'error', f'{str(e)}，任務 {self.task_id}')
            
            # 同時記錄失敗到最近比對記錄
            add_comparison(self.task_id, '一步到位處理失敗', 'error', 0)
            raise
            
    def process_download(self, excel_file, sftp_config, options):
        """執行下載處理 - 包含 Excel 檔案複製改名功能"""
        try:
            self.update_progress(10, 'downloading', '正在連接 SFTP 伺服器...')
            
            # 使用新的 Web 下載器
            from sftp_web_downloader import SFTPWebDownloader
            
            self.downloader = SFTPWebDownloader(
                sftp_config.get('host', config.SFTP_HOST),
                sftp_config.get('port', config.SFTP_PORT),
                sftp_config.get('username', config.SFTP_USERNAME),
                sftp_config.get('password', config.SFTP_PASSWORD)
            )
            
            # 設定進度回調
            def progress_callback(progress, status, message, stats=None, files=None):
                if stats:
                    self.update_progress(
                        int(progress),
                        status, 
                        message, 
                        stats=stats,
                        files=files
                    )
                else:
                    self.update_progress(int(progress), status, message)
            
            self.downloader.set_progress_callback(progress_callback)
            
            self.update_progress(20, 'downloading', '開始下載檔案...')
            
            # 建立下載目錄
            download_dir = os.path.join('downloads', self.task_id)
            
            try:
                # 執行下載
                report_path = self.downloader.download_from_excel_with_progress(
                    excel_file, download_dir
                )
                
                # 取得統計資料和檔案列表
                download_data = self.downloader.get_download_stats()
                stats = download_data['stats']
                files = download_data['files']
                
                # ===== 處理 Excel 檔案複製改名 =====
                self.logger.info("=" * 60)
                self.logger.info("開始處理 Excel 檔案改名")
                self.logger.info(f"  Task ID: {self.task_id}")
                self.logger.info(f"  下載資料夾: {download_dir}")
                self.logger.info(f"  Excel 檔案路徑: {excel_file}")
                
                # 重新檢查 Excel 檔案的欄位（這會包含 filepath）
                global excel_handler
                excel_check_result = excel_handler.check_excel_columns(excel_file)
                
                # 確保 filepath 存在（向後相容）
                if 'filepath' not in excel_check_result or not excel_check_result['filepath']:
                    excel_check_result['filepath'] = excel_file
                    self.logger.info(f"  補充 filepath: {excel_file}")
                
                # 處理 Excel 檔案複製改名
                excel_result = excel_handler.process_download_complete(
                    self.task_id,
                    download_dir,
                    excel_check_result
                )
                
                # 生成資料夾結構
                folder_structure = self._generate_folder_structure(download_dir, report_path)
                
                # 儲存結果
                self.results['download_report'] = report_path
                self.results['stats'] = stats
                self.results['files'] = files
                self.results['folder_structure'] = folder_structure
                
                # 如果有 Excel 複製結果，加入到結果中
                if excel_result['excel_copied']:
                    self.results['excel_copied'] = True
                    self.results['excel_new_name'] = excel_result['excel_new_name']
                    # 更新訊息
                    self.update_progress(95, 'downloading', 
                        f'Excel 檔案已另存為: {excel_result["excel_new_name"]}')
                    self.logger.info(f"Excel 檔案複製成功: {excel_result['excel_new_name']}")
                else:
                    self.logger.info(f"{excel_result['message']}")
                
                self.logger.info("=" * 60)
                
                # 確保最終統計正確
                self.update_progress(100, 'completed', '下載完成！', stats, files)
                
                # 記錄到最近活動
                add_activity('完成檔案下載', 'success', 
                            f'成功下載 {stats["downloaded"]} 個檔案，任務 {self.task_id}')
                
                # 同時記錄到最近比對記錄
                add_comparison(self.task_id, '完成檔案下載', 'completed', stats["downloaded"])
                
            except Exception as e:
                error_msg = str(e)
                current_stats = self.downloader.get_download_stats()
                self.update_progress(0, 'error', f'下載失敗：{error_msg}', 
                                stats=current_stats['stats'])
                
                # 記錄失敗到最近活動
                add_activity('檔案下載失敗', 'error', f'{error_msg}，任務 {self.task_id}')
                
                # 同時記錄失敗到最近比對記錄
                add_comparison(self.task_id, '檔案下載失敗', 'error', 0)
                raise
                
        except Exception as e:
            error_msg = str(e)
            self.update_progress(0, 'error', f'處理失敗：{error_msg}')
            
            # 記錄失敗到最近活動
            add_activity('檔案下載失敗', 'error', f'{error_msg}，任務 {self.task_id}')
            
            # 同時記錄失敗到最近比對記錄
            add_comparison(self.task_id, '檔案下載失敗', 'error', 0)
            raise

    def _handle_excel_copy_rename(self, excel_file, download_dir):
        """
        處理 Excel 檔案的複製和改名
        
        Args:
            excel_file: Excel 檔案路徑
            download_dir: 下載目錄
            
        Returns:
            處理結果字典
        """
        result = {
            'excel_copied': False,
            'excel_new_name': None
        }
        
        try:
            # 從全域變數獲取 Excel 元資料
            global uploaded_excel_metadata, excel_handler
            
            if excel_file in uploaded_excel_metadata:
                excel_metadata = uploaded_excel_metadata[excel_file]
                
                self.logger.info("=" * 60)
                self.logger.info(f"開始處理 Excel 檔案改名")
                self.logger.info(f"  Task ID: {self.task_id}")
                self.logger.info(f"  下載資料夾: {download_dir}")
                
                # 使用 ExcelHandler 處理
                process_result = excel_handler.process_download_complete(
                    self.task_id,
                    download_dir,
                    excel_metadata
                )
                
                result.update(process_result)
                
                if result['excel_copied']:
                    self.logger.info(f"✅ Excel 檔案已成功複製並改名: {result['excel_new_name']}")
                    
                    # 加入活動記錄
                    add_activity('Excel 檔案處理', 'success', 
                            f"檔案已另存為: {result['excel_new_name']}")
                else:
                    self.logger.info(f"ℹ️ {process_result.get('message', '不需要處理 Excel 檔案')}")
                    
            else:
                self.logger.info(f"沒有找到 Excel 元資料: {excel_file}")
                
        except Exception as e:
            self.logger.error(f"處理 Excel 檔案時發生錯誤: {str(e)}")
            # 不要因為 Excel 處理失敗而中斷整個下載流程
            
        return result
        
    def _generate_simple_folder_structure(self, download_dir):
        """生成簡單的資料夾結構"""
        structure = {}
        
        try:
            for item in os.listdir(download_dir):
                item_path = os.path.join(download_dir, item)
                if os.path.isdir(item_path):
                    # 遞迴處理子目錄
                    structure[item] = {}
                    for subitem in os.listdir(item_path):
                        structure[item][subitem] = subitem
                else:
                    # 檔案
                    if not item.endswith('.xlsx'):  # 排除報告檔案
                        structure[item] = item
        except Exception as e:
            print(f"Error generating folder structure: {e}")
            
        return structure
        
    def _generate_folder_structure(self, download_dir, report_path):
        """生成資料夾結構"""
        folder_structure = {}
        
        try:
            # 確保目錄存在
            if not os.path.exists(download_dir):
                return folder_structure
                
            # 遞迴建立資料夾結構
            def build_tree(path, tree_dict):
                try:
                    items = os.listdir(path)
                    for item in sorted(items):
                        item_path = os.path.join(path, item)
                        
                        # 跳過報告檔案
                        if report_path and item_path == report_path:
                            continue
                            
                        if os.path.isdir(item_path):
                            # 資料夾
                            tree_dict[item] = {}
                            build_tree(item_path, tree_dict[item])
                        else:
                            # 檔案
                            tree_dict[item] = os.path.relpath(item_path, os.getcwd())
                except Exception as e:
                    self.logger.error(f"Error building tree for {path}: {e}")
                    
            build_tree(download_dir, folder_structure)
                        
        except Exception as e:
            self.logger.error(f"Error generating folder structure: {e}")
            print(f"Error generating folder structure: {e}")
            
        return folder_structure
        
    def _get_download_stats(self, report_path, download_dir):
        """從下載報告或目錄中獲取統計資料"""
        stats = {
            'total': 0,
            'downloaded': 0,
            'skipped': 0,
            'failed': 0
        }
        
        # 嘗試從報告檔案讀取統計
        if report_path and os.path.exists(report_path):
            try:
                import pandas as pd
                df = pd.read_excel(report_path)
                stats['total'] = len(df)
                
                # 檢查可能的狀態欄位名稱
                status_columns = ['status', 'Status', '狀態', 'download_status', 'result']
                status_column = None
                
                for col in status_columns:
                    if col in df.columns:
                        status_column = col
                        break
                
                if status_column:
                    # 統計各種狀態
                    for status in df[status_column].unique():
                        status_lower = str(status).lower()
                        if 'download' in status_lower or 'success' in status_lower or '成功' in status:
                            stats['downloaded'] += len(df[df[status_column] == status])
                        elif 'skip' in status_lower or '跳過' in status:
                            stats['skipped'] += len(df[df[status_column] == status])
                        elif 'fail' in status_lower or 'error' in status_lower or '失敗' in status:
                            stats['failed'] += len(df[df[status_column] == status])
                else:
                    # 如果沒有狀態欄位，計算下載目錄中的檔案數
                    file_count = 0
                    for root, dirs, files in os.walk(download_dir):
                        # 排除報告檔案
                        files = [f for f in files if not f.endswith('_report.xlsx')]
                        file_count += len(files)
                    stats['downloaded'] = file_count
                    
            except Exception as e:
                print(f"Error reading report: {e}")
                # 如果無法讀取報告，使用預設值
                stats['downloaded'] = stats['total']
        
        return stats
                    
    def process_comparison(self, source_dir, scenarios):
        """執行比對處理"""
        
        # 在方法開始就 import 所需的模組
        import pandas as pd
        from file_comparator import FileComparator
        
        try:
            self.update_progress(10, 'comparing', '正在準備比對...')
            
            compare_dir = os.path.join('compare_results', self.task_id)
            
            if not os.path.exists(compare_dir):
                os.makedirs(compare_dir, exist_ok=True)
            
            if scenarios == 'all':
                self.update_progress(30, 'comparing', '正在執行所有比對情境...')
                all_results = self.comparator.compare_all_scenarios(source_dir, compare_dir)
                
                # 直接使用 FileComparator 返回的結果
                self.results['compare_results'] = all_results
                
                # 如果有總摘要報告，保存路徑
                if 'summary_report' in all_results:
                    self.results['summary_report'] = all_results['summary_report']
            
            else:
                # 單一情境比對
                self.update_progress(30, 'comparing', f'正在執行 {scenarios} 比對情境...')
                
                # 🔥 關鍵修正：模仿 compare_all_scenarios 的邏輯
                try:
                    # 載入 mapping tables 並保存到 comparator
                    self.logger.info(f"🔍 準備載入 mapping tables，source_dir: {source_dir}")
                    self.comparator.mapping_tables = self.comparator._load_mapping_tables(source_dir)
                    self.logger.info(f"📊 載入結果: {len(self.comparator.mapping_tables) if self.comparator.mapping_tables else 0} 個 mapping tables")
                    
                    # 🔥 關鍵：如果有 mapping table，使用 _compare_with_mapping 的邏輯
                    if self.comparator.mapping_tables:
                        self.logger.info("✅ 找到 mapping tables，使用 mapping 邏輯")
                        
                        # 使用 compare_with_mapping，然後篩選特定情境的結果
                        all_results = self.comparator._compare_with_mapping(source_dir, compare_dir)
                        
                        # 從完整結果中提取單一情境
                        scenario_map = {
                            'master_vs_premp': 'master_vs_premp',
                            'premp_vs_wave': 'premp_vs_wave',
                            'wave_vs_backup': 'wave_vs_backup'
                        }
                        
                        if scenarios in scenario_map:
                            scenario_key = scenario_map[scenarios]
                            
                            # 提取單一情境結果
                            if scenario_key in all_results:
                                single_scenario_result = {scenario_key: all_results[scenario_key]}
                                self.results['compare_results'] = single_scenario_result
                                
                                # 尋找對應的報表檔案
                                scenario_report_path = os.path.join(compare_dir, scenario_key, 'all_scenarios_compare.xlsx')
                                if os.path.exists(scenario_report_path):
                                    self.results['summary_report'] = scenario_report_path
                                elif 'summary_report' in all_results:
                                    self.results['summary_report'] = all_results['summary_report']
                                    
                                self.logger.info(f"✅ 成功使用 mapping 邏輯處理 {scenario_key}")
                            else:
                                raise Exception(f"在結果中找不到情境: {scenario_key}")
                        else:
                            raise Exception(f"不支援的情境: {scenarios}")
                            
                    else:
                        # 沒有 mapping table，使用原有邏輯
                        self.logger.warning("⚠️ 沒有載入 mapping table，使用原有邏輯（可能會失敗）")
                        success = self._process_single_scenario_without_mapping(source_dir, compare_dir, scenarios)
                        if not success:
                            raise Exception("沒有 mapping table 的情況下處理失敗")
                        
                except Exception as e:
                    self.logger.error(f"❌ 單一情境比對失敗: {str(e)}")
                    # 設定失敗的結果結構
                    scenario_key = {'master_vs_premp': 'master_vs_premp', 'premp_vs_wave': 'premp_vs_wave', 'wave_vs_backup': 'wave_vs_backup'}.get(scenarios, scenarios)
                    self.results['compare_results'] = {
                        scenario_key: {
                            'success': 0,
                            'failed': 0,
                            'modules': [],
                            'failed_modules': []
                        }
                    }
                    raise
            
            self.update_progress(100, 'completed', '比對完成！')
            
            # 記錄比對，計算正確的總模組數
            total_modules = 0
            total_failed = 0
            
            # 確保 compare_results 存在
            if 'compare_results' in self.results:
                for scenario_data in self.results['compare_results'].values():
                    if isinstance(scenario_data, dict):
                        total_modules += scenario_data.get('success', 0)
                        total_failed += scenario_data.get('failed', 0)
            
            add_comparison(self.task_id, scenarios, 'completed', total_modules)
            
            # 儲存結果
            save_task_results(self.task_id, self.results)
            
        except Exception as e:
            self.logger.error(f"Comparison error: {str(e)}")
            self.update_progress(0, 'error', f'比對失敗：{str(e)}')
            
            # 確保即使出錯也有基本的結構，避免後續 KeyError
            if 'compare_results' not in self.results:
                self.results['compare_results'] = {}
                
            raise

    def _process_single_scenario_without_mapping(self, source_dir, compare_dir, scenarios):
        """沒有 mapping table 時的後備處理方式"""
        # 這裡可以實作原有的邏輯，但通常在有 mapping table 的情況下不會用到
        self.logger.warning("使用後備邏輯處理單一情境（通常會失敗）")
        return False

    def _get_scenario_display_name(self, scenario):
        """取得情境的顯示名稱"""
        name_map = {
            'master_vs_premp': 'Master vs PreMP',
            'premp_vs_wave': 'PreMP vs Wave',
            'wave_vs_backup': 'Wave vs Backup'
        }
        return name_map.get(scenario, scenario)

# 輔助函數
def add_activity(action, status, details=None):
    """添加活動記錄"""
    activity = {
        'timestamp': datetime.now(),
        'action': action,
        'status': status,
        'details': details
    }
    recent_activities.insert(0, activity)
    # 只保留最近 20 筆
    if len(recent_activities) > 20:
        recent_activities.pop()

def add_comparison(task_id, scenario, status, modules):
    """添加比對記錄"""
    comparison = {
        'id': task_id,  # 使用傳入的 task_id
        'task_id': task_id,  # 明確保存 task_id
        'timestamp': datetime.now(),
        'scenario': scenario,
        'status': status,
        'modules': modules,
        'duration': '< 1 分鐘'
    }
    recent_comparisons.insert(0, comparison)
    # 只保留最近 10 筆
    if len(recent_comparisons) > 10:
        recent_comparisons.pop()

def save_task_results(task_id, results):
    """儲存任務結果供樞紐分析使用"""
    # 確保儲存完整的結果
    task_results[task_id] = {
        'results': results,
        'summary_report': results.get('summary_report', ''),
        'compare_results': results.get('compare_results', {}),
        'timestamp': datetime.now()
    }
    
    # 同時更新 processing_status 以確保資料持久性
    if task_id in processing_status:
        processing_status[task_id]['results'] = results

def global_login_required(f):
    """全域登入檢查裝飾器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 如果沒有啟用登入功能，直接通過
        if not getattr(config, 'ENABLE_LOGIN', False):
            return f(*args, **kwargs)
        
        # 如果是全域登入模式
        if getattr(config, 'LOGIN_MODE', 'admin_only') == 'global':
            # 檢查登入狀態
            if 'logged_in' not in session or not session['logged_in']:
                if request.is_json:
                    return jsonify({'error': '請先登入', 'redirect': '/login'}), 401
                return redirect(url_for('admin.login_page', redirect=request.url))
        
        return f(*args, **kwargs)
    return decorated_function

# 路由定義
@app.route('/')
@global_login_required
def index():
    """首頁"""
    return render_template('index.html')

@app.route('/compare')
@global_login_required
def compare_page():
    """比較頁面"""
    return render_template('compare.html')

@app.route('/one-step')
@global_login_required
def one_step_page():
    """一步到位頁面"""
    return render_template('one_step.html')

@app.route('/results/<task_id>')
@global_login_required
def results_page(task_id):
    """結果頁面"""
    return render_template('results.html', task_id=task_id)

# API 端點
@app.route('/api/upload', methods=['POST'])
def upload_file():
    """上傳檔案 API - 支援 Excel 和 CSV，並檢查欄位"""
    if 'file' not in request.files:
        return jsonify({'error': '沒有檔案'}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '沒有選擇檔案'}), 400
    
    # 支援的檔案格式
    allowed_extensions = {'.xlsx', '.xls', '.csv'}
    file_ext = os.path.splitext(file.filename)[1].lower()
    
    if file and file_ext in allowed_extensions:
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        # 確保上傳目錄存在
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        
        file.save(filepath)
        
        # 檢查 Excel 欄位
        excel_metadata = {
            'original_name': file.filename,
            'filepath': filepath,
            'has_sftp_columns': False,
            'root_folder': None
        }
        
        # 如果是 Excel 或 CSV 檔案，檢查欄位
        if file_ext in ['.xlsx', '.xls', '.csv']:
            try:
                check_result = excel_handler.check_excel_columns(filepath)
                excel_metadata.update(check_result)
                app.logger.info(f"Excel 欄位檢查結果: {check_result}")
            except Exception as e:
                app.logger.warning(f"檢查 Excel 欄位時發生錯誤: {str(e)}")
        
        # 使用元資料管理器儲存
        metadata_manager.store_metadata(filepath, excel_metadata)
        
        app.logger.info(f'檔案上傳: {filename} (類型: {file_ext})')
        
        return jsonify({
            'filename': filename, 
            'filepath': filepath,
            'file_type': file_ext[1:],
            'excel_metadata': excel_metadata
        })
    
    return jsonify({
        'error': f'只支援 Excel (.xlsx, .xls) 和 CSV (.csv) 檔案，您上傳的是 {file_ext} 檔案'
    }), 400

@app.route('/api/test-connection', methods=['POST'])
def test_connection():
    """測試 SFTP 連線"""
    data = request.json
    try:
        downloader = SFTPDownloader(
            data.get('host', config.SFTP_HOST),
            data.get('port', config.SFTP_PORT),
            data.get('username', config.SFTP_USERNAME),
            data.get('password', config.SFTP_PASSWORD)
        )
        if downloader.test_connection():
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'message': '連線失敗'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/one-step', methods=['POST'])
def process_one_step():
    """一步到位處理 API"""
    data = request.json
    excel_file = data.get('excel_file')
    sftp_config = data.get('sftp_config', {})
    
    if not excel_file:
        return jsonify({'error': '缺少 Excel 檔案'}), 400
        
    # 生成任務 ID
    task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{os.urandom(4).hex()}"
    
    # 在背景執行處理
    processor = WebProcessor(task_id)
    thread = threading.Thread(
        target=processor.process_one_step,
        args=(excel_file, sftp_config)
    )
    thread.start()
    
    return jsonify({'task_id': task_id})

@app.route('/api/download', methods=['POST'])
def process_download():
    """下載處理 API - 包含 Excel 元資料處理"""
    try:
        data = request.json
        
        # 驗證必要參數
        excel_file = data.get('excel_file')
        if not excel_file:
            return jsonify({'error': '缺少 Excel 檔案'}), 400
            
        sftp_config = data.get('sftp_config', {})
        options = data.get('options', {})
        
        # 獲取 Excel 元資料（從前端傳來或從全域變數取得）
        excel_metadata = data.get('excel_metadata')
        if not excel_metadata and excel_file in uploaded_excel_metadata:
            excel_metadata = uploaded_excel_metadata[excel_file]
        
        # 生成任務 ID
        task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{os.urandom(4).hex()}"
        
        # 如果有元資料，儲存到全域變數中
        if excel_metadata:
            uploaded_excel_metadata[excel_file] = excel_metadata
        
        # 在背景執行處理
        processor = WebProcessor(task_id)
        thread = threading.Thread(
            target=processor.process_download,
            args=(excel_file, sftp_config, options)
        )
        thread.start()
        
        return jsonify({'task_id': task_id})
        
    except Exception as e:
        print(f"Download API error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/compare', methods=['POST'])
def process_compare():
    """比較處理 API"""
    data = request.json
    source_dir = data.get('source_dir')
    scenarios = data.get('scenarios', 'all')
    
    if not source_dir:
        return jsonify({'error': '缺少來源目錄'}), 400
        
    # 生成任務 ID
    task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{os.urandom(4).hex()}"
    
    # 在背景執行處理
    processor = WebProcessor(task_id)
    thread = threading.Thread(
        target=processor.process_comparison,
        args=(source_dir, scenarios)
    )
    thread.start()
    
    return jsonify({'task_id': task_id})

@app.route('/api/status/<task_id>')
def get_status(task_id):
    """取得任務狀態 API - 增強版，支援從文件系統恢復任務狀態"""
    
    # 1. 首先檢查記憶體中的狀態
    if task_id in processing_status:
        return jsonify(processing_status[task_id])
    
    # 2. 如果記憶體中沒有，嘗試從文件系統恢復任務狀態
    try:
        task_status = recover_task_status_from_filesystem(task_id)
        if task_status:
            # 將恢復的狀態存回記憶體中，供後續使用
            processing_status[task_id] = task_status
            return jsonify(task_status)
    except Exception as e:
        app.logger.error(f'Error recovering task status for {task_id}: {str(e)}')
    
    # 3. 如果都找不到，返回 not_found 狀態
    return jsonify({
        'progress': 0,
        'status': 'not_found',
        'message': '找不到任務',
        'task_id': task_id
    })

def recover_task_status_from_filesystem(task_id):
    """從文件系統恢復任務狀態 - 增強一步到位支援"""
    if not task_id.startswith('task_'):
        return None
    
    # 檢查下載目錄
    download_dir = os.path.join('downloads', task_id)
    compare_dir = os.path.join('compare_results', task_id)
    
    task_info = {
        'task_id': task_id,
        'progress': 100,
        'status': 'completed',
        'message': '任務已完成（從文件系統恢復）',
        'results': {}
    }
    
    # 檢查是否有下載結果
    if os.path.exists(download_dir):
        app.logger.info(f'Found download directory for task {task_id}')
        
        # 統計下載的文件
        download_stats = analyze_download_directory(download_dir)
        
        # 保存到多個位置確保相容性
        task_info['results']['stats'] = download_stats['stats']
        task_info['results']['files'] = download_stats['files']
        task_info['results']['download_results'] = {
            'stats': download_stats['stats'],
            'files': download_stats['files']
        }
        
        # 同時在頂層保存統計資料（供下載頁面使用）
        task_info['stats'] = download_stats['stats']
        task_info['files'] = download_stats['files']
        
        # 查找下載報告
        report_files = [f for f in os.listdir(download_dir) if f.endswith('_report.xlsx')]
        if report_files:
            task_info['results']['download_report'] = os.path.join(download_dir, report_files[0])
        
        # 生成文件夾結構
        task_info['results']['folder_structure'] = generate_folder_structure_from_directory(download_dir)
        
        # 如果只有下載，沒有比較，就返回下載完成狀態
        if not os.path.exists(compare_dir):
            task_info['message'] = f'下載完成，共 {download_stats["stats"]["downloaded"]} 個文件'
            return task_info
    
    # 檢查是否有比較結果
    if os.path.exists(compare_dir):
        app.logger.info(f'Found compare directory for task {task_id}')
        
        # 分析比較結果
        compare_stats = analyze_compare_directory(compare_dir)
        task_info['results']['compare_results'] = compare_stats
        
        # 查找總摘要報告
        summary_files = [f for f in os.listdir(compare_dir) 
                        if f in ['all_scenarios_summary.xlsx', 'all_scenarios_compare.xlsx']]
        if summary_files:
            task_info['results']['summary_report'] = os.path.join(compare_dir, summary_files[0])
        
        # 如果有下載和比對結果，這是一步到位任務
        if os.path.exists(download_dir):
            total_files = task_info.get('stats', {}).get('downloaded', 0)
            total_scenarios = len([d for d in os.listdir(compare_dir) 
                                 if os.path.isdir(os.path.join(compare_dir, d))])
            task_info['message'] = f'一步到位處理完成：下載 {total_files} 個檔案，處理 {total_scenarios} 個比較情境'
        else:
            # 只有比較結果
            total_scenarios = len([d for d in os.listdir(compare_dir) 
                                 if os.path.isdir(os.path.join(compare_dir, d))])
            task_info['message'] = f'比較完成，處理了 {total_scenarios} 個比較情境'
    
    # 如果沒有找到任何相關目錄，返回 None
    if not os.path.exists(download_dir) and not os.path.exists(compare_dir):
        return None
    
    return task_info

def generate_folder_structure_from_directory(directory):
    """從目錄生成文件夾結構"""
    structure = {}
    
    try:
        for root, dirs, files in os.walk(directory):
            # 獲取相對路徑
            rel_path = os.path.relpath(root, directory)
            if rel_path == '.':
                current_level = structure
            else:
                # 構建嵌套結構
                path_parts = rel_path.split(os.sep)
                current_level = structure
                for part in path_parts:
                    if part not in current_level:
                        current_level[part] = {}
                    current_level = current_level[part]
            
            # 添加文件
            for file in files:
                if not file.endswith('_report.xlsx'):  # 跳過報告文件
                    file_path = os.path.join(root, file)
                    current_level[file] = os.path.relpath(file_path, os.getcwd())
    
    except Exception as e:
        app.logger.error(f'Error generating folder structure: {str(e)}')
    
    return structure

@app.route('/api/check-task-exists/<task_id>')
def check_task_exists(task_id):
    """檢查任務是否存在於文件系統中"""
    try:
        download_dir = os.path.join('downloads', task_id)
        compare_dir = os.path.join('compare_results', task_id)
        
        exists_info = {
            'task_id': task_id,
            'exists': False,
            'has_download': False,
            'has_compare': False,
            'paths': []
        }
        
        if os.path.exists(download_dir):
            exists_info['has_download'] = True
            exists_info['exists'] = True
            exists_info['paths'].append(f'downloads/{task_id}')
        
        if os.path.exists(compare_dir):
            exists_info['has_compare'] = True
            exists_info['exists'] = True  
            exists_info['paths'].append(f'compare_results/{task_id}')
        
        return jsonify(exists_info)
        
    except Exception as e:
        return jsonify({
            'task_id': task_id,
            'exists': False,
            'error': str(e)
        })

def analyze_compare_directory(compare_dir):
    """分析比較結果目錄"""
    compare_results = {}
    
    try:
        # 檢查各個比較情境目錄
        scenarios = ['master_vs_premp', 'premp_vs_wave', 'wave_vs_backup']
        
        for scenario in scenarios:
            scenario_dir = os.path.join(compare_dir, scenario)
            if os.path.exists(scenario_dir):
                # 統計該情境下的模組數量
                module_count = count_modules_in_scenario(scenario_dir)
                compare_results[scenario] = {
                    'success': module_count,
                    'failed': 0,  # 從文件系統恢復時很難確定失敗數量
                    'modules': [],  # 可以進一步實現詳細模組列表
                    'failed_modules': []
                }
    
    except Exception as e:
        app.logger.error(f'Error analyzing compare directory {compare_dir}: {str(e)}')
    
    return compare_results

def count_modules_in_scenario(scenario_dir):
    """計算情境目錄下的模組數量"""
    try:
        # 計算有比較報告的模組數量
        module_count = 0
        for root, dirs, files in os.walk(scenario_dir):
            # 計算xlsx文件數量作為模組數量的參考
            xlsx_files = [f for f in files if f.endswith('.xlsx') and not f.startswith('all_')]
            module_count += len(xlsx_files)
        return module_count
    except Exception:
        return 0

def analyze_download_directory(download_dir):
    """分析下載目錄，統計文件信息"""
    stats = {'total': 0, 'downloaded': 0, 'skipped': 0, 'failed': 0}
    files = {'downloaded': [], 'skipped': [], 'failed': []}
    
    try:
        # 遍歷下載目錄
        for root, dirs, file_list in os.walk(download_dir):
            for file in file_list:
                # 跳過報告文件
                if file.endswith('_report.xlsx'):
                    continue
                
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, download_dir)
                
                # 構建文件信息
                file_info = {
                    'name': file,
                    'path': file_path,
                    'ftp_path': rel_path,  # 使用相對路徑作為FTP路徑
                    'size': os.path.getsize(file_path) if os.path.exists(file_path) else 0
                }
                
                files['downloaded'].append(file_info)
                stats['downloaded'] += 1
        
        stats['total'] = stats['downloaded']
        
        # 嘗試從報告文件中獲取更準確的統計
        report_files = [f for f in os.listdir(download_dir) if f.endswith('_report.xlsx')]
        if report_files:
            try:
                report_path = os.path.join(download_dir, report_files[0])
                import pandas as pd
                df = pd.read_excel(report_path)
                
                # 從報告中獲取更準確的統計
                if 'status' in df.columns:
                    status_counts = df['status'].value_counts()
                    stats['downloaded'] = status_counts.get('downloaded', 0)
                    stats['skipped'] = status_counts.get('skipped', 0)
                    stats['failed'] = status_counts.get('failed', 0)
                    stats['total'] = len(df)
                    
            except Exception as e:
                app.logger.warning(f'Could not read download report: {str(e)}')
        
    except Exception as e:
        app.logger.error(f'Error analyzing download directory {download_dir}: {str(e)}')
    
    return {'stats': stats, 'files': files}

@app.route('/api/list-directories')
def list_directories():
    """列出可用的目錄 API"""
    directories = []
    
    # 只檢查 downloads 目錄下的 task_ 開頭的資料夾
    download_base_dir = config.DEFAULT_OUTPUT_DIR  # 使用 config 中的預設目錄
    item_path = download_base_dir
    if os.path.isdir(item_path):
        directories.append({
            'path': item_path,
            'name': f'{os.path.basename(download_base_dir)}',  # 顯示相對路徑
            'type': 'download'
        })
    if os.path.exists(download_base_dir):
        for item in os.listdir(download_base_dir):
            # 只列出 task_ 開頭的資料夾
            if item.startswith('task_'):
                item_path = os.path.join(download_base_dir, item)
                if os.path.isdir(item_path):
                    directories.append({
                        'path': item_path,
                        'name': f'{os.path.basename(download_base_dir)}/{item}',  # 顯示相對路徑
                        'type': 'download'
                    })
    
    # 按時間排序（最新的在前）
    directories.sort(key=lambda x: os.path.getmtime(x['path']), reverse=True)
    
    return jsonify(directories)

@app.route('/api/recent-activities')
def get_recent_activities():
    """取得最近活動 - 包含從檔案系統推斷的活動"""
    try:
        activities = []
        
        # 1. 從記憶體中的活動記錄
        for activity in recent_activities[:10]:
            activities.append({
                'timestamp': activity['timestamp'].isoformat(),
                'action': activity['action'],
                'status': activity['status'],
                'details': activity['details']
            })
        
        # 2. 如果記憶體中沒有足夠的活動，從檔案系統推斷
        if len(activities) < 5:
            inferred_activities = infer_activities_from_filesystem()
            activities.extend(inferred_activities)
        
        # 3. 按時間排序並只取前10筆
        activities = sorted(activities, key=lambda x: x['timestamp'], reverse=True)[:10]
        
        # 4. 如果還是沒有資料，返回空列表（前端會顯示友好訊息）
        return jsonify(activities)
        
    except Exception as e:
        app.logger.error(f'Get recent activities error: {e}')
        return jsonify([])

def infer_activities_from_filesystem():
    """從檔案系統推斷歷史活動"""
    activities = []
    
    try:
        # 從下載目錄推斷活動
        downloads_dir = 'downloads'
        if os.path.exists(downloads_dir):
            for item in os.listdir(downloads_dir):
                if item.startswith('task_') and os.path.isdir(os.path.join(downloads_dir, item)):
                    item_path = os.path.join(downloads_dir, item)
                    mtime = os.path.getmtime(item_path)
                    timestamp = datetime.fromtimestamp(mtime)
                    
                    # 統計該任務的檔案數量
                    file_count = 0
                    for root, dirs, files in os.walk(item_path):
                        file_count += len([f for f in files if not f.endswith('_report.xlsx')])
                    
                    activities.append({
                        'timestamp': timestamp.isoformat(),
                        'action': '完成檔案下載',
                        'status': 'success',
                        'details': f'{file_count} 個檔案，任務 {item}'
                    })
        
        # 從比對結果目錄推斷活動
        compare_dir = 'compare_results'
        if os.path.exists(compare_dir):
            for item in os.listdir(compare_dir):
                if item.startswith('task_') and os.path.isdir(os.path.join(compare_dir, item)):
                    item_path = os.path.join(compare_dir, item)
                    mtime = os.path.getmtime(item_path)
                    timestamp = datetime.fromtimestamp(mtime)
                    
                    # 檢查比對情境
                    scenarios = []
                    for scenario in ['master_vs_premp', 'premp_vs_wave', 'wave_vs_backup']:
                        scenario_path = os.path.join(item_path, scenario)
                        if os.path.exists(scenario_path):
                            scenarios.append(scenario)
                    
                    scenario_text = f"{len(scenarios)} 個比對情境" if scenarios else "比對處理"
                    
                    activities.append({
                        'timestamp': timestamp.isoformat(),
                        'action': '完成比對分析',
                        'status': 'success',
                        'details': f'{scenario_text}，任務 {item}'
                    })
    
    except Exception as e:
        app.logger.warning(f'Error inferring activities: {e}')
    
    return activities

@app.route('/download')
@global_login_required
def download_page():
    """下載頁面 - 支援 task_id 參數"""
    # 獲取 task_id 參數
    task_id = request.args.get('task_id')
    
    # 如果有 task_id，傳遞給模板
    return render_template('download.html', task_id=task_id)
    
@app.route('/api/recent-comparisons')
def get_recent_comparisons():
    """取得最近比對記錄"""
    return jsonify([{
        'id': comp.get('task_id', comp.get('id', '')),  # 優先使用 task_id
        'task_id': comp.get('task_id', comp.get('id', '')),  # 確保有 task_id
        'timestamp': comp['timestamp'].isoformat(),
        'scenario': comp['scenario'],
        'status': comp['status'],
        'modules': comp['modules'],
        'duration': comp.get('duration', '< 1 分鐘')
    } for comp in recent_comparisons[:10]])

@app.route('/api/statistics')
def get_statistics():
    """取得真實統計資料"""
    try:
        # 計算總處理數
        total_processed = calculate_total_processed()
        
        # 計算今日處理數
        today_processed = calculate_today_processed()
        
        # 計算成功率
        success_rate = calculate_success_rate()
        
        return jsonify({
            'total': total_processed,
            'today': today_processed,
            'successRate': success_rate
        })
        
    except Exception as e:
        app.logger.error(f'Calculate statistics error: {e}')
        # 如果計算失敗，返回 0 而不是假資料
        return jsonify({
            'total': 0,
            'today': 0,
            'successRate': 0
        })

def calculate_success_rate():
    """計算成功率"""
    if not processing_status and not recent_activities and not recent_comparisons:
        return 0
    
    total_tasks = 0
    successful_tasks = 0
    
    # 從處理狀態計算
    for task_id, status in processing_status.items():
        if task_id.startswith('task_'):
            total_tasks += 1
            if status.get('status') == 'completed':
                successful_tasks += 1
    
    # 從比對記錄計算
    for comparison in recent_comparisons:
        total_tasks += 1
        if comparison.get('status') == 'completed':
            successful_tasks += 1
    
    # 從活動記錄計算（只計算明確標示成功/失敗的活動）
    for activity in recent_activities:
        if activity.get('status') in ['success', 'error']:
            total_tasks += 1
            if activity.get('status') == 'success':
                successful_tasks += 1
    
    # 避免除以零
    if total_tasks == 0:
        return 0
    
    # 計算百分比並四捨五入
    success_rate = (successful_tasks / total_tasks) * 100
    return round(success_rate, 1)

@app.route('/api/detailed-statistics')
def get_detailed_statistics():
    """取得詳細統計資料"""
    try:
        # 基本統計
        total = calculate_total_processed()
        today = calculate_today_processed()
        success_rate = calculate_success_rate()
        
        # 額外統計
        download_tasks = count_download_tasks()
        compare_tasks = count_compare_tasks()
        failed_tasks = count_failed_tasks()
        
        # 本週統計
        week_processed = calculate_week_processed()
        
        # 平均處理時間（如果有記錄的話）
        avg_processing_time = calculate_average_processing_time()
        
        return jsonify({
            'basic': {
                'total': total,
                'today': today,
                'successRate': success_rate
            },
            'breakdown': {
                'downloadTasks': download_tasks,
                'compareTasks': compare_tasks,
                'failedTasks': failed_tasks
            },
            'temporal': {
                'weekProcessed': week_processed,
                'avgProcessingTime': avg_processing_time
            }
        })
        
    except Exception as e:
        app.logger.error(f'Detailed statistics error: {e}')
        return jsonify({'error': str(e)}), 500

def calculate_average_processing_time():
    """計算平均處理時間（分鐘）"""
    # 這個需要你在處理過程中記錄開始和結束時間
    # 目前先返回估計值
    try:
        # 可以從 processing_status 或其他地方獲取實際處理時間
        # 這裡提供一個簡單的估算
        total_tasks = len(processing_status)
        if total_tasks > 0:
            # 假設平均每個任務 5 分鐘（你可以根據實際情況調整）
            return 5.0
        return 0.0
    except Exception:
        return 0.0

def calculate_week_processed():
    """計算本週處理數"""
    from datetime import datetime, timedelta
    
    # 獲取本週的開始日期（週一）
    today = datetime.now()
    week_start = today - timedelta(days=today.weekday())
    week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
    
    week_count = 0
    
    # 從活動記錄計算
    for activity in recent_activities:
        try:
            if activity['timestamp'] >= week_start:
                week_count += 1
        except Exception:
            continue
    
    # 從比對記錄計算
    for comparison in recent_comparisons:
        try:
            if comparison['timestamp'] >= week_start:
                week_count += 1
        except Exception:
            continue
            
    return week_count

def count_failed_tasks():
    """統計失敗任務數量"""
    failed_count = 0
    
    # 從處理狀態統計
    for status in processing_status.values():
        if status.get('status') == 'error':
            failed_count += 1
    
    # 從活動記錄統計
    for activity in recent_activities:
        if activity.get('status') == 'error':
            failed_count += 1
            
    return failed_count

def count_compare_tasks():
    """統計比對任務數量"""
    count = 0
    compare_dir = 'compare_results'
    if os.path.exists(compare_dir):
        try:
            count = len([d for d in os.listdir(compare_dir) 
                        if d.startswith('task_') and os.path.isdir(os.path.join(compare_dir, d))])
        except Exception:
            pass
    return count

def count_download_tasks():
    """統計下載任務數量"""
    count = 0
    downloads_dir = 'downloads'
    if os.path.exists(downloads_dir):
        try:
            count = len([d for d in os.listdir(downloads_dir) 
                        if d.startswith('task_') and os.path.isdir(os.path.join(downloads_dir, d))])
        except Exception:
            pass
    return count

def calculate_today_processed():
    """計算今日處理數"""
    from datetime import datetime, timedelta
    
    today = datetime.now().date()
    today_count = 0
    
    # 從活動記錄計算今日處理數
    for activity in recent_activities:
        try:
            # activity['timestamp'] 是 datetime 物件
            activity_date = activity['timestamp'].date()
            if activity_date == today:
                today_count += 1
        except Exception as e:
            app.logger.warning(f'Error parsing activity timestamp: {e}')
            continue
    
    # 從比對記錄計算今日處理數
    for comparison in recent_comparisons:
        try:
            # comparison['timestamp'] 是 datetime 物件
            comparison_date = comparison['timestamp'].date()
            if comparison_date == today:
                today_count += 1
        except Exception as e:
            app.logger.warning(f'Error parsing comparison timestamp: {e}')
            continue
    
    # 從任務目錄的修改時間計算
    try:
        for dir_name in ['downloads', 'compare_results']:
            if os.path.exists(dir_name):
                for item in os.listdir(dir_name):
                    if item.startswith('task_'):
                        item_path = os.path.join(dir_name, item)
                        if os.path.isdir(item_path):
                            # 獲取目錄的修改時間
                            mtime = os.path.getmtime(item_path)
                            mdate = datetime.fromtimestamp(mtime).date()
                            if mdate == today:
                                today_count += 1
    except Exception as e:
        app.logger.warning(f'Error counting today tasks from directories: {e}')
    
    return today_count

def calculate_total_processed():
    """計算總處理數"""
    total = 0
    
    # 方法1：從活動記錄計算
    total += len(recent_activities)
    
    # 方法2：從比對記錄計算
    total += len(recent_comparisons)
    
    # 方法3：從檔案系統計算（統計已完成的任務目錄）
    try:
        # 統計 downloads 目錄下的任務資料夾
        downloads_dir = 'downloads'
        if os.path.exists(downloads_dir):
            download_tasks = [d for d in os.listdir(downloads_dir) 
                            if d.startswith('task_') and os.path.isdir(os.path.join(downloads_dir, d))]
            total += len(download_tasks)
        
        # 統計 compare_results 目錄下的任務資料夾
        compare_dir = 'compare_results'
        if os.path.exists(compare_dir):
            compare_tasks = [d for d in os.listdir(compare_dir) 
                           if d.startswith('task_') and os.path.isdir(os.path.join(compare_dir, d))]
            total += len(compare_tasks)
            
    except Exception as e:
        app.logger.warning(f'Error counting task directories: {e}')
    
    # 去重複（因為同一個任務可能同時有下載和比對）
    unique_tasks = set()
    
    # 從處理狀態獲取唯一任務
    for task_id in processing_status.keys():
        if task_id.startswith('task_'):
            unique_tasks.add(task_id)
    
    # 從目錄獲取唯一任務
    try:
        for dir_name in ['downloads', 'compare_results']:
            if os.path.exists(dir_name):
                for item in os.listdir(dir_name):
                    if item.startswith('task_') and os.path.isdir(os.path.join(dir_name, item)):
                        unique_tasks.add(item)
    except Exception:
        pass
    
    return len(unique_tasks) if unique_tasks else max(total, 0)

@app.route('/api/pivot-data/<task_id>')
def get_pivot_data(task_id):
    """取得樞紐分析資料 API - 支援按情境查找"""
    try:
        app.logger.info(f'Getting pivot data for task: {task_id}')
        
        # 檢查是否有情境參數
        scenario = request.args.get('scenario', 'all')
        app.logger.info(f'Requested scenario: {scenario}')
        
        # 查找任務結果
        summary_report_path = None
        
        # 1. 根據您提供的實際路徑結構進行精確映射
        if scenario == 'all':
            # 全部情境使用 all_scenarios_summary.xlsx
            summary_report_path = os.path.join('compare_results', task_id, 'all_scenarios_summary.xlsx')
            if not os.path.exists(summary_report_path):
                # 備選路徑
                alt_paths = [
                    os.path.join('compare_results', task_id, 'all_scenarios_compare.xlsx'),
                    os.path.join('compare_results', task_id, 'all_compare.xlsx')
                ]
                for path in alt_paths:
                    if os.path.exists(path):
                        summary_report_path = path
                        break
        else:
            # 根據實際的資料夾結構，不需要映射！
            # 前端的 scenario 名稱就是實際的資料夾名稱
            folder_name = scenario  # 直接使用 scenario 作為資料夾名稱
            
            # 構建精確路徑
            summary_report_path = os.path.join('compare_results', task_id, folder_name, 'all_scenarios_compare.xlsx')
            app.logger.info(f'Checking path: {summary_report_path}')
            
            if not os.path.exists(summary_report_path):
                app.logger.warning(f'File not found at primary path: {summary_report_path}')
                
                # 嘗試其他可能的檔名
                alt_names = ['all_compare.xlsx', f'{folder_name}_compare.xlsx']
                for alt_name in alt_names:
                    alt_path = os.path.join('compare_results', task_id, folder_name, alt_name)
                    app.logger.info(f'Trying alternative path: {alt_path}')
                    if os.path.exists(alt_path):
                        summary_report_path = alt_path
                        app.logger.info(f'Found alternative file: {alt_path}')
                        break
        
        # 2. 如果還是找不到，提供詳細的錯誤訊息
        if not summary_report_path or not os.path.exists(summary_report_path):
            app.logger.error(f'Could not find report for scenario: {scenario}')
            
            # 列出實際存在的檔案結構供除錯
            compare_dir = os.path.join('compare_results', task_id)
            available_files = []
            
            if os.path.exists(compare_dir):
                app.logger.info(f'Listing directory structure for {compare_dir}:')
                for root, dirs, files in os.walk(compare_dir):
                    for file in files:
                        if file.endswith('.xlsx'):
                            rel_path = os.path.relpath(os.path.join(root, file), compare_dir)
                            available_files.append(rel_path)
                            app.logger.info(f'  Found: {rel_path}')
            
            # 返回更詳細的錯誤訊息
            error_msg = f'找不到資料檔案：{scenario}'
            
            return jsonify({
                'error': error_msg,
                'available_files': available_files
            }), 404
        
        # 3. 讀取並返回資料
        try:
            app.logger.info(f'Reading Excel file: {summary_report_path}')
            
            # 讀取 Excel 檔案的所有工作表
            excel_data = pd.read_excel(summary_report_path, sheet_name=None)
            
            # 列出所有工作表名稱
            app.logger.info(f'Available sheets: {list(excel_data.keys())}')
            
            # 轉換為 JSON 格式
            pivot_data = {}
            for sheet_name, df in excel_data.items():
                app.logger.info(f'Processing sheet: {sheet_name} with {len(df)} rows')
                
                # 處理 NaN 值
                df = df.fillna('')
                
                # 將日期轉換為字串
                for col in df.columns:
                    if df[col].dtype == 'datetime64[ns]':
                        df[col] = df[col].astype(str)
                    elif df[col].dtype == 'object':
                        # 確保所有值都是可序列化的
                        df[col] = df[col].apply(lambda x: str(x) if pd.notna(x) else '')
                
                # 將 DataFrame 轉換為記錄格式
                pivot_data[sheet_name] = {
                    'columns': df.columns.tolist(),
                    'data': df.to_dict('records')
                }
            
            app.logger.info(f'Successfully loaded {len(pivot_data)} sheets')
            return jsonify(pivot_data)
            
        except Exception as e:
            app.logger.error(f'Error reading Excel file: {e}')
            import traceback
            app.logger.error(traceback.format_exc())
            return jsonify({'error': f'讀取資料失敗：{str(e)}'}), 500
        
    except Exception as e:
        app.logger.error(f'Get pivot data error: {e}')
        import traceback
        app.logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

def row_belongs_to_scenario(row, scenario):
    """判斷資料行是否屬於特定情境"""
    base_folder = str(row.get('base_folder', ''))
    compare_folder = str(row.get('compare_folder', ''))
    
    if scenario == 'master_vs_premp':
        # Master 資料夾（無後綴）vs PreMP 資料夾
        return (not any(base_folder.endswith(suffix) for suffix in ['-premp', '-wave', '-wave.backup', '-mp']) and
                (compare_folder.endswith('-premp') or compare_folder.endswith('-pre-mp')))
    
    elif scenario == 'premp_vs_wave':
        # PreMP 資料夾 vs Wave/MP 資料夾
        return ((base_folder.endswith('-premp') or base_folder.endswith('-pre-mp')) and 
                (compare_folder.endswith('-wave') or compare_folder.endswith('-mp')) and 
                not compare_folder.endswith('-wave.backup') and
                not compare_folder.endswith('-mpbackup'))
    
    elif scenario == 'wave_vs_backup':
        # Wave/MP 資料夾 vs Backup 資料夾
        return ((base_folder.endswith('-wave') or base_folder.endswith('-mp')) and 
                not base_folder.endswith('-wave.backup') and
                not base_folder.endswith('-mpbackup') and
                (compare_folder.endswith('-wave.backup') or 
                 compare_folder.endswith('-wavebackup') or
                 compare_folder.endswith('-mpbackup')))
    
    return False

def row_belongs_to_scenario(row, scenario):
    """判斷資料行是否屬於特定情境（獨立函數，不是方法）"""
    # 根據資料夾名稱判斷
    base_folder = str(row.get('base_folder', ''))
    compare_folder = str(row.get('compare_folder', ''))
    
    if scenario == 'master_vs_premp':
        # Master 資料夾（無後綴）vs PreMP 資料夾
        return (not any(base_folder.endswith(suffix) for suffix in ['-premp', '-wave', '-wave.backup']) and
                compare_folder.endswith('-premp'))
    
    elif scenario == 'premp_vs_wave':
        # PreMP 資料夾 vs Wave 資料夾
        return (base_folder.endswith('-premp') and 
                compare_folder.endswith('-wave') and 
                not compare_folder.endswith('-wave.backup'))
    
    elif scenario == 'wave_vs_backup':
        # Wave 資料夾 vs Wave.backup 資料夾
        return (base_folder.endswith('-wave') and 
                not base_folder.endswith('-wave.backup') and
                compare_folder.endswith('-wave.backup'))
    
    return False

def _row_belongs_to_scenario(self, row, scenario):
    """判斷資料行是否屬於特定情境"""
    # 根據資料夾名稱判斷
    base_folder = str(row.get('base_folder', ''))
    compare_folder = str(row.get('compare_folder', ''))
    
    if scenario == 'master_vs_premp':
        # Master 資料夾（無後綴）vs PreMP 資料夾
        return (not any(base_folder.endswith(suffix) for suffix in ['-premp', '-wave', '-wave.backup']) and
                base_folder.endswith('-premp'))
    
    elif scenario == 'premp_vs_wave':
        # PreMP 資料夾 vs Wave 資料夾
        return (base_folder.endswith('-premp') and 
                compare_folder.endswith('-wave') and 
                not compare_folder.endswith('-wave.backup'))
    
    elif scenario == 'wave_vs_backup':
        # Wave 資料夾 vs Wave.backup 資料夾
        return (compare_folder.endswith('-wave') and 
                not compare_folder.endswith('-wave.backup') and
                compare_folder.endswith('-wave.backup'))
    
    return False

def get_mock_pivot_data():
    """取得模擬的樞紐分析資料"""
    return {
        'revision_diff': {
            'columns': ['SN', 'module', 'name', 'path', 'base_short', 'base_revision', 
                       'compare_short', 'compare_revision', 'has_wave'],
            'data': [
                {
                    'SN': 1,
                    'module': 'bootcode',
                    'name': 'realtek/mac7p/bootcode',
                    'path': 'bootcode/src',
                    'base_short': 'abc123d',
                    'base_revision': 'abc123def456...',
                    'compare_short': 'def456g',
                    'compare_revision': 'def456ghi789...',
                    'has_wave': 'N'
                },
                {
                    'SN': 2,
                    'module': 'emcu',
                    'name': 'realtek/emcu',
                    'path': 'emcu/src',
                    'base_short': 'aaa111b',
                    'base_revision': 'aaa111bbb222...',
                    'compare_short': 'ccc333d',
                    'compare_revision': 'ccc333ddd444...',
                    'has_wave': 'Y'
                }
            ]
        },
        'branch_error': {
            'columns': ['SN', 'module', 'name', 'problem', 'has_wave'],
            'data': [
                {
                    'SN': 1,
                    'module': 'bootcode',
                    'name': 'realtek/bootcode',
                    'problem': '沒改成 premp',
                    'has_wave': 'N'
                }
            ]
        }
    }

# 路徑建議 API - 新增
@app.route('/api/path-suggestions')
def get_path_suggestions():
    """獲取路徑建議 API"""
    path = request.args.get('path', '')
    
    if not path:
        return jsonify({'directories': [], 'files': []})
    
    try:
        # 嘗試獲取真實路徑建議
        suggestions = {'directories': [], 'files': []}
        
        # 檢查路徑是否存在
        if os.path.exists(path):
            # 如果路徑存在，列出子目錄和檔案
            try:
                for item in os.listdir(path):
                    item_path = os.path.join(path, item)
                    if os.path.isdir(item_path):
                        suggestions['directories'].append({
                            'name': item,
                            'path': item_path
                        })
                    elif item.endswith('.xlsx'):
                        suggestions['files'].append({
                            'name': item,
                            'path': item_path,
                            'size': os.path.getsize(item_path)
                        })
            except PermissionError:
                pass
        else:
            # 如果路徑不存在，嘗試尋找相似的路徑
            parent_path = os.path.dirname(path)
            if os.path.exists(parent_path):
                base_name = os.path.basename(path).lower()
                try:
                    for item in os.listdir(parent_path):
                        if base_name in item.lower():
                            item_path = os.path.join(parent_path, item)
                            if os.path.isdir(item_path):
                                suggestions['directories'].append({
                                    'name': item,
                                    'path': item_path
                                })
                            elif item.endswith('.xlsx'):
                                suggestions['files'].append({
                                    'name': item,
                                    'path': item_path,
                                    'size': os.path.getsize(item_path)
                                })
                except PermissionError:
                    pass
            
        # 如果沒有找到建議，提供常用路徑
        if not suggestions['directories'] and not suggestions['files']:
            from config import COMMON_PATHS
            for common_path in COMMON_PATHS:
                if path.lower() in common_path.lower():
                    if os.path.exists(common_path):
                        name = common_path.split('/')[-1] or common_path
                        suggestions['directories'].append({
                            'name': name,
                            'path': common_path
                        })
        
        # 限制建議數量
        suggestions['directories'] = suggestions['directories'][:10]
        suggestions['files'] = suggestions['files'][:10]
        
        return jsonify(suggestions)
        
    except Exception as e:
        print(f"Path suggestions error: {e}")
        return jsonify({'directories': [], 'files': []})

# 瀏覽伺服器 API - 更新
@app.route('/api/browse-server')
def browse_server():
    path = request.args.get('path', '/')
    
    try:
        items = os.listdir(path)
        folders = []
        files = []
        
        for item in items:
            item_path = os.path.join(path, item)
            if os.path.isdir(item_path):
                folders.append({
                    'name': item,
                    'path': item_path
                })
            elif os.path.isfile(item_path):
                # 檢查是否為支援的檔案類型
                if item.lower().endswith(('.xlsx', '.xls', '.csv')):
                    files.append({
                        'name': item,
                        'path': item_path,
                        'size': os.path.getsize(item_path)
                    })
        
        return jsonify({
            'folders': folders,
            'files': files
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 非同步下載支援
@app.route('/api/prepare-download/<task_id>', methods=['POST'])
def prepare_download(task_id):
    """準備大檔案下載"""
    data = request.json
    format_type = data.get('format', 'zip')
    
    # 生成下載任務 ID
    download_task_id = f"download_{task_id}_{format_type}"
    
    # 在背景準備檔案
    def prepare_file():
        time.sleep(3)  # 模擬檔案準備時間
        # 實際應用中這裡應該生成真實的檔案
        download_url = f"/api/download-ready/{download_task_id}"
        processing_status[download_task_id] = {
            'ready': True,
            'download_url': download_url
        }
    
    thread = threading.Thread(target=prepare_file)
    thread.start()
    
    return jsonify({
        'task_id': download_task_id,
        'ready': False
    })

@app.route('/api/download-status/<task_id>')
def download_status(task_id):
    """檢查下載準備狀態"""
    status = processing_status.get(task_id, {'ready': False})
    return jsonify(status)

@app.route('/api/download-ready/<task_id>')
def download_ready(task_id):
    """下載準備好的檔案"""
    # 實際應用中這裡應該返回真實的檔案
    # 這裡返回一個模擬的檔案
    return send_file('README.md', as_attachment=True, download_name='result.zip')

@app.route('/api/export-excel/<task_id>')
def export_excel(task_id):
    """匯出 Excel API - 根據當前情境下載對應的檔案"""
    try:
        # 獲取情境參數（從前端傳來）
        scenario = request.args.get('scenario', 'all')
        app.logger.info(f'匯出Excel: task_id={task_id}, scenario={scenario}')
        
        # 根據情境決定要下載的檔案路徑（與 get_pivot_data 邏輯一致）
        summary_report_path = None
        
        if scenario == 'all':
            # 全部情境使用 all_scenarios_summary.xlsx
            summary_report_path = os.path.join('compare_results', task_id, 'all_scenarios_summary.xlsx')
            if not os.path.exists(summary_report_path):
                # 備選路徑
                alt_paths = [
                    os.path.join('compare_results', task_id, 'all_scenarios_compare.xlsx'),
                    os.path.join('compare_results', task_id, 'all_compare.xlsx')
                ]
                for path in alt_paths:
                    if os.path.exists(path):
                        summary_report_path = path
                        break
        else:
            # 特定情境使用對應資料夾下的 all_scenarios_compare.xlsx
            folder_name = scenario  # 直接使用 scenario 作為資料夾名稱
            summary_report_path = os.path.join('compare_results', task_id, folder_name, 'all_scenarios_compare.xlsx')
            
            if not os.path.exists(summary_report_path):
                # 嘗試其他可能的檔名
                alt_names = ['all_compare.xlsx', f'{folder_name}_compare.xlsx']
                for alt_name in alt_names:
                    alt_path = os.path.join('compare_results', task_id, folder_name, alt_name)
                    if os.path.exists(alt_path):
                        summary_report_path = alt_path
                        break
        
        # 檢查檔案是否存在
        if not summary_report_path or not os.path.exists(summary_report_path):
            app.logger.error(f'找不到Excel檔案: scenario={scenario}, path={summary_report_path}')
            return jsonify({'error': f'找不到 {scenario} 情境的報表檔案'}), 404
        
        # 生成檔案名稱（包含情境資訊）
        if scenario == 'all':
            filename = f'完整報表_{task_id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        else:
            scenario_names = {
                'master_vs_premp': 'Master_vs_PreMP',
                'premp_vs_wave': 'PreMP_vs_Wave', 
                'wave_vs_backup': 'Wave_vs_Backup'
            }
            scenario_display = scenario_names.get(scenario, scenario)
            filename = f'{scenario_display}報表_{task_id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        
        app.logger.info(f'匯出檔案: {summary_report_path} -> {filename}')
        
        return send_file(
            summary_report_path, 
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
    except Exception as e:
        app.logger.error(f'Export Excel error: {e}')
        import traceback
        app.logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@app.route('/api/export-zip/<task_id>')
def export_zip(task_id):
    """匯出 ZIP 檔案 API - 包含所有結果"""
    try:
        import tempfile
        import shutil
        import zipfile
        import io
        
        # 使用 BytesIO 而不是臨時檔案
        zip_buffer = io.BytesIO()
        
        # 創建 ZIP
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
            files_added = False
            
            # 添加下載的檔案
            download_dir = os.path.join('downloads', task_id)
            if os.path.exists(download_dir):
                for root, dirs, files in os.walk(download_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arc_name = os.path.join('downloads', os.path.relpath(file_path, download_dir))
                        zipf.write(file_path, arc_name)
                        files_added = True
                app.logger.info(f'Added downloads directory: {download_dir}')
            
            # 添加比對結果
            compare_dir = os.path.join('compare_results', task_id)
            if os.path.exists(compare_dir):
                for root, dirs, files in os.walk(compare_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arc_name = os.path.join('compare_results', os.path.relpath(file_path, compare_dir))
                        zipf.write(file_path, arc_name)
                        files_added = True
                app.logger.info(f'Added compare results directory: {compare_dir}')
            
            # 如果沒有檔案，至少添加一個 README
            if not files_added:
                readme_content = f'任務 ID: {task_id}\n'
                readme_content += f'創建時間: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n'
                readme_content += '暫無比對結果\n'
                zipf.writestr('README.txt', readme_content.encode('utf-8'))
        
        # 重置 buffer 位置
        zip_buffer.seek(0)
        
        # 生成檔案名稱
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        zip_filename = f'results_{task_id}_{timestamp}.zip'
        
        # 返回檔案
        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name=zip_filename
        )
        
    except Exception as e:
        app.logger.error(f'Export ZIP error: {e}')
        import traceback
        app.logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500
    
def create_mock_excel(task_id):
    """創建模擬的 Excel 檔案"""
    import tempfile
    
    # 創建臨時檔案
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx')
    
    # 創建模擬資料
    data = get_mock_pivot_data()
    
    with pd.ExcelWriter(temp_file.name, engine='openpyxl') as writer:
        for sheet_name, sheet_data in data.items():
            df = pd.DataFrame(sheet_data['data'])
            df.to_excel(writer, sheet_name=sheet_name, index=False)
    
    return temp_file.name

@app.route('/api/preview-file')
def preview_file():
    """預覽檔案內容 API"""
    file_path = request.args.get('path')
    
    if not file_path:
        return jsonify({'error': '缺少檔案路徑'}), 400
        
    try:
        # 建構真實的檔案路徑
        full_path = os.path.join(os.getcwd(), file_path)
        
        # 安全性檢查
        allowed_dirs = ['downloads', 'compare_results']
        path_parts = file_path.split('/')
        
        if len(path_parts) > 0 and path_parts[0] not in allowed_dirs:
            return jsonify({'error': '無效的檔案路徑'}), 403
            
        # 檢查檔案是否存在
        if not os.path.exists(full_path):
            return jsonify({'error': '檔案不存在'}), 404
            
        # 讀取檔案內容（限制大小）
        max_size = 1024 * 1024  # 1MB
        file_size = os.path.getsize(full_path)
        
        if file_size > max_size:
            return jsonify({'content': f'檔案太大 ({file_size} bytes)，無法預覽'})
            
        # 判斷檔案類型
        file_ext = os.path.splitext(full_path)[1].lower()
        
        # 讀取檔案
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # 針對XML特別處理
            if file_ext == '.xml':
                import xml.dom.minidom
                try:
                    # 格式化XML
                    dom = xml.dom.minidom.parseString(content)
                    content = dom.toprettyxml(indent="  ")
                    # 移除多餘的空白行
                    content = '\n'.join([line for line in content.split('\n') if line.strip()])
                except:
                    # 如果解析失敗，返回原始內容
                    pass
                    
        except UnicodeDecodeError:
            # 嘗試其他編碼
            try:
                with open(full_path, 'r', encoding='big5') as f:
                    content = f.read()
            except:
                content = '無法解碼檔案內容（可能是二進位檔案）'
                
        return jsonify({
            'content': content,
            'type': file_ext[1:] if file_ext else 'txt'
        })
        
    except Exception as e:
        print(f"Preview file error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/download-file')
def download_single_file():
    """下載單一檔案 API"""
    file_path = request.args.get('path')
    
    if not file_path:
        return jsonify({'error': '缺少檔案路徑'}), 400
        
    try:
        # 建構真實的檔案路徑
        full_path = os.path.join(os.getcwd(), file_path)
        
        # 安全性檢查 - 確保路徑在允許的目錄內
        allowed_dirs = ['downloads', 'compare_results', 'zip_output']
        path_parts = file_path.split('/')
        
        if len(path_parts) > 0 and path_parts[0] not in allowed_dirs:
            return jsonify({'error': '無效的檔案路徑'}), 403
            
        # 檢查檔案是否存在
        if not os.path.exists(full_path):
            return jsonify({'error': '檔案不存在'}), 404
            
        # 返回真實檔案
        return send_file(
            full_path, 
            as_attachment=True,
            download_name=os.path.basename(file_path)
        )
        
    except Exception as e:
        print(f"Download file error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/download-report/<task_id>')
def download_report(task_id):
    """下載報表 API"""
    try:
        # 查找任務的下載報告
        if task_id in processing_status:
            task_data = processing_status[task_id]
            report_path = task_data.get('results', {}).get('download_report')
            
            if report_path and os.path.exists(report_path):
                return send_file(report_path, as_attachment=True, 
                               download_name=f'download_report_{task_id}.xlsx')
        
        # 如果沒有找到，嘗試在下載目錄中查找
        download_dir = os.path.join('downloads', task_id)
        report_path = os.path.join(download_dir, 'download_report.xlsx')
        
        if os.path.exists(report_path):
            return send_file(report_path, as_attachment=True,
                           download_name=f'download_report_{task_id}.xlsx')
        
        return jsonify({'error': '找不到下載報表'}), 404
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# SocketIO 事件處理
@socketio.on('connect')
def handle_connect():
    """處理連線事件"""
    print(f'Client connected: {request.sid}')

@socketio.on('disconnect')
def handle_disconnect():
    """處理斷線事件"""
    print(f'Client disconnected: {request.sid}')

@socketio.on('join_task')
def handle_join_task(data):
    """加入任務房間"""
    task_id = data.get('task_id')
    if task_id:
        join_room(task_id)
        emit('joined', {'task_id': task_id})

# 錯誤處理
@app.errorhandler(404)
def not_found(error):
    """404 錯誤處理"""
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    """500 錯誤處理"""
    return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/list-folders')
async def list_folders():
    path = request.args.get('path', '/home/vince_lin/ai/preMP/downloads')
    
    try:
        folders = []
        
        # 使用 SFTP 或本地檔案系統列出資料夾
        if os.path.exists(path) and os.path.isdir(path):
            for item in os.listdir(path):
                item_path = os.path.join(path, item)
                if os.path.isdir(item_path):
                    folders.append({
                        'name': item,
                        'path': item_path
                    })
        
        # 按名稱排序
        folders.sort(key=lambda x: x['name'])
        
        return jsonify({'folders': folders})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/browse-directory')
async def browse_directory():
    path = request.args.get('path', '/home/vince_lin/ai/preMP')
    
    try:
        folders = []
        
        # 檢查路徑是否存在
        if not os.path.exists(path) or not os.path.isdir(path):
            return jsonify({'error': '路徑不存在或不是目錄'})
        
        # 列出所有子目錄
        for item in sorted(os.listdir(path)):
            item_path = os.path.join(path, item)
            if os.path.isdir(item_path):
                folders.append({
                    'name': item,
                    'path': item_path
                })
        
        return jsonify({
            'path': path,
            'folders': folders
        })
        
    except PermissionError:
        return jsonify({'error': '沒有權限訪問此目錄'})
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/api/list-export-tasks')
def list_export_tasks():
    """列出可匯出的任務 API"""
    try:
        tasks = []
        
        # 從比對結果目錄獲取任務
        if os.path.exists('compare_results'):
            for task_dir in os.listdir('compare_results'):
                task_path = os.path.join('compare_results', task_dir)
                if os.path.isdir(task_path):
                    # 檢查是否有報告檔案
                    has_report = False
                    for file in os.listdir(task_path):
                        if file.endswith('.xlsx'):
                            has_report = True
                            break
                    
                    if has_report:
                        # 獲取修改時間
                        timestamp = os.path.getmtime(task_path)
                        tasks.append({
                            'id': task_dir,
                            'name': f'比對任務 {task_dir}',
                            'timestamp': timestamp * 1000,  # 轉換為毫秒
                            'type': 'compare'
                        })
        
        # 從處理狀態獲取任務
        for task_id, status in processing_status.items():
            if status.get('status') == 'completed':
                tasks.append({
                    'id': task_id,
                    'name': f'處理任務 {task_id}',
                    'timestamp': time.time() * 1000,
                    'type': 'process'
                })
        
        # 按時間排序（最新的在前）
        tasks.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return jsonify({'tasks': tasks})
        
    except Exception as e:
        app.logger.error(f'List export tasks error: {e}')
        return jsonify({'error': str(e)}), 500

@app.route('/api/export-sheet/<task_id>/<sheet_name>')
def export_sheet(task_id, sheet_name):
    """匯出單一資料表 API"""
    try:
        format_type = request.args.get('format', 'excel')
        
        # 獲取資料
        data = get_task_data(task_id)
        if not data or sheet_name not in data:
            return jsonify({'error': '找不到資料表'}), 404
        
        sheet_data = data[sheet_name]
        
        if format_type == 'excel':
            # 創建 Excel 檔案
            import tempfile
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx')
            
            df = pd.DataFrame(sheet_data['data'])
            with pd.ExcelWriter(temp_file.name, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name=sheet_name, index=False)
            
            # 確保檔案關閉
            temp_file.close()
            
            return send_file(
                temp_file.name,
                as_attachment=True,
                download_name=f'{sheet_name}_{task_id}.xlsx',
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
        
        return jsonify({'error': '不支援的格式'}), 400
        
    except Exception as e:
        app.logger.error(f'Export sheet error: {e}')
        return jsonify({'error': str(e)}), 500

@app.route('/api/export-pdf/<task_id>')
def export_pdf(task_id):
    """匯出 PDF 報告 API"""
    try:
        # 這裡可以整合 PDF 生成功能
        # 目前先返回錯誤訊息
        return jsonify({'error': 'PDF 匯出功能開發中'}), 501
        
    except Exception as e:
        app.logger.error(f'Export PDF error: {e}')
        return jsonify({'error': str(e)}), 500

def get_task_data(task_id):
    """獲取任務資料的輔助函數"""
    try:
        # 1. 從處理狀態中查找
        if task_id in processing_status:
            task_data = processing_status[task_id]
            results = task_data.get('results', {})
            
            if 'summary_report' in results:
                summary_report_path = results['summary_report']
                if os.path.exists(summary_report_path):
                    excel_data = pd.read_excel(summary_report_path, sheet_name=None)
                    data = {}
                    for sheet_name, df in excel_data.items():
                        df = df.fillna('')
                        data[sheet_name] = {
                            'columns': df.columns.tolist(),
                            'data': df.to_dict('records')
                        }
                    return data
        
        # 2. 從比對結果目錄中查找
        compare_dir = os.path.join('compare_results', task_id)
        if os.path.exists(compare_dir):
            for file in os.listdir(compare_dir):
                if file == 'all_compare.xlsx' or file.endswith('_summary.xlsx'):
                    file_path = os.path.join(compare_dir, file)
                    excel_data = pd.read_excel(file_path, sheet_name=None)
                    data = {}
                    for sheet_name, df in excel_data.items():
                        df = df.fillna('')
                        data[sheet_name] = {
                            'columns': df.columns.tolist(),
                            'data': df.to_dict('records')
                        }
                    return data
        
        return None
        
    except Exception as e:
        app.logger.error(f'Get task data error: {e}')
        return None


@app.route('/api/export-html/<task_id>')
def export_html(task_id):
    """匯出 HTML 報告 API"""
    try:
        # 獲取任務資料
        data = get_task_data(task_id)
        if not data:
            return jsonify({'error': '找不到任務資料'}), 404
        
        # 生成 HTML 報告
        html_content = generate_html_report(task_id, data)
        
        # 返回 HTML 檔案
        response = make_response(html_content)
        response.headers['Content-Type'] = 'text/html; charset=utf-8'
        response.headers['Content-Disposition'] = f'attachment; filename=report_{task_id}.html'
        
        return response
        
    except Exception as e:
        app.logger.error(f'Export HTML error: {e}')
        return jsonify({'error': str(e)}), 500

def generate_html_report(task_id, data):
    """生成 HTML 報告內容"""
    # 獲取內嵌的 CSS 樣式
    css_content = get_embedded_report_styles()
    
    # 生成資料表格 HTML
    tables_html = ""
    ordered_sheets = ['revision_diff', 'branch_error', 'lost_project', 'version_diff', '無法比對']
    
    for sheet_name in ordered_sheets:
        if sheet_name in data:
            sheet_data = data[sheet_name]
            tables_html += f"""
            <div class="sheet-section">
                <h2 class="sheet-title">
                    <i class="fas fa-table"></i> {sheet_name}
                </h2>
                <div class="table-container">
                    <div class="table-wrapper">
                        {generate_table_html(sheet_data)}
                    </div>
                </div>
            </div>
            """
    
    html = f"""
    <!DOCTYPE html>
    <html lang="zh-TW">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>比對報告 - {task_id}</title>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
        <style>{css_content}</style>
    </head>
    <body>
        <div class="container">
            <div class="page-header">
                <h1 class="page-title">
                    <i class="fas fa-chart-line"></i> 比對結果報告
                </h1>
                <p class="page-subtitle">任務 ID: {task_id}</p>
                <p class="page-subtitle">生成時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            </div>
            
            <div class="report-content">
                {tables_html}
            </div>
        </div>
    </body>
    </html>
    """
    return html

def generate_html_report(task_id, data):
    """生成 HTML 報告內容"""
    html = f"""
    <!DOCTYPE html>
    <html lang="zh-TW">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>比對報告 - {task_id}</title>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
        <style>
            {get_export_styles()}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="page-header">
                <h1 class="page-title">
                    <i class="fas fa-chart-line"></i> 比對結果報告
                </h1>
                <p class="page-subtitle">任務 ID: {task_id}</p>
            </div>
            
            <div class="report-content">
                {generate_data_tables(data)}
            </div>
        </div>
    </body>
    </html>
    """
    return html

def get_export_styles():
    """獲取匯出 HTML 的樣式（與 get_embedded_report_styles 不同，這是更簡潔的版本）"""
    return """
    * {
        margin: 0;
        padding: 0;
        box-sizing: border-box;
    }
    
    body {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        background: #FAFBFD;
        color: #1A237E;
        line-height: 1.6;
    }
    
    .container {
        max-width: 1400px;
        margin: 0 auto;
        padding: 20px;
    }
    
    /* 頁面標題 - 與 download.css 風格一致 */
    .page-header {
        text-align: center;
        margin-bottom: 48px;
        padding: 48px 0;
        position: relative;
        background: white;
        border-radius: 20px;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.06);
    }
    
    .page-header::before {
        content: "";
        position: absolute;
        top: 0;
        left: 50%;
        transform: translateX(-50%);
        width: 120%;
        height: 100%;
        background: radial-gradient(ellipse at center, rgba(33, 150, 243, 0.03) 0%, transparent 70%);
        z-index: -1;
    }
    
    .page-title {
        font-size: 2.75rem;
        font-weight: 600;
        color: #1A237E;
        margin-bottom: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 16px;
        letter-spacing: -0.02em;
        text-shadow: 0 2px 4px rgba(0, 33, 71, 0.05);
    }
    
    .page-title i {
        font-size: 2.5rem;
        color: #2196F3;
        filter: drop-shadow(0 2px 4px rgba(33, 150, 243, 0.15));
    }
    
    .page-subtitle {
        font-size: 1.125rem;
        color: #5C6BC0;
        font-weight: 400;
    }
    
    /* 報表內容區塊 */
    .report-content {
        margin-top: 32px;
    }
    
    .sheet-section {
        background: white;
        border-radius: 20px;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.06);
        margin-bottom: 32px;
        overflow: hidden;
        border: 1px solid #EDF2FC;
        transition: all 0.3s ease;
    }
    
    .sheet-section:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.08);
    }
    
    .sheet-title {
        background: #2196F3;
        color: white;
        padding: 24px 32px;
        margin: 0;
        font-size: 1.375rem;
        font-weight: 600;
        display: flex;
        align-items: center;
        gap: 12px;
        position: relative;
        overflow: hidden;
    }
    
    .sheet-title::before {
        content: "";
        position: absolute;
        top: -100%;
        right: -25%;
        width: 70%;
        height: 300%;
        background: linear-gradient(120deg, transparent 0%, rgba(255, 255, 255, 0.4) 50%, transparent 100%);
        transform: rotate(35deg);
        opacity: 0.5;
    }
    
    .sheet-title i {
        font-size: 1.25rem;
    }
    
    /* 表格容器 */
    .table-container {
        overflow-x: auto;
        background: #FAFBFD;
    }
    
    .table-wrapper {
        min-width: 100%;
        overflow-x: auto;
    }
    
    /* 表格樣式 */
    .data-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.9rem;
        background: white;
    }
    
    .data-table th {
        background: #E3F2FD;
        color: #1976D2;
        padding: 14px 20px;
        text-align: left;
        font-weight: 600;
        border-bottom: 2px solid #BBDEFB;
        white-space: nowrap;
        position: sticky;
        top: 0;
        z-index: 10;
    }
    
    .data-table td {
        padding: 12px 20px;
        border-bottom: 1px solid #EDF2FC;
        color: #424242;
    }
    
    .data-table tr:hover td {
        background: #F5F9FF;
    }
    
    .data-table tr:nth-child(even) td {
        background: #FAFBFD;
    }
    
    .data-table tr:nth-child(even):hover td {
        background: #F0F7FF;
    }
    
    /* 特殊欄位樣式 */
    .highlight-red {
        color: #F44336 !important;
        font-weight: 600;
    }
    
    .highlight-blue {
        color: #2196F3 !important;
    }
    
    /* 徽章樣式 */
    .badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 9999px;
        font-size: 0.8125rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.025em;
    }
    
    .badge-success {
        background: #E8F5E9;
        color: #4CAF50;
        border: 1px solid #4CAF50;
    }
    
    .badge-danger {
        background: #FFEBEE;
        color: #F44336;
        border: 1px solid #F44336;
    }
    
    .badge-warning {
        background: #FFF3E0;
        color: #FF9800;
        border: 1px solid #FF9800;
    }
    
    .badge-info {
        background: #E3F2FD;
        color: #2196F3;
        border: 1px solid #2196F3;
    }
    
    /* 連結樣式 */
    .link {
        color: #2196F3;
        text-decoration: none;
        font-weight: 500;
        transition: all 0.2s ease;
    }
    
    .link:hover {
        color: #1976D2;
        text-decoration: underline;
    }
    
    .link i {
        margin-left: 4px;
        font-size: 0.875em;
    }
    
    /* 空資料提示 */
    .no-data {
        text-align: center;
        padding: 60px;
        color: #9FA8DA;
        font-size: 1.125rem;
    }
    
    .no-data i {
        font-size: 3rem;
        margin-bottom: 16px;
        opacity: 0.5;
    }
    
    /* 列印樣式 */
    @media print {
        body {
            background: white;
        }
        
        .page-header {
            box-shadow: none;
            border: 1px solid #E0E0E0;
            page-break-after: avoid;
        }
        
        .sheet-section {
            box-shadow: none;
            border: 1px solid #E0E0E0;
            page-break-inside: avoid;
            margin-bottom: 20px;
        }
        
        .sheet-section:hover {
            transform: none;
        }
        
        .table-container {
            overflow: visible;
        }
        
        .data-table {
            font-size: 0.8rem;
        }
        
        .data-table th,
        .data-table td {
            padding: 8px 12px;
        }
    }
    
    /* 響應式設計 */
    @media (max-width: 768px) {
        .container {
            padding: 10px;
        }
        
        .page-header {
            padding: 24px 16px;
        }
        
        .page-title {
            font-size: 2rem;
        }
        
        .sheet-title {
            padding: 16px 20px;
            font-size: 1.125rem;
        }
        
        .data-table {
            font-size: 0.8rem;
        }
        
        .data-table th,
        .data-table td {
            padding: 8px 12px;
        }
    }
    """

def generate_data_tables(data):
    """生成所有資料表的 HTML"""
    if not data:
        return '<div class="no-data"><i class="fas fa-inbox"></i><p>無資料</p></div>'
    
    tables_html = ""
    
    # 按照固定順序處理資料表
    sheet_order = ['revision_diff', 'branch_error', 'lost_project', 'version_diff', '無法比對']
    
    # 先處理已定義順序的資料表
    for sheet_name in sheet_order:
        if sheet_name in data:
            sheet_data = data[sheet_name]
            icon = get_sheet_icon(sheet_name)
            tables_html += f"""
            <div class="sheet-section">
                <h2 class="sheet-title">
                    <i class="fas {icon}"></i> {format_sheet_name(sheet_name)}
                </h2>
                <div class="table-container">
                    <div class="table-wrapper">
                        {generate_single_table_html(sheet_name, sheet_data)}
                    </div>
                </div>
            </div>
            """
    
    # 再處理其他未定義的資料表
    for sheet_name, sheet_data in data.items():
        if sheet_name not in sheet_order:
            icon = 'fa-table'
            tables_html += f"""
            <div class="sheet-section">
                <h2 class="sheet-title">
                    <i class="fas {icon}"></i> {format_sheet_name(sheet_name)}
                </h2>
                <div class="table-container">
                    <div class="table-wrapper">
                        {generate_single_table_html(sheet_name, sheet_data)}
                    </div>
                </div>
            </div>
            """
    
    return tables_html

def generate_single_table_html(sheet_name, sheet_data):
    """生成單一表格的 HTML"""
    if not sheet_data or 'data' not in sheet_data:
        return '<div class="no-data"><i class="fas fa-inbox"></i><p>此資料表無內容</p></div>'
    
    columns = sheet_data.get('columns', [])
    data = sheet_data.get('data', [])
    
    if not columns or not data:
        return '<div class="no-data"><i class="fas fa-inbox"></i><p>此資料表無內容</p></div>'
    
    # 開始建立表格
    html = '<table class="data-table">'
    
    # 表頭
    html += '<thead><tr>'
    for col in columns:
        # 特殊處理某些欄位的標題樣式
        header_class = ''
        if col in ['problem', '問題', 'base_short', 'compare_short', 'base_revision', 'compare_revision']:
            header_class = 'highlight-header'
        html += f'<th class="{header_class}">{col}</th>'
    html += '</tr></thead>'
    
    # 表身
    html += '<tbody>'
    for row_idx, row in enumerate(data):
        html += '<tr>'
        for col in columns:
            value = row.get(col, '')
            cell_class = ''
            formatted_value = str(value) if value is not None else ''
            
            # 特殊處理某些欄位
            if col in ['problem', '問題'] and formatted_value:
                cell_class = 'highlight-red'
            elif col == '狀態':
                if formatted_value == '新增':
                    formatted_value = f'<span class="badge badge-success">{formatted_value}</span>'
                elif formatted_value == '刪除':
                    formatted_value = f'<span class="badge badge-danger">{formatted_value}</span>'
            elif col == 'has_wave':
                if formatted_value == 'Y':
                    formatted_value = f'<span class="badge badge-info">Y</span>'
                elif formatted_value == 'N':
                    formatted_value = f'<span class="badge badge-warning">N</span>'
            elif col in ['base_link', 'compare_link', 'link'] and formatted_value:
                # 處理連結
                if formatted_value.startswith('http'):
                    short_url = formatted_value.split('/')[-1][:30] + '...' if len(formatted_value) > 50 else formatted_value
                    formatted_value = f'<a href="{formatted_value}" target="_blank" class="link" title="{formatted_value}">{short_url} <i class="fas fa-external-link-alt"></i></a>'
            elif col in ['base_short', 'compare_short', 'base_revision', 'compare_revision']:
                # Hash 值用等寬字體
                formatted_value = f'<code>{formatted_value}</code>'
            
            html += f'<td class="{cell_class}">{formatted_value}</td>'
        html += '</tr>'
    html += '</tbody>'
    
    html += '</table>'
    return html

def get_sheet_icon(sheet_name):
    """根據資料表名稱返回對應的圖標"""
    icon_map = {
        'revision_diff': 'fa-code-branch',
        'branch_error': 'fa-exclamation-triangle',
        'lost_project': 'fa-folder-minus',
        'version_diff': 'fa-file-alt',
        '無法比對': 'fa-times-circle'
    }
    return icon_map.get(sheet_name, 'fa-table')

def format_sheet_name(sheet_name):
    """格式化資料表名稱為更友好的顯示名稱"""
    name_map = {
        'revision_diff': 'Revision 差異',
        'branch_error': '分支錯誤',
        'lost_project': '新增/刪除專案',
        'version_diff': '版本檔案差異',
        '無法比對': '無法比對的模組'
    }
    return name_map.get(sheet_name, sheet_name)

def get_embedded_report_styles():
    """獲取內嵌的報告樣式"""
    return """
    body {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        background: #F5F7FA;
        margin: 0;
        padding: 0;
        color: #1A237E;
    }
    
    .container {
        max-width: 1400px;
        margin: 0 auto;
        padding: 20px;
    }
    
    .page-header {
        text-align: center;
        margin-bottom: 48px;
        padding: 48px 0;
        background: white;
        border-radius: 16px;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.06);
    }
    
    .page-title {
        font-size: 2.75rem;
        font-weight: 600;
        color: #1A237E;
        margin-bottom: 8px;
    }
    
    .page-subtitle {
        font-size: 1.125rem;
        color: #5C6BC0;
        margin: 0;
    }
    
    .sheet-section {
        background: white;
        border-radius: 16px;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.06);
        margin-bottom: 24px;
        overflow: hidden;
    }
    
    .sheet-title {
        background: #2196F3;
        color: white;
        padding: 20px 32px;
        margin: 0;
        font-size: 1.5rem;
        font-weight: 600;
    }
    
    .table-container {
        padding: 0;
        overflow-x: auto;
    }
    
    .data-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.9rem;
    }
    
    .data-table th {
        background: #E3F2FD;
        color: #1976D2;
        padding: 14px 20px;
        text-align: left;
        font-weight: 600;
        border-bottom: 2px solid #BBDEFB;
        position: sticky;
        top: 0;
    }
    
    .data-table td {
        padding: 12px 20px;
        border-bottom: 1px solid #E8EAF6;
    }
    
    .data-table tr:hover td {
        background: #F5F7FA;
    }
    
    .data-table td.highlight-red {
        color: #F44336;
        font-weight: 600;
    }
    
    .badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 12px;
        font-size: 0.8125rem;
        font-weight: 600;
    }
    
    .badge-success {
        background: #E8F5E9;
        color: #4CAF50;
    }
    
    .badge-danger {
        background: #FFEBEE;
        color: #F44336;
    }
    
    .link {
        color: #2196F3;
        text-decoration: none;
    }
    
    .link:hover {
        text-decoration: underline;
    }
    
    @media print {
        .page-header {
            box-shadow: none;
            border: 1px solid #E0E0E0;
        }
        
        .sheet-section {
            page-break-inside: avoid;
            box-shadow: none;
            border: 1px solid #E0E0E0;
        }
    }
    """

def generate_table_html(sheet_data):
    """生成表格 HTML"""
    if not sheet_data or 'data' not in sheet_data:
        return '<p>無資料</p>'
    
    columns = sheet_data.get('columns', [])
    data = sheet_data.get('data', [])
    
    if not columns or not data:
        return '<p>無資料</p>'
    
    # 開始建立表格
    html = '<table class="data-table">'
    
    # 表頭
    html += '<thead><tr>'
    for col in columns:
        html += f'<th>{col}</th>'
    html += '</tr></thead>'
    
    # 表身
    html += '<tbody>'
    for row in data:
        html += '<tr>'
        for col in columns:
            value = row.get(col, '')
            cell_class = ''
            
            # 特殊處理某些欄位
            if col in ['problem', '問題'] and value:
                cell_class = 'highlight-red'
            elif col == '狀態':
                if value == '新增':
                    value = f'<span class="badge badge-success">{value}</span>'
                elif value == '刪除':
                    value = f'<span class="badge badge-danger">{value}</span>'
            elif col in ['base_link', 'compare_link', 'link'] and value:
                # 處理連結
                if value.startswith('http'):
                    value = f'<a href="{value}" target="_blank" class="link">{value} <i class="fas fa-external-link-alt"></i></a>'
            
            html += f'<td class="{cell_class}">{value}</td>'
        html += '</tr>'
    html += '</tbody>'
    
    html += '</table>'
    return html

@app.route('/api/export-excel-single/<task_id>/<sheet_name>')
def export_excel_single_sheet(task_id, sheet_name):
    """
    匯出原始 Excel 檔案中的單一資料表
    保留原始格式，只移除其他資料表
    """
    try:
        # 查找原始的比對結果檔案
        excel_path = None
        
        # 1. 從比對結果目錄查找
        compare_dir = os.path.join('compare_results', task_id)
        if os.path.exists(compare_dir):
            # 優先查找 all_scenarios_compare.xlsx 或 all_compare.xlsx
            priority_files = ['all_scenarios_compare.xlsx', 'all_compare.xlsx']
            for filename in priority_files:
                file_path = os.path.join(compare_dir, filename)
                if os.path.exists(file_path):
                    excel_path = file_path
                    break
            
            # 如果沒找到，查找任何 xlsx 檔案
            if not excel_path:
                for file in os.listdir(compare_dir):
                    if file.endswith('.xlsx') and not file.startswith('~'):
                        excel_path = os.path.join(compare_dir, file)
                        break
        
        # 2. 從處理狀態中查找
        if not excel_path and task_id in processing_status:
            task_data = processing_status[task_id]
            results = task_data.get('results', {})
            if 'summary_report' in results and os.path.exists(results['summary_report']):
                excel_path = results['summary_report']
            elif 'compare_results' in results:
                compare_results = results['compare_results']
                if isinstance(compare_results, dict) and 'summary_report' in compare_results:
                    if os.path.exists(compare_results['summary_report']):
                        excel_path = compare_results['summary_report']
        
        if not excel_path or not os.path.exists(excel_path):
            app.logger.error(f'找不到 Excel 檔案: task_id={task_id}')
            return jsonify({'error': '找不到原始檔案'}), 404
        
        # 讀取原始 Excel 檔案
        wb = openpyxl.load_workbook(excel_path, data_only=False, keep_vba=False)
        
        # 檢查資料表是否存在
        if sheet_name not in wb.sheetnames:
            app.logger.error(f'找不到資料表: {sheet_name} in {excel_path}')
            return jsonify({'error': f'找不到資料表: {sheet_name}'}), 404
        
        # 創建新的工作簿，只包含指定的資料表
        new_wb = openpyxl.Workbook()
        
        # 移除預設的工作表
        default_sheet = new_wb.active
        new_wb.remove(default_sheet)
        
        # 複製指定的工作表（包含格式）
        source_sheet = wb[sheet_name]
        target_sheet = new_wb.create_sheet(title=sheet_name)
        
        # 複製儲存格資料和格式
        for row in source_sheet.iter_rows():
            for cell in row:
                target_cell = target_sheet.cell(
                    row=cell.row, 
                    column=cell.column, 
                    value=cell.value
                )
                
                # 複製格式
                if cell.has_style:
                    target_cell.font = copy(cell.font)
                    target_cell.fill = copy(cell.fill)
                    target_cell.border = copy(cell.border)
                    target_cell.alignment = copy(cell.alignment)
                    target_cell.number_format = cell.number_format
                    target_cell.protection = copy(cell.protection)
        
        # 複製列寬
        for column_cells in source_sheet.columns:
            column_letter = column_cells[0].column_letter
            if source_sheet.column_dimensions[column_letter].width:
                target_sheet.column_dimensions[column_letter].width = \
                    source_sheet.column_dimensions[column_letter].width
        
        # 複製行高
        for row_cells in source_sheet.rows:
            row_number = row_cells[0].row
            if source_sheet.row_dimensions[row_number].height:
                target_sheet.row_dimensions[row_number].height = \
                    source_sheet.row_dimensions[row_number].height
        
        # 複製合併儲存格
        for merged_range in source_sheet.merged_cells.ranges:
            target_sheet.merge_cells(str(merged_range))
        
        # 複製自動篩選
        if source_sheet.auto_filter.ref:
            target_sheet.auto_filter.ref = source_sheet.auto_filter.ref
        
        # 儲存到記憶體
        output = io.BytesIO()
        new_wb.save(output)
        output.seek(0)
        
        # 生成檔案名稱
        filename = f"{sheet_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        # 回傳檔案
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        app.logger.error(f"匯出單一資料表錯誤: {str(e)}")
        import traceback
        app.logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@app.route('/api/check-excel-columns', methods=['POST'])
def check_excel_columns():
    """檢查 Excel 檔案的欄位"""
    try:
        data = request.json
        filepath = data.get('filepath')
        
        if not filepath or not os.path.exists(filepath):
            return jsonify({'error': '檔案不存在'}), 404
        
        # 使用 ExcelHandler 檢查欄位
        result = excel_handler.check_excel_columns(filepath)
        
        app.logger.info(f"檢查 Excel 欄位結果: {result}")
        
        return jsonify(result)
        
    except Exception as e:
        app.logger.error(f"檢查 Excel 欄位失敗: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/download-complete/<task_id>', methods=['POST'])
def handle_download_complete(task_id):
    """處理下載完成事件 - 用於手動觸發 Excel 檔案處理"""
    try:
        data = request.json
        excel_file = data.get('excel_file')
        
        # 獲取下載資料夾路徑
        download_folder = os.path.join('downloads', task_id)
        
        if not os.path.exists(download_folder):
            return jsonify({'error': '下載資料夾不存在'}), 404
        
        # 獲取 Excel 元資料
        excel_metadata = uploaded_excel_metadata.get(excel_file)
        
        if not excel_metadata:
            return jsonify({
                'excel_copied': False,
                'message': '沒有 Excel 元資料'
            })
        
        # 處理 Excel 檔案
        excel_result = excel_handler.process_download_complete(
            task_id,
            download_folder,
            excel_metadata
        )
        
        # 更新任務結果
        if task_id in processing_status:
            processing_status[task_id]['results'].update(excel_result)
        
        return jsonify(excel_result)
        
    except Exception as e:
        app.logger.error(f"處理下載完成事件失敗: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/copy-excel-to-results', methods=['POST'])
def copy_excel_to_results():
    """複製 Excel 檔案到結果資料夾 API"""
    try:
        data = request.json
        task_id = data.get('task_id')
        original_filepath = data.get('original_filepath')
        new_filename = data.get('new_filename')
        
        if not all([task_id, original_filepath]):
            return jsonify({'error': '缺少必要參數'}), 400
        
        # 獲取下載資料夾
        download_folder = os.path.join('downloads', task_id)
        
        if not os.path.exists(download_folder):
            os.makedirs(download_folder, exist_ok=True)
        
        # 如果沒有指定新檔名，從元資料決定
        if not new_filename:
            excel_metadata = uploaded_excel_metadata.get(original_filepath, {})
            root_folder = excel_metadata.get('root_folder')
            
            if root_folder == 'DailyBuild':
                new_filename = 'DailyBuild_mapping.xlsx'
            elif root_folder in ['/DailyBuild/PrebuildFW', 'PrebuildFW']:
                new_filename = 'PrebuildFW_mapping.xlsx'
            else:
                new_filename = os.path.basename(original_filepath)
        
        # 複製檔案
        target_path = os.path.join(download_folder, new_filename)
        shutil.copy2(original_filepath, target_path)
        
        app.logger.info(f"Excel 檔案已複製: {original_filepath} -> {target_path}")
        
        return jsonify({
            'success': True,
            'new_path': target_path,
            'new_filename': new_filename
        })
        
    except Exception as e:
        app.logger.error(f"複製 Excel 檔案失敗: {str(e)}")
        return jsonify({'error': str(e)}), 500

# 在 web_app.py 的 API 路由部分新增
@app.route('/api/results-structure/<task_id>')
def get_results_structure(task_id):
    """獲取結果檔案結構 API"""
    try:
        structure = {
            'task_id': task_id,
            'scenarios': {}
        }
        
        # 檢查比對結果目錄
        compare_dir = os.path.join('compare_results', task_id)
        
        if not os.path.exists(compare_dir):
            return jsonify({'error': '找不到結果目錄'}), 404
        
        # 檢查各情境子目錄
        scenarios = ['master_vs_premp', 'premp_vs_wave', 'wave_vs_backup']
        
        for scenario in scenarios:
            scenario_dir = os.path.join(compare_dir, scenario)
            if os.path.exists(scenario_dir):
                scenario_data = {
                    'path': scenario_dir,
                    'files': []
                }
                
                # 列出該情境目錄下的所有檔案
                for file in os.listdir(scenario_dir):
                    if file.endswith('.xlsx'):
                        file_path = os.path.join(scenario_dir, file)
                        file_stat = os.stat(file_path)
                        scenario_data['files'].append({
                            'name': file,
                            'path': file_path,
                            'size': file_stat.st_size,
                            'modified': file_stat.st_mtime
                        })
                
                structure['scenarios'][scenario] = scenario_data
        
        return jsonify(structure)
        
    except Exception as e:
        app.logger.error(f'Get results structure error: {e}')
        return jsonify({'error': str(e)}), 500

@app.route('/api/check-scenarios/<task_id>')
def check_scenarios(task_id):
    """檢查情境檔案是否存在"""
    base_path = f"compare_results/{task_id}"
    
    files_to_check = {
        'all': f"{base_path}/all_scenarios_summary.xlsx",
        'master_vs_premp': f"{base_path}/master_vs_premp/all_scenarios_compare.xlsx", 
        'premp_vs_wave': f"{base_path}/premp_vs_wave/all_scenarios_compare.xlsx",
        'wave_vs_backup': f"{base_path}/wave_vs_backup/all_scenarios_compare.xlsx"
    }
    
    scenario_status = {}
    for scenario, file_path in files_to_check.items():
        scenario_status[scenario] = os.path.exists(file_path)
    
    return jsonify(scenario_status)
    
if __name__ == '__main__':
    # 開發模式執行
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)