"""
功能三：Manifest 轉換工具 - 全新版本
從 Gerrit 下載源檔案，進行 revision 轉換，並與目標檔案比較差異
"""
import os
import xml.etree.ElementTree as ET
import pandas as pd
import re
import tempfile
from typing import Dict, List, Any, Optional, Tuple
import utils
from excel_handler import ExcelHandler
from gerrit_manager import GerritManager

logger = utils.setup_logger(__name__)

class FeatureThree:
    """功能三：Manifest 轉換工具 - 全新版本"""
    
    def __init__(self):
        self.logger = logger
        self.excel_handler = ExcelHandler()
        self.gerrit_manager = GerritManager()
        
        # Gerrit 基礎 URL 模板
        self.gerrit_base_url = "https://mm2sd.rtkbf.com/gerrit/plugins/gitiles/realtek/android/manifest/+/refs/heads/realtek/android-14/master"
        
        # 檔案映射表
        self.source_files = {
            'master_to_premp': 'atv-google-refplus.xml',
            'premp_to_mp': 'atv-google-refplus-premp.xml',
            'mp_to_mpbackup': 'atv-google-refplus-wave.xml'
        }
        
        # 輸出檔案映射表
        self.output_files = {
            'master_to_premp': 'atv-google-refplus-premp.xml',
            'premp_to_mp': 'atv-google-refplus-wave.xml',
            'mp_to_mpbackup': 'atv-google-refplus-wave-backup.xml'
        }
        
        # 目標檔案映射表（用於比較）
        self.target_files = {
            'master_to_premp': 'atv-google-refplus-premp.xml',
            'premp_to_mp': 'atv-google-refplus-wave.xml', 
            'mp_to_mpbackup': 'atv-google-refplus-wave-backup.xml'
        }
    
    def process(self, overwrite_type: str, output_folder: str, 
                excel_filename: Optional[str] = None) -> bool:
        """
        處理功能三的主要邏輯 - 全新版本
        
        Args:
            overwrite_type: 轉換類型 (master_to_premp, premp_to_mp, mp_to_mpbackup)
            output_folder: 輸出資料夾
            excel_filename: 自定義 Excel 檔名
            
        Returns:
            是否處理成功
        """
        try:
            self.logger.info("=== 開始執行功能三：Manifest 轉換工具 (全新版本) ===")
            self.logger.info(f"轉換類型: {overwrite_type}")
            self.logger.info(f"輸出資料夾: {output_folder}")
            
            # 驗證參數
            if overwrite_type not in self.source_files:
                self.logger.error(f"不支援的轉換類型: {overwrite_type}")
                return False
            
            # 確保輸出資料夾存在
            utils.ensure_dir(output_folder)
            
            # 步驟 1: 從 Gerrit 下載源檔案
            source_content = self._download_source_file(overwrite_type)
            if not source_content:
                self.logger.error("下載源檔案失敗")
                return False
            
            # 步驟 2: 進行 revision 轉換
            converted_content = self._convert_revisions(source_content, overwrite_type)
            
            # 步驟 3: 保存轉換後的檔案
            output_file_path = self._save_converted_file(converted_content, overwrite_type, output_folder)
            
            # 步驟 4: 從 Gerrit 下載目標檔案進行比較
            target_content = self._download_target_file(overwrite_type)
            target_file_path = None
            if target_content:
                target_file_path = self._save_target_file(target_content, overwrite_type, output_folder)
            
            # 步驟 5: 進行差異分析
            diff_analysis = self._analyze_differences(
                converted_content, target_content, overwrite_type
            )
            
            # 步驟 6: 產生 Excel 報告
            excel_file = self._generate_excel_report(
                overwrite_type, output_file_path, target_file_path, 
                diff_analysis, output_folder, excel_filename
            )
            
            self.logger.info(f"=== 功能三執行完成，Excel 報告：{excel_file} ===")
            return True
            
        except Exception as e:
            self.logger.error(f"功能三執行失敗: {str(e)}")
            return False
    
    def _download_source_file(self, overwrite_type: str) -> Optional[str]:
        """從 Gerrit 下載源檔案"""
        try:
            source_filename = self.source_files[overwrite_type]
            source_url = f"{self.gerrit_base_url}/{source_filename}"
            
            self.logger.info(f"下載源檔案: {source_filename}")
            self.logger.info(f"URL: {source_url}")
            
            # 使用臨時檔案下載
            with tempfile.NamedTemporaryFile(delete=False, suffix='.xml') as temp_file:
                temp_path = temp_file.name
            
            try:
                success = self.gerrit_manager.download_file_from_link(source_url, temp_path)
                
                if success and os.path.exists(temp_path):
                    with open(temp_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    self.logger.info(f"成功下載源檔案: {len(content)} 字符")
                    return content
                else:
                    self.logger.error("下載源檔案失敗")
                    return None
                    
            finally:
                # 清理臨時檔案
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                    
        except Exception as e:
            self.logger.error(f"下載源檔案異常: {str(e)}")
            return None
    
    def _download_target_file(self, overwrite_type: str) -> Optional[str]:
        """從 Gerrit 下載目標檔案進行比較"""
        try:
            target_filename = self.target_files[overwrite_type]
            target_url = f"{self.gerrit_base_url}/{target_filename}"
            
            self.logger.info(f"下載目標檔案: {target_filename}")
            self.logger.info(f"URL: {target_url}")
            
            # 使用臨時檔案下載
            with tempfile.NamedTemporaryFile(delete=False, suffix='.xml') as temp_file:
                temp_path = temp_file.name
            
            try:
                success = self.gerrit_manager.download_file_from_link(target_url, temp_path)
                
                if success and os.path.exists(temp_path):
                    with open(temp_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    self.logger.info(f"成功下載目標檔案: {len(content)} 字符")
                    return content
                else:
                    self.logger.warning("下載目標檔案失敗，將只進行轉換不做比較")
                    return None
                    
            finally:
                # 清理臨時檔案
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                    
        except Exception as e:
            self.logger.warning(f"下載目標檔案異常: {str(e)}")
            return None
    
    def _convert_revisions(self, xml_content: str, overwrite_type: str) -> str:
        """根據轉換類型進行 revision 轉換"""
        try:
            self.logger.info(f"開始進行 revision 轉換: {overwrite_type}")
            
            # 解析 XML
            root = ET.fromstring(xml_content)
            conversion_count = 0
            
            # 遍歷所有 project 元素
            for project in root.findall('project'):
                revision = project.get('revision')
                if not revision:
                    continue
                
                old_revision = revision
                new_revision = self._convert_single_revision(revision, overwrite_type)
                
                if new_revision != old_revision:
                    project.set('revision', new_revision)
                    conversion_count += 1
                    self.logger.debug(f"轉換 revision: {old_revision} → {new_revision}")
            
            # 轉換回字串
            converted_xml = ET.tostring(root, encoding='unicode')
            
            self.logger.info(f"revision 轉換完成，共轉換 {conversion_count} 個專案")
            return converted_xml
            
        except Exception as e:
            self.logger.error(f"revision 轉換失敗: {str(e)}")
            return xml_content
    
    def _convert_single_revision(self, revision: str, overwrite_type: str) -> str:
        """轉換單一 revision"""
        if overwrite_type == 'master_to_premp':
            return self._convert_master_to_premp(revision)
        elif overwrite_type == 'premp_to_mp':
            return self._convert_premp_to_mp(revision)
        elif overwrite_type == 'mp_to_mpbackup':
            return self._convert_mp_to_mpbackup(revision)
        else:
            return revision
    
    def _convert_master_to_premp(self, revision: str) -> str:
        """master → premp 轉換規則"""
        # 具體的轉換規則
        conversions = [
            # 基本轉換
            ('realtek/android-14/master', 'realtek/android-14/premp.google-refplus'),
            ('realtek/linux-5.15/android-14/master', 'realtek/linux-5.15/android-14/premp.google-refplus'),
            ('realtek/master', 'realtek/android-14/premp.google-refplus'),
            ('realtek/gaia', 'realtek/android-14/premp.google-refplus'),
            ('realtek/gki/master', 'realtek/android-14/premp.google-refplus'),
            
            # mp.google-refplus 相關
            ('realtek/android-14/mp.google-refplus', 'realtek/android-14/premp.google-refplus'),
            ('realtek/v3.16/mp.google-refplus', 'realtek/v3.16/premp.google-refplus'),
            ('realtek/linux-5.4/android-14/mp.google-refplus.rtd2851f', 'realtek/linux-5.4/android-14/premp.google-refplus.rtd2851f'),
            
            # upgrade-11 相關
            ('realtek/android-14/mp.google-refplus.upgrade-11.rtd6748', 'realtek/android-14/premp.google-refplus.upgrade-11.rtd6748'),
        ]
        
        # 進行轉換
        for old_pattern, new_pattern in conversions:
            if revision == old_pattern:
                return new_pattern
        
        # 如果沒有匹配的規則，使用預設轉換
        return 'realtek/android-14/premp.google-refplus'
    
    def _convert_premp_to_mp(self, revision: str) -> str:
        """premp → mp 轉換規則"""
        # 將 premp.google-refplus 關鍵字替換為 mp.google-refplus.wave
        return revision.replace('premp.google-refplus', 'mp.google-refplus.wave')
    
    def _convert_mp_to_mpbackup(self, revision: str) -> str:
        """mp → mpbackup 轉換規則"""
        # 將 mp.google-refplus.wave 關鍵字替換為 mp.google-refplus.wave.backup
        return revision.replace('mp.google-refplus.wave', 'mp.google-refplus.wave.backup')
    
    def _save_converted_file(self, content: str, overwrite_type: str, output_folder: str) -> str:
        """保存轉換後的檔案"""
        try:
            output_filename = self.output_files[overwrite_type]
            output_path = os.path.join(output_folder, output_filename)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            self.logger.info(f"轉換後檔案已保存: {output_path}")
            return output_path
            
        except Exception as e:
            self.logger.error(f"保存轉換檔案失敗: {str(e)}")
            raise
    
    def _save_target_file(self, content: str, overwrite_type: str, output_folder: str) -> str:
        """保存目標檔案（從 Gerrit 下載的）"""
        try:
            target_filename = f"gerrit_{self.target_files[overwrite_type]}"
            target_path = os.path.join(output_folder, target_filename)
            
            with open(target_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            self.logger.info(f"Gerrit 目標檔案已保存: {target_path}")
            return target_path
            
        except Exception as e:
            self.logger.error(f"保存目標檔案失敗: {str(e)}")
            raise
    
    def _analyze_differences(self, converted_content: str, target_content: Optional[str], 
                           overwrite_type: str) -> Dict[str, Any]:
        """分析轉換檔案與目標檔案的差異"""
        analysis = {
            'has_target': target_content is not None,
            'converted_projects': [],
            'target_projects': [],
            'differences': [],
            'summary': {}
        }
        
        try:
            # 解析轉換後的檔案
            converted_root = ET.fromstring(converted_content)
            converted_projects = self._extract_projects_with_line_numbers(converted_content)
            analysis['converted_projects'] = converted_projects
            
            if target_content:
                # 解析目標檔案
                target_root = ET.fromstring(target_content)
                target_projects = self._extract_projects_with_line_numbers(target_content)
                analysis['target_projects'] = target_projects
                
                # 進行差異比較
                differences = self._compare_projects(converted_projects, target_projects)
                analysis['differences'] = differences
                
                # 統計摘要
                analysis['summary'] = {
                    'converted_count': len(converted_projects),
                    'target_count': len(target_projects),
                    'differences_count': len(differences),
                    'identical_count': len(converted_projects) - len(differences)
                }
                
                self.logger.info(f"差異分析完成: {len(differences)} 個差異")
            else:
                analysis['summary'] = {
                    'converted_count': len(converted_projects),
                    'target_count': 0,
                    'differences_count': 0,
                    'identical_count': 0
                }
                self.logger.info("沒有目標檔案，跳過差異比較")
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"差異分析失敗: {str(e)}")
            return analysis
    
    def _extract_projects_with_line_numbers(self, xml_content: str) -> List[Dict[str, Any]]:
        """提取專案資訊並記錄行號"""
        projects = []
        lines = xml_content.split('\n')
        
        try:
            root = ET.fromstring(xml_content)
            
            # 為每個 project 找到對應的行號
            for project in root.findall('project'):
                project_name = project.get('name', '')
                
                # 在原始內容中尋找對應的行號
                line_number = self._find_project_line_number(lines, project_name)
                
                project_info = {
                    'line_number': line_number,
                    'name': project.get('name', ''),
                    'path': project.get('path', ''),
                    'revision': project.get('revision', ''),
                    'upstream': project.get('upstream', ''),
                    'dest-branch': project.get('dest-branch', ''),
                    'groups': project.get('groups', ''),
                    'clone-depth': project.get('clone-depth', ''),
                    'remote': project.get('remote', ''),
                    'full_line': self._get_full_project_line(lines, line_number)
                }
                projects.append(project_info)
            
            return projects
            
        except Exception as e:
            self.logger.error(f"提取專案資訊失敗: {str(e)}")
            return []
    
    def _find_project_line_number(self, lines: List[str], project_name: str) -> int:
        """尋找專案在 XML 中的行號"""
        for i, line in enumerate(lines, 1):
            if f'name="{project_name}"' in line:
                return i
        return 0
    
    def _get_full_project_line(self, lines: List[str], line_number: int) -> str:
        """取得完整的專案行（可能跨多行）"""
        if line_number == 0 or line_number > len(lines):
            return ''
        
        # 從指定行開始，找到完整的 project 標籤
        start_line = line_number - 1
        full_line = lines[start_line].strip()
        
        # 如果行不以 /> 或 > 結尾，可能跨多行
        if not (full_line.endswith('/>') or full_line.endswith('>')):
            for i in range(start_line + 1, len(lines)):
                full_line += ' ' + lines[i].strip()
                if lines[i].strip().endswith('/>') or lines[i].strip().endswith('>'):
                    break
        
        return full_line
    
    def _compare_projects(self, converted_projects: List[Dict], target_projects: List[Dict]) -> List[Dict]:
        """比較轉換後專案與目標專案的差異"""
        differences = []
        
        # 建立目標專案的索引
        target_index = {proj['name']: proj for proj in target_projects}
        
        for conv_proj in converted_projects:
            project_name = conv_proj['name']
            
            if project_name in target_index:
                target_proj = target_index[project_name]
                
                # 比較各個屬性
                diff_attrs = []
                for attr in ['path', 'revision', 'upstream', 'dest-branch', 'groups', 'clone-depth', 'remote']:
                    conv_val = conv_proj.get(attr, '')
                    target_val = target_proj.get(attr, '')
                    
                    if conv_val != target_val:
                        diff_attrs.append(attr)
                
                # 如果有差異，記錄
                if diff_attrs:
                    difference = {
                        'SN': len(differences) + 1,
                        'diff_line': conv_proj['line_number'],
                        'name': conv_proj['name'],
                        'path': conv_proj['path'],
                        'revision': conv_proj['revision'],
                        'upstream': conv_proj['upstream'],
                        'dest-branch': conv_proj['dest-branch'],
                        'groups': conv_proj['groups'],
                        'clone-depth': conv_proj['clone-depth'],
                        'remote': conv_proj['remote'],
                        'gerrit_diff_line': target_proj['line_number'],
                        'gerrit_name': target_proj['name'],
                        'gerrit_path': target_proj['path'],
                        'gerrit_revision': target_proj['revision'],
                        'gerrit_upstream': target_proj['upstream'],
                        'gerrit_dest-branch': target_proj['dest-branch'],
                        'gerrit_groups': target_proj['groups'],
                        'gerrit_clone-depth': target_proj['clone-depth'],
                        'gerrit_remote': target_proj['remote'],
                        'diff_attributes': diff_attrs,
                        'converted_full_line': conv_proj['full_line'],
                        'gerrit_full_line': target_proj['full_line']
                    }
                    differences.append(difference)
        
        return differences
    
    def _generate_excel_report(self, overwrite_type: str, output_file_path: str, 
                             target_file_path: Optional[str], diff_analysis: Dict,
                             output_folder: str, excel_filename: Optional[str]) -> str:
        """產生 Excel 報告"""
        try:
            # 決定 Excel 檔名
            if excel_filename:
                excel_file = os.path.join(output_folder, excel_filename)
            else:
                default_name = f"{overwrite_type}_conversion_report.xlsx"
                excel_file = os.path.join(output_folder, default_name)
            
            with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
                # 頁籤 1: 轉換摘要
                summary_data = [{
                    'SN': 1,
                    '轉換類型': overwrite_type,
                    '源檔案': self.source_files.get(overwrite_type, ''),
                    '輸出檔案': os.path.basename(output_file_path) if output_file_path else '',
                    '目標檔案': os.path.basename(target_file_path) if target_file_path else '無',
                    '轉換專案數': diff_analysis['summary'].get('converted_count', 0),
                    '目標專案數': diff_analysis['summary'].get('target_count', 0),
                    '差異數量': diff_analysis['summary'].get('differences_count', 0),
                    '相同數量': diff_analysis['summary'].get('identical_count', 0)
                }]
                
                df_summary = pd.DataFrame(summary_data)
                df_summary.to_excel(writer, sheet_name='轉換摘要', index=False)
                
                # 頁籤 2: 轉換後專案清單
                if diff_analysis['converted_projects']:
                    converted_data = []
                    for i, proj in enumerate(diff_analysis['converted_projects'], 1):
                        converted_data.append({
                            'SN': i,
                            '行號': proj['line_number'],
                            '專案名稱': proj['name'],
                            '路徑': proj['path'],
                            'Revision': proj['revision'],
                            'Upstream': proj['upstream'],
                            'Dest-Branch': proj['dest-branch'],
                            'Groups': proj['groups'],
                            'Clone-Depth': proj['clone-depth'],
                            'Remote': proj['remote']
                        })
                    
                    df_converted = pd.DataFrame(converted_data)
                    df_converted.to_excel(writer, sheet_name='轉換後專案', index=False)
                
                # 頁籤 3: 差異部份（如果有目標檔案）
                if diff_analysis['has_target'] and diff_analysis['differences']:
                    diff_sheet_name = f"{overwrite_type}_差異部份"
                    df_diff = pd.DataFrame(diff_analysis['differences'])
                    
                    # 調整欄位順序
                    diff_columns = [
                        'SN', 'diff_line', 'name', 'path', 'revision', 'upstream', 
                        'dest-branch', 'groups', 'clone-depth', 'remote',
                        'gerrit_diff_line', 'gerrit_name', 'gerrit_path', 'gerrit_revision',
                        'gerrit_upstream', 'gerrit_dest-branch', 'gerrit_groups', 
                        'gerrit_clone-depth', 'gerrit_remote'
                    ]
                    
                    # 只保留存在的欄位
                    available_columns = [col for col in diff_columns if col in df_diff.columns]
                    df_diff = df_diff[available_columns]
                    
                    df_diff.to_excel(writer, sheet_name=diff_sheet_name, index=False)
                
                # 格式化所有工作表
                for sheet_name in writer.sheets:
                    worksheet = writer.sheets[sheet_name]
                    self.excel_handler._format_worksheet(worksheet)
                    
                    # 特別格式化差異部份頁籤
                    if '差異部份' in sheet_name:
                        self._format_diff_sheet(worksheet)
            
            self.logger.info(f"成功產生 Excel 報告: {excel_file}")
            return excel_file
            
        except Exception as e:
            self.logger.error(f"產生 Excel 報告失敗: {str(e)}")
            raise
    
    def _format_diff_sheet(self, worksheet):
        """格式化差異部份頁籤 - 綠底白字 vs 藍底白字"""
        try:
            from openpyxl.styles import PatternFill, Font
            from openpyxl.utils import get_column_letter
            
            # 定義顏色
            green_fill = PatternFill(start_color="00B050", end_color="00B050", fill_type="solid")  # 綠底
            blue_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")   # 藍底
            white_font = Font(color="FFFFFF", bold=True)  # 白字
            
            # 綠底白字欄位（轉換後的資料）
            green_columns = ['SN', 'diff_line', 'name', 'path', 'revision', 'upstream', 'dest-branch', 'groups', 'clone-depth', 'remote']
            
            # 藍底白字欄位（Gerrit 的資料）
            blue_columns = ['gerrit_diff_line', 'gerrit_name', 'gerrit_path', 'gerrit_revision', 'gerrit_upstream', 'gerrit_dest-branch', 'gerrit_groups', 'gerrit_clone-depth', 'gerrit_remote']
            
            # 找到各欄位的位置並設定格式
            for col_num, cell in enumerate(worksheet[1], 1):  # 標題列
                col_letter = get_column_letter(col_num)
                header_value = str(cell.value) if cell.value else ''
                
                if header_value in green_columns:
                    # 設定綠底白字
                    cell.fill = green_fill
                    cell.font = white_font
                elif header_value in blue_columns:
                    # 設定藍底白字
                    cell.fill = blue_fill
                    cell.font = white_font
            
            self.logger.info("已設定差異部份頁籤格式：綠底白字 vs 藍底白字")
            
        except Exception as e:
            self.logger.error(f"格式化差異頁籤失敗: {str(e)}")