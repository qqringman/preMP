"""
SFTP 下載與比較系統 - Flask Web 應用程式 (改進版)
"""
import os
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

# 初始化 Flask 應用
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'  # 請更改為安全的密鑰
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB 最大檔案大小

# 初始化 SocketIO
socketio = SocketIO(app, cors_allowed_origins="*")

# 確保必要的目錄存在
for folder in ['uploads', 'downloads', 'compare_results', 'zip_output', 'logs']:
    if not os.path.exists(folder):
        os.makedirs(folder)

# 全域變數存儲處理進度和歷史記錄
processing_status = {}
recent_activities = []
recent_comparisons = []
task_results = {}  # 儲存任務結果以供樞紐分析

# 模擬的統計資料（實際應用中應從資料庫讀取）
statistics = {
    'total': 1234,
    'today': 56,
    'successRate': 98
}

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

    def update_progress(self, progress, status, message, stats=None):
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
            
        processing_status[self.task_id] = update_data
        
        # 透過 SocketIO 發送即時更新
        socketio.emit('progress_update', {
            'task_id': self.task_id,
            **update_data
        }, room=self.task_id)
        
    def process_one_step(self, excel_file, sftp_config):
        """執行一步到位處理"""
        try:
            # 步驟 1：下載
            self.update_progress(10, 'downloading', '正在連接 SFTP 伺服器...')
            
            self.downloader = SFTPDownloader(
                sftp_config.get('host', config.SFTP_HOST),
                sftp_config.get('port', config.SFTP_PORT),
                sftp_config.get('username', config.SFTP_USERNAME),
                sftp_config.get('password', config.SFTP_PASSWORD)
            )
            
            self.update_progress(20, 'downloading', '正在下載檔案...')
            download_dir = os.path.join('downloads', self.task_id)
            report_path = self.downloader.download_from_excel(excel_file, download_dir)
            
            # 模擬下載統計
            stats = {
                'total': 15,
                'downloaded': 12,
                'skipped': 3,
                'failed': 0
            }
            
            self.results['download_report'] = report_path
            self.results['stats'] = stats
            self.update_progress(40, 'downloaded', '下載完成！', stats)
            
            # 步驟 2：比較
            self.update_progress(50, 'comparing', '正在執行所有比對...')
            compare_dir = os.path.join('compare_results', self.task_id)
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
            self.update_progress(100, 'completed', '所有處理完成！')
            
            # 記錄活動
            add_activity('完成一步到位處理', 'success', '15 個模組，3 個比對情境')
            
            # 儲存結果供樞紐分析使用
            save_task_results(self.task_id, all_results)
            
        except Exception as e:
            self.update_progress(0, 'error', f'處理失敗：{str(e)}')
            add_activity('一步到位處理失敗', 'error', str(e))
            raise
            
    def process_download(self, excel_file, sftp_config, options):
        """執行下載處理"""
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
            self.downloader.set_progress_callback(
                lambda p, s, m: self.update_progress(int(20 + p * 0.7), s, m)
            )
            
            self.update_progress(20, 'downloading', '開始下載檔案...')
            
            # 建立下載目錄
            download_dir = os.path.join('downloads', self.task_id)
            
            try:
                # 執行下載
                report_path = self.downloader.download_from_excel_with_progress(
                    excel_file, download_dir
                )
                
                # 取得統計資料
                stats = self.downloader.get_download_stats()
                
                # 生成資料夾結構 - 修正：傳入兩個參數
                folder_structure = self._generate_folder_structure(download_dir, report_path)
                
                # 儲存結果
                self.results['download_report'] = report_path
                self.results['stats'] = stats
                self.results['folder_structure'] = folder_structure
                
                self.update_progress(100, 'completed', '下載完成！', stats)
                add_activity('下載 SFTP 檔案', 'success', 
                            f'成功下載 {stats["downloaded"]} 個檔案')
                
            except Exception as e:
                error_msg = str(e)
                self.update_progress(0, 'error', f'下載失敗：{error_msg}')
                add_activity('下載失敗', 'error', error_msg)
                raise
                
        except Exception as e:
            error_msg = str(e)
            self.update_progress(0, 'error', f'處理失敗：{error_msg}')
            add_activity('下載失敗', 'error', error_msg)
            raise

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
        try:
            self.update_progress(10, 'comparing', '正在準備比對...')
            
            compare_dir = os.path.join('compare_results', self.task_id)
            
            if scenarios == 'all':
                # 執行所有比對情境
                self.update_progress(30, 'comparing', '正在執行所有比對情境...')
                all_results = self.comparator.compare_all_scenarios(source_dir, compare_dir)
                self.results['compare_results'] = all_results
            else:
                # 執行單一比對情境
                self.update_progress(30, 'comparing', f'正在執行 {scenarios} 比對...')
                compare_files = self.comparator.compare_all_modules(source_dir, compare_dir, scenarios)
                self.results['compare_files'] = compare_files
                self.results['summary_report'] = os.path.join(compare_dir, 'all_compare.xlsx')
            
            self.update_progress(100, 'completed', '比對完成！')
            
            # 記錄比對
            add_comparison(scenarios, 'completed', 15)
            
            # 儲存結果
            save_task_results(self.task_id, self.results.get('compare_results', {}))
            
        except Exception as e:
            self.update_progress(0, 'error', f'比對失敗：{str(e)}')
            add_comparison(scenarios, 'error', 0)
            raise

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

