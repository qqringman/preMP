"""
功能1處理器
處理 all_chip_mapping_table.xlsx 並產生 DailyBuild_mapping.xlsx
"""
import os
import sys
import pandas as pd
from typing import List, Dict, Optional, Tuple
import re

# 加入父目錄到路徑
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

from data_models import ChipMapping, DBInfo
from sftp_manager import SFTPManager
import utils
import config

logger = utils.setup_logger(__name__)

class Feature1Processor:
    """功能1: 處理晶片映射表"""
    
    def __init__(self):
        self.logger = logger
        self.sftp_manager = SFTPManager()
        
    def load_mapping_table(self, file_path: str) -> List[ChipMapping]:
        """載入映射表（支援 Excel 和 CSV）"""
        try:
            # 判斷檔案類型
            file_ext = os.path.splitext(file_path)[1].lower()
            
            if file_ext == '.csv':
                # 讀取 CSV
                self.logger.info(f"讀取 CSV 檔案: {file_path}")
                df = pd.read_csv(file_path, encoding='utf-8')
            elif file_ext in ['.xlsx', '.xls']:
                # 讀取 Excel
                self.logger.info(f"讀取 Excel 檔案: {file_path}")
                df = pd.read_excel(file_path)
            else:
                raise ValueError(f"不支援的檔案格式: {file_ext}")
            
            mappings = []
            
            for idx, row in df.iterrows():
                mapping = ChipMapping(
                    sn=str(idx + 1),  # 使用行號作為 SN
                    module=str(row.get('Module', '')),
                    master_db=DBInfo(
                        db_type='master',
                        db_info=row.get('DB_Info', ''),
                        db_folder=row.get('DB_Folder', ''),
                        sftp_path=row.get('SftpPath', '')
                    ) if pd.notna(row.get('DB_Info')) else None,
                    premp_db=DBInfo(
                        db_type='premp',
                        db_info=row.get('premp_DB_Info', ''),
                        db_folder=row.get('premp_DB_Folder', ''),
                        sftp_path=row.get('premp_SftpPath', '')
                    ) if pd.notna(row.get('premp_DB_Info')) else None,
                    mp_db=DBInfo(
                        db_type='mp',
                        db_info=row.get('mp_DB_Info', ''),
                        db_folder=row.get('mp_DB_Folder', ''),
                        sftp_path=row.get('mp_SftpPath', '')
                    ) if pd.notna(row.get('mp_DB_Info')) else None,
                    mpbackup_db=DBInfo(
                        db_type='mpbackup',
                        db_info=row.get('mpbackup_DB_Info', ''),
                        db_folder=row.get('mpbackup_DB_Folder', ''),
                        sftp_path=row.get('mpbackup_SftpPath', '')
                    ) if pd.notna(row.get('mpbackup_DB_Info')) else None
                )
                mappings.append(mapping)
                
            self.logger.info(f"載入 {len(mappings)} 筆映射資料")
            return mappings
            
        except Exception as e:
            self.logger.error(f"載入映射表失敗: {str(e)}")
            raise
            
    def process_db_parameter(self, db_param: str) -> Dict[str, Dict]:
        """
        處理 -db 參數
        
        Args:
            db_param: DB參數字串 (例如: "DB2302#196,DB2686#168")
            
        Returns:
            字典 {db_info: {folder, version, path}}
        """
        if not db_param or db_param == 'all':
            return {}
            
        db_dict = {}
        db_items = db_param.split(',')
        
        for item in db_items:
            item = item.strip()
            if '#' in item:
                db_number, version = item.split('#')
                db_dict[db_number] = {
                    'version_prefix': version
                }
                
        return db_dict
        
    def parse_filter_param(self, filter_param: str) -> Tuple[List[str], str]:
        """
        解析 filter 參數
        
        Returns:
            (module_filters, comparison_filter)
        """
        if not filter_param or filter_param == 'all':
            return [], 'all'
            
        filters = filter_param.lower().split(',')
        module_filters = []
        comparison_filter = 'all'
        
        for f in filters:
            f = f.strip()
            if '_vs_' in f:
                # 這是比較類型的過濾
                comparison_filter = f
            else:
                # 這是模組過濾
                module_filters.append(f)
                
        return module_filters, comparison_filter
        
    def apply_filters(self, mappings: List[ChipMapping], filter_param: str) -> Tuple[List[ChipMapping], str]:
        """
        套用過濾條件
        
        Returns:
            (filtered_mappings, comparison_type)
        """
        if not filter_param or filter_param == 'all':
            return mappings, 'all'
            
        module_filters, comparison_filter = self.parse_filter_param(filter_param)
        
        # 先套用模組過濾
        filtered = mappings
        if module_filters:
            filtered = []
            for mapping in mappings:
                module_lower = mapping.module.lower()
                # 檢查是否符合任一模組過濾條件
                for mf in module_filters:
                    if mf in module_lower:
                        filtered.append(mapping)
                        break
            
            self.logger.info(f"模組過濾後剩餘 {len(filtered)} 筆資料")
        
        return filtered, comparison_filter
        
    def update_version_info(self, mappings: List[ChipMapping], db_dict: Dict) -> None:
        """更新版本資訊"""
        try:
            self.sftp_manager.connect()
            
            for mapping in mappings:
                # 更新各個 DB 的版本資訊
                for db_type in ['master', 'premp', 'mp', 'mpbackup']:
                    db_info = mapping.get_db_by_type(db_type)
                    if db_info and db_info.sftp_path:
                        # 檢查是否有指定版本
                        if db_info.db_info in db_dict:
                            version_info = db_dict[db_info.db_info]
                            db_folder, db_version, full_path = self.sftp_manager.get_specific_version(
                                db_info.sftp_path, f"{db_info.db_info}#{version_info['version_prefix']}"
                            )
                        else:
                            # 取得最新版本（版號最大的）
                            db_folder, db_version, full_path = self.sftp_manager.get_latest_version(
                                db_info.sftp_path
                            )
                        
                        # 更新資訊
                        if db_folder:
                            db_info.db_folder = db_folder
                        if db_version:
                            db_info.db_version = db_version
                        if full_path:
                            db_info.sftp_path = full_path
                        
                        self.logger.debug(f"更新 {mapping.module} {db_type}: {db_version}")
                        
        except Exception as e:
            self.logger.error(f"更新版本資訊失敗: {str(e)}")
        finally:
            self.sftp_manager.disconnect()

    def track_changes(self, mappings: List[ChipMapping], filtered_mappings: List[ChipMapping], 
                 comparison_type: str) -> Dict[str, List[Dict]]:
        """
        追蹤比對過程中的變更
        
        Args:
            mappings: 原始映射列表
            filtered_mappings: 過濾後的映射列表
            comparison_type: 比較類型
            
        Returns:
            包含變更記錄的字典
        """
        changes = {
            'filtered_out': [],  # 被過濾掉的項目
            'missing_pair': [],  # 缺少配對的項目
            'summary': {
                'total_original': len(mappings),
                'total_filtered': len(filtered_mappings),
                'total_compared': 0
            }
        }
        
        # 找出被過濾掉的項目
        filtered_sns = {m.sn for m in filtered_mappings}
        for mapping in mappings:
            if mapping.sn not in filtered_sns:
                changes['filtered_out'].append({
                    'SN': mapping.sn,
                    'Module': mapping.module,
                    'Reason': '被過濾條件排除',
                    'Master_DB': mapping.master_db.db_info if mapping.master_db else '',
                    'PreMP_DB': mapping.premp_db.db_info if mapping.premp_db else '',
                    'MP_DB': mapping.mp_db.db_info if mapping.mp_db else '',
                    'MPBackup_DB': mapping.mpbackup_db.db_info if mapping.mpbackup_db else ''
                })
        
        # 找出缺少配對的項目
        for mapping in filtered_mappings:
            missing_pairs = []
            
            if comparison_type in ['all', 'master_vs_premp']:
                if bool(mapping.master_db) != bool(mapping.premp_db):
                    if mapping.master_db and not mapping.premp_db:
                        missing_pairs.append('缺少 PreMP')
                    elif not mapping.master_db and mapping.premp_db:
                        missing_pairs.append('缺少 Master')
                        
            if comparison_type in ['all', 'premp_vs_mp']:
                if bool(mapping.premp_db) != bool(mapping.mp_db):
                    if mapping.premp_db and not mapping.mp_db:
                        missing_pairs.append('缺少 MP')
                    elif not mapping.premp_db and mapping.mp_db:
                        missing_pairs.append('缺少 PreMP')
                        
            if comparison_type in ['all', 'mp_vs_mpbackup']:
                if bool(mapping.mp_db) != bool(mapping.mpbackup_db):
                    if mapping.mp_db and not mapping.mpbackup_db:
                        missing_pairs.append('缺少 MP Backup')
                    elif not mapping.mp_db and mapping.mpbackup_db:
                        missing_pairs.append('缺少 MP')
            
            if missing_pairs:
                changes['missing_pair'].append({
                    'SN': mapping.sn,
                    'Module': mapping.module,
                    'Missing': ', '.join(missing_pairs),
                    'Master_DB': mapping.master_db.db_info if mapping.master_db else '',
                    'PreMP_DB': mapping.premp_db.db_info if mapping.premp_db else '',
                    'MP_DB': mapping.mp_db.db_info if mapping.mp_db else '',
                    'MPBackup_DB': mapping.mpbackup_db.db_info if mapping.mpbackup_db else ''
                })
        
        return changes
            
    def generate_comparison_data(self, mappings: List[ChipMapping], comparison_type: str) -> List[Dict]:
        """
        產生比較資料
        
        Args:
            mappings: 映射列表
            comparison_type: 比較類型 (all, master_vs_premp, premp_vs_mp, mp_vs_mpbackup)
        """
        result = []
        sn = 1
        
        if comparison_type == 'all':
            # 產生所有比較組合
            for mapping in mappings:
                # master vs premp
                if mapping.master_db and mapping.premp_db:
                    row = mapping.to_comparison_dict('master', 'premp')
                    if row:
                        # 確保所有必要欄位都有值
                        row['SN'] = sn
                        row['RootFolder'] = row.get('RootFolder', '/DailyBuild')
                        row['Module'] = row.get('Module', '')
                        row['DB_Type'] = row.get('DB_Type', 'master')
                        row['DB_Info'] = row.get('DB_Info', '')
                        row['DB_Folder'] = row.get('DB_Folder', '')
                        row['DB_Version'] = row.get('DB_Version', '')
                        row['SftpPath'] = row.get('SftpPath', '')
                        row['compare_DB_Type'] = row.get('compare_DB_Type', 'premp')
                        row['compare_DB_Info'] = row.get('compare_DB_Info', '')
                        row['compare_DB_Folder'] = row.get('compare_DB_Folder', '')
                        row['compare_DB_Version'] = row.get('compare_DB_Version', '')
                        row['compare_SftpPath'] = row.get('compare_SftpPath', '')
                        
                        result.append(row)
                        sn += 1
                
                # premp vs mp
                if mapping.premp_db and mapping.mp_db:
                    row = mapping.to_comparison_dict('premp', 'mp')
                    if row:
                        row['SN'] = sn
                        row['RootFolder'] = row.get('RootFolder', '/DailyBuild')
                        row['Module'] = row.get('Module', '')
                        row['DB_Type'] = row.get('DB_Type', 'premp')
                        row['DB_Info'] = row.get('DB_Info', '')
                        row['DB_Folder'] = row.get('DB_Folder', '')
                        row['DB_Version'] = row.get('DB_Version', '')
                        row['SftpPath'] = row.get('SftpPath', '')
                        row['compare_DB_Type'] = row.get('compare_DB_Type', 'mp')
                        row['compare_DB_Info'] = row.get('compare_DB_Info', '')
                        row['compare_DB_Folder'] = row.get('compare_DB_Folder', '')
                        row['compare_DB_Version'] = row.get('compare_DB_Version', '')
                        row['compare_SftpPath'] = row.get('compare_SftpPath', '')
                        
                        result.append(row)
                        sn += 1
                
                # mp vs mpbackup
                if mapping.mp_db and mapping.mpbackup_db:
                    row = mapping.to_comparison_dict('mp', 'mpbackup')
                    if row:
                        row['SN'] = sn
                        row['RootFolder'] = row.get('RootFolder', '/DailyBuild')
                        row['Module'] = row.get('Module', '')
                        row['DB_Type'] = row.get('DB_Type', 'mp')
                        row['DB_Info'] = row.get('DB_Info', '')
                        row['DB_Folder'] = row.get('DB_Folder', '')
                        row['DB_Version'] = row.get('DB_Version', '')
                        row['SftpPath'] = row.get('SftpPath', '')
                        row['compare_DB_Type'] = row.get('compare_DB_Type', 'mpbackup')
                        row['compare_DB_Info'] = row.get('compare_DB_Info', '')
                        row['compare_DB_Folder'] = row.get('compare_DB_Folder', '')
                        row['compare_DB_Version'] = row.get('compare_DB_Version', '')
                        row['compare_SftpPath'] = row.get('compare_SftpPath', '')
                        
                        result.append(row)
                        sn += 1
        else:
            # 根據特定 comparison_type 產生比較
            if comparison_type == 'master_vs_premp':
                for mapping in mappings:
                    if mapping.master_db and mapping.premp_db:
                        row = mapping.to_comparison_dict('master', 'premp')
                        if row:
                            row['SN'] = sn
                            row['RootFolder'] = row.get('RootFolder', '/DailyBuild')
                            row['Module'] = row.get('Module', '')
                            row['DB_Type'] = row.get('DB_Type', 'master')
                            row['DB_Info'] = row.get('DB_Info', '')
                            row['DB_Folder'] = row.get('DB_Folder', '')
                            row['DB_Version'] = row.get('DB_Version', '')
                            row['SftpPath'] = row.get('SftpPath', '')
                            row['compare_DB_Type'] = row.get('compare_DB_Type', 'premp')
                            row['compare_DB_Info'] = row.get('compare_DB_Info', '')
                            row['compare_DB_Folder'] = row.get('compare_DB_Folder', '')
                            row['compare_DB_Version'] = row.get('compare_DB_Version', '')
                            row['compare_SftpPath'] = row.get('compare_SftpPath', '')
                            
                            result.append(row)
                            sn += 1
                            
            elif comparison_type == 'premp_vs_mp':
                for mapping in mappings:
                    if mapping.premp_db and mapping.mp_db:
                        row = mapping.to_comparison_dict('premp', 'mp')
                        if row:
                            row['SN'] = sn
                            row['RootFolder'] = row.get('RootFolder', '/DailyBuild')
                            row['Module'] = row.get('Module', '')
                            row['DB_Type'] = row.get('DB_Type', 'premp')
                            row['DB_Info'] = row.get('DB_Info', '')
                            row['DB_Folder'] = row.get('DB_Folder', '')
                            row['DB_Version'] = row.get('DB_Version', '')
                            row['SftpPath'] = row.get('SftpPath', '')
                            row['compare_DB_Type'] = row.get('compare_DB_Type', 'mp')
                            row['compare_DB_Info'] = row.get('compare_DB_Info', '')
                            row['compare_DB_Folder'] = row.get('compare_DB_Folder', '')
                            row['compare_DB_Version'] = row.get('compare_DB_Version', '')
                            row['compare_SftpPath'] = row.get('compare_SftpPath', '')
                            
                            result.append(row)
                            sn += 1
                            
            elif comparison_type == 'mp_vs_mpbackup':
                for mapping in mappings:
                    if mapping.mp_db and mapping.mpbackup_db:
                        row = mapping.to_comparison_dict('mp', 'mpbackup')
                        if row:
                            row['SN'] = sn
                            row['RootFolder'] = row.get('RootFolder', '/DailyBuild')
                            row['Module'] = row.get('Module', '')
                            row['DB_Type'] = row.get('DB_Type', 'mp')
                            row['DB_Info'] = row.get('DB_Info', '')
                            row['DB_Folder'] = row.get('DB_Folder', '')
                            row['DB_Version'] = row.get('DB_Version', '')
                            row['SftpPath'] = row.get('SftpPath', '')
                            row['compare_DB_Type'] = row.get('compare_DB_Type', 'mpbackup')
                            row['compare_DB_Info'] = row.get('compare_DB_Info', '')
                            row['compare_DB_Folder'] = row.get('compare_DB_Folder', '')
                            row['compare_DB_Version'] = row.get('compare_DB_Version', '')
                            row['compare_SftpPath'] = row.get('compare_SftpPath', '')
                            
                            result.append(row)
                            sn += 1
        
        # 最終檢查：確保所有資料都有正確的欄位
        required_fields = [
            'SN', 'RootFolder', 'Module', 'DB_Type', 'DB_Info', 
            'DB_Folder', 'DB_Version', 'SftpPath',
            'compare_DB_Type', 'compare_DB_Info', 
            'compare_DB_Folder', 'compare_DB_Version', 'compare_SftpPath'
        ]
        
        for row in result:
            for field in required_fields:
                if field not in row or row[field] is None:
                    row[field] = ''
                # 將所有值轉為字串，除了 SN
                if field != 'SN':
                    row[field] = str(row[field])
                            
        self.logger.info(f"產生 {len(result)} 筆比較資料")
        return result
        
    def process(self, input_file: str, db_param: str = 'all', 
            filter_param: str = 'all', output_dir: str = './output') -> str:
        """執行功能1處理"""
        try:
            # 載入資料
            self.logger.info("載入映射表...")
            mappings = self.load_mapping_table(input_file)
            original_count = len(mappings)
            
            # 處理 DB 參數
            db_dict = self.process_db_parameter(db_param)
            if db_dict:
                self.logger.info(f"指定版本: {db_dict}")
            else:
                self.logger.info("將從 SFTP 取得最新版本")
            
            # 套用過濾並取得比較類型
            self.logger.info(f"套用過濾條件: {filter_param}")
            filtered_mappings, comparison_type = self.apply_filters(mappings, filter_param)
            
            if not filtered_mappings:
                self.logger.warning("過濾後沒有資料")
                raise ValueError("過濾條件沒有匹配到任何資料")
            
            self.logger.info(f"過濾後 {len(filtered_mappings)} 筆資料，比較類型: {comparison_type}")
            
            # 更新版本資訊
            self.logger.info("從 SFTP 取得版本資訊...")
            self.update_version_info(filtered_mappings, db_dict)
            
            # 追蹤變更
            self.logger.info("追蹤資料變更...")
            changes = self.track_changes(mappings, filtered_mappings, comparison_type)
            
            # 產生比較資料
            self.logger.info(f"產生比較資料 (類型: {comparison_type})...")
            comparison_data = self.generate_comparison_data(filtered_mappings, comparison_type)
            
            # 更新統計
            changes['summary']['total_compared'] = len(comparison_data)
            
            if not comparison_data:
                self.logger.warning("沒有產生任何比較資料")
                raise ValueError("無法產生比較資料，請檢查資料是否完整")
            
            # 輸出 Excel with 兩個頁籤
            utils.create_directory(output_dir)
            output_file = f"{output_dir}/{config.DEFAULT_DAILYBUILD_OUTPUT}"
            
            # 使用 ExcelWriter 寫入多個頁籤
            with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
                # 第一個頁籤：比較結果
                df_comparison = pd.DataFrame(comparison_data)
                
                # 確保欄位順序正確
                expected_columns = [
                    'SN', 'RootFolder', 'Module', 'DB_Type', 'DB_Info', 
                    'DB_Folder', 'DB_Version', 'SftpPath',
                    'compare_DB_Type', 'compare_DB_Info', 
                    'compare_DB_Folder', 'compare_DB_Version', 'compare_SftpPath'
                ]
                existing_columns = [col for col in expected_columns if col in df_comparison.columns]
                df_comparison = df_comparison[existing_columns]
                
                df_comparison.to_excel(writer, sheet_name='比較結果', index=False)
                
                # 第二個頁籤：變更記錄
                change_records = []
                
                # 統計摘要
                change_records.append({
                    'Type': '統計摘要',
                    'Count': '',
                    'Description': '',
                    'SN': '',
                    'Module': '',
                    'Details': ''
                })
                change_records.append({
                    'Type': '原始資料筆數',
                    'Count': str(changes['summary']['total_original']),
                    'Description': '載入的原始資料總數',
                    'SN': '',
                    'Module': '',
                    'Details': ''
                })
                change_records.append({
                    'Type': '過濾後筆數',
                    'Count': str(changes['summary']['total_filtered']),
                    'Description': '套用過濾條件後的資料數',
                    'SN': '',
                    'Module': '',
                    'Details': ''
                })
                change_records.append({
                    'Type': '比較結果筆數',
                    'Count': str(changes['summary']['total_compared']),
                    'Description': '實際產生的比較資料數',
                    'SN': '',
                    'Module': '',
                    'Details': ''
                })
                
                # 空行
                change_records.append({key: '' for key in change_records[0].keys()})
                
                # 被過濾掉的項目
                if changes['filtered_out']:
                    change_records.append({
                        'Type': '被過濾項目',
                        'Count': str(len(changes['filtered_out'])),
                        'Description': '被過濾條件排除的項目',
                        'SN': '',
                        'Module': '',
                        'Details': ''
                    })
                    for item in changes['filtered_out']:
                        change_records.append({
                            'Type': '',
                            'Count': '',
                            'Description': item['Reason'],
                            'SN': item['SN'],
                            'Module': item['Module'],
                            'Details': f"Master:{item['Master_DB']}, PreMP:{item['PreMP_DB']}, MP:{item['MP_DB']}, MPBackup:{item['MPBackup_DB']}"
                        })
                
                # 空行
                if changes['filtered_out']:
                    change_records.append({key: '' for key in change_records[0].keys()})
                
                # 缺少配對的項目
                if changes['missing_pair']:
                    change_records.append({
                        'Type': '缺少配對',
                        'Count': str(len(changes['missing_pair'])),
                        'Description': '缺少配對無法比較的項目',
                        'SN': '',
                        'Module': '',
                        'Details': ''
                    })
                    for item in changes['missing_pair']:
                        change_records.append({
                            'Type': '',
                            'Count': '',
                            'Description': item['Missing'],
                            'SN': item['SN'],
                            'Module': item['Module'],
                            'Details': f"Master:{item['Master_DB']}, PreMP:{item['PreMP_DB']}, MP:{item['MP_DB']}, MPBackup:{item['MPBackup_DB']}"
                        })
                
                # 寫入變更記錄
                if change_records:
                    df_changes = pd.DataFrame(change_records)
                    df_changes.to_excel(writer, sheet_name='變更記錄', index=False)
                    
                    # 調整欄寬
                    worksheet = writer.sheets['變更記錄']
                    for idx, column in enumerate(df_changes.columns):
                        worksheet.column_dimensions[chr(65 + idx)].width = 20
            
            self.logger.info(f"成功輸出 {len(comparison_data)} 筆資料到: {output_file}")
            self.logger.info(f"變更記錄: 被過濾 {len(changes['filtered_out'])} 筆, 缺少配對 {len(changes['missing_pair'])} 筆")
            
            return output_file
            
        except Exception as e:
            self.logger.error(f"處理失敗: {str(e)}")
            raise