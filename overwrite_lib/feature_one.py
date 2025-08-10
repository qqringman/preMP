"""
功能一：擴充 all_chip_mapping_table.xlsx
將輸入的 all_chip_mapping_table.xlsx 擴充成另一張 all_chip_mapping_table_ext.xlsx
並同時下載相關的 JIRA file 和檢查資訊
"""
import os
import pandas as pd
from typing import Dict, List, Any, Optional
import utils
import sys

# 加入上一層目錄到路徑
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
    
# 載入模組 (處理 import 路徑)
try:
    from excel_handler import ExcelHandler
except ImportError:
    # 如果無法直接導入，可能路徑不對，嘗試處理
    import sys
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
    from excel_handler import ExcelHandler

from jira_manager import JiraManager
from gerrit_manager import GerritManager

logger = utils.setup_logger(__name__)

class FeatureOne:
    """功能一：擴充晶片映射表"""
    
    def __init__(self):
        self.logger = logger
        self.excel_handler = ExcelHandler()
        self.jira_manager = JiraManager()
        self.gerrit_manager = GerritManager()
    
    def process(self, input_file: str, output_folder: str) -> bool:
        """
        處理功能一的主要邏輯
        
        Args:
            input_file: 輸入的 all_chip_mapping_table.xlsx
            output_folder: 輸出資料夾
            
        Returns:
            是否處理成功
        """
        try:
            self.logger.info("=== 開始執行功能一：擴充晶片映射表 ===")
            
            # 確保輸出資料夾存在
            utils.ensure_dir(output_folder)
            
            # 讀取輸入檔案
            df = self.excel_handler.read_excel(input_file)
            self.logger.info(f"成功讀取輸入檔案，共 {len(df)} 筆資料")
            
            # 處理每一列資料
            processed_data = []
            missing_manifests = []
            shared_sources = {}
            
            for index, row in df.iterrows():
                processed_row = self._process_row(row, output_folder, missing_manifests, shared_sources)
                processed_data.append(processed_row)
                
                if (index + 1) % 10 == 0:
                    self.logger.info(f"已處理 {index + 1}/{len(df)} 筆資料")
            
            # 建立輸出 DataFrame
            output_df = pd.DataFrame(processed_data)
            
            # 寫入 Excel 檔案
            output_file = os.path.join(output_folder, 'all_chip_mapping_table_ext.xlsx')
            self._write_excel_with_tabs(output_df, missing_manifests, shared_sources, output_file)
            
            self.logger.info(f"=== 功能一執行完成，輸出檔案：{output_file} ===")
            return True
            
        except Exception as e:
            self.logger.error(f"功能一執行失敗: {str(e)}")
            return False
    
    def _process_row(self, row: pd.Series, output_folder: str, 
                missing_manifests: List, shared_sources: Dict) -> Dict:
        """
        處理單一列資料
        """
        processed_row = row.to_dict()
        
        # 需要處理的 DB 欄位
        db_fields = ['DB_Info', 'premp_DB_Info', 'mp_DB_Info', 'mpbackup_DB_Info']
        
        for field in db_fields:
            if field in row and pd.notna(row[field]):
                db_info = str(row[field]).strip()
                
                # 取得 JIRA 資訊
                jira_info = self.jira_manager.get_issue_info_from_db(db_info)
                
                # 建立對應的欄位名稱前綴
                prefix = field.replace('_DB_Info', '')
                if prefix == 'DB':
                    prefix = ''
                else:
                    prefix = prefix + '_'
                
                # 填入新欄位
                processed_row[f'{prefix}Jira'] = jira_info['jira_link']
                processed_row[f'{prefix}Source'] = jira_info['source']
                processed_row[f'{prefix}Source_manifest'] = jira_info['manifest']
                processed_row[f'{prefix}Source_link'] = jira_info['source_link']
                
                # 下載 manifest 檔案
                if jira_info['source_link'] and jira_info['manifest']:
                    self._download_manifest_files(db_info, jira_info, output_folder)
                    
                    # 檢查檔案是否存在（Gerrit 和本地）
                    self._check_manifest_availability(
                        row, db_info, jira_info, missing_manifests, field, output_folder
                    )
                
                # 收集共用來源資訊
                if jira_info['source']:
                    self._collect_shared_sources(row, db_info, jira_info, shared_sources, field)
        
        return processed_row
    
    def _download_manifest_files(self, db_info: str, jira_info: Dict, output_folder: str):
        """下載 manifest 檔案和建立 README"""
        try:
            # 建立 DB 資料夾
            db_folder = os.path.join(output_folder, db_info)
            utils.ensure_dir(db_folder)
            
            # 下載 manifest 檔案
            if jira_info['source_link'] and jira_info['manifest']:
                manifest_path = os.path.join(db_folder, jira_info['manifest'])
                success = self.gerrit_manager.download_file_from_link(
                    jira_info['source_link'], manifest_path
                )
                
                if success:
                    self.logger.info(f"成功下載 {db_info}/{jira_info['manifest']}")
            
            # 建立 README.txt
            readme_path = os.path.join(db_folder, 'ReadMe.txt')
            readme_content = f"""Jira: {jira_info['jira_link']}
Source: {jira_info['source']}
Source_manifest: {jira_info['manifest']}
Source_link: {jira_info['source_link']}
"""
            with open(readme_path, 'w', encoding='utf-8') as f:
                f.write(readme_content)
            
            self.logger.info(f"建立 README: {readme_path}")
            
        except Exception as e:
            self.logger.error(f"下載檔案失敗 {db_info}: {str(e)}")
    
    def _check_manifest_availability(self, row: pd.Series, db_info: str, 
                               jira_info: Dict, missing_manifests: List, field: str, output_folder: str):
        """檢查 manifest 檔案的可用性"""
        try:
            if not jira_info['source_link'] or not jira_info['manifest']:
                return
            
            # 檢查 Gerrit 上是否存在
            gerrit_exists = self.gerrit_manager.check_file_exists(jira_info['source_link'])
            
            # 檢查本地是否存在
            local_path = os.path.join(output_folder, db_info, jira_info['manifest'])
            local_exists = os.path.exists(local_path)
            
            # 如果任一不存在，加入缺失清單
            if not gerrit_exists or not local_exists:
                # 決定 DB 類型
                db_type = self._determine_db_type_from_field(field)
                
                missing_entry = {
                    'SN': len(missing_manifests) + 1,
                    'Module': row.get('Module', ''),
                    'DB_Type': db_type,
                    'DB Info': db_info,
                    'DB_Info_Jira': jira_info['jira_link'],  # 新增 JIRA 連結
                    'Source': jira_info['source'],
                    'Source_manifest': jira_info['manifest'],
                    'Source_link': jira_info['source_link']
                }
                missing_manifests.append(missing_entry)
                
        except Exception as e:
            self.logger.error(f"檢查檔案可用性失敗: {str(e)}")

    def _determine_db_type_from_field(self, field: str) -> str:
        """從欄位名稱判斷 DB 類型"""
        if 'premp' in field:
            return 'premp'
        elif 'mpbackup' in field:
            return 'mpbackup'
        elif 'mp' in field:
            return 'mp'
        else:
            return 'master'
            
    def _collect_shared_sources(self, row: pd.Series, db_info: str, jira_info: Dict, 
                          shared_sources: Dict, field: str):
        """收集共用來源資訊"""
        try:
            source_key = jira_info['source']
            if not source_key:
                return
            
            if source_key not in shared_sources:
                shared_sources[source_key] = {
                    'db_list': [],
                    'source': jira_info['source'],
                    'manifest': jira_info['manifest'],
                    'source_link': jira_info['source_link']
                }
            
            # 建立 DB 資訊（包含 Module 和類型）
            module = row.get('Module', 'Unknown')
            db_type = self._determine_db_type_from_field(field)
            db_entry = f"{db_info}({module}, {db_type})"
            
            if db_entry not in shared_sources[source_key]['db_list']:
                shared_sources[source_key]['db_list'].append(db_entry)
                
        except Exception as e:
            self.logger.error(f"收集共用來源失敗: {str(e)}")
    
    def _determine_db_type(self, row: pd.Series, db_info: str, field: str = None) -> str:
        """判斷 DB 類型"""
        if field:
            if 'premp' in field:
                return 'premp'
            elif 'mpbackup' in field:
                return 'mpbackup'
            elif 'mp' in field:
                return 'mp'
            else:
                return 'master'
        
        # 從列資料判斷
        for col in row.index:
            if col.endswith('_DB_Info') and str(row[col]) == db_info:
                if 'premp' in col:
                    return 'premp'
                elif 'mpbackup' in col:
                    return 'mpbackup'
                elif 'mp' in col:
                    return 'mp'
        
        return 'master'
    
    def _write_excel_with_tabs(self, main_df: pd.DataFrame, missing_manifests: List,
                          shared_sources: Dict, output_file: str):
        """寫入 Excel 檔案（包含多個頁籤）"""
        try:
            with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
                # 主要資料頁籤（永遠存在）
                main_df.to_excel(writer, sheet_name='主要資料', index=False)
                
                # 缺少 manifest 頁籤（只有在有資料時才建立）
                if missing_manifests:
                    missing_df = pd.DataFrame(missing_manifests)
                    # 確保欄位順序
                    missing_columns = ['SN', 'Module', 'DB_Type', 'DB Info', 'DB_Info_Jira', 
                                    'Source', 'Source_manifest', 'Source_link']
                    missing_df = missing_df.reindex(columns=missing_columns)
                    missing_df.to_excel(writer, sheet_name='缺少_manifest', index=False)
                    self.logger.info(f"建立 '缺少_manifest' 頁籤，共 {len(missing_manifests)} 筆資料")
                else:
                    self.logger.info("沒有缺少的 manifest 檔案，跳過 '缺少_manifest' 頁籤")
                
                # 共用來源頁籤（只有在有共用資料時才建立）
                shared_data = []
                if shared_sources:
                    sn = 1
                    for source, info in shared_sources.items():
                        if len(info['db_list']) > 1:  # 只有多個 DB 使用同一來源才算共用
                            # 組合 DB Info，格式：DB2302(Merlin7, master),DB2857(Merlin8, premp)
                            db_info_combined = ','.join(info['db_list'])
                            
                            shared_data.append({
                                'SN': sn,
                                'DB Info': db_info_combined,
                                'Source': info['source'],
                                'Source_manifest': info['manifest'],
                                'Source_link': info['source_link']
                            })
                            sn += 1
                
                # 只有在有共用資料時才建立頁籤
                if shared_data:
                    shared_df = pd.DataFrame(shared_data)
                    # 確保欄位順序
                    shared_columns = ['SN', 'DB Info', 'Source', 'Source_manifest', 'Source_link']
                    shared_df = shared_df.reindex(columns=shared_columns)
                    shared_df.to_excel(writer, sheet_name='共用', index=False)
                    self.logger.info(f"建立 '共用' 頁籤，共 {len(shared_data)} 筆資料")
                else:
                    self.logger.info("沒有共用的來源，跳過 '共用' 頁籤")
                
                # 格式化所有工作表
                for sheet_name in writer.sheets:
                    worksheet = writer.sheets[sheet_name]
                    self.excel_handler._format_worksheet(worksheet)
            
            # 統計頁籤資訊
            created_sheets = ['主要資料']
            if missing_manifests:
                created_sheets.append('缺少_manifest')
            if shared_data:
                created_sheets.append('共用')
            
            self.logger.info(f"成功寫入 Excel 檔案: {output_file}")
            self.logger.info(f"建立的頁籤: {', '.join(created_sheets)}")
            
        except Exception as e:
            self.logger.error(f"寫入 Excel 檔案失敗: {str(e)}")
            raise