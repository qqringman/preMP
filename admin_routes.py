"""
後台管理功能路由
處理 chip-mapping 和 prebuild-mapping 功能
"""
import os
import json
import tempfile
import subprocess
import pandas as pd
from flask import Blueprint, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename
import logging
from typing import List, Dict, Any
import glob
import re

logger = logging.getLogger(__name__)

# 建立 Blueprint
admin_bp = Blueprint('admin', __name__)

# 支援的檔案格式
ALLOWED_EXTENSIONS = {'xlsx', 'xls', 'csv'}

def allowed_file(filename):
    """檢查檔案格式是否允許"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@admin_bp.route('/admin')
def admin_page():
    """後台管理主頁面"""
    return render_template('admin.html')

@admin_bp.route('/api/admin/analyze-mapping-table', methods=['POST'])
def analyze_mapping_table():
    """分析 all_chip_mapping_table.xlsx 檔案"""
    try:
        data = request.json
        file_path = data.get('file_path')
        
        if not file_path or not os.path.exists(file_path):
            return jsonify({'error': '檔案不存在'}), 400
            
        # 讀取 Excel 檔案
        df = pd.read_excel(file_path)
        
        # 提取唯一的 DB 資訊
        db_set = set()
        db_details = {}
        
        # 獲取所有模組（晶片）類型
        modules_set = set()
        if 'Module' in df.columns:
            modules_set = set(df['Module'].dropna().unique())
        
        # 檢查所有包含 DB_Info 的欄位
        db_info_columns = [col for col in df.columns if 'DB_Info' in col]
        
        for idx, row in df.iterrows():
            for col in db_info_columns:
                if col in df.columns and pd.notna(row.get(col)):
                    db_val = str(row[col]).strip()
                    # 使用正則表達式匹配 DB 編號
                    match = re.match(r'(DB\d+)', db_val)
                    if match:
                        db_num = match.group(1)
                        db_set.add(db_num)
                        
                        # 初始化 DB 詳細資訊
                        if db_num not in db_details:
                            db_details[db_num] = {
                                'types': set(),
                                'modules': set(),
                                'paths': []
                            }
                        
                        # 分析 DB 類型
                        if 'master' in col.lower():
                            db_details[db_num]['types'].add('master')
                        elif 'premp' in col.lower():
                            db_details[db_num]['types'].add('premp')
                        elif 'mpbackup' in col.lower():
                            db_details[db_num]['types'].add('mpbackup')
                        elif 'mp' in col.lower():
                            db_details[db_num]['types'].add('mp')
                        
                        # 添加模組資訊
                        if 'Module' in row and pd.notna(row['Module']):
                            db_details[db_num]['modules'].add(str(row['Module']))
                        
                        # 添加路徑資訊
                        path_col = col.replace('DB_Info', 'SftpPath')
                        if path_col in df.columns and pd.notna(row.get(path_col)):
                            db_details[db_num]['paths'].append(str(row[path_col]))
        
        # 轉換 set 為 list
        db_list = sorted(list(db_set))
        
        # 格式化 DB 資訊
        db_info = {}
        for db, details in db_details.items():
            db_info[db] = {
                'types': sorted(list(details['types'])),
                'modules': sorted(list(details['modules'])),
                'paths': details['paths'][:5]  # 限制路徑數量
            }
        
        return jsonify({
            'success': True,
            'db_list': db_list,
            'db_info': db_info,
            'modules': sorted(list(modules_set)),
            'total_rows': len(df),
            'columns': list(df.columns)
        })
        
    except Exception as e:
        logger.error(f"分析 mapping table 失敗: {str(e)}")
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/api/admin/get-db-versions', methods=['POST'])
def get_db_versions():
    """獲取指定 DB 的版本列表"""
    try:
        data = request.json
        db_name = data.get('db_name')
        mapping_file = data.get('mapping_file')
        
        if not mapping_file or not os.path.exists(mapping_file):
            return jsonify({'error': 'Mapping 檔案不存在'}), 400
            
        # 讀取 Excel 檔案
        df = pd.read_excel(mapping_file)
        
        # 收集所有相關的 SFTP 路徑
        sftp_paths = []
        
        # 查找所有包含 DB_Info 和對應 SftpPath 的欄位
        for col in df.columns:
            if 'DB_Info' in col:
                # 找到對應的 SftpPath 欄位
                path_col = col.replace('DB_Info', 'SftpPath')
                if path_col in df.columns:
                    # 過濾出匹配的 DB
                    mask = df[col].astype(str).str.strip().str.startswith(db_name)
                    paths = df.loc[mask, path_col].dropna().unique()
                    sftp_paths.extend(paths)
        
        # 使用 SFTP Manager 獲取版本資訊
        from vp_lib.sftp_manager import SFTPManager
        sftp_manager = SFTPManager()
        versions = set()
        
        try:
            sftp_manager.connect()
            
            for path in sftp_paths[:10]:  # 限制查詢數量以提高效能
                try:
                    # 列出目錄內容
                    items = sftp_manager._sftp.listdir(path)
                    
                    # 過濾版本資料夾（格式: 數字開頭）
                    for item in items:
                        match = re.match(r'^(\d+)_', item)
                        if match:
                            versions.add(match.group(1))
                            
                except Exception as e:
                    logger.warning(f"無法讀取路徑 {path}: {str(e)}")
                    continue
                    
        finally:
            sftp_manager.disconnect()
        
        # 排序版本號（數字排序，大的在前）
        sorted_versions = sorted(list(versions), key=lambda x: int(x) if x.isdigit() else 0, reverse=True)
        
        return jsonify({
            'success': True,
            'versions': sorted_versions[:50]  # 限制返回數量
        })
        
    except Exception as e:
        logger.error(f"獲取 DB 版本失敗: {str(e)}")
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/api/admin/run-chip-mapping', methods=['POST'])
def run_chip_mapping():
    """執行 chip-mapping 命令"""
    try:
        data = request.json
        mapping_file = data.get('mapping_file')
        filter_type = data.get('filter_type', 'all')
        db_filter = data.get('db_filter', 'all')
        output_path = data.get('output_path', './output')
        
        if not mapping_file or not os.path.exists(mapping_file):
            return jsonify({'error': 'Mapping 檔案不存在'}), 400
        
        # 建立輸出目錄
        if not os.path.exists(output_path):
            os.makedirs(output_path)
        
        # 處理 DB 參數
        db_param = db_filter
        if '#' in db_filter:
            # 已經包含版本資訊
            db_param = db_filter
        elif db_filter != 'all':
            # 只有 DB 名稱，沒有版本
            db_param = db_filter
        
        # 組合命令
        cmd = [
            'python3', 'vp_lib/cli_interface.py', 'chip-mapping',
            '-i', mapping_file,
            '-filter', filter_type,
            '-o', output_path
        ]
        
        # 添加 DB 參數
        if db_param != 'all':
            cmd.extend(['-db', db_param])
        
        logger.info(f"執行命令: {' '.join(cmd)}")
        
        # 執行命令
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=os.getcwd())
        
        if result.returncode != 0:
            logger.error(f"執行失敗: stdout={result.stdout}, stderr={result.stderr}")
            return jsonify({
                'error': '執行失敗',
                'stdout': result.stdout,
                'stderr': result.stderr,
                'command': ' '.join(cmd)
            }), 500
        
        # 查找輸出的 Excel 檔案
        output_files = glob.glob(os.path.join(output_path, '*.xlsx'))
        
        # 讀取結果檔案
        result_data = []
        columns = []
        if output_files:
            # 讀取最新的檔案
            latest_file = max(output_files, key=os.path.getctime)
            df = pd.read_excel(latest_file)
            result_data = df.to_dict('records')
            columns = list(df.columns)
        
        return jsonify({
            'success': True,
            'output_file': latest_file if output_files else None,
            'data': result_data[:100],  # 限制返回的資料量
            'total_rows': len(result_data),
            'columns': columns
        })
        
    except Exception as e:
        logger.error(f"執行 chip-mapping 失敗: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/api/admin/run-prebuild-mapping', methods=['POST'])
def run_prebuild_mapping():
    """執行 prebuild-mapping 命令"""
    try:
        data = request.json
        files = data.get('files', {})
        output_path = data.get('output_path', './output')
        
        # 檢查至少有兩個檔案
        valid_files = {k: v for k, v in files.items() if v and os.path.exists(v)}
        if len(valid_files) < 2:
            return jsonify({'error': '至少需要選擇兩個檔案'}), 400
        
        # 建立輸出目錄
        if not os.path.exists(output_path):
            os.makedirs(output_path)
        
        # 決定 filter 參數
        filter_parts = []
        if 'master' in valid_files and 'premp' in valid_files:
            filter_parts.append('master_vs_premp')
        if 'premp' in valid_files and 'mp' in valid_files:
            filter_parts.append('premp_vs_mp')
        if 'mp' in valid_files and 'mpbackup' in valid_files:
            filter_parts.append('mp_vs_mpbackup')
        
        if not filter_parts:
            return jsonify({'error': '無法決定比對類型'}), 400
        
        filter_param = ','.join(filter_parts) if len(filter_parts) > 1 else filter_parts[0]
        
        # 準備檔案列表
        file_list = []
        for file_type in ['master', 'premp', 'mp', 'mpbackup']:
            if file_type in valid_files:
                file_list.append(valid_files[file_type])
        
        # 組合命令
        cmd = [
            'python3', 'vp_lib/cli_interface.py', 'prebuild-mapping',
            '-filter', filter_param,
            '-i', ','.join(file_list),
            '-o', output_path
        ]
        
        logger.info(f"執行命令: {' '.join(cmd)}")
        
        # 執行命令
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=os.getcwd())
        
        if result.returncode != 0:
            logger.error(f"執行失敗: stdout={result.stdout}, stderr={result.stderr}")
            return jsonify({
                'error': '執行失敗',
                'stdout': result.stdout,
                'stderr': result.stderr,
                'command': ' '.join(cmd)
            }), 500
        
        # 查找輸出的 Excel 檔案
        output_files = glob.glob(os.path.join(output_path, '*.xlsx'))
        
        # 讀取結果檔案
        result_data = []
        columns = []
        if output_files:
            # 讀取最新的檔案
            latest_file = max(output_files, key=os.path.getctime)
            df = pd.read_excel(latest_file)
            result_data = df.to_dict('records')
            columns = list(df.columns)
        
        return jsonify({
            'success': True,
            'output_file': latest_file if output_files else None,
            'data': result_data[:100],  # 限制返回的資料量
            'total_rows': len(result_data),
            'columns': columns
        })
        
    except Exception as e:
        logger.error(f"執行 prebuild-mapping 失敗: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/api/admin/export-result', methods=['POST'])
def export_result():
    """匯出結果為 Excel"""
    try:
        data = request.json
        result_data = data.get('data', [])
        columns = data.get('columns', [])
        filename = data.get('filename', 'export.xlsx')
        
        # 建立 DataFrame
        df = pd.DataFrame(result_data, columns=columns)
        
        # 建立臨時檔案
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
            df.to_excel(tmp.name, index=False)
            tmp_path = tmp.name
        
        return send_file(
            tmp_path,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        logger.error(f"匯出結果失敗: {str(e)}")
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/api/admin/get-download-dirs', methods=['GET'])
def get_download_dirs():
    """獲取已下載的目錄列表"""
    try:
        import config
        import re
        
        dirs = []
        
        # 使用 config 中的 DEFAULT_OUTPUT_DIR
        download_base = getattr(config, 'DEFAULT_OUTPUT_DIR', './downloads')
        
        # 獲取當前工作目錄的絕對路徑
        current_dir = os.getcwd()
        
        # 掃描當前目錄下所有符合 task_* 模式的目錄
        task_pattern = re.compile(r'^task_\d{8}_\d{6}_[a-f0-9]+$')
        
        # 掃描當前目錄
        for item in os.listdir(current_dir):
            item_path = os.path.join(current_dir, item)
            if os.path.isdir(item_path):
                # 檢查是否是 task 目錄
                if task_pattern.match(item):
                    # 計算目錄資訊
                    file_count = 0
                    total_size = 0
                    for root, _, files in os.walk(item_path):
                        file_count += len(files)
                        for f in files:
                            try:
                                total_size += os.path.getsize(os.path.join(root, f))
                            except:
                                pass
                    
                    dirs.append({
                        'name': item,
                        'path': item_path,
                        'file_count': file_count,
                        'size': total_size,
                        'size_formatted': format_file_size(total_size),
                        'type': 'task'
                    })
        
        # 掃描 downloads 目錄（如果存在）
        if os.path.exists(download_base):
            # 掃描 downloads 下的所有子目錄
            for root, directories, files in os.walk(download_base):
                for dir_name in directories:
                    dir_path = os.path.join(root, dir_name)
                    rel_path = os.path.relpath(dir_path, download_base)
                    
                    # 計算目錄資訊
                    file_count = 0
                    total_size = 0
                    for sub_root, _, sub_files in os.walk(dir_path):
                        file_count += len(sub_files)
                        for f in sub_files:
                            try:
                                total_size += os.path.getsize(os.path.join(sub_root, f))
                            except:
                                pass
                    
                    if file_count > 0:  # 只顯示有檔案的目錄
                        dirs.append({
                            'name': f'downloads/{rel_path}',
                            'path': dir_path,
                            'file_count': file_count,
                            'size': total_size,
                            'size_formatted': format_file_size(total_size),
                            'type': 'download'
                        })
        
        # 按名稱排序
        dirs.sort(key=lambda x: x['name'])
        
        return jsonify({
            'success': True,
            'directories': dirs,
            'base_path': current_dir,
            'download_path': download_base
        })
        
    except Exception as e:
        logger.error(f"獲取下載目錄失敗: {str(e)}")
        return jsonify({'error': str(e)}), 500

def format_file_size(size_bytes):
    """格式化檔案大小"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"