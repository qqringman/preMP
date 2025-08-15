#!/usr/bin/env python3
"""
Manifest 比較工具 - 完全獨立版本，不依賴 feature_three.py
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
from excel_handler import ExcelHandler
from gerrit_manager import GerritManager
import utils

# 設定日誌
logger = utils.setup_logger(__name__)

class ManifestComparator:
    """Manifest 比較器 - 完全獨立版本，不依賴 feature_three.py"""
    
    def __init__(self):
        """初始化方法 - 增加 local_vs_* 的檔案映射"""
        self.excel_handler = ExcelHandler()
        self.gerrit_manager = GerritManager()
        self.logger = logger
        
        # 檔案路徑記錄
        self.local_file_path = None
        self.gerrit_file_path = None
        self.expanded_file_path = None
        self.use_expanded = False
        
        # 從 feature_three.py 複製的設定
        self.gerrit_base_url = "https://mm2sd.rtkbf.com/gerrit/plugins/gitiles/realtek/android/manifest/+/refs/heads/realtek/android-14/master"
        
        # 檔案映射表（從 feature_three.py 複製）
        self.source_files = {
            'master_to_premp': 'atv-google-refplus.xml',
            'premp_to_mp': 'atv-google-refplus-premp.xml',
            'mp_to_mpbackup': 'atv-google-refplus-wave.xml'
        }
        
        self.output_files = {
            'master_to_premp': 'atv-google-refplus-premp.xml',
            'premp_to_mp': 'atv-google-refplus-wave.xml',
            'mp_to_mpbackup': 'atv-google-refplus-wave-backup.xml'
        }
        
        self.target_files = {
            'master_to_premp': 'atv-google-refplus-premp.xml',
            'premp_to_mp': 'atv-google-refplus-wave.xml', 
            'mp_to_mpbackup': 'atv-google-refplus-wave-backup.xml'
        }
        
        # 🔥 新增：local_vs_* 格式的檔案映射（用於比較模式）
        self.local_comparison_files = {
            'local_vs_master': {
                'source': 'atv-google-refplus.xml',
                'target': 'atv-google-refplus.xml'
            },
            'local_vs_premp': {
                'source': 'atv-google-refplus-premp.xml',
                'target': 'atv-google-refplus-premp.xml'
            },
            'local_vs_mp': {
                'source': 'atv-google-refplus-wave.xml',
                'target': 'atv-google-refplus-wave.xml'
            },
            'local_vs_mp_backup': {
                'source': 'atv-google-refplus-wave-backup.xml',
                'target': 'atv-google-refplus-wave-backup.xml'
            },
            'local_vs_local': {
                'source': 'local_file1.xml',  # 會在實際使用時被替換
                'target': 'local_file2.xml'   # 會在實際使用時被替換
            }
        }
        
        # Gerrit 檔案 URL 映射
        self.gerrit_urls = {
            'master': {
                'filename': 'atv-google-refplus.xml',
                'url': f'{self.gerrit_base_url}/atv-google-refplus.xml'
            },
            'premp': {
                'filename': 'atv-google-refplus-premp.xml',
                'url': f'{self.gerrit_base_url}/atv-google-refplus-premp.xml'
            },
            'mp': {
                'filename': 'atv-google-refplus-wave.xml',
                'url': f'{self.gerrit_base_url}/atv-google-refplus-wave.xml'
            },
            'mp_backup': {
                'filename': 'atv-google-refplus-wave-backup.xml',
                'url': f'{self.gerrit_base_url}/atv-google-refplus-wave-backup.xml'
            }
        }
    
    def compare_local_with_gerrit(self, local_file: str, gerrit_type: str, output_file: str) -> bool:
        """
        比較本地檔案與 Gerrit manifest 檔案 - 修正版：確保使用正確的比較邏輯
        """
        try:
            # 🔥 設定比較模式標記
            self._current_is_local_comparison = False
            
            self.logger.info("=" * 80)
            self.logger.info(f"開始執行本地檔案與 {gerrit_type.upper()} 比較（修正版）")
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
            
            # 步驟 4: 讀取檔案內容（🔥 修正：使用正確的比較邏輯）
            self.logger.info(f"\n📊 步驟 4: 分析專案資訊（使用修正的比較邏輯）")
            
            with open(self.local_file_path, 'r', encoding='utf-8') as f:
                local_content = f.read()
            
            with open(actual_gerrit_file, 'r', encoding='utf-8') as f:
                gerrit_content = f.read()
            
            # 🔥 修正：確保使用正確的比較邏輯
            conversion_info = self._create_conversion_info_for_local_comparison(local_content, gerrit_content)
            
            # 步驟 5: 執行差異分析
            self.logger.info(f"\n📋 步驟 5: 執行差異分析（修正邏輯）")
            
            diff_analysis = self._analyze_differences(
                local_content, gerrit_content, f"local_vs_{gerrit_type}", conversion_info
            )
            
            # 步驟 6: 生成 Excel 報告
            self.logger.info(f"\n📄 步驟 6: 生成 Excel 報告（修正格式）")
            
            success = self._generate_excel_report_like_feature_three(
                f"local_vs_{gerrit_type}", self.local_file_path, None, actual_gerrit_file,
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
        比較兩個本地檔案 - 純比對，不執行轉換（修正版：確保資料正確）
        """
        try:
            # 🔥 設定比較模式標記
            self._current_is_local_comparison = True
            
            self.logger.info("=" * 80)
            self.logger.info(f"開始執行本地檔案比較（修正版：確保 compare_ 欄位使用第二個檔案資料）")
            self.logger.info("=" * 80)
            
            # 確保輸出資料夾存在
            output_folder = os.path.dirname(output_file)
            if not output_folder:
                output_folder = "."
            utils.ensure_dir(output_folder)
            
            # 保留原始檔案名稱
            self.logger.info("\n📋 複製檔案到輸出目錄")
            file1_dest = self._copy_local_file_to_output(file1, output_folder)
            file2_dest = self._copy_local_file_to_output(file2, output_folder)
            
            # 讀取檔案內容
            with open(file1_dest, 'r', encoding='utf-8') as f:
                content1 = f.read()
            
            with open(file2_dest, 'r', encoding='utf-8') as f:
                content2 = f.read()
            
            # 為本地檔案比較創建正確的 conversion_info
            conversion_info = self._create_conversion_info_for_local_comparison(content1, content2)
            
            # 🔥 新增：驗證 target_projects 是否正確解析第二個檔案
            target_projects_verify = self._extract_projects_with_line_numbers(content2)
            self.logger.info(f"✅ 第二個檔案解析驗證: {len(target_projects_verify)} 個專案")
            
            # 🔥 新增：除錯檢查
            self._debug_local_comparison_data(conversion_info, target_projects_verify)
            
            # 執行差異分析
            diff_analysis = self._analyze_differences(
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

    # ===============================
    # ===== 從 feature_three.py 複製的方法 =====
    # ===============================

    def _has_include_tags(self, xml_content: str) -> bool:
        """
        檢查 XML 內容是否包含 include 標籤（從 feature_three.py 複製）
        """
        try:
            import re
            
            # 使用正規表達式檢查 include 標籤
            include_pattern = r'<include\s+name\s*=\s*["\'][^"\']*["\'][^>]*/?>'
            matches = re.findall(include_pattern, xml_content, re.IGNORECASE)
            
            if matches:
                self.logger.info(f"🔍 發現 {len(matches)} 個 include 標籤:")
                for i, match in enumerate(matches, 1):
                    self.logger.info(f"  {i}. {match}")
                return True
            else:
                self.logger.info("ℹ️ 未發現 include 標籤")
                return False
                
        except Exception as e:
            self.logger.error(f"檢查 include 標籤時發生錯誤: {str(e)}")
            return False

    def _expand_manifest_with_repo_fixed(self, overwrite_type: str, output_folder: str) -> tuple:
        """
        使用 repo 命令展開包含 include 的 manifest（從 feature_three.py 複製）
        """
        import subprocess
        import tempfile
        import shutil
        
        try:
            # 取得相關參數
            source_filename = self.source_files[overwrite_type]
            repo_url = "ssh://mm2sd.rtkbf.com:29418/realtek/android/manifest"
            branch = "realtek/android-14/master"
            
            # 生成展開檔案名稱
            expanded_filename = f"gerrit_{source_filename.replace('.xml', '_expand.xml')}"
            final_expanded_path = os.path.abspath(os.path.join(output_folder, expanded_filename))
            
            self.logger.info(f"🎯 準備展開 manifest...")
            self.logger.info(f"🎯 源檔案: {source_filename}")
            self.logger.info(f"🎯 展開檔案名: {expanded_filename}")
            self.logger.info(f"🎯 目標絕對路徑: {final_expanded_path}")
            
            # 在切換目錄前確保輸出資料夾存在
            utils.ensure_dir(output_folder)
            abs_output_folder = os.path.abspath(output_folder)
            self.logger.info(f"🎯 輸出資料夾絕對路徑: {abs_output_folder}")
            
            # 檢查 repo 命令是否可用
            try:
                repo_check = subprocess.run(
                    ["repo", "--version"], 
                    capture_output=True, 
                    text=True, 
                    timeout=10
                )
                if repo_check.returncode == 0:
                    self.logger.info(f"✅ repo 工具可用: {repo_check.stdout.strip()}")
                else:
                    self.logger.error(f"❌ repo 工具檢查失敗: {repo_check.stderr}")
                    return None, None
            except FileNotFoundError:
                self.logger.error("❌ repo 命令未找到，請確認已安裝 repo 工具")
                return None, None
            except Exception as e:
                self.logger.error(f"❌ repo 工具檢查異常: {str(e)}")
                return None, None
            
            # 建立臨時工作目錄
            temp_work_dir = tempfile.mkdtemp(prefix='repo_expand_')
            self.logger.info(f"📁 建立臨時工作目錄: {temp_work_dir}")
            
            original_cwd = os.getcwd()
            
            try:
                # 切換到臨時目錄
                os.chdir(temp_work_dir)
                self.logger.info(f"📂 切換到臨時目錄: {temp_work_dir}")
                
                # 步驟 1: repo init
                self.logger.info(f"🔄 執行 repo init...")
                init_cmd = [
                    "repo", "init", 
                    "-u", repo_url,
                    "-b", branch,
                    "-m", source_filename
                ]
                
                self.logger.info(f"🎯 Init 指令: {' '.join(init_cmd)}")
                
                init_result = subprocess.run(
                    init_cmd,
                    capture_output=True,
                    text=True,
                    timeout=120
                )
                
                self.logger.info(f"🔍 repo init 返回碼: {init_result.returncode}")
                if init_result.stdout:
                    self.logger.info(f"🔍 repo init stdout: {init_result.stdout}")
                if init_result.stderr:
                    self.logger.info(f"🔍 repo init stderr: {init_result.stderr}")
                
                if init_result.returncode != 0:
                    self.logger.error(f"❌ repo init 失敗 (返回碼: {init_result.returncode})")
                    return None, None
                
                self.logger.info("✅ repo init 成功")
                
                # 檢查 .repo 目錄是否存在
                repo_dir = os.path.join(temp_work_dir, ".repo")
                if os.path.exists(repo_dir):
                    self.logger.info(f"✅ .repo 目錄已建立: {repo_dir}")
                else:
                    self.logger.error(f"❌ .repo 目錄不存在: {repo_dir}")
                    return None, None
                
                # 步驟 2: repo manifest 展開
                self.logger.info(f"🔄 執行 repo manifest 展開...")
                
                manifest_cmd = ["repo", "manifest"]
                self.logger.info(f"🎯 Manifest 指令: {' '.join(manifest_cmd)}")
                
                manifest_result = subprocess.run(
                    manifest_cmd,
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                
                self.logger.info(f"🔍 repo manifest 返回碼: {manifest_result.returncode}")
                if manifest_result.stderr:
                    self.logger.info(f"🔍 repo manifest stderr: {manifest_result.stderr}")
                
                if manifest_result.returncode != 0:
                    self.logger.error(f"❌ repo manifest 失敗 (返回碼: {manifest_result.returncode})")
                    return None, None
                
                expanded_content = manifest_result.stdout
                
                if not expanded_content.strip():
                    self.logger.error("❌ repo manifest 返回空內容")
                    return None, None
                
                self.logger.info(f"✅ repo manifest 成功，內容長度: {len(expanded_content)} 字符")
                
                # 檢查展開內容的基本特徵
                project_count = expanded_content.count('<project ')
                include_count = expanded_content.count('<include ')
                self.logger.info(f"🔍 展開內容分析:")
                self.logger.info(f"   - Project 標籤數量: {project_count}")
                self.logger.info(f"   - Include 標籤數量: {include_count}")
                
                # 步驟 3A: 在臨時目錄保存一份展開檔案
                temp_expanded_path = os.path.join(temp_work_dir, expanded_filename)
                self.logger.info(f"📝 在臨時目錄保存展開檔案: {temp_expanded_path}")
                
                try:
                    with open(temp_expanded_path, 'w', encoding='utf-8') as f:
                        f.write(expanded_content)
                    self.logger.info(f"✅ 臨時目錄檔案保存成功")
                    
                    # 驗證臨時檔案
                    if os.path.exists(temp_expanded_path):
                        temp_file_size = os.path.getsize(temp_expanded_path)
                        self.logger.info(f"✅ 臨時檔案驗證: {temp_file_size} bytes")
                    
                except Exception as temp_write_error:
                    self.logger.error(f"❌ 臨時目錄檔案保存失敗: {str(temp_write_error)}")
                    return None, None
                
                # 步驟 3B: 複製到輸出資料夾
                self.logger.info(f"📝 複製展開檔案到輸出資料夾...")
                self.logger.info(f"📝 目標絕對路徑: {final_expanded_path}")
                
                # 確保目標資料夾存在
                target_dir = os.path.dirname(final_expanded_path)
                utils.ensure_dir(target_dir)
                self.logger.info(f"✅ 目標資料夾確認存在: {target_dir}")
                
                # 複製檔案到輸出目錄
                try:
                    shutil.copy2(temp_expanded_path, final_expanded_path)
                    self.logger.info(f"✅ 檔案複製完成（臨時→輸出）")
                except Exception as copy_error:
                    self.logger.error(f"❌ 檔案複製失敗: {str(copy_error)}")
                    return None, None
                
                # 步驟 4: 驗證檔案保存狀態
                if os.path.exists(final_expanded_path):
                    file_size = os.path.getsize(final_expanded_path)
                    self.logger.info(f"✅ 輸出檔案存在: {final_expanded_path} ({file_size} bytes)")
                    
                    # 驗證檔案內容一致性
                    try:
                        with open(final_expanded_path, 'r', encoding='utf-8') as f:
                            saved_content = f.read()
                            
                        if len(saved_content) == len(expanded_content):
                            self.logger.info(f"✅ 檔案內容驗證成功 ({len(saved_content)} 字符)")
                        else:
                            self.logger.warning(f"⚠️ 檔案內容長度不匹配: 原始 {len(expanded_content)}, 保存 {len(saved_content)}")
                            
                        # 驗證專案數量
                        saved_project_count = saved_content.count('<project ')
                        self.logger.info(f"✅ 保存檔案專案數量: {saved_project_count}")
                        
                    except Exception as read_error:
                        self.logger.error(f"❌ 檔案內容驗證失敗: {str(read_error)}")
                        return None, None
                    
                    # 成功返回
                    self.logger.info(f"🎉 展開檔案處理完成!")
                    self.logger.info(f"   📁 臨時位置: {temp_expanded_path}")
                    self.logger.info(f"   📁 輸出位置: {final_expanded_path}")
                    self.logger.info(f"   📊 檔案大小: {file_size} bytes")
                    self.logger.info(f"   📊 專案數量: {project_count}")
                    
                    return expanded_content, final_expanded_path
                else:
                    self.logger.error(f"❌ 輸出檔案不存在: {final_expanded_path}")
                    return None, None
                
            finally:
                # 恢復原始工作目錄
                os.chdir(original_cwd)
                
                # 清理臨時目錄
                try:
                    shutil.rmtree(temp_work_dir)
                    self.logger.info(f"🗑️ 清理臨時目錄成功: {temp_work_dir}")
                except Exception as e:
                    self.logger.warning(f"⚠️ 清理臨時目錄失敗: {str(e)}")
                
        except subprocess.TimeoutExpired:
            self.logger.error("❌ repo 命令執行超時")
            return None, None
        except Exception as e:
            self.logger.error(f"❌ 展開 manifest 時發生錯誤: {str(e)}")
            import traceback
            self.logger.error(f"❌ 錯誤詳情: {traceback.format_exc()}")
            return None, None

    def _analyze_differences(self, converted_content: str, target_content: Optional[str], 
                    overwrite_type: str, conversion_info: List[Dict]) -> Dict[str, Any]:
        """分析轉換檔案與目標檔案的差異（從 feature_three.py 複製）"""
        
        self.logger.info(f"🔍 差異分析檔案確認:")
        self.logger.info(f"   轉換類型: {overwrite_type}")
        self.logger.info(f"   轉換後內容長度: {len(converted_content) if converted_content else 0}")
        self.logger.info(f"   目標內容長度: {len(target_content) if target_content else 0}")
        
        analysis = {
            'has_target': target_content is not None,
            'converted_projects': conversion_info,
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
                differences = self._compare_projects_with_conversion_info(
                    conversion_info, target_projects, overwrite_type
                )
                analysis['differences'] = differences
                
                # 修正統計摘要
                total_projects = len(conversion_info)
                converted_projects = sum(1 for proj in conversion_info if proj.get('changed', False))
                unchanged_projects = total_projects - converted_projects
                
                analysis['summary'] = {
                    'converted_count': total_projects,
                    'target_count': len(target_projects),
                    'actual_conversion_count': converted_projects,
                    'unchanged_count': unchanged_projects,
                    'differences_count': len(differences),
                    'identical_converted_count': max(0, converted_projects - len(differences)),
                    'conversion_match_rate': f"{(max(0, converted_projects - len(differences)) / max(converted_projects, 1) * 100):.1f}%" if converted_projects > 0 else "N/A"
                }
                
                self.logger.info(f"差異分析完成:")
                self.logger.info(f"  📋 總專案數: {total_projects}")
                self.logger.info(f"  🔄 實際轉換專案: {converted_projects}")
                self.logger.info(f"  ⭕ 未轉換專案: {unchanged_projects}")
                self.logger.info(f"  ❌ 轉換後有差異: {len(differences)}")
                self.logger.info(f"  ✔️ 轉換後相同: {max(0, converted_projects - len(differences))}")
                if converted_projects > 0:
                    match_rate = max(0, converted_projects - len(differences)) / converted_projects * 100
                    self.logger.info(f"  📊 轉換匹配率: {match_rate:.1f}%")
            else:
                analysis['summary'] = {
                    'converted_count': len(conversion_info),
                    'target_count': 0,
                    'actual_conversion_count': sum(1 for proj in conversion_info if proj.get('changed', False)),
                    'unchanged_count': len(conversion_info) - sum(1 for proj in conversion_info if proj.get('changed', False)),
                    'differences_count': 0,
                    'identical_converted_count': 0,
                    'conversion_match_rate': "N/A (無目標檔案)"
                }
                self.logger.info("沒有目標檔案，跳過差異比較")
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"差異分析失敗: {str(e)}")
            return analysis

    def _extract_projects_with_line_numbers(self, xml_content: str) -> List[Dict[str, Any]]:
        """提取專案資訊並記錄行號（修正版：正確處理 default 值）"""
        projects = []
        lines = xml_content.split('\n')
        
        try:
            root = ET.fromstring(xml_content)
            
            # 🔥 修正：讀取 default 資訊
            default_remote = ''
            default_revision = ''
            default_element = root.find('default')
            if default_element is not None:
                default_remote = default_element.get('remote', '')
                default_revision = default_element.get('revision', '')
            
            # 為每個 project 找到對應的完整行內容
            for project in root.findall('project'):
                project_name = project.get('name', '')
                
                # 在原始內容中尋找對應的行號和完整內容
                line_number, full_line = self._find_project_line_and_content(lines, project_name)
                
                project_info = {
                    'line_number': line_number,
                    'name': project.get('name', ''),
                    'path': project.get('path', ''),
                    'revision': project.get('revision', '') or default_revision,  # 🔥 修正：正確處理 default revision
                    'upstream': project.get('upstream', ''),
                    'dest-branch': project.get('dest-branch', ''),
                    'groups': project.get('groups', ''),
                    'clone-depth': project.get('clone-depth', ''),
                    'remote': project.get('remote', '') or default_remote,  # 🔥 修正：正確處理 default remote
                    'full_line': full_line
                }
                projects.append(project_info)
            
            return projects
            
        except Exception as e:
            self.logger.error(f"提取專案資訊失敗: {str(e)}")
            return []

    def _debug_local_comparison_data(self, conversion_info: List[Dict], target_projects: List[Dict]):
        """除錯：檢查本地比較的資料是否正確"""
        try:
            self.logger.info("🔍 本地比較資料檢查:")
            
            # 檢查前3個專案的資料
            for i in range(min(3, len(conversion_info))):
                conv_proj = conversion_info[i]
                project_name = conv_proj['name']
                
                # 查找對應的目標專案
                target_proj = None
                for t_proj in target_projects:
                    if t_proj['name'] == project_name and t_proj['path'] == conv_proj['path']:
                        target_proj = t_proj
                        break
                
                self.logger.info(f"專案 {i+1}: {project_name}")
                self.logger.info(f"  來源 revision: {conv_proj['original_revision']}")
                self.logger.info(f"  目標 revision: {conv_proj['converted_revision']}")
                if target_proj:
                    self.logger.info(f"  target_projects revision: {target_proj['revision']}")
                    self.logger.info(f"  target_projects upstream: {target_proj['upstream']}")
                    self.logger.info(f"  target_projects groups: {target_proj['groups']}")
                else:
                    self.logger.info(f"  ⚠️ 在 target_projects 中找不到對應專案")
                
        except Exception as e:
            self.logger.error(f"除錯檢查失敗: {str(e)}")
            
    def _find_project_line_and_content(self, lines: List[str], project_name: str) -> tuple:
        """尋找專案在 XML 中的行號和完整內容（從 feature_three.py 複製）"""
        line_number = 0
        full_content = ""
        
        try:
            import re
            
            for i, line in enumerate(lines, 1):
                stripped_line = line.strip()
                
                # 檢查是否包含該專案名稱
                if f'name="{project_name}"' in line:
                    line_number = i
                    
                    # 使用正規表達式只抓取 project 標籤本身
                    if stripped_line.startswith('<project') and stripped_line.endswith('/>'):
                        # 單行 project 標籤
                        full_content = stripped_line
                    elif stripped_line.startswith('<project'):
                        # 多行 project 標籤，需要找到結束位置
                        if '/>' in stripped_line:
                            # project 標籤在同一行結束
                            project_match = re.search(r'<project[^>]*/?>', stripped_line)
                            if project_match:
                                full_content = project_match.group(0)
                        else:
                            # project 標籤跨多行，找到 > 結束
                            project_content = stripped_line
                            for j in range(i, len(lines)):
                                next_line = lines[j].strip()
                                if j > i - 1:
                                    project_content += " " + next_line
                                
                                if next_line.endswith('>'):
                                    project_match = re.search(r'<project[^>]*>', project_content)
                                    if project_match:
                                        full_content = project_match.group(0)
                                    break
                    else:
                        # 如果不是以<project開始，往前找
                        for k in range(i-2, -1, -1):
                            prev_line = lines[k].strip()
                            if prev_line.startswith('<project'):
                                # 組合完整內容，然後用正規表達式提取
                                combined_content = prev_line
                                for m in range(k+1, i):
                                    combined_content += " " + lines[m].strip()
                                combined_content += " " + stripped_line
                                
                                project_match = re.search(r'<project[^>]*/?>', combined_content)
                                if project_match:
                                    full_content = project_match.group(0)
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

    def _compare_projects_with_conversion_info(self, converted_projects: List[Dict], 
                                    target_projects: List[Dict], overwrite_type: str) -> List[Dict]:
        """使用轉換資訊比較專案差異（完整版：確保所有content欄位使用原始資料）"""
        differences = []
        
        # 🔥 判斷比較模式
        is_local_comparison = (overwrite_type == "local_vs_local")
        is_gerrit_comparison = overwrite_type.startswith("local_vs_") and overwrite_type != "local_vs_local"
        
        # 建立目標專案的索引
        target_index = {}
        for proj in target_projects:
            name = proj['name']
            path = proj['path']
            composite_key = f"{name}|{path}"
            target_index[composite_key] = proj
        
        # 獲得正確的檔案名稱
        source_file, gerrit_source_file = self._get_source_and_target_filenames(overwrite_type)
        
        # 🔥 新增：統計計數器
        total_compared = 0
        identical_count = 0
        different_count = 0
        
        for conv_proj in converted_projects:
            project_name = conv_proj['name']
            project_path = conv_proj['path']
            conv_composite_key = f"{project_name}|{project_path}"
            has_conversion = conv_proj.get('changed', False)
            
            # 只有真正有轉換的專案才進行差異比較
            if not has_conversion:
                continue
            
            total_compared += 1
            
            # 使用 composite key 查找對應專案
            if conv_composite_key not in target_index:
                # 專案在來源檔案存在，但在目標檔案中不存在
                different_count += 1
                comparison_result = '專案僅存在於來源檔案，目標檔案無此專案'
                    
                difference = {
                    'SN': len(differences) + 1,
                    'source_file': source_file,
                    'content': conv_proj.get('source_full_line', ''),  # 🔥 使用來源檔案原始行內容
                    'name': conv_proj['name'],
                    'path': conv_proj['path'],
                    'revision': conv_proj['converted_revision'],
                    'original_revision': conv_proj['original_revision'],
                    'Revision 是否相等': '',
                    'upstream': conv_proj.get('_source_upstream', conv_proj['upstream']) if is_local_comparison else conv_proj['upstream'],
                    'dest-branch': conv_proj.get('_source_dest_branch', conv_proj['dest-branch']) if is_local_comparison else conv_proj['dest-branch'],
                    'groups': conv_proj.get('_source_groups', conv_proj['groups']) if is_local_comparison else conv_proj['groups'],
                    'clone-depth': conv_proj.get('_source_clone_depth', conv_proj['clone-depth']) if is_local_comparison else conv_proj['clone-depth'],
                    'remote': conv_proj.get('_source_remote', conv_proj['remote']) if is_local_comparison else conv_proj['remote'],
                    'source_link': self._generate_source_link(conv_proj['name'], conv_proj['original_revision'], conv_proj.get('_source_remote', conv_proj['remote']) if is_local_comparison else conv_proj['remote']),
                    'gerrit_source_file': gerrit_source_file,
                    'gerrit_content': 'N/A (專案不存在)',
                    'gerrit_name': 'N/A',
                    'gerrit_path': 'N/A',
                    'gerrit_revision': 'N/A',
                    'gerrit_upstream': 'N/A',
                    'gerrit_dest-branch': 'N/A',
                    'gerrit_groups': 'N/A',
                    'gerrit_clone-depth': 'N/A',
                    'gerrit_remote': 'N/A',
                    'gerrit_source_link': 'N/A',
                    'comparison_status': '➕ 新增',
                    'comparison_result': comparison_result,
                    'status_color': 'yellow'
                }
                differences.append(difference)
                continue
            
            # 🔥 修正：使用 composite key 獲得目標專案，確保資料來源正確
            target_proj = target_index[conv_composite_key]
            
            # 🔥 修正：針對不同比較模式使用正確的比較邏輯
            if is_local_comparison:
                # [5] 本地比較：建構來源檔案的專案資訊用於比較
                source_proj_for_comparison = {
                    'name': conv_proj['name'],
                    'path': conv_proj['path'],
                    'revision': conv_proj['original_revision'],
                    'upstream': conv_proj.get('_source_upstream', ''),
                    'dest-branch': conv_proj.get('_source_dest_branch', ''),
                    'groups': conv_proj.get('_source_groups', ''),
                    'clone-depth': conv_proj.get('_source_clone_depth', ''),
                    'remote': conv_proj.get('_source_remote', '')
                }
                diff_details = self._get_detailed_differences_between_projects(source_proj_for_comparison, target_proj)
            elif is_gerrit_comparison:
                # 🔥 修正：[1]-[4] Gerrit 比較：比較本地檔案和 Gerrit 檔案
                local_proj_for_comparison = {
                    'name': conv_proj['name'],
                    'path': conv_proj['path'],
                    'revision': conv_proj['original_revision'],          # 🔥 本地檔案的 revision
                    'upstream': conv_proj['upstream'],                   # 🔥 本地檔案的屬性
                    'dest-branch': conv_proj['dest-branch'],
                    'groups': conv_proj['groups'],
                    'clone-depth': conv_proj['clone-depth'],
                    'remote': conv_proj['remote']
                }
                diff_details = self._get_detailed_differences_between_projects(local_proj_for_comparison, target_proj)
            else:
                # 其他情況：使用原有邏輯（保險起見）
                diff_details = self._get_detailed_differences(conv_proj, target_proj, use_converted_revision=False)
            
            is_identical = len(diff_details) == 0
            
            # 🔥 修正：不論相同或不同，都要加入到 differences 陣列中
            if is_identical:
                identical_count += 1
                comparison_status = '✔️ 相同'
                comparison_result = '兩檔案中此專案的所有屬性完全一致'
                status_color = 'green'
            else:
                different_count += 1
                comparison_status = '❌ 不同'
                # 詳細說明差異內容
                diff_summary = self._format_difference_summary(diff_details)
                comparison_result = f'屬性差異：{diff_summary}'
                status_color = 'red'
            
            # 🔥 關鍵修正：確保content欄位使用正確的原始資料來源
            if is_local_comparison:
                # 本地比較模式：content使用來源檔案，gerrit_content使用目標檔案
                content_value = conv_proj.get('source_full_line', '')
                gerrit_content_value = conv_proj.get('target_full_line', target_proj.get('full_line', ''))
            else:
                # Gerrit比較模式：content使用本地檔案，gerrit_content使用Gerrit檔案
                content_value = conv_proj.get('source_full_line', '')
                gerrit_content_value = target_proj.get('full_line', '')
            
            difference = {
                'SN': len(differences) + 1,
                'source_file': source_file,
                'content': content_value,  # 🔥 確保使用正確的原始資料
                'name': conv_proj['name'],
                'path': conv_proj['path'],
                'revision': conv_proj['converted_revision'],
                'original_revision': conv_proj['original_revision'],
                'upstream': conv_proj.get('_source_upstream', conv_proj['upstream']) if is_local_comparison else conv_proj['upstream'],
                'dest-branch': conv_proj.get('_source_dest_branch', conv_proj['dest-branch']) if is_local_comparison else conv_proj['dest-branch'],
                'groups': conv_proj.get('_source_groups', conv_proj['groups']) if is_local_comparison else conv_proj['groups'],
                'clone-depth': conv_proj.get('_source_clone_depth', conv_proj['clone-depth']) if is_local_comparison else conv_proj['clone-depth'],
                'remote': conv_proj.get('_source_remote', conv_proj['remote']) if is_local_comparison else conv_proj['remote'],
                'source_link': self._generate_source_link(conv_proj['name'], conv_proj['original_revision'], conv_proj.get('_source_remote', conv_proj['remote']) if is_local_comparison else conv_proj['remote']),
                'gerrit_source_file': gerrit_source_file,
                'gerrit_content': gerrit_content_value,  # 🔥 確保使用正確的原始資料
                'gerrit_name': target_proj['name'],
                'gerrit_path': target_proj['path'],
                'gerrit_revision': target_proj['revision'],
                'gerrit_upstream': target_proj['upstream'],
                'gerrit_dest-branch': target_proj['dest-branch'],
                'gerrit_groups': target_proj['groups'],
                'gerrit_clone-depth': target_proj['clone-depth'],
                'gerrit_remote': target_proj['remote'],
                'gerrit_source_link': self._generate_source_link(target_proj['name'], target_proj['revision'], target_proj['remote']),
                'comparison_status': comparison_status,
                'comparison_result': comparison_result,
                'status_color': status_color
            }
            differences.append(difference)
        
        # 檢查目標檔案中存在但來源檔案不存在的專案（無此專案）
        converted_composite_keys = set()
        for proj in converted_projects:
            composite_key = f"{proj['name']}|{proj['path']}"
            converted_composite_keys.add(composite_key)

        for composite_key, target_proj in target_index.items():
            if composite_key not in converted_composite_keys:
                different_count += 1
                comparison_result = '專案僅存在於目標檔案，來源檔案無此專案'  # 🔥 修改文字
                    
                difference = {
                    'SN': len(differences) + 1,
                    'source_file': source_file,
                    'content': 'N/A (專案無此專案)',  # 🔥 修改文字
                    'name': target_proj['name'],
                    'path': target_proj['path'],
                    'revision': 'N/A',
                    'original_revision': 'N/A',
                    'upstream': 'N/A',
                    'dest-branch': 'N/A',
                    'groups': 'N/A',
                    'clone-depth': 'N/A',
                    'remote': 'N/A',
                    'source_link': 'N/A',
                    'gerrit_source_file': gerrit_source_file,
                    'gerrit_content': target_proj.get('full_line', ''),  # 🔥 使用目標檔案原始行內容
                    'gerrit_name': target_proj['name'],
                    'gerrit_path': target_proj['path'],
                    'gerrit_revision': target_proj['revision'],
                    'gerrit_upstream': target_proj['upstream'],
                    'gerrit_dest-branch': target_proj['dest-branch'],
                    'gerrit_groups': target_proj['groups'],
                    'gerrit_clone-depth': target_proj['clone-depth'],
                    'gerrit_remote': target_proj['remote'],
                    'gerrit_source_link': self._generate_source_link(target_proj['name'], target_proj['revision'], target_proj['remote']),
                    'comparison_status': '❓ 無此專案',  # 🔥 修改狀態圖示和文字
                    'comparison_result': comparison_result,
                    'status_color': 'orange'
                }
                differences.append(difference)
        
        # 🔥 新增：統計報告和除錯訊息
        self.logger.info(f"📊 專案比較統計 ({overwrite_type}):")
        self.logger.info(f"   比較模式: {'本地檔案比較' if is_local_comparison else 'Gerrit比較' if is_gerrit_comparison else '其他'}")
        self.logger.info(f"   總比較專案數: {total_compared}")
        self.logger.info(f"   完全相同專案: {identical_count}")
        self.logger.info(f"   有差異專案: {different_count}")
        self.logger.info(f"   差異明細記錄數: {len(differences)} (包含所有專案)")
        
        return differences

    def _build_project_line_content_for_source(self, project: Dict) -> str:
        """為來源檔案建立 project 行內容（本地比較專用）"""
        try:
            # 建立基本的 project 標籤
            project_line = "<project"
            
            # 標準屬性順序
            attrs_order = ['groups', 'name', 'path', 'revision', 'upstream', 'dest-branch', 'clone-depth', 'remote']
            
            for attr in attrs_order:
                if attr == 'revision':
                    value = project.get('original_revision', '')
                elif attr == 'upstream':
                    value = project.get('_source_upstream', '')
                elif attr == 'dest-branch':
                    value = project.get('_source_dest_branch', '')
                elif attr == 'groups':
                    value = project.get('_source_groups', '')
                elif attr == 'clone-depth':
                    value = project.get('_source_clone_depth', '')
                elif attr == 'remote':
                    value = project.get('_source_remote', '')
                else:
                    value = project.get(attr, '')
                
                # 只添加非空值
                if value and value.strip():
                    project_line += f' {attr}="{value}"'
            
            project_line += ">"
            
            return project_line
            
        except Exception as e:
            self.logger.error(f"建立來源 project 行內容失敗: {str(e)}")
            return f"<project name=\"{project.get('name', 'unknown')}\" ... >"

    def _get_detailed_differences_between_projects(self, source_proj: Dict, target_proj: Dict) -> List[Dict]:
        """取得兩個專案之間的詳細差異列表（本地比較專用）"""
        differences = []
        
        try:
            # 要比較的屬性列表
            attrs_to_compare = ['name', 'path', 'revision', 'upstream', 'dest-branch', 'groups', 'clone-depth', 'remote']
            
            # 逐一比較每個屬性
            for attr in attrs_to_compare:
                source_val = source_proj.get(attr, '').strip()
                target_val = target_proj.get(attr, '').strip()
                
                # 如果不同，記錄差異
                if source_val != target_val:
                    diff_info = {
                        'attribute': attr,
                        'source_value': source_val,
                        'target_value': target_val
                    }
                    differences.append(diff_info)
            
            return differences
            
        except Exception as e:
            self.logger.error(f"取得專案間詳細差異失敗: {str(e)}")
            return []
            
    def _format_difference_summary(self, diff_details: List[Dict]) -> str:
        """格式化差異摘要"""
        try:
            if not diff_details:
                return "無差異"
            
            # 按屬性重要性排序
            attr_priority = {'revision': 1, 'name': 2, 'path': 3, 'upstream': 4, 'dest-branch': 5, 
                            'groups': 6, 'clone-depth': 7, 'remote': 8}
            
            diff_details.sort(key=lambda x: attr_priority.get(x['attribute'], 99))
            
            # 格式化差異說明
            diff_parts = []
            for diff in diff_details[:3]:  # 最多顯示前3個差異
                attr = diff['attribute']
                source_val = diff['source_value'] or '(空)'
                target_val = diff['target_value'] or '(空)'
                
                # 特殊處理不同屬性的顯示
                if attr == 'revision':
                    diff_parts.append(f"版本號[{source_val} ≠ {target_val}]")
                elif attr == 'upstream':
                    diff_parts.append(f"上游分支[{source_val} ≠ {target_val}]")
                elif attr == 'dest-branch':
                    diff_parts.append(f"目標分支[{source_val} ≠ {target_val}]")
                elif attr == 'groups':
                    diff_parts.append(f"群組[{source_val} ≠ {target_val}]")
                elif attr == 'clone-depth':
                    diff_parts.append(f"克隆深度[{source_val} ≠ {target_val}]")
                elif attr == 'remote':
                    diff_parts.append(f"遠端[{source_val} ≠ {target_val}]")
                else:
                    diff_parts.append(f"{attr}[{source_val} ≠ {target_val}]")
            
            # 如果差異超過3個，加上省略號
            if len(diff_details) > 3:
                diff_parts.append(f"等{len(diff_details)}項差異")
            
            return "、".join(diff_parts)
            
        except Exception as e:
            self.logger.error(f"格式化差異摘要失敗: {str(e)}")
            return "差異格式化失敗"
            
    def _get_detailed_differences(self, conv_proj: Dict, target_proj: Dict, use_converted_revision: bool = False) -> List[Dict]:
        """取得詳細的屬性差異列表"""
        differences = []
        
        try:
            # 要比較的屬性列表
            attrs_to_compare = ['name', 'path', 'revision', 'upstream', 'dest-branch', 'groups', 'clone-depth', 'remote']
            
            # 逐一比較每個屬性
            for attr in attrs_to_compare:
                conv_val = conv_proj.get(attr, '').strip()
                target_val = target_proj.get(attr, '').strip()
                
                # 特殊處理 revision
                if attr == 'revision' and use_converted_revision:
                    conv_val = conv_proj.get('converted_revision', '').strip()
                
                # 如果不同，記錄差異
                if conv_val != target_val:
                    diff_info = {
                        'attribute': attr,
                        'source_value': conv_val,
                        'target_value': target_val
                    }
                    differences.append(diff_info)
            
            return differences
            
        except Exception as e:
            self.logger.error(f"取得詳細差異失敗: {str(e)}")
            return []
            
    def _compare_project_attributes_ignore_order(self, conv_proj: Dict, target_proj: Dict, use_converted_revision: bool = False) -> bool:
        """比較專案屬性，忽略順序差異（從 feature_three.py 複製）"""
        try:
            project_name = conv_proj.get('name', 'unknown')
            
            # 要比較的屬性列表
            attrs_to_compare = ['name', 'path', 'revision', 'upstream', 'dest-branch', 'groups', 'clone-depth', 'remote']
            
            # 逐一比較每個屬性
            for attr in attrs_to_compare:
                conv_val = conv_proj.get(attr, '').strip()
                target_val = target_proj.get(attr, '').strip()
                
                # 特殊處理 revision
                if attr == 'revision' and use_converted_revision:
                    conv_val = conv_proj.get('converted_revision', '').strip()
                
                # 如果不同，立即返回
                if conv_val != target_val:
                    self.logger.info(f"❌ 專案 {project_name} 在屬性 {attr} 不同")
                    self.logger.info(f"   轉換後值: '{conv_val}' (長度: {len(conv_val)})")
                    self.logger.info(f"   Gerrit值:  '{target_val}' (長度: {len(target_val)})")
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"比較專案屬性失敗: {str(e)}")
            return False

    def _build_project_line_content(self, project: Dict, use_converted_revision: bool = False) -> str:
        """根據專案資訊建立完整的 project 行內容（修正版：正確處理來源 revision）"""
        try:
            # 建立基本的 project 標籤
            project_line = "<project"
            
            # 標準屬性順序
            attrs_order = ['groups', 'name', 'path', 'revision', 'upstream', 'dest-branch', 'clone-depth', 'remote']
            
            for attr in attrs_order:
                value = project.get(attr, '')
                
                # 🔥 修正：特殊處理 revision
                if attr == 'revision':
                    if use_converted_revision:
                        value = project.get('converted_revision', project.get('revision', ''))
                    else:
                        # 🔥 修正：應該使用 original_revision 作為來源檔案的 revision
                        value = project.get('original_revision', project.get('revision', ''))
                
                # 處理 remote 屬性
                if attr == 'remote':
                    original_remote = project.get('original_remote', None)
                    if original_remote is None or original_remote == '':
                        continue
                    value = original_remote
                
                # 只添加非空值
                if value and value.strip():
                    project_line += f' {attr}="{value}"'
            
            project_line += ">"
            
            return project_line
            
        except Exception as e:
            self.logger.error(f"建立 project 行內容失敗: {str(e)}")
            return f"<project name=\"{project.get('name', 'unknown')}\" ... >"

    def _generate_source_link(self, project_name: str, revision: str, remote: str = '') -> str:
        """根據專案名稱、revision 和 remote 生成 gerrit source link（從 feature_three.py 複製）"""
        try:
            if not project_name or not revision:
                return 'N/A'
            
            # 根據 remote 決定 base URL
            if remote == 'rtk-prebuilt':
                base_url = "https://mm2sd-git2.rtkbf.com/gerrit/plugins/gitiles"
            else:  # rtk 或空值
                base_url = "https://mm2sd.rtkbf.com/gerrit/plugins/gitiles"
            
            # 檢查 revision 是否為 hash (40 字符的十六進制)
            if len(revision) == 40 and all(c in '0123456789abcdefABCDEF' for c in revision):
                # Hash 格式
                return f"{base_url}/{project_name}/+/{revision}"
            
            # 檢查是否為 tag 格式
            elif revision.startswith('refs/tags/'):
                return f"{base_url}/{project_name}/+/{revision}"
            
            # 檢查是否為完整的 branch 路徑
            elif revision.startswith('refs/heads/'):
                return f"{base_url}/{project_name}/+/{revision}"
            
            # 其他情況假設為 branch name，加上 refs/heads/ 前綴
            else:
                return f"{base_url}/{project_name}/+/refs/heads/{revision}"
                
        except Exception as e:
            self.logger.error(f"生成 source link 失敗: {str(e)}")
            return 'N/A'

    def _get_source_and_target_filenames(self, overwrite_type: str) -> tuple:
        """取得來源和目標檔案名稱（修正版：正確處理 local_vs_* 格式）"""
        try:
            # 🔥 修正：處理 local_vs_* 格式的 overwrite_type
            if overwrite_type.startswith('local_vs_'):
                gerrit_type = overwrite_type.replace('local_vs_', '')
                
                # 根據 gerrit_type 對應到正確的檔案名稱
                gerrit_type_mapping = {
                    'master': {
                        'source': 'atv-google-refplus.xml',
                        'target': 'atv-google-refplus.xml'
                    },
                    'premp': {
                        'source': 'atv-google-refplus-premp.xml', 
                        'target': 'atv-google-refplus-premp.xml'
                    },
                    'mp': {
                        'source': 'atv-google-refplus-wave.xml',
                        'target': 'atv-google-refplus-wave.xml'
                    },
                    'mp_backup': {
                        'source': 'atv-google-refplus-wave-backup.xml',
                        'target': 'atv-google-refplus-wave-backup.xml'
                    },
                    'local': {
                        'source': 'local_source.xml',
                        'target': 'local_target.xml'
                    }
                }
                
                if gerrit_type in gerrit_type_mapping:
                    mapping = gerrit_type_mapping[gerrit_type]
                    source_filename = mapping['source']
                    target_filename = f"gerrit_{mapping['target']}"
                    
                    self.logger.debug(f"🔧 檔案名稱映射: {overwrite_type}")
                    self.logger.debug(f"   來源檔案: {source_filename}")
                    self.logger.debug(f"   目標檔案: {target_filename}")
                    
                    return source_filename, target_filename
                else:
                    self.logger.warning(f"未知的 gerrit_type: {gerrit_type}")
                    return 'unknown.xml', 'gerrit_unknown.xml'
            
            # 🔥 原有邏輯：處理 feature_three.py 的傳統格式
            else:
                source_filename = self.output_files.get(overwrite_type, 'unknown.xml')
                target_filename = f"gerrit_{self.target_files.get(overwrite_type, 'unknown.xml')}"
                return source_filename, target_filename
                
        except Exception as e:
            self.logger.error(f"取得檔案名稱失敗: {str(e)}")
            return 'unknown.xml', 'gerrit_unknown.xml'

    def _is_revision_hash(self, revision: str) -> bool:
        """判斷 revision 是否為 commit hash（從 feature_three.py 複製）"""
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

    def _generate_gerrit_manifest_link(self, filename: str) -> str:
        """生成 Gerrit manifest 檔案的連結（從 feature_three.py 複製）"""
        try:
            if not filename or filename == '無':
                return '無'
            
            # 移除 gerrit_ 前綴（如果有的話）
            clean_filename = filename.replace('gerrit_', '') if filename.startswith('gerrit_') else filename
            
            # 構建 Gerrit 連結
            gerrit_link = f"{self.gerrit_base_url}/{clean_filename}"
            
            self.logger.debug(f"生成 Gerrit 連結: {clean_filename} → {gerrit_link}")
            return gerrit_link
            
        except Exception as e:
            self.logger.error(f"生成 Gerrit 連結失敗: {str(e)}")
            return filename

    def _add_hyperlink_to_cell(self, worksheet, row: int, col: int, url: str, display_text: str):
        """為 Excel 單元格添加超連結（從 feature_three.py 複製）"""
        try:
            from openpyxl.worksheet.hyperlink import Hyperlink
            from openpyxl.styles import Font
            
            cell = worksheet.cell(row=row, column=col)
            
            # 方案1: 使用完整的 HYPERLINK 函數格式
            try:
                cell.value = f'=HYPERLINK("{url}","{display_text}")'
                cell.font = Font(color="0000FF", underline="single")
                self.logger.debug(f"添加 HYPERLINK 函數: {display_text} → {url}")
                return
            except Exception as e:
                self.logger.warning(f"HYPERLINK 函數失敗，嘗試標準超連結: {str(e)}")
            
            # 方案2: 標準超連結（備用）
            cell.value = display_text
            cell.hyperlink = Hyperlink(ref=f"{cell.coordinate}", target=url)
            cell.font = Font(color="0000FF", underline="single")
            
            self.logger.debug(f"添加標準超連結: {display_text} → {url}")
            
        except Exception as e:
            self.logger.error(f"添加超連結失敗: {str(e)}")
            # 備用方案：顯示文字 + URL 備註
            cell = worksheet.cell(row=row, column=col)
            cell.value = f"{display_text}"
            
            # 在註解中添加 URL
            try:
                from openpyxl.comments import Comment
                cell.comment = Comment(f"Gerrit 連結:\n{url}", "System")
            except:
                pass

    # ===============================
    # ===== 新增的輔助方法 =====
    # ===============================
                
    def _copy_local_file_to_output(self, local_file: str, output_folder: str, 
                                custom_name: Optional[str] = None) -> str:
        """複製本地檔案到輸出目錄 - 保留原始檔案名稱"""
        try:
            if custom_name:
                dest_name = custom_name
            else:
                # 直接保留原始檔案名稱
                dest_name = os.path.basename(local_file)
            
            dest_path = os.path.join(output_folder, dest_name)
            shutil.copy2(local_file, dest_path)
            
            self.logger.info(f"✅ 複製本地檔案: {dest_name}")
            return dest_path
            
        except Exception as e:
            self.logger.error(f"複製本地檔案失敗: {str(e)}")
            raise
    
    def _download_gerrit_file(self, gerrit_type: str, output_folder: str) -> Optional[str]:
        """從 Gerrit 下載檔案到輸出目錄，使用 gerrit_ 前綴命名"""
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
        """處理 Gerrit manifest 的 include 展開"""
        try:
            self.logger.info("🔍 檢查 Gerrit manifest 是否需要展開")
            
            # 讀取 Gerrit 檔案內容
            with open(gerrit_file_path, 'r', encoding='utf-8') as f:
                gerrit_content = f.read()
            
            # 檢查 include 標籤
            if not self._has_include_tags(gerrit_content):
                self.logger.info("ℹ️ 未檢測到 include 標籤，使用原始檔案")
                return gerrit_file_path
            
            self.logger.info("🔍 檢測到 include 標籤，開始展開 manifest...")
            
            # 根據檔案名稱推測 overwrite_type
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
                overwrite_type = 'master_to_premp'
            
            expanded_content, expanded_file_path = self._expand_manifest_with_repo_fixed(
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
        """創建 conversion_info 但不執行轉換 - 比較模式（修正版：用於 Gerrit 比較）"""
        try:
            # 🔥 重要：這個方法主要用於 [1]-[4] Gerrit 比較
            # 但現在 [1]-[4] 應該使用 _create_conversion_info_for_local_comparison
            # 所以這個方法可能不再需要，或者需要重新定義其用途
            
            # 解析 XML
            root = ET.fromstring(xml_content)
            
            # 讀取 default 資訊
            default_remote = ''
            default_revision = ''
            default_element = root.find('default')
            if default_element is not None:
                default_remote = default_element.get('remote', '')
                default_revision = default_element.get('revision', '')
            
            projects = []
            
            # 遍歷所有 project 元素
            for project in root.findall('project'):
                project_name = project.get('name', '')
                project_path = project.get('path', '')
                project_remote = project.get('remote', '') or default_remote
                original_revision = project.get('revision', '') or default_revision
                upstream = project.get('upstream', '')
                
                # 🔥 重要提醒：這個方法的 converted_revision 邏輯需要重新考慮
                # 因為沒有目標檔案資訊，converted_revision 應該如何設定？
                project_info = {
                    'name': project_name,
                    'path': project_path,
                    'original_revision': original_revision,
                    'effective_revision': original_revision,
                    'converted_revision': original_revision,  # 🔥 這裡可能需要重新定義邏輯
                    'upstream': upstream,
                    'dest-branch': project.get('dest-branch', ''),
                    'groups': project.get('groups', ''),
                    'clone-depth': project.get('clone-depth', ''),
                    'remote': project.get('remote', ''),
                    'original_remote': project.get('remote', ''),
                    'changed': True,  # 標記為參與比較
                    'used_default_revision': False,
                    'used_upstream_for_conversion': False
                }
                
                projects.append(project_info)
            
            self.logger.info(f"成功分析 {len(projects)} 個專案（無轉換模式）")
            return projects
            
        except Exception as e:
            self.logger.error(f"分析專案資訊失敗: {str(e)}")
            return []

    def _create_conversion_info_for_local_comparison(self, source_content: str, target_content: str) -> List[Dict]:
        """為本地檔案比較創建正確的 conversion_info - 修正版：完整保存原始行內容"""
        try:
            # 解析源檔案和目標檔案 XML
            source_root = ET.fromstring(source_content)
            target_root = ET.fromstring(target_content)
            
            # 🔥 改進：同時解析兩個檔案的原始行內容
            source_projects_with_lines = self._extract_projects_with_line_numbers(source_content)
            source_full_lines = {}
            for proj in source_projects_with_lines:
                key = f"{proj['name']}|||{proj['path']}"
                source_full_lines[key] = proj['full_line']
            
            target_projects_with_lines = self._extract_projects_with_line_numbers(target_content)
            target_full_lines = {}
            for proj in target_projects_with_lines:
                key = f"{proj['name']}|||{proj['path']}"
                target_full_lines[key] = proj['full_line']
            
            # 讀取源檔案 default 資訊
            source_default_remote = ''
            source_default_revision = ''
            source_default = source_root.find('default')
            if source_default is not None:
                source_default_remote = source_default.get('remote', '')
                source_default_revision = source_default.get('revision', '')
            
            # 讀取目標檔案 default 資訊
            target_default_remote = ''
            target_default_revision = ''
            target_default = target_root.find('default')
            if target_default is not None:
                target_default_remote = target_default.get('remote', '')
                target_default_revision = target_default.get('revision', '')
            
            # 創建目標檔案的專案字典
            target_projects = {}
            for project in target_root.findall('project'):
                project_name = project.get('name', '')
                project_path = project.get('path', '')
                key = f"{project_name}|||{project_path}"
                
                target_projects[key] = {
                    'name': project_name,
                    'path': project_path,
                    'revision': project.get('revision', '') or target_default_revision,
                    'upstream': project.get('upstream', ''),
                    'dest-branch': project.get('dest-branch', ''),
                    'groups': project.get('groups', ''),
                    'clone-depth': project.get('clone-depth', ''),
                    'remote': project.get('remote', '') or target_default_remote,
                    # 🔥 關鍵改進：保存目標檔案的原始行內容
                    'full_line': target_full_lines.get(key, '')
                }
            
            projects = []
            
            # 遍歷源檔案的所有 project 元素
            for project in source_root.findall('project'):
                project_name = project.get('name', '')
                project_path = project.get('path', '')
                project_remote = project.get('remote', '') or source_default_remote
                original_revision = project.get('revision', '') or source_default_revision
                upstream = project.get('upstream', '')
                
                # 🔥 獲得來源檔案的原始行內容
                key = f"{project_name}|||{project_path}"
                source_full_line = source_full_lines.get(key, '')
                
                # 🔥 修正：查找目標檔案中的對應專案，獲得正確的 target 資料
                target_project = target_projects.get(key)
                
                if target_project:
                    # 🔥 關鍵修正：所有 converted_ 相關欄位都應該使用目標檔案的資料
                    target_revision = target_project['revision']
                    target_upstream = target_project['upstream']
                    target_dest_branch = target_project['dest-branch']
                    target_groups = target_project['groups']
                    target_clone_depth = target_project['clone-depth']
                    target_remote = target_project['remote']
                    target_full_line = target_project['full_line']  # 🔥 新增：目標檔案原始行內容
                    target_found = True
                else:
                    # 專案在目標檔案中不存在
                    target_revision = 'N/A (專案不存在)'
                    target_upstream = 'N/A'
                    target_dest_branch = 'N/A'
                    target_groups = 'N/A'
                    target_clone_depth = 'N/A'
                    target_remote = 'N/A'
                    target_full_line = 'N/A (專案不存在)'  # 🔥 新增
                    target_found = False
                
                project_info = {
                    'name': project_name,
                    'path': project_path,
                    'original_revision': original_revision,        # 🔥 來源檔案的 revision
                    'effective_revision': original_revision,
                    'converted_revision': target_revision,         # 🔥 修正：目標檔案的 revision
                    'upstream': target_upstream,                   # 🔥 修正：目標檔案的 upstream
                    'dest-branch': target_dest_branch,             # 🔥 修正：目標檔案的 dest-branch
                    'groups': target_groups,                       # 🔥 修正：目標檔案的 groups
                    'clone-depth': target_clone_depth,             # 🔥 修正：目標檔案的 clone-depth
                    'remote': target_remote,                       # 🔥 修正：目標檔案的 remote
                    'original_remote': project.get('remote', ''), # 🔥 保留：來源檔案的 remote
                    'changed': True,  # 標記為參與比較
                    'used_default_revision': not project.get('revision'),
                    'used_upstream_for_conversion': False,
                    # 🔥 額外記錄：方便後續除錯
                    '_actual_target_revision': target_revision,
                    '_target_found': target_found,
                    # 🔥 新增：保留來源檔案的所有原始屬性，方便對比
                    '_source_upstream': upstream,
                    '_source_dest_branch': project.get('dest-branch', ''),
                    '_source_groups': project.get('groups', ''),
                    '_source_clone_depth': project.get('clone-depth', ''),
                    '_source_remote': project_remote,
                    # 🔥 關鍵改進：保存兩個檔案的原始行內容
                    'source_full_line': source_full_line,      # 來源檔案原始行
                    'target_full_line': target_full_line       # 目標檔案原始行
                }
                
                projects.append(project_info)
            
            self.logger.info(f"成功分析源檔案 {len(projects)} 個專案（修正版本地比較模式 - 完整屬性+雙重原始行內容）")
            self.logger.info(f"目標檔案包含 {len(target_projects)} 個專案")
            
            # 🔥 修正版除錯輸出：檢查前幾個專案的所有屬性
            for i, proj in enumerate(projects[:3]):
                self.logger.info(f"專案 {i+1}: {proj['name']}")
                self.logger.info(f"  來源 revision: {proj['original_revision']}")
                self.logger.info(f"  目標 revision: {proj['converted_revision']}")
                self.logger.info(f"  來源 upstream: {proj['_source_upstream']}")
                self.logger.info(f"  目標 upstream: {proj['upstream']}")
                self.logger.info(f"  來源 groups: {proj['_source_groups']}")
                self.logger.info(f"  目標 groups: {proj['groups']}")
                self.logger.info(f"  是否找到目標: {proj['_target_found']}")
                self.logger.info(f"  來源原始行內容: {proj['source_full_line'][:100]}...")
                self.logger.info(f"  目標原始行內容: {proj['target_full_line'][:100]}...")
            
            return projects
            
        except Exception as e:
            self.logger.error(f"創建本地比較 conversion_info 失敗: {str(e)}")
            import traceback
            self.logger.error(f"詳細錯誤: {traceback.format_exc()}")
            return []

    def _generate_excel_report_like_feature_three(self, overwrite_type: str, source_file_path: Optional[str],
                                                output_file_path: Optional[str], target_file_path: Optional[str], 
                                                diff_analysis: Dict, output_folder: str, 
                                                excel_filename: Optional[str], source_download_success: bool,
                                                target_download_success: bool, push_result: Optional[Dict[str, Any]] = None,
                                                expanded_file_path: Optional[str] = None, use_expanded: bool = False) -> bool:
        """使用與 feature_three.py 完全相同的 Excel 報告生成邏輯 - 比較模式優化版"""
        try:
            self.logger.info("📋 生成 Excel 報告（完全基於 feature_three.py 邏輯，比較模式）")
            
            # 生成 Excel 報告
            excel_file = self._generate_excel_report_safe(
                overwrite_type=overwrite_type,
                source_file_path=source_file_path,
                output_file_path=output_file_path,
                target_file_path=target_file_path,
                diff_analysis=diff_analysis,
                output_folder=output_folder,
                excel_filename=excel_filename,
                source_download_success=source_download_success,
                target_download_success=target_download_success,
                push_result=None,  # 比較模式不產生推送相關內容
                expanded_file_path=expanded_file_path,
                use_expanded=use_expanded
            )
            
            if excel_file and os.path.exists(excel_file):
                # 後處理：針對比較模式進行優化
                try:
                    from openpyxl import load_workbook
                    workbook = load_workbook(excel_file)
                    
                    # 🔥 判斷是否為本地比較模式
                    is_local_comparison = (overwrite_type == "local_vs_local")
                    
                    # 移除 "轉換後的 manifest" 頁籤（比較模式不需要）
                    if '轉換後的 manifest' in workbook.sheetnames:
                        del workbook['轉換後的 manifest']
                        self.logger.info("✅ 已移除 '轉換後的 manifest' 頁籤（比較模式不需要）")
                    
                    # 修正其他頁籤的檔案名稱問題和比較模式優化
                    # 🔥 重要：傳遞 is_local_comparison 參數
                    self._fix_sheet_filenames(workbook, excel_file, overwrite_type, source_file_path, target_file_path, is_local_comparison)
                    
                    # 更新比較摘要的統計數據
                    self._update_summary_statistics(workbook, diff_analysis)
                    
                    # 最終保存
                    workbook.save(excel_file)
                    
                except Exception as e:
                    self.logger.warning(f"後處理 Excel 檔案時發生錯誤: {str(e)}")
                
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

    def _generate_excel_report_safe(self, overwrite_type: str, source_file_path: Optional[str],
                            output_file_path: Optional[str], target_file_path: Optional[str], 
                            diff_analysis: Dict, output_folder: str, 
                            excel_filename: Optional[str], source_download_success: bool,
                            target_download_success: bool, push_result: Optional[Dict[str, Any]] = None,
                            expanded_file_path: Optional[str] = None, use_expanded: bool = False) -> str:
        """安全的 Excel 報告生成（從 feature_three.py 複製）"""
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
                push_result=push_result,
                expanded_file_path=expanded_file_path,
                use_expanded=use_expanded
            )
        except Exception as e:
            self.logger.error(f"標準 Excel 報告生成失敗: {str(e)}")
            self.logger.info("嘗試生成基本錯誤報告...")
            return self._generate_error_report(output_folder, overwrite_type, str(e))

    def _generate_excel_report(self, overwrite_type: str, source_file_path: Optional[str],
                        output_file_path: Optional[str], target_file_path: Optional[str], 
                        diff_analysis: Dict, output_folder: str, 
                        excel_filename: Optional[str], source_download_success: bool,
                        target_download_success: bool, push_result: Optional[Dict[str, Any]] = None,
                        expanded_file_path: Optional[str] = None, use_expanded: bool = False) -> str:
        """產生 Excel 報告（完整修正版：處理所有比較模式和欄位命名）"""
        try:
            # 🔥 判斷比較模式
            is_local_comparison = (overwrite_type == "local_vs_local")
            
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
                    'Gerrit 源檔案': os.path.basename(source_file_path) if source_file_path else '無',
                    '源檔案下載狀態': '成功' if source_download_success else '失敗',
                    '源檔案': self.source_files.get(overwrite_type, ''),
                    '包含 include 標籤': '是' if use_expanded else '否',
                    'Gerrit 展開檔案': os.path.basename(expanded_file_path) if expanded_file_path else '無',
                    '使用展開檔案轉換': '是' if use_expanded else '否',
                    '輸出檔案': os.path.basename(output_file_path) if output_file_path else '',
                    'Gerrit 目標檔案': os.path.basename(target_file_path) if target_file_path else '無',
                    '目標檔案下載狀態': '成功' if target_download_success else '失敗 (檔案不存在)',
                    '目標檔案': self.target_files.get(overwrite_type, ''),
                    '📊 總專案數': diff_analysis['summary'].get('converted_count', 0),
                    '📄 實際轉換專案數': diff_analysis['summary'].get('actual_conversion_count', 0),
                    '⭕ 未轉換專案數': diff_analysis['summary'].get('unchanged_count', 0),
                    '🎯 目標檔案專案數': diff_analysis['summary'].get('target_count', 0),
                    '❌ 轉換後有差異數': diff_analysis['summary'].get('differences_count', 0),
                    '✔️ 轉換後相同數': diff_analysis['summary'].get('identical_converted_count', 0),
                    '📈 轉換匹配率': diff_analysis['summary'].get('conversion_match_rate', 'N/A')
                }]

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

                # 為轉換摘要頁籤添加超連結
                worksheet_summary = writer.sheets['轉換摘要']
                self._add_summary_hyperlinks(worksheet_summary, overwrite_type)
                
                # 🔥 頁籤 2: 轉換後專案 - 移除所有比較狀態欄位
                if diff_analysis['converted_projects']:
                    converted_data = []
                    for i, proj in enumerate(diff_analysis['converted_projects'], 1):
                        has_conversion = proj.get('changed', False)
                        if has_conversion:
                            # 🔥 統一：不論哪種比較模式都不顯示轉換狀態
                            status_description = f"來源檔案: {proj['original_revision']} → 目標檔案: {proj['converted_revision']}"
                        else:
                            # 🔥 統一：版本相同描述
                            status_description = f"兩檔案版本相同: {proj['original_revision']}"
                        
                        # 🔥 統一的欄位結構：移除所有 "轉換狀態" 欄位
                        row_data = {
                            'SN': i,
                            '專案名稱': proj['name'],
                            '專案路徑': proj['path'],
                            # 🔥 移除：'轉換狀態': conversion_status,  # 完全移除這個欄位
                            '原始 Revision': proj['original_revision'],
                            '轉換後 Revision': proj['converted_revision'],
                            'Revision 是否相等': '',
                            '轉換說明': status_description,
                            'Upstream': proj['upstream'],
                            'Dest-Branch': proj['dest-branch'],
                            'Groups': proj['groups'],
                            'Clone-Depth': proj['clone-depth'],
                            'Remote': proj['remote']
                        }
                        
                        converted_data.append(row_data)
                    
                    df_converted = pd.DataFrame(converted_data)
                    df_converted.to_excel(writer, sheet_name='轉換後專案', index=False)
                    
                    # 添加 Excel 公式到 "轉換後專案" 頁籤
                    worksheet_converted = writer.sheets['轉換後專案']
                    self._add_revision_comparison_formula_converted_projects(worksheet_converted)
                
                # 🔥 頁籤 3: 差異（修正：處理本地比較的欄位重新命名）
                if diff_analysis['has_target'] and diff_analysis['differences']:
                    diff_sheet_name = "轉換後與 Gerrit manifest 的差異"
                    
                    # 🔥 為本地比較模式重新命名欄位並驗證資料來源
                    if is_local_comparison:
                        differences_data = []
                        for i, diff in enumerate(diff_analysis['differences']):
                            # 🔥 新增：檢查資料來源
                            if i < 3:  # 只檢查前3筆，避免太多 log
                                self.logger.info(f"差異資料 {i+1} 檢查:")
                                self.logger.info(f"  gerrit_name: {diff.get('gerrit_name', 'N/A')}")
                                self.logger.info(f"  gerrit_revision: {diff.get('gerrit_revision', 'N/A')}")
                                self.logger.info(f"  gerrit_upstream: {diff.get('gerrit_upstream', 'N/A')}")
                            
                            # 創建新的字典，將 gerrit_ 欄位重新命名為 compare_
                            new_diff = {}
                            for key, value in diff.items():
                                if key.startswith('gerrit_'):
                                    new_key = key.replace('gerrit_', 'compare_')
                                    new_diff[new_key] = value
                                else:
                                    new_diff[key] = value
                            differences_data.append(new_diff)
                        
                        df_diff = pd.DataFrame(differences_data)
                        
                        self.logger.info("✅ 本地比較模式：gerrit_ 欄位已重新命名為 compare_")
                        
                        # 修正欄位順序（本地比較版本）
                        diff_columns = [
                            'SN', 'comparison_status', 'comparison_result',
                            'source_file', 'content', 'name', 'path', 
                            'original_revision',
                            'upstream', 'dest-branch', 'groups', 'clone-depth', 'remote', 'source_link',
                            'compare_source_file', 'compare_content', 'compare_name', 
                            'compare_path', 'compare_revision', 'compare_upstream', 
                            'compare_dest-branch', 'compare_groups', 'compare_clone-depth', 'compare_remote', 'compare_source_link'
                        ]
                    else:
                        # Gerrit 比較模式，保持原有欄位名稱
                        df_diff = pd.DataFrame(diff_analysis['differences'])
                        
                        # 修正欄位順序（Gerrit 比較版本）
                        diff_columns = [
                            'SN', 'comparison_status', 'comparison_result',
                            'source_file', 'content', 'name', 'path', 
                            'original_revision',
                            'upstream', 'dest-branch', 'groups', 'clone-depth', 'remote', 'source_link',
                            'gerrit_source_file', 'gerrit_content', 'gerrit_name', 
                            'gerrit_path', 'gerrit_revision', 'gerrit_upstream', 
                            'gerrit_dest-branch', 'gerrit_groups', 'gerrit_clone-depth', 'gerrit_remote', 'gerrit_source_link'
                        ]
                    
                    available_columns = [col for col in diff_columns if col in df_diff.columns]
                    df_diff = df_diff[available_columns]
                    
                    df_diff.to_excel(writer, sheet_name=diff_sheet_name, index=False)
                
                # 頁籤 4: 未轉換專案
                unchanged_projects = [proj for proj in diff_analysis['converted_projects'] 
                                    if not proj.get('changed', False)]
                if unchanged_projects:
                    unchanged_data = []
                    for i, proj in enumerate(unchanged_projects, 1):
                        reason = "符合跳過轉換條件或無需轉換"
                        needs_red_font = False
                        
                        if proj['original_revision']:
                            if self._is_revision_hash(proj['original_revision']):
                                reason = "符合跳過轉換條件或無需轉換 (Hash Revision)"
                                needs_red_font = False
                            else:
                                reason = "需檢查是否來源端是否有問題"
                                needs_red_font = True
                            
                        unchanged_data.append({
                            'SN': i,
                            '專案名稱': proj['name'],
                            '專案路徑': proj['path'],
                            '保持的 Revision': proj['original_revision'],
                            '原因': reason,
                            '需要紅字': needs_red_font,
                            'Upstream': proj['upstream'],
                            'Groups': proj['groups'],
                            'Remote': proj['remote']
                        })
                    
                    df_unchanged = pd.DataFrame(unchanged_data)
                    df_unchanged.to_excel(writer, sheet_name='未轉換專案', index=False)
                    
                    # 設定原因欄位的紅字格式
                    worksheet_unchanged = writer.sheets['未轉換專案']
                    self._format_unchanged_projects_reason_column(worksheet_unchanged)
                
                # 頁籤 5: 來源的 manifest（🔥 修正檔案名稱）
                if diff_analysis['converted_projects']:
                    source_data = []
                    for i, proj in enumerate(diff_analysis['converted_projects'], 1):
                        source_link = self._generate_source_link(proj['name'], proj['original_revision'], proj['remote'])
                        
                        # 🔥 修正：使用正確的來源檔案名稱
                        if source_file_path:
                            source_filename = os.path.basename(source_file_path)
                        else:
                            # 備用方案：從映射表取得
                            source_filename, _ = self._get_source_and_target_filenames(overwrite_type)
                        
                        source_data.append({
                            'SN': i,
                            'source_file': source_filename,
                            'name': proj['name'],
                            'path': proj['path'],
                            'revision': proj['original_revision'],
                            'upstream': proj['upstream'],
                            'dest-branch': proj['dest-branch'],
                            'groups': proj['groups'],
                            'clone-depth': proj['clone-depth'],
                            'remote': proj['remote'],
                            'source_link': source_link
                        })
                    
                    df_source = pd.DataFrame(source_data)
                    df_source.to_excel(writer, sheet_name='來源的 manifest', index=False)
                
                # 頁籤 6: 轉換後的 manifest（🔥 修正檔案名稱）
                if diff_analysis['converted_projects']:
                    converted_manifest_data = []
                    for i, proj in enumerate(diff_analysis['converted_projects'], 1):
                        source_link = self._generate_source_link(proj['name'], proj['converted_revision'], proj['remote'])
                        
                        # 🔥 修正：對於比較模式，轉換後檔案就是目標檔案
                        if target_file_path and overwrite_type.startswith('local_vs_'):
                            # 比較模式：使用目標檔案名稱
                            output_filename = os.path.basename(target_file_path)
                        elif output_file_path:
                            # 傳統模式：使用輸出檔案名稱
                            output_filename = os.path.basename(output_file_path)
                        else:
                            # 備用方案：從映射表取得
                            output_filename = self.output_files.get(overwrite_type, 'unknown.xml')
                        
                        converted_manifest_data.append({
                            'SN': i,
                            'source_file': output_filename,
                            'name': proj['name'],
                            'path': proj['path'],
                            'revision': proj['converted_revision'],
                            'upstream': proj['upstream'],
                            'dest-branch': proj['dest-branch'],
                            'groups': proj['groups'],
                            'clone-depth': proj['clone-depth'],
                            'remote': proj['remote'],
                            'source_link': source_link
                        })
                    
                    df_converted_manifest = pd.DataFrame(converted_manifest_data)
                    df_converted_manifest.to_excel(writer, sheet_name='轉換後的 manifest', index=False)
                
                # 🔥 頁籤 7: gerrit 上的 manifest（直接在原邏輯中修正檔案名稱）
                if diff_analysis['has_target'] and diff_analysis['target_projects']:
                    gerrit_data = []
                    for i, proj in enumerate(diff_analysis['target_projects'], 1):
                        source_link = self._generate_source_link(proj['name'], proj['revision'], proj['remote'])
                        
                        # 🔥 修正：獲取正確的檔案名稱，移除展開後綴
                        if target_file_path:
                            gerrit_target_filename = os.path.basename(target_file_path)
                            # 🔥 關鍵修正：直接移除 _expand 後綴
                            if '_expand' in gerrit_target_filename:
                                gerrit_target_filename = gerrit_target_filename.replace('_expand', '')
                        else:
                            # 備用方案：從映射表取得
                            _, gerrit_target_filename = self._get_source_and_target_filenames(overwrite_type)
                        
                        gerrit_data.append({
                            'SN': i,
                            'source_file': gerrit_target_filename,  # 現在會是正確的原始檔案名稱
                            'name': proj['name'],
                            'path': proj['path'],
                            'revision': proj['revision'],
                            'upstream': proj['upstream'],
                            'dest-branch': proj['dest-branch'],
                            'groups': proj['groups'],
                            'clone-depth': proj['clone-depth'],
                            'remote': proj['remote'],
                            'source_link': source_link
                        })
                    
                    df_gerrit = pd.DataFrame(gerrit_data)
                    df_gerrit.to_excel(writer, sheet_name='gerrit 上的 manifest', index=False)
                
                # 格式化所有工作表
                for sheet_name in writer.sheets:
                    worksheet = writer.sheets[sheet_name]
                    # 🔥 重要：傳遞 is_local_comparison 參數給格式化函數
                    self._format_worksheet_with_background_colors(worksheet, sheet_name, is_local_comparison)
                    
                    # 為相關頁籤添加超連結
                    if sheet_name in ['來源的 manifest', '轉換後的 manifest', 'gerrit 上的 manifest', '轉換後與 Gerrit manifest 的差異']:
                        self._add_manifest_hyperlinks(worksheet, sheet_name)
            
            self.logger.info(f"成功產生 Excel 報告: {excel_file}")
            return excel_file
            
        except Exception as e:
            self.logger.error(f"產生 Excel 報告失敗: {str(e)}")
            raise


    def _validate_file_mapping(self, overwrite_type: str) -> None:
        """驗證檔案名稱映射是否正確"""
        try:
            source_filename, target_filename = self._get_source_and_target_filenames(overwrite_type)
            
            self.logger.info(f"📋 檔案映射驗證: {overwrite_type}")
            self.logger.info(f"   ✅ 來源檔案: {source_filename}")
            self.logger.info(f"   ✅ 目標檔案: {target_filename}")
            
            if 'unknown' in source_filename or 'unknown' in target_filename:
                self.logger.warning(f"⚠️ 檔案映射包含 unknown，請檢查配置")
                
        except Exception as e:
            self.logger.error(f"檔案映射驗證失敗: {str(e)}")
            
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

    # ===============================
    # ===== Excel 格式化方法（從 feature_three.py 複製） =====
    # ===============================

    def _add_summary_hyperlinks(self, worksheet, overwrite_type: str):
        """為轉換摘要頁籤添加 Gerrit 超連結（從 feature_three.py 複製）"""
        try:
            from openpyxl.styles import PatternFill, Font
            
            purple_fill = PatternFill(start_color="8A2BE2", end_color="8A2BE2", fill_type="solid")
            white_font = Font(color="FFFFFF", bold=True)
            
            # 找到需要添加連結的欄位
            target_columns = {
                '源檔案': self.source_files.get(overwrite_type, ''),
                '目標檔案': self.target_files.get(overwrite_type, '')
            }
            
            # 為每個目標欄位添加連結
            for col_num, cell in enumerate(worksheet[1], 1):  # 表頭行
                header_value = str(cell.value) if cell.value else ''
                
                if header_value in target_columns:
                    filename = target_columns[header_value]
                    if filename and filename != '':
                        gerrit_url = self._generate_gerrit_manifest_link(filename)
                        
                        # 在數據行添加超連結（第2行）
                        self._add_hyperlink_to_cell(worksheet, 2, col_num, gerrit_url, filename)
                        
                        self.logger.info(f"已為轉換摘要添加 {header_value} 連結: {filename}")
            
        except Exception as e:
            self.logger.error(f"添加轉換摘要超連結失敗: {str(e)}")

    def _add_revision_comparison_formula_converted_projects(self, worksheet):
        """為轉換後專案頁籤添加真正的動態條件格式（從 feature_three.py 複製）"""
        try:
            from openpyxl.styles import Font
            from openpyxl.utils import get_column_letter
            from openpyxl.formatting.rule import Rule
            from openpyxl.styles.differential import DifferentialStyle
            
            # 找到相關欄位的位置
            original_revision_col = None
            converted_revision_col = None
            comparison_col = None
            
            for col_num, cell in enumerate(worksheet[1], 1):
                header_value = str(cell.value) if cell.value else ''
                if header_value == '原始 Revision':
                    original_revision_col = col_num
                elif header_value == '轉換後 Revision':
                    converted_revision_col = col_num
                elif header_value == 'Revision 是否相等':
                    comparison_col = col_num
            
            if not all([original_revision_col, converted_revision_col, comparison_col]):
                self.logger.warning(f"轉換後專案頁籤：無法找到所需的欄位位置")
                return
            
            # 取得欄位字母
            original_col_letter = get_column_letter(original_revision_col)
            converted_col_letter = get_column_letter(converted_revision_col)
            comparison_col_letter = get_column_letter(comparison_col)
            
            # 只添加 Excel 公式，不手動設定顏色
            for row_num in range(2, worksheet.max_row + 1):
                formula = f'=IF({original_col_letter}{row_num}={converted_col_letter}{row_num},"Y","N")'
                cell = worksheet[f"{comparison_col_letter}{row_num}"]
                cell.value = formula
            
            # 設定真正的動態條件格式
            green_font = Font(color="00B050", bold=True)
            red_font = Font(color="FF0000", bold=True)
            
            # 條件格式範圍
            range_string = f"{comparison_col_letter}2:{comparison_col_letter}{worksheet.max_row}"
            
            # 為 "Y" 值設定綠色字體
            green_rule = Rule(
                type="containsText",
                operator="containsText",
                text="Y",
                dxf=DifferentialStyle(font=green_font)
            )
            green_rule.formula = [f'NOT(ISERROR(SEARCH("Y",{comparison_col_letter}2)))']
            
            # 為 "N" 值設定紅色字體
            red_rule = Rule(
                type="containsText", 
                operator="containsText",
                text="N",
                dxf=DifferentialStyle(font=red_font)
            )
            red_rule.formula = [f'NOT(ISERROR(SEARCH("N",{comparison_col_letter}2)))']
            
            # 添加條件格式規則
            worksheet.conditional_formatting.add(range_string, green_rule)
            worksheet.conditional_formatting.add(range_string, red_rule)
            
            self.logger.info("✅ 已添加真正的動態條件格式")
            
        except Exception as e:
            self.logger.error(f"添加動態條件格式失敗: {str(e)}")

    def _format_unchanged_projects_reason_column(self, worksheet):
        """格式化未轉換專案的原因欄位（從 feature_three.py 複製）"""
        try:
            from openpyxl.styles import Font
            
            red_font = Font(color="FF0000", bold=True)
            
            # 找到原因欄位的位置
            reason_col = None
            needs_red_col = None
            
            for col_num, cell in enumerate(worksheet[1], 1):
                header_value = str(cell.value) if cell.value else ''
                if header_value == '原因':
                    reason_col = col_num
                elif header_value == '需要紅字':
                    needs_red_col = col_num
            
            if not reason_col:
                self.logger.warning("無法找到原因欄位，跳過紅字格式設定")
                return
            
            # 為符合條件的原因欄位設定紅字
            for row_num in range(2, worksheet.max_row + 1):
                if needs_red_col:
                    # 檢查是否需要紅字標記
                    needs_red_cell = worksheet.cell(row=row_num, column=needs_red_col)
                    if needs_red_cell.value:
                        reason_cell = worksheet.cell(row=row_num, column=reason_col)
                        reason_cell.font = red_font
            
            # 隱藏 "需要紅字" 輔助欄位
            if needs_red_col:
                from openpyxl.utils import get_column_letter
                col_letter = get_column_letter(needs_red_col)
                worksheet.column_dimensions[col_letter].hidden = True
            
            self.logger.info("✅ 已設定未轉換專案原因欄位的紅字格式")
            
        except Exception as e:
            self.logger.error(f"設定原因欄位紅字格式失敗: {str(e)}")

    def _format_worksheet_with_background_colors(self, worksheet, sheet_name: str, is_local_comparison: bool = False):
        """格式化工作表（修正版：為比較說明欄位設定橘底白字）"""
        try:
            from openpyxl.styles import PatternFill, Font, Alignment
            from openpyxl.utils import get_column_letter
            
            # 設定Excel頁籤標籤顏色
            if sheet_name in ['轉換摘要', '比較摘要']:
                worksheet.sheet_properties.tabColor = "ADD8E6"  # Light Blue
            elif sheet_name in ['來源的 manifest', '轉換後的 manifest', 'gerrit 上的 manifest', '目標的 manifest']:
                worksheet.sheet_properties.tabColor = "90EE90"  # Light Green
            elif sheet_name in ['轉換後與 Gerrit manifest 的差異', '未轉換專案', '相同專案', 
                            '比較專案內容差異明細', '與現行版本比較差異', '轉換後專案']:
                worksheet.sheet_properties.tabColor = "FFB6C1"  # Light Pink
            
            # 顏色定義
            blue_header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
            green_fill = PatternFill(start_color="00B050", end_color="00B050", fill_type="solid")
            red_fill = PatternFill(start_color="C5504B", end_color="C5504B", fill_type="solid")
            orange_fill = PatternFill(start_color="FF8C00", end_color="FF8C00", fill_type="solid")
            purple_fill = PatternFill(start_color="8A2BE2", end_color="8A2BE2", fill_type="solid")
            link_blue_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")   # 連結藍色背景

            white_font = Font(color="FFFFFF", bold=True)
            blue_font = Font(color="0070C0", bold=True)
            gray_font = Font(color="808080", bold=True)
            
            # 定義特殊顏色的欄位
            orange_header_fields = ["推送狀態", "推送結果", "Commit ID", "Review URL"]
            green_header_fields = ["Gerrit 源檔案", "Gerrit 展開檔案", "Gerrit 目標檔案"]
            purple_header_fields = ["源檔案", "輸出檔案", "目標檔案", "來源檔案", "比較檔案", "實際比較的目標檔案", "source_file"]
            link_blue_header_fields = ["source_link", "gerrit_source_link", "compare_source_link"]

            # 🔥 新增：特定頁籤的橘色欄位
            if sheet_name == "與現行版本比較差異":
                orange_header_fields.append("比較說明")
                orange_header_fields.append("轉換說明")  # 以防萬一有其他名稱
            
            # 檢查是否為本地比較模式（通過檢查是否有 compare_ 欄位）
            has_compare_fields = any(str(cell.value).startswith('compare_') for cell in worksheet[1] if cell.value)
            
            # 設定表頭和欄寬
            for col_num, cell in enumerate(worksheet[1], 1):
                col_letter = get_column_letter(col_num)
                header_value = str(cell.value) if cell.value else ''
                
                # 處理 compare_ 欄位（本地比較模式）
                if has_compare_fields and header_value.startswith('compare_'):
                    if header_value == 'compare_revision':
                        cell.fill = red_fill  # 版本號：紅色
                    elif header_value == 'compare_source_file':
                        cell.fill = purple_fill  # 檔案名稱：紫色
                    elif header_value == 'compare_source_link':  # 🔥 新增：特殊處理 compare_source_link
                        cell.fill = link_blue_fill  # 連結：藍色
                        self.logger.debug(f"設定藍色白字表頭: {header_value}")
                    else:
                        cell.fill = green_fill  # 其他 compare_ 欄位：綠色
                    cell.font = white_font
                # 處理 gerrit_ 開頭的欄位（Gerrit 比較）
                elif header_value.startswith('gerrit_') and header_value not in green_header_fields:
                    if header_value == 'gerrit_revision':
                        cell.fill = red_fill  # 版本號：紅色
                    elif header_value == 'gerrit_source_file':
                        cell.fill = green_fill  # Gerrit 檔案名稱：綠色
                    else:
                        cell.fill = green_fill  # 其他 gerrit_ 欄位：綠色
                    cell.font = white_font
                # "original_revision" 顏色設定
                elif header_value == 'original_revision':
                    cell.fill = red_fill  # 紅色
                    cell.font = white_font
                # 🔥 橘色欄位設定（包含新增的比較說明）
                elif header_value in orange_header_fields:
                    cell.fill = orange_fill
                    cell.font = white_font
                    # 🔥 記錄橘色欄位設定
                    if header_value in ["比較說明", "轉換說明"]:
                        self.logger.debug(f"✅ 設定橘底白字: {header_value} (欄位 {col_letter})")
                elif header_value in green_header_fields:
                    cell.fill = green_fill
                    cell.font = white_font
                elif header_value in purple_header_fields:
                    cell.fill = purple_fill
                    cell.font = white_font
                elif header_value in link_blue_header_fields:  # 🔥 新增藍色背景欄位
                    cell.fill = link_blue_fill
                    cell.font = white_font
                    self.logger.debug(f"設定藍色白字表頭: {header_value}")                    
                else:
                    # 預設所有其他表頭都是藍底白字
                    cell.fill = blue_header_fill
                    cell.font = white_font
                
                cell.alignment = Alignment(horizontal='center', vertical='center')
                
                # 特殊處理各種頁籤的欄寬
                if sheet_name in ["轉換後專案", "與現行版本比較差異"]:
                    if header_value == '原始 Revision' or header_value == '來源 Revision':
                        cell.fill = red_fill
                        cell.font = white_font
                        worksheet.column_dimensions[col_letter].width = 35
                    elif header_value == '轉換後 Revision' or header_value == '目標 Revision':
                        cell.fill = red_fill
                        cell.font = white_font
                        worksheet.column_dimensions[col_letter].width = 35
                    elif header_value == 'Revision 是否相等':
                        cell.fill = red_fill
                        cell.font = white_font
                        worksheet.column_dimensions[col_letter].width = 15
                    # 🔥 新增：比較說明欄位的特殊處理
                    elif header_value in ["比較說明", "轉換說明"]:
                        cell.fill = orange_fill  # 確保橘底
                        cell.font = white_font   # 確保白字
                        worksheet.column_dimensions[col_letter].width = 50  # 設定較寬的欄寬
                    elif 'revision' in header_value.lower():
                        worksheet.column_dimensions[col_letter].width = 35

                elif sheet_name in ["轉換後與 Gerrit manifest 的差異", "比較專案內容差異明細"]:
                    if 'content' in header_value or ('compare_content' in header_value or 'gerrit_content' in header_value):
                        worksheet.column_dimensions[col_letter].width = 80
                    elif 'revision' in header_value.lower():
                        worksheet.column_dimensions[col_letter].width = 35
                    elif 'comparison' in header_value:
                        worksheet.column_dimensions[col_letter].width = 20
                    elif header_value in ['name', 'gerrit_name', 'compare_name']:
                        worksheet.column_dimensions[col_letter].width = 25
                    elif header_value in ['path', 'gerrit_path', 'compare_path']:
                        worksheet.column_dimensions[col_letter].width = 30
                    elif header_value in ['groups', 'gerrit_groups', 'compare_groups']:
                        worksheet.column_dimensions[col_letter].width = 40
                    elif header_value in ['source_link', 'gerrit_source_link', 'compare_source_link']:
                        worksheet.column_dimensions[col_letter].width = 60
                    elif header_value in ['source_file', 'gerrit_source_file', 'compare_source_file']:
                        worksheet.column_dimensions[col_letter].width = 30
                    
                    # 根據比較狀態設定行的背景色
                    self._set_comparison_row_colors(worksheet, col_num, header_value)
                
                elif sheet_name in ['來源的 manifest', '轉換後的 manifest', 'gerrit 上的 manifest', '目標的 manifest']:
                    if 'revision' in header_value.lower():
                        worksheet.column_dimensions[col_letter].width = 35
                    elif header_value in ['name']:
                        worksheet.column_dimensions[col_letter].width = 25
                    elif header_value in ['path']:
                        worksheet.column_dimensions[col_letter].width = 30
                    elif header_value in ['groups']:
                        worksheet.column_dimensions[col_letter].width = 40
                    elif header_value == 'source_link':
                        worksheet.column_dimensions[col_letter].width = 60
                    elif header_value == 'source_file':
                        worksheet.column_dimensions[col_letter].width = 30
                
                # 其他頁籤的一般欄寬調整
                else:
                    if 'revision' in header_value.lower():
                        worksheet.column_dimensions[col_letter].width = 35
                    elif '名稱' in header_value or 'name' in header_value:
                        worksheet.column_dimensions[col_letter].width = 25
                    elif '路徑' in header_value or 'path' in header_value:
                        worksheet.column_dimensions[col_letter].width = 30

            # 🔥 使用增強版的自動調整欄寬功能
            self._auto_adjust_column_widths_enhanced(worksheet, sheet_name)

            self.logger.debug(f"已格式化工作表: {sheet_name}")
            
        except Exception as e:
            self.logger.error(f"格式化工作表失敗 {sheet_name}: {str(e)}")

    def _calculate_display_width(self, text: str) -> float:
        """
        計算文字的顯示寬度（從 feature_three.py 複製）
        中文字符通常需要2個單位寬度，英文字符需要1個單位寬度
        
        Args:
            text: 要計算的文字
            
        Returns:
            顯示寬度
        """
        if not text:
            return 0
        
        width = 0
        for char in str(text):
            # 判斷是否為中文字符、全形字符或特殊符號
            if ord(char) > 127:  # 非 ASCII 字符
                if ord(char) >= 0x4e00 and ord(char) <= 0x9fff:  # 中文字符
                    width += 2
                elif ord(char) >= 0xff00 and ord(char) <= 0xffef:  # 全形字符
                    width += 2
                elif char in '📊🔄⭕🎯❌✅✔️':  # emoji 符號
                    width += 2.5
                else:
                    width += 1.5  # 其他特殊字符
            else:
                width += 1  # ASCII 字符
        
        return width

    def _adjust_summary_column_widths_enhanced(self, worksheet):
        """專門調整轉換摘要頁籤的欄寬（從 feature_three.py 複製並修改）"""
        try:
            from openpyxl.utils import get_column_letter
            
            # 動態計算每個欄位的適當寬度
            for col_num, cell in enumerate(worksheet[1], 1):
                col_letter = get_column_letter(col_num)
                header_value = str(cell.value) if cell.value else ''
                
                if header_value:
                    # 使用精確的寬度計算
                    header_display_width = self._calculate_display_width(header_value)
                    
                    # 計算該欄位內容的最大寬度
                    max_content_width = 0
                    for row_num in range(2, worksheet.max_row + 1):
                        content_cell = worksheet.cell(row=row_num, column=col_num)
                        if content_cell.value:
                            content_str = str(content_cell.value)
                            # 特別處理 HYPERLINK 函數
                            if content_str.startswith('=HYPERLINK('):
                                import re
                                match = re.search(r'=HYPERLINK\("[^"]*","([^"]*)"', content_str)
                                if match:
                                    display_text = match.group(1)
                                    content_width = self._calculate_display_width(display_text)
                                else:
                                    content_width = self._calculate_display_width(content_str)
                            else:
                                content_width = self._calculate_display_width(content_str)
                            
                            if content_width > max_content_width:
                                max_content_width = content_width
                    
                    # 根據欄位類型設定基礎寬度
                    if header_value == 'SN':
                        base_width = 8
                    elif 'revision' in header_value.lower():
                        base_width = 40
                    elif 'content' in header_value:
                        base_width = 80
                    elif 'URL' in header_value:
                        base_width = 60
                    elif '❌' in header_value or '✅' in header_value or '✔️' in header_value:
                        base_width = 40  # 長的統計欄位
                    elif '📊' in header_value or '🔄' in header_value or '⭕' in header_value or '🎯' in header_value:
                        base_width = max(header_display_width + 5, 20)  # 根據實際內容調整
                    elif '狀態' in header_value:
                        base_width = max(header_display_width + 5, 20)
                    elif 'ID' in header_value:
                        base_width = 15
                    elif '檔案' in header_value:
                        base_width = max(max_content_width + 5, 25)  # 根據檔名長度調整
                    else:
                        base_width = max(header_display_width + 5, 15)  # 確保表頭能完整顯示
                    
                    # 確保寬度足夠顯示所有內容
                    final_width = max(base_width, header_display_width + 5, max_content_width + 5)
                    
                    # 設定合理的最大寬度限制
                    final_width = min(final_width, 100)
                    
                else:
                    final_width = 15  # 空表頭的預設寬度
                
                # 設定欄寬
                worksheet.column_dimensions[col_letter].width = final_width
                
                self.logger.debug(f"比較摘要欄位 '{header_value}' 計算寬度: {final_width}")
            
            self.logger.info("✅ 已調整比較摘要頁籤的欄寬（增強版，確保所有內容完整顯示）")
            
        except Exception as e:
            self.logger.error(f"調整比較摘要欄寬失敗: {str(e)}")

    def _auto_adjust_column_widths_enhanced(self, worksheet, sheet_name: str):
        """自動調整欄寬以適應內容（從 feature_three.py 複製並修改）"""
        try:
            from openpyxl.utils import get_column_letter
            
            # 特別處理比較摘要頁籤
            if sheet_name in ["比較摘要", "轉換摘要"]:
                self._adjust_summary_column_widths_enhanced(worksheet)
                return
            
            # 遍歷所有欄位
            for col in worksheet.columns:
                max_content_width = 0
                header_width = 0
                column = col[0].column_letter
                
                # 計算表頭的顯示寬度
                header_cell = worksheet[f"{column}1"]
                if header_cell.value:
                    header_value = str(header_cell.value)
                    header_width = self._calculate_display_width(header_value)
                    self.logger.debug(f"欄位 {column} 表頭 '{header_value}' 顯示寬度: {header_width}")
                
                # 計算內容的最大顯示寬度（檢查所有行）
                for cell in col[1:]:  # 跳過表頭行
                    try:
                        if cell.value:
                            cell_content = str(cell.value)
                            # 特別處理 HYPERLINK 函數內容
                            if cell_content.startswith('=HYPERLINK('):
                                # 從 HYPERLINK 函數中提取顯示文字
                                import re
                                match = re.search(r'=HYPERLINK\("[^"]*","([^"]*)"', cell_content)
                                if match:
                                    display_text = match.group(1)
                                    cell_width = self._calculate_display_width(display_text)
                                else:
                                    cell_width = self._calculate_display_width(cell_content)
                            else:
                                cell_width = self._calculate_display_width(cell_content)
                            
                            if cell_width > max_content_width:
                                max_content_width = cell_width
                    except:
                        pass
                
                # 取表頭寬度和內容寬度的較大值，加上足夠的邊距
                required_width = max(header_width, max_content_width) + 5  # 增加邊距
                
                # 設定特殊欄位的最小寬度
                if header_cell.value:
                    header_value = str(header_cell.value)
                    
                    if 'revision' in header_value.lower():
                        min_width = 40  # 增加 revision 欄位寬度
                    elif 'content' in header_value:
                        min_width = 80  # 增加 content 欄位寬度
                    elif header_value in ['name', 'gerrit_name', 'compare_name', '專案名稱']:
                        min_width = 30  # 增加專案名稱欄位寬度
                    elif header_value in ['path', '專案路徑']:
                        min_width = 35  # 增加路徑欄位寬度
                    elif 'source_link' in header_value or 'gerrit_source_link' in header_value or 'compare_source_link' in header_value:
                        min_width = 60  # 增加連結欄位寬度
                    elif header_value in ['groups']:
                        min_width = 45  # 增加 groups 欄位寬度
                    elif header_value == 'SN':
                        min_width = 8
                    elif header_value in ['comparison_status', 'comparison_result']:
                        min_width = 25  # 增加比較狀態欄位寬度
                    elif header_value in ['目標 Revision', 'Revision 是否相等']:
                        # 🔥 讓這些欄位使用自動計算寬度，不設定最小寬度
                        min_width = max(header_width + 3, 12)  # 只比表頭稍微寬一點                        
                    elif 'upstream' in header_value.lower():
                        min_width = 25  # 增加 upstream 欄位寬度
                    elif 'dest-branch' in header_value.lower():
                        min_width = 25  # 增加 dest-branch 欄位寬度
                    elif 'clone-depth' in header_value.lower():
                        min_width = 15  # clone-depth 欄位寬度
                    elif 'remote' in header_value.lower():
                        min_width = 15  # remote 欄位寬度
                    else:
                        # 一般欄位最小寬度 = max(表頭寬度 + 邊距, 15)
                        min_width = max(header_width + 5, 15)
                    
                    final_width = max(required_width, min_width)
                else:
                    final_width = max(required_width, 15)
                
                # 設定最大寬度限制（增加到 120）
                final_width = min(final_width, 120)
                
                # 應用欄寬
                worksheet.column_dimensions[column].width = final_width
                
                self.logger.debug(f"欄位 {column} 最終寬度: {final_width} (表頭:{header_width}, 內容:{max_content_width})")
            
            self.logger.debug(f"已自動調整 {sheet_name} 的欄寬（增強版，確保所有內容完整顯示）")
            
        except Exception as e:
            self.logger.error(f"自動調整欄寬失敗 {sheet_name}: {str(e)}")
                    
    def _set_comparison_row_colors(self, worksheet, status_col_num: int, header_value: str):
        """設定比較狀態的行顏色（保持原方法，增加除錯）"""
        try:
            # 🔥 增加除錯資訊
            self.logger.debug(f"_set_comparison_row_colors 被調用: col={status_col_num}, header='{header_value}'")
            
            # 找到比較狀態欄位
            if header_value != 'comparison_status':
                return
            
            self.logger.info(f"🎨 找到 comparison_status 欄位，開始設定行顏色")
            self._apply_comparison_row_colors(worksheet, status_col_num)
                
        except Exception as e:
            self.logger.error(f"設定比較狀態行顏色失敗: {str(e)}")

    def _set_conversion_status_colors_v2(self, worksheet):
        """設定轉換狀態的文字顏色（從 feature_three.py 複製）"""
        try:
            from openpyxl.styles import Font
            
            blue_font = Font(color="0070C0", bold=True)
            gray_font = Font(color="808080", bold=True)
            
            # 只找轉換狀態欄位
            status_column = None
            
            for col_num, cell in enumerate(worksheet[1], 1):
                header_value = str(cell.value) if cell.value else ''
                if '轉換狀態' in header_value:
                    status_column = col_num
                    break
            
            # 🔥 只有找到轉換狀態欄位才設定顏色（避免本地比較模式的錯誤）
            if status_column:
                for row_num in range(2, worksheet.max_row + 1):
                    status_cell = worksheet.cell(row=row_num, column=status_column)
                    status_value = str(status_cell.value) if status_cell.value else ''
                    
                    if '🔄 已轉換' in status_value:
                        status_cell.font = blue_font
                    elif '⭕ 未轉換' in status_value:
                        status_cell.font = gray_font
            
        except Exception as e:
            self.logger.error(f"設定轉換狀態顏色失敗: {str(e)}")

    def _add_manifest_hyperlinks(self, worksheet, sheet_name: str):
        """為 manifest 相關頁籤添加 source_link 欄位的正確 gerrit 連結（修正版：使用 HYPERLINK 函數）"""
        try:
            # 找到需要處理的欄位
            source_file_col = None
            gerrit_source_file_col = None
            source_link_col = None
            gerrit_source_link_col = None
            compare_source_link_col = None
            
            for col_num, cell in enumerate(worksheet[1], 1):  # 表頭行
                header_value = str(cell.value) if cell.value else ''
                
                if header_value == 'source_file':
                    source_file_col = col_num
                elif header_value == 'gerrit_source_file':
                    gerrit_source_file_col = col_num
                elif header_value == 'source_link':
                    source_link_col = col_num
                elif header_value == 'gerrit_source_link':
                    gerrit_source_link_col = col_num
                elif header_value == 'compare_source_link':
                    compare_source_link_col = col_num
            
            # 🔥 只有特定頁籤的 source_file 欄位需要添加連結
            source_file_need_link = sheet_name in ['來源的 manifest', 'gerrit 上的 manifest', '目標的 manifest']
            
            # 為 source_file 欄位添加連結（僅限指定頁籤）
            if source_file_col and source_file_need_link:
                for row_num in range(2, worksheet.max_row + 1):
                    cell = worksheet.cell(row=row_num, column=source_file_col)
                    filename = str(cell.value) if cell.value else ''
                    
                    if filename and filename not in ['', 'N/A']:
                        gerrit_url = self._generate_gerrit_manifest_link(filename)
                        self._add_hyperlink_formula_to_cell(worksheet, row_num, source_file_col, gerrit_url, filename)
            
            # 為 gerrit_source_file 欄位添加連結
            if gerrit_source_file_col:
                for row_num in range(2, worksheet.max_row + 1):
                    cell = worksheet.cell(row=row_num, column=gerrit_source_file_col)
                    filename = str(cell.value) if cell.value else ''
                    
                    if filename and filename not in ['', 'N/A']:
                        gerrit_url = self._generate_gerrit_manifest_link(filename)
                        self._add_hyperlink_formula_to_cell(worksheet, row_num, gerrit_source_file_col, gerrit_url, filename)
            
            # 🔥 修正：為 source_link 欄位添加正確的專案連結（使用 HYPERLINK 函數）
            if source_link_col:
                for row_num in range(2, worksheet.max_row + 1):
                    # 取得該行的專案資訊
                    name_cell = self._find_cell_value_in_row(worksheet, row_num, ['name'])
                    revision_cell = self._find_cell_value_in_row(worksheet, row_num, ['revision'])
                    remote_cell = self._find_cell_value_in_row(worksheet, row_num, ['remote'])
                    
                    if name_cell:
                        project_name = str(name_cell)
                        revision = str(revision_cell) if revision_cell else ''
                        remote = str(remote_cell) if remote_cell else ''
                        
                        # 🔥 使用新的生成邏輯
                        gerrit_project_url = self._generate_source_link(project_name, revision, remote)
                        
                        if gerrit_project_url and gerrit_project_url != 'N/A':
                            # 🔥 使用 HYPERLINK 格式，顯示連結本身
                            self._add_hyperlink_formula_to_cell(worksheet, row_num, source_link_col, gerrit_project_url, gerrit_project_url)
            
            # 🔥 修正：為 gerrit_source_link 欄位添加正確的專案連結（使用 HYPERLINK 函數）
            if gerrit_source_link_col:
                for row_num in range(2, worksheet.max_row + 1):
                    # 取得該行的 Gerrit 專案資訊
                    gerrit_name_cell = self._find_cell_value_in_row(worksheet, row_num, ['gerrit_name'])
                    gerrit_revision_cell = self._find_cell_value_in_row(worksheet, row_num, ['gerrit_revision'])
                    gerrit_remote_cell = self._find_cell_value_in_row(worksheet, row_num, ['gerrit_remote'])
                    
                    if gerrit_name_cell:
                        project_name = str(gerrit_name_cell)
                        revision = str(gerrit_revision_cell) if gerrit_revision_cell else ''
                        remote = str(gerrit_remote_cell) if gerrit_remote_cell else ''
                        
                        gerrit_project_url = self._generate_source_link(project_name, revision, remote)
                        
                        if gerrit_project_url and gerrit_project_url != 'N/A':
                            self._add_hyperlink_formula_to_cell(worksheet, row_num, gerrit_source_link_col, gerrit_project_url, gerrit_project_url)
            
            # 🔥 新增：為 compare_source_link 欄位添加正確的專案連結（使用 HYPERLINK 函數）
            if compare_source_link_col:
                for row_num in range(2, worksheet.max_row + 1):
                    # 取得該行的 compare 專案資訊
                    compare_name_cell = self._find_cell_value_in_row(worksheet, row_num, ['compare_name'])
                    compare_revision_cell = self._find_cell_value_in_row(worksheet, row_num, ['compare_revision'])
                    compare_remote_cell = self._find_cell_value_in_row(worksheet, row_num, ['compare_remote'])
                    
                    if compare_name_cell:
                        project_name = str(compare_name_cell)
                        revision = str(compare_revision_cell) if compare_revision_cell else ''
                        remote = str(compare_remote_cell) if compare_remote_cell else ''
                        
                        gerrit_project_url = self._generate_source_link(project_name, revision, remote)
                        
                        if gerrit_project_url and gerrit_project_url != 'N/A':
                            self._add_hyperlink_formula_to_cell(worksheet, row_num, compare_source_link_col, gerrit_project_url, gerrit_project_url)
            
            # 記錄處理結果
            if source_file_col and source_file_need_link:
                self.logger.info(f"✅ 已為 {sheet_name} 添加 source_file 欄位連結")
            
            if gerrit_source_file_col:
                self.logger.info(f"✅ 已為 {sheet_name} 添加 gerrit_source_file 欄位連結")
            
            if source_link_col:
                self.logger.info(f"✅ 已為 {sheet_name} 添加 source_link 欄位正確的專案連結（HYPERLINK函數）")
            
            if gerrit_source_link_col:
                self.logger.info(f"✅ 已為 {sheet_name} 添加 gerrit_source_link 欄位正確的專案連結（HYPERLINK函數）")
                
            if compare_source_link_col:
                self.logger.info(f"✅ 已為 {sheet_name} 添加 compare_source_link 欄位正確的專案連結（HYPERLINK函數）")
            
        except Exception as e:
            self.logger.error(f"添加 {sheet_name} 超連結失敗: {str(e)}")

    def _find_cell_value_in_row(self, worksheet, row_num: int, header_names: List[str]):
        """
        在指定行中尋找指定表頭名稱對應的值
        
        Args:
            worksheet: Excel 工作表
            row_num: 行號
            header_names: 要尋找的表頭名稱列表
            
        Returns:
            找到的值，如果沒找到則返回 None
        """
        try:
            # 先找到表頭對應的欄位號
            for col_num, header_cell in enumerate(worksheet[1], 1):  # 表頭行
                header_value = str(header_cell.value) if header_cell.value else ''
                
                if header_value in header_names:
                    # 找到對應欄位，取得該行該欄的值
                    cell = worksheet.cell(row=row_num, column=col_num)
                    return cell.value
            
            return None
            
        except Exception as e:
            self.logger.error(f"尋找行中欄位值失敗: {str(e)}")
            return None
        
    def _add_hyperlink_formula_to_cell(self, worksheet, row: int, col: int, url: str, display_text: str = None):
        """
        為 Excel 單元格添加 HYPERLINK 函數格式的超連結（增強版）
        """
        try:
            from openpyxl.styles import Font
            
            cell = worksheet.cell(row=row, column=col)
            
            # 🔥 確保 URL 和顯示文字不為空
            if not url or url == 'N/A':
                self.logger.debug(f"跳過無效的 URL: {url}")
                return
            
            # 清理 URL 中的特殊字符
            clean_url = str(url).replace('"', '""')
            
            # 🔥 修正：如果沒有 display_text，直接顯示 URL
            if not display_text or display_text == url:
                cell.value = f'=HYPERLINK("{clean_url}")'
                self.logger.debug(f"設定 HYPERLINK (URL only): {clean_url}")
            else:
                clean_display_text = str(display_text).replace('"', '""')
                cell.value = f'=HYPERLINK("{clean_url}","{clean_display_text}")'
                self.logger.debug(f"設定 HYPERLINK (with text): {clean_display_text} → {clean_url}")
            
            # 設定藍色超連結樣式
            cell.font = Font(color="0000FF", underline="single")
            
        except Exception as e:
            self.logger.error(f"添加 HYPERLINK 函數失敗: {str(e)}")
            # 🔥 備用方案：直接顯示URL
            try:
                cell = worksheet.cell(row=row, column=col)
                cell.value = url
                cell.font = Font(color="0000FF")
                self.logger.debug(f"使用備用方案顯示連結: {url}")
            except:
                pass
            
    # ===============================
    # ===== 比較模式專用的後處理方法 =====
    # ===============================

    def _fix_sheet_filenames(self, workbook, excel_file: str, overwrite_type: str, 
                            source_file_path: Optional[str], target_file_path: Optional[str], 
                            is_local_comparison: bool = None):
        """修正 Excel 頁籤中的檔案名稱問題，統一處理所有比較模式"""
        try:
            # 🔥 如果沒有傳遞 is_local_comparison，自動判斷
            if is_local_comparison is None:
                is_local_comparison = (overwrite_type == "local_vs_local")
            
            is_gerrit_comparison = overwrite_type.startswith("local_vs_") and overwrite_type != "local_vs_local"
            
            # 獲得正確的檔案名稱
            source_filename = os.path.basename(source_file_path) if source_file_path else '無'
            target_filename = os.path.basename(target_file_path) if target_file_path else '無'
            
            self.logger.info(f"🔧 修正 Excel 檔案（統一邏輯）")
            self.logger.info(f"   比較類型: {overwrite_type}")
            self.logger.info(f"   本地比較: {is_local_comparison}")
            self.logger.info(f"   Gerrit比較: {is_gerrit_comparison}")
            self.logger.info(f"   來源檔案: {source_filename}")
            self.logger.info(f"   目標檔案: {target_filename}")
            
            # 重新設計 "比較摘要" 頁籤（統一邏輯）
            if '轉換摘要' in workbook.sheetnames:
                self._fix_summary_sheet_unified(workbook, overwrite_type, source_filename, target_filename, target_file_path)
            
            # 修正其他頁籤（統一邏輯）
            # 🔥 重要：傳遞 is_local_comparison 參數
            self._fix_other_sheets(workbook, is_local_comparison, source_filename, target_filename, target_file_path)
            
            # 保存修改
            workbook.save(excel_file)
            
            self.logger.info("✅ Excel 檔案修正完成（統一邏輯版本）")
        
        except Exception as e:
            self.logger.error(f"修正 Excel 檔案失敗: {str(e)}")

    def _fix_summary_sheet_unified(self, workbook, overwrite_type: str, source_filename: str, 
                                target_filename: str, target_file_path: Optional[str]):
        """統一修正比較摘要頁籤"""
        try:
            from openpyxl.styles import PatternFill, Font
            
            # 定義表頭顏色
            blue_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
            purple_fill = PatternFill(start_color="8A2BE2", end_color="8A2BE2", fill_type="solid")
            orange_fill = PatternFill(start_color="FF8C00", end_color="FF8C00", fill_type="solid")
            green_fill = PatternFill(start_color="00B050", end_color="00B050", fill_type="solid")
            white_font = Font(color="FFFFFF", bold=True)
            
            ws = workbook['轉換摘要']
            ws.title = '比較摘要'
            
            # 清空原有內容，重新設計欄位
            ws.delete_rows(1, ws.max_row)
            
            # 重新設計表頭（統一版本）
            headers = [
                'SN', '比較類型', '來源檔案名稱', '目標檔案類型',
                '目標檔案下載狀態', '目標檔案包含 include 標籤', '目標檔案已展開',
                '實際比較的目標檔案', '📊 總專案數', '🎯 目標檔案專案數',
                '❌ 與現行版本版號差異數', '✔️ 與現行版本版號相同數',
                '❌ 比較現行版本內容差異數', '✔️ 比較現行版本內容相同數'
            ]
            
            # 寫入表頭並設定顏色
            for col, header in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col)
                cell.value = header
                cell.font = white_font
                
                # 根據欄位設定顏色
                if header in ['來源檔案名稱', '實際比較的目標檔案']:
                    cell.fill = purple_fill
                elif header in ['❌ 與現行版本版號差異數', '✔️ 與現行版本版號相同數']:
                    cell.fill = orange_fill
                elif header in ['❌ 比較現行版本內容差異數', '✔️ 比較現行版本內容相同數']:
                    cell.fill = green_fill
                else:
                    cell.fill = blue_fill
            
            # 準備數據（統一邏輯）
            is_local_comparison = (overwrite_type == "local_vs_local")
            
            if is_local_comparison:
                target_type = target_filename
                actual_target_file = target_filename
                download_status = 'N/A (本地檔案)'
                include_status = '否'
                expanded_status = '否'
            else:
                # Gerrit 比較模式
                target_type_mapping = {
                    'local_vs_master': 'atv-google-refplus.xml',
                    'local_vs_premp': 'atv-google-refplus-premp.xml', 
                    'local_vs_mp': 'atv-google-refplus-wave.xml',
                    'local_vs_mp_backup': 'atv-google-refplus-wave-backup.xml'
                }
                
                if target_file_path:
                    actual_filename = os.path.basename(target_file_path)
                    target_type = actual_filename[7:] if actual_filename.startswith('gerrit_') else actual_filename
                else:
                    target_type = target_type_mapping.get(overwrite_type, '未知')
                
                if hasattr(self, 'expanded_file_path') and self.expanded_file_path:
                    actual_target_file = os.path.basename(self.expanded_file_path)
                elif target_file_path:
                    actual_target_file = os.path.basename(target_file_path)
                else:
                    actual_target_file = ""
                
                download_status = '成功' if target_file_path else '失敗'
                include_status = '是' if hasattr(self, 'expanded_file_path') and self.expanded_file_path else '否'
                expanded_status = '是' if hasattr(self, 'use_expanded') and self.use_expanded else '否'
            
            # 寫入數據
            data_row = [
                1, overwrite_type, source_filename, target_type,
                download_status, include_status, expanded_status, actual_target_file,
                '', '', '', '', '', ''  # 統計數據會被後續邏輯填入
            ]
            
            for col, value in enumerate(data_row, 1):
                ws.cell(row=2, column=col).value = value
            
            # 添加超連結（僅非本地比較模式）
            if not is_local_comparison and actual_target_file and target_type != '本地檔案':
                target_filename_clean = actual_target_file.replace('gerrit_', '')
                gerrit_url = self._generate_gerrit_manifest_link(target_filename_clean)
                self._add_hyperlink_to_cell(ws, 2, 8, gerrit_url, actual_target_file)
            
            self.logger.info("✅ 比較摘要頁籤修正完成（統一邏輯）")
            
        except Exception as e:
            self.logger.error(f"修正比較摘要頁籤失敗: {str(e)}")
            
    def _fix_other_sheets(self, workbook, is_local_comparison: bool, source_filename: str, 
                    target_filename: str, target_file_path: Optional[str]):
        """修正其他頁籤的內容 - 增強版：特別處理本地比較模式的字體問題"""
        try:
            from openpyxl.styles import PatternFill, Font
            
            purple_fill = PatternFill(start_color="8A2BE2", end_color="8A2BE2", fill_type="solid")
            white_font = Font(color="FFFFFF", bold=True)
            normal_font = Font(color="000000", underline=None)
            
            # 修正 "轉換後專案" → "與現行版本比較差異"
            if '轉換後專案' in workbook.sheetnames:
                ws = workbook['轉換後專案']
                ws.title = '與現行版本比較差異'
                
                # 🔥 新增：檢查是否為本地比較模式，如果是則不處理轉換狀態欄位
                has_conversion_status = False
                conversion_status_col = None
                
                for col in range(1, ws.max_column + 1):
                    header_value = str(ws.cell(row=1, column=col).value) if ws.cell(row=1, column=col).value else ''
                    if header_value == '轉換狀態':
                        has_conversion_status = True
                        conversion_status_col = col
                        break
                
                # 🔥 記錄發現的狀態，用於除錯
                self.logger.info(f"📊 '與現行版本比較差異' 頁籤檢查:")
                self.logger.info(f"   是否為本地比較: {is_local_comparison}")
                self.logger.info(f"   是否有轉換狀態欄位: {has_conversion_status}")
                self.logger.info(f"   轉換狀態欄位位置: {conversion_status_col}")
                
                # 找到現有欄位位置
                source_revision_col = None
                target_revision_col = None
                
                for col in range(1, ws.max_column + 1):
                    header_value = str(ws.cell(row=1, column=col).value) if ws.cell(row=1, column=col).value else ''
                    
                    if header_value in ['原始 Revision', '來源 Revision']:
                        source_revision_col = col
                    elif header_value in ['轉換後 Revision', '目標 Revision']:
                        target_revision_col = col
                
                # 在 "來源 Revision" 左邊插入 "來源檔案" 欄位
                if source_revision_col:
                    ws.insert_cols(source_revision_col)
                    header_cell = ws.cell(row=1, column=source_revision_col)
                    header_cell.value = '來源檔案'
                    header_cell.fill = purple_fill
                    header_cell.font = white_font
                    
                    # 🔥 來源檔案欄位 - 確保無超連結（所有模式）
                    for row in range(2, ws.max_row + 1):
                        cell = ws.cell(row=row, column=source_revision_col)
                        cell.value = source_filename
                        cell.hyperlink = None
                        cell.font = normal_font
                        cell.style = 'Normal'
                    
                    # 更新目標欄位位置
                    target_revision_col += 1
                    if conversion_status_col and conversion_status_col >= source_revision_col:
                        conversion_status_col += 1
                
                # 在 "目標 Revision" 左邊插入 "比較檔案" 欄位
                if target_revision_col:
                    ws.insert_cols(target_revision_col)
                    header_cell = ws.cell(row=1, column=target_revision_col)
                    header_cell.value = '比較檔案'
                    header_cell.fill = purple_fill
                    header_cell.font = white_font
                    
                    # 🔥 重點修正：比較檔案欄位的處理
                    if is_local_comparison:
                        # 🔥 本地比較模式：特別強化黑色字體設定
                        for row in range(2, ws.max_row + 1):
                            cell = ws.cell(row=row, column=target_revision_col)
                            cell.value = target_filename
                            cell.hyperlink = None  # 🔥 重要：確保移除任何超連結
                            cell.font = normal_font
                            cell.style = 'Normal'  # 🔥 重要：重設樣式
                            
                            # 🔥 額外確保：移除可能的樣式屬性
                            if hasattr(cell, '_style'):
                                cell._style = None
                        
                        self.logger.info(f"✅ 本地比較模式：'比較檔案'欄位已強化設定為黑色字體")
                    else:
                        # Gerrit 比較：添加超連結
                        actual_target_file = os.path.basename(target_file_path) if target_file_path else ""
                        for row in range(2, ws.max_row + 1):
                            ws.cell(row=row, column=target_revision_col).value = actual_target_file
                            if actual_target_file:
                                clean_filename = actual_target_file.replace('gerrit_', '')
                                gerrit_url = self._generate_gerrit_manifest_link(clean_filename)
                                self._add_hyperlink_to_cell(ws, row, target_revision_col, gerrit_url, actual_target_file)
                    
                    # 更新轉換狀態欄位位置（如果存在）
                    if conversion_status_col:
                        conversion_status_col += 1
                
                # 修正表頭名稱
                for col in range(1, ws.max_column + 1):
                    header_value = str(ws.cell(row=1, column=col).value) if ws.cell(row=1, column=col).value else ''
                    
                    if header_value in ['原始 Revision', '來源 Revision']:
                        ws.cell(row=1, column=col).value = '來源 Revision'
                    elif header_value in ['轉換後 Revision', '目標 Revision']:
                        ws.cell(row=1, column=col).value = '目標 Revision'
                    elif header_value in ['轉換說明', '比較說明']:
                        ws.cell(row=1, column=col).value = '比較說明'
                
                # 統一處理目標 Revision
                self._fix_target_revision_unified(ws, target_revision_col + 1, target_file_path, is_local_comparison)
                
                # 🔥 重要：使用修正版的公式設定方法，確保向後兼容
                self._reapply_revision_comparison_formulas(ws, is_local_comparison)
                
                # 🔥 額外保護：針對本地比較模式再次確保"比較檔案"欄位
                if is_local_comparison:
                    self._ensure_compare_file_black_text(ws, target_revision_col)
            
            # 修正其他頁籤...
            self._fix_difference_sheet(workbook, is_local_comparison, source_filename, target_filename)
            self._fix_manifest_sheets(workbook, is_local_comparison, source_filename, target_filename, target_file_path)
            
        except Exception as e:
            self.logger.error(f"修正其他頁籤失敗: {str(e)}")

    def _ensure_compare_file_black_text(self, worksheet, compare_file_col: int):
        """確保比較檔案欄位是黑色字體（本地比較模式專用）"""
        try:
            from openpyxl.styles import Font
            
            black_font = Font(color="000000", bold=False, underline=None)
            
            for row in range(2, worksheet.max_row + 1):
                cell = worksheet.cell(row=row, column=compare_file_col)
                cell.font = black_font
                cell.hyperlink = None
                cell.style = 'Normal'
            
            self.logger.info("🔒 額外確保：'比較檔案'欄位為黑色字體（本地比較模式）")
            
        except Exception as e:
            self.logger.error(f"確保比較檔案黑色字體失敗: {str(e)}")
            
    def _fix_target_revision_unified(self, worksheet, target_revision_col: int, target_file_path: str, is_local_comparison: bool):
        """統一修正目標 Revision 欄位 - 適用於所有比較模式"""
        try:
            if not target_file_path or not os.path.exists(target_file_path):
                self.logger.warning(f"目標檔案不存在，跳過 Revision 修正: {target_file_path}")
                return
            
            self.logger.info(f"🔧 開始修正目標 Revision（統一邏輯）")
            
            # 重新解析目標檔案
            with open(target_file_path, 'r', encoding='utf-8') as f:
                target_content = f.read()
            
            target_root = ET.fromstring(target_content)
            
            # 讀取目標檔案 default 資訊
            target_default_revision = ''
            target_default = target_root.find('default')
            if target_default is not None:
                target_default_revision = target_default.get('revision', '')
            
            # 創建目標檔案的專案字典
            target_projects = {}
            for project in target_root.findall('project'):
                project_name = project.get('name', '')
                project_path = project.get('path', '')
                key = f"{project_name}|||{project_path}"
                
                target_projects[key] = project.get('revision', '') or target_default_revision
            
            # 找到專案名稱和路徑的欄位
            name_col = None
            path_col = None
            for col in range(1, worksheet.max_column + 1):
                header_value = str(worksheet.cell(row=1, column=col).value) if worksheet.cell(row=1, column=col).value else ''
                if header_value in ['專案名稱', 'name']:
                    name_col = col
                elif header_value in ['專案路徑', 'path']:
                    path_col = col
            
            if not name_col or not path_col:
                self.logger.error("無法找到專案名稱或路徑欄位")
                return
            
            # 更新每一行的目標 Revision
            updated_count = 0
            for row in range(2, worksheet.max_row + 1):
                project_name = str(worksheet.cell(row=row, column=name_col).value) if worksheet.cell(row=row, column=name_col).value else ''
                project_path = str(worksheet.cell(row=row, column=path_col).value) if worksheet.cell(row=row, column=path_col).value else ''
                
                key = f"{project_name}|||{project_path}"
                target_revision = target_projects.get(key, '')
                
                if target_revision:
                    worksheet.cell(row=row, column=target_revision_col).value = target_revision
                    updated_count += 1
                else:
                    # 專案在目標檔案中不存在
                    worksheet.cell(row=row, column=target_revision_col).value = 'N/A (專案不存在)'
            
            self.logger.info(f"✅ 已更新 {updated_count} 個專案的目標 Revision（統一邏輯）")
            
        except Exception as e:
            self.logger.error(f"修正目標 Revision 失敗: {str(e)}")
            
    def _fix_target_revision_for_local_comparison(self, worksheet, target_revision_col: int, target_file_path: str):
        """修正本地比較模式下的目標 Revision 欄位"""
        try:
            if not target_file_path or not os.path.exists(target_file_path):
                return
            
            # 重新解析目標檔案
            with open(target_file_path, 'r', encoding='utf-8') as f:
                target_content = f.read()
            
            target_root = ET.fromstring(target_content)
            
            # 讀取目標檔案 default 資訊
            target_default_revision = ''
            target_default = target_root.find('default')
            if target_default is not None:
                target_default_revision = target_default.get('revision', '')
            
            # 創建目標檔案的專案字典
            target_projects = {}
            for project in target_root.findall('project'):
                project_name = project.get('name', '')
                project_path = project.get('path', '')
                key = f"{project_name}|||{project_path}"
                
                target_projects[key] = project.get('revision', '') or target_default_revision
            
            # 找到專案名稱和路徑的欄位
            name_col = None
            path_col = None
            for col in range(1, worksheet.max_column + 1):
                header_value = str(worksheet.cell(row=1, column=col).value) if worksheet.cell(row=1, column=col).value else ''
                if header_value in ['專案名稱', 'name']:
                    name_col = col
                elif header_value in ['專案路徑', 'path']:
                    path_col = col
            
            if not name_col or not path_col:
                return
            
            # 更新每一行的目標 Revision
            updated_count = 0
            for row in range(2, worksheet.max_row + 1):
                project_name = str(worksheet.cell(row=row, column=name_col).value) if worksheet.cell(row=row, column=name_col).value else ''
                project_path = str(worksheet.cell(row=row, column=path_col).value) if worksheet.cell(row=row, column=path_col).value else ''
                
                key = f"{project_name}|||{project_path}"
                target_revision = target_projects.get(key, '')
                
                if target_revision:
                    worksheet.cell(row=row, column=target_revision_col).value = target_revision
                    updated_count += 1
            
            self.logger.info(f"✅ 已更新 {updated_count} 個專案的目標 Revision")
            
        except Exception as e:
            self.logger.error(f"修正目標 Revision 失敗: {str(e)}")

    def _reapply_revision_comparison_formulas(self, worksheet, is_local_comparison: bool = None):
        """重新設定 Revision 比較公式（修正版：根據比較模式處理）"""
        try:
            from openpyxl.utils import get_column_letter
            from openpyxl.styles import Font
            from openpyxl.formatting.rule import FormulaRule
            
            # 🔥 如果沒有傳入 is_local_comparison，自動判斷
            if is_local_comparison is None:
                # 通過檢查工作表內容或類別變數來判斷
                is_local_comparison = getattr(self, '_current_is_local_comparison', False)
            
            # 找到相關欄位的位置
            source_revision_col = None
            target_revision_col = None
            comparison_col = None
            compare_file_col = None
            
            for col in range(1, worksheet.max_column + 1):
                header_value = str(worksheet.cell(row=1, column=col).value) if worksheet.cell(row=1, column=col).value else ''
                if header_value == '來源 Revision':
                    source_revision_col = col
                elif header_value == '目標 Revision':
                    # 🔥 目標 Revision 使用較小的寬度
                    min_width = max(header_width + 2, 25)  # 固定合理寬度
                elif header_value == 'Revision 是否相等':
                    # 🔥 Revision 是否相等 用更小的寬度
                    min_width = max(header_width + 2, 12)  # 很小的寬度
                elif header_value == '比較檔案':
                    compare_file_col = col
            
            if not all([source_revision_col, target_revision_col, comparison_col]):
                self.logger.warning("無法找到所需的 Revision 欄位")
                return
            
            # 🔥 步驟1：根據比較模式保護"比較檔案"欄位
            if compare_file_col:
                self._protect_compare_file_column(worksheet, compare_file_col, is_local_comparison)
            
            # 🔥 步驟2：清除現有的條件格式，避免衝突
            self._clean_existing_conditional_formatting(worksheet)
            
            # 🔥 步驟3：設定動態公式（核心邏輯不變）
            self._set_revision_comparison_formulas(worksheet, source_revision_col, target_revision_col, comparison_col)
            
            # 🔥 步驟4：只對"Revision 是否相等"欄位設定條件格式
            self._set_conditional_formatting_for_revision_column(worksheet, comparison_col)
            
            # 🔥 步驟5：根據比較模式最終確認"比較檔案"欄位格式
            if compare_file_col:
                self._final_verify_compare_file_column(worksheet, compare_file_col, is_local_comparison)
            
            self.logger.info("✅ 已重新設定 Revision 比較公式和條件格式（核心邏輯保持不變）")
            
        except Exception as e:
            self.logger.error(f"重新設定 Revision 比較公式失敗: {str(e)}")

    def _final_verify_compare_file_column(self, worksheet, compare_file_col: int, is_local_comparison: bool = None):
        """根據比較模式最終確認"比較檔案"欄位格式"""
        try:
            from openpyxl.styles import Font
            from openpyxl.utils import get_column_letter
            
            # 🔥 如果沒有傳入參數，使用類別變數
            if is_local_comparison is None:
                is_local_comparison = getattr(self, '_current_is_local_comparison', False)
            
            col_letter = get_column_letter(compare_file_col)
            
            if is_local_comparison:
                # 🔥 只有本地比較模式才強制設定黑色字體
                black_font = Font(color="000000", bold=False, underline=None)
                
                # 🔥 最終確認並強制設定黑色字體
                for row in range(2, worksheet.max_row + 1):
                    cell = worksheet.cell(row=row, column=compare_file_col)
                    
                    # 強制設定為黑色字體
                    cell.font = black_font
                    cell.hyperlink = None
                    cell.style = 'Normal'
                
                self.logger.info(f"✅ 最終確認：'比較檔案'欄位({col_letter})已設定為黑色字體（僅限本地比較）")
            else:
                # 🔥 Gerrit 比較模式：不改變現有樣式
                self.logger.info(f"✅ 最終確認：'比較檔案'欄位({col_letter})保持 Gerrit 超連結樣式")
            
        except Exception as e:
            self.logger.error(f"最終確認失敗: {str(e)}")
            
    def _set_conditional_formatting_for_revision_column(self, worksheet, comparison_col: int):
        """只對"Revision 是否相等"欄位設定條件格式"""
        try:
            from openpyxl.utils import get_column_letter
            from openpyxl.styles import Font
            from openpyxl.formatting.rule import FormulaRule
            
            equal_col_letter = get_column_letter(comparison_col)
            
            # 🔥 確認"Revision 是否相等"欄位確實存在
            equal_header = str(worksheet.cell(row=1, column=comparison_col).value) if worksheet.cell(row=1, column=comparison_col).value else ''
            if "Revision 是否相等" not in equal_header:
                self.logger.error(f"❌ 第 {comparison_col} 欄不是 'Revision 是否相等' 欄位，實際是: '{equal_header}'")
                return
            
            # 🔥 設定條件格式規則
            green_rule = FormulaRule(
                formula=[f'${equal_col_letter}2="Y"'],
                font=Font(color="00B050", bold=True)
            )
            
            red_rule = FormulaRule(
                formula=[f'${equal_col_letter}2="N"'],
                font=Font(color="FF0000", bold=True)
            )
            
            # 🔥 重要：確保範圍只包含"Revision 是否相等"欄位
            range_string = f"{equal_col_letter}2:{equal_col_letter}{worksheet.max_row}"
            
            # 🔥 確認範圍正確性
            self.logger.info(f"🎯 條件格式範圍: {range_string}")
            self.logger.info(f"🎯 該範圍只影響 '{equal_header}' 欄位")
            
            worksheet.conditional_formatting.add(range_string, green_rule)
            worksheet.conditional_formatting.add(range_string, red_rule)
            
            self.logger.info("✅ 已設定條件格式（僅限 Revision 是否相等欄位）")
            
        except Exception as e:
            self.logger.error(f"設定條件格式失敗: {str(e)}")
            
    def _set_revision_comparison_formulas(self, worksheet, source_col: int, target_col: int, comparison_col: int):
        """設定 Revision 比較公式"""
        try:
            from openpyxl.utils import get_column_letter
            
            source_col_letter = get_column_letter(source_col)
            target_col_letter = get_column_letter(target_col)
            
            self.logger.info(f"📊 設定動態 Revision 比較公式:")
            self.logger.info(f"   來源 Revision: {source_col_letter} 欄")
            self.logger.info(f"   目標 Revision: {target_col_letter} 欄")
            
            # 為每一行設定動態公式
            for row in range(2, worksheet.max_row + 1):
                cell = worksheet.cell(row=row, column=comparison_col)
                formula = f'=IF({source_col_letter}{row}={target_col_letter}{row},"Y","N")'
                cell.value = formula
                # 🔥 新增：設定置中對齊
                from openpyxl.styles import Alignment
                cell.alignment = Alignment(horizontal='center', vertical='center')
            
            self.logger.info("✅ 已設定動態比較公式")
            
        except Exception as e:
            self.logger.error(f"設定比較公式失敗: {str(e)}")
            
    def _clean_existing_conditional_formatting(self, worksheet):
        """清除現有的條件格式，避免衝突"""
        try:
            # 🔥 記錄現有的條件格式
            cf_count = len(worksheet.conditional_formatting)
            if cf_count > 0:
                self.logger.info(f"🗑️ 發現 {cf_count} 個現有條件格式，準備清除")
                
                # 🔥 記錄範圍（用於除錯）
                for i, cf in enumerate(worksheet.conditional_formatting):
                    for cell_range in cf.cells:
                        self.logger.debug(f"   第 {i+1} 個條件格式範圍: {cell_range}")
                
                # 🔥 創建新的空的條件格式列表
                worksheet.conditional_formatting = type(worksheet.conditional_formatting)()
                self.logger.info("✅ 已清除所有現有條件格式")
            else:
                self.logger.debug("ℹ️ 沒有現有的條件格式")
                
        except Exception as e:
            self.logger.warning(f"清除現有條件格式失敗: {str(e)}")
            
    def _protect_compare_file_column(self, worksheet, compare_file_col: int, is_local_comparison: bool = None):
        """根據比較模式保護"比較檔案"欄位"""
        try:
            from openpyxl.styles import Font
            from openpyxl.utils import get_column_letter
            
            # 🔥 如果沒有傳入參數，使用類別變數
            if is_local_comparison is None:
                is_local_comparison = getattr(self, '_current_is_local_comparison', False)
            
            col_letter = get_column_letter(compare_file_col)
            
            if is_local_comparison:
                # 🔥 只有本地比較模式才設定黑色字體
                black_font = Font(color="000000", bold=False, underline=None)
                
                self.logger.info(f"🛡️ 預先保護 '比較檔案' 欄位 ({col_letter} 欄) - 本地比較模式")
                
                for row in range(2, worksheet.max_row + 1):
                    cell = worksheet.cell(row=row, column=compare_file_col)
                    cell.font = black_font
                    cell.hyperlink = None  # 移除超連結
                    cell.style = 'Normal'  # 重設為一般樣式
                
                self.logger.info("✅ '比較檔案' 欄位已預先設定為黑色字體（僅限本地比較）")
            else:
                # 🔥 Gerrit 比較模式：保持原有超連結樣式
                self.logger.info(f"🛡️ '比較檔案' 欄位 ({col_letter} 欄) - Gerrit比較模式，保持超連結樣式")
            
        except Exception as e:
            self.logger.error(f"保護比較檔案欄位失敗: {str(e)}")
            
    def _fix_difference_sheet(self, workbook, is_local_comparison: bool, source_filename: str, target_filename: str):
        """修正差異頁籤 - 處理本地比較的欄位名稱（增加顏色重新設定）"""
        try:
            from openpyxl.styles import PatternFill, Font
            
            purple_fill = PatternFill(start_color="8A2BE2", end_color="8A2BE2", fill_type="solid")
            green_fill = PatternFill(start_color="00B050", end_color="00B050", fill_type="solid")
            white_font = Font(color="FFFFFF", bold=True)
            
            if '轉換後與 Gerrit manifest 的差異' in workbook.sheetnames:
                ws = workbook['轉換後與 Gerrit manifest 的差異']
                ws.title = '比較專案內容差異明細'
                
                # 記錄 comparison_status 欄位位置（重新設定顏色用）
                comparison_status_col = None
                
                # 🔥 修正：處理本地比較模式的欄位名稱和顏色
                for col in range(1, ws.max_column + 1):
                    header_value = str(ws.cell(row=1, column=col).value) if ws.cell(row=1, column=col).value else ''
                    header_cell = ws.cell(row=1, column=col)
                    
                    # 🔥 記錄 comparison_status 欄位位置
                    if header_value == 'comparison_status':
                        comparison_status_col = col
                    
                    if header_value == 'source_file':
                        # 設定表頭為紫底白字
                        header_cell.fill = purple_fill
                        header_cell.font = white_font
                        
                        # 處理內容 - 都使用黑色字體，無超連結
                        normal_font = Font(color="000000", underline=None)
                        for row in range(2, ws.max_row + 1):
                            cell = ws.cell(row=row, column=col)
                            cell.value = source_filename
                            cell.hyperlink = None
                            cell.font = normal_font
                            cell.style = 'Normal'
                    
                    elif header_value in ['gerrit_source_file', 'compare_source_file']:
                        # 🔥 修正表頭名稱（本地比較模式）
                        if is_local_comparison:
                            header_cell.value = 'compare_source_file'
                        
                        # 設定表頭顏色
                        if is_local_comparison:
                            header_cell.fill = purple_fill  # 本地比較：紫色
                        else:
                            header_cell.fill = green_fill   # Gerrit 比較：綠色
                        header_cell.font = white_font
                        
                        # 處理內容
                        normal_font = Font(color="000000", underline=None)
                        for row in range(2, ws.max_row + 1):
                            cell = ws.cell(row=row, column=col)
                            if is_local_comparison:
                                cell.value = target_filename
                                cell.hyperlink = None
                                cell.font = normal_font
                                cell.style = 'Normal'
                            # Gerrit 比較模式保持原有邏輯
                    
                    # 🔥 處理其他 gerrit_ 開頭的欄位（本地比較模式）
                    elif header_value.startswith('gerrit_') and is_local_comparison:
                        # 將 gerrit_ 替換為 compare_
                        new_header = header_value.replace('gerrit_', 'compare_')
                        header_cell.value = new_header
                        
                        # 根據欄位類型設定顏色
                        if new_header in ['compare_revision']:
                            header_cell.fill = PatternFill(start_color="C5504B", end_color="C5504B", fill_type="solid")  # 紅色
                        elif new_header.startswith('compare_'):
                            header_cell.fill = purple_fill  # 紫色（本地比較的目標檔案相關欄位）
                        else:
                            header_cell.fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")  # 藍色
                        
                        header_cell.font = white_font
                
                # 🔥 新增：重新設定行背景色
                if comparison_status_col:
                    self.logger.info(f"🎨 重新設定比較專案內容差異明細的行背景色（第 {comparison_status_col} 欄）")
                    self._apply_comparison_row_colors(ws, comparison_status_col)
                else:
                    self.logger.warning("⚠️ 找不到 comparison_status 欄位，無法設定行背景色")
        
        except Exception as e:
            self.logger.error(f"修正差異頁籤失敗: {str(e)}")

    def _apply_comparison_row_colors(self, worksheet, status_col: int):
        """套用比較狀態的行背景色（獨立方法）"""
        try:
            from openpyxl.styles import PatternFill
            
            self.logger.info(f"🎨 開始設定行背景色，comparison_status 在第 {status_col} 欄")
            
            # 🔥 狀態顏色配置
            status_colors = {
                '✔️ 相同': PatternFill(start_color="E8F5E8", end_color="E8F5E8", fill_type="solid"),      # 淺綠底
                '❌ 不同': PatternFill(start_color="FFE8E8", end_color="FFE8E8", fill_type="solid"),      # 淺紅底
                '➕ 新增': PatternFill(start_color="E8F0FF", end_color="E8F0FF", fill_type="solid"),      # 淺藍底
                '❓ 無此專案': PatternFill(start_color="FFE8CC", end_color="FFE8CC", fill_type="solid"),  # 淺橘底
                
                # 🔥 保留舊的狀態以防萬一
                '⚠️ 不同': PatternFill(start_color="FFE8E8", end_color="FFE8E8", fill_type="solid"),     # 淺紅底
                '🗑️ 刪除': PatternFill(start_color="FFE8CC", end_color="FFE8CC", fill_type="solid")      # 淺橘底
            }
            
            # 統計各種狀態的數量
            status_counts = {}
            applied_count = 0
            
            # 設定每一行的背景色
            for row_num in range(2, worksheet.max_row + 1):
                status_cell = worksheet.cell(row=row_num, column=status_col)
                status_value = str(status_cell.value) if status_cell.value else ''
                
                # 統計狀態數量
                status_counts[status_value] = status_counts.get(status_value, 0) + 1
                
                # 根據狀態設定整行背景色
                color_applied = False
                for status_pattern, fill_color in status_colors.items():
                    if status_pattern in status_value:
                        # 設定整行的背景色
                        for col in range(1, worksheet.max_column + 1):
                            worksheet.cell(row=row_num, column=col).fill = fill_color
                        applied_count += 1
                        color_applied = True
                        break
                
                # 🔥 除錯：記錄前5行的狀態
                if row_num <= 6:
                    color_info = "✅ 已套用" if color_applied else "❌ 未套用"
                    self.logger.debug(f"第 {row_num} 行: '{status_value}' -> {color_info}")
            
            # 🔥 統計報告
            total_rows = worksheet.max_row - 1
            self.logger.info(f"📊 行背景色設定完成:")
            self.logger.info(f"   總資料行數: {total_rows}")
            self.logger.info(f"   已套用顏色: {applied_count}")
            self.logger.info(f"   套用率: {applied_count/total_rows*100:.1f}%" if total_rows > 0 else "N/A")
            
            self.logger.info("📈 狀態統計:")
            for status, count in status_counts.items():
                color_info = "有顏色" if any(s in status for s in status_colors.keys()) else "無顏色"
                self.logger.info(f"   '{status}': {count} 個 ({color_info})")
            
            if applied_count == 0 and total_rows > 0:
                self.logger.warning("⚠️ 沒有任何行套用到背景色，請檢查狀態值格式")
                # 顯示實際的狀態值以便除錯
                sample_statuses = []
                for row in range(2, min(6, worksheet.max_row + 1)):
                    status = str(worksheet.cell(row=row, column=status_col).value) if worksheet.cell(row=row, column=status_col).value else ''
                    if status:
                        sample_statuses.append(f"'{status}'")
                self.logger.info(f"實際狀態值範例: {', '.join(sample_statuses)}")
            
        except Exception as e:
            self.logger.error(f"套用比較狀態行顏色失敗: {str(e)}")
            
    def _fix_manifest_sheets(self, workbook, is_local_comparison: bool, source_filename: str, 
                        target_filename: str, target_file_path: Optional[str]):
        """修正 manifest 相關頁籤 - 確保 gerrit 上的 manifest 使用原始檔案名稱"""
        try:
            from openpyxl.styles import PatternFill, Font
            
            purple_fill = PatternFill(start_color="8A2BE2", end_color="8A2BE2", fill_type="solid")
            white_font = Font(color="FFFFFF", bold=True)
            normal_font = Font(color="000000", underline=None)
            
            # 修正 "來源的 manifest" 頁籤
            if '來源的 manifest' in workbook.sheetnames:
                ws = workbook['來源的 manifest']
                
                for col in range(1, ws.max_column + 1):
                    header_value = str(ws.cell(row=1, column=col).value) if ws.cell(row=1, column=col).value else ''
                    if header_value == 'source_file':
                        header_cell = ws.cell(row=1, column=col)
                        header_cell.fill = purple_fill
                        header_cell.font = white_font
                        
                        for row in range(2, ws.max_row + 1):
                            cell = ws.cell(row=row, column=col)
                            cell.value = source_filename
                            cell.hyperlink = None
                            cell.font = normal_font
                            cell.style = 'Normal'
                        break
            
            # 🔥 修正 "gerrit 上的 manifest" 頁籤
            if 'gerrit 上的 manifest' in workbook.sheetnames:
                ws = workbook['gerrit 上的 manifest']
                
                if is_local_comparison:
                    ws.title = '目標的 manifest'
                
                for col in range(1, ws.max_column + 1):
                    header_value = str(ws.cell(row=1, column=col).value) if ws.cell(row=1, column=col).value else ''
                    if header_value == 'source_file':
                        header_cell = ws.cell(row=1, column=col)
                        header_cell.fill = purple_fill
                        header_cell.font = white_font
                        
                        if is_local_comparison:
                            # 本地比較模式：使用目標檔案名，確保無超連結
                            for row in range(2, ws.max_row + 1):
                                cell = ws.cell(row=row, column=col)
                                cell.value = target_filename
                                cell.hyperlink = None
                                cell.font = normal_font
                                cell.style = 'Normal'
                        else:
                            # 🔥 Gerrit 比較：修正檔案名稱邏輯
                            if target_file_path:
                                actual_target_file = os.path.basename(target_file_path)
                                # 🔥 關鍵修正：移除 _expand 後綴
                                if '_expand' in actual_target_file:
                                    original_name = actual_target_file
                                    actual_target_file = actual_target_file.replace('_expand', '')
                                    self.logger.info(f"🔧 後處理修正檔案名稱: {original_name} → {actual_target_file}")
                            else:
                                # 🔥 備用方案：如果沒有 target_file_path
                                actual_target_file = target_filename
                                self.logger.info(f"🔧 使用備用檔案名稱: {actual_target_file}")
                            
                            # 更新所有行
                            for row in range(2, ws.max_row + 1):
                                ws.cell(row=row, column=col).value = actual_target_file
                                if actual_target_file:
                                    clean_filename = actual_target_file.replace('gerrit_', '') if actual_target_file.startswith('gerrit_') else actual_target_file
                                    gerrit_url = self._generate_gerrit_manifest_link(clean_filename)
                                    self._add_hyperlink_to_cell(ws, row, col, gerrit_url, actual_target_file)
                        break
            
            # 修正其他頁籤...
            if '未轉換專案' in workbook.sheetnames:
                ws = workbook['未轉換專案']
                ws.title = '相同專案'
                
                # 修正表頭和內容
                for col in range(1, ws.max_column + 1):
                    header_value = str(ws.cell(row=1, column=col).value) if ws.cell(row=1, column=col).value else ''
                    if header_value == '保持的 Revision':
                        ws.cell(row=1, column=col).value = '相同的 Revision'
                
                # 修正內容
                for row in range(2, ws.max_row + 1):
                    for col in range(1, ws.max_column + 1):
                        cell_value = str(ws.cell(row=row, column=col).value) if ws.cell(row=row, column=col).value else ''
                        
                        if '符合跳過轉換條件或無需轉換' in cell_value:
                            ws.cell(row=row, column=col).value = '兩檔案內容相同'
                        elif 'Hash Revision' in cell_value:
                            ws.cell(row=row, column=col).value = '兩檔案內容相同 (Hash Revision)'
                        elif '需檢查是否來源端是否有問題' in cell_value:
                            ws.cell(row=row, column=col).value = '需檢查是否來源端有問題'
                
                # 移除 "需要紅字" 欄位
                needs_red_col = None
                for col in range(1, ws.max_column + 1):
                    if ws.cell(row=1, column=col).value == '需要紅字':
                        needs_red_col = col
                        break
                
                if needs_red_col:
                    ws.delete_cols(needs_red_col)
                
                # 設定原因欄位格式
                self._format_reason_column_for_comparison_mode(ws)
            
        except Exception as e:
            self.logger.error(f"修正 manifest 頁籤失敗: {str(e)}")

    def _format_reason_column_for_comparison_mode(self, worksheet):
        """設定比較模式下的原因欄位格式"""
        try:
            from openpyxl.styles import Font, PatternFill
            
            red_font = Font(color="FF0000", bold=True)
            red_fill = PatternFill(start_color="C5504B", end_color="C5504B", fill_type="solid")
            white_font = Font(color="FFFFFF", bold=True)
            
            # 找到原因欄位
            reason_col = None
            revision_col = None
            
            for col in range(1, worksheet.max_column + 1):
                header_value = str(worksheet.cell(row=1, column=col).value) if worksheet.cell(row=1, column=col).value else ''
                if header_value == '原因':
                    reason_col = col
                    # 設定表頭為紅底白字（參考其他頁籤的樣式）
                    header_cell = worksheet.cell(row=1, column=col)
                    header_cell.fill = red_fill
                    header_cell.font = white_font
                elif header_value == '相同的 Revision':
                    revision_col = col
            
            if not reason_col or not revision_col:
                return
            
            # 根據 revision 和原因內容設定紅字
            for row in range(2, worksheet.max_row + 1):
                revision_cell = worksheet.cell(row=row, column=revision_col)
                reason_cell = worksheet.cell(row=row, column=reason_col)
                
                revision_value = str(revision_cell.value) if revision_cell.value else ''
                reason_value = str(reason_cell.value) if reason_cell.value else ''
                
                # 如果有 revision 值且不是 hash，並且原因包含 "需檢查"，則設為紅字
                if revision_value and not self._is_revision_hash(revision_value) and "需檢查" in reason_value:
                    reason_cell.font = red_font
            
            self.logger.info("✅ 已設定比較模式下的原因欄位格式")
            
        except Exception as e:
            self.logger.error(f"設定原因欄位格式失敗: {str(e)}")

    def _update_summary_statistics(self, workbook, diff_analysis: Dict):
        """更新比較摘要頁籤的統計數據（安全版：根據比較類型使用不同邏輯）"""
        try:
            if '比較摘要' in workbook.sheetnames:
                ws = workbook['比較摘要']
                
                # 重新計算統計數據
                summary = diff_analysis.get('summary', {})
                differences = diff_analysis.get('differences', [])
                converted_projects = diff_analysis.get('converted_projects', [])
                
                # 🔥 判斷比較類型
                is_local_comparison = any('local_vs_local' in str(cell.value) for row in ws.iter_rows() for cell in row if cell.value)
                
                # 🔥 修正：根據比較類型使用不同的統計邏輯
                content_same_count = 0
                content_diff_count = 0
                revision_same_count = 0
                revision_diff_count = 0
                
                # 統計 1：從 differences 統計比較狀態（所有模式都一樣）
                for diff in differences:
                    comparison_status = diff.get('comparison_status', '')
                    
                    if '✔️ 相同' in comparison_status:
                        content_same_count += 1
                    else:
                        # 所有不是 "✔️ 相同" 的都算差異
                        content_diff_count += 1
                
                # 統計 2：版號差異統計（根據比較類型使用不同邏輯）
                if is_local_comparison:
                    # 🔥 [5] 本地檔案比較：保持原有邏輯
                    for proj in converted_projects:
                        original_rev = proj.get('original_revision', '')
                        converted_rev = proj.get('converted_revision', '')
                        
                        if original_rev == converted_rev:
                            revision_same_count += 1
                        else:
                            revision_diff_count += 1
                else:
                    # 🔥 [1]-[4] Gerrit 比較：使用修正後的邏輯
                    for proj in converted_projects:
                        original_rev = proj.get('original_revision', '')
                        converted_rev = proj.get('converted_revision', '')
                        
                        # 模擬 "Revision 是否相等" 的邏輯
                        if original_rev == converted_rev and original_rev and converted_rev:
                            revision_same_count += 1
                        else:
                            revision_diff_count += 1
                
                # 🔥 除錯輸出
                self.logger.info(f"📊 統計除錯:")
                self.logger.info(f"   比較類型: {'[5] 本地檔案比較' if is_local_comparison else '[1]-[4] Gerrit 比較'}")
                self.logger.info(f"   差異明細中的專案數: {len(differences)}")
                self.logger.info(f"   總專案數: {summary.get('converted_count', 0)}")
                self.logger.info(f"   內容相同數: {content_same_count}")
                self.logger.info(f"   內容差異數: {content_diff_count}")
                self.logger.info(f"   版號相同數: {revision_same_count}")
                self.logger.info(f"   版號差異數: {revision_diff_count}")
                
                # 找到統計相關欄位的位置並更新
                stats_mapping = {
                    '📊 總專案數': summary.get('converted_count', 0),
                    '🎯 目標檔案專案數': summary.get('target_count', 0),
                    '❌ 與現行版本版號差異數': revision_diff_count,
                    '✔️ 與現行版本版號相同數': revision_same_count,
                    '❌ 比較現行版本內容差異數': content_diff_count,
                    '✔️ 比較現行版本內容相同數': content_same_count
                }
                
                for col in range(1, ws.max_column + 1):
                    header_value = str(ws.cell(row=1, column=col).value) if ws.cell(row=1, column=col).value else ''
                    
                    if header_value in stats_mapping:
                        ws.cell(row=2, column=col).value = stats_mapping[header_value]
                        self.logger.debug(f"更新統計: {header_value} = {stats_mapping[header_value]}")
                
                self.logger.info("✅ 已更新比較摘要頁籤的統計數據（分類型處理）")
        
        except Exception as e:
            self.logger.error(f"更新統計數據失敗: {str(e)}")

    def _show_comparison_results(self, comparison_type: str, diff_analysis: Dict):
        """顯示比較結果統計"""
        self.logger.info(f"\n📈 {comparison_type} 比較結果統計:")
        self.logger.info(f"  🔧 使用邏輯: 完全獨立版本（不依賴 feature_three.py）")
        self.logger.info(f"  📋 Excel 格式: 比較模式優化版本")
        self.logger.info(f"  📄 處理模式: 純比對（不執行轉換）")
        self.logger.info(f"  📊 差異分析: 完整比較邏輯")
        self.logger.info(f"  📝 Excel 生成: 完整格式化和動態公式")
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
    parser = argparse.ArgumentParser(description='Manifest 比較工具 - 完全獨立版本')
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
        print(f"🔧 使用邏輯: 完全獨立版本（不依賴 feature_three.py）")
        print(f"📋 Excel 格式: 與原始版本完全一致")
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