"""
SFTP 下載與比較系統 - Flask Web 應用程式
"""
import os
import sys
import json
import threading
import time
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file, session, url_for, redirect
from flask_socketio import SocketIO, emit
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
for folder in ['uploads', 'downloads', 'compare_results', 'zip_output']:
    if not os.path.exists(folder):
        os.makedirs(folder)

# 全域變數存儲處理進度
processing_status = {}

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
        
    def update_progress(self, progress, status, message):
        """更新處理進度"""
        self.progress = progress
        self.status = status
        self.message = message
        processing_status[self.task_id] = {
            'progress': progress,
            'status': status,
            'message': message,
            'results': self.results
        }
        # 透過 SocketIO 發送即時更新
        socketio.emit('progress_update', {
            'task_id': self.task_id,
            'progress': progress,
            'status': status,
            'message': message
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
            
            self.results['download_report'] = report_path
            self.update_progress(40, 'downloaded', '下載完成！')
            
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
            
        except Exception as e:
            self.update_progress(0, 'error', f'處理失敗：{str(e)}')
            raise
            
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
            
        except Exception as e:
            self.update_progress(0, 'error', f'比對失敗：{str(e)}')
            raise

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

@app.route('/api/download-file/<path:filepath>')
def download_file(filepath):
    """下載檔案 API"""
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True)
    return jsonify({'error': '檔案不存在'}), 404

@app.route('/api/export-excel/<task_id>')
def export_excel(task_id):
    """匯出 Excel API"""
    status = processing_status.get(task_id, {})
    results = status.get('results', {})
    
    if 'compare_results' in results:
        summary_report = results['compare_results'].get('summary_report')
        if summary_report and os.path.exists(summary_report):
            return send_file(summary_report, as_attachment=True, 
                           download_name=f'compare_results_{task_id}.xlsx')
    
    return jsonify({'error': '找不到比對結果'}), 404

@app.route('/api/export-html/<task_id>')
def export_html(task_id):
    """匯出 HTML API"""
    status = processing_status.get(task_id, {})
    results = status.get('results', {})
    
    # 讀取 Excel 並轉換為 HTML
    if 'compare_results' in results:
        summary_report = results['compare_results'].get('summary_report')
        if summary_report and os.path.exists(summary_report):
            try:
                # 讀取 Excel 檔案
                excel_data = pd.read_excel(summary_report, sheet_name=None)
                
                # 生成 HTML
                html_content = render_template('export_report.html',
                                             task_id=task_id,
                                             sheets=excel_data)
                
                # 儲存為檔案
                html_file = os.path.join('zip_output', task_id, f'report_{task_id}.html')
                os.makedirs(os.path.dirname(html_file), exist_ok=True)
                
                with open(html_file, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                
                return send_file(html_file, as_attachment=True,
                               download_name=f'report_{task_id}.html')
            except Exception as e:
                return jsonify({'error': f'轉換失敗：{str(e)}'}), 500
    
    return jsonify({'error': '找不到比對結果'}), 404

@app.route('/api/export-zip/<task_id>')
def export_zip(task_id):
    """匯出 ZIP API"""
    status = processing_status.get(task_id, {})
    results = status.get('results', {})
    
    if 'zip_file' in results:
        zip_file = results['zip_file']
        if zip_file and os.path.exists(zip_file):
            return send_file(zip_file, as_attachment=True)
    
    return jsonify({'error': '找不到打包檔案'}), 404

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

@app.route('/api/pivot-data/<task_id>')
def get_pivot_data(task_id):
    """取得樞紐分析資料 API"""
    status = processing_status.get(task_id, {})
    results = status.get('results', {})
    
    if 'compare_results' in results:
        summary_report = results['compare_results'].get('summary_report')
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
    
    return jsonify({'error': '找不到比對結果'}), 404

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
        socketio.server.enter_room(request.sid, task_id)
        emit('joined', {'task_id': task_id})

# 錯誤處理
@app.errorhandler(404)
def not_found(error):
    """404 錯誤處理"""
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    """500 錯誤處理"""
    return render_template('500.html'), 500

if __name__ == '__main__':
    # 開發模式執行
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)