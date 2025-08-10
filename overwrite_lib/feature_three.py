"""
功能三：Manifest 轉換工具 - 微調版本
從 Gerrit 下載源檔案，進行 revision 轉換，並與目標檔案比較差異
微調：確保 Gerrit 檔案正確保存，增加 revision 比較資訊，標頭格式化
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
    """功能三：Manifest 轉換工具 - 微調版本"""
    
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
        處理功能三的主要邏輯 - 微調版本
        
        Args:
            overwrite_type: 轉換類型 (master_to_premp, premp_to_mp, mp_to_mpbackup)
            output_folder: 輸出資料夾
            excel_filename: 自定義 Excel 檔名
            
        Returns:
            是否處理成功
        """
        try:
            self.logger.info("=== 開始執行功能三：Manifest 轉換工具 (微調版本) ===")
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
            
            # 步驟 1.5: 保存源檔案到 output 資料夾（加上 gerrit_ 前綴）
            source_file_path = self._save_source_file(source_content, overwrite_type, output_folder)
            
            # 步驟 2: 進行 revision 轉換
            converted_content, conversion_info = self._convert_revisions(source_content, overwrite_type)
            
            # 步驟 3: 保存轉換後的檔案
            output_file_path = self._save_converted_file(converted_content, overwrite_type, output_folder)
            
            # 步驟 4: 從 Gerrit 下載目標檔案進行比較
            target_content = self._download_target_file(overwrite_type)
            target_file_path = None
            if target_content:
                target_file_path = self._save_target_file(target_content, overwrite_type, output_folder)
                # 再次確認檔案是否存在
                if target_file_path and os.path.exists(target_file_path):
                    self.logger.info(f"✅ 確認目標檔案已保存: {target_file_path}")
                else:
                    self.logger.error(f"❌ 目標檔案保存失敗或不存在: {target_file_path}")
            else:
                self.logger.warning("⚠️ 無法下載目標檔案，將跳過差異比較")
            
            # 步驟 5: 進行差異分析
            diff_analysis = self._analyze_differences(
                converted_content, target_content, overwrite_type, conversion_info
            )
            
            # 步驟 6: 產生 Excel 報告
            excel_file = self._generate_excel_report(
                overwrite_type, source_file_path, output_file_path, target_file_path, 
                diff_analysis, output_folder, excel_filename
            )
            
            # 最終檔案檢查和報告
            self._final_file_report(output_folder, source_file_path, output_file_path, target_file_path, 
                                   excel_file, source_download_success, target_download_success)
            
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
                    self.logger.info(f"臨時檔案位置: {temp_path}")
                    return content
                else:
                    self.logger.warning("下載目標檔案失敗，將只進行轉換不做比較")
                    return None
                    
            finally:
                # 清理臨時檔案
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                    self.logger.info(f"已清理臨時檔案: {temp_path}")
                    
        except Exception as e:
            self.logger.warning(f"下載目標檔案異常: {str(e)}")
            return None
    
    def _convert_revisions(self, xml_content: str, overwrite_type: str) -> Tuple[str, List[Dict]]:
        """根據轉換類型進行 revision 轉換 - 使用字串替換保留所有原始格式"""
        try:
            self.logger.info(f"開始進行 revision 轉換: {overwrite_type}")
            self.logger.info("使用字串替換方式，保留所有原始格式（包含註釋、空格等）")
            
            # 先用 ElementTree 解析以取得專案資訊（但不用於生成最終檔案）
            temp_root = ET.fromstring(xml_content)
            conversion_info = []
            conversion_count = 0
            
            # 建立轉換後的內容（從原始字串開始）
            converted_content = xml_content
            
            # 遍歷所有 project 元素以記錄轉換資訊
            for project in temp_root.findall('project'):
                revision = project.get('revision')
                project_name = project.get('name', '')
                
                if not revision:
                    continue
                
                old_revision = revision
                new_revision = self._convert_single_revision(revision, overwrite_type)
                
                # 記錄轉換資訊
                conversion_info.append({
                    'name': project_name,
                    'path': project.get('path', ''),
                    'original_revision': old_revision,
                    'converted_revision': new_revision,
                    'upstream': project.get('upstream', ''),
                    'dest-branch': project.get('dest-branch', ''),
                    'groups': project.get('groups', ''),
                    'clone-depth': project.get('clone-depth', ''),
                    'remote': project.get('remote', ''),
                    'changed': new_revision != old_revision
                })
                
                # 如果需要轉換，在字串中直接替換
                if new_revision != old_revision:
                    # 使用正規表達式精確替換該專案的 revision
                    import re
                    
                    # 轉義專案名稱中的特殊字符
                    escaped_project_name = re.escape(project_name)
                    escaped_old_revision = re.escape(old_revision)
                    
                    replacement_success = False
                    
                    # 嘗試多種匹配模式
                    patterns_to_try = [
                        # 模式 1: name 在 revision 之前
                        rf'(<project[^>]*name="{escaped_project_name}"[^>]*revision=")({escaped_old_revision})(")',
                        # 模式 2: revision 在 name 之前  
                        rf'(<project[^>]*revision=")({escaped_old_revision})("[^>]*name="{escaped_project_name}")',
                        # 模式 3: 更寬鬆的匹配，允許更多空格和屬性
                        rf'(<project[^>]*name\s*=\s*"{escaped_project_name}"[^>]*revision\s*=\s*")({escaped_old_revision})(")',
                        rf'(<project[^>]*revision\s*=\s*")({escaped_old_revision})("[^>]*name\s*=\s*"{escaped_project_name}")',
                        # 模式 4: 單引號版本
                        rf"(<project[^>]*name='{escaped_project_name}'[^>]*revision=')({escaped_old_revision})(')",
                        rf"(<project[^>]*revision=')({escaped_old_revision})('[^>]*name='{escaped_project_name}')",
                    ]
                    
                    for i, pattern in enumerate(patterns_to_try):
                        if re.search(pattern, converted_content):
                            converted_content = re.sub(pattern, rf'\1{new_revision}\3', converted_content)
                            replacement_success = True
                            conversion_count += 1
                            self.logger.debug(f"字串替換成功 (模式{i+1}): {project_name} - {old_revision} → {new_revision}")
                            break
                    
                    if not replacement_success:
                        # 提供詳細診斷資訊
                        self.logger.warning(f"無法找到匹配的專案進行替換: {project_name}")
                        self.logger.debug(f"  專案名稱: {project_name}")
                        self.logger.debug(f"  原始 revision: {old_revision}")
                        self.logger.debug(f"  目標 revision: {new_revision}")
                        
                        # 搜尋該專案在檔案中的所有出現位置
                        project_matches = re.findall(rf'<project[^>]*name=.{escaped_project_name}.[^>]*>', converted_content)
                        if project_matches:
                            self.logger.debug(f"  找到的專案行數: {len(project_matches)}")
                            for j, match in enumerate(project_matches[:3]):  # 只顯示前3個
                                self.logger.debug(f"    專案行 {j+1}: {match}")
                        else:
                            self.logger.debug(f"  在 XML 中找不到該專案名稱")
                        
                        # 檢查是否該專案已經是目標 revision
                        if new_revision in converted_content and project_name in converted_content:
                            already_converted_matches = re.findall(
                                rf'<project[^>]*name=.{escaped_project_name}.[^>]*revision=.{re.escape(new_revision)}.[^>]*>', 
                                converted_content
                            )
                            if already_converted_matches:
                                self.logger.info(f"  ✅ 專案 {project_name} 已經是目標 revision: {new_revision}")
                                replacement_success = True
                                # 不增加 conversion_count，因為實際上沒有轉換
            
            self.logger.info(f"revision 轉換完成，共轉換 {conversion_count} 個專案")
            self.logger.info("✅ 保留了所有原始格式：XML 宣告、註釋、空格、換行等")
            
            return converted_content, conversion_info
            
        except Exception as e:
            self.logger.error(f"revision 轉換失敗: {str(e)}")
            return xml_content, []
    
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
    
    def _save_source_file(self, content: str, overwrite_type: str, output_folder: str) -> str:
        """保存源檔案（從 Gerrit 下載的源檔案） - 新增方法"""
        try:
            # 使用源檔案名並加上 gerrit_ 前綴
            source_filename = self.source_files[overwrite_type]
            gerrit_source_filename = f"gerrit_{source_filename}"
            source_path = os.path.join(output_folder, gerrit_source_filename)
            
            # 確保輸出資料夾存在
            utils.ensure_dir(output_folder)
            
            self.logger.info(f"準備保存源檔案到: {source_path}")
            self.logger.info(f"檔案內容長度: {len(content)} 字符")
            
            # 寫入檔案
            with open(source_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # 驗證檔案是否成功保存
            if os.path.exists(source_path):
                file_size = os.path.getsize(source_path)
                self.logger.info(f"✅ Gerrit 源檔案已成功保存: {source_path}")
                self.logger.info(f"✅ 檔案大小: {file_size} bytes")
                self.logger.info(f"✅ 檔案名格式: gerrit_{source_filename}")
                
                # 再次確認檔案內容
                with open(source_path, 'r', encoding='utf-8') as f:
                    saved_content = f.read()
                    if len(saved_content) == len(content):
                        self.logger.info(f"✅ 源檔案內容驗證成功: {len(saved_content)} 字符")
                    else:
                        self.logger.warning(f"⚠️ 源檔案內容長度不匹配: 原始 {len(content)}, 保存 {len(saved_content)}")
                
                return source_path
            else:
                raise Exception(f"源檔案保存後不存在: {source_path}")
                
        except Exception as e:
            self.logger.error(f"保存源檔案失敗: {str(e)}")
            self.logger.error(f"目標路徑: {source_path}")
            self.logger.error(f"輸出資料夾: {output_folder}")
            self.logger.error(f"檔案名: {gerrit_source_filename}")
            raise
    
    def _save_converted_file(self, content: str, overwrite_type: str, output_folder: str) -> str:
        """保存轉換後的檔案 - 增強版本，確保檔案正確保存"""
        try:
            output_filename = self.output_files[overwrite_type]
            output_path = os.path.join(output_folder, output_filename)
            
            # 確保輸出資料夾存在
            utils.ensure_dir(output_folder)
            
            self.logger.info(f"準備保存轉換檔案到: {output_path}")
            self.logger.info(f"檔案內容長度: {len(content)} 字符")
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # 驗證檔案是否成功保存
            if os.path.exists(output_path):
                file_size = os.path.getsize(output_path)
                self.logger.info(f"✅ 轉換後檔案已成功保存: {output_path}")
                self.logger.info(f"✅ 檔案大小: {file_size} bytes")
                
                # 再次確認檔案內容
                with open(output_path, 'r', encoding='utf-8') as f:
                    saved_content = f.read()
                    if len(saved_content) == len(content):
                        self.logger.info(f"✅ 檔案內容驗證成功: {len(saved_content)} 字符")
                    else:
                        self.logger.warning(f"⚠️ 檔案內容長度不匹配: 原始 {len(content)}, 保存 {len(saved_content)}")
                
                return output_path
            else:
                raise Exception(f"檔案保存後不存在: {output_path}")
            
        except Exception as e:
            self.logger.error(f"保存轉換檔案失敗: {str(e)}")
            self.logger.error(f"目標路徑: {output_path}")
            self.logger.error(f"輸出資料夾: {output_folder}")
            self.logger.error(f"檔案名: {output_filename}")
            raise
    
    def _save_target_file(self, content: str, overwrite_type: str, output_folder: str) -> str:
        """保存目標檔案（從 Gerrit 下載的） - 修正版本，確保檔案正確保存"""
        try:
            # 使用正確的目標檔名並加上 gerrit_ 前綴
            original_target_filename = self.target_files[overwrite_type]
            target_filename = f"gerrit_{original_target_filename}"
            target_path = os.path.join(output_folder, target_filename)
            
            # 確保輸出資料夾存在
            utils.ensure_dir(output_folder)
            
            self.logger.info(f"準備保存目標檔案到: {target_path}")
            self.logger.info(f"檔案內容長度: {len(content)} 字符")
            
            # 寫入檔案
            with open(target_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # 驗證檔案是否成功保存
            if os.path.exists(target_path):
                file_size = os.path.getsize(target_path)
                self.logger.info(f"✅ Gerrit 目標檔案已成功保存: {target_path}")
                self.logger.info(f"✅ 檔案大小: {file_size} bytes")
                self.logger.info(f"✅ 檔案名格式: gerrit_{original_target_filename}")
                
                # 再次確認檔案內容
                with open(target_path, 'r', encoding='utf-8') as f:
                    saved_content = f.read()
                    if len(saved_content) == len(content):
                        self.logger.info(f"✅ 檔案內容驗證成功: {len(saved_content)} 字符")
                    else:
                        self.logger.warning(f"⚠️ 檔案內容長度不匹配: 原始 {len(content)}, 保存 {len(saved_content)}")
                
                return target_path
            else:
                raise Exception(f"檔案保存後不存在: {target_path}")
                
        except Exception as e:
            self.logger.error(f"保存目標檔案失敗: {str(e)}")
            self.logger.error(f"目標路徑: {target_path}")
            self.logger.error(f"輸出資料夾: {output_folder}")
            self.logger.error(f"檔案名: {target_filename}")
            raise
    
    def _analyze_differences(self, converted_content: str, target_content: Optional[str], 
                           overwrite_type: str, conversion_info: List[Dict]) -> Dict[str, Any]:
        """分析轉換檔案與目標檔案的差異 - 微調版本，包含轉換資訊"""
        analysis = {
            'has_target': target_content is not None,
            'converted_projects': conversion_info,  # 使用詳細的轉換資訊
            'target_projects': [],
            'differences': [],
            'summary': {}
        }
        
        try:
            if target_content:
                # 解析目標檔案
                target_root = ET.fromstring(target_content)
                target_projects = self._extract_projects_with_line_numbers(target_content)
                analysis['target_projects'] = target_projects
                
                # 進行差異比較
                differences = self._compare_projects_with_conversion_info(conversion_info, target_projects)
                analysis['differences'] = differences
                
                # 統計摘要
                analysis['summary'] = {
                    'converted_count': len(conversion_info),
                    'target_count': len(target_projects),
                    'differences_count': len(differences),
                    'identical_count': len(conversion_info) - len(differences),
                    'conversion_count': sum(1 for proj in conversion_info if proj['changed'])
                }
                
                self.logger.info(f"差異分析完成: {len(differences)} 個差異")
            else:
                analysis['summary'] = {
                    'converted_count': len(conversion_info),
                    'target_count': 0,
                    'differences_count': 0,
                    'identical_count': 0,
                    'conversion_count': sum(1 for proj in conversion_info if proj['changed'])
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
    
    def _compare_projects_with_conversion_info(self, converted_projects: List[Dict], 
                                             target_projects: List[Dict]) -> List[Dict]:
        """使用轉換資訊比較專案差異"""
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
                    # 對於 revision，使用轉換後的值
                    if attr == 'revision':
                        conv_val = conv_proj.get('converted_revision', '')
                    
                    target_val = target_proj.get(attr, '')
                    
                    if conv_val != target_val:
                        diff_attrs.append(attr)
                
                # 如果有差異，記錄
                if diff_attrs:
                    difference = {
                        'SN': len(differences) + 1,
                        'diff_line': 0,  # 轉換檔案沒有實際行號
                        'name': conv_proj['name'],
                        'path': conv_proj['path'],
                        'revision': conv_proj['converted_revision'],
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
                        'original_revision': conv_proj['original_revision'],  # 新增原始 revision
                        'converted_full_line': '',  # 轉換檔案沒有實際行
                        'gerrit_full_line': target_proj['full_line']
                    }
                    differences.append(difference)
        
        return differences
    
    def _generate_excel_report(self, overwrite_type: str, source_file_path: Optional[str],
                             output_file_path: str, target_file_path: Optional[str], 
                             diff_analysis: Dict, output_folder: str, 
                             excel_filename: Optional[str], source_download_success: bool,
                             target_download_success: bool) -> str:
        """產生 Excel 報告 - 完整版本，包含下載狀態記錄和格式保留"""
        try:
            # 決定 Excel 檔名
            if excel_filename:
                excel_file = os.path.join(output_folder, excel_filename)
            else:
                default_name = f"{overwrite_type}_conversion_report.xlsx"
                excel_file = os.path.join(output_folder, default_name)
            
            with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
                # 頁籤 1: 轉換摘要 - 增強版本，包含下載狀態
                summary_data = [{
                    'SN': 1,
                    '轉換類型': overwrite_type,
                    'Gerrit 源檔案': os.path.basename(source_file_path) if source_file_path else '無',
                    '源檔案下載狀態': '成功' if source_download_success else '失敗',
                    '源檔案': self.source_files.get(overwrite_type, ''),
                    '輸出檔案': os.path.basename(output_file_path) if output_file_path else '',
                    'Gerrit 目標檔案': os.path.basename(target_file_path) if target_file_path else '無',
                    '目標檔案下載狀態': '成功' if target_download_success else '失敗 (檔案不存在)',
                    '目標檔案': self.target_files.get(overwrite_type, ''),
                    '轉換專案數': diff_analysis['summary'].get('converted_count', 0),
                    '實際轉換數': diff_analysis['summary'].get('conversion_count', 0),
                    '目標專案數': diff_analysis['summary'].get('target_count', 0),
                    '差異數量': diff_analysis['summary'].get('differences_count', 0),
                    '相同數量': diff_analysis['summary'].get('identical_count', 0)
                }]
                
                df_summary = pd.DataFrame(summary_data)
                df_summary.to_excel(writer, sheet_name='轉換摘要', index=False)
                
                # 頁籤 2: 轉換後專案清單 - 微調版本（增加 revision 資訊）
                if diff_analysis['converted_projects']:
                    converted_data = []
                    for i, proj in enumerate(diff_analysis['converted_projects'], 1):
                        converted_data.append({
                            'SN': i,
                            '專案名稱': proj['name'],
                            '路徑': proj['path'],
                            '原始 Revision': proj['original_revision'],
                            '轉換後 Revision': proj['converted_revision'],
                            '是否轉換': '是' if proj['changed'] else '否',
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
                    
                    # 調整欄位順序 - 增加原始 revision
                    diff_columns = [
                        'SN', 'diff_line', 'name', 'path', 'original_revision', 'revision', 
                        'upstream', 'dest-branch', 'groups', 'clone-depth', 'remote',
                        'gerrit_diff_line', 'gerrit_name', 'gerrit_path', 'gerrit_revision',
                        'gerrit_upstream', 'gerrit_dest-branch', 'gerrit_groups', 
                        'gerrit_clone-depth', 'gerrit_remote'
                    ]
                    
                    # 只保留存在的欄位
                    available_columns = [col for col in diff_columns if col in df_diff.columns]
                    df_diff = df_diff[available_columns]
                    
                    df_diff.to_excel(writer, sheet_name=diff_sheet_name, index=False)
                
                # 格式化所有工作表 - 增強版本（綠底白字標頭 + 下載狀態紅字標示）
                for sheet_name in writer.sheets:
                    worksheet = writer.sheets[sheet_name]
                    self._format_worksheet_with_green_headers(worksheet)
                    
                    # 特別格式化轉換摘要頁籤的下載狀態
                    if sheet_name == '轉換摘要':
                        self._format_download_status_columns(worksheet, source_download_success, target_download_success)
                    
                    # 特別格式化差異部份頁籤
                    if '差異部份' in sheet_name:
                        self._format_diff_sheet(worksheet)
            
            self.logger.info(f"成功產生 Excel 報告: {excel_file}")
            return excel_file
            
        except Exception as e:
            self.logger.error(f"產生 Excel 報告失敗: {str(e)}")
            raise
    
    def _format_worksheet_with_green_headers(self, worksheet):
        """格式化工作表 - 微調版本，所有標頭都用綠底白字"""
        try:
            from openpyxl.styles import PatternFill, Font, Alignment
            from openpyxl.utils import get_column_letter
            
            # 綠底白字格式
            green_fill = PatternFill(start_color="00B050", end_color="00B050", fill_type="solid")
            white_font = Font(color="FFFFFF", bold=True)
            center_alignment = Alignment(horizontal="center", vertical="center")
            
            # 設定所有標頭（第一列）為綠底白字
            for col_num in range(1, worksheet.max_column + 1):
                col_letter = get_column_letter(col_num)
                header_cell = worksheet[f"{col_letter}1"]
                
                header_cell.fill = green_fill
                header_cell.font = white_font
                header_cell.alignment = center_alignment
            
            # 自動調整欄寬
            for col_num in range(1, worksheet.max_column + 1):
                col_letter = get_column_letter(col_num)
                column = worksheet[col_letter]
                
                # 計算最大寬度
                max_length = 0
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                
                # 設定欄寬（最小8，最大50）
                adjusted_width = min(max(max_length + 2, 8), 50)
                worksheet.column_dimensions[col_letter].width = adjusted_width
            
            self.logger.info(f"已設定工作表格式：所有標頭綠底白字，自動調整欄寬")
            
        except Exception as e:
            self.logger.error(f"格式化工作表失敗: {str(e)}")
    
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
            green_columns = ['SN', 'diff_line', 'name', 'path', 'original_revision', 'revision', 'upstream', 'dest-branch', 'groups', 'clone-depth', 'remote']
            
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
    
    def _format_download_status_columns(self, worksheet, source_download_success: bool, 
                                      target_download_success: bool):
        """格式化下載狀態欄位 - 失敗狀態用紅字標示"""
        try:
            from openpyxl.styles import Font
            from openpyxl.utils import get_column_letter
            
            # 定義顏色
            red_font = Font(color="FF0000", bold=True)    # 紅字
            green_font = Font(color="00B050", bold=True)  # 綠字
            black_font = Font(color="000000")             # 黑字
            
            # 找到下載狀態欄位的位置
            status_columns = {}
            for col_num, cell in enumerate(worksheet[1], 1):  # 標題列
                header_value = str(cell.value) if cell.value else ''
                
                if '下載狀態' in header_value:
                    status_columns[header_value] = col_num
            
            # 格式化源檔案下載狀態欄位
            for header_name, col_num in status_columns.items():
                col_letter = get_column_letter(col_num)
                
                # 資料列（第2列開始）
                for row_num in range(2, worksheet.max_row + 1):
                    cell = worksheet[f"{col_letter}{row_num}"]
                    cell_value = str(cell.value) if cell.value else ''
                    
                    if '源檔案下載狀態' in header_name:
                        # 源檔案下載狀態
                        if source_download_success and '成功' in cell_value:
                            cell.font = green_font
                        elif not source_download_success and ('失敗' in cell_value or '不存在' in cell_value):
                            cell.font = red_font
                        else:
                            cell.font = black_font
                    
                    elif '目標檔案下載狀態' in header_name:
                        # 目標檔案下載狀態
                        if target_download_success and '成功' in cell_value:
                            cell.font = green_font
                        elif not target_download_success and ('失敗' in cell_value or '不存在' in cell_value):
                            cell.font = red_font
                        else:
                            cell.font = black_font
            
            self.logger.info("已設定下載狀態欄位格式：成功=綠字，失敗=紅字")
            
        except Exception as e:
            self.logger.error(f"格式化下載狀態欄位失敗: {str(e)}")
    
    def _final_file_report(self, output_folder: str, source_file_path: Optional[str], 
                          output_file_path: Optional[str], target_file_path: Optional[str], 
                          excel_file: str, source_download_success: bool, target_download_success: bool):
        """最終檔案檢查和報告 - 增強版本，包含下載狀態統計"""
        try:
            self.logger.info("📁 最終檔案檢查報告:")
            self.logger.info(f"📂 輸出資料夾: {output_folder}")
            
            # 檢查所有應該存在的檔案
            files_to_check = []
            
            if source_file_path:
                status = "✅" if source_download_success else "❌"
                files_to_check.append((f"Gerrit 源檔案 {status}", source_file_path))
            
            if output_file_path:
                files_to_check.append(("轉換後檔案 ✅", output_file_path))
            
            if target_file_path:
                status = "✅" if target_download_success else "❌"
                files_to_check.append((f"Gerrit 目標檔案 {status}", target_file_path))
            
            files_to_check.append(("Excel 報告 ✅", excel_file))
            
            # 逐一檢查檔案
            all_files_exist = True
            for file_type, file_path in files_to_check:
                if os.path.exists(file_path):
                    file_size = os.path.getsize(file_path)
                    filename = os.path.basename(file_path)
                    self.logger.info(f"  {file_type}: {filename} ({file_size} bytes)")
                else:
                    self.logger.error(f"  {file_type}: {file_path} (檔案不存在)")
                    all_files_exist = False
            
            # 下載狀態統計
            self.logger.info(f"\n📊 Gerrit 下載狀態統計:")
            self.logger.info(f"  🔵 源檔案下載: {'✅ 成功' if source_download_success else '❌ 失敗'}")
            self.logger.info(f"  🟡 目標檔案下載: {'✅ 成功' if target_download_success else '❌ 失敗 (檔案不存在)'}")
            
            if not target_download_success:
                self.logger.info(f"  💡 提示: 目標檔案在 Gerrit 上不存在是正常情況")
                self.logger.info(f"       這表示該 manifest 檔案尚未在 master 分支上建立")
            
            # 額外檢查 output 資料夾中的所有 XML 檔案
            self.logger.info(f"\n📋 Output 資料夾中的所有 XML 檔案:")
            xml_files_found = []
            try:
                for filename in os.listdir(output_folder):
                    if filename.lower().endswith('.xml'):
                        file_path = os.path.join(output_folder, filename)
                        file_size = os.path.getsize(file_path)
                        xml_files_found.append((filename, file_size))
                        self.logger.info(f"  📄 {filename} ({file_size} bytes)")
                
                if not xml_files_found:
                    self.logger.warning("  ⚠️ 沒有找到任何 XML 檔案")
                else:
                    self.logger.info(f"\n📊 XML 檔案統計:")
                    gerrit_files = [f for f in xml_files_found if f[0].startswith('gerrit_')]
                    converted_files = [f for f in xml_files_found if not f[0].startswith('gerrit_')]
                    
                    self.logger.info(f"  🔵 Gerrit 原始檔案: {len(gerrit_files)} 個")
                    for filename, size in gerrit_files:
                        self.logger.info(f"    - {filename} ({size} bytes)")
                    
                    self.logger.info(f"  🟢 轉換後檔案: {len(converted_files)} 個")
                    for filename, size in converted_files:
                        self.logger.info(f"    - {filename} ({size} bytes)")
                    
            except Exception as e:
                self.logger.error(f"  ❌ 無法列出資料夾內容: {str(e)}")
            
            # 總結
            if all_files_exist:
                self.logger.info(f"\n✅ 所有檔案都已成功保存")
                if source_file_path:
                    source_filename = os.path.basename(source_file_path)
                    self.logger.info(f"🎯 重點提醒: 已保存 Gerrit 源檔案為 {source_filename}")
                if not target_download_success:
                    self.logger.info(f"📋 Excel 報告中已記錄目標檔案下載失敗狀態（紅字標示）")
            else:
                self.logger.warning(f"\n⚠️ 部分檔案可能保存失敗，請檢查上述報告")
                
        except Exception as e:
            self.logger.error(f"檔案檢查報告失敗: {str(e)}")