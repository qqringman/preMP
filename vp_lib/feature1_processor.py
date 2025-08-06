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
            
            if not comparison_data:
                self.logger.warning("沒有產生任何比較資料")
                raise ValueError("無法產生比較資料，請檢查資料是否完整")
            
            # 輸出 Excel
            utils.create_directory(output_dir)
            output_file = f"{output_dir}/{config.DEFAULT_DAILYBUILD_OUTPUT}"
            
            df = pd.DataFrame(comparison_data)
            df.to_excel(output_file, index=False)
            
            self.logger.info(f"成功輸出 {len(comparison_data)} 筆資料到: {output_file}")
            return output_file
            
        except Exception as e:
            self.logger.error(f"處理失敗: {str(e)}")
            raise