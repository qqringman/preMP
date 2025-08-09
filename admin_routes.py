"""
後台管理功能路由
處理 chip-mapping 和 prebuild-mapping 功能
"""
import os
import json
import tempfile
import subprocess
import pandas as pd
from flask import Blueprint, render_template, request, jsonify, send_file, session, redirect, url_for
from werkzeug.utils import secure_filename
import logging
from typing import List, Dict, Any
import glob
import re
from functools import wraps
import config

logger = logging.getLogger(__name__)

# 建立 Blueprint
admin_bp = Blueprint('admin', __name__)

# 支援的檔案格式
ALLOWED_EXTENSIONS = {'xlsx', 'xls', 'csv'}

def allowed_file(filename):
    """檢查檔案格式是否允許"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def login_required(f):
    """登入檢查裝飾器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 如果沒有啟用登入功能，直接通過
        if not getattr(config, 'ENABLE_LOGIN', False):
            return f(*args, **kwargs)
        
        # 檢查登入狀態
        if 'logged_in' not in session or not session['logged_in']:
            if request.is_json:
                return jsonify({'error': '請先登入', 'redirect': '/login'}), 401
            return redirect(url_for('admin.login_page', redirect=request.url))
        
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/api/user-status', methods=['GET'])
def get_user_status():
    """獲取用戶登入狀態"""
    # 如果沒有啟用登入功能
    if not getattr(config, 'ENABLE_LOGIN', False):
        return jsonify({
            'logged_in': False,
            'login_enabled': False,
            'username': None
        })
    
    # 檢查登入狀態
    is_logged_in = 'logged_in' in session and session['logged_in']
    username = session.get('username') if is_logged_in else None
    
    return jsonify({
        'logged_in': is_logged_in,
        'login_enabled': True,
        'username': username
    })

@admin_bp.route('/login')
def login_page():
    """登入頁面"""
    # 如果沒有啟用登入功能，重定向到後台
    if not getattr(config, 'ENABLE_LOGIN', False):
        return redirect(url_for('admin.admin_page'))
    
    # 如果已經登入，重定向到目標頁面
    if 'logged_in' in session and session['logged_in']:
        redirect_url = request.args.get('redirect', url_for('admin.admin_page'))
        return redirect(redirect_url)
    
    return render_template('login.html', login_hint="請使用管理員帳號登入後台系統")

@admin_bp.route('/api/login', methods=['POST'])
def login():
    """處理登入請求"""
    try:
        data = request.json
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        
        # 檢查帳號密碼
        admin_users = getattr(config, 'ADMIN_USERS', {})
        
        if username in admin_users and admin_users[username] == password:
            # 登入成功
            session['logged_in'] = True
            session['username'] = username
            session.permanent = True
            
            return jsonify({
                'success': True,
                'message': '登入成功',
                'username': username
            })
        else:
            return jsonify({
                'success': False,
                'message': '帳號或密碼錯誤'
            }), 401
            
    except Exception as e:
        logger.error(f"登入失敗: {str(e)}")
        return jsonify({
            'success': False,
            'message': '登入失敗，請稍後再試'
        }), 500

@admin_bp.route('/api/logout', methods=['POST'])
def logout():
    """登出"""
    session.clear()
    return jsonify({'success': True, 'message': '已登出'})

@admin_bp.route('/admin')
@login_required
def admin_page():
    """後台管理主頁面"""
    return render_template('admin.html')

@admin_bp.route('/api/admin/analyze-mapping-table', methods=['POST'])
@login_required
def analyze_mapping_table():
    """分析 all_chip_mapping_table.xlsx 檔案 - 修正版本"""
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
                                'paths': [],
                                'full_info': db_val  # 保存完整資訊
                            }
                        
                        # 分析 DB 類型 - 更精確的判斷
                        col_lower = col.lower()
                        if 'master' in col_lower:
                            db_details[db_num]['types'].add('master')
                        elif 'premp' in col_lower or 'pre' in col_lower:
                            db_details[db_num]['types'].add('premp')
                        elif 'mpbackup' in col_lower or 'backup' in col_lower:
                            db_details[db_num]['types'].add('mpbackup')
                        elif 'mp' in col_lower and 'backup' not in col_lower:
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
                'paths': details['paths'][:5],  # 限制路徑數量
                'display_types': list(details['types'])  # 用於顯示
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