def add_comparison(scenario, status, modules):
    """添加比對記錄"""
    comparison = {
        'id': f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
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
    # 模擬儲存比對結果
    if 'summary_report' in results:
        task_results[task_id] = {
            'summary_report': results['summary_report'],
            'timestamp': datetime.now()
        }

# 路由定義
@app.route('/')
def index():
    """首頁"""
    return render_template('index.html')

@app.route('/download')
def download_page():
    """下載頁面"""
    return render_template('download.html')

@app.route('/compare')
def compare_page():
    """比較頁面"""
    return render_template('compare.html')

@app.route('/one-step')
def one_step_page():
    """一步到位頁面"""
    return render_template('one_step.html')

@app.route('/results/<task_id>')
def results_page(task_id):
    """結果頁面"""
    return render_template('results.html', task_id=task_id)

# API 端點
@app.route('/api/upload', methods=['POST'])
def upload_file():
    """上傳檔案 API"""
    if 'file' not in request.files:
        return jsonify({'error': '沒有檔案'}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '沒有選擇檔案'}), 400
        
    if file and file.filename.endswith('.xlsx'):
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        return jsonify({'filename': filename, 'filepath': filepath})
    
    return jsonify({'error': '只支援 Excel (.xlsx) 檔案'}), 400

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
    """下載處理 API"""
    try:
        data = request.json
        
        # 驗證必要參數
        excel_file = data.get('excel_file')
        if not excel_file:
            return jsonify({'error': '缺少 Excel 檔案'}), 400
            
        sftp_config = data.get('sftp_config', {})
        options = data.get('options', {})
        
        # 處理伺服器檔案（如果有）
        server_files = data.get('server_files', [])
        
        # 生成任務 ID
        task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{os.urandom(4).hex()}"
        
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
    """取得任務狀態 API"""
    status = processing_status.get(task_id, {
        'progress': 0,
        'status': 'not_found',
        'message': '找不到任務'
    })
    return jsonify(status)

@app.route('/api/list-directories')
def list_directories():
    """列出可用的目錄 API"""
    directories = []
    
    # 檢查 downloads 目錄
    if os.path.exists('downloads'):
        for item in os.listdir('downloads'):
            item_path = os.path.join('downloads', item)
            if os.path.isdir(item_path):
                directories.append({
                    'path': item_path,
                    'name': f'downloads/{item}',
                    'type': 'download'
                })
    
    # 檢查 compare_results 目錄
    if os.path.exists('compare_results'):
        for item in os.listdir('compare_results'):
            item_path = os.path.join('compare_results', item)
            if os.path.isdir(item_path):
                directories.append({
                    'path': item_path,
                    'name': f'compare_results/{item}',
                    'type': 'compare'
                })
    
    return jsonify(directories)

@app.route('/api/recent-activities')
def get_recent_activities():
    """取得最近活動"""
    return jsonify([{
        'timestamp': activity['timestamp'].isoformat(),
        'action': activity['action'],
        'status': activity['status'],
        'details': activity['details']
    } for activity in recent_activities[:10]])

@app.route('/api/recent-comparisons')
def get_recent_comparisons():
    """取得最近比對記錄"""
    return jsonify([{
        'id': comp['id'],
        'timestamp': comp['timestamp'].isoformat(),
        'scenario': comp['scenario'],
        'status': comp['status'],
        'modules': comp['modules'],
        'duration': comp['duration']
    } for comp in recent_comparisons[:10]])

@app.route('/api/statistics')
def get_statistics():
    """取得統計資料"""
    return jsonify(statistics)

