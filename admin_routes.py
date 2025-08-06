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
        
        # 提取 DB/IC 資訊
        db_list = []
        if 'DB' in df.columns:
            db_list = df['DB'].dropna().unique().tolist()
        
        # 分析每個 DB 的路徑和版本
        db_info = {}
        for db in db_list:
            db_rows = df[df['DB'] == db]
            if 'ftp path' in db_rows.columns:
                paths = db_rows['ftp path'].dropna().unique().tolist()
                # 從路徑中提取版本號（這裡需要根據實際路徑格式調整）
                versions = []
                for path in paths:
                    # 假設版本號在路徑中的格式是 /DBxxxx_xxx/版本號/
                    parts = path.split('/')
                    for part in parts:
                        if part.isdigit() or (part and part[0].isdigit()):
                            versions.append(part)
                            break
                
                db_info[db] = {
                    'paths': paths[:5],  # 只返回前5個路徑作為示例
                    'versions': list(set(versions))[:10]  # 去重並限制數量
                }
        
        return jsonify({
            'success': True,
            'db_list': db_list[:50],  # 限制返回數量
            'db_info': db_info,
            'total_rows': len(df)
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
        
        # 過濾指定的 DB
        if 'DB' in df.columns:
            db_rows = df[df['DB'] == db_name]
            
            # 從 FTP 路徑中提取版本號
            versions = set()
            if 'ftp path' in db_rows.columns:
                for path in db_rows['ftp path'].dropna():
                    # 解析路徑提取版本號
                    # 例如: /DailyBuild/Merlin7/DB2857_xxx/69_202507292300
                    parts = path.split('/')
                    for i, part in enumerate(parts):
                        if part.startswith(f'DB{db_name[2:]}'):  # 假設 DB 名稱格式為 DBxxxx
                            # 下一個部分可能是版本號
                            if i + 1 < len(parts):
                                version_part = parts[i + 1]
                                if '_' in version_part:
                                    version = version_part.split('_')[0]
                                    if version.isdigit():
                                        versions.add(version)
                            break
            
            return jsonify({
                'success': True,
                'versions': sorted(list(versions), key=lambda x: int(x) if x.isdigit() else 0, reverse=True)[:20]
            })
        
        return jsonify({'success': True, 'versions': []})
        
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
        db_version = data.get('db_version')
        output_path = data.get('output_path', './output')
        
        if not mapping_file or not os.path.exists(mapping_file):
            return jsonify({'error': 'Mapping 檔案不存在'}), 400
        
        # 建立輸出目錄
        if not os.path.exists(output_path):
            os.makedirs(output_path)
        
        # 組合命令
        cmd = [
            'python3.12', 'cli_interface.py', 'chip-mapping',
            '-i', mapping_file,
            '-filter', filter_type,
            '-o', output_path
        ]
        
        # 添加 DB 過濾參數
        if db_filter != 'all':
            cmd.extend(['-db', db_filter])
            if db_version:
                cmd[-1] = f"{db_filter}:{db_version}"
        
        logger.info(f"執行命令: {' '.join(cmd)}")
        
        # 執行命令
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            return jsonify({
                'error': '執行失敗',
                'stderr': result.stderr
            }), 500
        
        # 查找輸出的 Excel 檔案
        output_files = glob.glob(os.path.join(output_path, '*.xlsx'))
        
        # 讀取結果檔案
        result_data = []
        if output_files:
            # 讀取最新的檔案
            latest_file = max(output_files, key=os.path.getctime)
            df = pd.read_excel(latest_file)
            result_data = df.to_dict('records')
        
        return jsonify({
            'success': True,
            'output_file': latest_file if output_files else None,
            'data': result_data[:100],  # 限制返回的資料量
            'total_rows': len(result_data),
            'columns': list(df.columns) if output_files else []
        })
        
    except Exception as e:
        logger.error(f"執行 chip-mapping 失敗: {str(e)}")
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
            'python3.12', 'cli_interface.py', 'prebuild-mapping',
            '-filter', filter_param,
            '-i', ','.join(file_list),
            '-o', output_path
        ]
        
        logger.info(f"執行命令: {' '.join(cmd)}")
        
        # 執行命令
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            return jsonify({
                'error': '執行失敗',
                'stderr': result.stderr
            }), 500
        
        # 查找輸出的 Excel 檔案
        output_files = glob.glob(os.path.join(output_path, '*.xlsx'))
        
        # 讀取結果檔案
        result_data = []
        if output_files:
            # 讀取最新的檔案
            latest_file = max(output_files, key=os.path.getctime)
            df = pd.read_excel(latest_file)
            result_data = df.to_dict('records')
        
        return jsonify({
            'success': True,
            'output_file': latest_file if output_files else None,
            'data': result_data[:100],  # 限制返回的資料量
            'total_rows': len(result_data),
            'columns': list(df.columns) if output_files else []
        })
        
    except Exception as e:
        logger.error(f"執行 prebuild-mapping 失敗: {str(e)}")
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
        dirs = []
        
        # 檢查 downloads 目錄
        download_base = './downloads'
        if os.path.exists(download_base):
            # 獲取 PrebuildFW 下的目錄
            prebuild_path = os.path.join(download_base, 'PrebuildFW')
            if os.path.exists(prebuild_path):
                for module in os.listdir(prebuild_path):
                    module_path = os.path.join(prebuild_path, module)
                    if os.path.isdir(module_path):
                        dirs.append({
                            'name': f'PrebuildFW/{module}',
                            'path': module_path
                        })
            
            # 獲取 DailyBuild 下的目錄
            daily_path = os.path.join(download_base, 'DailyBuild')
            if os.path.exists(daily_path):
                for platform in os.listdir(daily_path):
                    platform_path = os.path.join(daily_path, platform)
                    if os.path.isdir(platform_path):
                        dirs.append({
                            'name': f'DailyBuild/{platform}',
                            'path': platform_path
                        })
        
        # 檢查 compare_results 目錄
        compare_base = './compare_results'
        if os.path.exists(compare_base):
            for scenario in os.listdir(compare_base):
                scenario_path = os.path.join(compare_base, scenario)
                if os.path.isdir(scenario_path):
                    dirs.append({
                        'name': f'compare_results/{scenario}',
                        'path': scenario_path
                    })
        
        return jsonify({
            'success': True,
            'directories': dirs
        })
        
    except Exception as e:
        logger.error(f"獲取下載目錄失敗: {str(e)}")
        return jsonify({'error': str(e)}), 500