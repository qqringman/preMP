"""
功能1處理器
處理 all_chip_mapping_table.xlsx 並產生 DailyBuild_mapping.xlsx
"""
import sys
import os
import pandas as pd
from typing import List, Dict, Optional
from data_models import ChipMapping, DBInfo
from sftp_manager import SFTPManager

# 將上層目錄加入 Python 路徑
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
                        db_info=row['DB_Info'],
                        db_folder=row['DB_Folder'],
                        sftp_path=row['SftpPath']
                    ) if pd.notna(row.get('DB_Info')) else None,
                    premp_db=DBInfo(
                        db_type='premp',
                        db_info=row['premp_DB_Info'],
                        db_folder=row['premp_DB_Folder'],
                        sftp_path=row['premp_SftpPath']
                    ) if pd.notna(row.get('premp_DB_Info')) else None,
                    mp_db=DBInfo(
                        db_type='mp',
                        db_info=row['mp_DB_Info'],
                        db_folder=row['mp_DB_Folder'],
                        sftp_path=row['mp_SftpPath']
                    ) if pd.notna(row.get('mp_DB_Info')) else None,
                    mpbackup_db=DBInfo(
                        db_type='mpbackup',
                        db_info=row['mpbackup_DB_Info'],
                        db_folder=row['mpbackup_DB_Folder'],
                        sftp_path=row['mpbackup_SftpPath']
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
                # 這裡需要從實際 SFTP 路徑解析
                # 範例路徑: /DailyBuild/Merlin7/DB2302_Merlin7_32Bit_FW_Android14_Ref_Plus_GoogleGMS/196_all_202508060105
                db_dict[db_number] = {
                    'version_prefix': version
                }
                
        return db_dict
        
    def apply_filters(self, mappings: List[ChipMapping], filter_param: str) -> List[ChipMapping]:
        """套用過濾條件"""
        if not filter_param or filter_param == 'all':
            return mappings
            
        filtered = []
        filters = filter_param.lower().split(',')
        
        for mapping in mappings:
            # 檢查模組過濾
            module_lower = mapping.module.lower()
            if any(f in module_lower for f in filters):
                filtered.append(mapping)
                continue
                
        return filtered
        
    def update_version_info(self, mappings: List[ChipMapping], db_dict: Dict) -> None:
        """更新版本資訊"""
        try:
            self.sftp_manager.connect()
            
            for mapping in mappings:
                # 更新各個 DB 的版本資訊
                for db_type in ['master', 'premp', 'mp', 'mpbackup']:
                    db_info = mapping.get_db_by_type(db_type)
                    if db_info:
                        # 檢查是否有指定版本
                        if db_info.db_info in db_dict:
                            version_info = db_dict[db_info.db_info]
                            db_folder, db_version, full_path = self.sftp_manager.get_specific_version(
                                db_info.sftp_path, f"{db_info.db_info}#{version_info['version_prefix']}"
                            )
                        else:
                            # 取得最新版本
                            db_folder, db_version, full_path = self.sftp_manager.get_latest_version(
                                db_info.sftp_path
                            )
                        
                        # 更新資訊
                        db_info.db_folder = db_folder
                        db_info.db_version = db_version
                        db_info.sftp_path = full_path
                        
        finally:
            self.sftp_manager.disconnect()
            
    def generate_comparison_data(self, mappings: List[ChipMapping], filter_type: str) -> List[Dict]:
        """產生比較資料"""
        result = []
        sn = 1
        
        if filter_type == 'all':
            # 產生所有比較組合
            for mapping in mappings:
                for db_type1, db_type2 in config.DB_TYPE_PAIRS:
                    row = mapping.to_comparison_dict(db_type1, db_type2)
                    if row:
                        row['SN'] = sn
                        result.append(row)
                        sn += 1
        else:
            # 根據 filter_type 產生特定比較
            if '_vs_' in filter_type:
                db_type1, db_type2 = filter_type.split('_vs_')
                for mapping in mappings:
                    row = mapping.to_comparison_dict(db_type1, db_type2)
                    if row:
                        row['SN'] = sn
                        result.append(row)
                        sn += 1
                        
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
            
            # 套用過濾
            self.logger.info("套用過濾條件...")
            filtered_mappings = self.apply_filters(mappings, filter_param)
            
            # 更新版本資訊
            self.logger.info("從 SFTP 取得版本資訊...")
            self.update_version_info(filtered_mappings, db_dict)
            
            # 產生比較資料
            self.logger.info("產生比較資料...")
            comparison_data = self.generate_comparison_data(filtered_mappings, filter_param)
            
            # 輸出 Excel
            utils.create_directory(output_dir)
            output_file = f"{output_dir}/{config.DEFAULT_DAILYBUILD_OUTPUT}"
            
            df = pd.DataFrame(comparison_data)
            df.to_excel(output_file, index=False)
            
            self.logger.info(f"成功輸出: {output_file}")
            return output_file
            
        except Exception as e:
            self.logger.error(f"處理失敗: {str(e)}")
            raise