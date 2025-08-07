"""
檔案比較模組（增強版）
處理 manifest.xml, F_Version.txt, Version.txt 的差異比較
支援一次執行所有比對情境
支援 Mapping Table 進行比對
"""
import os
import re
import glob
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Tuple, Set, Optional
import pandas as pd
import utils
import config
from excel_handler import ExcelHandler

logger = utils.setup_logger(__name__)

class FileComparator:
    """檔案比較器類別"""
    
    def __init__(self):
        self.logger = logger
        self.excel_handler = ExcelHandler()
        self.base_url_prebuilt = config.GERRIT_BASE_URL_PREBUILT
        self.base_url_normal = config.GERRIT_BASE_URL_NORMAL
        self.mapping_table = None  # 儲存 mapping table
        
    def _shorten_hash(self, hash_str: str) -> str:
        """將 hash code 縮短為前 7 個字元"""
        if hash_str and len(hash_str) >= 7:
            return hash_str[:7]
        return hash_str
    
    def _generate_link(self, project_info: Dict[str, str]) -> str:
        """根據 project 資訊生成 Gerrit link"""
        name = project_info.get('name', '')
        upstream = project_info.get('upstream', '')
        dest_branch = project_info.get('dest-branch', '')
        
        # 優先使用 upstream，如果沒有則使用 dest-branch
        branch = upstream if upstream else dest_branch
        
        if name and branch:
            # 判斷是否包含 prebuilt 或 prebuild，選擇對應的 base URL
            if 'prebuilt' in name.lower() or 'prebuild' in name.lower():
                base_url = self.base_url_prebuilt
            else:
                base_url = self.base_url_normal
            
            # 處理特殊的 branch 格式
            if branch.startswith('refs/'):
                # 如果 branch 已經包含 refs/，直接使用
                # 例如：refs/tags/u-tv-keystone-rtk-refplus-wave3-release-UKR8.20250727
                return f"{base_url}{name}/+log/{branch}"
            else:
                # 一般情況，加上 refs/heads/
                return f"{base_url}{name}/+log/refs/heads/{branch}"
        return ""
    
    def _extract_simple_module_name(self, full_module: str) -> str:
        """從完整模組路徑提取簡單模組名稱"""
        # PrebuildFW/bootcode -> bootcode
        # DailyBuild/Merlin7 -> Merlin7
        if '/' in full_module:
            return full_module.split('/')[-1]
        return full_module
    
    def _load_mapping_table(self, source_dir: str) -> Optional[pd.DataFrame]:
        """
        載入 mapping table
        
        Args:
            source_dir: 來源目錄
            
        Returns:
            Mapping table DataFrame 或 None
        """
        # 尋找 mapping table 檔案
        mapping_patterns = [
            'DailyBuild_mapping.xlsx',
            'PrebuildFW_mapping.xlsx',
            'DailyBuild_*_mapping.xlsx',
            'PrebuildFW_*_mapping.xlsx',
            '*_mapping.xlsx'
        ]
        
        mapping_files = []
        for pattern in mapping_patterns:
            files = glob.glob(os.path.join(source_dir, pattern))
            mapping_files.extend(files)
        
        if mapping_files:
            # 選擇第一個找到的 mapping table
            mapping_file = mapping_files[0]
            self.logger.info(f"找到 mapping table: {mapping_file}")
            
            try:
                df = self.excel_handler.read_excel(mapping_file)
                
                # 檢查必要欄位
                required_cols = ['DB_Type', 'DB_Info', 'SftpPath', 
                               'compare_DB_Type', 'compare_DB_Info', 'compare_SftpPath']
                
                # 檢查是否有足夠的欄位
                missing_cols = [col for col in required_cols if col not in df.columns]
                if missing_cols:
                    self.logger.warning(f"Mapping table 缺少欄位: {missing_cols}")
                    return None
                
                self.logger.info(f"成功載入 mapping table，共 {len(df)} 筆資料")
                return df
                
            except Exception as e:
                self.logger.error(f"讀取 mapping table 失敗: {str(e)}")
                return None
        
        self.logger.info("未找到 mapping table，使用預設比對邏輯")
        return None
    
    def _get_mapping_pairs(self, mapping_df: pd.DataFrame, compare_mode: str) -> List[Dict[str, Any]]:
        """
        從 mapping table 取得比對配對
        
        Args:
            mapping_df: Mapping table DataFrame
            compare_mode: 比對模式 (master_vs_premp, premp_vs_wave, wave_vs_backup)
            
        Returns:
            比對配對列表
        """
        pairs = []
        
        # 根據比對模式過濾資料
        for idx, row in mapping_df.iterrows():
            db_type = str(row.get('DB_Type', '')).lower()
            compare_db_type = str(row.get('compare_DB_Type', '')).lower()
            
            # 檢查是否符合比對模式
            match = False
            if compare_mode == 'master_vs_premp':
                match = (db_type == 'master' and compare_db_type == 'premp')
            elif compare_mode == 'premp_vs_wave':
                match = (db_type == 'premp' and compare_db_type in ['mp', 'wave'])
            elif compare_mode == 'wave_vs_backup':
                match = (db_type in ['mp', 'wave'] and compare_db_type in ['mpbackup', 'wave.backup'])
            
            if match:
                # 從路徑提取資料夾名稱
                sftp_path = row.get('SftpPath', '')
                compare_sftp_path = row.get('compare_SftpPath', '')
                
                # 解析路徑以取得本地資料夾名稱
                base_folder = self._extract_folder_from_path(sftp_path, row.get('DB_Folder', ''))
                compare_folder = self._extract_folder_from_path(compare_sftp_path, row.get('compare_DB_Folder', ''))
                
                pairs.append({
                    'module': row.get('Module', ''),
                    'base_type': row.get('DB_Type', ''),
                    'base_info': row.get('DB_Info', ''),
                    'base_path': sftp_path,
                    'base_folder': base_folder,
                    'compare_type': row.get('compare_DB_Type', ''),
                    'compare_info': row.get('compare_DB_Info', ''),
                    'compare_path': compare_sftp_path,
                    'compare_folder': compare_folder
                })
        
        return pairs
    
    def _extract_folder_from_path(self, sftp_path: str, db_folder: str = '') -> str:
        """
        從 SFTP 路徑提取資料夾名稱
        
        Args:
            sftp_path: SFTP 路徑
            db_folder: DB_Folder 欄位值（如果有）
            
        Returns:
            資料夾名稱
        """
        if db_folder:
            return db_folder
        
        # 從路徑提取資料夾名稱
        # 例如：/DailyBuild/Merlin7/DB2302_xxx -> DB2302_xxx
        parts = sftp_path.rstrip('/').split('/')
        if parts:
            # 取得包含 DB 或 RDDB 的部分
            for part in parts:
                if part.startswith('DB') or part.startswith('RDDB-'):
                    # 只取得版本號之前的部分
                    if '/' in part:
                        return part.split('/')[0]
                    return part
        
        return os.path.basename(sftp_path.rstrip('/'))
    
    def _find_module_path(self, source_dir: str, module: str, folder_name: str) -> Optional[str]:
        """
        尋找模組的實際路徑
        
        Args:
            source_dir: 來源目錄
            module: 模組名稱
            folder_name: 資料夾名稱（用於判斷）
            
        Returns:
            模組路徑或 None
        """
        # 可能的路徑組合
        possible_paths = [
            os.path.join(source_dir, module),  # 直接在 source_dir 下
            os.path.join(source_dir, 'DailyBuild', module),  # 在 DailyBuild 下
            os.path.join(source_dir, 'PrebuildFW', module),  # 在 PrebuildFW 下
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                # 檢查是否包含目標資料夾
                if os.path.exists(os.path.join(path, folder_name)):
                    return path
        
        # 如果都找不到，嘗試搜尋
        for root, dirs, files in os.walk(source_dir):
            if module in dirs:
                module_path = os.path.join(root, module)
                if os.path.exists(os.path.join(module_path, folder_name)):
                    return module_path
        
        return None
        
    def _parse_manifest_xml(self, file_path: str) -> Dict[str, Dict[str, str]]:
        """
        解析 manifest.xml 檔案
        
        Args:
            file_path: XML 檔案路徑
            
        Returns:
            專案資訊字典 {key: project_info}
        """
        projects = {}
        
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            
            # 尋找所有 project 元素
            for project in root.findall('.//project'):
                name = project.get('name', '')
                path = project.get('path', '')
                key = f"{name}||{path}"  # 使用 name 和 path 作為唯一鍵
                
                projects[key] = {
                    'name': name,
                    'path': path,
                    'revision': project.get('revision', ''),
                    'upstream': project.get('upstream', ''),
                    'dest-branch': project.get('dest-branch', ''),
                    'groups': project.get('groups', ''),
                    'clone-depth': project.get('clone-depth', ''),
                    'remote': project.get('remote', ''),
                    'element': ET.tostring(project, encoding='unicode').strip()
                }
                
            self.logger.info(f"成功解析 {file_path}，找到 {len(projects)} 個專案")
            
        except Exception as e:
            self.logger.error(f"解析 XML 檔案失敗 {file_path}: {str(e)}")
            
        return projects
        
    def _compare_manifest_files(self, file1: str, file2: str, module: str, base_folder: str = None, compare_folder: str = None, module_path: str = None, compare_mode: str = None) -> Tuple[List[Dict], List[Dict], List[Dict]]:
        """
        比較兩個 manifest.xml 檔案（修改後的邏輯）
        """
        # 解析兩個檔案
        base_projects = self._parse_manifest_xml(file1)
        compare_projects = self._parse_manifest_xml(file2)
        
        # 簡化模組名稱
        simple_module = self._extract_simple_module_name(module)
        
        # 1. 比較 revision 差異
        revision_diff = []
        sn = 1
        
        for key, base_proj in base_projects.items():
            if key in compare_projects:
                compare_proj = compare_projects[key]
                base_revision = base_proj.get('revision', '')
                compare_revision = compare_proj.get('revision', '')
                
                if base_revision != compare_revision or not compare_revision:
                    revision_diff.append({
                        'SN': sn,
                        'module': simple_module,
                        'location_path': module_path if module_path else '',
                        'base_folder': base_folder,
                        'compare_folder': compare_folder,
                        'name': base_proj['name'],
                        'path': base_proj['path'],
                        'base_short': self._shorten_hash(base_revision),
                        'base_revision': base_revision,
                        'compare_short': self._shorten_hash(compare_revision),
                        'compare_revision': compare_revision,
                        'base_upstream': base_proj.get('upstream', ''),
                        'compare_upstream': compare_proj.get('upstream', ''),
                        'base_dest-branch': base_proj.get('dest-branch', ''),
                        'compare_dest-branch': compare_proj.get('dest-branch', ''),
                        'base_link': self._generate_link(base_proj),
                        'compare_link': self._generate_link(compare_proj)
                    })
                    sn += 1
        
        # 2. 檢查分支命名錯誤
        branch_error = []
        sn = 1
        
        # 根據資料夾名稱決定檢查規則
        check_keyword = None
        if base_folder and compare_folder:
            if "-premp" in compare_folder and "-premp" not in base_folder:
                check_keyword = 'premp'
            elif "-wave" in compare_folder and "-wave.backup" not in compare_folder:
                if "-premp" in base_folder:
                    check_keyword = 'wave'
            elif "-wave.backup" in compare_folder:
                check_keyword = 'wave.backup'
        
        if check_keyword:
            for key, compare_proj in compare_projects.items():
                upstream = compare_proj.get('upstream', '')
                dest_branch = compare_proj.get('dest-branch', '')
                revision = compare_proj.get('revision', '')
                
                # 根據檢查關鍵字進行相應的檢查
                should_check = False
                
                if check_keyword == 'premp':
                    # 檢查是否都不包含 'premp'
                    if upstream and dest_branch:
                        if 'premp' not in upstream and 'premp' not in dest_branch:
                            should_check = True
                elif check_keyword == 'wave':
                    # 檢查是否都不包含 'wave'
                    if upstream and dest_branch:
                        if 'wave' not in upstream and 'wave' not in dest_branch:
                            should_check = True
                elif check_keyword == 'wave.backup':
                    # 檢查是否都不包含 'wave.backup'
                    if upstream and dest_branch:
                        if 'wave.backup' not in upstream and 'wave.backup' not in dest_branch:
                            should_check = True
                
                if should_check:
                    # 檢查是否包含 wave
                    has_wave = ('wave' in upstream or 'wave' in dest_branch)
                    
                    # 決定問題描述
                    problem = ""
                    if not has_wave:  # 只有 has_wave = N 時才顯示問題
                        if check_keyword == 'premp':
                            problem = "沒改成 premp"
                        elif check_keyword == 'wave':
                            problem = "沒改成 wave"
                        elif check_keyword == 'wave.backup':
                            problem = "沒改成 wavebackup"
                    
                    branch_error.append({
                        'SN': sn,
                        'module': simple_module,
                        'location_path': module_path if module_path else '',
                        'base_folder': base_folder,
                        'compare_folder': compare_folder,
                        'name': compare_proj['name'],
                        'path': compare_proj['path'],
                        'revision_short': self._shorten_hash(revision),
                        'revision': revision,
                        'upstream': upstream,
                        'dest-branch': dest_branch,
                        'compare_link': self._generate_link(compare_proj),
                        'has_wave': 'Y' if has_wave else 'N',
                        'problem': problem
                    })
                    sn += 1
        
        # 3. 檢查缺少或新增的 project（保持原有邏輯）
        lost_project = []
        sn = 1
        
        # 決定 Base folder 值
        base_folder_value = ""
        if compare_mode == 'master_vs_premp':
            base_folder_value = "premp"
        elif compare_mode == 'premp_vs_wave':
            base_folder_value = "wave"
        elif compare_mode == 'wave_vs_backup':
            base_folder_value = "wavebackup"
        
        # 檢查在 base 檔案中但不在 compare 檔案中的項目（刪除）
        for key, base_proj in base_projects.items():
            if key not in compare_projects:
                revision = base_proj.get('revision', '')
                lost_project.append({
                    'SN': sn,
                    'Base folder': base_folder_value,
                    '狀態': '刪除',
                    'module': simple_module,
                    'location_path': module_path if module_path else '',
                    'folder': base_folder,  # 記錄是哪個資料夾
                    'name': base_proj['name'],
                    'path': base_proj['path'],
                    'upstream': base_proj.get('upstream', ''),
                    'dest-branch': base_proj.get('dest-branch', ''),
                    'revision': revision,
                    'link': self._generate_link(base_proj)
                })
                sn += 1
        
        # 檢查在 compare 檔案中但不在 base 檔案中的項目（新增）
        for key, compare_proj in compare_projects.items():
            if key not in base_projects:
                revision = compare_proj.get('revision', '')
                lost_project.append({
                    'SN': sn,
                    'Base folder': base_folder_value,
                    '狀態': '新增',
                    'module': simple_module,
                    'location_path': module_path if module_path else '',
                    'folder': compare_folder,  # 記錄是哪個資料夾
                    'name': compare_proj['name'],
                    'path': compare_proj['path'],
                    'upstream': compare_proj.get('upstream', ''),
                    'dest-branch': compare_proj.get('dest-branch', ''),
                    'revision': revision,
                    'link': self._generate_link(compare_proj)
                })
                sn += 1
        
        return revision_diff, branch_error, lost_project
        
    def _compare_text_files(self, file1: str, file2: str, file_type: str) -> List[Dict[str, Any]]:
        """
        比較兩個文字檔案（根據檔案類型使用不同的比較規則）
        
        Args:
            file1: 第一個檔案路徑
            file2: 第二個檔案路徑
            file_type: 檔案類型（F_Version.txt 或 Version.txt）
            
        Returns:
            差異列表
        """
        differences = []
        
        try:
            with open(file1, 'r', encoding='utf-8', errors='ignore') as f1:
                content1 = f1.read()
                lines1 = content1.splitlines()
            with open(file2, 'r', encoding='utf-8', errors='ignore') as f2:
                content2 = f2.read()
                lines2 = content2.splitlines()
            
            if file_type.lower() == 'f_version.txt':
                # F_Version.txt 比較規則：只比較 P_GIT_xxx 行
                git_lines1 = {}
                git_lines2 = {}
                
                # 提取 P_GIT_xxx 行
                for line in lines1:
                    line = line.strip()
                    if line.startswith('P_GIT_'):
                        parts = line.split(';')
                        if len(parts) >= 5:
                            git_id = parts[0]
                            git_lines1[git_id] = line
                
                for line in lines2:
                    line = line.strip()
                    if line.startswith('P_GIT_'):
                        parts = line.split(';')
                        if len(parts) >= 5:
                            git_id = parts[0]
                            git_lines2[git_id] = line
                
                # 比較差異
                all_git_ids = set(git_lines1.keys()) | set(git_lines2.keys())
                for git_id in sorted(all_git_ids):
                    line1 = git_lines1.get(git_id, '')
                    line2 = git_lines2.get(git_id, '')
                    if line1 != line2:
                        differences.append({
                            'line': git_id,
                            'file1': line1,
                            'file2': line2,
                            'content1': content1,
                            'content2': content2
                        })
                        
            else:  # Version.txt
                # 檢查是否是特殊格式（有 F_HASH）
                has_f_hash = any('F_HASH:' in line for line in lines1 + lines2)
                
                if has_f_hash:
                    # Version.txt with F_HASH format
                    hash1 = None
                    hash2 = None
                    
                    for line in lines1:
                        if 'F_HASH:' in line:
                            parts = line.split('F_HASH:')
                            if len(parts) > 1:
                                hash1 = parts[1].strip()
                                hash_line1 = line.strip()
                                break
                    
                    for line in lines2:
                        if 'F_HASH:' in line:
                            parts = line.split('F_HASH:')
                            if len(parts) > 1:
                                hash2 = parts[1].strip()
                                hash_line2 = line.strip()
                                break
                    
                    if hash1 != hash2:
                        differences.append({
                            'line': 'F_HASH',
                            'file1': hash_line1 if 'hash_line1' in locals() else f'F_HASH: {hash1}' if hash1 else 'F_HASH: (not found)',
                            'file2': hash_line2 if 'hash_line2' in locals() else f'F_HASH: {hash2}' if hash2 else 'F_HASH: (not found)',
                            'content1': content1,
                            'content2': content2
                        })
                else:
                    # Other Version.txt format: 比較所有包含 ":" 的行
                    colon_lines1 = {}
                    colon_lines2 = {}
                    
                    # 提取包含 ":" 的行
                    for line in lines1:
                        line = line.strip()
                        if ':' in line and not line.startswith('#') and not line.startswith('//'):
                            # 使用冒號前的部分作為鍵
                            key = line.split(':')[0].strip()
                            colon_lines1[key] = line
                    
                    for line in lines2:
                        line = line.strip()
                        if ':' in line and not line.startswith('#') and not line.startswith('//'):
                            key = line.split(':')[0].strip()
                            colon_lines2[key] = line
                    
                    # 比較差異
                    all_keys = set(colon_lines1.keys()) | set(colon_lines2.keys())
                    for key in sorted(all_keys):
                        line1 = colon_lines1.get(key, '')
                        line2 = colon_lines2.get(key, '')
                        if line1 != line2:
                            differences.append({
                                'line': key,
                                'file1': line1,
                                'file2': line2,
                                'content1': content1,
                                'content2': content2
                            })
                        
        except Exception as e:
            self.logger.error(f"比較文字檔案失敗: {str(e)}")
            
        return differences
    
    def compare_all_scenarios(self, source_dir: str, output_dir: str = None) -> Dict[str, Any]:
        """
        執行所有比對情境（支援 mapping table）
        
        Args:
            source_dir: 來源目錄
            output_dir: 輸出目錄
            
        Returns:
            所有比對結果的摘要
        """
        output_dir = output_dir or source_dir
        
        # 載入 mapping table（如果存在）
        self.mapping_table = self._load_mapping_table(source_dir)
        
        if self.mapping_table is not None:
            # 使用 mapping table 進行比對
            return self._compare_with_mapping_table(source_dir, output_dir)
        else:
            # 使用原有邏輯進行比對
            return self._compare_all_scenarios_default(source_dir, output_dir)
    
    def _compare_with_mapping_table(self, source_dir: str, output_dir: str) -> Dict[str, Any]:
        """
        使用 mapping table 進行比對
        
        Args:
            source_dir: 來源目錄
            output_dir: 輸出目錄
            
        Returns:
            比對結果
        """
        # 初始化結果
        all_results = {
            'master_vs_premp': {
                'success': 0,
                'failed': 0,
                'modules': [],
                'failed_modules': [],
                'reports': []
            },
            'premp_vs_wave': {
                'success': 0,
                'failed': 0,
                'modules': [],
                'failed_modules': [],
                'reports': []
            },
            'wave_vs_backup': {
                'success': 0,
                'failed': 0,
                'modules': [],
                'failed_modules': [],
                'reports': []
            },
            'failed': 0,
            'failed_modules': [],
            'summary_report': ''
        }
        
        # 整合報表的資料
        all_revision_diff = []
        all_branch_error = []
        all_lost_project = []
        all_version_diff = []
        cannot_compare_modules = []
        
        try:
            # 處理每個比對情境
            scenarios = [
                ('master_vs_premp', 'Master vs PreMP'),
                ('premp_vs_wave', 'PreMP vs Wave'),
                ('wave_vs_backup', 'Wave vs Wave.backup')
            ]
            
            for scenario_key, scenario_name in scenarios:
                # 取得該情境的比對配對
                pairs = self._get_mapping_pairs(self.mapping_table, scenario_key)
                
                self.logger.info(f"處理 {scenario_name}，找到 {len(pairs)} 個比對配對")
                
                for pair in pairs:
                    module = pair['module']
                    base_folder = pair['base_folder']
                    compare_folder = pair['compare_folder']
                    
                    # 尋找實際的資料夾路徑
                    module_path = self._find_module_path(source_dir, module, base_folder)
                    
                    if not module_path:
                        self.logger.warning(f"找不到模組路徑: {module}/{base_folder}")
                        all_results[scenario_key]['failed'] += 1
                        all_results[scenario_key]['failed_modules'].append(module)
                        continue
                    
                    # 確認兩個資料夾都存在
                    base_path = os.path.join(module_path, base_folder)
                    compare_path = os.path.join(module_path, compare_folder)
                    
                    if not os.path.exists(base_path):
                        self.logger.warning(f"Base 資料夾不存在: {base_path}")
                        all_results[scenario_key]['failed'] += 1
                        all_results[scenario_key]['failed_modules'].append(module)
                        continue
                    
                    if not os.path.exists(compare_path):
                        self.logger.warning(f"Compare 資料夾不存在: {compare_path}")
                        all_results[scenario_key]['failed'] += 1
                        all_results[scenario_key]['failed_modules'].append(module)
                        continue
                    
                    # 執行比對
                    try:
                        results = self._compare_specific_folders(
                            module_path, base_folder, compare_folder, module, scenario_key
                        )
                        
                        # 收集資料
                        all_revision_diff.extend(results['revision_diff'])
                        all_branch_error.extend(results['branch_error'])
                        all_lost_project.extend(results['lost_project'])
                        if 'version_diffs' in results:
                            all_version_diff.extend(results['version_diffs'])
                        
                        # 記錄成功
                        all_results[scenario_key]['success'] += 1
                        all_results[scenario_key]['modules'].append(module)
                        
                        # 寫入個別報表
                        if any([results['revision_diff'], results['branch_error'], results['lost_project']]):
                            scenario_dir = os.path.join(output_dir, scenario_key)
                            module_output_dir = os.path.join(scenario_dir, module)
                            
                            if not os.path.exists(module_output_dir):
                                os.makedirs(module_output_dir)
                            
                            # 生成檔案名稱
                            compare_filename = self._generate_compare_filename(
                                module, base_folder, compare_folder
                            )
                            
                            report_file = self._write_module_compare_report(
                                module, results, module_output_dir, compare_filename
                            )
                            if report_file:
                                all_results[scenario_key]['reports'].append(report_file)
                                
                    except Exception as e:
                        self.logger.error(f"比對 {module} ({scenario_name}) 失敗: {str(e)}")
                        all_results[scenario_key]['failed'] += 1
                        all_results[scenario_key]['failed_modules'].append(module)
            
            # 重新編號所有資料
            for i, item in enumerate(all_revision_diff, 1):
                item['SN'] = i
            for i, item in enumerate(all_branch_error, 1):
                item['SN'] = i
            for i, item in enumerate(all_lost_project, 1):
                item['SN'] = i
            for i, item in enumerate(all_version_diff, 1):
                item['SN'] = i
            
            # 寫入總整合報表
            summary_report_path = self._write_all_scenarios_report(
                all_revision_diff, all_branch_error, all_lost_project,
                all_version_diff, cannot_compare_modules, all_results, output_dir
            )
            
            all_results['summary_report'] = summary_report_path
            
            return all_results
            
        except Exception as e:
            self.logger.error(f"使用 mapping table 執行比對失敗: {str(e)}")
            raise
    
    def _compare_all_scenarios_default(self, source_dir: str, output_dir: str) -> Dict[str, Any]:
        """
        使用預設邏輯執行所有比對情境（原有邏輯）
        
        Args:
            source_dir: 來源目錄
            output_dir: 輸出目錄
            
        Returns:
            所有比對結果的摘要
        """
        output_dir = output_dir or source_dir
        
        # 初始化結果
        all_results = {
            'master_vs_premp': {
                'success': 0,
                'failed': 0,
                'modules': [],
                'failed_modules': [],
                'reports': []
            },
            'premp_vs_wave': {
                'success': 0,
                'failed': 0,
                'modules': [],
                'failed_modules': [],
                'reports': []
            },
            'wave_vs_backup': {
                'success': 0,
                'failed': 0,
                'modules': [],
                'failed_modules': [],
                'reports': []
            },
            'failed': 0,
            'failed_modules': [],
            'summary_report': ''
        }
        
        # 整合報表的資料
        all_revision_diff = []
        all_branch_error = []
        all_lost_project = []
        all_version_diff = []
        cannot_compare_modules = []
        
        try:
            # 取得所有模組
            actual_modules = self._get_all_modules(source_dir)
            self.logger.info(f"找到 {len(actual_modules)} 個模組")
            
            # 處理每個模組
            for top_dir, module, module_path in actual_modules:
                full_module = f"{top_dir}/{module}" if top_dir else module
                
                # 執行三種比對情境
                scenarios = [
                    ('master_vs_premp', 'Master vs PreMP'),
                    ('premp_vs_wave', 'PreMP vs Wave'),
                    ('wave_vs_backup', 'Wave vs Wave.backup')
                ]
                
                module_has_comparison = False
                module_failures = []
                
                for scenario_key, scenario_name in scenarios:
                    base_folder, compare_folder, missing_info = self._find_folders_for_comparison(
                        module_path, scenario_key
                    )
                    
                    if base_folder and compare_folder:
                        # 可以進行比對
                        try:
                            results = self._compare_specific_folders(
                                module_path, base_folder, compare_folder, full_module, scenario_key
                            )
                            
                            # 收集資料
                            all_revision_diff.extend(results['revision_diff'])
                            all_branch_error.extend(results['branch_error'])
                            all_lost_project.extend(results['lost_project'])
                            if 'version_diffs' in results:
                                all_version_diff.extend(results['version_diffs'])
                            
                            # 記錄成功
                            all_results[scenario_key]['success'] += 1
                            all_results[scenario_key]['modules'].append(module)
                            module_has_comparison = True
                            
                            # 寫入個別報表
                            if any([results['revision_diff'], results['branch_error'], results['lost_project']]):
                                # 建立輸出路徑
                                scenario_dir = os.path.join(output_dir, scenario_key)
                                if top_dir:
                                    module_output_dir = os.path.join(scenario_dir, top_dir, module)
                                else:
                                    module_output_dir = os.path.join(scenario_dir, module)
                                
                                if not os.path.exists(module_output_dir):
                                    os.makedirs(module_output_dir)
                                
                                # 生成檔案名稱
                                compare_filename = self._generate_compare_filename(
                                    module, base_folder, compare_folder
                                )
                                
                                report_file = self._write_module_compare_report(
                                    module, results, module_output_dir, compare_filename
                                )
                                if report_file:
                                    all_results[scenario_key]['reports'].append(report_file)
                                    
                        except Exception as e:
                            self.logger.error(f"比對 {module} ({scenario_name}) 失敗: {str(e)}")
                            module_failures.append({
                                'scenario': scenario_name,
                                'error': str(e)
                            })
                            all_results[scenario_key]['failed'] += 1
                            all_results[scenario_key]['failed_modules'].append(module)
                    else:
                        # 無法比對
                        all_results[scenario_key]['failed'] += 1
                        all_results[scenario_key]['failed_modules'].append(module)
                        module_failures.append({
                            'scenario': scenario_name,
                            'reason': missing_info
                        })
                
                # 如果這個模組完全無法比對
                if not module_has_comparison:
                    folders = [f for f in os.listdir(module_path) 
                              if os.path.isdir(os.path.join(module_path, f))]
                    
                    # 使用第一個資料夾的完整路徑
                    if folders:
                        full_path = os.path.join(module_path, folders[0])
                    else:
                        full_path = module_path
                    
                    # 整理失敗原因
                    failure_reasons = []
                    for failure in module_failures:
                        if 'reason' in failure:
                            failure_reasons.append(f"{failure['scenario']}: {failure['reason']}")
                        else:
                            failure_reasons.append(f"{failure['scenario']}: {failure['error']}")
                    
                    cannot_compare_modules.append({
                        'SN': len(cannot_compare_modules) + 1,
                        'module': module,
                        'location_path': module_path,
                        'folder_count': len(folders),
                        'folders': ', '.join(folders) if folders else '無資料夾',
                        'path': full_path,
                        'reason': '; '.join(failure_reasons)
                    })
                    all_results['failed'] += 1
                    all_results['failed_modules'].append(module)
            
            # 重新編號所有資料
            for i, item in enumerate(all_revision_diff, 1):
                item['SN'] = i
            for i, item in enumerate(all_branch_error, 1):
                item['SN'] = i
            for i, item in enumerate(all_lost_project, 1):
                item['SN'] = i
            for i, item in enumerate(all_version_diff, 1):
                item['SN'] = i
            
            # 寫入總整合報表
            summary_report_path = self._write_all_scenarios_report(
                all_revision_diff, all_branch_error, all_lost_project,
                all_version_diff, cannot_compare_modules, all_results, output_dir
            )
            
            all_results['summary_report'] = summary_report_path
            
            return all_results
            
        except Exception as e:
            self.logger.error(f"執行所有比對情境失敗: {str(e)}")
            raise
    
    def _generate_compare_filename(self, module: str, base_folder: str, compare_folder: str) -> str:
        """
        生成比較檔案名稱
        例如：bootcode_RDDB-531_RDDB-1046-premp_compare.xlsx
        """
        # 提取資料夾中的 RDDB 或 DB 編號
        base_id = base_folder
        compare_id = compare_folder
        
        # 簡化：去除後綴，只保留編號部分
        if base_folder.startswith('RDDB-'):
            base_id = base_folder.split('-premp')[0].split('-wave')[0]
        elif base_folder.startswith('DB'):
            base_id = base_folder.split('-premp')[0].split('-wave')[0]
            
        filename = f"{module}_{base_id}_{compare_folder}_compare.xlsx"
        return filename
    
    def _get_all_modules(self, source_dir: str) -> List[Tuple[str, str, str]]:
        """取得所有模組"""
        actual_modules = []
        
        # 檢查是否有 PrebuildFW 或 DailyBuild 子目錄
        has_top_dirs = False
        
        # 檢查 PrebuildFW 目錄
        prebuild_path = os.path.join(source_dir, 'PrebuildFW')
        if os.path.exists(prebuild_path) and os.path.isdir(prebuild_path):
            has_top_dirs = True
            # 取得 PrebuildFW 下的所有模組
            for module in os.listdir(prebuild_path):
                module_path = os.path.join(prebuild_path, module)
                if os.path.isdir(module_path):
                    actual_modules.append(('PrebuildFW', module, module_path))
        
        # 檢查 DailyBuild 目錄
        daily_path = os.path.join(source_dir, 'DailyBuild')
        if os.path.exists(daily_path) and os.path.isdir(daily_path):
            has_top_dirs = True
            # 取得 DailyBuild 下的所有模組（平台）
            for platform in os.listdir(daily_path):
                platform_path = os.path.join(daily_path, platform)
                if os.path.isdir(platform_path):
                    actual_modules.append(('DailyBuild', platform, platform_path))
        
        # 如果沒有頂層目錄，使用原本的邏輯
        if not has_top_dirs:
            modules = [d for d in os.listdir(source_dir) 
                      if os.path.isdir(os.path.join(source_dir, d))]
            for module in modules:
                module_path = os.path.join(source_dir, module)
                actual_modules.append(('', module, module_path))
        
        return actual_modules
    
    def _write_all_scenarios_report(self, revision_diff: List[Dict], branch_error: List[Dict],
                               lost_project: List[Dict], version_diff: List[Dict],
                               cannot_compare_modules: List[Dict], all_results: Dict,
                               output_dir: str) -> str:
        """寫入所有比對情境的整合報表"""
        try:
            import pandas as pd
            from openpyxl.styles import PatternFill, Font, Alignment
            from openpyxl.worksheet.filters import FilterColumn, Filters, AutoFilter
            
            output_file = os.path.join(output_dir, "all_scenarios_compare.xlsx")
            
            with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
                # 摘要頁籤
                summary_data = []
                
                # 各情境的統計
                scenarios = [
                    ('Master vs PreMP', all_results['master_vs_premp']),
                    ('PreMP vs Wave', all_results['premp_vs_wave']),
                    ('Wave vs Backup', all_results['wave_vs_backup'])
                ]
                
                for scenario_name, scenario_result in scenarios:
                    summary_data.append({
                        '比對情境': scenario_name,
                        '成功模組數': scenario_result['success'],
                        '失敗模組數': scenario_result['failed'],
                        '成功模組清單': ', '.join(scenario_result['modules']) if scenario_result['modules'] else '',
                        '失敗模組清單': ', '.join(scenario_result['failed_modules']) if scenario_result['failed_modules'] else ''
                    })
                
                # 加入總計
                total_modules = len(set(
                    all_results['master_vs_premp']['modules'] +
                    all_results['premp_vs_wave']['modules'] +
                    all_results['wave_vs_backup']['modules']
                ))
                
                total_failed = len(set(
                    all_results['master_vs_premp']['failed_modules'] +
                    all_results['premp_vs_wave']['failed_modules'] +
                    all_results['wave_vs_backup']['failed_modules']
                ))
                
                summary_data.append({
                    '比對情境': '總計',
                    '成功模組數': total_modules,
                    '失敗模組數': total_failed,
                    '成功模組清單': str(total_modules),
                    '失敗模組清單': str(total_failed)
                })
                
                df_summary = pd.DataFrame(summary_data)
                df_summary.to_excel(writer, sheet_name='摘要', index=False)
                
                # 格式化摘要頁籤
                worksheet_summary = writer.sheets['摘要']
                
                # 設定標題列格式（深藍底白字）
                header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
                header_font = Font(color="FFFFFF", bold=True)
                
                # 格式化標題列
                for cell in worksheet_summary[1]:
                    cell.fill = header_fill
                    cell.font = header_font
                    cell.alignment = Alignment(horizontal='center', vertical='center')
                
                # 設定總計列的格式（淺藍底）
                total_fill = PatternFill(start_color="DCE6F1", end_color="DCE6F1", fill_type="solid")
                total_font = Font(bold=True)
                
                # 找到總計列（最後一列）
                total_row = len(df_summary) + 1  # +1 因為第一行是標題
                for col in range(1, len(df_summary.columns) + 1):
                    cell = worksheet_summary.cell(row=total_row, column=col)
                    cell.fill = total_fill
                    cell.font = total_font
                    # 總計列的數字也要置中
                    if col in [2, 3]:  # 成功模組數和失敗模組數欄位
                        cell.alignment = Alignment(horizontal='center', vertical='center')
                
                # 設定所有資料列的對齊方式
                for row_idx in range(2, total_row + 1):  # 包含總計列
                    # 比對情境欄位（第1欄）靠左
                    worksheet_summary.cell(row=row_idx, column=1).alignment = Alignment(horizontal='left', vertical='center')
                    
                    # 成功模組數和失敗模組數（第2、3欄）置中
                    worksheet_summary.cell(row=row_idx, column=2).alignment = Alignment(horizontal='center', vertical='center')
                    worksheet_summary.cell(row=row_idx, column=3).alignment = Alignment(horizontal='center', vertical='center')
                    
                    # 成功模組清單和失敗模組清單（第4、5欄）靠左
                    if row_idx < total_row:  # 非總計列
                        worksheet_summary.cell(row=row_idx, column=4).alignment = Alignment(horizontal='left', vertical='center')
                        worksheet_summary.cell(row=row_idx, column=5).alignment = Alignment(horizontal='left', vertical='center')
                    else:  # 總計列的清單欄位也置中
                        worksheet_summary.cell(row=row_idx, column=4).alignment = Alignment(horizontal='center', vertical='center')
                        worksheet_summary.cell(row=row_idx, column=5).alignment = Alignment(horizontal='center', vertical='center')
                
                # 調整欄寬
                worksheet_summary.column_dimensions['A'].width = 20  # 比對情境
                worksheet_summary.column_dimensions['B'].width = 15  # 成功模組數
                worksheet_summary.column_dimensions['C'].width = 15  # 失敗模組數
                worksheet_summary.column_dimensions['D'].width = 60  # 成功模組清單
                worksheet_summary.column_dimensions['E'].width = 60  # 失敗模組清單
                
                # revision_diff 頁籤
                if revision_diff:
                    df = pd.DataFrame(revision_diff)
                    columns_order = ['SN', 'module', 'location_path', 'base_folder', 'compare_folder', 'name', 'path', 
                                'base_short', 'base_revision', 'compare_short', 'compare_revision',
                                'base_upstream', 'compare_upstream', 'base_dest-branch', 'compare_dest-branch',
                                'base_link', 'compare_link']
                    columns_order = [col for col in columns_order if col in df.columns]
                    df = df[columns_order]
                    df.to_excel(writer, sheet_name='revision_diff', index=False)
                
                # branch_error 頁籤
                if branch_error:
                    df = pd.DataFrame(branch_error)
                    columns_order = ['SN', 'module', 'location_path', 'base_folder', 'compare_folder', 'name', 'path', 
                                'revision_short', 'revision', 'upstream', 'dest-branch', 
                                'compare_link', 'problem', 'has_wave']
                    columns_order = [col for col in columns_order if col in df.columns]
                    df = df[columns_order]
                    df_sorted = df.sort_values('has_wave', ascending=True)
                    df_sorted.to_excel(writer, sheet_name='branch_error', index=False)
                
                # lost_project 頁籤
                if lost_project:
                    df = pd.DataFrame(lost_project)
                    columns_order = ['SN', 'Base folder', '狀態', 'module', 'location_path', 'folder', 'name', 'path', 
                                'upstream', 'dest-branch', 'revision', 'link']
                    columns_order = [col for col in columns_order if col in df.columns]
                    df = df[columns_order]
                    df.to_excel(writer, sheet_name='lost_project', index=False)
                
                # version_diff 頁籤
                if version_diff:
                    df = pd.DataFrame(version_diff)
                    # 移除 module_path 欄位
                    if 'module_path' in df.columns:
                        df = df.drop('module_path', axis=1)
                    # 移除 is_different 欄位（如果存在）
                    if 'is_different' in df.columns:
                        df = df.drop('is_different', axis=1)
                    
                    # 確保欄位順序正確
                    columns_order = ['SN', 'module', 'location_path', 'base_folder', 'compare_folder', 'file_type', 
                                'base_content', 'compare_content', 'org_content']
                    
                    # 只保留存在的欄位
                    columns_order = [col for col in columns_order if col in df.columns]
                    
                    # 重新排序欄位
                    df = df.reindex(columns=columns_order)
                    
                    df.to_excel(writer, sheet_name='version_diff', index=False)
                
                # 無法比對頁籤
                if cannot_compare_modules:
                    df = pd.DataFrame(cannot_compare_modules)
                    columns_order = ['SN', 'module', 'location_path', 'folder_count', 'folders', 'path', 'reason']
                    columns_order = [col for col in columns_order if col in df.columns]
                    df = df[columns_order]
                    df.to_excel(writer, sheet_name='無法比對', index=False)
                
                # 格式化所有工作表
                for sheet_name in writer.sheets:
                    worksheet = writer.sheets[sheet_name]
                    self.excel_handler._format_worksheet(worksheet)
                
                # 套用特定格式和篩選
                self._apply_special_formatting_and_filters(writer, revision_diff, branch_error, 
                                            lost_project, version_diff)
            
            self.logger.info(f"成功寫入所有情境整合報表: {output_file}")
            return output_file
            
        except Exception as e:
            self.logger.error(f"寫入所有情境整合報表失敗: {str(e)}")
            raise
    
    def _apply_special_formatting_and_filters(self, writer, revision_diff, branch_error, 
                        lost_project, version_diff):
        """套用特定欄位的格式和篩選器"""
        import pandas as pd
        from openpyxl.styles import PatternFill, Font
        from openpyxl.worksheet.filters import FilterColumn, Filters, AutoFilter
        
        # revision_diff 頁籤的特定格式
        if revision_diff and 'revision_diff' in writer.sheets:
            worksheet = writer.sheets['revision_diff']
            df = pd.DataFrame(revision_diff)
            
            # 設定深紅底標題的欄位
            header_fill = PatternFill(start_color="C00000", end_color="C00000", fill_type="solid")
            white_font = Font(color="FFFFFF", bold=True)
            red_font = Font(color="FF0000")
            
            # 找到需要格式化的欄位位置
            target_columns = ['base_short', 'base_revision', 'compare_short', 'compare_revision']
            column_indices = {}
            
            for idx, col in enumerate(df.columns):
                if col in target_columns:
                    column_indices[col] = idx + 1
            
            # 設定標題為深紅底白字
            for col_name, col_idx in column_indices.items():
                cell = worksheet.cell(row=1, column=col_idx)
                cell.fill = header_fill
                cell.font = white_font
            
            # 設定內容為紅字
            for row in range(2, len(df) + 2):
                for col_name, col_idx in column_indices.items():
                    worksheet.cell(row=row, column=col_idx).font = red_font
        
        # branch_error 頁籤的特定格式和篩選
        if branch_error and 'branch_error' in writer.sheets:
            worksheet = writer.sheets['branch_error']
            df = pd.DataFrame(branch_error)
            
            # 找到 "problem" 和 "has_wave" 欄位的位置
            problem_col = None
            has_wave_col = None
            for idx, col in enumerate(df.columns):
                if col == 'problem':
                    problem_col = idx + 1  # 修正：改為 idx + 1
                elif col == 'has_wave':
                    has_wave_col = idx + 1  # 修正：改為 idx + 1
            
            if problem_col:
                # 設定深紅底白字
                header_fill = PatternFill(start_color="C00000", end_color="C00000", fill_type="solid")
                white_font = Font(color="FFFFFF", bold=True)
                red_font = Font(color="FF0000")
                
                # 設定標題
                cell = worksheet.cell(row=1, column=problem_col)
                cell.fill = header_fill
                cell.font = white_font
                
                # 設定 problem 欄位有內容的儲存格為紅字
                for row_idx in range(2, worksheet.max_row + 1):
                    cell_value = worksheet.cell(row=row_idx, column=problem_col).value
                    if cell_value and str(cell_value).strip():
                        worksheet.cell(row=row_idx, column=problem_col).font = red_font
            
            # 設定自動篩選
            worksheet.auto_filter.ref = worksheet.dimensions

            # 設定 has_wave 欄位的篩選條件為只顯示 "N"
            if has_wave_col:
                # 取得所有唯一的 has_wave 值
                has_wave_values = df['has_wave'].unique().tolist()
                
                # 建立篩選器
                has_wave_df_index = df.columns.get_loc('has_wave')
                filter_column = FilterColumn(colId=has_wave_df_index)
                filter_column.filters = Filters()
                filter_column.filters.filter = ['N']
                
                # 如果有 'Y' 值，需要將其設為隱藏
                if 'Y' in has_wave_values:
                    # 直接根據工作表中的值來隱藏
                    for row_idx in range(2, worksheet.max_row + 1):
                        if worksheet.cell(row=row_idx, column=has_wave_col).value == 'Y':
                            worksheet.row_dimensions[row_idx].hidden = True
                
                # 將篩選器加入自動篩選
                worksheet.auto_filter.filterColumn.append(filter_column)
        
        # lost_project 頁籤的特定格式
        if lost_project and 'lost_project' in writer.sheets:
            worksheet = writer.sheets['lost_project']
            df = pd.DataFrame(lost_project)
            
            # 定義顏色
            red_font = Font(color="FF0000")  # 紅色
            blue_font = Font(color="0000FF")  # 藍色
            
            # 找到 "Base folder" 和 "狀態" 欄位的位置
            base_folder_col = None
            status_col = None
            for idx, col in enumerate(df.columns):
                if col == 'Base folder':
                    base_folder_col = idx + 1
                    # 設定深紅底白字
                    header_fill = PatternFill(start_color="C00000", end_color="C00000", fill_type="solid")
                    white_font = Font(color="FFFFFF", bold=True)
                    cell = worksheet.cell(row=1, column=base_folder_col)
                    cell.fill = header_fill
                    cell.font = white_font
                elif col == '狀態':
                    status_col = idx + 1
                    # 設定深紅底白字
                    header_fill = PatternFill(start_color="C00000", end_color="C00000", fill_type="solid")
                    white_font = Font(color="FFFFFF", bold=True)
                    cell = worksheet.cell(row=1, column=status_col)
                    cell.fill = header_fill
                    cell.font = white_font
            
            # 設定狀態欄位的文字顏色
            if status_col:
                for row_idx in range(2, len(df) + 2):
                    df_row_idx = row_idx - 2
                    if '狀態' in df.columns:
                        status_value = df.iloc[df_row_idx]['狀態']
                        if status_value == '刪除':
                            worksheet.cell(row=row_idx, column=status_col).font = red_font
                        elif status_value == '新增':
                            worksheet.cell(row=row_idx, column=status_col).font = blue_font
        
        # version_diff 頁籤的特定格式
        if version_diff and 'version_diff' in writer.sheets:
            worksheet = writer.sheets['version_diff']
            df = pd.DataFrame(version_diff)
            
            from openpyxl.cell.text import InlineFont
            from openpyxl.cell.rich_text import TextBlock, CellRichText
            
            # 設定深紅底白字的標題
            header_fill = PatternFill(start_color="C00000", end_color="C00000", fill_type="solid")
            white_font = Font(color="FFFFFF", bold=True)
            red_font = Font(color="FF0000")
            
            # 找到需要格式化的欄位位置
            target_columns = ['base_content', 'compare_content']
            column_indices = {}
            
            for idx, col in enumerate(df.columns):
                if col in target_columns:
                    column_indices[col] = idx + 1  # 修正：改為 idx + 1
            
            # 設定標題為深紅底白字（只有 base_content 和 compare_content）
            for col_name, col_idx in column_indices.items():
                cell = worksheet.cell(row=1, column=col_idx)
                cell.fill = header_fill
                cell.font = white_font
            
            # 處理內容，根據檔案類型標記不同部分
            for row_idx in range(2, len(df) + 2):
                # 讀取實際的值
                df_row_idx = row_idx - 2  # DataFrame 的索引
                
                # 取得檔案類型
                file_type = ''
                if 'file_type' in df.columns:
                    file_type = df.iloc[df_row_idx]['file_type']
                
                # 取得 base_content 和 compare_content
                base_content = ''
                compare_content = ''
                
                if 'base_content' in df.columns:
                    base_content = df.iloc[df_row_idx]['base_content']
                if 'compare_content' in df.columns:
                    compare_content = df.iloc[df_row_idx]['compare_content']
                
                # 檢查是否為檔案不存在的情況
                if str(base_content) == '(檔案不存在)':
                    # base_content 為紅字
                    if 'base_content' in column_indices:
                        worksheet.cell(row=row_idx, column=column_indices['base_content']).font = red_font
                        worksheet.cell(row=row_idx, column=column_indices['base_content']).value = base_content
                        
                    # 如果 compare_content 是 "(檔案存在)"，保持黑字
                    if 'compare_content' in column_indices and str(compare_content) == '(檔案存在)':
                        worksheet.cell(row=row_idx, column=column_indices['compare_content']).value = compare_content
                        
                elif str(compare_content) == '(檔案不存在)':
                    # compare_content 為紅字
                    if 'compare_content' in column_indices:
                        worksheet.cell(row=row_idx, column=column_indices['compare_content']).font = red_font
                        worksheet.cell(row=row_idx, column=column_indices['compare_content']).value = compare_content
                        
                    # 如果 base_content 是 "(檔案存在)"，保持黑字
                    if 'base_content' in column_indices and str(base_content) == '(檔案存在)':
                        worksheet.cell(row=row_idx, column=column_indices['base_content']).value = base_content
                else:
                    # 根據檔案類型和內容選擇處理方式
                    if str(file_type).lower() == 'f_version.txt' and base_content and compare_content:
                        # F_Version.txt: 處理 P_GIT_xxx 行
                        if str(base_content).startswith('P_GIT_') and str(compare_content).startswith('P_GIT_'):
                            self._format_f_version_content(worksheet, row_idx, column_indices, base_content, compare_content)
                        else:
                            # 其他行不需要特殊格式化
                            pass  # 加上 pass
                    elif 'F_HASH:' in str(base_content) or 'F_HASH:' in str(compare_content):
                        # Version.txt with F_HASH
                        self._format_f_hash_content(worksheet, row_idx, column_indices, base_content, compare_content)
                    elif ':' in str(base_content) or ':' in str(compare_content):
                        # Other Version.txt with colon
                        self._format_colon_content(worksheet, row_idx, column_indices, base_content, compare_content)

    def _format_f_version_content(self, worksheet, row_idx, column_indices, base_content, compare_content):
        """格式化 F_Version.txt 內容 - 只標記 git hash 和 svn number"""
        from openpyxl.cell.text import InlineFont
        from openpyxl.cell.rich_text import TextBlock, CellRichText
        
        # 處理 base_content
        if 'base_content' in column_indices and base_content:
            base_parts = str(base_content).split(';')
            compare_parts = str(compare_content).split(';') if compare_content else []
            
            rich_text_parts = []
            for i, part in enumerate(base_parts):
                if i > 0:
                    rich_text_parts.append(TextBlock(InlineFont(color="000000"), ";"))
                
                # 只有第3、4部分（索引3和4，即git hash 和 svn number）需要比較
                if i in [3, 4] and i < len(compare_parts) and part != compare_parts[i]:
                    rich_text_parts.append(TextBlock(InlineFont(color="FF0000"), part))
                else:
                    rich_text_parts.append(TextBlock(InlineFont(color="000000"), part))
            
            cell_rich_text = CellRichText(rich_text_parts)
            worksheet.cell(row=row_idx, column=column_indices['base_content']).value = cell_rich_text
        
        # 處理 compare_content
        if 'compare_content' in column_indices and compare_content:
            base_parts = str(base_content).split(';') if base_content else []
            compare_parts = str(compare_content).split(';')
            
            rich_text_parts = []
            for i, part in enumerate(compare_parts):
                if i > 0:
                    rich_text_parts.append(TextBlock(InlineFont(color="000000"), ";"))
                
                # 只有第3、4部分（索引3和4，即git hash 和 svn number）需要比較
                if i in [3, 4] and i < len(base_parts) and part != base_parts[i]:
                    rich_text_parts.append(TextBlock(InlineFont(color="FF0000"), part))
                else:
                    rich_text_parts.append(TextBlock(InlineFont(color="000000"), part))
            
            cell_rich_text = CellRichText(rich_text_parts)
            worksheet.cell(row=row_idx, column=column_indices['compare_content']).value = cell_rich_text

    def _format_f_hash_content(self, worksheet, row_idx, column_indices, base_content, compare_content):
        """格式化 F_HASH 內容 - 只標記 hash 值"""
        from openpyxl.cell.text import InlineFont
        from openpyxl.cell.rich_text import TextBlock, CellRichText
        
        # 處理 base_content
        if 'base_content' in column_indices and base_content and 'F_HASH:' in str(base_content):
            parts = str(base_content).split('F_HASH:', 1)
            if len(parts) == 2:
                hash1 = parts[1].strip()
                hash2 = ''
                if compare_content and 'F_HASH:' in str(compare_content):
                    compare_parts = str(compare_content).split('F_HASH:', 1)
                    if len(compare_parts) == 2:
                        hash2 = compare_parts[1].strip()
                
                rich_text_parts = [
                    TextBlock(InlineFont(color="000000"), "F_HASH: "),
                    TextBlock(InlineFont(color="FF0000" if hash1 != hash2 else "000000"), hash1)
                ]
                
                cell_rich_text = CellRichText(rich_text_parts)
                worksheet.cell(row=row_idx, column=column_indices['base_content']).value = cell_rich_text
        
        # 處理 compare_content
        if 'compare_content' in column_indices and compare_content and 'F_HASH:' in str(compare_content):
            parts = str(compare_content).split('F_HASH:', 1)
            if len(parts) == 2:
                hash2 = parts[1].strip()
                hash1 = ''
                if base_content and 'F_HASH:' in str(base_content):
                    base_parts = str(base_content).split('F_HASH:', 1)
                    if len(base_parts) == 2:
                        hash1 = base_parts[1].strip()
                
                rich_text_parts = [
                    TextBlock(InlineFont(color="000000"), "F_HASH: "),
                    TextBlock(InlineFont(color="FF0000" if hash1 != hash2 else "000000"), hash2)
                ]
                
                cell_rich_text = CellRichText(rich_text_parts)
                worksheet.cell(row=row_idx, column=column_indices['compare_content']).value = cell_rich_text

    def _format_colon_content(self, worksheet, row_idx, column_indices, base_content, compare_content):
        """格式化包含冒號的內容 - 只標記值的部分"""
        from openpyxl.cell.text import InlineFont
        from openpyxl.cell.rich_text import TextBlock, CellRichText
        
        # 處理 base_content
        if 'base_content' in column_indices and base_content and ':' in str(base_content):
            parts = str(base_content).split(':', 1)
            if len(parts) == 2:
                key = parts[0]
                value1 = parts[1].strip()
                value2 = ''
                
                if compare_content and ':' in str(compare_content):
                    compare_parts = str(compare_content).split(':', 1)
                    if len(compare_parts) == 2 and compare_parts[0] == key:
                        value2 = compare_parts[1].strip()
                
                rich_text_parts = [
                    TextBlock(InlineFont(color="000000"), key + ": "),
                    TextBlock(InlineFont(color="FF0000" if value1 != value2 else "000000"), value1)
                ]
                
                cell_rich_text = CellRichText(rich_text_parts)
                worksheet.cell(row=row_idx, column=column_indices['base_content']).value = cell_rich_text
        
        # 處理 compare_content
        if 'compare_content' in column_indices and compare_content and ':' in str(compare_content):
            parts = str(compare_content).split(':', 1)
            if len(parts) == 2:
                key = parts[0]
                value2 = parts[1].strip()
                value1 = ''
                
                if base_content and ':' in str(base_content):
                    base_parts = str(base_content).split(':', 1)
                    if len(base_parts) == 2 and base_parts[0] == key:
                        value1 = base_parts[1].strip()
                
                rich_text_parts = [
                    TextBlock(InlineFont(color="000000"), key + ": "),
                    TextBlock(InlineFont(color="FF0000" if value1 != value2 else "000000"), value2)
                ]
                
                cell_rich_text = CellRichText(rich_text_parts)
                worksheet.cell(row=row_idx, column=column_indices['compare_content']).value = cell_rich_text
                        
    def compare_module_folders(self, module_path: str, base_folder_suffix: str = None) -> Dict[str, Any]:
        """
        比較模組下的兩個資料夾
        
        Args:
            module_path: 模組路徑
            base_folder_suffix: 指定要作為 base 的資料夾後綴（如 "wave", "premp"）
            
        Returns:
            比較結果
        """
        results = {
            'module': os.path.basename(module_path),
            'revision_diff': [],
            'branch_error': [],
            'lost_project': [],
            'text_file_differences': {},
            'base_folder': '',
            'compare_folder': ''
        }
        
        try:
            # 取得模組下的所有資料夾
            folders = [f for f in os.listdir(module_path) 
                      if os.path.isdir(os.path.join(module_path, f))]
            
            if len(folders) < 2:
                return results
            
            # 根據使用者選擇決定 base 和 compare 資料夾
            base_folder = None
            compare_folder = None
            
            if base_folder_suffix:
                # 尋找符合後綴的資料夾作為 base
                for folder in folders:
                    if folder.endswith(f"-{base_folder_suffix}"):
                        base_folder = folder
                        break
                    elif base_folder_suffix == "default" and not any(folder.endswith(suffix) for suffix in ["-wave", "-premp", "-wave.backup"]):
                        base_folder = folder
                        break
                        
                # 找出 compare 資料夾（另一個資料夾）
                if base_folder:
                    for folder in folders:
                        if folder != base_folder:
                            compare_folder = folder
                            break
            
            # 如果沒有找到或沒有指定，使用前兩個資料夾
            if not base_folder or not compare_folder:
                base_folder = folders[0]
                compare_folder = folders[1]
            
            folder1_path = os.path.join(module_path, base_folder)
            folder2_path = os.path.join(module_path, compare_folder)
            
            self.logger.info(f"比較資料夾: {base_folder} (base) vs {compare_folder} (compare)")
            results['base_folder'] = base_folder
            results['compare_folder'] = compare_folder
            
            # 比較每個目標檔案
            for target_file in config.TARGET_FILES:
                file1 = utils.find_file_case_insensitive(folder1_path, target_file)
                file2 = utils.find_file_case_insensitive(folder2_path, target_file)
                
                if file1 and file2:
                    if target_file.lower() == 'manifest.xml':
                        # 比較 manifest.xml（傳入 module_path）
                        revision_diff, branch_error, lost_project = self._compare_manifest_files(
                            file1, file2, results['module'], base_folder, compare_folder, module_path
                        )
                        results['revision_diff'] = revision_diff
                        results['branch_error'] = branch_error
                        results['lost_project'] = lost_project
                    else:
                        # 比較文字檔案（使用新的比較規則）
                        differences = self._compare_text_files(file1, file2, target_file)
                        if differences:
                            results['text_file_differences'][target_file] = differences
                            
                            # 為整合報表準備版本檔案差異資料
                            if target_file.lower() in ['version.txt', 'f_version.txt']:
                                for diff in differences:
                                    version_diff_item = {
                                        'module': self._extract_simple_module_name(module),
                                        'location_path': module_path,
                                        'base_folder': base_folder,
                                        'compare_folder': compare_folder,
                                        'file_type': target_file,  
                                        'base_content': diff.get('file1', ''), 
                                        'compare_content': diff.get('file2', ''),  
                                        'org_content': diff.get('content1', '')  
                                    }
                                    results['version_diffs'].append(version_diff_item)
                else:
                    self.logger.warning(f"檔案 {target_file} 在一個或兩個資料夾中都不存在")
                    
        except Exception as e:
            self.logger.error(f"比較模組資料夾失敗: {str(e)}")
            
        return results
        
    def compare_all_modules(self, source_dir: str, output_dir: str = None, compare_mode: str = None) -> List[str]:
        """
        比較所有模組
        
        Args:
            source_dir: 來源目錄
            output_dir: 輸出目錄
            compare_mode: 比對模式
            
        Returns:
            產生的比較報表檔案列表
        """
        output_dir = output_dir or source_dir
        compare_files = []
        
        # 用於整合報表的資料
        all_revision_diff = []
        all_branch_error = []
        all_lost_project = []
        all_version_diff = []  # 新增：版本檔案差異
        cannot_compare_modules = []  # 記錄無法比對的模組
        
        try:
            # 取得所有模組
            actual_modules = self._get_all_modules(source_dir)
            self.logger.info(f"找到 {len(actual_modules)} 個模組")
            
            # 處理每個模組
            for top_dir, module, module_path in actual_modules:
                # 組合完整模組名稱
                full_module = f"{top_dir}/{module}" if top_dir else module
                
                # 根據比對模式找出需要比對的資料夾
                base_folder, compare_folder, missing_info = self._find_folders_for_comparison(
                    module_path, compare_mode
                )
                
                if not base_folder or not compare_folder:
                    # 記錄無法比對的原因
                    folders = [f for f in os.listdir(module_path) 
                              if os.path.isdir(os.path.join(module_path, f))]
                    
                    # 如果有資料夾，使用第一個資料夾的完整路徑
                    if folders:
                        full_path = os.path.join(module_path, folders[0])
                    else:
                        full_path = module_path
                        
                    self.logger.warning(f"模組 {module} 無法進行比對")
                    cannot_compare_modules.append({
                        'SN': len(cannot_compare_modules) + 1,
                        'module': module,  # 簡化的模組名稱
                        'location_path': module_path,
                        'folder_count': len(folders),
                        'folders': ', '.join(folders) if folders else '無資料夾',
                        'path': full_path,
                        'reason': missing_info
                    })
                    continue
                
                # 比較模組
                results = self._compare_specific_folders(
                    module_path, base_folder, compare_folder, full_module, compare_mode
                )
                
                # 收集所有資料（模組名稱已經在 _compare_manifest_files 中簡化）
                all_revision_diff.extend(results['revision_diff'])
                all_branch_error.extend(results['branch_error'])
                all_lost_project.extend(results['lost_project'])
                
                # 收集版本檔案差異
                if 'version_diffs' in results:
                    all_version_diff.extend(results['version_diffs'])
                
                # 如果有比較結果，寫入模組報表
                if any([results['revision_diff'], results['branch_error'], results['lost_project']]):
                    # 建立輸出路徑，保持目錄結構
                    if top_dir:
                        module_output_dir = os.path.join(output_dir, top_dir, module)
                    else:
                        module_output_dir = os.path.join(output_dir, module)
                    
                    # 確保目錄存在
                    if not os.path.exists(module_output_dir):
                        os.makedirs(module_output_dir)
                    
                    # 生成檔案名稱
                    compare_filename = self._generate_compare_filename(
                        module, base_folder, compare_folder
                    )
                        
                    report_file = self._write_module_compare_report(
                        module, results, module_output_dir, compare_filename
                    )
                    if report_file:
                        compare_files.append(report_file)
                        
            # 寫入整合報表（包含無法比對的模組）
            if any([all_revision_diff, all_branch_error, all_lost_project, all_version_diff, cannot_compare_modules]):
                self._write_all_compare_report(
                    all_revision_diff, all_branch_error, all_lost_project, 
                    all_version_diff, cannot_compare_modules, output_dir
                )
                
            return compare_files
            
        except Exception as e:
            self.logger.error(f"比較所有模組失敗: {str(e)}")
            raise
            
    def _find_folders_for_comparison(self, module_path: str, compare_mode: str) -> Tuple[str, str, str]:
        """
        根據比對模式找出需要比對的資料夾
        
        Args:
            module_path: 模組路徑
            compare_mode: 比對模式
            
        Returns:
            (base_folder, compare_folder, missing_info)
        """
        folders = [f for f in os.listdir(module_path) 
                   if os.path.isdir(os.path.join(module_path, f))]
        
        # 判斷是 RDDB 還是 DB 格式
        is_rddb_format = any(folder.startswith('RDDB-') for folder in folders)
        
        # 根據資料夾名稱分類
        master_folder = None
        premp_folder = None
        wave_folder = None
        backup_folder = None
        
        for folder in folders:
            if folder.endswith('-wave.backup'):
                backup_folder = folder
            elif folder.endswith('-wave'):
                wave_folder = folder
            elif folder.endswith('-premp'):
                premp_folder = folder
            else:
                # 沒有後綴的是 master
                if is_rddb_format and folder.startswith('RDDB-'):
                    master_folder = folder
                elif not is_rddb_format and folder.startswith('DB'):
                    master_folder = folder
        
        # 根據比對模式決定要比對的資料夾
        base_folder = None
        compare_folder = None
        missing_info = ""
        
        if compare_mode == 'master_vs_premp':
            base_folder = master_folder
            compare_folder = premp_folder
            if not master_folder:
                if is_rddb_format:
                    missing_info = "缺少 master 資料夾 (RDDB-XXX)"
                else:
                    missing_info = "缺少 master 資料夾 (DBXXXX)"
            elif not premp_folder:
                if is_rddb_format:
                    missing_info = "缺少 premp 資料夾 (RDDB-XXX-premp)"
                else:
                    missing_info = "缺少 premp 資料夾 (DBXXXX-premp)"
                
        elif compare_mode == 'premp_vs_wave':
            base_folder = premp_folder
            compare_folder = wave_folder
            if not premp_folder:
                if is_rddb_format:
                    missing_info = "缺少 premp 資料夾 (RDDB-XXX-premp)"
                else:
                    missing_info = "缺少 premp 資料夾 (DBXXXX-premp)"
            elif not wave_folder:
                if is_rddb_format:
                    missing_info = "缺少 wave 資料夾 (RDDB-XXX-wave)"
                else:
                    missing_info = "缺少 wave 資料夾 (DBXXXX-wave)"
                
        elif compare_mode == 'wave_vs_backup':
            base_folder = wave_folder
            compare_folder = backup_folder
            if not wave_folder:
                if is_rddb_format:
                    missing_info = "缺少 wave 資料夾 (RDDB-XXX-wave)"
                else:
                    missing_info = "缺少 wave 資料夾 (DBXXXX-wave)"
            elif not backup_folder:
                if is_rddb_format:
                    missing_info = "缺少 wave.backup 資料夾 (RDDB-XXX-wave.backup)"
                else:
                    missing_info = "缺少 wave.backup 資料夾 (DBXXXX-wave.backup)"
                
        elif compare_mode and compare_mode.startswith('manual_'):
            # 手動模式解析
            parts = compare_mode.split('_')
            if len(parts) >= 4:
                base_type = parts[1]
                compare_type = parts[3]
                
                # 根據類型找資料夾
                type_to_folder = {
                    'master': master_folder,
                    'premp': premp_folder,
                    'wave': wave_folder,
                    'wave.backup': backup_folder
                }
                
                base_folder = type_to_folder.get(base_type)
                compare_folder = type_to_folder.get(compare_type)
                
                if not base_folder:
                    missing_info = f"缺少 {base_type} 資料夾"
                elif not compare_folder:
                    missing_info = f"缺少 {compare_type} 資料夾"
        
        return base_folder, compare_folder, missing_info

    def _compare_specific_folders(self, module_path: str, base_folder: str, compare_folder: str, module: str, compare_mode: str = None) -> Dict[str, Any]:
        """
        比較指定的兩個資料夾
        """
        results = {
            'module': module,
            'revision_diff': [],
            'branch_error': [],
            'lost_project': [],
            'text_file_differences': {},
            'version_diffs': [],  # 新增版本檔案差異
            'base_folder': base_folder,
            'compare_folder': compare_folder
        }
        
        try:
            folder1_path = os.path.join(module_path, base_folder)
            folder2_path = os.path.join(module_path, compare_folder)
            
            self.logger.info(f"比較資料夾: {base_folder} (base) vs {compare_folder} (compare)")
            
            # 判斷是否為 DailyBuild
            is_daily_build = 'DailyBuild' in module_path
            
            # 比較每個目標檔案
            for target_file in config.TARGET_FILES:
                # 如果是 DailyBuild 的 Version.txt，跳過
                if is_daily_build and target_file.lower() == 'version.txt':
                    self.logger.info(f"跳過 DailyBuild 的 Version.txt 比對")
                    continue
                    
                file1 = utils.find_file_case_insensitive(folder1_path, target_file)
                file2 = utils.find_file_case_insensitive(folder2_path, target_file)
                
                if file1 and file2:
                    if target_file.lower() == 'manifest.xml':
                        # 比較 manifest.xml
                        revision_diff, branch_error, lost_project = self._compare_manifest_files(
                            file1, file2, module, base_folder, compare_folder, module_path, compare_mode
                        )
                        results['revision_diff'] = revision_diff
                        results['branch_error'] = branch_error
                        results['lost_project'] = lost_project
                    else:
                        # 比較文字檔案（使用新的比較規則）
                        differences = self._compare_text_files(file1, file2, target_file)
                        if differences:
                            results['text_file_differences'][target_file] = differences
                            
                            # 為整合報表準備版本檔案差異資料
                            if target_file.lower() in ['version.txt', 'f_version.txt']:
                                for diff in differences:
                                    version_diff_item = {
                                        'module': self._extract_simple_module_name(module),
                                        'location_path': module_path,
                                        'base_folder': base_folder,
                                        'compare_folder': compare_folder,
                                        'file_type': target_file,  # 保持為檔案類型名稱
                                        'base_content': diff.get('file1', ''),  # 差異行內容
                                        'compare_content': diff.get('file2', ''),  # 差異行內容
                                        'org_content': diff.get('content1', '')  # base 檔案的完整內容
                                    }
                                    results['version_diffs'].append(version_diff_item)
                elif file1 or file2:
                    # 只有一個檔案存在的情況
                    self.logger.warning(f"檔案 {target_file} 只在一個資料夾中存在")
                    
                    # 如果是 DailyBuild 的 Version.txt，跳過
                    if is_daily_build and target_file.lower() == 'version.txt':
                        continue
                        
                    if target_file.lower() in ['version.txt', 'f_version.txt']:
                        # 處理只有一個檔案的情況
                        if file1:
                            try:
                                with open(file1, 'r', encoding='utf-8', errors='ignore') as f:
                                    content1 = f.read()
                                version_diff_item = {
                                    'module': self._extract_simple_module_name(module),
                                    'location_path': module_path,
                                    'base_folder': base_folder,
                                    'compare_folder': compare_folder,
                                    'file_type': target_file,  # 保持為檔案類型名稱
                                    'base_content': '(檔案存在)',
                                    'compare_content': '(檔案不存在)',
                                    'org_content': content1
                                }
                                results['version_diffs'].append(version_diff_item)
                            except Exception as e:
                                self.logger.error(f"讀取檔案失敗 {file1}: {str(e)}")
                        elif file2:
                            try:
                                with open(file2, 'r', encoding='utf-8', errors='ignore') as f:
                                    content2 = f.read()
                                version_diff_item = {
                                    'module': self._extract_simple_module_name(module),
                                    'location_path': module_path,
                                    'base_folder': base_folder,
                                    'compare_folder': compare_folder,
                                    'file_type': target_file,  # 保持為檔案類型名稱
                                    'base_content': '(檔案不存在)',
                                    'compare_content': '(檔案存在)',
                                    'org_content': content2
                                }
                                results['version_diffs'].append(version_diff_item)
                            except Exception as e:
                                self.logger.error(f"讀取檔案失敗 {file2}: {str(e)}")
                else:
                    self.logger.warning(f"檔案 {target_file} 在兩個資料夾中都不存在")
                        
        except Exception as e:
            self.logger.error(f"比較資料夾失敗: {str(e)}")
            
        return results
        
    def _write_module_compare_report(self, module: str, results: Dict, output_dir: str, filename: str = None) -> str:
        """
        寫入單一模組的比較報表（與 all_compare.xlsx 相同格式）
        """
        try:
            import pandas as pd
            from openpyxl.styles import PatternFill, Font
            from openpyxl.worksheet.filters import FilterColumn, Filters
            
            # 使用自訂檔名或預設檔名
            output_file = os.path.join(output_dir, filename or f"{module}_compare.xlsx")
            
            # 準備各頁籤的資料
            revision_diff = results.get('revision_diff', [])
            branch_error = results.get('branch_error', [])
            lost_project = results.get('lost_project', [])
            version_diffs = results.get('version_diffs', [])
            
            # 重新編號
            for i, item in enumerate(revision_diff, 1):
                item['SN'] = i
            for i, item in enumerate(branch_error, 1):
                item['SN'] = i
            for i, item in enumerate(lost_project, 1):
                item['SN'] = i
            for i, item in enumerate(version_diffs, 1):
                item['SN'] = i
            
            with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
                # revision_diff 頁籤
                if revision_diff:
                    df = pd.DataFrame(revision_diff)
                    columns_order = ['SN', 'module', 'location_path', 'base_folder', 'compare_folder', 'name', 'path', 
                                'base_short', 'base_revision', 'compare_short', 'compare_revision',
                                'base_upstream', 'compare_upstream', 'base_dest-branch', 'compare_dest-branch',
                                'base_link', 'compare_link']
                    columns_order = [col for col in columns_order if col in df.columns]
                    df = df[columns_order]
                    df.to_excel(writer, sheet_name='revision_diff', index=False)
                else:
                    # 即使沒有資料也建立空的頁籤
                    pd.DataFrame(columns=['SN', 'module', 'location_path', 'base_folder', 'compare_folder', 'name', 'path',
                                        'base_short', 'base_revision', 'compare_short', 'compare_revision']).to_excel(
                        writer, sheet_name='revision_diff', index=False)
                
                # branch_error 頁籤
                if branch_error:
                    df = pd.DataFrame(branch_error)
                    columns_order = ['SN', 'module', 'location_path', 'base_folder', 'compare_folder', 'name', 'path', 
                                'revision_short', 'revision', 'upstream', 'dest-branch', 
                                'compare_link', 'problem', 'has_wave']
                    columns_order = [col for col in columns_order if col in df.columns]
                    df = df[columns_order]
                    
                    # 將 has_wave = N 的資料排在前面
                    df_sorted = df.sort_values('has_wave', ascending=True)
                    df_sorted.to_excel(writer, sheet_name='branch_error', index=False)
                else:
                    pd.DataFrame(columns=['SN', 'module', 'location_path', 'base_folder', 'compare_folder', 'name', 'path',
                                        'problem', 'has_wave']).to_excel(
                        writer, sheet_name='branch_error', index=False)
                
                # lost_project 頁籤
                if lost_project:
                    df = pd.DataFrame(lost_project)
                    columns_order = ['SN', 'Base folder', '狀態', 'module', 'location_path', 'folder', 'name', 'path', 
                                'upstream', 'dest-branch', 'revision', 'link']
                    columns_order = [col for col in columns_order if col in df.columns]
                    df = df[columns_order]
                    df.to_excel(writer, sheet_name='lost_project', index=False)
                else:
                    pd.DataFrame(columns=['SN', 'Base folder', '狀態', 'module', 'location_path', 'folder', 'name', 'path']).to_excel(
                        writer, sheet_name='lost_project', index=False)
                
                # version_diff 頁籤 - 修正：加入 org_content
                if version_diffs:
                    df = pd.DataFrame(version_diffs)
                    # 確保欄位順序正確，org_content 在最後
                    columns_order = ['SN', 'module', 'location_path', 'base_folder', 'compare_folder', 'file_type', 
                                'base_content', 'compare_content', 'org_content']  # 加入 org_content
                    columns_order = [col for col in columns_order if col in df.columns]
                    df = df[columns_order]
                    df.to_excel(writer, sheet_name='version_diff', index=False)
                else:
                    pd.DataFrame(columns=['SN', 'module', 'location_path', 'base_folder', 'compare_folder', 'file_type',
                                        'base_content', 'compare_content', 'org_content']).to_excel(  # 加入 org_content
                        writer, sheet_name='version_diff', index=False)
                
                # 先格式化所有工作表（基本格式）
                for sheet_name in writer.sheets:
                    worksheet = writer.sheets[sheet_name]
                    self.excel_handler._format_worksheet(worksheet)
                
                # 套用特定欄位的格式和篩選
                self._apply_special_formatting_and_filters(writer, revision_diff, branch_error, 
                                                    lost_project, version_diffs)
                        
            self.logger.info(f"成功寫入比較報表: {output_file}")
            return output_file
            
        except Exception as e:
            self.logger.error(f"寫入模組比較報表失敗: {str(e)}")
            return None
            
    def _write_all_compare_report(self, revision_diff: List[Dict], branch_error: List[Dict],
                             lost_project: List[Dict], version_diff: List[Dict],
                             cannot_compare_modules: List[Dict], output_dir: str) -> str:
        """
        寫入整合比較報表（包含所有比較結果）
        """
        try:
            import pandas as pd
            from openpyxl.styles import PatternFill, Font
            from openpyxl.worksheet.filters import FilterColumn, Filters
            
            # 確保輸出目錄存在
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
                
            output_file = os.path.join(output_dir, "all_compare.xlsx")
            
            # 重新編號
            for i, item in enumerate(revision_diff, 1):
                item['SN'] = i
            for i, item in enumerate(branch_error, 1):
                item['SN'] = i
            for i, item in enumerate(lost_project, 1):
                item['SN'] = i
            for i, item in enumerate(version_diff, 1):
                item['SN'] = i
            
            with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
                # revision_diff 頁籤（只在有資料時產生）
                if revision_diff:
                    df = pd.DataFrame(revision_diff)
                    # 調整欄位順序
                    columns_order = ['SN', 'module', 'location_path', 'base_folder', 'compare_folder', 'name', 'path', 
                                'base_short', 'base_revision', 'compare_short', 'compare_revision',
                                'base_upstream', 'compare_upstream', 'base_dest-branch', 'compare_dest-branch',
                                'base_link', 'compare_link']
                    columns_order = [col for col in columns_order if col in df.columns]
                    df = df[columns_order]
                    df.to_excel(writer, sheet_name='revision_diff', index=False)
                
                # branch_error 頁籤（只在有資料時產生）
                if branch_error:
                    df = pd.DataFrame(branch_error)
                    # 調整欄位順序
                    columns_order = ['SN', 'module', 'location_path', 'base_folder', 'compare_folder', 'name', 'path', 
                                'revision_short', 'revision', 'upstream', 'dest-branch', 
                                'compare_link', 'problem', 'has_wave']
                    columns_order = [col for col in columns_order if col in df.columns]
                    df = df[columns_order]
                    
                    # 將 has_wave = N 的資料排在前面
                    df_sorted = df.sort_values('has_wave', ascending=True)
                    df_sorted.to_excel(writer, sheet_name='branch_error', index=False)
                
                # lost_project 頁籤（只在有資料時產生）
                if lost_project:
                    df = pd.DataFrame(lost_project)
                    # 調整欄位順序
                    columns_order = ['SN', 'Base folder', '狀態', 'module', 'location_path', 'folder', 'name', 'path', 
                                'upstream', 'dest-branch', 'revision', 'link']
                    columns_order = [col for col in columns_order if col in df.columns]
                    df = df[columns_order]
                    df.to_excel(writer, sheet_name='lost_project', index=False)
                
                # version_diff 頁籤
                if version_diff:
                    df = pd.DataFrame(version_diff)
                    # 移除 module_path 欄位
                    if 'module_path' in df.columns:
                        df = df.drop('module_path', axis=1)
                    # 移除 is_different 欄位（如果存在）
                    if 'is_different' in df.columns:
                        df = df.drop('is_different', axis=1)
                    
                    # 確保欄位順序正確
                    columns_order = ['SN', 'module', 'location_path', 'base_folder', 'compare_folder', 'file_type', 
                                'base_content', 'compare_content', 'org_content']
                    
                    # 只保留存在的欄位
                    columns_order = [col for col in columns_order if col in df.columns]
                    
                    # 重新排序欄位
                    df = df.reindex(columns=columns_order)
                    
                    df.to_excel(writer, sheet_name='version_diff', index=False)
                
                # 無法比對頁籤（只在有資料時產生）
                if cannot_compare_modules:
                    df = pd.DataFrame(cannot_compare_modules)
                    columns_order = ['SN', 'module', 'location_path', 'folder_count', 'folders', 'path', 'reason']
                    columns_order = [col for col in columns_order if col in df.columns]
                    df = df[columns_order]
                    df.to_excel(writer, sheet_name='無法比對', index=False)
                
                # 先格式化所有工作表（基本格式）
                for sheet_name in writer.sheets:
                    worksheet = writer.sheets[sheet_name]
                    self.excel_handler._format_worksheet(worksheet)
                
                # 套用特定欄位的格式和篩選
                self._apply_special_formatting_and_filters(writer, revision_diff, branch_error, 
                                                       lost_project, version_diff)
                        
            self.logger.info(f"成功寫入整合報表: {output_file}")
            return output_file
            
        except Exception as e:
            self.logger.error(f"寫入整合報表失敗: {str(e)}")
            raise    