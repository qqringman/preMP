#!/usr/bin/env python3
"""
Manifest 比較工具 - 完全基於 feature_three.py 的邏輯
支援本地檔案與 Gerrit manifest 比較，不執行轉換只做純比對
使用與 feature_three.py 完全相同的處理和 Excel 輸出格式
"""

import os
import sys
import xml.etree.ElementTree as ET
import pandas as pd
from typing import Dict, List, Tuple, Optional, Any
import argparse
from datetime import datetime
import logging
import tempfile
import subprocess
import shutil
import re

# 添加專案路徑
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import config
from overwrite_lib.feature_three import FeatureThree
from excel_handler import ExcelHandler
from gerrit_manager import GerritManager
import utils

# 設定日誌
logger = utils.setup_logger(__name__)

class ManifestComparator:
    """Manifest 比較器 - 完全基於 feature_three.py 的邏輯，但不執行轉換"""
    
    def __init__(self):
        self.feature_three = FeatureThree()
        self.excel_handler = ExcelHandler()
        self.gerrit_manager = GerritManager()
        self.logger = logger
        
        # 檔案路徑記錄（與 feature_three 一致）
        self.local_file_path = None
        self.gerrit_file_path = None
        self.expanded_file_path = None
        self.use_expanded = False
        
        # Gerrit 檔案 URL 映射
        self.gerrit_urls = {
            'master': {
                'filename': 'atv-google-refplus.xml',
                'url': 'https://mm2sd.rtkbf.com/gerrit/plugins/gitiles/realtek/android/manifest/+/refs/heads/realtek/android-14/master/atv-google-refplus.xml'
            },
            'premp': {
                'filename': 'atv-google-refplus-premp.xml',
                'url': 'https://mm2sd.rtkbf.com/gerrit/plugins/gitiles/realtek/android/manifest/+/refs/heads/realtek/android-14/master/atv-google-refplus-premp.xml'
            },
            'mp': {
                'filename': 'atv-google-refplus-wave.xml',
                'url': 'https://mm2sd.rtkbf.com/gerrit/plugins/gitiles/realtek/android/manifest/+/refs/heads/realtek/android-14/master/atv-google-refplus-wave.xml'
            },
            'mp_backup': {
                'filename': 'atv-google-refplus-wave-backup.xml',
                'url': 'https://mm2sd.rtkbf.com/gerrit/plugins/gitiles/realtek/android/manifest/+/refs/heads/realtek/android-14/master/atv-google-refplus-wave-backup.xml'
            }
        }
    
    def compare_local_with_gerrit(self, local_file: str, gerrit_type: str, output_file: str) -> bool:
        """
        比較本地檔案與 Gerrit manifest 檔案 - 不執行轉換，純比對
        
        Args:
            local_file: 本地檔案路徑
            gerrit_type: Gerrit 檔案類型 (master, premp, mp, mp_backup)
            output_file: 輸出 Excel 檔案路徑
            
        Returns:
            比較是否成功
        """
        try:
            self.logger.info("=" * 80)
            self.logger.info(f"開始執行本地檔案與 {gerrit_type.upper()} 比較（基於 feature_three.py 邏輯）")
            self.logger.info("=" * 80)
            
            # 確保輸出資料夾存在
            output_folder = os.path.dirname(output_file)
            if not output_folder:
                output_folder = "."
            utils.ensure_dir(output_folder)
            
            # 步驟 1: 複製本地檔案到 output 目錄
            self.logger.info("\n📋 步驟 1: 複製本地檔案到輸出目錄")
            self.local_file_path = self._copy_local_file_to_output(local_file, output_folder)
            
            # 步驟 2: 從 Gerrit 下載檔案
            self.logger.info(f"\n⬇️ 步驟 2: 從 Gerrit 下載 {gerrit_type.upper()} manifest")
            self.gerrit_file_path = self._download_gerrit_file(gerrit_type, output_folder)
            
            if not self.gerrit_file_path:
                self.logger.error(f"❌ 無法下載 {gerrit_type.upper()} manifest")
                return False
            
            # 步驟 3: 檢查並處理 Gerrit 檔案的 include 展開
            self.logger.info(f"\n🔍 步驟 3: 檢查 {gerrit_type.upper()} manifest 是否需要展開")
            actual_gerrit_file = self._handle_gerrit_include_expansion(self.gerrit_file_path, output_folder)
            
            # 步驟 4: 讀取檔案內容並創建 conversion_info（不執行轉換）
            self.logger.info(f"\n📊 步驟 4: 分析專案資訊（不執行轉換，純比對）")
            
            with open(self.local_file_path, 'r', encoding='utf-8') as f:
                local_content = f.read()
            
            with open(actual_gerrit_file, 'r', encoding='utf-8') as f:
                gerrit_content = f.read()
            
            # 創建 conversion_info（不執行轉換，只是分析）
            conversion_info = self._create_conversion_info_without_conversion(local_content)
            
            # 步驟 5: 執行差異分析（與 feature_three 一致）
            self.logger.info(f"\n📋 步驟 5: 執行差異分析（feature_three.py 邏輯）")
            
            diff_analysis = self._analyze_differences_like_feature_three(
                local_content, gerrit_content, f"local_vs_{gerrit_type}", conversion_info
            )
            
            # 步驟 6: 生成與 feature_three 完全相同格式的 Excel 報告
            self.logger.info(f"\n📄 步驟 6: 生成 Excel 報告（feature_three.py 完整格式）")
            
            success = self._generate_excel_report_like_feature_three(
                f"local_vs_{gerrit_type}", self.local_file_path, None, self.gerrit_file_path,
                diff_analysis, output_folder, os.path.basename(output_file),
                True, True, None, self.expanded_file_path, self.use_expanded
            )
            
            # 步驟 7: 顯示結果統計
            self._show_comparison_results(f"local_vs_{gerrit_type}", diff_analysis)
            
            return success
            
        except Exception as e:
            self.logger.error(f"本地檔案與 {gerrit_type.upper()} 比較執行失敗: {str(e)}")
            import traceback
            self.logger.error(f"詳細錯誤: {traceback.format_exc()}")
            return False
    
    def compare_local_files(self, file1: str, file2: str, output_file: str) -> bool:
        """
        比較兩個本地檔案 - 純比對，不執行轉換
        
        Args:
            file1: 本地檔案1路徑
            file2: 本地檔案2路徑
            output_file: 輸出 Excel 檔案路徑
            
        Returns:
            比較是否成功
        """
        try:
            self.logger.info("=" * 80)
            self.logger.info(f"開始執行本地檔案比較（基於 feature_three.py 邏輯）")
            self.logger.info("=" * 80)
            
            # 確保輸出資料夾存在
            output_folder = os.path.dirname(output_file)
            if not output_folder:
                output_folder = "."
            utils.ensure_dir(output_folder)
            
            # 複製檔案到 output 目錄
            self.logger.info("\n📋 複製檔案到輸出目錄")
            file1_dest = self._copy_local_file_to_output(file1, output_folder, "local_file1.xml")
            file2_dest = self._copy_local_file_to_output(file2, output_folder, "local_file2.xml")
            
            # 讀取檔案內容
            with open(file1_dest, 'r', encoding='utf-8') as f:
                content1 = f.read()
            
            with open(file2_dest, 'r', encoding='utf-8') as f:
                content2 = f.read()
            
            # 創建 conversion_info（不執行轉換）
            conversion_info = self._create_conversion_info_without_conversion(content1)
            
            # 執行差異分析
            diff_analysis = self._analyze_differences_like_feature_three(
                content1, content2, "local_vs_local", conversion_info
            )
            
            # 生成 Excel 報告
            success = self._generate_excel_report_like_feature_three(
                "local_vs_local", file1_dest, None, file2_dest,
                diff_analysis, output_folder, os.path.basename(output_file),
                True, True, None, None, False
            )
            
            self._show_comparison_results("local_vs_local", diff_analysis)
            
            return success
            
        except Exception as e:
            self.logger.error(f"本地檔案比較執行失敗: {str(e)}")
            import traceback
            self.logger.error(f"詳細錯誤: {traceback.format_exc()}")
            return False
    
    def _copy_local_file_to_output(self, local_file: str, output_folder: str, 
                                custom_name: Optional[str] = None) -> str:
        """
        複製本地檔案到輸出目錄 - 保留原始檔案名稱
        
        Args:
            local_file: 本地檔案路徑
            output_folder: 輸出資料夾
            custom_name: 自定義檔案名稱（可選）
            
        Returns:
            複製後的檔案路徑
        """
        try:
            if custom_name:
                dest_name = custom_name
            else:
                # 🔥 修正：直接保留原始檔案名稱，不加 local_ 前綴
                dest_name = os.path.basename(local_file)
            
            dest_path = os.path.join(output_folder, dest_name)
            shutil.copy2(local_file, dest_path)
            
            self.logger.info(f"✅ 複製本地檔案: {dest_name}")
            return dest_path
            
        except Exception as e:
            self.logger.error(f"複製本地檔案失敗: {str(e)}")
            raise
    
    def _download_gerrit_file(self, gerrit_type: str, output_folder: str) -> Optional[str]:
        """
        從 Gerrit 下載檔案到輸出目錄，使用 gerrit_ 前綴命名
        
        Args:
            gerrit_type: Gerrit 檔案類型
            output_folder: 輸出資料夾
            
        Returns:
            下載後的檔案路徑，失敗時返回 None
        """
        try:
            if gerrit_type not in self.gerrit_urls:
                self.logger.error(f"不支援的 Gerrit 類型: {gerrit_type}")
                return None
            
            config = self.gerrit_urls[gerrit_type]
            gerrit_filename = f"gerrit_{config['filename']}"
            gerrit_path = os.path.join(output_folder, gerrit_filename)
            
            self.logger.info(f"下載 {gerrit_type.upper()} manifest: {config['filename']}")
            self.logger.info(f"URL: {config['url']}")
            self.logger.info(f"保存為: {gerrit_filename}")
            
            # 使用 gerrit_manager 下載檔案
            success = self.gerrit_manager.download_file_from_link(config['url'], gerrit_path)
            
            if success and os.path.exists(gerrit_path):
                file_size = os.path.getsize(gerrit_path)
                self.logger.info(f"✅ 成功下載 {gerrit_type.upper()} manifest: {file_size} bytes")
                return gerrit_path
            else:
                self.logger.error(f"❌ 下載 {gerrit_type.upper()} manifest 失敗")
                return None
                
        except Exception as e:
            self.logger.error(f"下載 Gerrit 檔案異常: {str(e)}")
            return None
    
    def _handle_gerrit_include_expansion(self, gerrit_file_path: str, output_folder: str) -> str:
        """
        處理 Gerrit manifest 的 include 展開 - 完全使用 feature_three.py 的邏輯
        
        Args:
            gerrit_file_path: Gerrit 檔案路徑
            output_folder: 輸出資料夾
            
        Returns:
            實際使用的檔案路徑（可能是展開後的檔案）
        """
        try:
            self.logger.info("🔍 檢查 Gerrit manifest 是否需要展開")
            
            # 讀取 Gerrit 檔案內容
            with open(gerrit_file_path, 'r', encoding='utf-8') as f:
                gerrit_content = f.read()
            
            # 使用 feature_three 的邏輯檢查 include 標籤
            if not self.feature_three._has_include_tags(gerrit_content):
                self.logger.info("ℹ️ 未檢測到 include 標籤，使用原始檔案")
                return gerrit_file_path
            
            self.logger.info("🔍 檢測到 include 標籤，開始展開 manifest...")
            
            # 🔥 使用 feature_three 的展開邏輯
            # 根據檔案名稱推測 overwrite_type（只用於生成檔名）
            gerrit_filename = os.path.basename(gerrit_file_path)
            if 'atv-google-refplus.xml' in gerrit_filename:
                overwrite_type = 'master_to_premp'
            elif 'premp' in gerrit_filename:
                overwrite_type = 'premp_to_mp'
            elif 'wave-backup' in gerrit_filename:
                overwrite_type = 'mp_to_mpbackup'
            elif 'wave' in gerrit_filename:
                overwrite_type = 'premp_to_mp'
            else:
                overwrite_type = 'master_to_premp'  # 預設
            
            expanded_content, expanded_file_path = self.feature_three._expand_manifest_with_repo_fixed(
                overwrite_type, output_folder
            )
            
            if expanded_content and expanded_file_path and os.path.exists(expanded_file_path):
                self.expanded_file_path = expanded_file_path
                self.use_expanded = True
                self.logger.info(f"✅ Manifest 展開成功: {os.path.basename(expanded_file_path)}")
                self.logger.info(f"✅ 展開內容長度: {len(expanded_content)} 字符")
                return expanded_file_path
            else:
                self.logger.warning("⚠️ Manifest 展開失敗，使用原始檔案")
                return gerrit_file_path
                
        except Exception as e:
            self.logger.error(f"處理 include 展開時發生錯誤: {str(e)}")
            self.logger.warning("⚠️ 使用原始檔案繼續執行")
            return gerrit_file_path
        
    def _create_conversion_info_without_conversion(self, xml_content: str) -> List[Dict]:
        """
        創建 conversion_info 但不執行轉換 - 比較模式修正版，標記所有專案為參與比較
        
        Args:
            xml_content: XML 檔案內容
            
        Returns:
            專案列表（feature_three conversion_info 格式）
        """
        try:
            # 解析 XML
            root = ET.fromstring(xml_content)
            
            # 讀取 default 資訊（與 feature_three 一致）
            default_remote = ''
            default_revision = ''
            default_element = root.find('default')
            if default_element is not None:
                default_remote = default_element.get('remote', '')
                default_revision = default_element.get('revision', '')
            
            projects = []
            
            # 遍歷所有 project 元素（與 feature_three 一致）
            for project in root.findall('project'):
                project_name = project.get('name', '')
                project_path = project.get('path', '')
                project_remote = project.get('remote', '') or default_remote
                original_revision = project.get('revision', '')
                upstream = project.get('upstream', '')
                
                # 🔥 修正：在比較模式下，將所有專案標記為參與比較
                project_info = {
                    'name': project_name,
                    'path': project_path,
                    'original_revision': original_revision,
                    'effective_revision': original_revision,
                    'converted_revision': original_revision,  # 比較模式：保持原值
                    'upstream': upstream,
                    'dest-branch': project.get('dest-branch', ''),
                    'groups': project.get('groups', ''),
                    'clone-depth': project.get('clone-depth', ''),
                    'remote': project.get('remote', ''),
                    'original_remote': project.get('remote', ''),
                    'changed': True,  # 🔥 關鍵修正：標記為參與比較，讓差異分析邏輯能處理
                    'used_default_revision': False,
                    'used_upstream_for_conversion': False
                }
                
                projects.append(project_info)
            
            self.logger.info(f"成功分析 {len(projects)} 個專案（比較模式：所有專案都參與比較）")
            return projects
            
        except Exception as e:
            self.logger.error(f"分析專案資訊失敗: {str(e)}")
            return []
    
    def _analyze_differences_like_feature_three(self, local_content: str, gerrit_content: str,
                                              comparison_type: str, conversion_info: List[Dict]) -> Dict[str, Any]:
        """
        使用與 feature_three.py 完全相同的差異分析邏輯
        
        Args:
            local_content: 本地檔案內容
            gerrit_content: Gerrit 檔案內容
            comparison_type: 比較類型
            conversion_info: 轉換資訊（這裡是不轉換的專案資訊）
            
        Returns:
            差異分析結果（與 feature_three._analyze_differences 格式一致）
        """
        try:
            self.logger.info(f"🔍 執行差異分析（使用 feature_three.py 邏輯）")
            
            # 🔥 直接使用 feature_three 的差異分析邏輯
            analysis = self.feature_three._analyze_differences(
                local_content, gerrit_content, comparison_type, conversion_info
            )
            
            self.logger.info(f"差異分析完成:")
            self.logger.info(f"  📋 總專案數: {analysis['summary'].get('converted_count', 0)}")
            self.logger.info(f"  🔄 實際轉換專案: {analysis['summary'].get('actual_conversion_count', 0)} (比對模式為0)")
            self.logger.info(f"  ❌ 差異項目: {analysis['summary'].get('differences_count', 0)}")
            self.logger.info(f"  ✅ 相同項目: {analysis['summary'].get('identical_converted_count', 0)}")
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"差異分析失敗: {str(e)}")
            import traceback
            self.logger.error(f"詳細錯誤: {traceback.format_exc()}")
            
            # 返回基本的分析結果
            return {
                'has_target': True,
                'converted_projects': conversion_info,
                'target_projects': [],
                'differences': [],
                'summary': {
                    'converted_count': len(conversion_info),
                    'target_count': 0,
                    'actual_conversion_count': 0,  # 比對模式不執行轉換
                    'unchanged_count': len(conversion_info),
                    'differences_count': 0,
                    'identical_converted_count': 0,
                    'conversion_match_rate': "N/A (比對模式)"
                }
            }
    
    def _generate_excel_report_like_feature_three(self, overwrite_type: str, source_file_path: Optional[str],
                                                output_file_path: Optional[str], target_file_path: Optional[str], 
                                                diff_analysis: Dict, output_folder: str, 
                                                excel_filename: Optional[str], source_download_success: bool,
                                                target_download_success: bool, push_result: Optional[Dict[str, Any]] = None,
                                                expanded_file_path: Optional[str] = None, use_expanded: bool = False) -> bool:
        """
        使用與 feature_three.py 完全相同的 Excel 報告生成邏輯 - 比較模式優化版
        """
        try:
            self.logger.info("📝 生成 Excel 報告（使用 feature_three._generate_excel_report_safe，比較模式）")
            
            # 🔥 臨時修改 feature_three 的 _generate_excel_report 方法以適應比較模式
            original_method = self.feature_three._generate_excel_report
            
            def modified_generate_excel_report(*args, **kwargs):
                # 🔥 修改 push_result 為 None，避免產生推送相關欄位
                if 'push_result' in kwargs:
                    kwargs['push_result'] = None
                
                # 調用原始方法生成報告
                result = original_method(*args, **kwargs)
                
                # 🔥 後處理：針對比較模式進行優化
                try:
                    if result and os.path.exists(result):
                        from openpyxl import load_workbook
                        workbook = load_workbook(result)
                        
                        # 移除 "轉換後的 manifest" 頁籤（因為比較模式不需要）
                        if '轉換後的 manifest' in workbook.sheetnames:
                            del workbook['轉換後的 manifest']
                            self.logger.info("✅ 已移除 '轉換後的 manifest' 頁籤（比較模式不需要）")
                        
                        # 🔥 修正其他頁籤的檔案名稱問題和比較模式優化
                        self._fix_sheet_filenames(workbook, result, overwrite_type, source_file_path, target_file_path)
                        
                        # 🔥 更新比較摘要的統計數據
                        self._update_summary_statistics(workbook, diff_analysis)
                        
                        # 最終保存
                        workbook.save(result)
                        
                except Exception as e:
                    self.logger.warning(f"後處理 Excel 檔案時發生錯誤: {str(e)}")
                
                return result
            
            # 暫時替換方法
            self.feature_three._generate_excel_report = modified_generate_excel_report
            
            try:
                # 🔥 調用修改後的方法，確保不產生推送相關內容
                excel_file = self.feature_three._generate_excel_report_safe(
                    overwrite_type=overwrite_type,
                    source_file_path=source_file_path,
                    output_file_path=output_file_path,
                    target_file_path=target_file_path,
                    diff_analysis=diff_analysis,
                    output_folder=output_folder,
                    excel_filename=excel_filename,
                    source_download_success=source_download_success,
                    target_download_success=target_download_success,
                    push_result=None,  # 🔥 確保不產生推送相關內容
                    expanded_file_path=expanded_file_path,
                    use_expanded=use_expanded
                )
            finally:
                # 恢復原始方法
                self.feature_three._generate_excel_report = original_method
            
            if excel_file and os.path.exists(excel_file):
                self.logger.info(f"✅ Excel 報告生成成功（比較模式完全優化）: {excel_file}")
                return True
            else:
                self.logger.error("❌ Excel 報告生成失敗")
                return False
            
        except Exception as e:
            self.logger.error(f"生成 Excel 報告失敗: {str(e)}")
            import traceback
            self.logger.error(f"詳細錯誤: {traceback.format_exc()}")
            return False

    def _fix_revision_comparison_formulas_dynamic(self, worksheet, revision_equal_col: int, 
                                                source_revision_col: int, target_revision_col: int):
        """
        修正 "Revision 是否相等" 欄位的動態公式，支援用戶修改時自動更新
        
        Args:
            worksheet: 工作表
            revision_equal_col: "Revision 是否相等" 欄位位置
            source_revision_col: 來源 Revision 欄位位置
            target_revision_col: 目標 Revision 欄位位置
        """
        try:
            from openpyxl.utils import get_column_letter
            from openpyxl.styles import PatternFill, Font
            from openpyxl.formatting.rule import FormulaRule
            
            source_col_letter = get_column_letter(source_revision_col)
            target_col_letter = get_column_letter(target_revision_col)
            equal_col_letter = get_column_letter(revision_equal_col)
            
            self.logger.info(f"📊 設定動態 Revision 比較公式: {source_col_letter} 欄 vs {target_col_letter} 欄")
            
            # 🔥 為每一行設定動態公式
            for row in range(2, worksheet.max_row + 1):
                cell = worksheet.cell(row=row, column=revision_equal_col)
                
                # 🔥 設定動態 Excel 公式 - Y/N 格式
                formula = f'=IF({source_col_letter}{row}={target_col_letter}{row},"Y","N")'
                cell.value = formula
            
            # 🔥 設定條件格式 - 綠字和紅字
            # 定義顏色
            green_font = Font(color="00B050", bold=True)  # 綠字
            red_font = Font(color="FF0000", bold=True)    # 紅字
            
            # 🔥 條件格式規則 1: 當值為 "Y" 時顯示綠字
            green_rule = FormulaRule(
                formula=[f'${equal_col_letter}2="Y"'],
                font=green_font
            )
            
            # 🔥 條件格式規則 2: 當值為 "N" 時顯示紅字
            red_rule = FormulaRule(
                formula=[f'${equal_col_letter}2="N"'],
                font=red_font
            )
            
            # 🔥 應用條件格式到整個欄位範圍
            range_string = f"{equal_col_letter}2:{equal_col_letter}{worksheet.max_row}"
            worksheet.conditional_formatting.add(range_string, green_rule)
            worksheet.conditional_formatting.add(range_string, red_rule)
            
            self.logger.info(f"✅ 已設定動態 Revision 比較公式和條件格式")
            self.logger.info(f"   📍 公式範圍: {range_string}")
            self.logger.info(f"   🟢 相等顯示: Y (綠字)")
            self.logger.info(f"   🔴 不相等顯示: N (紅字)")
            self.logger.info(f"   🔄 支援用戶修改 {source_col_letter} 或 {target_col_letter} 欄位時自動更新")
            
        except Exception as e:
            self.logger.error(f"設定動態 Revision 比較公式失敗: {str(e)}")
            
    def _fix_sheet_filenames(self, workbook, excel_file: str, overwrite_type: str, 
                            source_file_path: Optional[str], target_file_path: Optional[str]):
        """
        修正 Excel 頁籤中的檔案名稱問題，調整比較模式的內容
        
        Args:
            workbook: Excel 工作簿
            excel_file: Excel 檔案路徑
            overwrite_type: 轉換類型
            source_file_path: 源檔案路徑
            target_file_path: 目標檔案路徑
        """
        try:
            # 🔥 定義表頭顏色和頁籤顏色 - 新增紫底白字和頁籤顏色
            from openpyxl.styles import PatternFill, Font
            blue_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")   # 藍底
            purple_fill = PatternFill(start_color="8A2BE2", end_color="8A2BE2", fill_type="solid") # 紫底
            orange_fill = PatternFill(start_color="FF8C00", end_color="FF8C00", fill_type="solid") # 橘底
            green_fill = PatternFill(start_color="00B050", end_color="00B050", fill_type="solid")  # 綠底
            white_font = Font(color="FFFFFF", bold=True)
            
            # 🔥 獲取 "比較專案內容差異明細" 頁籤的顏色作為參考
            reference_tab_color = None
            if '轉換後與 Gerrit manifest 的差異' in workbook.sheetnames:
                ref_ws = workbook['轉換後與 Gerrit manifest 的差異']
                reference_tab_color = ref_ws.sheet_properties.tabColor
            elif '比較專案內容差異明細' in workbook.sheetnames:
                ref_ws = workbook['比較專案內容差異明細']
                reference_tab_color = ref_ws.sheet_properties.tabColor
            
            # 🔥 完全重新設計 "比較摘要" 頁籤
            if '轉換摘要' in workbook.sheetnames or '比較摘要' in workbook.sheetnames:
                ws = workbook['轉換摘要'] if '轉換摘要' in workbook.sheetnames else workbook['比較摘要']
                ws.title = '比較摘要'
                
                # 🔥 清空原有內容，重新設計欄位
                ws.delete_rows(1, ws.max_row)
                
                # 🔥 重新設計表頭 - 包含新的統計欄位
                headers = [
                    'SN',
                    '比較類型', 
                    '來源檔案名稱',  # 紫底白字
                    '目標檔案類型',
                    '目標檔案下載狀態',
                    '目標檔案包含 include 標籤',
                    '目標檔案已展開',
                    '實際比較的目標檔案',  # 紫底白字
                    '📊 總專案數',
                    '🎯 目標檔案專案數',
                    '❌ 與現行版本版號差異數',  # 橘底白字
                    '✅ 與現行版本版號相同數',  # 橘底白字
                    '❌ 比較現行版本內容差異數',  # 綠底白字
                    '✅ 比較現行版本內容相同數'   # 綠底白字
                ]
                
                # 🔥 寫入表頭並設定顏色
                for col, header in enumerate(headers, 1):
                    cell = ws.cell(row=1, column=col)
                    cell.value = header
                    cell.font = white_font
                    
                    # 根據欄位設定顏色
                    if header in ['來源檔案名稱', '實際比較的目標檔案']:
                        cell.fill = purple_fill  # 紫底白字
                    elif header in ['❌ 與現行版本版號差異數', '✅ 與現行版本版號相同數']:
                        cell.fill = orange_fill  # 橘底白字
                    elif header in ['❌ 比較現行版本內容差異數', '✅ 比較現行版本內容相同數']:
                        cell.fill = green_fill   # 綠底白字
                    else:
                        cell.fill = blue_fill    # 預設藍底白字
                
                # 🔥 準備數據 - 修正目標檔案類型顯示實際檔案名稱
                target_type_mapping = {
                    'local_vs_master': 'atv-google-refplus.xml',
                    'local_vs_premp': 'atv-google-refplus-premp.xml', 
                    'local_vs_mp': 'atv-google-refplus-wave.xml',
                    'local_vs_mp_backup': 'atv-google-refplus-wave-backup.xml',
                    'local_vs_local': '本地檔案'
                }
                
                # 🔥 如果有實際的目標檔案，優先使用實際檔案名稱
                if target_file_path:
                    actual_filename = os.path.basename(target_file_path)
                    # 移除 gerrit_ 前綴來顯示原始檔名
                    if actual_filename.startswith('gerrit_'):
                        target_type = actual_filename[7:]  # 移除 "gerrit_" 前綴
                    else:
                        target_type = actual_filename
                else:
                    target_type = target_type_mapping.get(overwrite_type, '未知')
                
                # 獲取實際比較的目標檔案名稱
                actual_target_file = ""
                if hasattr(self, 'expanded_file_path') and self.expanded_file_path:
                    actual_target_file = os.path.basename(self.expanded_file_path)
                elif target_file_path:
                    actual_target_file = os.path.basename(target_file_path)
                
                # 🔥 寫入數據（第2行）- 只寫檔案名稱，不寫路徑
                data_row = [
                    1,  # SN
                    overwrite_type,  # 比較類型
                    os.path.basename(source_file_path) if source_file_path else '無',  # 來源檔案名稱（只要檔名）
                    target_type,  # 目標檔案類型
                    '成功' if target_file_path else '失敗',  # 目標檔案下載狀態
                    '是' if hasattr(self, 'use_expanded') and hasattr(self, 'expanded_file_path') and self.expanded_file_path else '否',  # 包含 include 標籤
                    '是' if hasattr(self, 'use_expanded') and self.use_expanded else '否',  # 已展開
                    actual_target_file,  # 實際比較的目標檔案
                    '',  # 總專案數 - 會被後續邏輯填入
                    '',  # 目標檔案專案數 - 會被後續邏輯填入
                    '',  # 版號差異數 - 會被後續邏輯填入
                    '',  # 版號相同數 - 會被後續邏輯填入
                    '',  # 內容差異數 - 會被後續邏輯填入
                    ''   # 內容相同數 - 會被後續邏輯填入
                ]
                
                for col, value in enumerate(data_row, 1):
                    ws.cell(row=2, column=col).value = value
                
                # 🔥 添加 "實際比較的目標檔案" 欄位超連結（第8欄）
                if actual_target_file and target_type != '本地檔案':
                    target_filename = actual_target_file.replace('gerrit_', '')
                    gerrit_url = self.feature_three._generate_gerrit_manifest_link(target_filename)
                    self.feature_three._add_hyperlink_to_cell(ws, 2, 8, gerrit_url, actual_target_file)
                
                self.logger.info("✅ 已重新設計 '比較摘要' 頁籤欄位（包含新統計欄位和顏色）")
            
            # 🔥 修正 "比較後專案" 頁籤 - 只新增欄位，保持原有所有欄位
            if '轉換後專案' in workbook.sheetnames or '比較後專案' in workbook.sheetnames:
                ws = workbook['轉換後專案'] if '轉換後專案' in workbook.sheetnames else workbook['比較後專案']
                ws.title = '與現行版本比較差異'
                
                # 🔥 找到現有欄位位置（不刪除任何欄位）
                source_revision_col = None
                target_revision_col = None
                revision_equal_col = None
                
                for col in range(1, ws.max_column + 1):
                    header_value = str(ws.cell(row=1, column=col).value) if ws.cell(row=1, column=col).value else ''
                    
                    if header_value in ['原始 Revision', '來源 Revision']:
                        source_revision_col = col
                    elif header_value in ['轉換後 Revision', '目標 Revision']:
                        target_revision_col = col
                    elif header_value in ['Revision 是否相等']:
                        revision_equal_col = col
                
                # 🔥 在 "來源 Revision" 左邊插入 "來源檔案" 欄位
                if source_revision_col:
                    ws.insert_cols(source_revision_col)
                    header_cell = ws.cell(row=1, column=source_revision_col)
                    header_cell.value = '來源檔案'
                    header_cell.fill = purple_fill
                    header_cell.font = white_font
                    
                    # 為所有資料行填入來源檔案名稱
                    source_filename = os.path.basename(source_file_path) if source_file_path else '無'
                    for row in range(2, ws.max_row + 1):
                        ws.cell(row=row, column=source_revision_col).value = source_filename
                    
                    # 🔥 更新其他欄位位置
                    target_revision_col += 1
                    if revision_equal_col and revision_equal_col > source_revision_col:
                        revision_equal_col += 1
                
                # 🔥 在 "目標 Revision" 左邊插入 "比較檔案" 欄位
                if target_revision_col:
                    ws.insert_cols(target_revision_col)
                    header_cell = ws.cell(row=1, column=target_revision_col)
                    header_cell.value = '比較檔案'
                    header_cell.fill = purple_fill
                    header_cell.font = white_font
                    
                    # 為所有資料行填入比較檔案名稱並添加超連結
                    actual_target_file = ""
                    if hasattr(self, 'expanded_file_path') and self.expanded_file_path:
                        actual_target_file = os.path.basename(self.expanded_file_path)
                    elif target_file_path:
                        actual_target_file = os.path.basename(target_file_path)
                    
                    for row in range(2, ws.max_row + 1):
                        ws.cell(row=row, column=target_revision_col).value = actual_target_file
                        
                        # 添加超連結
                        if actual_target_file:
                            clean_filename = actual_target_file.replace('gerrit_', '')
                            gerrit_url = self.feature_three._generate_gerrit_manifest_link(clean_filename)
                            self.feature_three._add_hyperlink_to_cell(ws, row, target_revision_col, gerrit_url, actual_target_file)
                    
                    # 🔥 更新 revision_equal_col 位置
                    if revision_equal_col and revision_equal_col > target_revision_col:
                        revision_equal_col += 1
                
                # 🔥 找到插入後的實際欄位位置
                final_source_revision_col = None
                final_target_revision_col = None
                final_revision_equal_col = None
                
                for col in range(1, ws.max_column + 1):
                    header_value = str(ws.cell(row=1, column=col).value) if ws.cell(row=1, column=col).value else ''
                    
                    if header_value in ['原始 Revision', '來源 Revision']:
                        ws.cell(row=1, column=col).value = '來源 Revision'
                        final_source_revision_col = col
                    elif header_value in ['轉換後 Revision', '目標 Revision']:
                        ws.cell(row=1, column=col).value = '目標 Revision'
                        final_target_revision_col = col
                    elif header_value in ['Revision 是否相等']:
                        final_revision_equal_col = col
                    elif header_value in ['轉換狀態', '比較狀態']:
                        ws.cell(row=1, column=col).value = '比較狀態'
                    elif header_value in ['轉換說明', '比較說明']:
                        ws.cell(row=1, column=col).value = '比較說明'
                
                # 🔥 修正 "Revision 是否相等" 欄位的動態公式
                if final_revision_equal_col and final_source_revision_col and final_target_revision_col:
                    self._fix_revision_comparison_formulas_dynamic(ws, final_revision_equal_col, final_source_revision_col, final_target_revision_col)
                
                # 🔥 設定頁籤顏色與 "比較專案內容差異明細" 頁籤一樣
                if reference_tab_color:
                    ws.sheet_properties.tabColor = reference_tab_color
                    self.logger.info("✅ 已設定 '與現行版本比較差異' 頁籤顏色與 '比較專案內容差異明細' 一致")
                
                self.logger.info("✅ 已完成 '與現行版本比較差異' 頁籤修正（保持所有原有欄位 + 動態公式）")
            
            # 🔥 修正 "比較差異明細" 頁籤名稱和 source_file 問題
            if '轉換後與 Gerrit manifest 的差異' in workbook.sheetnames or '比較差異明細' in workbook.sheetnames:
                ws_name = '轉換後與 Gerrit manifest 的差異' if '轉換後與 Gerrit manifest 的差異' in workbook.sheetnames else '比較差異明細'
                ws = workbook[ws_name]
                ws.title = '比較專案內容差異明細'
                
                # 🔥 修正 source_file 欄位內容和表頭顏色
                source_file_col = None
                comparison_result_col = None
                for col in range(1, ws.max_column + 1):
                    header_value = str(ws.cell(row=1, column=col).value) if ws.cell(row=1, column=col).value else ''
                    if header_value == 'source_file':
                        source_file_col = col
                        # 🔥 設定表頭為紫底白字
                        header_cell = ws.cell(row=1, column=col)
                        header_cell.fill = purple_fill
                        header_cell.font = white_font
                    elif header_value == 'comparison_result':
                        comparison_result_col = col
                
                if source_file_col and source_file_path:
                    source_filename = os.path.basename(source_file_path)
                    for row in range(2, ws.max_row + 1):
                        ws.cell(row=row, column=source_file_col).value = source_filename
                    
                    self.logger.info(f"✅ 修正 '比較專案內容差異明細' 頁籤 source_file 欄位: {source_filename}")
                
                # 🔥 修正 comparison_result 欄位內容
                if comparison_result_col:
                    for row in range(2, ws.max_row + 1):
                        cell = ws.cell(row=row, column=comparison_result_col)
                        if cell.value and "差異" in str(cell.value):
                            cell.value = "與現行 Gerrit 版本的內容有差異"
                    
                    self.logger.info("✅ 已修正 comparison_result 欄位內容")
                
                self.logger.info("✅ 已重新命名頁籤: '比較專案內容差異明細'")
            
            # 🔥 修正 "相同專案" 頁籤
            if '未轉換專案' in workbook.sheetnames or '相同專案' in workbook.sheetnames:
                ws_name = '未轉換專案' if '未轉換專案' in workbook.sheetnames else '相同專案'
                ws = workbook[ws_name]
                ws.title = '相同專案'
                
                # 修正表頭和內容...（保持原有邏輯）
                for col in range(1, ws.max_column + 1):
                    header_value = str(ws.cell(row=1, column=col).value) if ws.cell(row=1, column=col).value else ''
                    if header_value == '保持的 Revision':
                        ws.cell(row=1, column=col).value = '相同的 Revision'
                
                # 修正內容中的詞彙
                for row in range(2, ws.max_row + 1):
                    for col in range(1, ws.max_column + 1):
                        cell_value = str(ws.cell(row=row, column=col).value) if ws.cell(row=row, column=col).value else ''
                        
                        if '符合跳過轉換條件或無需轉換' in cell_value:
                            ws.cell(row=row, column=col).value = '兩檔案內容相同'
                        elif '符合跳過比較條件或無需比較' in cell_value:
                            ws.cell(row=row, column=col).value = '兩檔案內容相同'
                        elif 'Hash Revision' in cell_value:
                            ws.cell(row=row, column=col).value = '兩檔案內容相同 (Hash Revision)'
                        elif '需檢查是否來源端是否有問題' in cell_value:
                            ws.cell(row=row, column=col).value = '需檢查是否來源端有問題'
                
                # 移除 "需要紅字" 欄位並設定樣式
                needs_red_col = None
                for col in range(1, ws.max_column + 1):
                    if ws.cell(row=1, column=col).value == '需要紅字':
                        needs_red_col = col
                        break
                
                if needs_red_col:
                    ws.delete_cols(needs_red_col)
                    self.logger.info("✅ 已移除 '相同專案' 頁籤的 '需要紅字' 欄位")
                
                # 設定原因欄位顏色
                self._format_reason_column_like_source_revision(ws, workbook)
                
                self.logger.info("✅ 已完成 '相同專案' 頁籤修正")
            
            # 🔥 修正其他頁籤...（保持原有邏輯並新增表頭顏色）
            if '來源的 manifest' in workbook.sheetnames:
                ws = workbook['來源的 manifest']
                
                source_file_col = None
                for col in range(1, ws.max_column + 1):
                    header_value = str(ws.cell(row=1, column=col).value) if ws.cell(row=1, column=col).value else ''
                    if header_value == 'source_file':
                        source_file_col = col
                        # 🔥 設定表頭為紫底白字
                        header_cell = ws.cell(row=1, column=col)
                        header_cell.fill = purple_fill
                        header_cell.font = white_font
                        break
                
                if source_file_col and source_file_path:
                    from openpyxl.styles import Font
                    normal_font = Font(color="000000", underline=None)
                    
                    correct_filename = os.path.basename(source_file_path)
                    for row in range(2, ws.max_row + 1):
                        cell = ws.cell(row=row, column=source_file_col)
                        cell.value = correct_filename
                        cell.hyperlink = None
                        cell.font = normal_font
                    
                    self.logger.info(f"✅ 修正 '來源的 manifest' 頁籤檔案名稱（純文字）: {correct_filename}")
            
            if 'gerrit 上的 manifest' in workbook.sheetnames:
                ws = workbook['gerrit 上的 manifest']
                
                source_file_col = None
                for col in range(1, ws.max_column + 1):
                    header_value = str(ws.cell(row=1, column=col).value) if ws.cell(row=1, column=col).value else ''
                    if header_value == 'source_file':
                        source_file_col = col
                        # 🔥 設定表頭為紫底白字
                        header_cell = ws.cell(row=1, column=col)
                        header_cell.fill = purple_fill
                        header_cell.font = white_font
                        break
                
                if source_file_col and target_file_path:
                    correct_filename = os.path.basename(target_file_path)
                    gerrit_clean_filename = correct_filename.replace('gerrit_', '')
                    
                    for row in range(2, ws.max_row + 1):
                        ws.cell(row=row, column=source_file_col).value = correct_filename
                        gerrit_url = self.feature_three._generate_gerrit_manifest_link(gerrit_clean_filename)
                        self.feature_three._add_hyperlink_to_cell(ws, row, source_file_col, gerrit_url, correct_filename)
                    
                    self.logger.info(f"✅ 修正 'gerrit 上的 manifest' 頁籤檔案名稱和超連結: {correct_filename}")
            
            # 🔥 自動調整所有頁籤的欄寬
            self._auto_adjust_column_width(workbook)
            
            # 保存修改
            workbook.save(excel_file)
            self.logger.info("✅ Excel 檔案修正完成（完整比較模式優化 + 自動調整欄寬 + 動態公式）")
            
        except Exception as e:
            self.logger.error(f"修正 Excel 檔案失敗: {str(e)}")

    def _auto_adjust_column_width(self, workbook):
        """
        自動調整所有頁籤的欄寬
        
        Args:
            workbook: Excel 工作簿
        """
        try:
            from openpyxl.utils import get_column_letter
            
            for sheet_name in workbook.sheetnames:
                ws = workbook[sheet_name]
                
                # 遍歷每一欄
                for col in range(1, ws.max_column + 1):
                    max_length = 0
                    column_letter = get_column_letter(col)
                    
                    # 找出該欄最長的內容
                    for row in range(1, ws.max_row + 1):
                        cell_value = str(ws.cell(row=row, column=col).value) if ws.cell(row=row, column=col).value else ''
                        if len(cell_value) > max_length:
                            max_length = len(cell_value)
                    
                    # 設定欄寬（最小10，最大50）
                    adjusted_width = min(max(max_length + 2, 10), 50)
                    ws.column_dimensions[column_letter].width = adjusted_width
            
            self.logger.info("✅ 已自動調整所有頁籤的欄寬")
            
        except Exception as e:
            self.logger.error(f"自動調整欄寬失敗: {str(e)}")

    def _update_summary_statistics(self, workbook, diff_analysis: Dict):
        """
        更新比較摘要頁籤的統計數據 - 包含版號和內容的分別統計
        
        Args:
            workbook: Excel 工作簿
            diff_analysis: 差異分析結果
        """
        try:
            if '比較摘要' in workbook.sheetnames:
                ws = workbook['比較摘要']
                
                # 🔥 重新計算統計數據
                summary = diff_analysis.get('summary', {})
                differences = diff_analysis.get('differences', [])
                converted_projects = diff_analysis.get('converted_projects', [])
                
                # 計算版號差異統計
                revision_diff_count = 0
                revision_same_count = 0
                
                for proj in converted_projects:
                    original_rev = proj.get('original_revision', '')
                    converted_rev = proj.get('converted_revision', '')
                    
                    if original_rev != converted_rev:
                        revision_diff_count += 1
                    else:
                        revision_same_count += 1
                
                # 內容差異統計來自 differences（實際的專案內容比較）
                content_diff_count = len(differences)
                content_same_count = summary.get('identical_converted_count', 0)
                
                # 🔥 找到統計相關欄位的位置並更新
                stats_mapping = {
                    '📊 總專案數': summary.get('converted_count', 0),
                    '🎯 目標檔案專案數': summary.get('target_count', 0),
                    '❌ 與現行版本版號差異數': revision_diff_count,
                    '✅ 與現行版本版號相同數': revision_same_count,
                    '❌ 比較現行版本內容差異數': content_diff_count,
                    '✅ 比較現行版本內容相同數': content_same_count
                }
                
                for col in range(1, ws.max_column + 1):
                    header_value = str(ws.cell(row=1, column=col).value) if ws.cell(row=1, column=col).value else ''
                    
                    if header_value in stats_mapping:
                        ws.cell(row=2, column=col).value = stats_mapping[header_value]
                
                self.logger.info("✅ 已更新比較摘要頁籤的統計數據（包含版號和內容分別統計）")
                self.logger.info(f"   版號差異: {revision_diff_count}, 版號相同: {revision_same_count}")
                self.logger.info(f"   內容差異: {content_diff_count}, 內容相同: {content_same_count}")
        
        except Exception as e:
            self.logger.error(f"更新統計數據失敗: {str(e)}")
            
    def _format_reason_column_like_source_revision(self, current_ws, workbook):
        """
        設定 "相同專案" 頁籤的 "原因" 欄位顏色，參考 "比較後專案" 頁籤的 "來源 Revision" 樣式
        
        Args:
            current_ws: 當前工作表 ("相同專案")
            workbook: 整個工作簿
        """
        try:
            # 🔥 從 "比較後專案" 頁籤獲取 "來源 Revision" 的樣式
            reference_style = None
            if '比較後專案' in workbook.sheetnames:
                ref_ws = workbook['比較後專案']
                
                # 找到 "來源 Revision" 欄位
                source_revision_col = None
                for col in range(1, ref_ws.max_column + 1):
                    header_value = str(ref_ws.cell(row=1, column=col).value) if ref_ws.cell(row=1, column=col).value else ''
                    if header_value == '來源 Revision':
                        source_revision_col = col
                        break
                
                # 獲取表頭的樣式
                if source_revision_col:
                    header_cell = ref_ws.cell(row=1, column=source_revision_col)
                    reference_style = {
                        'fill': header_cell.fill,
                        'font': header_cell.font,
                        'alignment': header_cell.alignment,
                        'border': header_cell.border
                    }
                    self.logger.info("✅ 已獲取 '比較後專案' 頁籤 '來源 Revision' 的樣式")
            
            # 🔥 將樣式應用到 "相同專案" 頁籤的 "原因" 欄位表頭
            if reference_style:
                # 找到 "原因" 欄位
                reason_col = None
                for col in range(1, current_ws.max_column + 1):
                    header_value = str(current_ws.cell(row=1, column=col).value) if current_ws.cell(row=1, column=col).value else ''
                    if header_value == '原因':
                        reason_col = col
                        break
                
                if reason_col:
                    # 應用樣式到表頭
                    header_cell = current_ws.cell(row=1, column=reason_col)
                    header_cell.fill = reference_style['fill']
                    header_cell.font = reference_style['font']
                    header_cell.alignment = reference_style['alignment'] 
                    header_cell.border = reference_style['border']
                    
                    self.logger.info("✅ 已將 '來源 Revision' 樣式應用到 '原因' 欄位表頭")
                    
                    # 🔥 繼續處理原因欄位的紅字邏輯（針對內容）
                    self._format_unchanged_projects_reason_column_fixed(current_ws)
            
        except Exception as e:
            self.logger.error(f"設定原因欄位樣式失敗: {str(e)}")
            
    def _format_unchanged_projects_reason_column_fixed(self, worksheet):
        """格式化未轉換專案的原因欄位 - 修正版，不依賴 "需要紅字" 欄位"""
        try:
            from openpyxl.styles import Font
            
            red_font = Font(color="FF0000", bold=True)  # 紅字
            
            # 找到相關欄位的位置
            reason_col = None
            revision_col = None
            
            for col_num, cell in enumerate(worksheet[1], 1):
                header_value = str(cell.value) if cell.value else ''
                if header_value == '原因':
                    reason_col = col_num
                elif header_value == '保持的 Revision':
                    revision_col = col_num
            
            if not reason_col or not revision_col:
                self.logger.warning("無法找到必要欄位，跳過格式設定")
                return
            
            # 🔥 直接根據 "保持的 Revision" 欄位和 "原因" 欄位判斷是否需要紅字
            for row_num in range(2, worksheet.max_row + 1):
                revision_cell = worksheet.cell(row=row_num, column=revision_col)
                reason_cell = worksheet.cell(row=row_num, column=reason_col)
                
                revision_value = str(revision_cell.value) if revision_cell.value else ''
                reason_value = str(reason_cell.value) if reason_cell.value else ''
                
                # 如果有 revision 值且不是 hash，並且原因包含 "需檢查"，則設為紅字
                if revision_value and not self._is_revision_hash(revision_value) and "需檢查" in reason_value:
                    reason_cell.font = red_font
            
            self.logger.info("✅ 已設定未轉換專案原因欄位的紅字格式（修正版）")
            
        except Exception as e:
            self.logger.error(f"設定原因欄位紅字格式失敗: {str(e)}")

    def _is_revision_hash(self, revision: str) -> bool:
        """
        判斷 revision 是否為 commit hash - 與 feature_three.py 同步
        
        Args:
            revision: revision 字串
            
        Returns:
            True 如果是 hash，False 如果是 branch name
        """
        if not revision:
            return False
        
        revision = revision.strip()
        
        # Hash 特徵：40 字符的十六進制字符串
        if len(revision) == 40 and all(c in '0123456789abcdefABCDEF' for c in revision):
            return True
        
        # Hash 特徵：較短的 hash (7-12 字符的十六進制)
        if 7 <= len(revision) <= 12 and all(c in '0123456789abcdefABCDEF' for c in revision):
            return True
        
        # Branch name 特徵：包含斜線和可讀名稱
        if '/' in revision and any(c.isalpha() for c in revision):
            return False
        
        # 其他情況當作 branch name 處理
        return False
                                    
    def _show_comparison_results(self, comparison_type: str, diff_analysis: Dict):
        """顯示比較結果統計 - 修正詞彙"""
        self.logger.info(f"\n📈 {comparison_type} 比較結果統計:")
        self.logger.info(f"  🔧 使用邏輯: feature_three.py 完全相同")
        self.logger.info(f"  📋 Excel 格式: 比較模式優化版本")
        self.logger.info(f"  📄 處理模式: 純比對（不執行轉換）")
        self.logger.info(f"  📊 差異分析: 使用 feature_three._analyze_differences")
        self.logger.info(f"  📝 Excel 生成: 使用 feature_three._generate_excel_report_safe")
        self.logger.info(f"  🔥 比較模式優化: 移除無關欄位，修正詞彙，調整頁籤名稱")
        
        summary = diff_analysis.get('summary', {})
        self.logger.info(f"\n📊 統計摘要:")
        self.logger.info(f"  總專案數: {summary.get('converted_count', 0)}")
        self.logger.info(f"  差異項目數: {summary.get('differences_count', 0)}")
        self.logger.info(f"  相同項目數: {summary.get('identical_converted_count', 0)}")
        
        if self.use_expanded:
            self.logger.info(f"  🔍 特殊處理: Gerrit include 標籤已自動展開")
            self.logger.info(f"  📄 展開檔案: {os.path.basename(self.expanded_file_path) if self.expanded_file_path else 'N/A'}")
        
        self.logger.info("=" * 80)

