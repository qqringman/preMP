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
        """
        解析 SFTP URL 資訊
        
        Args:
            sftp_url: SFTP URL
            master_jira: Master JIRA ID（用於 NotFound 情況）
            
        Returns:
            包含 module, db_info, db_folder, db_version 的字典
        """
        try:
            # 檢查是否為 NotFound 或空值
            sftp_url_lower = str(sftp_url).lower().strip()
            if (not sftp_url or 
                pd.isna(sftp_url) or 
                sftp_url_lower == 'notfound_sftp_src_path' or 
                sftp_url_lower == 'sftpnotfound' or
                sftp_url_lower == 'notfound' or
                sftp_url_lower == 'nan'):
                
                # 清理 JIRA ID
                cleaned_jira = self.clean_jira_id(master_jira)
                
                return {
                    'module': 'Unknown',
                    'db_info': cleaned_jira if cleaned_jira else '',
                    'db_folder': '',
                    'db_version': '',
                    'sftp_path': sftp_url if sftp_url and not pd.isna(sftp_url) else 'NotFound'
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
            # 解析兩個來源的 SFTP 資訊，同時傳入 master_jira
            info1 = self.parse_sftp_info(source1.sftp_url, source1.master_jira)
            info2 = self.parse_sftp_info(source2.sftp_url, source2.master_jira)
            
            row = {
                'SN': sn,
                'RootFolder': '/DailyBuild/PrebuildFW',
                'Module': info1['module'],
                'DB_Type': type1,
                'DB_Info': info1['db_info'],
                'DB_Folder': info1['db_folder'],
                'DB_Version': info1['db_version'],
                'SftpPath': info1['sftp_path'],
                'compare_DB_Type': type2,
                'compare_DB_Info': info2['db_info'],
                'compare_DB_Folder': info2['db_folder'],
                'compare_DB_Version': info2['db_version'],
                'compare_SftpPath': info2['sftp_path']
            }
            result.append(row)
            sn += 1
            
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
            
            # 如果有模組過濾，先過濾資料
            if module_filter:
                self.logger.info(f"套用模組過濾: {module_filter}")
                filtered_data = []
                for source1, source2 in joined_data:
                    # 從 SFTP URL 解析模組
                    info1 = self.parse_sftp_info(source1.sftp_url, source1.master_jira)
                    if info1['module'].lower() == module_filter or module_filter in info1['module'].lower():
                        filtered_data.append((source1, source2))
                joined_data = filtered_data
                self.logger.info(f"過濾後剩餘 {len(joined_data)} 筆資料")
            
            # 產生映射資料
            self.logger.info("產生映射資料...")
            mapping_data = self.generate_mapping_data(joined_data, compare_type)
            
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
            
            # 輸出 Excel
            df = pd.DataFrame(mapping_data)
            df.to_excel(output_file, index=False)
            
            self.logger.info(f"成功輸出: {output_file}")
            return output_file
            
        except Exception as e:
            self.logger.error(f"處理失敗: {str(e)}")
            raise