@admin_bp.route('/api/admin/get-default-mapping-table', methods=['GET'])
@login_required
def get_default_mapping_table():
    """取得預設的 mapping table 路徑和內容"""
    try:
        default_path = getattr(config, 'DEFAULT_MAPPING_TABLE_PATH', '/home/vince_lin/ai/preMP/vp_lib/all_chip_mapping_table.xlsx')
        
        # 檢查檔案是否存在
        if not os.path.exists(default_path):
            return jsonify({
                'success': False,
                'error': f'預設檔案不存在: {default_path}'
            }), 404
        
        # 分析檔案 - 修復 coroutine 錯誤，移除 async
        analysis_result = analyze_mapping_file(default_path)
        
        return jsonify({
            'success': True,
            'file_path': default_path,
            'file_info': {
                'name': os.path.basename(default_path),
                'size': os.path.getsize(default_path),
                'modified': os.path.getmtime(default_path)
            },
            'analysis': analysis_result
        })
        
    except Exception as e:
        logger.error(f"取得預設 mapping table 失敗: {str(e)}")
        return jsonify({'error': str(e)}), 500

def analyze_mapping_file(file_path):
    """分析 mapping 檔案的輔助函數 - 修復：移除 async"""
    # 讀取 Excel 檔案
    df = pd.read_excel(file_path)
    
    # 提取 DB 和模組資訊（重複使用現有邏輯）
    db_set = set()
    modules_set = set()
    
    if 'Module' in df.columns:
        modules_set = set(df['Module'].dropna().unique())
    
    db_info_columns = [col for col in df.columns if 'DB_Info' in col]
    for idx, row in df.iterrows():
        for col in db_info_columns:
            if col in df.columns and pd.notna(row.get(col)):
                db_val = str(row[col]).strip()
                match = re.match(r'(DB\d+)', db_val)
                if match:
                    db_set.add(match.group(1))
    
    return {
        'db_list': sorted(list(db_set)),
        'modules': sorted(list(modules_set)),
        'total_rows': len(df)
    }

