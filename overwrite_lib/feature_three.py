"""
功能三：去除版本號產生新的 manifest.xml
透過另一張 manifest.xml 去除版本號後產生另一張 manifest.xml
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
    """功能三：去除版本號產生新的 manifest"""
    
    def __init__(self):
        self.logger = logger
        self.excel_handler = ExcelHandler()
        self.gerrit_manager = GerritManager()
    
    def process(self, input_path: str, output_folder: str, process_type: str, 
                excel_filename: Optional[str] = None) -> bool:
        """
        處理功能三的主要邏輯
        
        Args:
            input_path: 輸入的 manifest.xml 檔案或資料夾路徑
            output_folder: 輸出資料夾
            process_type: 處理類型 (master, premp, mp, mpbackup)
            excel_filename: 自定義 Excel 檔名
            
        Returns:
            是否處理成功
        """
        try:
            self.logger.info("=== 開始執行功能三：去除版本號產生新 manifest ===")
            self.logger.info(f"輸入路徑: {input_path}")
            self.logger.info(f"輸出資料夾: {output_folder}")
            self.logger.info(f"處理類型: {process_type}")
            
            # 確保輸出資料夾存在
            utils.ensure_dir(output_folder)
            
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
            
            # 進行比較並產生報告
            comparison_results = []
            for result in results:
                if result['success']:
                    comparison_result = self._compare_with_gerrit(result, process_type)
                    comparison_results.append(comparison_result)
            
            # 產生 Excel 報告
            excel_file = self._generate_excel_report(results, comparison_results, output_folder, 
                                                   process_type, excel_filename)
            
            self.logger.info(f"=== 功能三執行完成，Excel 報告：{excel_file} ===")
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
                # 移除版本相關屬性
                for attr in ['dest-branch', 'revision', 'upstream']:
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
    
    def _compare_with_gerrit(self, result: Dict, process_type: str) -> Dict:
        """與 Gerrit 上的檔案進行比較 - 支援 XML 格式化比較"""
        comparison_result = result.copy()
        comparison_result.update({
            'gerrit_link': '',
            'comparison_status': '未比較',
            'comparison_message': ''
        })
        
        try:
            # 取得對應的 Gerrit 連結
            gerrit_link = self._get_gerrit_link(process_type)
            comparison_result['gerrit_link'] = gerrit_link
            
            if not gerrit_link:
                comparison_result['comparison_message'] = '無對應的 Gerrit 連結'
                return comparison_result
            
            self.logger.info(f"開始比較 Gerrit 檔案: {gerrit_link}")
            
            # 下載 Gerrit 檔案
            gerrit_content = self._download_gerrit_file_content(gerrit_link)
            
            if gerrit_content is None:
                comparison_result['comparison_status'] = 'Gerrit檔案無法存取'
                comparison_result['comparison_message'] = 'Gerrit 檔案不存在或無法下載'
                return comparison_result
            
            # 讀取本地檔案
            local_content = self._read_local_file_content(result['output_file'])
            
            if local_content is None:
                comparison_result['comparison_status'] = '讀取失敗'
                comparison_result['comparison_message'] = '無法讀取本地檔案'
                return comparison_result
            
            # 格式化兩個檔案以便比較
            gerrit_formatted = self._normalize_xml_for_comparison(gerrit_content)
            local_formatted = self._normalize_xml_for_comparison(local_content)
            
            # 比較格式化後的內容
            if gerrit_formatted == local_formatted:
                comparison_result['comparison_status'] = '相同'
                comparison_result['comparison_message'] = '檔案內容相同'
            else:
                comparison_result['comparison_status'] = '不同'
                
                # 提供更詳細的差異資訊
                gerrit_lines = len(gerrit_content.split('\n'))
                local_lines = len(local_content.split('\n'))
                gerrit_formatted_lines = len(gerrit_formatted.split('\n'))
                local_formatted_lines = len(local_formatted.split('\n'))
                
                comparison_result['comparison_message'] = (
                    f'檔案內容不同 (Gerrit: {gerrit_lines}→{gerrit_formatted_lines} 行, '
                    f'本地: {local_lines}→{local_formatted_lines} 行)'
                )
            
            self.logger.info(f"比較結果: {comparison_result['comparison_status']} - {result['output_filename']}")
            
        except Exception as e:
            comparison_result['comparison_status'] = '比較錯誤'
            comparison_result['comparison_message'] = f"比較過程發生錯誤: {str(e)}"
            self.logger.error(comparison_result['comparison_message'])
        
        return comparison_result

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
    
    def _download_gerrit_file_content(self, gerrit_link: str) -> Optional[str]:
        """下載 Gerrit 檔案內容 - 自動格式化 XML"""
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
                    
                    with open(temp_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # 統計行數
                    line_count = len(content.split('\n'))
                    self.logger.info(f"成功下載 Gerrit 檔案內容 ({file_size} bytes, {line_count} 行)")
                    
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
            self.logger.error(f"下載 Gerrit 檔案內容失敗: {str(e)}")
            return None
    
    def _read_local_file_content(self, file_path: str) -> Optional[str]:
        """讀取本地檔案內容"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            self.logger.error(f"讀取本地檔案失敗: {str(e)}")
            return None
    
    def _generate_excel_report(self, results: List[Dict], comparison_results: List[Dict],
                         output_folder: str, process_type: str, excel_filename: Optional[str]) -> str:
        """產生 Excel 報告"""
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
                
                # 比較結果頁籤
                if comparison_results:
                    df_comparison = pd.DataFrame(comparison_results)
                    # 重新編號
                    df_comparison['SN'] = range(1, len(df_comparison) + 1)
                    
                    # 調整欄位順序
                    comparison_columns = ['SN', 'source_filename', 'output_filename', 'output_file', 
                                        'gerrit_link', 'comparison_status', 'comparison_message']
                    df_comparison = df_comparison[[col for col in comparison_columns if col in df_comparison.columns]]
                else:
                    df_comparison = pd.DataFrame(columns=['SN', 'source_filename', 'output_filename', 'output_file', 
                                                        'gerrit_link', 'comparison_status', 'comparison_message'])
                
                df_comparison.to_excel(writer, sheet_name='比較結果', index=False)
                
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
                'Gerrit檔案不存在': {'fill': PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid"),
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