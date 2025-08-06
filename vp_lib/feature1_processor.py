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
            
            for _, row in df.iterrows():
                mapping = ChipMapping(
                    sn=row['SN'],
                    module=row['Module'],
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

    def track_changes(self, mappings: List[ChipMapping], comparison_type: str) -> Dict[str, List[Dict]]:
        """追蹤比較過程中的變更"""
        changes = {
            'added': [],        # 新增的項目（這次有但上次沒有）
            'removed': [],      # 移除的項目（上次有但這次沒有）
            'missing': [],      # 缺少配對的項目
            'matched': 0        # 成功匹配的數量
        }
        
        for mapping in mappings:
            issues = []
            missing_info = {}
            
            # 檢查各種比較類型的完整性
            if comparison_type == 'all' or comparison_type == 'master_vs_premp':
                if mapping.master_db and not mapping.premp_db:
                    missing_info = {
                        'SN': mapping.sn,
                        'Module': mapping.module,
                        'Type': 'PreMP DB',
                        'Reason': '缺少 PreMP DB',
                        'Master_DB': mapping.master_db.db_info if mapping.master_db else '',
                        'Master_Path': mapping.master_db.sftp_path if mapping.master_db else ''
                    }
                    changes['removed'].append(missing_info)
                elif not mapping.master_db and mapping.premp_db:
                    missing_info = {
                        'SN': mapping.sn,
                        'Module': mapping.module,
                        'Type': 'Master DB',
                        'Reason': '新增 Master DB（PreMP 存在但 Master 不存在）',
                        'PreMP_DB': mapping.premp_db.db_info if mapping.premp_db else '',
                        'PreMP_Path': mapping.premp_db.sftp_path if mapping.premp_db else ''
                    }
                    changes['added'].append(missing_info)
                elif mapping.master_db and mapping.premp_db:
                    changes['matched'] += 1
                    
            if comparison_type == 'all' or comparison_type == 'premp_vs_mp':
                if mapping.premp_db and not mapping.mp_db:
                    missing_info = {
                        'SN': mapping.sn,
                        'Module': mapping.module,
                        'Type': 'MP DB',
                        'Reason': '缺少 MP DB',
                        'PreMP_DB': mapping.premp_db.db_info if mapping.premp_db else '',
                        'PreMP_Path': mapping.premp_db.sftp_path if mapping.premp_db else ''
                    }
                    changes['removed'].append(missing_info)
                elif not mapping.premp_db and mapping.mp_db:
                    missing_info = {
                        'SN': mapping.sn,
                        'Module': mapping.module,
                        'Type': 'PreMP DB',
                        'Reason': '新增 PreMP DB（MP 存在但 PreMP 不存在）',
                        'MP_DB': mapping.mp_db.db_info if mapping.mp_db else '',
                        'MP_Path': mapping.mp_db.sftp_path if mapping.mp_db else ''
                    }
                    changes['added'].append(missing_info)
                elif mapping.premp_db and mapping.mp_db:
                    changes['matched'] += 1
                    
            if comparison_type == 'all' or comparison_type == 'mp_vs_mpbackup':
                if mapping.mp_db and not mapping.mpbackup_db:
                    missing_info = {
                        'SN': mapping.sn,
                        'Module': mapping.module,
                        'Type': 'MP Backup DB',
                        'Reason': '缺少 MP Backup DB',
                        'MP_DB': mapping.mp_db.db_info if mapping.mp_db else '',
                        'MP_Path': mapping.mp_db.sftp_path if mapping.mp_db else ''
                    }
                    changes['removed'].append(missing_info)
                elif not mapping.mp_db and mapping.mpbackup_db:
                    missing_info = {
                        'SN': mapping.sn,
                        'Module': mapping.module,
                        'Type': 'MP DB',
                        'Reason': '新增 MP DB（MP Backup 存在但 MP 不存在）',
                        'MPBackup_DB': mapping.mpbackup_db.db_info if mapping.mpbackup_db else '',
                        'MPBackup_Path': mapping.mpbackup_db.sftp_path if mapping.mpbackup_db else ''
                    }
                    changes['added'].append(missing_info)
                elif mapping.mp_db and mapping.mpbackup_db:
                    changes['matched'] += 1
            
            # 記錄完全缺失的項目
            if not any([mapping.master_db, mapping.premp_db, mapping.mp_db, mapping.mpbackup_db]):
                changes['missing'].append({
                    'SN': mapping.sn,
                    'Module': mapping.module,
                    'Type': 'All',
                    'Reason': '所有 DB 資訊都缺失',
                    'Master_DB': '',
                    'PreMP_DB': '',
                    'MP_DB': '',
                    'MPBackup_DB': ''
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
                        row['SN'] = sn
                        result.append(row)
                        sn += 1
                
                # premp vs mp
                if mapping.premp_db and mapping.mp_db:
                    row = mapping.to_comparison_dict('premp', 'mp')
                    if row:
                        row['SN'] = sn
                        result.append(row)
                        sn += 1
                
                # mp vs mpbackup
                if mapping.mp_db and mapping.mpbackup_db:
                    row = mapping.to_comparison_dict('mp', 'mpbackup')
                    if row:
                        row['SN'] = sn
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
                            result.append(row)
                            sn += 1
            elif comparison_type == 'premp_vs_mp':
                for mapping in mappings:
                    if mapping.premp_db and mapping.mp_db:
                        row = mapping.to_comparison_dict('premp', 'mp')
                        if row:
                            row['SN'] = sn
                            result.append(row)
                            sn += 1
            elif comparison_type == 'mp_vs_mpbackup':
                for mapping in mappings:
                    if mapping.mp_db and mapping.mpbackup_db:
                        row = mapping.to_comparison_dict('mp', 'mpbackup')
                        if row:
                            row['SN'] = sn
                            result.append(row)
                            sn += 1
                        
        self.logger.info(f"產生 {len(result)} 筆比較資料")
        return result
        
    def process(self, input_file: str, db_param: str = 'all', 
                filter_param: str = 'all', output_dir: str = './output') -> str:
        """
        執行功能1處理
        
        Args:
            input_file: 輸入檔案路徑
            db_param: DB參數
            filter_param: 過濾參數
            output_dir: 輸出目錄
            
        Returns:
            輸出檔案路徑
        """
        try:
            # 載入資料
            self.logger.info("載入映射表...")
            mappings = self.load_mapping_table(input_file)
            
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
            
            # 產生比較資料
            self.logger.info(f"產生比較資料 (類型: {comparison_type})...")
            comparison_data = self.generate_comparison_data(filtered_mappings, comparison_type)

            # 在產生比較資料之前追蹤變更
            self.logger.info("追蹤資料變更...")
            changes = self.track_changes(filtered_mappings, comparison_type)

            # 產生比較資料
            self.logger.info(f"產生比較資料 (類型: {comparison_type})...")
            comparison_data = self.generate_comparison_data(filtered_mappings, comparison_type)

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
                df_comparison.to_excel(writer, sheet_name='比較結果', index=False)
                
                # 第二個頁籤：變更記錄
                all_changes = []
                
                # 總覽資訊
                summary = {
                    'SN': '',
                    'Module': '=== 總覽 ===',
                    'Type': f"成功匹配: {changes['matched']} 筆",
                    'Reason': f"新增: {len(changes['added'])} 筆, 移除: {len(changes['removed'])} 筆, 完全缺失: {len(changes.get('missing', []))} 筆",
                    'DB_Info': '',
                    'Path': ''
                }
                all_changes.append(summary)
                
                # 空行
                all_changes.append({key: '' for key in summary.keys()})
                
                # 新增的項目
                if changes['added']:
                    all_changes.append({
                        'SN': '',
                        'Module': '=== 新增項目 ===',
                        'Type': '',
                        'Reason': '',
                        'DB_Info': '',
                        'Path': ''
                    })
                    for item in changes['added']:
                        all_changes.append({
                            'SN': item.get('SN', ''),
                            'Module': item.get('Module', ''),
                            'Type': item.get('Type', ''),
                            'Reason': item.get('Reason', ''),
                            'DB_Info': item.get('PreMP_DB', '') or item.get('MP_DB', '') or item.get('MPBackup_DB', ''),
                            'Path': item.get('PreMP_Path', '') or item.get('MP_Path', '') or item.get('MPBackup_Path', '')
                        })
                
                # 空行
                if changes['added']:
                    all_changes.append({key: '' for key in summary.keys()})
                
                # 移除的項目
                if changes['removed']:
                    all_changes.append({
                        'SN': '',
                        'Module': '=== 移除項目 ===',
                        'Type': '',
                        'Reason': '',
                        'DB_Info': '',
                        'Path': ''
                    })
                    for item in changes['removed']:
                        all_changes.append({
                            'SN': item.get('SN', ''),
                            'Module': item.get('Module', ''),
                            'Type': item.get('Type', ''),
                            'Reason': item.get('Reason', ''),
                            'DB_Info': item.get('Master_DB', '') or item.get('PreMP_DB', '') or item.get('MP_DB', ''),
                            'Path': item.get('Master_Path', '') or item.get('PreMP_Path', '') or item.get('MP_Path', '')
                        })
                
                # 空行
                if changes['removed']:
                    all_changes.append({key: '' for key in summary.keys()})
                
                # 完全缺失的項目
                if changes.get('missing', []):
                    all_changes.append({
                        'SN': '',
                        'Module': '=== 完全缺失 ===',
                        'Type': '',
                        'Reason': '',
                        'DB_Info': '',
                        'Path': ''
                    })
                    for item in changes['missing']:
                        all_changes.append({
                            'SN': item.get('SN', ''),
                            'Module': item.get('Module', ''),
                            'Type': item.get('Type', ''),
                            'Reason': item.get('Reason', ''),
                            'DB_Info': '',
                            'Path': ''
                        })
                
                # 寫入變更記錄
                if len(all_changes) > 1:
                    df_changes = pd.DataFrame(all_changes)
                    df_changes.to_excel(writer, sheet_name='變更記錄', index=False)
                else:
                    # 即使沒有變更也建立空白頁籤
                    df_empty = pd.DataFrame({'說明': ['沒有檢測到變更']})
                    df_empty.to_excel(writer, sheet_name='變更記錄', index=False)

            self.logger.info(f"成功輸出 {len(comparison_data)} 筆資料到: {output_file}")
            self.logger.info(f"記錄了 {len(changes['added'])} 筆新增，{len(changes['removed'])} 筆移除，{len(changes.get('missing', []))} 筆完全缺失")
            return output_file
            
        except Exception as e:
            self.logger.error(f"處理失敗: {str(e)}")
            raise