@admin_bp.route('/api/admin/get-db-versions', methods=['POST'])
@login_required
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
        
        # 檢查最大版本數限制
        max_versions = getattr(config, 'MAX_DB_VERSIONS', 50)
        if max_versions != 'max':
            sorted_versions = sorted_versions[:max_versions]
        
        return jsonify({
            'success': True,
            'versions': sorted_versions
        })
        
    except Exception as e:
        logger.error(f"獲取 DB 版本失敗: {str(e)}")
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/api/admin/run-chip-mapping', methods=['POST'])
@login_required
def run_chip_mapping():
    """執行 chip-mapping 命令"""
    try:
        data = request.json
        mapping_file = data.get('mapping_file')
        filter_types = data.get('filter_types', ['all'])  # 改為列表
        chip_filters = data.get('chip_filters', ['all'])  # 改為列表
        db_filters = data.get('db_filters', ['all'])  # 改為列表
        output_path = data.get('output_path', getattr(config, 'DEFAULT_CHIP_OUTPUT_DIR', './output/chip_mapping'))
        
        if not mapping_file or not os.path.exists(mapping_file):
            return jsonify({'error': 'Mapping 檔案不存在'}), 400
        
        # 建立輸出目錄
        if not os.path.exists(output_path):
            os.makedirs(output_path)
        
        # 組合 filter 參數 - 使用 OR 邏輯連接
        filter_parts = []
        
        # 組合所有篩選條件
        for filter_type in filter_types:
            if filter_type != 'all':
                filter_parts.append(filter_type)
        
        for chip_filter in chip_filters:
            if chip_filter != 'all':
                filter_parts.append(chip_filter)
        
        # 如果沒有特定篩選條件，使用 'all'
        filter_param = ','.join(filter_parts) if filter_parts else 'all'
        
        # 處理 DB 參數 - 支援多個 DB
        db_param_list = []
        for db_filter in db_filters:
            if db_filter != 'all':
                db_param_list.append(db_filter)
        
        # 為每個 DB 組合執行命令
        all_results = []
        
        if not db_param_list:
            db_param_list = ['all']
        
        for db_param in db_param_list:
            # 組合命令
            cmd = [
                'python3.12', 'vp_lib/cli_interface.py', 'chip-mapping',
                '-i', mapping_file,
                '-filter', filter_param,
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
            # 合併所有結果檔案
            all_data = []
            
            for file_path in output_files:
                df = pd.read_excel(file_path, dtype=str)
                df = df.fillna('')
                all_data.append(df)
            
            if all_data:
                # 合併所有 DataFrame
                combined_df = pd.concat(all_data, ignore_index=True)
                
                # 確保 SN 是數字字串
                if 'SN' in combined_df.columns:
                    combined_df['SN'] = combined_df['SN'].astype(str)
                
                # 預期的欄位順序
                expected_columns = [
                    'SN', 'RootFolder', 'Module', 'DB_Type', 'DB_Info', 
                    'DB_Folder', 'DB_Version', 'SftpPath',
                    'compare_DB_Type', 'compare_DB_Info', 
                    'compare_DB_Folder', 'compare_DB_Version', 'compare_SftpPath'
                ]
                
                # 確保欄位存在且順序正確
                available_columns = [col for col in expected_columns if col in combined_df.columns]
                
                if available_columns:
                    combined_df = combined_df[available_columns]
                
                result_data = combined_df.replace({pd.NA: '', pd.NaT: '', float('nan'): ''}).to_dict('records')
                columns = list(combined_df.columns)
        
        return jsonify({
            'success': True,
            'output_files': output_files,
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
@login_required
def run_prebuild_mapping():
    """執行 prebuild-mapping 命令 - 修改為分別處理不同組合"""
    try:
        data = request.json
        files = data.get('files', {})
        output_path = data.get('output_path', getattr(config, 'DEFAULT_PREBUILD_OUTPUT_DIR', './output/prebuild_mapping'))
        
        # 檢查至少有兩個檔案
        valid_files = {k: v for k, v in files.items() if v and os.path.exists(v)}
        if len(valid_files) < 2:
            return jsonify({'error': '至少需要選擇兩個檔案'}), 400
        
        # 建立輸出目錄
        if not os.path.exists(output_path):
            os.makedirs(output_path)
        
        # 定義可能的比對組合
        comparisons = []
        
        if 'master' in valid_files and 'premp' in valid_files:
            comparisons.append({
                'type': 'master_vs_premp',
                'files': [valid_files['master'], valid_files['premp']],
                'output_name': 'PrebuildFW_master_vs_premp_mapping.xlsx'
            })
        
        if 'premp' in valid_files and 'mp' in valid_files:
            comparisons.append({
                'type': 'premp_vs_mp',
                'files': [valid_files['premp'], valid_files['mp']],
                'output_name': 'PrebuildFW_premp_vs_mp_mapping.xlsx'
            })
        
        if 'mp' in valid_files and 'mpbackup' in valid_files:
            comparisons.append({
                'type': 'mp_vs_mpbackup',
                'files': [valid_files['mp'], valid_files['mpbackup']],
                'output_name': 'PrebuildFW_mp_vs_mpbackup_mapping.xlsx'
            })
        
        if not comparisons:
            return jsonify({'error': '無法決定比對類型'}), 400
        
        # 分別執行每個比對
        all_results = []
        output_files = []
        
        for comparison in comparisons:
            # 組合命令
            cmd = [
                'python3', 'vp_lib/cli_interface.py', 'prebuild-mapping',
                '-filter', comparison['type'],
                '-i', ','.join(comparison['files']),
                '-o', output_path
            ]
            
            logger.info(f"執行命令: {' '.join(cmd)}")
            
            # 執行命令
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=os.getcwd())
            
            if result.returncode != 0:
                logger.error(f"執行失敗: stdout={result.stdout}, stderr={result.stderr}")
                return jsonify({
                    'error': f'執行 {comparison["type"]} 失敗',
                    'stdout': result.stdout,
                    'stderr': result.stderr,
                    'command': ' '.join(cmd)
                }), 500
            
            # 查找該比對的輸出檔案
            comparison_output_files = glob.glob(os.path.join(output_path, '*.xlsx'))
            
            # 讀取結果檔案
            if comparison_output_files:
                latest_file = max(comparison_output_files, key=os.path.getctime)
                df = pd.read_excel(latest_file)
                df = df.fillna('')  # 處理 NaN 值
                
                # 加入比對類型標識
                df['comparison_type'] = comparison['type']
                
                all_results.append(df.to_dict('records'))
                output_files.append(latest_file)
        
        # 合併所有結果
        combined_data = []
        columns = []
        
        if all_results:
            # 展開所有結果
            for result_list in all_results:
                combined_data.extend(result_list)
            
            # 從第一個結果獲取欄位名稱
            if all_results[0]:
                columns = list(all_results[0][0].keys())
        
        return jsonify({
            'success': True,
            'output_files': output_files,
            'data': combined_data[:100],  # 限制返回的資料量
            'total_rows': len(combined_data),
            'columns': columns,
            'comparisons_performed': [comp['type'] for comp in comparisons]
        })
        
    except Exception as e:
        logger.error(f"執行 prebuild-mapping 失敗: {str(e)}")
        import traceback
        error_trace = traceback.format_exc()
        logger.error(error_trace)
        
        return jsonify({
            'error': str(e),
            'traceback': error_trace,
            'received_data': data if 'data' in locals() else None
        }), 500

@admin_bp.route('/api/admin/export-result', methods=['POST'])
@login_required
def export_result():
    """匯出結果為 Excel - 修正 xlsxwriter 參數錯誤"""
    try:
        data = request.json
        result_data = data.get('data', [])
        columns = data.get('columns', [])
        filename = data.get('filename', 'export.xlsx')
        
        if not result_data or not columns:
            return jsonify({'error': '沒有資料可匯出'}), 400
        
        # 建立 DataFrame
        df = pd.DataFrame(result_data, columns=columns)
        
        # 確保所有數據都是字符串或數值，避免公式錯誤
        for col in df.columns:
            if df[col].dtype == 'object':
                # 將所有文本數據轉換為字符串，並移除可能的公式字符
                df[col] = df[col].astype(str).replace({
                    'nan': '',
                    'None': '',
                    'NaT': '',
                    'null': '',
                    'NULL': ''
                })
                # 移除可能導致 Excel 解釋為公式的前綴
                df[col] = df[col].apply(lambda x: x if not str(x).startswith('=') else "'" + str(x))
        
        # 建立臨時檔案
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
            try:
                # 修正：使用正確的 xlsxwriter 參數方式
                writer = pd.ExcelWriter(tmp.name, engine='xlsxwriter')
                # 設定不要將字串轉換為公式
                writer.book.strings_to_formulas = False
                
                df.to_excel(writer, index=False, sheet_name='Result')
                
                # 獲取工作簿和工作表對象
                workbook = writer.book
                worksheet = writer.sheets['Result']
                
                # 設置表頭格式
                header_format = workbook.add_format({
                    'bold': True,
                    'text_wrap': True,
                    'valign': 'top',
                    'fg_color': '#E3F2FD',
                    'border': 1
                })
                
                # 應用格式到表頭
                for col_num, column in enumerate(df.columns):
                    worksheet.write(0, col_num, column, header_format)
                
                # 自動調整列寬
                for col_num, column in enumerate(df.columns):
                    column_width = min(max(len(str(column)), 10), 50)
                    worksheet.set_column(col_num, col_num, column_width)
                
                writer.close()
                        
            except ImportError:
                # 如果沒有 xlsxwriter，使用預設引擎
                logger.warning("xlsxwriter not available, using default engine")
                df.to_excel(tmp.name, index=False)
            except Exception as e:
                logger.error(f"xlsxwriter error: {str(e)}")
                # 回退到基本的 pandas 匯出
                df.to_excel(tmp.name, index=False)
            
            tmp_path = tmp.name
        
        # 讀取檔案並刪除臨時檔案
        try:
            with open(tmp_path, 'rb') as f:
                file_data = f.read()
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
        
        # 返回檔案
        from flask import Response
        return Response(
            file_data,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"'
            }
        )
        
    except Exception as e:
        logger.error(f"匯出結果失敗: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'error': f'匯出失敗: {str(e)}'}), 500

@admin_bp.route('/api/admin/get-download-dirs', methods=['GET'])
@login_required
def get_download_dirs():
    """獲取已下載的目錄列表 - 修復：只列出第1層子目錄"""
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
        
        # 掃描 downloads 目錄（如果存在）- 修復：只列出第1層
        if os.path.exists(download_base):
            # 添加 downloads 根目錄本身
            root_file_count = 0
            root_total_size = 0
            
            # 只掃描第1層子目錄
            try:
                for item in os.listdir(download_base):
                    item_path = os.path.join(download_base, item)
                    
                    if os.path.isfile(item_path):
                        # 計算根目錄中的檔案
                        try:
                            root_total_size += os.path.getsize(item_path)
                            root_file_count += 1
                        except:
                            pass
                    elif os.path.isdir(item_path):
                        # 這是第1層子目錄，計算其統計資訊
                        dir_file_count = 0
                        dir_total_size = 0
                        
                        # 遞迴計算這個子目錄的所有檔案
                        for root, _, files in os.walk(item_path):
                            dir_file_count += len(files)
                            for f in files:
                                try:
                                    dir_total_size += os.path.getsize(os.path.join(root, f))
                                except:
                                    pass
                        
                        # 只有當目錄有檔案時才添加
                        if dir_file_count > 0:
                            dirs.append({
                                'name': f'downloads/{item}',
                                'path': item_path,
                                'file_count': dir_file_count,
                                'size': dir_total_size,
                                'size_formatted': format_file_size(dir_total_size),
                                'type': 'download'
                            })
                        
                        # 累計到根目錄統計
                        root_file_count += dir_file_count
                        root_total_size += dir_total_size
                
                # 將 downloads 根目錄添加到列表開頭（如果有檔案）
                if root_file_count > 0:
                    dirs.insert(0, {
                        'name': 'downloads (根目錄)',
                        'path': download_base,
                        'file_count': root_file_count,
                        'size': root_total_size,
                        'size_formatted': format_file_size(root_total_size),
                        'type': 'download-root'
                    })
                    
            except Exception as e:
                logger.warning(f"掃描 downloads 目錄失敗: {str(e)}")
        
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

# 確保有這個路由
@admin_bp.route('/api/upload', methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({'error': '沒有檔案'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': '沒有選擇檔案'}), 400
        
        # 檢查檔案類型
        allowed_extensions = {'xlsx', 'xls', 'csv'}
        if not ('.' in file.filename and 
                file.filename.rsplit('.', 1)[1].lower() in allowed_extensions):
            return jsonify({'error': '不支援的檔案格式'}), 400
        
        # 儲存檔案
        filename = secure_filename(file.filename)
        upload_path = os.path.join('uploads', filename)
        
        # 確保目錄存在
        os.makedirs('uploads', exist_ok=True)
        
        file.save(upload_path)
        
        return jsonify({
            'success': True,
            'filepath': upload_path,
            'filename': filename
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 新增：瀏覽伺服器檔案的 API
@admin_bp.route('/api/admin/browse-server', methods=['POST'])
@login_required
def browse_server():
    """瀏覽伺服器檔案"""
    try:
        data = request.json
        path = data.get('path', getattr(config, 'DEFAULT_SERVER_PATH', '/home/vince_lin/ai/preMP'))
        
        from vp_lib.sftp_manager import SFTPManager
        sftp_manager = SFTPManager()
        
        try:
            sftp_manager.connect()
            
            # 列出目錄內容
            items = sftp_manager._sftp.listdir_attr(path)
            
            files = []
            folders = []
            
            for item in items:
                item_path = f"{path.rstrip('/')}/{item.filename}"
                
                if item.st_mode and (item.st_mode >> 15) == 0o040:  # 目錄
                    folders.append({
                        'name': item.filename,
                        'path': item_path,
                        'type': 'folder'
                    })
                else:  # 檔案
                    # 只顯示 Excel 和 CSV 檔案
                    if item.filename.lower().endswith(('.xlsx', '.xls', '.csv')):
                        files.append({
                            'name': item.filename,
                            'path': item_path,
                            'size': item.st_size or 0,
                            'type': 'file'
                        })
            
            return jsonify({
                'success': True,
                'path': path,
                'files': files,
                'folders': folders
            })
            
        finally:
            sftp_manager.disconnect()
        
    except Exception as e:
        logger.error(f"瀏覽伺服器失敗: {str(e)}")
        return jsonify({'error': str(e)}), 500