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
        
    def _parse_manifest_xml(self, file_path: str) -> List[Dict[str, str]]:
        """
        解析 manifest.xml 檔案
        
        Args:
            file_path: XML 檔案路徑
            
        Returns:
            專案資訊列表
        """
        projects = []
        
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            
            # 尋找所有 project 元素
            for project in root.findall('.//project'):
                project_info = {}
                
                # 取得所有屬性
                for attr in ['name', 'path', 'revision', 'upstream', 'dest-branch', 
                           'remote', 'groups', 'clone-depth']:
                    project_info[attr] = project.get(attr, '')
                    
                projects.append(project_info)
                
            self.logger.info(f"成功解析 {file_path}，找到 {len(projects)} 個專案")
            
        except Exception as e:
            self.logger.error(f"解析 XML 檔案失敗 {file_path}: {str(e)}")
            
        return projects
        
    def _create_project_key(self, project: Dict[str, str]) -> str:
        """
        建立專案的主鍵
        
        Args:
            project: 專案資訊
            
        Returns:
            主鍵字串
        """
        key_values = []
        for key in config.MANIFEST_PRIMARY_KEYS:
            key_values.append(project.get(key, ''))
        return '|'.join(key_values)
        
    def _compare_manifest_files(self, file1: str, file2: str) -> Tuple[List[Dict], List[Dict]]:
        """
        比較兩個 manifest.xml 檔案
        
        Args:
            file1: 第一個檔案路徑
            file2: 第二個檔案路徑
            
        Returns:
            (不同的專案列表, 新增/刪除的專案列表)
        """
        # 解析兩個檔案
        projects1 = self._parse_manifest_xml(file1)
        projects2 = self._parse_manifest_xml(file2)
        
        # 建立專案字典（以主鍵為 key）
        projects_dict1 = {self._create_project_key(p): p for p in projects1}
        projects_dict2 = {self._create_project_key(p): p for p in projects2}
        
        # 找出不同的專案
        different_projects = []
        
        # 比較相同主鍵的專案
        for key in projects_dict1:
            if key in projects_dict2:
                proj1 = projects_dict1[key]
                proj2 = projects_dict2[key]
                
                # 比較所有屬性
                if proj1 != proj2:
                    different_projects.append({
                        'project_key': key,
                        'file1': proj1,
                        'file2': proj2,
                        'differences': self._find_differences(proj1, proj2)
                    })
                    
        # 找出新增/刪除的專案
        added_deleted_projects = []
        
        # 只在 file1 中的專案（已刪除）
        for key in projects_dict1:
            if key not in projects_dict2:
                added_deleted_projects.append({
                    'status': '刪除',
                    'project': projects_dict1[key]
                })
                
        # 只在 file2 中的專案（新增）
        for key in projects_dict2:
            if key not in projects_dict1:
                added_deleted_projects.append({
                    'status': '新增',
                    'project': projects_dict2[key]
                })
                
        return different_projects, added_deleted_projects
        
    def _find_differences(self, dict1: Dict, dict2: Dict) -> Dict[str, Tuple[str, str]]:
        """
        找出兩個字典的差異
        
        Args:
            dict1: 第一個字典
            dict2: 第二個字典
            
        Returns:
            差異字典 {key: (value1, value2)}
        """
        differences = {}
        all_keys = set(dict1.keys()) | set(dict2.keys())
        
        for key in all_keys:
            val1 = dict1.get(key, '')
            val2 = dict2.get(key, '')
            if val1 != val2:
                differences[key] = (val1, val2)
                
        return differences
        
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
        
    def compare_module_folders(self, module_path: str) -> Dict[str, Any]:
        """
        比較模組下的兩個資料夾
        
        Args:
            module_path: 模組路徑
            
        Returns:
            比較結果
        """
        results = {
            'module': os.path.basename(module_path),
            'manifest_different': [],
            'manifest_added_deleted': [],
            'text_file_differences': {}
        }
        
        try:
            # 取得模組下的所有資料夾
            folders = [f for f in os.listdir(module_path) 
                      if os.path.isdir(os.path.join(module_path, f))]
            
            if len(folders) < 2:
                self.logger.warning(f"模組 {module_path} 下的資料夾少於 2 個，無法比較")
                return results
                
            # 只比較前兩個資料夾
            folder1 = os.path.join(module_path, folders[0])
            folder2 = os.path.join(module_path, folders[1])
            
            self.logger.info(f"比較資料夾: {folders[0]} vs {folders[1]}")
            
            # 比較每個目標檔案
            for target_file in config.TARGET_FILES:
                file1 = utils.find_file_case_insensitive(folder1, target_file)
                file2 = utils.find_file_case_insensitive(folder2, target_file)
                
                if file1 and file2:
                    if target_file.lower() == 'manifest.xml':
                        # 比較 manifest.xml
                        different, added_deleted = self._compare_manifest_files(file1, file2)
                        results['manifest_different'] = different
                        results['manifest_added_deleted'] = added_deleted
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
        
    def compare_all_modules(self, source_dir: str, output_dir: str = None) -> List[str]:
        """
        比較所有模組
        
        Args:
            source_dir: 來源目錄
            output_dir: 輸出目錄
            
        Returns:
            產生的比較報表檔案列表
        """
        output_dir = output_dir or source_dir
        compare_files = []
        
        try:
            # 取得所有模組資料夾
            modules = [d for d in os.listdir(source_dir) 
                      if os.path.isdir(os.path.join(source_dir, d))]
            
            self.logger.info(f"找到 {len(modules)} 個模組")
            
            for module in modules:
                module_path = os.path.join(source_dir, module)
                
                # 比較模組
                results = self.compare_module_folders(module_path)
                
                # 準備報表資料
                different_projects = []
                added_deleted_projects = []
                
                # 處理 manifest 差異
                sn = 1
                for diff in results['manifest_different']:
                    project = diff['file1']
                    different_projects.append({
                        'SN': sn,
                        'module': module,
                        'name': project.get('name', ''),
                        'path': project.get('path', ''),
                        'upstream': project.get('upstream', ''),
                        'dest-branch': project.get('dest-branch', ''),
                        'revision': project.get('revision', '')
                    })
                    sn += 1
                    
                # 處理新增/刪除
                sn = 1
                for item in results['manifest_added_deleted']:
                    project = item['project']
                    added_deleted_projects.append({
                        'SN': sn,
                        '狀態': item['status'],
                        'module': module,
                        'name': project.get('name', ''),
                        'path': project.get('path', ''),
                        'upstream': project.get('upstream', ''),
                        'dest-branch': project.get('dest-branch', ''),
                        'revision': project.get('revision', '')
                    })
                    sn += 1
                    
                # 寫入模組比較報表
                if different_projects or added_deleted_projects:
                    report_file = self.excel_handler.write_compare_report(
                        module, different_projects, added_deleted_projects, module_path
                    )
                    compare_files.append(report_file)
                    
            # 合併所有報表
            if compare_files:
                self.excel_handler.merge_compare_reports(compare_files, output_dir)
                
            return compare_files
            
        except Exception as e:
            self.logger.error(f"比較所有模組失敗: {str(e)}")
            raise