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
            return f"{base_url}{name}/+log/refs/heads/{branch}"
        return ""
        
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
        
        Args:
            file1: 第一個檔案路徑（base）
            file2: 第二個檔案路徑（compare）
            module: 模組名稱
            base_folder: base 資料夾名稱
            compare_folder: compare 資料夾名稱
            module_path: 模組完整路徑
            
        Returns:
            (revision_diff, branch_error, lost_project)
        """
        # 解析兩個檔案
        base_projects = self._parse_manifest_xml(file1)
        compare_projects = self._parse_manifest_xml(file2)
        
        # 1. 比較 revision 差異（移除 has_wave）
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
                        'module': module,
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
        
        # 2. 檢查分支命名錯誤（新增 folders 和 module_path）
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
                    branch_error.append({
                        'SN': sn,
                        'module': module,
                        'name': compare_proj['name'],
                        'path': compare_proj['path'],
                        'revision_short': self._shorten_hash(revision),
                        'revision': revision,
                        'upstream': upstream,
                        'dest-branch': dest_branch,
                        'check_keyword': check_keyword,
                        'folders': f"{base_folder} vs {compare_folder}",
                        'module_path': module_path if module_path else '',
                        'compare_link': self._generate_link(compare_proj)
                    })
                    sn += 1
        
        # 3. 檢查缺少或新增的 project
        lost_project = []
        sn = 1
        
        # 檢查在 base 檔案中但不在 compare 檔案中的項目（缺少）
        for key, base_proj in base_projects.items():
            if key not in compare_projects:
                revision = base_proj.get('revision', '')
                lost_project.append({
                    'SN': sn,
                    '狀態': '刪除',
                    'module': module,
                    'name': base_proj['name'],
                    'path': base_proj['path'],
                    'upstream': base_proj.get('upstream', ''),
                    'dest-branch': base_proj.get('dest-branch', ''),
                    'revision': revision
                })
                sn += 1
        
        # 檢查在 compare 檔案中但不在 base 檔案中的項目（新增）
        for key, compare_proj in compare_projects.items():
            if key not in base_projects:
                revision = compare_proj.get('revision', '')
                lost_project.append({
                    'SN': sn,
                    '狀態': '新增',
                    'module': module,
                    'name': compare_proj['name'],
                    'path': compare_proj['path'],
                    'upstream': compare_proj.get('upstream', ''),
                    'dest-branch': compare_proj.get('dest-branch', ''),
                    'revision': revision
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
                - master_vs_premp: RDDB-XXX vs RDDB-XXX-premp
                - premp_vs_wave: RDDB-XXX-premp vs RDDB-XXX-wave
                - wave_vs_backup: RDDB-XXX-wave vs RDDB-XXX-wave.backup
                - manual_XXX_vs_YYY: 手動選擇的組合
            
        Returns:
            產生的比較報表檔案列表
        """
        output_dir = output_dir or source_dir
        compare_files = []
        
        # 用於整合報表的資料
        all_revision_diff = []
        all_branch_error = []
        all_lost_project = []
        cannot_compare_modules = []  # 記錄無法比對的模組
        
        try:
            # 取得所有模組資料夾
            modules = [d for d in os.listdir(source_dir) 
                    if os.path.isdir(os.path.join(source_dir, d))]
            
            self.logger.info(f"找到 {len(modules)} 個模組")
            
            for module in modules:
                module_path = os.path.join(source_dir, module)
                
                # 根據比對模式找出需要比對的資料夾
                base_folder, compare_folder, missing_info = self._find_folders_for_comparison(
                    module_path, compare_mode
                )
                
                if not base_folder or not compare_folder:
                    # 記錄無法比對的原因
                    self.logger.warning(f"模組 {module} 無法進行比對")
                    cannot_compare_modules.append({
                        'SN': len(cannot_compare_modules) + 1,
                        'module': module,
                        'folder_count': len(os.listdir(module_path)),
                        'folders': ', '.join(os.listdir(module_path)) if os.listdir(module_path) else '無資料夾',
                        'path': module_path,
                        'reason': missing_info
                    })
                    continue
                
                # 比較模組
                results = self._compare_specific_folders(
                    module_path, base_folder, compare_folder, module
                )
                
                # 收集所有資料
                all_revision_diff.extend(results['revision_diff'])
                all_branch_error.extend(results['branch_error'])
                all_lost_project.extend(results['lost_project'])
                
                # 如果有比較結果，寫入模組報表
                if any([results['revision_diff'], results['branch_error'], results['lost_project']]):
                    report_file = self._write_module_compare_report(
                        module, results, module_path
                    )
                    if report_file:
                        compare_files.append(report_file)
                        
            # 寫入整合報表（包含無法比對的模組）
            if any([all_revision_diff, all_branch_error, all_lost_project, cannot_compare_modules]):
                self._write_all_compare_report(
                    all_revision_diff, all_branch_error, all_lost_project, 
                    cannot_compare_modules, output_dir
                )
                
            return compare_files
            
        except Exception as e:
            self.logger.error(f"比較所有模組失敗: {str(e)}")
            raise

    def _compare_specific_folders(self, module_path: str, base_folder: str, compare_folder: str, module: str) -> Dict[str, Any]:
        """
        比較指定的兩個資料夾
        
        Args:
            module_path: 模組路徑
            base_folder: base 資料夾名稱
            compare_folder: compare 資料夾名稱
            module: 模組名稱
            
        Returns:
            比較結果
        """
        results = {
            'module': module,
            'revision_diff': [],
            'branch_error': [],
            'lost_project': [],
            'text_file_differences': {},
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
                else:
                    self.logger.warning(f"檔案 {target_file} 在一個或兩個資料夾中都不存在")
                    
        except Exception as e:
            self.logger.error(f"比較資料夾失敗: {str(e)}")
            
        return results
        
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
                # 假設沒有後綴的是 master
                if folder.startswith('RDDB-'):
                    master_folder = folder
        
        # 根據比對模式決定要比對的資料夾
        base_folder = None
        compare_folder = None
        missing_info = ""
        
        if compare_mode == 'master_vs_premp':
            base_folder = master_folder
            compare_folder = premp_folder
            if not master_folder:
                missing_info = "缺少 master 資料夾 (RDDB-XXX)"
            elif not premp_folder:
                missing_info = "缺少 premp 資料夾 (RDDB-XXX-premp)"
                
        elif compare_mode == 'premp_vs_wave':
            base_folder = premp_folder
            compare_folder = wave_folder
            if not premp_folder:
                missing_info = "缺少 premp 資料夾 (RDDB-XXX-premp)"
            elif not wave_folder:
                missing_info = "缺少 wave 資料夾 (RDDB-XXX-wave)"
                
        elif compare_mode == 'wave_vs_backup':
            base_folder = wave_folder
            compare_folder = backup_folder
            if not wave_folder:
                missing_info = "缺少 wave 資料夾 (RDDB-XXX-wave)"
            elif not backup_folder:
                missing_info = "缺少 wave.backup 資料夾 (RDDB-XXX-wave.backup)"
                
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
                    'name': item['name'],
                    'path': item['path'],
                    'upstream': item.get('base_upstream', ''),
                    'dest-branch': item.get('base_dest-branch', ''),
                    'revision': item['base_revision'],
                    'base_folder': results.get('base_folder', ''),
                    'compare_folder': results.get('compare_folder', '')
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
                             lost_project: List[Dict], cannot_compare_modules: List[Dict], 
                             output_dir: str) -> str:
        """
        寫入整合比較報表（包含所有比較結果）
        
        Args:
            revision_diff: revision 差異列表
            branch_error: 分支命名錯誤列表
            lost_project: 新增/刪除專案列表
            cannot_compare_modules: 無法比對的模組列表
            output_dir: 輸出目錄
            
        Returns:
            報表檔案路徑
        """
        try:
            import pandas as pd
            
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
                    df.to_excel(writer, sheet_name='revision_diff', index=False)
                
                # branch_error 頁籤（只在有資料時產生）
                if branch_error:
                    # 移除 check_keyword 欄位（內部使用，不顯示在報表中）
                    # 將 module_path 改名為 path_location
                    for item in branch_error:
                        if 'check_keyword' in item:
                            del item['check_keyword']
                        if 'module_path' in item:
                            item['path_location'] = item.pop('module_path')
                    df = pd.DataFrame(branch_error)
                    # 調整欄位順序
                    columns_order = ['SN', 'module', 'name', 'path', 'revision_short', 'revision', 
                                'upstream', 'dest-branch', 'folders', 'path_location', 'compare_link']
                    # 只選擇存在的欄位
                    columns_order = [col for col in columns_order if col in df.columns]
                    df = df[columns_order]
                    df.to_excel(writer, sheet_name='branch_error', index=False)
                
                # lost_project 頁籤（只在有資料時產生）
                if lost_project:
                    df = pd.DataFrame(lost_project)
                    df.to_excel(writer, sheet_name='lost_project', index=False)
                
                # 無法比對頁籤（即使沒有資料也產生，但通常有資料才會呼叫此方法）
                if cannot_compare_modules:
                    df = pd.DataFrame(cannot_compare_modules)
                    df.to_excel(writer, sheet_name='無法比對', index=False)
                else:
                    pd.DataFrame(columns=['SN', 'module', 'folder_count', 
                                        'folders', 'path', 'reason']).to_excel(
                        writer, sheet_name='無法比對', index=False)
                
                # 格式化所有工作表
                for sheet_name in writer.sheets:
                    worksheet = writer.sheets[sheet_name]
                    self.excel_handler._format_worksheet(worksheet)
                        
            self.logger.info(f"成功寫入整合報表: {output_file}")
            return output_file
            
        except Exception as e:
            self.logger.error(f"寫入整合報表失敗: {str(e)}")
            raise