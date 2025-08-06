"""
功能2處理器
處理 prebuild source Excel/CSV 檔案並產生映射表
"""
import os
import sys
import pandas as pd
from typing import List, Dict, Tuple

# 加入父目錄到路徑
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

from data_models import PrebuildSource
import utils
import config

logger = utils.setup_logger(__name__)

class Feature2Processor:
    """功能2: 處理 Prebuild 來源檔案"""
    
    def __init__(self):
        self.logger = logger
        
    def load_prebuild_source(self, file_path: str) -> List[PrebuildSource]:
        """
        載入 Prebuild 來源檔案（支援 Excel 和 CSV）
        
        Args:
            file_path: 檔案路徑（.xlsx, .xls, .csv）
            
        Returns:
            PrebuildSource 物件列表
        """
        try:
            # 判斷檔案類型
            file_ext = os.path.splitext(file_path)[1].lower()
            
            if file_ext == '.csv':
                # 讀取 CSV 檔案
                self.logger.info(f"讀取 CSV 檔案: {file_path}")
                
                # 嘗試不同的編碼
                encodings = ['utf-8', 'utf-8-sig', 'big5', 'cp950', 'gbk', 'gb18030', 'latin1']
                df = None
                last_error = None
                
                for encoding in encodings:
                    try:
                        df = pd.read_csv(file_path, encoding=encoding)
                        self.logger.info(f"成功使用 {encoding} 編碼讀取 CSV")
                        break
                    except UnicodeDecodeError as e:
                        last_error = e
                        continue
                    except Exception as e:
                        # 其他錯誤，直接拋出
                        raise e
                
                if df is None:
                    # 如果所有編碼都失敗，嘗試使用 errors='ignore'
                    try:
                        df = pd.read_csv(file_path, encoding='utf-8', errors='ignore')
                        self.logger.warning(f"使用 utf-8 編碼（忽略錯誤）讀取 CSV")
                    except Exception:
                        raise ValueError(f"無法讀取 CSV 檔案: {last_error}")
                        
            elif file_ext in ['.xlsx', '.xls']:
                # 讀取 Excel 檔案
                self.logger.info(f"讀取 Excel 檔案: {file_path}")
                df = pd.read_excel(file_path)
            else:
                raise ValueError(f"不支援的檔案格式: {file_ext}。支援 .csv, .xlsx, .xls")
            
            # 轉換為 PrebuildSource 物件
            sources = []
            
            # 檢查必要欄位是否存在
            required_columns = ['Category', 'Project', 'LocalPath', 'Master_JIRA']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                self.logger.warning(f"缺少必要欄位: {missing_columns}")
            
            for idx, row in df.iterrows():
                try:
                    source = PrebuildSource(
                        module_owner=str(row.get('ModuleOwner', '')),
                        remote=str(row.get('Remote', '')),
                        category=str(row.get('Category', '')),
                        project=str(row.get('Project', '')),
                        branch=str(row.get('Branch', '')),
                        local_path=str(row.get('LocalPath', '')),
                        revision=str(row.get('Revision', '')),
                        master_jira=str(row.get('Master_JIRA', '')),
                        prebuild_src=str(row.get('PrebuildSRC', '')),
                        sftp_url=str(row.get('SftpURL', '')),
                        comment=str(row.get('Comment', ''))
                    )
                    sources.append(source)
                except Exception as e:
                    self.logger.warning(f"跳過第 {idx + 1} 筆資料: {str(e)}")
                    continue
                    
            self.logger.info(f"成功載入 {len(sources)} 筆來源資料 from {file_path}")
            return sources
            
        except Exception as e:
            self.logger.error(f"載入 Prebuild 來源檔案失敗: {str(e)}")
            raise
            
    def inner_join_sources(self, sources1: List[PrebuildSource], 
                          sources2: List[PrebuildSource]) -> List[Tuple[PrebuildSource, PrebuildSource]]:
        """
        使用 inner join 合併兩個來源
        使用 Category, Project, LocalPath, Master_JIRA 作為 key
        """
        joined = []
        
        # 建立 sources2 的索引
        sources2_dict = {}
        for source in sources2:
            key = source.key
            if key not in sources2_dict:
                sources2_dict[key] = []
            sources2_dict[key].append(source)
        
        # 進行 join
        for source1 in sources1:
            key = source1.key
            if key in sources2_dict:
                for source2 in sources2_dict[key]:
                    joined.append((source1, source2))
                    
        self.logger.info(f"Inner join 結果: {len(joined)} 筆配對")
        return joined

    def track_join_changes(self, sources1: List[PrebuildSource], 
                      sources2: List[PrebuildSource], 
                      joined_data: List[Tuple[PrebuildSource, PrebuildSource]]) -> Dict[str, List[Dict]]:
        """追蹤 join 過程中未匹配的項目"""
        changes = {
            'unmatched_file1': [],
            'unmatched_file2': [],
            'summary': {
                'file1_total': len(sources1),
                'file2_total': len(sources2),
                'matched': len(joined_data)
            }
        }
        
        # 建立已匹配的 key 集合
        matched_keys_s1 = {s1.key for s1, s2 in joined_data}
        matched_keys_s2 = {s2.key for s1, s2 in joined_data}
        
        # 找出未匹配的 source1 項目
        for source in sources1:
            if source.key not in matched_keys_s1:
                sftp_info = self.parse_sftp_info(source.sftp_url, source.master_jira)
                changes['unmatched_file1'].append({
                    'Category': source.category,
                    'Project': source.project,
                    'LocalPath': source.local_path,
                    'Master_JIRA': source.master_jira,
                    'Module': sftp_info['module'],
                    'DB_Info': sftp_info['db_info'],
                    'SftpPath': source.sftp_url
                })
        
        # 找出未匹配的 source2 項目
        for source in sources2:
            if source.key not in matched_keys_s2:
                sftp_info = self.parse_sftp_info(source.sftp_url, source.master_jira)
                changes['unmatched_file2'].append({
                    'Category': source.category,
                    'Project': source.project,
                    'LocalPath': source.local_path,
                    'Master_JIRA': source.master_jira,
                    'Module': sftp_info['module'],
                    'DB_Info': sftp_info['db_info'],
                    'SftpPath': source.sftp_url
                })
        
        return changes
        
    def clean_jira_id(self, jira_id: str) -> str:
        """
        清理 JIRA ID
        移除 '>' 符號並做 trim
        
        Args:
            jira_id: 原始 JIRA ID
            
        Returns:
            清理後的 JIRA ID
        """
        if not jira_id:
            return ''
        
        # 移除 '>' 符號並 trim
        cleaned = jira_id.replace('>', '').strip()
        return cleaned
        
    def parse_sftp_info(self, sftp_url: str, master_jira: str = '') -> Dict[str, str]:
        """解析 SFTP URL 資訊"""
        try:
            # 檢查是否為 NotFound 或空值
            sftp_url_str = str(sftp_url) if sftp_url else ''
            sftp_url_lower = sftp_url_str.lower().strip()
            
            # 處理 NotFound 情況
            if (not sftp_url or 
                pd.isna(sftp_url) or 
                sftp_url_lower in ['notfound_sftp_src_path', 'sftpnotfound', 'notfound', 'nan', '']):
                
                # 清理 JIRA ID
                cleaned_jira = self.clean_jira_id(master_jira)
                
                return {
                    'module': 'Unknown',
                    'db_info': cleaned_jira if cleaned_jira else 'Unknown',
                    'db_folder': '',
                    'db_version': '',
                    'sftp_path': 'NotFound'
                }
            
            # 進行路徑替換
            for old_path, new_path in config.PATH_REPLACEMENTS.items():
                if old_path in sftp_url:
                    sftp_url = sftp_url.replace(old_path, new_path)
            
            # 移除開頭的斜線並分割路徑
            parts = sftp_url.strip('/').split('/')
            
            # 尋找 DailyBuild 的位置
            if 'DailyBuild' in parts:
                daily_idx = parts.index('DailyBuild')
                
                # 取得 DailyBuild 後的第一個資料夾作為 Module
                if len(parts) > daily_idx + 1:
                    module = parts[daily_idx + 1]
                    
                    # 根據不同的路徑結構解析
                    if module == 'PrebuildFW':
                        # 路徑格式: /DailyBuild/PrebuildFW/dolby_ko/RDDB-xxx/...
                        if len(parts) > daily_idx + 2:
                            actual_module = parts[daily_idx + 2]  # dolby_ko
                            
                            # 提取 DB 資訊
                            if len(parts) > daily_idx + 3:
                                folder_part = parts[daily_idx + 3]
                                # 提取 RDDB 編號
                                if 'RDDB-' in folder_part:
                                    db_info = folder_part.split('_')[0]  # RDDB-xxx
                                else:
                                    db_info = folder_part
                            else:
                                db_info = ''
                            
                            # 版本資訊
                            db_version = parts[-1] if len(parts) > daily_idx + 4 else ''
                            
                            return {
                                'module': actual_module,  # dolby_ko
                                'db_info': db_info,
                                'db_folder': folder_part if len(parts) > daily_idx + 3 else '',
                                'db_version': db_version,
                                'sftp_path': sftp_url
                            }
                    else:
                        # 路徑格式: /DailyBuild/Merlin7/dolby_ko/RDDB-xxx/...
                        # 或: /DailyBuild/Mac7p/xxx/...
                        # Module 就是 DailyBuild 後的第一個資料夾 (Merlin7, Mac7p 等)
                        
                        # 提取 DB 資訊
                        db_info = ''
                        db_folder = ''
                        db_version = ''
                        
                        # 尋找 RDDB 或 DB 編號
                        for part in parts[daily_idx + 1:]:
                            if 'RDDB-' in part:
                                db_info = part.split('_')[0]
                                db_folder = part
                                break
                            elif part.startswith('DB') and any(c.isdigit() for c in part):
                                db_info = part.split('_')[0]
                                db_folder = part
                                break
                        
                        # 版本通常是最後一個部分
                        if len(parts) > 1:
                            last_part = parts[-1]
                            if any(c.isdigit() for c in last_part):
                                db_version = last_part
                        
                        return {
                            'module': module,  # Merlin7, Mac7p 等
                            'db_info': db_info,
                            'db_folder': db_folder,
                            'db_version': db_version,
                            'sftp_path': sftp_url
                        }
            
            # 如果不包含 DailyBuild，嘗試其他解析方式
            # 可能是舊格式或其他格式
            module = 'Unknown'
            db_info = ''
            db_folder = ''
            db_version = ''
            
            # 尋找 RDDB 編號
            for part in parts:
                if 'RDDB-' in part:
                    db_info = part.split('_')[0]
                    db_folder = part
                    break
            
            # 嘗試找模組名稱（可能是 PrebuildFW 後的資料夾）
            if 'PrebuildFW' in parts:
                idx = parts.index('PrebuildFW')
                if len(parts) > idx + 1:
                    module = parts[idx + 1]
            
            return {
                'module': module,
                'db_info': db_info,
                'db_folder': db_folder,
                'db_version': db_version,
                'sftp_path': sftp_url
            }
            
        except Exception as e:
            self.logger.error(f"解析 SFTP URL 失敗: {str(e)}, URL: {sftp_url}")
            
            # 如果解析失敗，使用 JIRA ID
            cleaned_jira = self.clean_jira_id(master_jira)
            
            return {
                'module': 'Unknown',
                'db_info': cleaned_jira if cleaned_jira else '',
                'db_folder': '',
                'db_version': '',
                'sftp_path': sftp_url if sftp_url else ''
            }
            
    def generate_mapping_data(self, joined_data: List[Tuple[PrebuildSource, PrebuildSource]], 
                         compare_type: str) -> List[Dict]:
        """產生映射資料"""
        result = []
        sn = 1
        
        # 解析比較類型
        if '_vs_' in compare_type:
            type1, type2 = compare_type.split('_vs_')
        else:
            type1, type2 = 'master', 'premp'  # 預設
        
        for source1, source2 in joined_data:
            # 解析兩個來源的 SFTP 資訊
            info1 = self.parse_sftp_info(source1.sftp_url, source1.master_jira)
            info2 = self.parse_sftp_info(source2.sftp_url, source2.master_jira)
            
            # 確保 Module 有值
            module = info1['module'] if info1['module'] != 'Unknown' else info2['module']
            if module == 'Unknown':
                # 嘗試從 Category 或 Project 推斷
                module = source1.category or source1.project or 'Unknown'
            
            row = {
                'SN': int(sn),  # 序號，而不是其他值
                'RootFolder': '/DailyBuild/PrebuildFW',
                'Module': module,
                'DB_Type': type1,
                'DB_Info': info1['db_info'] or source1.master_jira,  # 如果沒有 DB 資訊，使用 JIRA ID
                'DB_Folder': info1['db_folder'],
                'DB_Version': info1['db_version'],
                'SftpPath': info1['sftp_path'],
                'compare_DB_Type': type2,
                'compare_DB_Info': info2['db_info'] or source2.master_jira,
                'compare_DB_Folder': info2['db_folder'],
                'compare_DB_Version': info2['db_version'],
                'compare_SftpPath': info2['sftp_path']
            }
            result.append(row)
            sn += 1
        
        self.logger.info(f"產生 {len(result)} 筆映射資料")
        return result
        
    def process(self, input_files: str, filter_param: str = 'all', 
            output_dir: str = './output') -> str:
        """
        執行功能2處理
        
        Args:
            input_files: 輸入檔案路徑（逗號分隔）
            filter_param: 過濾參數（例如: master_vs_premp, mac7p）
            output_dir: 輸出目錄
            
        Returns:
            輸出檔案路徑
        """
        try:
            # 解析輸入檔案
            files = [f.strip() for f in input_files.split(',')]
            if len(files) != 2:
                raise ValueError("必須提供恰好 2 個輸入檔案")
            
            file1, file2 = files
            
            # 驗證檔案存在
            if not os.path.exists(file1):
                raise FileNotFoundError(f"找不到檔案: {file1}")
            if not os.path.exists(file2):
                raise FileNotFoundError(f"找不到檔案: {file2}")
            
            # 載入資料
            self.logger.info(f"載入第一個檔案: {file1}")
            sources1 = self.load_prebuild_source(file1)
            
            self.logger.info(f"載入第二個檔案: {file2}")
            sources2 = self.load_prebuild_source(file2)
            
            # 解析 filter 參數
            filter_lower = filter_param.lower() if filter_param else 'all'
            compare_type = 'master_vs_premp'  # 預設比較類型
            module_filter = None
            
            # 判斷 filter 類型
            if '_vs_' in filter_lower:
                # 這是比較類型
                compare_type = filter_lower
            elif filter_lower != 'all':
                # 這是模組過濾
                module_filter = filter_lower
            
            # 進行 inner join
            self.logger.info("執行 inner join...")
            joined_data = self.inner_join_sources(sources1, sources2)
            
            if not joined_data:
                self.logger.warning("沒有找到匹配的資料")
            
            # 追蹤變更（在過濾之前）
            self.logger.info("追蹤資料變更...")
            changes = self.track_join_changes(sources1, sources2, joined_data)
            
            # 如果有模組過濾，先過濾資料
            filtered_joined_data = joined_data
            if module_filter:
                self.logger.info(f"套用模組過濾: {module_filter}")
                filtered_data = []
                for source1, source2 in joined_data:
                    # 從 SFTP URL 解析模組
                    info1 = self.parse_sftp_info(source1.sftp_url, source1.master_jira)
                    if info1['module'].lower() == module_filter or module_filter in info1['module'].lower():
                        filtered_data.append((source1, source2))
                
                # 記錄被過濾掉的數量
                filtered_count = len(joined_data) - len(filtered_data)
                changes['filtered_by_module'] = {
                    'count': filtered_count,
                    'filter': module_filter
                }
                
                filtered_joined_data = filtered_data
                self.logger.info(f"過濾後剩餘 {len(filtered_joined_data)} 筆資料（過濾掉 {filtered_count} 筆）")
            
            # 產生映射資料
            self.logger.info("產生映射資料...")
            mapping_data = self.generate_mapping_data(filtered_joined_data, compare_type)
            
            # 決定輸出檔名
            utils.create_directory(output_dir)
            
            # 根據 filter 參數決定檔名
            if filter_param and filter_param.lower() != 'all':
                # 使用 filter 參數作為檔名的一部分
                filter_name = filter_param.lower().replace(',', '_')
                output_filename = f"PrebuildFW_{filter_name}_mapping.xlsx"
            else:
                # 使用預設檔名
                output_filename = config.DEFAULT_PREBUILD_OUTPUT  # PrebuildFW_mapping.xlsx
                
            output_file = os.path.join(output_dir, output_filename)
            
            # 輸出 Excel with 兩個頁籤
            self.logger.info("寫入 Excel 檔案...")
            
            with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
                # 第一個頁籤：映射結果
                df_mapping = pd.DataFrame(mapping_data)
                
                # 確保欄位順序正確
                expected_columns = [
                    'SN', 'RootFolder', 'Module', 'DB_Type', 'DB_Info', 
                    'DB_Folder', 'DB_Version', 'SftpPath',
                    'compare_DB_Type', 'compare_DB_Info', 
                    'compare_DB_Folder', 'compare_DB_Version', 'compare_SftpPath'
                ]
                
                # 只保留存在的欄位並按順序排列
                existing_columns = [col for col in expected_columns if col in df_mapping.columns]
                df_mapping = df_mapping[existing_columns]
                
                # 寫入第一個頁籤
                df_mapping.to_excel(writer, sheet_name='映射結果', index=False)
                
                # 調整第一個頁籤的欄寬
                worksheet1 = writer.sheets['映射結果']
                for idx, column in enumerate(df_mapping.columns):
                    max_length = max(
                        df_mapping[column].astype(str).map(len).max(),
                        len(str(column))
                    )
                    worksheet1.column_dimensions[chr(65 + idx)].width = min(max_length + 2, 50)
                
                # 第二個頁籤：變更記錄
                change_records = []
                
                # 統計摘要
                change_records.append({
                    'Type': '=== 統計摘要 ===',
                    'Count': '',
                    'File': '',
                    'Category': '',
                    'Project': '',
                    'Master_JIRA': '',
                    'Module': '',
                    'DB_Info': '',
                    'Description': ''
                })
                
                change_records.append({
                    'Type': 'File1 總筆數',
                    'Count': str(changes['summary']['file1_total']),
                    'File': os.path.basename(file1),
                    'Category': '',
                    'Project': '',
                    'Master_JIRA': '',
                    'Module': '',
                    'DB_Info': '',
                    'Description': '第一個檔案的總資料筆數'
                })
                
                change_records.append({
                    'Type': 'File2 總筆數',
                    'Count': str(changes['summary']['file2_total']),
                    'File': os.path.basename(file2),
                    'Category': '',
                    'Project': '',
                    'Master_JIRA': '',
                    'Module': '',
                    'DB_Info': '',
                    'Description': '第二個檔案的總資料筆數'
                })
                
                change_records.append({
                    'Type': '成功匹配',
                    'Count': str(changes['summary']['matched']),
                    'File': 'Both',
                    'Category': '',
                    'Project': '',
                    'Master_JIRA': '',
                    'Module': '',
                    'DB_Info': '',
                    'Description': '兩個檔案成功匹配的筆數'
                })
                
                # 如果有模組過濾
                if 'filtered_by_module' in changes:
                    change_records.append({
                        'Type': '模組過濾',
                        'Count': str(changes['filtered_by_module']['count']),
                        'File': 'Both',
                        'Category': '',
                        'Project': '',
                        'Master_JIRA': '',
                        'Module': changes['filtered_by_module']['filter'],
                        'DB_Info': '',
                        'Description': f"被模組過濾 '{changes['filtered_by_module']['filter']}' 排除的筆數"
                    })
                
                change_records.append({
                    'Type': '最終輸出',
                    'Count': str(len(mapping_data)),
                    'File': 'Result',
                    'Category': '',
                    'Project': '',
                    'Master_JIRA': '',
                    'Module': '',
                    'DB_Info': '',
                    'Description': '最終輸出到映射結果的筆數'
                })
                
                # 空行
                change_records.append({key: '' for key in change_records[0].keys()})
                
                # File1 未匹配項目
                if changes['unmatched_file1']:
                    change_records.append({
                        'Type': '=== File1 未匹配項目 ===',
                        'Count': str(len(changes['unmatched_file1'])),
                        'File': os.path.basename(file1),
                        'Category': '',
                        'Project': '',
                        'Master_JIRA': '',
                        'Module': '',
                        'DB_Info': '',
                        'Description': '在 File2 中找不到對應的項目'
                    })
                    
                    for item in changes['unmatched_file1']:
                        change_records.append({
                            'Type': '',
                            'Count': '',
                            'File': 'File1',
                            'Category': item['Category'],
                            'Project': item['Project'],
                            'Master_JIRA': item['Master_JIRA'],
                            'Module': item['Module'],
                            'DB_Info': item['DB_Info'],
                            'Description': 'No match in File2'
                        })
                
                # 空行
                if changes['unmatched_file1']:
                    change_records.append({key: '' for key in change_records[0].keys()})
                
                # File2 未匹配項目
                if changes['unmatched_file2']:
                    change_records.append({
                        'Type': '=== File2 未匹配項目 ===',
                        'Count': str(len(changes['unmatched_file2'])),
                        'File': os.path.basename(file2),
                        'Category': '',
                        'Project': '',
                        'Master_JIRA': '',
                        'Module': '',
                        'DB_Info': '',
                        'Description': '在 File1 中找不到對應的項目'
                    })
                    
                    for item in changes['unmatched_file2']:
                        change_records.append({
                            'Type': '',
                            'Count': '',
                            'File': 'File2',
                            'Category': item['Category'],
                            'Project': item['Project'],
                            'Master_JIRA': item['Master_JIRA'],
                            'Module': item['Module'],
                            'DB_Info': item['DB_Info'],
                            'Description': 'No match in File1'
                        })
                
                # 寫入變更記錄
                if change_records:
                    df_changes = pd.DataFrame(change_records)
                    df_changes.to_excel(writer, sheet_name='變更記錄', index=False)
                    
                    # 調整第二個頁籤的欄寬
                    worksheet2 = writer.sheets['變更記錄']
                    column_widths = {
                        'Type': 25,
                        'Count': 10,
                        'File': 20,
                        'Category': 15,
                        'Project': 20,
                        'Master_JIRA': 15,
                        'Module': 15,
                        'DB_Info': 15,
                        'Description': 40
                    }
                    
                    for idx, column in enumerate(df_changes.columns):
                        width = column_widths.get(column, 20)
                        worksheet2.column_dimensions[chr(65 + idx)].width = width
            
            self.logger.info(f"成功輸出: {output_file}")
            self.logger.info(f"- 映射結果: {len(mapping_data)} 筆")
            self.logger.info(f"- 匹配統計: 總共 {changes['summary']['matched']} 筆匹配")
            self.logger.info(f"- File1 未匹配: {len(changes['unmatched_file1'])} 筆")
            self.logger.info(f"- File2 未匹配: {len(changes['unmatched_file2'])} 筆")
            
            return output_file
            
        except Exception as e:
            self.logger.error(f"處理失敗: {str(e)}")
            raise