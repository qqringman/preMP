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
                excel_filename: Optional[str] = None, push_to_gerrit: bool = False) -> bool:
        """
        處理功能三的主要邏輯 - 微調版本
        
        Args:
            overwrite_type: 轉換類型 (master_to_premp, premp_to_mp, mp_to_mpbackup)
            output_folder: 輸出資料夾
            excel_filename: 自定義 Excel 檔名
            push_to_gerrit: 是否推送到 Gerrit 服務器
            
        Returns:
            是否處理成功
        """
        try:
            self.logger.info("=== 開始執行功能三：Manifest 轉換工具 (微調版本) ===")
            self.logger.info(f"轉換類型: {overwrite_type}")
            self.logger.info(f"輸出資料夾: {output_folder}")
            self.logger.info(f"推送到 Gerrit: {'是' if push_to_gerrit else '否'}")
            
            # 驗證參數
            if overwrite_type not in self.source_files:
                self.logger.error(f"不支援的轉換類型: {overwrite_type}")
                return False
            
            # 確保輸出資料夾存在
            utils.ensure_dir(output_folder)
            
            # 記錄下載狀態
            source_download_success = False
            target_download_success = False
            
            # 步驟 1: 從 Gerrit 下載源檔案
            source_content = self._download_source_file(overwrite_type)
            if source_content:
                source_download_success = True
                self.logger.info("✅ 源檔案下載成功")
            else:
                self.logger.error("❌ 下載源檔案失敗")
                # 仍然繼續執行，生成錯誤報告
            
            # 步驟 1.5: 保存源檔案到 output 資料夾（加上 gerrit_ 前綴）
            source_file_path = None
            if source_content:
                source_file_path = self._save_source_file(source_content, overwrite_type, output_folder)
            
            # 步驟 2: 進行 revision 轉換
            if source_content:
                converted_content, conversion_info = self._convert_revisions(source_content, overwrite_type)
            else:
                # 如果沒有源檔案，建立空的轉換結果
                converted_content = ""
                conversion_info = []
            
            # 步驟 3: 保存轉換後的檔案
            output_file_path = None
            if converted_content:
                output_file_path = self._save_converted_file(converted_content, overwrite_type, output_folder)
            
            # 步驟 4: 從 Gerrit 下載目標檔案進行比較
            target_content = self._download_target_file(overwrite_type)
            target_file_path = None
            if target_content:
                target_download_success = True
                target_file_path = self._save_target_file(target_content, overwrite_type, output_folder)
                self.logger.info("✅ 目標檔案下載成功")
            else:
                self.logger.warning("⚠️ 無法下載目標檔案，將跳過差異比較")
            
            # 步驟 5: 進行差異分析
            diff_analysis = self._analyze_differences(
                converted_content, target_content, overwrite_type, conversion_info
            )
            
            # 步驟 6: 推送到 Gerrit（如果需要）
            push_result = None
            if push_to_gerrit and converted_content:
                self.logger.info("🚀 開始推送到 Gerrit...")
                push_result = self._push_to_gerrit(overwrite_type, converted_content, target_content, output_folder)
            else:
                self.logger.info("⏭️ 跳過 Gerrit 推送")
            
            # 步驟 7: 產生 Excel 報告
            excel_file = self._generate_excel_report_safe(
                overwrite_type, source_file_path, output_file_path, target_file_path, 
                diff_analysis, output_folder, excel_filename, source_download_success, 
                target_download_success, push_result
            )
            
            # 最終檔案檢查和報告
            self._final_file_report_complete(
                output_folder, source_file_path, output_file_path, target_file_path, 
                excel_file, source_download_success, target_download_success
            )
            
            self.logger.info(f"=== 功能三執行完成，Excel 報告：{excel_file} ===")
            return True
            
        except Exception as e:
            self.logger.error(f"功能三執行失敗: {str(e)}")
            
            # 即使失敗也嘗試生成錯誤報告
            try:
                error_excel = self._generate_error_report(output_folder, overwrite_type, str(e))
                if error_excel:
                    self.logger.info(f"已生成錯誤報告: {error_excel}")
            except:
                pass
            
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
    
    def _get_source_and_target_filenames(self, overwrite_type: str) -> tuple:
        """取得來源和目標檔案名稱"""
        source_filename = self.output_files.get(overwrite_type, 'unknown.xml')
        target_filename = f"gerrit_{self.target_files.get(overwrite_type, 'unknown.xml')}"
        return source_filename, target_filename
    
    def _build_project_line_content(self, project: Dict, use_converted_revision: bool = False) -> str:
        """根據專案資訊建立完整的 project 行內容"""
        try:
            # 建立基本的 project 標籤
            project_line = "<project"
            
            # 添加各個屬性（按照常見順序）
            attrs_order = ['name', 'path', 'revision', 'upstream', 'dest-branch', 'groups', 'clone-depth', 'remote']
            
            for attr in attrs_order:
                value = project.get(attr, '')
                
                # 特殊處理 revision
                if attr == 'revision' and use_converted_revision:
                    value = project.get('converted_revision', project.get('revision', ''))
                
                # 只添加非空值
                if value:
                    project_line += f' {attr}="{value}"'
            
            project_line += " />"
            
            return project_line
            
        except Exception as e:
            self.logger.error(f"建立 project 行內容失敗: {str(e)}")
            return f"<project name=\"{project.get('name', 'unknown')}\" ... />"
    
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
                
                # 進行差異比較（傳遞 overwrite_type）
                differences = self._compare_projects_with_conversion_info(
                    conversion_info, target_projects, overwrite_type
                )
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
        """提取專案資訊並記錄行號 - 改進版本，提取完整的project行內容"""
        projects = []
        lines = xml_content.split('\n')
        
        try:
            root = ET.fromstring(xml_content)
            
            # 為每個 project 找到對應的完整行內容
            for project in root.findall('project'):
                project_name = project.get('name', '')
                
                # 在原始內容中尋找對應的行號和完整內容
                line_number, full_line = self._find_project_line_and_content(lines, project_name)
                
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
                    'full_line': full_line  # 完整的project行內容
                }
                projects.append(project_info)
            
            return projects
            
        except Exception as e:
            self.logger.error(f"提取專案資訊失敗: {str(e)}")
            return []

    def _find_project_line_and_content(self, lines: List[str], project_name: str) -> tuple:
        """尋找專案在 XML 中的行號和完整內容"""
        line_number = 0
        full_content = ""
        
        try:
            for i, line in enumerate(lines, 1):
                stripped_line = line.strip()
                
                # 檢查是否包含該專案名稱
                if f'name="{project_name}"' in line:
                    line_number = i
                    
                    # 提取完整的project標籤內容
                    if stripped_line.startswith('<project') and stripped_line.endswith('/>'):
                        # 單行project標籤
                        full_content = stripped_line
                    elif stripped_line.startswith('<project'):
                        # 多行project標籤，需要收集到結束標籤
                        full_content = stripped_line
                        
                        # 繼續收集後續行直到找到結束
                        for j in range(i, len(lines)):
                            next_line = lines[j].strip()
                            if j > i - 1:  # 不重複第一行
                                full_content += " " + next_line
                            
                            if next_line.endswith('/>') or next_line.endswith('</project>'):
                                break
                    else:
                        # 如果不是以<project開始，可能是內容在前一行
                        full_content = stripped_line
                        
                        # 往前找project開始標籤
                        for k in range(i-2, -1, -1):
                            prev_line = lines[k].strip()
                            if prev_line.startswith('<project'):
                                # 組合完整內容
                                full_content = prev_line
                                for m in range(k+1, i):
                                    full_content += " " + lines[m].strip()
                                full_content += " " + stripped_line
                                line_number = k + 1
                                break
                    
                    break
            
            # 清理多餘的空格
            full_content = ' '.join(full_content.split())
            
            self.logger.debug(f"找到專案 {project_name} 在第 {line_number} 行: {full_content[:100]}...")
            
            return line_number, full_content
            
        except Exception as e:
            self.logger.error(f"尋找專案行失敗 {project_name}: {str(e)}")
            return 0, f"<project name=\"{project_name}\" ... />"

    def _get_full_project_line(self, lines: List[str], line_number: int) -> str:
        """取得完整的專案行（可能跨多行） - 改進版本"""
        if line_number == 0 or line_number > len(lines):
            return ''
        
        try:
            # 從指定行開始，找到完整的 project 標籤
            start_line = line_number - 1
            full_line = lines[start_line].strip()
            
            # 如果行不以 /> 或 > 結尾，可能跨多行
            if not (full_line.endswith('/>') or full_line.endswith('>')):
                for i in range(start_line + 1, len(lines)):
                    next_line = lines[i].strip()
                    full_line += ' ' + next_line
                    if next_line.endswith('/>') or next_line.endswith('>'):
                        break
            
            # 清理多餘的空格
            full_line = ' '.join(full_line.split())
            
            return full_line
            
        except Exception as e:
            self.logger.error(f"取得完整專案行失敗: {str(e)}")
            return ''
    
    def _compare_projects_with_conversion_info(self, converted_projects: List[Dict], 
                                             target_projects: List[Dict], overwrite_type: str) -> List[Dict]:
        """使用轉換資訊比較專案差異 - 修改版本（記錄完整內容）"""
        differences = []
        
        # 建立目標專案的索引
        target_index = {proj['name']: proj for proj in target_projects}
        
        # 取得正確的檔案名稱
        source_file, gerrit_source_file = self._get_source_and_target_filenames(overwrite_type)
        
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
                    # 建立轉換後檔案的 project 行內容
                    converted_content = self._build_project_line_content(conv_proj, use_converted_revision=True)
                    
                    difference = {
                        'SN': len(differences) + 1,
                        'source_file': source_file,  # 來源檔案
                        'content': converted_content,  # 完整的project行內容
                        'name': conv_proj['name'],
                        'path': conv_proj['path'],
                        'revision': conv_proj['converted_revision'],
                        'upstream': conv_proj['upstream'],
                        'dest-branch': conv_proj['dest-branch'],
                        'groups': conv_proj['groups'],
                        'clone-depth': conv_proj['clone-depth'],
                        'remote': conv_proj['remote'],
                        'gerrit_source_file': gerrit_source_file,  # Gerrit來源檔案
                        'gerrit_content': target_proj['full_line'],  # Gerrit的完整project行內容
                        'gerrit_name': target_proj['name'],
                        'gerrit_path': target_proj['path'],
                        'gerrit_revision': target_proj['revision'],
                        'gerrit_upstream': target_proj['upstream'],
                        'gerrit_dest-branch': target_proj['dest-branch'],
                        'gerrit_groups': target_proj['groups'],
                        'gerrit_clone-depth': target_proj['clone-depth'],
                        'gerrit_remote': target_proj['remote'],
                        'diff_attributes': diff_attrs,
                        'original_revision': conv_proj['original_revision'],  # 保留原始 revision
                    }
                    differences.append(difference)
        
        return differences
    
    def _push_to_gerrit(self, overwrite_type: str, converted_content: str, 
                       target_content: Optional[str], output_folder: str) -> Dict[str, Any]:
        """推送轉換後的檔案到 Gerrit 服務器"""
        push_result = {
            'success': False,
            'message': '',
            'need_push': False,
            'commit_id': '',
            'review_url': ''
        }
        
        try:
            self.logger.info("🚀 開始推送到 Gerrit 服務器...")
            
            # 判斷是否需要推送
            push_result['need_push'] = self._should_push_to_gerrit(converted_content, target_content)
            
            if not push_result['need_push']:
                push_result['success'] = True
                push_result['message'] = "目標檔案與轉換結果相同，無需推送"
                self.logger.info("✅ " + push_result['message'])
                return push_result
            
            # 執行 Git 操作
            git_result = self._execute_git_push(overwrite_type, converted_content, output_folder)
            
            push_result.update(git_result)
            
            if push_result['success']:
                self.logger.info(f"✅ 成功推送到 Gerrit: {push_result['review_url']}")
            else:
                self.logger.error(f"❌ 推送失敗: {push_result['message']}")
            
            return push_result
            
        except Exception as e:
            push_result['message'] = f"推送過程發生錯誤: {str(e)}"
            self.logger.error(push_result['message'])
            return push_result
    
    def _should_push_to_gerrit(self, converted_content: str, target_content: Optional[str]) -> bool:
        """判斷是否需要推送到 Gerrit"""
        if target_content is None:
            self.logger.info("🎯 目標檔案不存在，需要推送新檔案")
            return True
        
        # 簡單的內容比較（忽略空白差異）
        def normalize_content(content):
            return ''.join(content.split()) if content else ''
        
        converted_normalized = normalize_content(converted_content)
        target_normalized = normalize_content(target_content)
        
        if converted_normalized == target_normalized:
            self.logger.info("📋 轉換結果與目標檔案相同，無需推送")
            return False
        else:
            self.logger.info("🔄 轉換結果與目標檔案不同，需要推送更新")
            return True
    
    def _execute_git_push(self, overwrite_type: str, converted_content: str, output_folder: str) -> Dict[str, Any]:
        """執行 Git clone, commit, push 操作 - 修復版本（使用 commit-msg hook 自動生成 Change-Id）"""
        import subprocess
        import tempfile
        import shutil
        
        result = {
            'success': False,
            'message': '',
            'commit_id': '',
            'review_url': ''
        }
        
        # 建立臨時 Git 工作目錄
        temp_git_dir = None
        
        try:
            temp_git_dir = tempfile.mkdtemp(prefix='gerrit_push_')
            self.logger.info(f"📁 建立臨時 Git 目錄: {temp_git_dir}")
            
            # Git 設定
            repo_url = "ssh://mm2sd.rtkbf.com:29418/realtek/android/manifest"
            branch = "realtek/android-14/master"
            target_filename = self.output_files[overwrite_type]
            
            # 步驟 1: Clone repository
            self.logger.info(f"📥 Clone repository: {repo_url}")
            clone_cmd = ["git", "clone", "-b", branch, repo_url, temp_git_dir]
            
            subprocess.run(clone_cmd, check=True, capture_output=True, text=True, timeout=60)
            
            # 步驟 2: 切換到 Git 目錄並設定環境
            original_cwd = os.getcwd()
            os.chdir(temp_git_dir)
            
            # 步驟 2.5: 安裝 commit-msg hook（使用您提供的命令）
            self.logger.info(f"🔧 安裝 commit-msg hook...")
            try:
                # 使用您提供的命令格式
                hook_install_cmd = "gitdir=$(git rev-parse --git-dir); scp -p -P 29418 vince_lin@mm2sd.rtkbf.com:hooks/commit-msg ${gitdir}/hooks/"
                
                # 執行命令安裝 hook
                result_hook = subprocess.run(
                    hook_install_cmd,
                    shell=True,  # 使用 shell 來執行複合命令
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result_hook.returncode == 0:
                    self.logger.info(f"✅ commit-msg hook 安裝成功")
                    
                    # 驗證 hook 是否存在
                    gitdir_result = subprocess.run(["git", "rev-parse", "--git-dir"], 
                                                capture_output=True, text=True, check=True)
                    git_dir = gitdir_result.stdout.strip()
                    hook_path = os.path.join(git_dir, "hooks", "commit-msg")
                    
                    if os.path.exists(hook_path):
                        self.logger.info(f"✅ hook 檔案確認存在: {hook_path}")
                        
                        # 確保 hook 有執行權限
                        import stat
                        os.chmod(hook_path, stat.S_IRWXU | stat.S_IRGRP | stat.S_IROTH)
                        self.logger.info(f"✅ hook 執行權限設定完成")
                    else:
                        self.logger.warning(f"⚠️ hook 檔案不存在: {hook_path}")
                        
                else:
                    self.logger.warning(f"⚠️ commit-msg hook 安裝失敗: {result_hook.stderr}")
                    self.logger.info(f"📝 將不使用 hook，可能需要手動處理 Change-Id")
                    
            except subprocess.CalledProcessError as e:
                self.logger.warning(f"⚠️ 安裝 commit-msg hook 失敗: {e.stderr}")
            except Exception as e:
                self.logger.warning(f"⚠️ 安裝 commit-msg hook 異常: {str(e)}")
            
            # 步驟 3: 寫入轉換後的檔案
            target_file_path = os.path.join(temp_git_dir, target_filename)
            with open(target_file_path, 'w', encoding='utf-8') as f:
                f.write(converted_content)
            
            self.logger.info(f"📝 寫入檔案: {target_filename}")
            
            # 步驟 4: 檢查 Git 狀態
            status_result = subprocess.run(
                ["git", "status", "--porcelain"], 
                capture_output=True, text=True, check=True
            )
            
            if not status_result.stdout.strip():
                result['success'] = True
                result['message'] = "檔案內容無變化，無需推送"
                self.logger.info("✅ " + result['message'])
                return result
            
            # 步驟 5: Add 檔案
            subprocess.run(["git", "add", target_filename], check=True)
            
            # 步驟 6: Commit（讓 hook 自動生成 Change-Id）
            commit_message = f"""Auto-generated manifest update: {overwrite_type}

    Generated by manifest conversion tool
    Source: {self.source_files[overwrite_type]}
    Target: {target_filename}"""
            
            # 不手動添加 Change-Id，讓 commit-msg hook 處理
            commit_result = subprocess.run(
                ["git", "commit", "-m", commit_message],
                capture_output=True, text=True, check=True
            )
            
            # 取得 commit ID
            commit_id_result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True, text=True, check=True
            )
            result['commit_id'] = commit_id_result.stdout.strip()[:8]
            
            self.logger.info(f"📝 創建 commit: {result['commit_id']}")
            
            # 檢查 commit message 是否包含 Change-Id（由 hook 添加）
            commit_msg_result = subprocess.run(
                ["git", "log", "-1", "--pretty=format:%B"],
                capture_output=True, text=True, check=True
            )
            
            if "Change-Id:" in commit_msg_result.stdout:
                self.logger.info(f"✅ Change-Id 已由 hook 自動添加")
            else:
                self.logger.warning(f"⚠️ commit message 中沒有 Change-Id，推送可能失敗")
            
            # 步驟 7: Push to Gerrit for review
            push_cmd = ["git", "push", "origin", f"HEAD:refs/for/{branch}"]
            
            self.logger.info(f"🚀 推送到 Gerrit: {' '.join(push_cmd)}")
            
            push_result = subprocess.run(
                push_cmd, capture_output=True, text=True, check=True, timeout=60
            )
            
            # 解析 Gerrit review URL
            output_lines = push_result.stderr.split('\n')
            review_url = ""
            for line in output_lines:
                if 'https://' in line and 'gerrit' in line:
                    # 提取 URL
                    import re
                    url_match = re.search(r'https://[^\s]+', line)
                    if url_match:
                        review_url = url_match.group(0)
                        break
            
            result['success'] = True
            result['message'] = f"成功推送到 Gerrit，Commit ID: {result['commit_id']}"
            result['review_url'] = review_url or f"https://mm2sd.rtkbf.com/gerrit/#/q/commit:{result['commit_id']}"
            
            self.logger.info(f"🎉 推送成功！Review URL: {result['review_url']}")
            
            return result
            
        except subprocess.TimeoutExpired:
            result['message'] = "Git 操作逾時，請檢查網路連線"
            return result
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr if e.stderr else str(e)
            
            # 特別處理常見錯誤
            if "missing Change-Id" in error_msg or "invalid Change-Id" in error_msg:
                result['message'] = f"Change-Id 問題: {error_msg}"
                self.logger.error(f"Change-Id 錯誤，可能 hook 安裝失敗: {error_msg}")
                
                # 提供詳細的故障排除資訊
                self.logger.info(f"🔧 Change-Id 故障排除步驟:")
                self.logger.info(f"  1. 確認 SSH 連線到 mm2sd.rtkbf.com")
                self.logger.info(f"  2. 手動執行: gitdir=$(git rev-parse --git-dir); scp -p -P 29418 vince_lin@mm2sd.rtkbf.com:hooks/commit-msg ${{gitdir}}/hooks/")
                self.logger.info(f"  3. 確認 ~/.ssh/config 設定正確")
                self.logger.info(f"  4. 檢查 Gerrit 帳號權限")
                
            elif "Permission denied" in error_msg or "publickey" in error_msg:
                result['message'] = f"SSH 認證失敗: {error_msg}"
                self.logger.error(f"SSH 認證問題: {error_msg}")
                self.logger.info(f"🔑 SSH 故障排除:")
                self.logger.info(f"  1. 檢查 SSH 金鑰: ssh-add -l")
                self.logger.info(f"  2. 測試連線: ssh -T -p 29418 vince_lin@mm2sd.rtkbf.com")
                self.logger.info(f"  3. 檢查 ~/.ssh/config")
                
            elif "remote rejected" in error_msg:
                result['message'] = f"Gerrit 拒絕推送: {error_msg}"
                self.logger.error(f"Gerrit 拒絕: {error_msg}")
                
            else:
                result['message'] = f"Git 命令失敗: {error_msg}"
                
            return result
        except Exception as e:
            result['message'] = f"Git 操作異常: {str(e)}"
            return result
        finally:
            # 恢復原始工作目錄
            if 'original_cwd' in locals():
                os.chdir(original_cwd)
            
            # 清理臨時目錄
            if temp_git_dir and os.path.exists(temp_git_dir):
                try:
                    shutil.rmtree(temp_git_dir)
                    self.logger.info(f"🗑️  清理臨時目錄: {temp_git_dir}")
                except Exception as e:
                    self.logger.warning(f"清理臨時目錄失敗: {str(e)}")
    
    def _generate_excel_report(self, overwrite_type: str, source_file_path: Optional[str],
                             output_file_path: Optional[str], target_file_path: Optional[str], 
                             diff_analysis: Dict, output_folder: str, 
                             excel_filename: Optional[str], source_download_success: bool,
                             target_download_success: bool, push_result: Optional[Dict[str, Any]] = None) -> str:
        """產生 Excel 報告 - 完整版本，包含下載狀態記錄和推送結果"""
        try:
            # 決定 Excel 檔名
            if excel_filename:
                excel_file = os.path.join(output_folder, excel_filename)
            else:
                default_name = f"{overwrite_type}_conversion_report.xlsx"
                excel_file = os.path.join(output_folder, default_name)
            
            with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
                # 更新推送狀態到摘要資料
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
                
                # 添加推送相關資訊
                if push_result:
                    summary_data[0].update({
                        '推送狀態': '成功' if push_result['success'] else '失敗',
                        '推送結果': push_result['message'],
                        'Commit ID': push_result.get('commit_id', ''),
                        'Review URL': push_result.get('review_url', '')
                    })
                else:
                    summary_data[0].update({
                        '推送狀態': '未執行',
                        '推送結果': '未執行推送',
                        'Commit ID': '',
                        'Review URL': ''
                    })
                
                df_summary = pd.DataFrame(summary_data)
                df_summary.to_excel(writer, sheet_name='轉換摘要', index=False)
                
                # 頁籤 2: 轉換後專案清單 - 微調版本（增加 revision 資訊和中文表頭）
                if diff_analysis['converted_projects']:
                    converted_data = []
                    for i, proj in enumerate(diff_analysis['converted_projects'], 1):
                        converted_data.append({
                            'SN': i,
                            '專案名稱': proj['name'],
                            '路徑': proj['path'],
                            '原始 Revision': proj['original_revision'],  # 中文表頭
                            '轉換後 Revision': proj['converted_revision'],  # 中文表頭
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
                    
                    # 調整欄位順序 - 新版本（添加來源檔案欄位）
                    diff_columns = [
                        'SN', 
                        'source_file',  # 新增：來源檔案
                        'content',      # 修改：完整內容（原 diff_line）
                        'name', 'path', 'original_revision', 'revision', 
                        'upstream', 'dest-branch', 'groups', 'clone-depth', 'remote',
                        'gerrit_source_file',  # 新增：Gerrit來源檔案
                        'gerrit_content',      # 修改：Gerrit完整內容（原 gerrit_diff_line）
                        'gerrit_name', 'gerrit_path', 'gerrit_revision',
                        'gerrit_upstream', 'gerrit_dest-branch', 'gerrit_groups', 
                        'gerrit_clone-depth', 'gerrit_remote'
                    ]
                    
                    # 只保留存在的欄位
                    available_columns = [col for col in diff_columns if col in df_diff.columns]
                    df_diff = df_diff[available_columns]
                    
                    df_diff.to_excel(writer, sheet_name=diff_sheet_name, index=False)
                
                # 格式化所有工作表 - 增強版本（綠底白字標頭 + 下載狀態紅字標示 + 轉換後專案格式化）
                for sheet_name in writer.sheets:
                    worksheet = writer.sheets[sheet_name]
                    self.excel_handler._format_worksheet(worksheet)
                    
                    # 特別格式化轉換摘要頁籤的下載狀態
                    if sheet_name == '轉換摘要':
                        self._format_download_status_columns(worksheet, source_download_success, target_download_success)
                    
                    # 特別格式化轉換後專案頁籤
                    elif sheet_name == '轉換後專案':
                        self._format_converted_projects_sheet(worksheet)
                    
                    # 特別格式化差異部份頁籤
                    elif '差異部份' in sheet_name:
                        self._format_diff_sheet(worksheet)
            
            self.logger.info(f"成功產生 Excel 報告: {excel_file}")
            return excel_file
            
        except Exception as e:
            self.logger.error(f"產生 Excel 報告失敗: {str(e)}")
            raise
    
    def _format_converted_projects_sheet(self, worksheet):
        """格式化轉換後專案頁籤 - 新版本（紅底白字表頭 + 是否轉換內容顏色）"""
        try:
            from openpyxl.styles import PatternFill, Font
            from openpyxl.utils import get_column_letter
            
            # 定義顏色
            red_fill = PatternFill(start_color="C5504B", end_color="C5504B", fill_type="solid")    # 紅底
            white_font = Font(color="FFFFFF", bold=True)  # 白字
            blue_font = Font(color="0070C0", bold=True)   # 藍字（是）
            red_font = Font(color="C5504B", bold=True)    # 紅字（否）
            
            # 紅底白字表頭欄位
            red_header_columns = ['原始 Revision', '轉換後 Revision']
            
            # 找到各欄位的位置並設定表頭格式
            revision_columns = {}  # 記錄revision欄位位置
            conversion_column = None  # 記錄是否轉換欄位位置
            
            for col_num, cell in enumerate(worksheet[1], 1):  # 標題列
                col_letter = get_column_letter(col_num)
                header_value = str(cell.value) if cell.value else ''
                
                if header_value in red_header_columns:
                    # 設定紅底白字表頭
                    cell.fill = red_fill
                    cell.font = white_font
                    revision_columns[header_value] = col_num
                    self.logger.debug(f"設定紅底白字表頭: {header_value}")
                elif header_value == '是否轉換':
                    conversion_column = col_num
                    self.logger.debug(f"找到是否轉換欄位: 第{col_num}欄")
            
            # 設定是否轉換欄位的內容顏色
            if conversion_column:
                col_letter = get_column_letter(conversion_column)
                
                # 遍歷資料列（從第2列開始）
                for row_num in range(2, worksheet.max_row + 1):
                    cell = worksheet[f"{col_letter}{row_num}"]
                    cell_value = str(cell.value) if cell.value else ''
                    
                    if cell_value == '是':
                        cell.font = blue_font  # 是：藍色
                    elif cell_value == '否':
                        cell.font = red_font   # 否：紅色
            
            # 設定revision欄位的欄寬
            for header_name, col_num in revision_columns.items():
                col_letter = get_column_letter(col_num)
                worksheet.column_dimensions[col_letter].width = 35
                self.logger.debug(f"設定revision欄位寬度: {header_name} -> 35")
            
            self.logger.info("已設定轉換後專案頁籤格式：紅底白字表頭，是否轉換顏色區分")
            
        except Exception as e:
            self.logger.error(f"格式化轉換後專案頁籤失敗: {str(e)}")

    def _format_diff_sheet(self, worksheet):
        """格式化差異部份頁籤 - 新版本（綠底白字 vs 藍底白字 vs 紅底白字，包含來源檔案欄位）"""
        try:
            from openpyxl.styles import PatternFill, Font
            from openpyxl.utils import get_column_letter
            
            # 定義顏色
            green_fill = PatternFill(start_color="00B050", end_color="00B050", fill_type="solid")  # 綠底
            blue_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")   # 藍底
            red_fill = PatternFill(start_color="C5504B", end_color="C5504B", fill_type="solid")    # 紅底
            white_font = Font(color="FFFFFF", bold=True)  # 白字
            
            # 綠底白字欄位（轉換後的資料和來源檔案，除了revision相關）
            green_columns = [
                'SN', 'source_file', 'content', 'name', 'path',
                'upstream', 'dest-branch', 'groups', 'clone-depth', 'remote'
            ]
            
            # 藍底白字欄位（Gerrit 的資料和Gerrit來源檔案）
            blue_columns = [
                'gerrit_source_file', 'gerrit_content', 'gerrit_name', 'gerrit_path', 
                'gerrit_revision', 'gerrit_upstream', 'gerrit_dest-branch', 
                'gerrit_groups', 'gerrit_clone-depth', 'gerrit_remote'
            ]
            
            # 紅底白字欄位（revision 相關欄位，突出顯示變化）
            red_columns = [
                'original_revision', 'revision'
            ]
            
            # 找到各欄位的位置並設定格式
            for col_num, cell in enumerate(worksheet[1], 1):  # 標題列
                col_letter = get_column_letter(col_num)
                header_value = str(cell.value) if cell.value else ''
                
                if header_value in red_columns:
                    # 設定紅底白字（revision 欄位）
                    cell.fill = red_fill
                    cell.font = white_font
                    self.logger.debug(f"設定紅底白字欄位: {header_value}")
                elif header_value in green_columns:
                    # 設定綠底白字
                    cell.fill = green_fill
                    cell.font = white_font
                    self.logger.debug(f"設定綠底白字欄位: {header_value}")
                elif header_value in blue_columns:
                    # 設定藍底白字
                    cell.fill = blue_fill
                    cell.font = white_font
                    self.logger.debug(f"設定藍底白字欄位: {header_value}")
            
            # 特別處理各種欄位的欄寬
            for col_num, cell in enumerate(worksheet[1], 1):
                col_letter = get_column_letter(col_num)
                header_value = str(cell.value) if cell.value else ''
                
                if header_value in ['content', 'gerrit_content']:
                    # 設定較寬的欄寬以容納完整的 project 行
                    worksheet.column_dimensions[col_letter].width = 80
                    self.logger.debug(f"設定寬欄位: {header_value} -> 80")
                elif header_value in ['source_file', 'gerrit_source_file']:
                    # 設定檔名欄位的欄寬
                    worksheet.column_dimensions[col_letter].width = 25
                    self.logger.debug(f"設定檔名欄位: {header_value} -> 25")
                elif header_value in ['original_revision', 'revision', 'gerrit_revision']:
                    # 設定 revision 欄位的欄寬
                    worksheet.column_dimensions[col_letter].width = 35
                    self.logger.debug(f"設定 revision 欄位: {header_value} -> 35")
                elif header_value in ['upstream', 'dest-branch', 'gerrit_upstream', 'gerrit_dest-branch']:
                    # 設定分支欄位的欄寬
                    worksheet.column_dimensions[col_letter].width = 30
                    self.logger.debug(f"設定分支欄位: {header_value} -> 30")
            
            self.logger.info("已設定差異部份頁籤格式：綠底白字 vs 藍底白字 vs 紅底白字（revision），包含來源檔案欄位")
            
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
    
    def _generate_excel_report_safe(self, overwrite_type: str, source_file_path: Optional[str],
                                  output_file_path: Optional[str], target_file_path: Optional[str], 
                                  diff_analysis: Dict, output_folder: str, 
                                  excel_filename: Optional[str], source_download_success: bool,
                                  target_download_success: bool, push_result: Optional[Dict[str, Any]] = None) -> str:
        """安全的 Excel 報告生成 - 確保總是能產生報告"""
        try:
            return self._generate_excel_report(
                overwrite_type=overwrite_type,
                source_file_path=source_file_path,
                output_file_path=output_file_path,
                target_file_path=target_file_path,
                diff_analysis=diff_analysis,
                output_folder=output_folder,
                excel_filename=excel_filename,
                source_download_success=source_download_success,
                target_download_success=target_download_success,
                push_result=push_result
            )
        except Exception as e:
            self.logger.error(f"標準 Excel 報告生成失敗: {str(e)}")
            self.logger.info("嘗試生成基本錯誤報告...")
            return self._generate_error_report(output_folder, overwrite_type, str(e))
    
    def _generate_error_report(self, output_folder: str, overwrite_type: str, error_message: str) -> str:
        """生成基本錯誤報告"""
        try:
            excel_filename = f"{overwrite_type}_error_report.xlsx"
            excel_file = os.path.join(output_folder, excel_filename)
            
            error_data = [{
                'SN': 1,
                '轉換類型': overwrite_type,
                '處理狀態': '失敗',
                '錯誤訊息': error_message,
                '時間': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S'),
                '建議': '請檢查網路連線和 Gerrit 認證設定'
            }]
            
            with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
                df_error = pd.DataFrame(error_data)
                df_error.to_excel(writer, sheet_name='錯誤報告', index=False)
                
                # 格式化
                worksheet = writer.sheets['錯誤報告']
                self.excel_handler._format_worksheet(worksheet)
            
            self.logger.info(f"已生成基本錯誤報告: {excel_file}")
            return excel_file
            
        except Exception as e:
            self.logger.error(f"連基本錯誤報告都無法生成: {str(e)}")
            return ""
    
    def _final_file_report_complete(self, output_folder: str, source_file_path: Optional[str], 
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

# ===============================
# ===== 使用範例和說明 =====
# ===============================

"""
使用範例：

1. 基本使用（不推送到 Gerrit）：
   feature_three = FeatureThree()
   success = feature_three.process(
       overwrite_type='mp_to_mpbackup',
       output_folder='./output',
       excel_filename='my_report.xlsx',
       push_to_gerrit=False
   )

2. 完整使用（包含推送到 Gerrit）：
   feature_three = FeatureThree()
   success = feature_three.process(
       overwrite_type='master_to_premp',
       output_folder='./output',
       push_to_gerrit=True
   )

3. 命令行支援範例（需要在 main.py 中實現）：
   def _execute_feature_three(self):
       # ... 現有程式碼 ...
       
       # 新增：詢問是否推送到 Gerrit
       push_to_gerrit = self._get_yes_no_input(
           "是否要將轉換結果推送到 Gerrit 服務器？", False
       )
       
       success = self.feature_three.process(
           overwrite_type, output_folder, excel_filename, push_to_gerrit
       )

4. Gerrit 推送功能說明：
   - 自動判斷是否需要推送（目標檔案不存在或內容不同）
   - 執行 Git clone, commit, push 操作
   - 推送到 refs/for/branch（等待 Code Review）
   - 在 Excel 報告中記錄推送結果
   - 提供 Gerrit Review URL

5. 錯誤處理改進：
   - 即使下載失敗也會產生 Excel 報告
   - 詳細記錄失敗原因
   - 紅字標示下載失敗狀態
   - 提供故障排除建議

6. Excel 報告內容：
   ■ 轉換摘要頁籤：
     - 下載狀態（成功/失敗，紅綠字標示）
     - 推送狀態（成功/失敗/未執行）
     - Commit ID 和 Review URL
   
   ■ 轉換後專案頁籤：
     - 原始 Revision vs 轉換後 Revision（紅底白字表頭）
     - 是否轉換（是=藍色，否=紅色）
   
   ■ 差異部份頁籤：
     - 詳細差異分析（如有目標檔案）
     - 三色格式：綠色（基本）、紅色（revision）、藍色（Gerrit）

7. Git 需求：
   - 系統需要安裝 Git
   - 需要 SSH 認證到 mm2sd.rtkbf.com:29418
   - 建議設定 Git 用戶名和郵箱
"""