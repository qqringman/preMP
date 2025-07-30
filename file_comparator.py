"""
檔案比較模組
處理 manifest.xml, F_Version.txt, Version.txt 的差異比較
"""
import os
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Tuple, Set
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
        
    def _compare_manifest_files(self, file1: str, file2: str, module: str, base_folder: str = None, compare_folder: str = None, module_path: str = None) -> Tuple[List[Dict], List[Dict], List[Dict]]:
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
                        'base_folder': base_folder,
                        'compare_folder': compare_folder,
                        'name': compare_proj['name'],
                        'path': compare_proj['path'],
                        'revision_short': self._shorten_hash(revision),
                        'revision': revision,
                        'upstream': upstream,
                        'dest-branch': dest_branch,
                        'check_keyword': check_keyword,
                        'module_path': module_path if module_path else '',
                        'compare_link': self._generate_link(compare_proj),
                        'has_wave': 'Y' if has_wave else 'N',
                        'problem': problem
                    })
                    sn += 1
        
        # 3. 檢查缺少或新增的 project（保持原有邏輯）
        lost_project = []
        sn = 1
        
        # 檢查在 base 檔案中但不在 compare 檔案中的項目（刪除）
        for key, base_proj in base_projects.items():
            if key not in compare_projects:
                revision = base_proj.get('revision', '')
                lost_project.append({
                    'SN': sn,
                    '狀態': '刪除',
                    'module': simple_module,
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
                    '狀態': '新增',
                    'module': simple_module,
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
        
    def _compare_text_files(self, file1: str, file2: str) -> List[Dict[str, Any]]:
        """
        比較兩個文字檔案
        
        Args:
            file1: 第一個檔案路徑
            file2: 第二個檔案路徑
            
        Returns:
            差異列表
        """
        differences = []
        
        try:
            with open(file1, 'r', encoding='utf-8') as f1:
                lines1 = f1.readlines()
            with open(file2, 'r', encoding='utf-8') as f2:
                lines2 = f2.readlines()
                
            # 比較每一行
            max_lines = max(len(lines1), len(lines2))
            
            for i in range(max_lines):
                line1 = lines1[i].strip() if i < len(lines1) else ''
                line2 = lines2[i].strip() if i < len(lines2) else ''
                
                if line1 != line2:
                    differences.append({
                        'line': i + 1,
                        'file1': line1,
                        'file2': line2
                    })
                    
        except Exception as e:
            self.logger.error(f"比較文字檔案失敗: {str(e)}")
            
        return differences
        
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
                        # 比較文字檔案
                        differences = self._compare_text_files(file1, file2)
                        if differences:
                            results['text_file_differences'][target_file] = differences
                            
                            # 為整合報表準備版本檔案差異資料
                            if target_file.lower() in ['version.txt', 'f_version.txt']:
                                # 讀取檔案內容
                                with open(file1, 'r', encoding='utf-8') as f:
                                    base_content = f.read().strip()
                                with open(file2, 'r', encoding='utf-8') as f:
                                    compare_content = f.read().strip()
                                
                                version_diff_item = {
                                    'module': self._extract_simple_module_name(results['module']),
                                    'base_folder': base_folder,
                                    'compare_folder': compare_folder,
                                    'file_type': target_file,
                                    'base_content': base_content,
                                    'compare_content': compare_content,
                                    'is_different': 'Y',
                                    'module_path': module_path if module_path else ''
                                }
                                
                                # 將版本差異加入結果
                                if 'version_diffs' not in results:
                                    results['version_diffs'] = []
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
            # 檢查是否有 PrebuildFW 或 DailyBuild 子目錄
            has_top_dirs = False
            actual_modules = []
            
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
                        'folder_count': len(folders),
                        'folders': ', '.join(folders) if folders else '無資料夾',
                        'path': full_path,
                        'reason': missing_info
                    })
                    continue
                
                # 比較模組
                results = self._compare_specific_folders(
                    module_path, base_folder, compare_folder, full_module
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
                        
                    report_file = self._write_module_compare_report(
                        module, results, module_output_dir
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

    def _compare_specific_folders(self, module_path: str, base_folder: str, compare_folder: str, module: str) -> Dict[str, Any]:
        """
        比較指定的兩個資料夾
        
        Args:
            module_path: 模組路徑
            base_folder: base 資料夾名稱
            compare_folder: compare 資料夾名稱
            module: 模組名稱（完整路徑）
            
        Returns:
            比較結果
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
            
            # 比較每個目標檔案
            for target_file in config.TARGET_FILES:
                file1 = utils.find_file_case_insensitive(folder1_path, target_file)
                file2 = utils.find_file_case_insensitive(folder2_path, target_file)
                
                if file1 and file2:
                    if target_file.lower() == 'manifest.xml':
                        # 比較 manifest.xml
                        revision_diff, branch_error, lost_project = self._compare_manifest_files(
                            file1, file2, module, base_folder, compare_folder, module_path
                        )
                        results['revision_diff'] = revision_diff
                        results['branch_error'] = branch_error
                        results['lost_project'] = lost_project
                    else:
                        # 比較文字檔案
                        differences = self._compare_text_files(file1, file2)
                        if differences:
                            results['text_file_differences'][target_file] = differences
                            
                            # 為整合報表準備版本檔案差異資料
                            if target_file.lower() in ['version.txt', 'f_version.txt']:
                                # 讀取檔案內容
                                try:
                                    with open(file1, 'r', encoding='utf-8', errors='ignore') as f:
                                        base_content = f.read().strip()
                                    with open(file2, 'r', encoding='utf-8', errors='ignore') as f:
                                        compare_content = f.read().strip()
                                    
                                    version_diff_item = {
                                        'module': self._extract_simple_module_name(module),
                                        'base_folder': base_folder,
                                        'compare_folder': compare_folder,
                                        'file_type': target_file,
                                        'base_content': base_content[:100] + '...' if len(base_content) > 100 else base_content,
                                        'compare_content': compare_content[:100] + '...' if len(compare_content) > 100 else compare_content,
                                        'is_different': 'Y',
                                        'module_path': module_path
                                    }
                                    results['version_diffs'].append(version_diff_item)
                                except Exception as e:
                                    self.logger.error(f"讀取版本檔案失敗: {str(e)}")
                else:
                    self.logger.warning(f"檔案 {target_file} 在一個或兩個資料夾中都不存在")
                    
        except Exception as e:
            self.logger.error(f"比較資料夾失敗: {str(e)}")
            
        return results
        
    def _write_module_compare_report(self, module: str, results: Dict, output_dir: str) -> str:
        """
        寫入單一模組的比較報表
        
        Args:
            module: 模組名稱
            results: 比較結果
            output_dir: 輸出目錄
            
        Returns:
            報表檔案路徑
        """
        try:
            # 準備不同頁籤的資料
            different_projects = []
            added_deleted_projects = results['lost_project']  # 這已經是正確格式
            
            # 將 revision_diff 轉換為舊格式（第一個頁籤）
            for item in results['revision_diff']:
                different_projects.append({
                    'SN': item['SN'],
                    'module': module,
                    'base_folder': results.get('base_folder', ''),
                    'compare_folder': results.get('compare_folder', ''),
                    'name': item['name'],
                    'path': item['path'],
                    'upstream': item.get('base_upstream', ''),
                    'dest-branch': item.get('base_dest-branch', ''),
                    'revision': item['base_revision']
                })
                
            # 寫入報表
            report_file = self.excel_handler.write_compare_report(
                module, different_projects, added_deleted_projects, output_dir
            )
            
            return report_file
            
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
            
            with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
                # revision_diff 頁籤（只在有資料時產生）
                if revision_diff:
                    df = pd.DataFrame(revision_diff)
                    # 調整欄位順序
                    columns_order = ['SN', 'module', 'base_folder', 'compare_folder', 'name', 'path', 
                                'base_short', 'base_revision', 'compare_short', 'compare_revision',
                                'base_upstream', 'compare_upstream', 'base_dest-branch', 'compare_dest-branch',
                                'base_link', 'compare_link']
                    columns_order = [col for col in columns_order if col in df.columns]
                    df = df[columns_order]
                    df.to_excel(writer, sheet_name='revision_diff', index=False)
                    
                    # 格式化 revision_diff 頁籤
                    worksheet = writer.sheets['revision_diff']
                    
                    # 設定深紅底標題的欄位
                    header_fill = PatternFill(start_color="C00000", end_color="C00000", fill_type="solid")  # 深紅色背景
                    white_font = Font(color="FFFFFF", bold=True)  # 白色粗體字
                    red_font = Font(color="FF0000")  # 紅色字體
                    
                    # 找到需要格式化的欄位位置
                    target_columns = ['base_short', 'base_revision', 'compare_short', 'compare_revision']
                    column_indices = {}
                    
                    for idx, col in enumerate(df.columns):
                        if col in target_columns:
                            column_indices[col] = idx + 1  # Excel 是 1-based
                    
                    # 設定標題為深紅底白字
                    for col_name, col_idx in column_indices.items():
                        cell = worksheet.cell(row=1, column=col_idx)
                        cell.fill = header_fill
                        cell.font = white_font
                    
                    # 設定內容為紅字
                    for row in range(2, len(df) + 2):  # 從第2行開始（第1行是標題）
                        for col_name, col_idx in column_indices.items():
                            worksheet.cell(row=row, column=col_idx).font = red_font
                
                # branch_error 頁籤（只在有資料時產生）
                if branch_error:
                    # 移除 check_keyword 欄位，將 module_path 改名為 path_location
                    for item in branch_error:
                        if 'check_keyword' in item:
                            del item['check_keyword']
                        if 'module_path' in item:
                            item['path_location'] = item.pop('module_path')
                    
                    df = pd.DataFrame(branch_error)
                    # 調整欄位順序，problem 和 has_wave 放在最後
                    columns_order = ['SN', 'module', 'base_folder', 'compare_folder', 'name', 'path', 
                                'revision_short', 'revision', 'upstream', 'dest-branch', 
                                'path_location', 'compare_link', 'problem', 'has_wave']
                    columns_order = [col for col in columns_order if col in df.columns]
                    df = df[columns_order]
                    
                    # 將 has_wave = N 的資料排在前面
                    df_sorted = df.sort_values('has_wave', ascending=True)
                    df_sorted.to_excel(writer, sheet_name='branch_error', index=False)
                    
                    # 格式化 branch_error 頁籤
                    worksheet = writer.sheets['branch_error']
                    
                    # 找到 "問題" 和 "has_wave" 欄位的位置
                    problem_col = None
                    has_wave_col = None
                    for idx, col in enumerate(df.columns):
                        if col == 'problem':
                            problem_col = idx + 1  # Excel 是 1-based
                        elif col == 'has_wave':
                            has_wave_col = idx + 1
                    
                    if problem_col:
                        # 設定 "problem" 標題為深紅底白字
                        header_fill = PatternFill(start_color="C00000", end_color="C00000", fill_type="solid")
                        white_font = Font(color="FFFFFF", bold=True)
                        cell = worksheet.cell(row=1, column=problem_col)
                        cell.fill = header_fill
                        cell.font = white_font
                    
                    # 設定自動篩選
                    worksheet.auto_filter.ref = worksheet.dimensions
                    
                    # 設定 has_wave 欄位的篩選條件為只顯示 "N"
                    if has_wave_col:
                        # 取得所有唯一的 has_wave 值
                        has_wave_values = df['has_wave'].unique().tolist()
                        
                        # 建立篩選器，只選擇 "N"
                        filter_column = FilterColumn(colId=has_wave_col - 1)
                        filter_column.filters = Filters()
                        filter_column.filters.filter = ['N']
                        
                        # 如果有 'Y' 值，需要將其設為隱藏
                        if 'Y' in has_wave_values:
                            # 找出所有 has_wave = 'Y' 的行並隱藏
                            for row_idx in range(2, len(df) + 2):  # 從第2行開始（第1行是標題）
                                if worksheet.cell(row=row_idx, column=has_wave_col).value == 'Y':
                                    worksheet.row_dimensions[row_idx].hidden = True
                        
                        # 將篩選器加入自動篩選
                        worksheet.auto_filter.filterColumn.append(filter_column)
                
                # lost_project 頁籤（只在有資料時產生）
                if lost_project:
                    df = pd.DataFrame(lost_project)
                    # 調整欄位順序
                    columns_order = ['SN', '狀態', 'module', 'folder', 'name', 'path', 
                                'upstream', 'dest-branch', 'revision', 'link']
                    columns_order = [col for col in columns_order if col in df.columns]
                    df = df[columns_order]
                    df.to_excel(writer, sheet_name='lost_project', index=False)
                    
                    # 格式化 lost_project 頁籤
                    worksheet = writer.sheets['lost_project']
                    
                    # 找到 "狀態" 欄位的位置
                    status_col = None
                    for idx, col in enumerate(df.columns):
                        if col == '狀態':
                            status_col = idx + 1  # Excel 是 1-based
                            break
                    
                    if status_col:
                        # 設定 "狀態" 標題為深紅底白字
                        header_fill = PatternFill(start_color="C00000", end_color="C00000", fill_type="solid")
                        white_font = Font(color="FFFFFF", bold=True)
                        cell = worksheet.cell(row=1, column=status_col)
                        cell.fill = header_fill
                        cell.font = white_font
                
                # version_diff 頁籤（只在有資料時產生）
                if version_diff:
                    # 重新編號
                    for i, item in enumerate(version_diff, 1):
                        item['SN'] = i
                    
                    df = pd.DataFrame(version_diff)
                    # 調整欄位順序
                    columns_order = ['SN', 'module', 'base_folder', 'compare_folder', 'file_type', 
                                'base_content', 'compare_content', 'is_different', 'module_path']
                    columns_order = [col for col in columns_order if col in df.columns]
                    df = df[columns_order]
                    df.to_excel(writer, sheet_name='version_diff', index=False)
                    
                    # 格式化 version_diff 頁籤
                    worksheet = writer.sheets['version_diff']
                    
                    # 找到 "is_different" 欄位的位置
                    diff_col = None
                    for idx, col in enumerate(df.columns):
                        if col == 'is_different':
                            diff_col = idx + 1  # Excel 是 1-based
                            break
                    
                    if diff_col:
                        # 設定 "is_different" 標題為深紅底白字
                        header_fill = PatternFill(start_color="C00000", end_color="C00000", fill_type="solid")
                        white_font = Font(color="FFFFFF", bold=True)
                        cell = worksheet.cell(row=1, column=diff_col)
                        cell.fill = header_fill
                        cell.font = white_font
                
                # 無法比對頁籤（只在有資料時產生）
                if cannot_compare_modules:
                    df = pd.DataFrame(cannot_compare_modules)
                    df.to_excel(writer, sheet_name='無法比對', index=False)
                
                # 先格式化所有工作表（基本格式）
                for sheet_name in writer.sheets:
                    worksheet = writer.sheets[sheet_name]
                    self.excel_handler._format_worksheet(worksheet)
                
                # 然後再套用特定欄位的格式（避免被覆蓋）
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
                
                # branch_error 頁籤的特定格式
                if branch_error and 'branch_error' in writer.sheets:
                    worksheet = writer.sheets['branch_error']
                    df = pd.DataFrame(branch_error)
                    
                    # 找到 "problem" 欄位的位置
                    for idx, col in enumerate(df.columns):
                        if col == 'problem':
                            problem_col = idx + 1
                            # 設定深紅底白字
                            header_fill = PatternFill(start_color="C00000", end_color="C00000", fill_type="solid")
                            white_font = Font(color="FFFFFF", bold=True)
                            cell = worksheet.cell(row=1, column=problem_col)
                            cell.fill = header_fill
                            cell.font = white_font
                            break
                
                # lost_project 頁籤的特定格式
                if lost_project and 'lost_project' in writer.sheets:
                    worksheet = writer.sheets['lost_project']
                    df = pd.DataFrame(lost_project)
                    
                    # 找到 "狀態" 欄位的位置
                    for idx, col in enumerate(df.columns):
                        if col == '狀態':
                            status_col = idx + 1
                            # 設定深紅底白字
                            header_fill = PatternFill(start_color="C00000", end_color="C00000", fill_type="solid")
                            white_font = Font(color="FFFFFF", bold=True)
                            cell = worksheet.cell(row=1, column=status_col)
                            cell.fill = header_fill
                            cell.font = white_font
                            break
                
                # version_diff 頁籤的特定格式
                if version_diff and 'version_diff' in writer.sheets:
                    worksheet = writer.sheets['version_diff']
                    df = pd.DataFrame(version_diff)
                    
                    # 找到 "is_different" 欄位的位置
                    for idx, col in enumerate(df.columns):
                        if col == 'is_different':
                            diff_col = idx + 1
                            # 設定深紅底白字
                            header_fill = PatternFill(start_color="C00000", end_color="C00000", fill_type="solid")
                            white_font = Font(color="FFFFFF", bold=True)
                            cell = worksheet.cell(row=1, column=diff_col)
                            cell.fill = header_fill
                            cell.font = white_font
                            break
                        
            self.logger.info(f"成功寫入整合報表: {output_file}")
            return output_file
            
        except Exception as e:
            self.logger.error(f"寫入整合報表失敗: {str(e)}")
            raise