# 為了保持與原始模組的兼容性，保留原始類名
class ManifestConversionTester(ManifestComparator):
    """保持與原始 API 的兼容性"""
    
    def __init__(self):
        super().__init__()
        # 保持統計格式的兼容性
        self.stats = {
            'total_projects': 0,
            'matched': 0,
            'mismatched': 0,
            'not_found_in_target': 0,
            'extra_in_target': 0,
            'no_revision_projects': 0,
            'revision_projects': 0,
            'skipped_special_projects': 0,
            'same_revision_projects': 0
        }
        self.failed_cases = []
    
    def test_conversion(self, source_file: str, target_file: str, output_file: str, 
                       comparison_type: str = 'master_vs_premp') -> bool:
        """兼容原始 API - 用於本地檔案比較"""
        return self.compare_local_files(source_file, target_file, output_file)


def main():
    """主函數"""
    parser = argparse.ArgumentParser(description='Manifest 比較工具 - 完全基於 feature_three.py 邏輯')
    parser.add_argument('local_file', help='本地 manifest.xml 檔案路徑')
    parser.add_argument('-g', '--gerrit-type', 
                       choices=['master', 'premp', 'mp', 'mp_backup'],
                       help='Gerrit 檔案類型 (與本地檔案比較)')
    parser.add_argument('-t', '--target-file', help='目標檔案路徑 (本地檔案比較)')
    parser.add_argument('-o', '--output', default='manifest_comparison_report.xlsx',
                       help='輸出 Excel 檔案名稱')
    
    args = parser.parse_args()
    
    # 確保輸出目錄存在
    output_dir = os.path.dirname(args.output) or '.'
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # 執行比較
    comparator = ManifestComparator()
    
    if args.gerrit_type:
        # 本地檔案與 Gerrit 比較
        success = comparator.compare_local_with_gerrit(args.local_file, args.gerrit_type, args.output)
        comparison_desc = f"本地檔案與 {args.gerrit_type.upper()}"
    elif args.target_file:
        # 本地檔案比較
        success = comparator.compare_local_files(args.local_file, args.target_file, args.output)
        comparison_desc = "本地檔案"
    else:
        print("❌ 請指定 --gerrit-type 或 --target-file")
        sys.exit(1)
    
    print(f"\n{'='*60}")
    if success:
        print(f"✅ {comparison_desc} 比較完成！")
        print(f"📊 報告檔案: {args.output}")
        print(f"🔧 使用邏輯: 完全基於 feature_three.py")
        print(f"📋 Excel 格式: 與 feature_three.py 完全一致")
        print(f"📄 處理模式: 純比對（不執行轉換）")
        if args.gerrit_type:
            print(f"🔍 include 處理: 自動檢測 Gerrit 檔案並展開")
    else:
        print(f"❌ {comparison_desc} 比較失敗")
        print(f"📄 請檢查日誌了解詳細錯誤")
    print(f"{'='*60}")
    
    # 返回狀態碼
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()