"""
資料模型定義
定義系統中使用的資料結構
"""
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
import pandas as pd

@dataclass
class DBInfo:
    """資料庫資訊類別"""
    db_type: str
    db_info: str
    db_folder: str
    sftp_path: str
    db_version: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典"""
        return {
            'DB_Type': self.db_type,
            'DB_Info': self.db_info,
            'DB_Folder': self.db_folder,
            'DB_Version': self.db_version,
            'SftpPath': self.sftp_path
        }

@dataclass
class ChipMapping:
    """晶片映射資料"""
    sn: int
    module: str
    master_db: DBInfo
    premp_db: Optional[DBInfo] = None
    mp_db: Optional[DBInfo] = None
    mpbackup_db: Optional[DBInfo] = None
    
    def get_db_by_type(self, db_type: str) -> Optional[DBInfo]:
        """根據類型取得 DB 資訊"""
        mapping = {
            'master': self.master_db,
            'premp': self.premp_db,
            'mp': self.mp_db,
            'mpbackup': self.mpbackup_db
        }
        return mapping.get(db_type)
    
    def to_comparison_dict(self, db_type1: str, db_type2: str, root_folder: str = 'DailyBuild') -> Dict[str, Any]:
        """轉換為比較格式的字典"""
        db1 = self.get_db_by_type(db_type1)
        db2 = self.get_db_by_type(db_type2)
        
        if not db1 or not db2:
            return None
            
        return {
            'SN': self.sn,
            'RootFolder': root_folder,
            'Module': self.module,
            'DB_Type': db1.db_type,
            'DB_Info': db1.db_info,
            'DB_Folder': db1.db_folder,
            'DB_Version': db1.db_version,
            'SftpPath': db1.sftp_path,
            'compare_DB_Type': db2.db_type,
            'compare_DB_Info': db2.db_info,
            'compare_DB_Folder': db2.db_folder,
            'compare_DB_Version': db2.db_version,
            'compare_SftpPath': db2.sftp_path
        }

@dataclass
class PrebuildSource:
    """Prebuild 來源資料"""
    module_owner: str
    remote: str
    category: str
    project: str
    branch: str
    local_path: str
    revision: str
    master_jira: str
    prebuild_src: str
    sftp_url: str
    comment: str
    
    @property
    def key(self) -> tuple:
        """取得用於比對的 key"""
        return (self.category, self.project, self.local_path, self.master_jira)
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典"""
        return {
            'ModuleOwner': self.module_owner,
            'Remote': self.remote,
            'Category': self.category,
            'Project': self.project,
            'Branch': self.branch,
            'LocalPath': self.local_path,
            'Revision': self.revision,
            'Master_JIRA': self.master_jira,
            'PrebuildSRC': self.prebuild_src,
            'SftpURL': self.sftp_url,
            'Comment': self.comment
        }