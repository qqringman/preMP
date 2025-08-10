"""
功能三：去除版本號產生新的 manifest.xml - 增強版
透過另一張 manifest.xml 去除版本號後產生另一張 manifest.xml
新增：保存下載檔案 + 詳細差異分析
"""
import os
import xml.etree.ElementTree as ET
import pandas as pd
from typing import Dict, List, Any, Optional
import utils
from excel_handler import ExcelHandler
from gerrit_manager import GerritManager

logger = utils.setup_logger(__name__)

class FeatureThree:
    """功能三：去除版本號產生新的 manifest - 增強版"""
    
    def __init__(self):
        self.logger = logger
        self.excel_handler = ExcelHandler()
        self.gerrit_manager = GerritManager()
    
    def process(self, input_path: str, output_folder: str, process_type: str, 
                excel_filename: Optional[str] = None) -> bool:
        """
        處理功能三的主要邏輯 - 增強版
        
        Args:
            input_path: 輸入的 manifest.xml 檔案或資料夾路徑
            output_folder: 輸出資料夾
            process_type: 處理類型 (master, premp, mp, mpbackup)
            excel_filename: 自定義 Excel 檔名
            
        Returns:
            是否處理成功
        """
        try:
            self.logger.info("=== 開始執行功能三：去除版本號產生新 manifest (增強版) ===")
            self.logger.info(f"輸入路徑: {input_path}")
            self.logger.info(f"輸出資料夾: {output_folder}")
            self.logger.info(f"處理類型: {process_type}")
            
            # 確保輸出資料夾存在
            utils.ensure_dir(output_folder)
            
            # 建立下載檔案的子資料夾
            download_folder = os.path.join(output_folder, "downloaded_gerrit_files")
            utils.ensure_dir(download_folder)
            
            # 取得要處理的檔案清單
            manifest_files = self._get_manifest_files(input_path)
            if not manifest_files:
                self.logger.error("找不到要處理的 manifest 檔案")
                return False
            
            self.logger.info(f"找到 {len(manifest_files)} 個 manifest 檔案")
            
            # 處理所有檔案
            results = []
            for manifest_file in manifest_files:
                result = self._process_single_manifest(manifest_file, output_folder, process_type)
                results.append(result)
            
            # 進行比較並產生報告 (增強版)
            comparison_results = []
            diff_analyses = []
            
            for result in results:
                if result['success']:
                    comparison_result, diff_analysis = self._compare_with_gerrit_enhanced(
                        result, process_type, download_folder
                    )
                    comparison_results.append(comparison_result)
                    if diff_analysis:
                        diff_analyses.append(diff_analysis)
            
            # 產生 Excel 報告 (包含差異分析頁籤)
            excel_file = self._generate_excel_report_enhanced(
                results, comparison_results, diff_analyses, output_folder, 
                process_type, excel_filename
            )
            
            self.logger.info(f"=== 功能三執行完成，Excel 報告：{excel_file} ===")
            self.logger.info(f"📁 下載的 Gerrit 檔案位於: {download_folder}")
            return True
            
        except Exception as e:
            self.logger.error(f"功能三執行失敗: {str(e)}")
            return False
    
    def _get_manifest_files(self, input_path: str) -> List[str]:
        """取得要處理的 manifest 檔案清單"""
        manifest_files = []
        
        try:
            if os.path.isfile(input_path):
                # 單一檔案
                if input_path.endswith('.xml'):
                    manifest_files.append(input_path)
            elif os.path.isdir(input_path):
                # 資料夾，尋找所有 .xml 檔案
                for file in os.listdir(input_path):
                    if file.endswith('.xml'):
                        full_path = os.path.join(input_path, file)
                        manifest_files.append(full_path)
            
            return manifest_files
            
        except Exception as e:
            self.logger.error(f"取得檔案清單失敗: {str(e)}")
            return []
    
    def _process_single_manifest(self, input_file: str, output_folder: str, process_type: str) -> Dict:
        """處理單一 manifest 檔案"""
        result = {
            'success': False,
            'source_file': input_file,
            'source_filename': os.path.basename(input_file),
            'output_file': '',
            'output_filename': '',
            'message': ''
        }
        
        try:
            # 解析 XML
            tree = ET.parse(input_file)
            root = tree.getroot()
            
            # 處理所有 project 元素
            for project in root.findall('project'):
                # 取得原始屬性值
                dest_branch = project.get('dest-branch', '')
                upstream = project.get('upstream', '')
                revision = project.get('revision', '')
                
                # 判斷是否為 tag 定版（dest-branch 或 upstream 以 refs/tags/ 開頭）
                is_tag_version = (
                    dest_branch.startswith('refs/tags/') or 
                    upstream.startswith('refs/tags/')
                )
                
                if is_tag_version:
                    # Case 1: Tag 定版 - 移除 dest-branch, upstream, revision
                    self.logger.debug(f"檢測到 Tag 定版專案: {project.get('name', '')}")
                    for attr in ['dest-branch', 'upstream', 'revision']:
                        if attr in project.attrib:
                            del project.attrib[attr]
                else:
                    # Case 2: 分支版本 - 保留 revision 但設為分支名稱
                    branch_name = dest_branch or upstream
                    if branch_name:
                        project.set('revision', branch_name)
                        self.logger.debug(f"分支版本專案 {project.get('name', '')}: revision 設為 {branch_name}")
                    
                    # 移除 dest-branch, upstream
                    for attr in ['dest-branch', 'upstream']:
                        if attr in project.attrib:
                            del project.attrib[attr]
                
                # 更新 path 欄位（如果需要）
                path = project.get('path', '')
                if path:
                    updated_path = self._update_path_for_type(path, process_type)
                    project.set('path', updated_path)
            
            # 決定輸出檔名
            output_filename = self._get_output_filename(process_type)
            output_file = os.path.join(output_folder, output_filename)
            
            # 寫入新的 XML 檔案
            tree.write(output_file, encoding='utf-8', xml_declaration=True)
            
            result.update({
                'success': True,
                'output_file': output_file,
                'output_filename': output_filename,
                'message': '處理成功'
            })
            
            self.logger.info(f"成功處理: {os.path.basename(input_file)} -> {output_filename}")
            
        except Exception as e:
            result['message'] = f"處理失敗: {str(e)}"
            self.logger.error(result['message'])
        
        return result
    
    def _update_path_for_type(self, original_path: str, process_type: str) -> str:
        """根據處理類型更新路徑"""
        # 這裡可以根據需求調整路徑轉換邏輯
        # 目前保持原始路徑不變
        return original_path
    
    def _get_output_filename(self, process_type: str) -> str:
        """根據處理類型取得輸出檔名"""
        filename_mapping = {
            'master': 'atv-google-refplus.xml',
            'premp': 'atv-google-refplus-premp.xml',
            'mp': 'atv-google-refplus-wave.xml',
            'mpbackup': 'atv-google-refplus-wave-backup.xml'
        }
        return filename_mapping.get(process_type, 'manifest.xml')
    
    def _compare_with_gerrit_enhanced(self, result: Dict, process_type: str, download_folder: str) -> tuple:
        """與 Gerrit 上的檔案進行比較 - 增強版 (保存檔案 + 詳細差異分析)"""
        comparison_result = result.copy()
        comparison_result.update({
            'gerrit_link': '',
            'gerrit_saved_file': '',
            'comparison_status': '未比較',
            'comparison_message': ''
        })
        
        diff_analysis = None
        
        try:
            # 取得對應的 Gerrit 連結
            gerrit_link = self._get_gerrit_link(process_type)
            comparison_result['gerrit_link'] = gerrit_link
            
            if not gerrit_link:
                comparison_result['comparison_message'] = '無對應的 Gerrit 連結'
                return comparison_result, None
            
            self.logger.info(f"開始比較 Gerrit 檔案: {gerrit_link}")
            
            # 下載並保存 Gerrit 檔案
            gerrit_file_path = os.path.join(download_folder, f"gerrit_{result['output_filename']}")
            gerrit_content = self._download_and_save_gerrit_file(gerrit_link, gerrit_file_path)
            
            if gerrit_content is None:
                comparison_result['comparison_status'] = 'Gerrit檔案無法存取'
                comparison_result['comparison_message'] = 'Gerrit 檔案不存在或無法下載'
                return comparison_result, None
            
            comparison_result['gerrit_saved_file'] = gerrit_file_path
            
            # 讀取本地檔案
            local_content = self._read_local_file_content(result['output_file'])
            
            if local_content is None:
                comparison_result['comparison_status'] = '讀取失敗'
                comparison_result['comparison_message'] = '無法讀取本地檔案'
                return comparison_result, None
            
            # 詳細差異分析 - 比較產出檔案和 Gerrit 檔案
            diff_analysis = self._analyze_xml_differences(
                local_content, gerrit_content, 
                result['output_filename'], f"gerrit_{result['output_filename']}"
            )
            
            # 基本比較
            if self._normalize_xml_for_comparison(gerrit_content) == self._normalize_xml_for_comparison(local_content):
                comparison_result['comparison_status'] = '相同'
                comparison_result['comparison_message'] = '檔案內容相同'
            else:
                comparison_result['comparison_status'] = '不同'
                
                # 提供更詳細的差異資訊
                gerrit_lines = len(gerrit_content.split('\n'))
                local_lines = len(local_content.split('\n'))
                
                comparison_result['comparison_message'] = (
                    f'檔案內容不同 (本地: {local_lines} 行, Gerrit: {gerrit_lines} 行)'
                )
            
            self.logger.info(f"比較結果: {comparison_result['comparison_status']} - {result['output_filename']}")
            
        except Exception as e:
            comparison_result['comparison_status'] = '比較錯誤'
            comparison_result['comparison_message'] = f"比較過程發生錯誤: {str(e)}"
            self.logger.error(comparison_result['comparison_message'])
        
        return comparison_result, diff_analysis
    
    def _download_and_save_gerrit_file(self, gerrit_link: str, save_path: str) -> Optional[str]:
        """下載並保存 Gerrit 檔案"""
        try:
            import tempfile
            
            with tempfile.NamedTemporaryFile(delete=False, suffix='.xml') as temp_file:
                temp_path = temp_file.name
            
            try:
                # 下載檔案
                success = self.gerrit_manager.download_file_from_link(gerrit_link, temp_path)
                
                if success and os.path.exists(temp_path):
                    # 檢查檔案大小
                    file_size = os.path.getsize(temp_path)
                    if file_size == 0:
                        self.logger.warning(f"下載的檔案為空: {gerrit_link}")
                        return None
                    
                    # 讀取內容
                    with open(temp_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # 保存到指定位置
                    with open(save_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    
                    # 統計行數
                    line_count = len(content.split('\n'))
                    self.logger.info(f"成功下載並保存 Gerrit 檔案: {save_path} ({file_size} bytes, {line_count} 行)")
                    
                    return content
                else:
                    self.logger.warning(f"下載 Gerrit 檔案失敗")
                    return None
                    
            finally:
                # 清理臨時檔案
                try:
                    if os.path.exists(temp_path):
                        os.unlink(temp_path)
                except Exception as cleanup_error:
                    self.logger.debug(f"清理臨時檔案失敗: {str(cleanup_error)}")
                    
        except Exception as e:
            self.logger.error(f"下載並保存 Gerrit 檔案失敗: {str(e)}")
            return None
    
    def _analyze_xml_differences(self, local_content: str, gerrit_content: str, 
                                local_filename: str, gerrit_filename: str) -> Dict:
        """詳細分析兩個 XML 檔案的差異 - 增強版 (比較產出檔案和 Gerrit 檔案)"""
        diff_analysis = {
            'local_filename': local_filename,        # 產出的檔案名稱
            'gerrit_filename': gerrit_filename,      # Gerrit 檔案名稱
            'local_projects': 0,
            'gerrit_projects': 0,
            'common_projects': 0,
            'local_only_projects': [],
            'gerrit_only_projects': [],
            'modified_projects': [],
            'tag_version_projects': 0,
            'branch_version_projects': 0,
            'analysis_details': []
        }
        
        try:
            # 解析兩個 XML 檔案
            local_root = ET.fromstring(local_content)
            gerrit_root = ET.fromstring(gerrit_content)
            
            # 取得專案清單
            local_projects = self._extract_projects_enhanced(local_root)
            gerrit_projects = self._extract_projects_enhanced(gerrit_root)
            
            diff_analysis['local_projects'] = len(local_projects)
            diff_analysis['gerrit_projects'] = len(gerrit_projects)
            
            # 統計處理類型
            tag_count = 0
            branch_count = 0
            for project_info in local_projects.values():
                processed_as = project_info.get('processed_as', 'unknown')
                if 'tag' in processed_as:
                    tag_count += 1
                elif 'branch' in processed_as:
                    branch_count += 1
            
            diff_analysis['tag_version_projects'] = tag_count
            diff_analysis['branch_version_projects'] = branch_count
            
            # 分析差異
            local_names = set(local_projects.keys())
            gerrit_names = set(gerrit_projects.keys())
            
            # 共同專案
            common_names = local_names & gerrit_names
            diff_analysis['common_projects'] = len(common_names)
            
            # 只在本地的專案
            local_only_names = local_names - gerrit_names
            for name in local_only_names:
                project_info = local_projects[name].copy()
                project_info['project_name'] = name
                diff_analysis['local_only_projects'].append(project_info)
            
            # 只在 Gerrit 的專案
            gerrit_only_names = gerrit_names - local_names
            for name in gerrit_only_names:
                project_info = gerrit_projects[name].copy()
                project_info['project_name'] = name
                diff_analysis['gerrit_only_projects'].append(project_info)
            
            # 檢查共同專案的差異
            for name in common_names:
                local_proj = local_projects[name]
                gerrit_proj = gerrit_projects[name]
                
                differences = []
                for attr in ['path', 'revision', 'upstream', 'dest-branch', 'groups']:
                    local_val = local_proj.get(attr, '')
                    gerrit_val = gerrit_proj.get(attr, '')
                    
                    if local_val != gerrit_val:
                        differences.append({
                            'attribute': attr,
                            'local_value': local_val,
                            'gerrit_value': gerrit_val
                        })
                
                if differences:
                    diff_analysis['modified_projects'].append({
                        'project_name': name,
                        'processed_as': local_proj.get('processed_as', 'unknown'),
                        'differences': differences
                    })
            
            # 產生分析摘要
            summary = []
            summary.append(f"專案總數: 本地產出 {diff_analysis['local_projects']}, Gerrit {diff_analysis['gerrit_projects']}")
            summary.append(f"共同專案: {diff_analysis['common_projects']}")
            summary.append(f"Tag 定版專案: {diff_analysis['tag_version_projects']}")
            summary.append(f"分支版本專案: {diff_analysis['branch_version_projects']}")
            summary.append(f"僅本地產出: {len(diff_analysis['local_only_projects'])}")
            summary.append(f"僅 Gerrit: {len(diff_analysis['gerrit_only_projects'])}")
            summary.append(f"有差異: {len(diff_analysis['modified_projects'])}")
            
            diff_analysis['analysis_details'] = summary
            
            self.logger.info(f"差異分析完成: {local_filename} vs {gerrit_filename}")
            for detail in summary:
                self.logger.info(f"  - {detail}")
            
        except Exception as e:
            self.logger.error(f"差異分析失敗: {str(e)}")
            diff_analysis['analysis_details'] = [f"分析失敗: {str(e)}"]
        
        return diff_analysis
    
    def _extract_projects_enhanced(self, root: ET.Element) -> Dict[str, Dict]:
        """從 XML 根元素提取所有專案資訊 - 增強版 (記錄處理類型)"""
        projects = {}
        
        for project in root.findall('project'):
            name = project.get('name', '')
            if name:
                # 取得當前的屬性
                dest_branch = project.get('dest-branch', '')
                upstream = project.get('upstream', '')
                revision = project.get('revision', '')
                
                # 判斷處理類型
                processed_as = 'unknown'
                
                # 如果有 dest-branch 或 upstream 且以 refs/tags/ 開頭，是原始 tag 定版
                if dest_branch.startswith('refs/tags/') or upstream.startswith('refs/tags/'):
                    processed_as = 'original_tag_version'
                # 如果有 dest-branch 或 upstream 且不以 refs/tags/ 開頭，是原始分支版本
                elif dest_branch or upstream:
                    processed_as = 'original_branch_version'
                # 如果只有 revision 且沒有 dest-branch/upstream，可能是處理後的分支版本
                elif revision and not dest_branch and not upstream:
                    # 進一步判斷 revision 的格式來猜測處理類型
                    if revision.startswith('refs/tags/'):
                        processed_as = 'processed_tag_version'
                    elif '/' in revision and not revision.startswith('refs/'):
                        # 類似 realtek/android-14/mp.google-refplus.wave.upgrade-11.rtd6748
                        processed_as = 'processed_branch_version'
                    else:
                        # 可能是 commit hash
                        processed_as = 'commit_hash'
                # 如果都沒有版本資訊，可能是處理後的 tag 定版
                elif not revision and not dest_branch and not upstream:
                    processed_as = 'processed_tag_version'
                
                projects[name] = {
                    'path': project.get('path', ''),
                    'revision': revision,
                    'upstream': upstream,
                    'dest-branch': dest_branch,
                    'groups': project.get('groups', ''),
                    'processed_as': processed_as
                }
        
        return projects
    
    def _extract_projects(self, root: ET.Element) -> Dict[str, Dict]:
        """從 XML 根元素提取所有專案資訊 - 原始版本 (向後相容)"""
        projects = {}
        
        for project in root.findall('project'):
            name = project.get('name', '')
            if name:
                projects[name] = {
                    'path': project.get('path', ''),
                    'revision': project.get('revision', ''),
                    'upstream': project.get('upstream', ''),
                    'dest-branch': project.get('dest-branch', ''),
                    'groups': project.get('groups', '')
                }
        
        return projects
    
    def _normalize_xml_for_comparison(self, xml_content: str) -> str:
        """標準化 XML 內容以便比較"""
        try:
            import xml.etree.ElementTree as ET
            
            # 解析 XML
            root = ET.fromstring(xml_content)
            
            # 移除所有空白和縮排，重新格式化為一致的格式
            def remove_whitespace(element):
                if element.text:
                    element.text = element.text.strip() or None
                if element.tail:
                    element.tail = element.tail.strip() or None
                for child in element:
                    remove_whitespace(child)
            
            remove_whitespace(root)
            
            # 重新格式化為統一格式
            rough_string = ET.tostring(root, encoding='unicode')
            
            # 重新解析並格式化
            reparsed = ET.fromstring(rough_string)
            formatted = ET.tostring(reparsed, encoding='unicode')
            
            # 使用 minidom 進行一致的格式化
            from xml.dom import minidom
            dom = minidom.parseString(formatted)
            pretty = dom.toprettyxml(indent="  ")
            
            # 移除空行
            lines = [line for line in pretty.split('\n') if line.strip()]
            
            return '\n'.join(lines)
            
        except Exception as e:
            self.logger.warning(f"XML 標準化失敗，使用原始內容比較: {str(e)}")
            return xml_content.strip()
            
    def _get_gerrit_link(self, process_type: str) -> str:
        """取得對應的 Gerrit 連結"""
        base_url = "https://mm2sd.rtkbf.com/gerrit/plugins/gitiles/realtek/android/manifest/+/refs/heads/realtek/android-14/master"
        
        link_mapping = {
            'master': f"{base_url}/atv-google-refplus.xml",
            'premp': f"{base_url}/atv-google-refplus-premp.xml",
            'mp': f"{base_url}/atv-google-refplus-wave.xml",
            'mpbackup': f"{base_url}/atv-google-refplus-wave-backup.xml"
        }
        
        gerrit_link = link_mapping.get(process_type, '')
        
        if gerrit_link:
            self.logger.info(f"建立 Gerrit 比較連結: {gerrit_link}")
        else:
            self.logger.warning(f"無法為類型 '{process_type}' 建立 Gerrit 連結")
        
        return gerrit_link
    
    def _read_local_file_content(self, file_path: str) -> Optional[str]:
        """讀取本地檔案內容"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            self.logger.error(f"讀取本地檔案失敗: {str(e)}")
            return None
    
    def _generate_excel_report_enhanced(self, results: List[Dict], comparison_results: List[Dict],
                                      diff_analyses: List[Dict], output_folder: str, 
                                      process_type: str, excel_filename: Optional[str]) -> str:
        """產生 Excel 報告 - 增強版 (包含差異分析頁籤)"""
        try:
            # 決定 Excel 檔名
            if excel_filename:
                excel_file = os.path.join(output_folder, excel_filename)
            else:
                default_name = f"{process_type}_manifest_status.xlsx"
                excel_file = os.path.join(output_folder, default_name)
            
            with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
                # 產生結果頁籤
                if results:
                    df_results = pd.DataFrame(results)
                    # 重新編號
                    df_results['SN'] = range(1, len(df_results) + 1)
                    
                    # 調整欄位順序
                    column_order = ['SN', 'source_filename', 'output_filename', 'output_file', 'success', 'message']
                    df_results = df_results[[col for col in column_order if col in df_results.columns]]
                else:
                    df_results = pd.DataFrame(columns=['SN', 'source_filename', 'output_filename', 'output_file', 'success', 'message'])
                
                df_results.to_excel(writer, sheet_name='產生結果', index=False)
                
                # 比較結果頁籤 (增強版)
                if comparison_results:
                    df_comparison = pd.DataFrame(comparison_results)
                    # 重新編號
                    df_comparison['SN'] = range(1, len(df_comparison) + 1)
                    
                    # 調整欄位順序 (新增 gerrit_saved_file)
                    comparison_columns = ['SN', 'source_filename', 'output_filename', 'output_file', 
                                        'gerrit_link', 'gerrit_saved_file', 'comparison_status', 'comparison_message']
                    df_comparison = df_comparison[[col for col in comparison_columns if col in df_comparison.columns]]
                else:
                    df_comparison = pd.DataFrame(columns=['SN', 'source_filename', 'output_filename', 'output_file', 
                                                        'gerrit_link', 'gerrit_saved_file', 'comparison_status', 'comparison_message'])
                
                df_comparison.to_excel(writer, sheet_name='比較結果', index=False)
                
                # 新增：差異分析頁籤
                if diff_analyses:
                    self._create_diff_analysis_sheets(writer, diff_analyses)
                
                # 格式化所有工作表
                for sheet_name in writer.sheets:
                    worksheet = writer.sheets[sheet_name]
                    self.excel_handler._format_worksheet(worksheet)
                    
                    # 特別格式化比較結果欄位
                    if sheet_name == '比較結果':
                        self._format_comparison_status_column(worksheet)
            
            self.logger.info(f"成功產生 Excel 報告: {excel_file}")
            return excel_file
            
        except Exception as e:
            self.logger.error(f"產生 Excel 報告失敗: {str(e)}")
            raise
    
    def _create_diff_analysis_sheets(self, writer, diff_analyses: List[Dict]):
        """建立差異分析相關的頁籤 - 增強版 (包含處理類型統計)"""
        try:
            # 頁籤1: 差異摘要 (修正比較對象)
            summary_data = []
            for i, analysis in enumerate(diff_analyses, 1):
                summary_data.append({
                    'SN': i,
                    '本地檔案': analysis['local_filename'],
                    'Gerrit檔案': analysis['gerrit_filename'],
                    '本地專案數': analysis['local_projects'],
                    'Gerrit專案數': analysis['gerrit_projects'],
                    '共同專案數': analysis['common_projects'],
                    'Tag定版專案數': analysis.get('tag_version_projects', 0),
                    '分支版本專案數': analysis.get('branch_version_projects', 0),
                    '僅本地專案數': len(analysis['local_only_projects']),
                    '僅Gerrit專案數': len(analysis['gerrit_only_projects']),
                    '有差異專案數': len(analysis['modified_projects']),
                    '分析詳情': '; '.join(analysis['analysis_details'])
                })
            
            if summary_data:
                df_summary = pd.DataFrame(summary_data)
                df_summary.to_excel(writer, sheet_name='差異摘要', index=False)
            
            # 頁籤2: 僅本地專案 (修正比較對象)
            local_only_data = []
            sn = 1
            for analysis in diff_analyses:
                for project in analysis['local_only_projects']:
                    local_only_data.append({
                        'SN': sn,
                        '本地檔案': analysis['local_filename'],
                        '專案名稱': project['project_name'],
                        '處理類型': project.get('processed_as', 'unknown'),
                        'Path': project.get('path', ''),
                        'Revision': project.get('revision', ''),
                        'Upstream': project.get('upstream', ''),
                        'Dest-Branch': project.get('dest-branch', ''),
                        'Groups': project.get('groups', '')
                    })
                    sn += 1
            
            if local_only_data:
                df_local_only = pd.DataFrame(local_only_data)
                df_local_only.to_excel(writer, sheet_name='僅本地專案', index=False)
            
            # 頁籤3: 僅Gerrit專案 (修正比較對象)
            gerrit_only_data = []
            sn = 1
            for analysis in diff_analyses:
                for project in analysis['gerrit_only_projects']:
                    gerrit_only_data.append({
                        'SN': sn,
                        'Gerrit檔案': analysis['gerrit_filename'],
                        '專案名稱': project['project_name'],
                        '處理類型': project.get('processed_as', 'unknown'),
                        'Path': project.get('path', ''),
                        'Revision': project.get('revision', ''),
                        'Upstream': project.get('upstream', ''),
                        'Dest-Branch': project.get('dest-branch', ''),
                        'Groups': project.get('groups', '')
                    })
                    sn += 1
            
            if gerrit_only_data:
                df_gerrit_only = pd.DataFrame(gerrit_only_data)
                df_gerrit_only.to_excel(writer, sheet_name='僅Gerrit專案', index=False)
            
            # 頁籤4: 專案差異詳情 (修正比較對象)
            diff_details_data = []
            sn = 1
            for analysis in diff_analyses:
                for project in analysis['modified_projects']:
                    project_name = project['project_name']
                    processed_as = project.get('processed_as', 'unknown')
                    for diff in project['differences']:
                        diff_details_data.append({
                            'SN': sn,
                            '本地檔案': analysis['local_filename'],
                            '專案名稱': project_name,
                            '處理類型': processed_as,
                            '差異屬性': diff['attribute'],
                            '本地值': diff['local_value'],
                            'Gerrit值': diff['gerrit_value']
                        })
                        sn += 1
            
            if diff_details_data:
                df_diff_details = pd.DataFrame(diff_details_data)
                df_diff_details.to_excel(writer, sheet_name='專案差異詳情', index=False)
            
            self.logger.info(f"成功建立差異分析頁籤，共 {len(diff_analyses)} 個分析結果")
            
        except Exception as e:
            self.logger.error(f"建立差異分析頁籤失敗: {str(e)}")

    def _format_comparison_status_column(self, worksheet):
        """格式化比較狀態欄位"""
        try:
            from openpyxl.styles import PatternFill, Font
            from openpyxl.utils import get_column_letter
            
            # 狀態顏色設定
            status_colors = {
                '相同': {'fill': PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid"),
                        'font': Font(color="006100", bold=True)},
                '不同': {'fill': PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid"),
                        'font': Font(color="9C0006", bold=True)},
                'Gerrit檔案無法存取': {'fill': PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid"),
                                'font': Font(color="9C6500", bold=True)},
                '下載失敗': {'fill': PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid"),
                            'font': Font(color="9C0006", bold=True)}
            }
            
            # 找到 comparison_status 欄位
            status_col = None
            for col_num, cell in enumerate(worksheet[1], 1):
                if cell.value == 'comparison_status':
                    status_col = col_num
                    break
            
            if status_col:
                col_letter = get_column_letter(status_col)
                
                # 格式化資料列
                for row_num in range(2, worksheet.max_row + 1):
                    cell = worksheet[f"{col_letter}{row_num}"]
                    status = str(cell.value) if cell.value else ''
                    
                    if status in status_colors:
                        cell.fill = status_colors[status]['fill']
                        cell.font = status_colors[status]['font']
                
                self.logger.info("已設定比較狀態欄位格式")
            
        except Exception as e:
            self.logger.error(f"格式化比較狀態欄位失敗: {str(e)}")