@app.route('/api/pivot-data/<task_id>')
def get_pivot_data(task_id):
    """取得樞紐分析資料 API"""
    # 檢查是否有儲存的結果
    if task_id in task_results:
        result_info = task_results[task_id]
        summary_report = result_info.get('summary_report')
        
        if summary_report and os.path.exists(summary_report):
            try:
                # 讀取 Excel 檔案
                excel_data = pd.read_excel(summary_report, sheet_name=None)
                
                # 轉換為 JSON 格式
                pivot_data = {}
                for sheet_name, df in excel_data.items():
                    # 將 DataFrame 轉換為記錄格式
                    pivot_data[sheet_name] = {
                        'columns': df.columns.tolist(),
                        'data': df.to_dict('records')
                    }
                
                return jsonify(pivot_data)
            except Exception as e:
                return jsonify({'error': f'讀取資料失敗：{str(e)}'}), 500
    
    # 如果沒有真實資料，返回模擬資料
    return jsonify(get_mock_pivot_data())

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
    """匯出 Excel API"""
    # 檢查是否有儲存的結果
    if task_id in task_results:
        result_info = task_results[task_id]
        summary_report = result_info.get('summary_report')
        
        if summary_report and os.path.exists(summary_report):
            return send_file(summary_report, as_attachment=True, 
                           download_name=f'compare_results_{task_id}.xlsx')
    
    # 如果沒有真實檔案，創建一個模擬檔案
    mock_file = create_mock_excel(task_id)
    return send_file(mock_file, as_attachment=True, 
                   download_name=f'compare_results_{task_id}.xlsx')

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

@app.route('/api/browse-server')
def browse_server():
    """瀏覽伺服器檔案 API - 使用真實路徑"""
    path = request.args.get('path', '/')
    
    try:
        # 定義基礎路徑（根據您的實際需求調整）
        base_paths = {
            '/R306_ShareFolder': '/home/vince_lin/ai/R306_ShareFolder',
            '/DailyBuild': '/home/vince_lin/ai/DailyBuild',
            '/PrebuildFW': '/home/vince_lin/ai/PrebuildFW'
        }
        
        # 如果是根目錄，返回可用的頂層目錄
        if path == '/':
            return jsonify({
                'folders': [
                    {'name': 'R306_ShareFolder', 'path': '/R306_ShareFolder'},
                    {'name': 'DailyBuild', 'path': '/DailyBuild'},
                    {'name': 'PrebuildFW', 'path': '/PrebuildFW'}
                ],
                'files': []
            })
            
        # 解析真實路徑
        real_path = None
        for prefix, base in base_paths.items():
            if path.startswith(prefix):
                real_path = path.replace(prefix, base)
                break
                
        if not real_path:
            # 如果沒有匹配的基礎路徑，使用模擬資料
            return get_mock_server_files(path)
            
        # 檢查路徑是否存在
        if os.path.exists(real_path):
            folders = []
            files = []
            
            try:
                for item in os.listdir(real_path):
                    item_path = os.path.join(real_path, item)
                    relative_path = os.path.join(path, item)
                    
                    if os.path.isdir(item_path):
                        folders.append({
                            'name': item,
                            'path': relative_path
                        })
                    elif item.endswith('.xlsx'):  # 只顯示Excel檔案
                        files.append({
                            'name': item,
                            'path': relative_path,
                            'size': os.path.getsize(item_path)
                        })
                        
                # 排序
                folders.sort(key=lambda x: x['name'])
                files.sort(key=lambda x: x['name'])
                
                return jsonify({
                    'folders': folders,
                    'files': files
                })
                
            except PermissionError:
                return jsonify({'error': '沒有權限訪問此目錄'}), 403
        else:
            # 使用模擬資料
            return get_mock_server_files(path)
            
    except Exception as e:
        print(f"Browse server error: {e}")
        return jsonify({'error': str(e)}), 500

def get_mock_server_files(path):
    """提供模擬的伺服器檔案資料"""
    mock_data = {
        '/R306_ShareFolder/nightrun_log': {
            'folders': [
                {'name': 'Demo_stress_Test_log', 'path': '/R306_ShareFolder/nightrun_log/Demo_stress_Test_log'},
                {'name': 'FTP_Paths_2025', 'path': '/R306_ShareFolder/nightrun_log/FTP_Paths_2025'}
            ],
            'files': [
                {'name': 'sample_ftp_paths.xlsx', 'path': '/R306_ShareFolder/nightrun_log/sample_ftp_paths.xlsx', 'size': 5270},
                {'name': 'test_data.xlsx', 'path': '/R306_ShareFolder/nightrun_log/test_data.xlsx', 'size': 8432}
            ]
        },
        '/DailyBuild/Merlin7': {
            'folders': [
                {'name': 'DB2302', 'path': '/DailyBuild/Merlin7/DB2302'},
                {'name': 'DB2857-premp', 'path': '/DailyBuild/Merlin7/DB2857-premp'}
            ],
            'files': []
        }
    }
    
    return jsonify(mock_data.get(path, {'folders': [], 'files': []}))

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
        # 假設檔案路徑格式為: downloads/task_xxx/DailyBuild/Merlin7/DB2302/Version.txt
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

if __name__ == '__main__':
    # 開發模式執行
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)