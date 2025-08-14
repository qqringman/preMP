"""
功能三：Manifest 轉換工具 - 微調版本
從 Gerrit 下載源檔案，進行 revision 轉換，並與目標檔案比較差異
微調：確保 Gerrit 檔案正確保存，增加 revision 比較資訊，標頭格式化
修正：確保展開檔案正確保存到 output 資料夾
修改：改進特殊項目處理邏輯，通用檢查master和premp是否相同
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
                excel_filename: Optional[str] = None, push_to_gerrit: bool = False,
                rddb_number: Optional[str] = None, chip_status: Optional[Dict[str, str]] = None) -> bool:
        """
        處理功能三的主要邏輯
        
        Args:
            overwrite_type: 轉換類型
            output_folder: 輸出資料夾
            excel_filename: 自定義 Excel 檔名
            push_to_gerrit: 是否推送到 Gerrit
            rddb_number: RDDB 號碼（可選，預設使用 config.py 的設定）
            chip_status: 晶片狀態字典（可選，如 {'Mac7p': 'Y', 'Merlin7': 'Y'}）
            
        Returns:
            是否處理成功
        """
        # 將 rddb_number 儲存為實例變數，供後續使用
        self.rddb_number = rddb_number
        self.chip_status = chip_status
        
        try:
            self.logger.info("=== 開始執行功能三：Manifest 轉換工具 (微調版本 + include 展開) ===")
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
            
            # 🆕 步驟 1.6: 檢查是否有 include 標籤，如果有則展開
            expanded_content = None
            expanded_file_path = None
            use_expanded = False
            
            if source_content and self._has_include_tags(source_content):
                self.logger.info("🔍 檢測到 include 標籤，準備展開 manifest...")
                expanded_content, expanded_file_path = self._expand_manifest_with_repo_fixed(
                    overwrite_type, output_folder
                )
                if expanded_content and expanded_file_path:
                    use_expanded = True
                    self.logger.info("✅ Manifest 展開成功，將使用展開後的檔案進行轉換")
                    self.logger.info(f"✅ 展開檔案已保存到: {expanded_file_path}")
                    
                    # 🆕 驗證展開檔案是否真的存在
                    if os.path.exists(expanded_file_path):
                        file_size = os.path.getsize(expanded_file_path)
                        self.logger.info(f"✅ 展開檔案驗證成功: {os.path.basename(expanded_file_path)} ({file_size} bytes)")
                    else:
                        self.logger.error(f"❌ 展開檔案不存在: {expanded_file_path}")
                        use_expanded = False
                else:
                    self.logger.warning("⚠️ Manifest 展開失敗，將使用原始檔案")
            else:
                self.logger.info("ℹ️ 未檢測到 include 標籤，使用原始檔案")
            
            # 決定要使用的內容進行轉換
            content_for_conversion = expanded_content if use_expanded else source_content
            
            # 步驟 2: 進行 revision 轉換
            if content_for_conversion:
                converted_content, conversion_info = self._convert_revisions(content_for_conversion, overwrite_type)
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
            
            # 步驟 7: 產生 Excel 報告（包含展開檔案資訊）
            excel_file = self._generate_excel_report_safe(
                overwrite_type, source_file_path, output_file_path, target_file_path, 
                diff_analysis, output_folder, excel_filename, source_download_success, 
                target_download_success, push_result, expanded_file_path, use_expanded
            )
            
            # 最終檔案檢查和報告
            self._final_file_report_complete(
                output_folder, source_file_path, output_file_path, target_file_path, 
                excel_file, source_download_success, target_download_success, expanded_file_path
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

    def _has_include_tags(self, xml_content: str) -> bool:
        """
        檢查 XML 內容是否包含 include 標籤
        
        Args:
            xml_content: XML 檔案內容
            
        Returns:
            是否包含 include 標籤
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
        使用 repo 命令展開包含 include 的 manifest - 修正版本，同時保存到臨時目錄和輸出目錄
        
        Args:
            overwrite_type: 轉換類型
            output_folder: 輸出資料夾
            
        Returns:
            (expanded_content, expanded_file_path) 或 (None, None) 如果失敗
        """
        import subprocess
        import tempfile
        import shutil
        
        try:
            # 取得相關參數
            source_filename = self.source_files[overwrite_type]
            repo_url = "ssh://mm2sd.rtkbf.com:29418/realtek/android/manifest"
            branch = "realtek/android-14/master"
            
            # 🆕 生成展開檔案名稱 - 使用絕對路徑解決臨時目錄問題
            expanded_filename = f"gerrit_{source_filename.replace('.xml', '_expand.xml')}"
            # 🔥 關鍵修正：轉換為絕對路徑，避免在臨時目錄中誤保存
            final_expanded_path = os.path.abspath(os.path.join(output_folder, expanded_filename))
            
            self.logger.info(f"🎯 準備展開 manifest...")
            self.logger.info(f"🎯 源檔案: {source_filename}")
            self.logger.info(f"🎯 展開檔案名: {expanded_filename}")
            self.logger.info(f"🎯 目標絕對路徑: {final_expanded_path}")
            
            # 🆕 在切換目錄前確保輸出資料夾存在
            utils.ensure_dir(output_folder)
            abs_output_folder = os.path.abspath(output_folder)
            self.logger.info(f"🎯 輸出資料夾絕對路徑: {abs_output_folder}")
            
            # 🆕 檢查 repo 命令是否可用
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
                self.logger.error("安裝方法: curl https://storage.googleapis.com/git-repo-downloads/repo > ~/.local/bin/repo && chmod a+x ~/.local/bin/repo")
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
                    timeout=120  # 2分鐘超時
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
                
                # 🆕 檢查 .repo 目錄是否存在
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
                
                # 🆕 檢查展開內容的基本特徵
                project_count = expanded_content.count('<project ')
                include_count = expanded_content.count('<include ')
                self.logger.info(f"🔍 展開內容分析:")
                self.logger.info(f"   - Project 標籤數量: {project_count}")
                self.logger.info(f"   - Include 標籤數量: {include_count}")
                
                # 🆕 步驟 3A: 在臨時目錄保存一份展開檔案
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
                
                # 🆕 步驟 3B: 同時複製到輸出資料夾（使用絕對路徑）
                self.logger.info(f"📝 複製展開檔案到輸出資料夾...")
                self.logger.info(f"📝 目標絕對路徑: {final_expanded_path}")
                self.logger.info(f"📝 當前工作目錄: {os.getcwd()}")
                
                # 🔥 關鍵：確保目標資料夾存在（使用絕對路徑）
                target_dir = os.path.dirname(final_expanded_path)
                utils.ensure_dir(target_dir)
                self.logger.info(f"✅ 目標資料夾確認存在: {target_dir}")
                
                # 複製檔案到輸出目錄（使用絕對路徑）
                try:
                    shutil.copy2(temp_expanded_path, final_expanded_path)
                    self.logger.info(f"✅ 檔案複製完成（臨時→輸出）")
                except Exception as copy_error:
                    self.logger.error(f"❌ 檔案複製失敗: {str(copy_error)}")
                    self.logger.error(f"❌ 源路徑: {temp_expanded_path}")
                    self.logger.error(f"❌ 目標路徑: {final_expanded_path}")
                    return None, None
                
                # 🆕 步驟 4: 驗證兩個位置的檔案都存在
                self.logger.info(f"🔍 驗證檔案保存狀態...")
                
                # 驗證臨時檔案
                if os.path.exists(temp_expanded_path):
                    temp_size = os.path.getsize(temp_expanded_path)
                    self.logger.info(f"✅ 臨時檔案存在: {temp_expanded_path} ({temp_size} bytes)")
                else:
                    self.logger.error(f"❌ 臨時檔案不存在: {temp_expanded_path}")
                
                # 驗證輸出檔案
                if os.path.exists(final_expanded_path):
                    file_size = os.path.getsize(final_expanded_path)
                    self.logger.info(f"✅ 輸出檔案存在: {final_expanded_path} ({file_size} bytes)")
                    
                    # 🆕 驗證檔案內容一致性
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
                    
                    # 🎉 成功返回
                    self.logger.info(f"🎉 展開檔案處理完成!")
                    self.logger.info(f"   📁 臨時位置: {temp_expanded_path}")
                    self.logger.info(f"   📁 輸出位置: {final_expanded_path}")
                    self.logger.info(f"   📊 檔案大小: {file_size} bytes")
                    self.logger.info(f"   📊 專案數量: {project_count}")
                    
                    return expanded_content, final_expanded_path
                else:
                    self.logger.error(f"❌ 輸出檔案不存在: {final_expanded_path}")
                    
                    # 🆕 檢查輸出目錄狀態
                    if os.path.exists(abs_output_folder):
                        files_in_output = os.listdir(abs_output_folder)
                        self.logger.error(f"❌ 輸出目錄內容: {files_in_output}")
                    else:
                        self.logger.error(f"❌ 輸出目錄不存在: {abs_output_folder}")
                    
                    return None, None
                
            finally:
                # 🆕 在清理前顯示臨時目錄內容
                self.logger.info(f"🔍 清理前臨時目錄內容:")
                try:
                    temp_files = os.listdir(temp_work_dir)
                    for filename in temp_files[:10]:  # 只顯示前10個檔案
                        filepath = os.path.join(temp_work_dir, filename)
                        if os.path.isfile(filepath):
                            filesize = os.path.getsize(filepath)
                            self.logger.info(f"   📄 {filename} ({filesize} bytes)")
                        else:
                            self.logger.info(f"   📁 {filename} (目錄)")
                except Exception as e:
                    self.logger.warning(f"⚠️ 無法列出臨時目錄內容: {str(e)}")
                
                # 恢復原始工作目錄
                os.chdir(original_cwd)
                self.logger.info(f"📂 恢復原始工作目錄: {original_cwd}")
                
                # 🆕 延遲清理臨時目錄（可選：保留一段時間供調試）
                # 注意：這裡我們還是清理，但添加了更多日誌
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
    
    # 🔥 完全重寫 _convert_revisions 方法，移除有問題的正規表達式
    def _convert_revisions(self, xml_content: str, overwrite_type: str) -> Tuple[str, List[Dict]]:
        """
        根據轉換類型進行 revision 轉換 - 修正正則表達式錯誤版本
        🔥 只轉換原本就有 revision 的專案，不自動插入 default revision
        🔥 確保所有專案都被記錄到 conversion_info 中，避免誤判刪除
        """
        try:
            self.logger.info(f"開始進行 revision 轉換: {overwrite_type}")
            self.logger.info("使用字串替換方式，保留所有原始格式（包含註解、空格等）")
            self.logger.info("🎯 轉換策略: 只轉換原本就有 revision 的專案")
            self.logger.info("🎯 記錄策略: 所有專案都記錄到 conversion_info 中")
            
            # 先解析 XML 取得 default 資訊
            temp_root = ET.fromstring(xml_content)
            
            # 讀取 default 標籤的 remote 和 revision 屬性
            default_remote = ''
            default_revision = ''
            default_element = temp_root.find('default')
            if default_element is not None:
                default_remote = default_element.get('remote', '')
                default_revision = default_element.get('revision', '')
                self.logger.info(f"找到預設 remote: {default_remote}, revision: {default_revision}")
            
            # 儲存為實例變數供其他方法使用
            self.default_remote = default_remote
            self.default_revision = default_revision
            
            conversion_info = []
            conversion_count = 0
            skipped_no_revision = 0  # 🔥 統計沒有 revision 而跳過的專案
            hash_revision_count = 0
            branch_revision_count = 0
            upstream_used_count = 0
            
            # 建立轉換後的內容（從原始字串開始）
            converted_content = xml_content
            
            # 遍歷所有 project 元素以記錄轉換資訊
            for project in temp_root.findall('project'):
                project_name = project.get('name', '')
                project_remote = project.get('remote', '') or default_remote
                original_revision = project.get('revision', '')  # 🔥 只使用原始的 revision
                upstream = project.get('upstream', '')
                
                # 🔥 添加調試：記錄所有處理的專案
                composite_key = f"{project_name}|{project.get('path', '')}"
                self.logger.debug(f"處理專案: {composite_key}, 原始 revision: '{original_revision}'")
                
                # 🔥 如果沒有 revision，記錄但跳過轉換
                if not original_revision:
                    skipped_no_revision += 1
                    self.logger.debug(f"跳過沒有 revision 的專案: {project_name}")
                    
                    # 🔥 重要：即使沒有 revision，也要加入 conversion_info
                    conversion_info.append({
                        'name': project_name,
                        'path': project.get('path', ''),
                        'original_revision': '',
                        'effective_revision': '',
                        'converted_revision': '',
                        'upstream': upstream,
                        'dest-branch': project.get('dest-branch', ''),
                        'groups': project.get('groups', ''),
                        'clone-depth': project.get('clone-depth', ''),
                        'remote': project.get('remote', ''),
                        'original_remote': project.get('remote', ''),
                        'changed': False,
                        'used_default_revision': False,
                        'used_upstream_for_conversion': False
                    })
                    continue
                
                # 使用新邏輯取得用於轉換的有效 revision
                effective_revision = self._get_effective_revision_for_conversion(project)
                
                # 統計 revision 類型
                if self._is_revision_hash(original_revision):
                    hash_revision_count += 1
                    if upstream:
                        upstream_used_count += 1
                elif original_revision:
                    branch_revision_count += 1
                
                if not effective_revision:
                    self.logger.debug(f"專案 {project_name} 沒有有效的轉換 revision，但仍記錄")
                    # 🔥 沒有有效 revision 也要記錄
                    conversion_info.append({
                        'name': project_name,
                        'path': project.get('path', ''),
                        'original_revision': original_revision,
                        'effective_revision': '',
                        'converted_revision': original_revision,  # 保持原值
                        'upstream': upstream,
                        'dest-branch': project.get('dest-branch', ''),
                        'groups': project.get('groups', ''),
                        'clone-depth': project.get('clone-depth', ''),
                        'remote': project.get('remote', ''),
                        'original_remote': project.get('remote', ''),
                        'changed': False,
                        'used_default_revision': False,
                        'used_upstream_for_conversion': False
                    })
                    continue
                
                old_revision = effective_revision
                new_revision = self._convert_single_revision(effective_revision, overwrite_type)
                
                # 🔥 增強除錯 - MP to MPBackup 專用
                if overwrite_type == 'mp_to_mpbackup':
                    self.logger.debug(f"🔍 MP to MPBackup 轉換除錯:")
                    self.logger.debug(f"  專案: {project_name}")
                    self.logger.debug(f"  原始 revision: {original_revision}")
                    self.logger.debug(f"  有效 revision: {effective_revision}")
                    self.logger.debug(f"  轉換結果: {new_revision}")
                    self.logger.debug(f"  是否改變: {new_revision != old_revision}")
                
                # 🔥 重要：所有專案都要記錄到 conversion_info 中
                conversion_info.append({
                    'name': project_name,
                    'path': project.get('path', ''),
                    'original_revision': original_revision,
                    'effective_revision': effective_revision,
                    'converted_revision': new_revision,
                    'upstream': upstream,
                    'dest-branch': project.get('dest-branch', ''),
                    'groups': project.get('groups', ''),
                    'clone-depth': project.get('clone-depth', ''),
                    'remote': project.get('remote', ''),
                    'original_remote': project.get('remote', ''),  # 🔥 保存原始 remote
                    'changed': new_revision != old_revision,
                    'used_default_revision': False,  # 🔥 不再插入 default revision
                    'used_upstream_for_conversion': self._is_revision_hash(original_revision) and upstream
                })
                
                # 如果需要轉換，在字串中直接替換
                if new_revision != old_revision:
                    # 🔥 使用安全的替換方法
                    replacement_success = self._safe_replace_revision_in_xml(
                        converted_content, project_name, old_revision, new_revision
                    )
                    
                    if replacement_success:
                        converted_content = replacement_success
                        conversion_count += 1
                        self.logger.debug(f"字串替換成功: {project_name} - {old_revision} → {new_revision}")
                        
                        # 🔥 MP to MPBackup 特別記錄
                        if overwrite_type == 'mp_to_mpbackup':
                            self.logger.info(f"✅ MP to MPBackup 轉換成功: {project_name}")
                            self.logger.info(f"  {old_revision} → {new_revision}")
            
            self.logger.info(f"revision 轉換完成，共轉換 {conversion_count} 個專案")
            self.logger.info(f"📊 處理統計:")
            self.logger.info(f"  - ⭐ 跳過沒有 revision 的專案: {skipped_no_revision} 個")
            self.logger.info(f"  - 🔸 Hash revision: {hash_revision_count} 個")
            self.logger.info(f"  - 🔹 Branch revision: {branch_revision_count} 個")
            self.logger.info(f"  - ⬆️ 使用 upstream 進行轉換: {upstream_used_count} 個")
            self.logger.info(f"  - 📋 總記錄專案數: {len(conversion_info)} 個")
            self.logger.info("✅ 保留了所有原始格式：XML 宣告、註解、空格、換行等")
            
            # 🔥 特別檢查 MP to MPBackup 轉換效果
            if overwrite_type == 'mp_to_mpbackup':
                self._verify_mp_to_mpbackup_conversion(converted_content, xml_content)
            
            return converted_content, conversion_info
            
        except Exception as e:
            self.logger.error(f"revision 轉換失敗: {str(e)}")
            import traceback
            self.logger.error(f"錯誤詳情: {traceback.format_exc()}")
            return xml_content, []

    def _verify_mp_to_mpbackup_conversion(self, converted_content: str, original_content: str):
        """驗證 MP to MPBackup 轉換是否成功"""
        try:
            # 統計轉換前後的 revision 差異
            original_wave_count = original_content.count('mp.google-refplus.wave')
            original_backup_count = original_content.count('mp.google-refplus.wave.backup')
            
            converted_wave_count = converted_content.count('mp.google-refplus.wave')
            converted_backup_count = converted_content.count('mp.google-refplus.wave.backup')
            
            # self.logger.info(f"🔍 MP to MPBackup 轉換驗證:")
            # self.logger.info(f"  轉換前: wave={original_wave_count}, backup={original_backup_count}")
            # self.logger.info(f"  轉換後: wave={converted_wave_count}, backup={converted_backup_count}")
            
            # 計算實際的變化
            # backup_increase = converted_backup_count - original_backup_count
            # wave_decrease = original_wave_count - converted_wave_count
            
            # if backup_increase > 0:
            #     self.logger.info(f"✅ 轉換成功: 新增了 {backup_increase} 個 backup")
            #     self.logger.info(f"✅ 減少了 {wave_decrease} 個 wave")
            # elif original_backup_count > 0 and original_wave_count == original_backup_count:
            #     self.logger.info(f"💡 所有 revision 可能已經是 backup 格式")
            # else:
            #     self.logger.warning(f"❌ 轉換可能失敗: backup 數量沒有增加")
                
        except Exception as e:
            self.logger.error(f"驗證 MP to MPBackup 轉換時發生錯誤: {str(e)}")
            
    def _safe_insert_revision(self, xml_content: str, project_name: str, revision: str) -> str:
        """
        安全地為專案插入 revision 屬性
        """
        try:
            lines = xml_content.split('\n')
            
            for i, line in enumerate(lines):
                if f'name="{project_name}"' in line and 'revision=' not in line:
                    # 找到沒有 revision 的專案行，插入 revision
                    if line.strip().endswith('/>'):
                        # 單行標籤
                        new_line = line.replace('/>', f' revision="{revision}"/>')
                        lines[i] = new_line
                        self.logger.debug(f"✅ 插入 revision: {project_name}")
                        break
                    elif line.strip().endswith('>'):
                        # 多行標籤的開始
                        new_line = line.replace('>', f' revision="{revision}">')
                        lines[i] = new_line
                        self.logger.debug(f"✅ 插入 revision (多行): {project_name}")
                        break
            
            return '\n'.join(lines)
            
        except Exception as e:
            self.logger.error(f"插入 revision 失敗: {str(e)}")
            return xml_content
            
    def _safe_replace_revision_in_xml(self, xml_content: str, project_name: str, 
                                 old_revision: str, new_revision: str) -> str:
        """
        安全的 XML 字串替換 - 避免有問題的正規表達式
        """
        try:
            # 🔥 使用簡單的字串搜尋和替換，避免複雜的正規表達式
            lines = xml_content.split('\n')
            modified = False
            
            for i, line in enumerate(lines):
                # 檢查這一行是否包含目標專案
                if f'name="{project_name}"' in line and 'revision=' in line:
                    # 找到目標行，進行替換
                    if f'revision="{old_revision}"' in line:
                        lines[i] = line.replace(f'revision="{old_revision}"', f'revision="{new_revision}"')
                        modified = True
                        self.logger.debug(f"✅ 替換成功: {project_name}")
                        break
                    elif f"revision='{old_revision}'" in line:
                        lines[i] = line.replace(f"revision='{old_revision}'", f"revision='{new_revision}'")
                        modified = True
                        self.logger.debug(f"✅ 替換成功 (單引號): {project_name}")
                        break
            
            if modified:
                return '\n'.join(lines)
            else:
                self.logger.warning(f"❌ 未找到匹配的替換: {project_name} - {old_revision}")
                return xml_content
                
        except Exception as e:
            self.logger.error(f"安全替換失敗: {str(e)}")
            return xml_content
            
    def _replace_revision_in_xml(self, xml_content: str, project_name: str, 
                            old_revision: str, new_revision: str) -> bool:
        """
        在 XML 字串中替換指定專案的 revision
        
        Args:
            xml_content: XML 內容
            project_name: 專案名稱
            old_revision: 舊的 revision
            new_revision: 新的 revision
            
        Returns:
            是否替換成功
        """
        import re
        
        # 轉義專案名稱中的特殊字符
        escaped_project_name = re.escape(project_name)
        escaped_old_revision = re.escape(old_revision)
        
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
            if re.search(pattern, xml_content):
                xml_content = re.sub(pattern, rf'\1{new_revision}\3', xml_content)
                self.logger.debug(f"字串替換成功 (模式{i+1}): {project_name} - {old_revision} → {new_revision}")
                return True
        
        self.logger.warning(f"無法找到匹配的專案進行替換: {project_name}")
        return False
            
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
        """
        master → premp 轉換規則 - 與 test_manifest_conversion.py 完全同步
        修改：確保與測試模組使用完全相同的轉換邏輯
        
        Args:
            revision: 原始 revision
            
        Returns:
            轉換後的 revision
        """
        if not revision:
            return revision
        
        original_revision = revision.strip()
        
        # 🆕 跳過 Google 開頭的項目（如 google/u-tv-keystone-rtk-refplus-wave4-release）
        if original_revision.startswith('google/'):
            self.logger.debug(f"跳過 Google 項目: {original_revision}")
            return original_revision
        
        # 🆕 跳過特殊項目（與測試模組保持一致）
        if self._should_skip_revision_conversion(original_revision):
            return original_revision
        
        # 🆕 精確匹配轉換規則（優先級最高）- 與測試模組完全同步
        exact_mappings = {
            # 基本 master 分支轉換
            'realtek/master': 'realtek/android-14/premp.google-refplus',
            'realtek/gaia': 'realtek/android-14/premp.google-refplus',
            'realtek/gki/master': 'realtek/android-14/premp.google-refplus',
            
            # Android 14 主要分支
            'realtek/android-14/master': 'realtek/android-14/premp.google-refplus',
            
            # 🔥 修正：Linux kernel android master 分支轉換（保留 linux 路徑）
            'realtek/linux-5.15/android-14/master': 'realtek/linux-5.15/android-14/premp.google-refplus',
            'realtek/linux-4.14/android-14/master': 'realtek/linux-4.14/android-14/premp.google-refplus',
            'realtek/linux-5.4/android-14/master': 'realtek/linux-5.4/android-14/premp.google-refplus',
            'realtek/linux-5.10/android-14/master': 'realtek/linux-5.10/android-14/premp.google-refplus',
            'realtek/linux-6.1/android-14/master': 'realtek/linux-6.1/android-14/premp.google-refplus',
            
            # 🔥 修正：直接的 mp.google-refplus 轉換（需要加上 android-14）
            'realtek/mp.google-refplus': 'realtek/android-14/premp.google-refplus',
            
            # 其他常見的轉換
            'realtek/android-14/mp.google-refplus': 'realtek/android-14/premp.google-refplus',
        }
        
        # 檢查精確匹配
        if original_revision in exact_mappings:
            self.logger.debug(f"精確匹配轉換: {original_revision} → {exact_mappings[original_revision]}")
            return exact_mappings[original_revision]
        
        # 🆕 模式匹配轉換規則（使用正規表達式）- 與測試模組完全同步
        import re
        
        # 規則 1: mp.google-refplus.upgrade-11.rtdXXXX → premp.google-refplus.upgrade-11.rtdXXXX
        pattern1 = r'realtek/android-(\d+)/mp\.google-refplus\.upgrade-(\d+)\.(rtd\w+)'
        match1 = re.match(pattern1, original_revision)
        if match1:
            android_ver, upgrade_ver, rtd_chip = match1.groups()
            result = f'realtek/android-{android_ver}/premp.google-refplus.upgrade-{upgrade_ver}.{rtd_chip}'
            self.logger.debug(f"模式1轉換: {original_revision} → {result}")
            return result
        
        # 規則 2: mp.google-refplus.upgrade-11 → premp.google-refplus.upgrade-11
        pattern2 = r'realtek/android-(\d+)/mp\.google-refplus\.upgrade-(\d+)$'
        match2 = re.match(pattern2, original_revision)
        if match2:
            android_ver, upgrade_ver = match2.groups()
            result = f'realtek/android-{android_ver}/premp.google-refplus.upgrade-{upgrade_ver}'
            self.logger.debug(f"模式2轉換: {original_revision} → {result}")
            return result
        
        # 🔥 規則 3: linux-X.X/master → linux-X.X/android-14/premp.google-refplus（修正版）
        pattern3 = r'realtek/linux-([\d.]+)/master$'
        match3 = re.match(pattern3, original_revision)
        if match3:
            linux_ver = match3.group(1)
            result = f'realtek/linux-{linux_ver}/android-14/premp.google-refplus'
            self.logger.debug(f"模式3轉換（Linux master）: {original_revision} → {result}")
            return result
        
        # 🔥 規則 4: linux-X.X/android-Y/master → linux-X.X/android-Y/premp.google-refplus（修正版）
        pattern4 = r'realtek/linux-([\d.]+)/android-(\d+)/master$'
        match4 = re.match(pattern4, original_revision)
        if match4:
            linux_ver, android_ver = match4.groups()
            result = f'realtek/linux-{linux_ver}/android-{android_ver}/premp.google-refplus'
            self.logger.debug(f"模式4轉換（Linux Android master）: {original_revision} → {result}")
            return result
        
        # 規則 5: linux-X.X/android-Y/mp.google-refplus → linux-X.X/android-Y/premp.google-refplus
        pattern5 = r'realtek/linux-([\d.]+)/android-(\d+)/mp\.google-refplus$'
        match5 = re.match(pattern5, original_revision)
        if match5:
            linux_ver, android_ver = match5.groups()
            result = f'realtek/linux-{linux_ver}/android-{android_ver}/premp.google-refplus'
            self.logger.debug(f"模式5轉換: {original_revision} → {result}")
            return result
        
        # 規則 6: linux-X.X/android-Y/mp.google-refplus.rtdXXXX → linux-X.X/android-Y/premp.google-refplus.rtdXXXX
        pattern6 = r'realtek/linux-([\d.]+)/android-(\d+)/mp\.google-refplus\.(rtd\w+)'
        match6 = re.match(pattern6, original_revision)
        if match6:
            linux_ver, android_ver, rtd_chip = match6.groups()
            result = f'realtek/linux-{linux_ver}/android-{android_ver}/premp.google-refplus.{rtd_chip}'
            self.logger.debug(f"模式6轉換: {original_revision} → {result}")
            return result
        
        # 規則 7: android-Y/mp.google-refplus → android-Y/premp.google-refplus
        pattern7 = r'realtek/android-(\d+)/mp\.google-refplus$'
        match7 = re.match(pattern7, original_revision)
        if match7:
            android_ver = match7.group(1)
            result = f'realtek/android-{android_ver}/premp.google-refplus'
            self.logger.debug(f"模式7轉換: {original_revision} → {result}")
            return result
        
        # 規則 8: android-Y/mp.google-refplus.rtdXXXX → android-Y/premp.google-refplus.rtdXXXX
        pattern8 = r'realtek/android-(\d+)/mp\.google-refplus\.(rtd\w+)'
        match8 = re.match(pattern8, original_revision)
        if match8:
            android_ver, rtd_chip = match8.groups()
            result = f'realtek/android-{android_ver}/premp.google-refplus.{rtd_chip}'
            self.logger.debug(f"模式8轉換: {original_revision} → {result}")
            return result
        
        # 規則 9: 晶片特定的 master 分支 → premp.google-refplus.rtdXXXX
        chip_mappings = {
            'mac7p': 'rtd2851a',
            'mac8q': 'rtd2851f', 
            'mac9p': 'rtd2895p',
            'merlin7': 'rtd6748',
            'merlin8': 'rtd2885p',
            'merlin8p': 'rtd2885q',
            'merlin9': 'rtd2875q',
        }
        
        for chip, rtd_model in chip_mappings.items():
            if f'realtek/{chip}/master' == original_revision:
                result = f'realtek/android-14/premp.google-refplus.{rtd_model}'
                self.logger.debug(f"晶片轉換: {original_revision} → {result}")
                return result
        
        # 規則 10: v3.16 版本轉換
        pattern10 = r'realtek/v3\.16/mp\.google-refplus$'
        if re.match(pattern10, original_revision):
            result = 'realtek/v3.16/premp.google-refplus'
            self.logger.debug(f"v3.16轉換: {original_revision} → {result}")
            return result
        
        # 🆕 如果沒有匹配的規則，根據關鍵字進行智能轉換
        smart_result = self._smart_conversion_fallback(original_revision)
        self.logger.debug(f"智能轉換: {original_revision} → {smart_result}")
        return smart_result

    def _should_skip_revision_conversion(self, revision: str) -> bool:
        """
        判斷是否應該跳過 revision 轉換 - 與測試模組完全同步
        
        Args:
            revision: 原始 revision
            
        Returns:
            是否應該跳過轉換
        """
        if not revision:
            return True
        
        # 🆕 跳過 Google 開頭的項目
        if revision.startswith('google/'):
            return True
        
        # 跳過 refs/tags/
        if revision.startswith('refs/tags/'):
            return True
        
        return False

    def _smart_conversion_fallback(self, revision: str) -> str:
        """
        智能轉換備案 - 當沒有精確規則時使用 - 與測試模組完全同步
        
        Args:
            revision: 原始 revision
            
        Returns:
            轉換後的 revision
        """
        # 如果包含 mp.google-refplus，嘗試替換為 premp.google-refplus
        if 'mp.google-refplus' in revision:
            # 保留原始路徑，只替換關鍵字
            result = revision.replace('mp.google-refplus', 'premp.google-refplus')
            self.logger.debug(f"智能替換 mp→premp: {revision} → {result}")
            return result
        
        # 如果是 master 但沒有匹配到特定規則，使用預設轉換
        if '/master' in revision and 'realtek/' in revision:
            # 提取 android 版本（如果有）
            import re
            android_match = re.search(r'android-(\d+)', revision)
            if android_match:
                android_ver = android_match.group(1)
                result = f'realtek/android-{android_ver}/premp.google-refplus'
                self.logger.debug(f"智能Android版本轉換: {revision} → {result}")
                return result
            else:
                result = 'realtek/android-14/premp.google-refplus'
                self.logger.debug(f"智能預設轉換: {revision} → {result}")
                return result
        
        # 如果完全沒有匹配，返回預設值
        result = 'realtek/android-14/premp.google-refplus'
        self.logger.debug(f"備案預設轉換: {revision} → {result}")
        return result
            
    def _convert_premp_to_mp(self, revision: str) -> str:
        """premp → mp 轉換規則"""
        # 將 premp.google-refplus 關鍵字替換為 mp.google-refplus.wave
        return revision.replace('premp.google-refplus', 'mp.google-refplus.wave')
    
    def _convert_mp_to_mpbackup(self, revision: str) -> str:
        """mp → mpbackup 轉換規則 - 修正正規表達式錯誤"""
        if not revision:
            return revision
        
        original_revision = revision.strip()
        
        # 記錄轉換前的狀態
        self.logger.debug(f"MP to MPBackup 轉換輸入: {original_revision}")
        
        # 檢查是否已經是 backup 格式
        if 'mp.google-refplus.wave.backup' in original_revision:
            self.logger.debug(f"已經是 backup 格式，不需轉換: {original_revision}")
            return original_revision
        
        # 🔥 主要轉換邏輯 - 簡化版，避免複雜正規表達式
        if 'mp.google-refplus.wave' in original_revision and 'backup' not in original_revision:
            result = original_revision.replace('mp.google-refplus.wave', 'mp.google-refplus.wave.backup')
            self.logger.debug(f"標準轉換: {original_revision} → {result}")
            return result
        
        # 🔥 處理以 .wave 結尾但沒有 backup 的情況
        if original_revision.endswith('.wave') and 'mp.google-refplus' in original_revision and 'backup' not in original_revision:
            result = original_revision + '.backup'
            self.logger.debug(f"後綴轉換: {original_revision} → {result}")
            return result
        
        # 🔥 處理包含 wave 但格式特殊的情況 - 使用安全的字串操作
        if 'mp.google-refplus' in original_revision and 'wave' in original_revision and 'backup' not in original_revision:
            # 找到 wave 的位置，在後面加 .backup
            wave_index = original_revision.find('wave')
            if wave_index != -1:
                # 檢查 wave 後面是否直接結束或跟著其他字符
                after_wave = original_revision[wave_index + 4:]  # wave 有4個字符
                if not after_wave or after_wave.startswith('.') or after_wave.startswith('/'):
                    # 在 wave 後面插入 .backup
                    result = original_revision[:wave_index + 4] + '.backup' + after_wave
                    self.logger.debug(f"插入轉換: {original_revision} → {result}")
                    return result
        
        # 如果沒有匹配，返回原值
        self.logger.debug(f"MP to MPBackup 轉換無變化: {original_revision}")
        return original_revision
    
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
        """根據專案資訊建立完整的 project 行內容 - 徹底修正remote問題"""
        try:
            # 建立基本的 project 標籤
            project_line = "<project"
            
            # 標準屬性順序
            attrs_order = ['groups', 'name', 'path', 'revision', 'upstream', 'dest-branch', 'clone-depth', 'remote']
            
            for attr in attrs_order:
                value = project.get(attr, '')
                
                # 特殊處理 revision
                if attr == 'revision' and use_converted_revision:
                    value = project.get('converted_revision', project.get('revision', ''))
                
                # 🔥 徹底修正 remote 屬性問題
                if attr == 'remote':
                    # 檢查專案的原始資料中是否有明確的 remote 屬性
                    original_remote = project.get('original_remote', None)  # 使用原始remote
                    if original_remote is None or original_remote == '':
                        # 如果原始專案沒有remote，完全跳過
                        self.logger.debug(f"專案 {project.get('name', 'unknown')} 原始沒有remote屬性，跳過添加")
                        continue
                    value = original_remote
                
                # 只添加非空值
                if value and value.strip():
                    project_line += f' {attr}="{value}"'
            
            # 🔥 重要修改：不要自動添加 />，保持原始格式
            project_line += ">"
            
            return project_line
            
        except Exception as e:
            self.logger.error(f"建立 project 行內容失敗: {str(e)}")
            return f"<project name=\"{project.get('name', 'unknown')}\" ... >"
    
    def _analyze_differences(self, converted_content: str, target_content: Optional[str], 
                    overwrite_type: str, conversion_info: List[Dict]) -> Dict[str, Any]:
        """分析轉換檔案與目標檔案的差異 - 修正版本，更準確的統計"""
        
        # 🔥 添加檔案來源確認日誌
        self.logger.info(f"🔍 差異分析檔案確認:")
        self.logger.info(f"   轉換類型: {overwrite_type}")
        self.logger.info(f"   來源檔案: {self.source_files.get(overwrite_type, 'unknown')}")
        self.logger.info(f"   輸出檔案: {self.output_files.get(overwrite_type, 'unknown')}")
        self.logger.info(f"   比較目標檔案: {self.target_files.get(overwrite_type, 'unknown')}")
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
                
                # 進行差異比較（使用修正後的邏輯）
                differences = self._compare_projects_with_conversion_info(
                    conversion_info, target_projects, overwrite_type
                )
                analysis['differences'] = differences
                
                # 🆕 修正統計摘要 - 更準確的計算
                total_projects = len(conversion_info)
                converted_projects = sum(1 for proj in conversion_info if proj.get('changed', False))
                unchanged_projects = total_projects - converted_projects
                
                analysis['summary'] = {
                    'converted_count': total_projects,  # 總專案數
                    'target_count': len(target_projects),
                    'actual_conversion_count': converted_projects,  # 實際轉換數
                    'unchanged_count': unchanged_projects,  # 未轉換數
                    'differences_count': len(differences),  # 有差異數
                    'identical_converted_count': max(0, converted_projects - len(differences)),  # 轉換後相同數
                    'conversion_match_rate': f"{(max(0, converted_projects - len(differences)) / max(converted_projects, 1) * 100):.1f}%" if converted_projects > 0 else "N/A"
                }
                
                self.logger.info(f"差異分析完成:")
                self.logger.info(f"  📋 總專案數: {total_projects}")
                self.logger.info(f"  🔄 實際轉換專案: {converted_projects}")
                self.logger.info(f"  ⭕ 未轉換專案: {unchanged_projects}")
                self.logger.info(f"  ❌ 轉換後有差異: {len(differences)}")
                self.logger.info(f"  ✅ 轉換後相同: {max(0, converted_projects - len(differences))}")
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
        """尋找專案在 XML 中的行號和完整內容 - 修正版本，只抓 project 標籤本身"""
        line_number = 0
        full_content = ""
        
        try:
            import re
            
            for i, line in enumerate(lines, 1):
                stripped_line = line.strip()
                
                # 檢查是否包含該專案名稱
                if f'name="{project_name}"' in line:
                    line_number = i
                    
                    # 🆕 使用正規表達式只抓取 project 標籤本身
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
                                if j > i - 1:  # 不重複第一行
                                    project_content += " " + next_line
                                
                                if next_line.endswith('>'):
                                    # 🆕 使用正規表達式提取完整的 project 標籤
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
        """使用轉換資訊比較專案差異 - 修正版本，使用 name+path composite key"""
        differences = []
        
        # 🔥 修改：建立目標專案的索引 - 使用 name+path 組合作為 key
        target_index = {}
        for proj in target_projects:
            name = proj['name']
            path = proj['path']
            composite_key = f"{name}|{path}"
            target_index[composite_key] = proj
        
        # 取得正確的檔案名稱
        source_file, gerrit_source_file = self._get_source_and_target_filenames(overwrite_type)
        
        for conv_proj in converted_projects:
            project_name = conv_proj['name']
            project_path = conv_proj['path']
            # 🔥 修改：建立轉換專案的 composite key
            conv_composite_key = f"{project_name}|{project_path}"
            has_conversion = conv_proj.get('changed', False)
            
            # 只有真正有轉換的專案才進行差異比較
            if not has_conversion:
                continue
            
            # 🔥 修改：使用 composite key 查找對應專案
            if conv_composite_key not in target_index:
                # 專案在轉換後存在，但在 Gerrit 中不存在 - 新增
                difference = {
                    'SN': len(differences) + 1,
                    'source_file': source_file,
                    'content': self._build_project_line_content(conv_proj, use_converted_revision=True),
                    'name': conv_proj['name'],
                    'path': conv_proj['path'],
                    'revision': conv_proj['converted_revision'],
                    'original_revision': conv_proj['original_revision'],
                    'Revision 是否相等': '',  # 🔥 添加新欄位，空值將由 Excel 公式填充
                    'upstream': conv_proj['upstream'],
                    'dest-branch': conv_proj['dest-branch'],
                    'groups': conv_proj['groups'],
                    'clone-depth': conv_proj['clone-depth'],
                    'remote': conv_proj['remote'],
                    'source_link': self._generate_source_link(conv_proj['name'], conv_proj['converted_revision'], conv_proj['remote']),
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
                    'comparison_status': '🆕 新增',
                    'comparison_result': '僅存在於轉換後',
                    'status_color': 'yellow'
                }
                differences.append(difference)
                continue
            
            # 🔥 修改：使用 composite key 取得目標專案
            target_proj = target_index[conv_composite_key]
            
            # 🔥 添加調試日誌確認找到正確的對應專案
            # self.logger.info(f"🔍 比較專案 composite key: {conv_composite_key}")
            # self.logger.info(f"   轉換後: name='{conv_proj['name']}', path='{conv_proj['path']}'")
            # self.logger.info(f"   Gerrit:  name='{target_proj['name']}', path='{target_proj['path']}'")
            
            # 修正比較邏輯：忽略屬性順序，只比較實際值
            is_identical = self._compare_project_attributes_ignore_order(conv_proj, target_proj, use_converted_revision=True)
            
            # 判斷比較狀態
            if is_identical:
                comparison_status = '✅ 相同'
                comparison_result = '轉換後與 Gerrit 完全一致'
                status_color = 'green'
            else:
                comparison_status = '❌ 不同'
                comparison_result = '轉換後與 Gerrit 有差異'
                status_color = 'red'
            
            # 記錄所有比較結果（包含相同的）
            difference = {
                'SN': len(differences) + 1,
                'source_file': source_file,
                'content': self._build_project_line_content(conv_proj, use_converted_revision=True),
                'name': conv_proj['name'],
                'path': conv_proj['path'],
                'revision': conv_proj['converted_revision'],
                'original_revision': conv_proj['original_revision'],
                'upstream': conv_proj['upstream'],
                'dest-branch': conv_proj['dest-branch'],
                'groups': conv_proj['groups'],
                'clone-depth': conv_proj['clone-depth'],
                'remote': conv_proj['remote'],
                'source_link': self._generate_source_link(conv_proj['name'], conv_proj['converted_revision'], conv_proj['remote']),
                'gerrit_source_file': gerrit_source_file,
                'gerrit_content': target_proj['full_line'],
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
        
        # 🔥 修正：檢查 Gerrit 中存在但轉換後不存在的專案（刪除）
        converted_composite_keys = set()
        for proj in converted_projects:
            composite_key = f"{proj['name']}|{proj['path']}"
            converted_composite_keys.add(composite_key)
            
            # 🔥 添加調試日誌 - 記錄每個轉換專案的狀態
            changed_status = proj.get('changed', False)
            self.logger.debug(f"轉換專案: {composite_key}, changed: {changed_status}")

        self.logger.info(f"🔍 轉換後存在的專案數量: {len(converted_composite_keys)}")
        self.logger.info(f"🔍 Gerrit 目標專案數量: {len(target_index)}")

        # 檢查被誤判為刪除的專案
        potentially_deleted = []
        for composite_key, target_proj in target_index.items():
            if composite_key not in converted_composite_keys:
                potentially_deleted.append(composite_key)

        if potentially_deleted:
            self.logger.warning(f"🔍 被判定為刪除的專案: {len(potentially_deleted)} 個")
            for key in potentially_deleted[:5]:  # 只顯示前5個
                self.logger.warning(f"   - {key}")

        for composite_key, target_proj in target_index.items():
            if composite_key not in converted_composite_keys:
                # 🔥 添加更詳細的刪除日誌
                self.logger.info(f"🗑️ 標記為刪除: {composite_key}")
                self.logger.info(f"   原因: 在 Gerrit 中存在但轉換後專案列表中不存在")
                
                difference = {
                    'SN': len(differences) + 1,
                    'source_file': source_file,
                    'content': 'N/A (專案已刪除)',
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
                    'gerrit_content': target_proj['full_line'],
                    'gerrit_name': target_proj['name'],
                    'gerrit_path': target_proj['path'],
                    'gerrit_revision': target_proj['revision'],
                    'gerrit_upstream': target_proj['upstream'],
                    'gerrit_dest-branch': target_proj['dest-branch'],
                    'gerrit_groups': target_proj['groups'],
                    'gerrit_clone-depth': target_proj['clone-depth'],
                    'gerrit_remote': target_proj['remote'],
                    'gerrit_source_link': self._generate_source_link(target_proj['name'], target_proj['revision'], target_proj['remote']),
                    'comparison_status': '🗑️ 刪除',
                    'comparison_result': '僅存在於 Gerrit',
                    'status_color': 'orange'
                }
                differences.append(difference)
        
        return differences
    
    def _compare_project_attributes_ignore_order(self, conv_proj: Dict, target_proj: Dict, use_converted_revision: bool = False) -> bool:
        """比較專案屬性，忽略順序差異 - 完全修正版本"""
        try:
            project_name = conv_proj.get('name', 'unknown')
            
            # 🔥 添加詳細比較日誌
            # self.logger.info(f"🔍 詳細比較專案: {project_name}")
            # self.logger.info(f"   轉換後 content: {conv_proj.get('content', 'N/A')}")
            # self.logger.info(f"   Gerrit content: {target_proj.get('full_line', 'N/A')}")
            
            # 要比較的屬性列表
            attrs_to_compare = ['name', 'path', 'revision', 'upstream', 'dest-branch', 'groups', 'clone-depth', 'remote']
            
            # 🔥 逐一比較每個屬性並記錄
            for attr in attrs_to_compare:
                conv_val = conv_proj.get(attr, '').strip()
                target_val = target_proj.get(attr, '').strip()
                
                # 特殊處理 revision
                if attr == 'revision' and use_converted_revision:
                    conv_val = conv_proj.get('converted_revision', '').strip()
                
                # 🔥 詳細記錄每個屬性的比較
                # self.logger.info(f"   屬性 {attr}:")
                # self.logger.info(f"     轉換後: '{conv_val}'")
                # self.logger.info(f"     Gerrit:  '{target_val}'")
                # self.logger.info(f"     相同: {conv_val == target_val}")
                
                # 如果不同，立即返回並記錄原因
                if conv_val != target_val:
                    self.logger.info(f"❌ 專案 {project_name} 在屬性 {attr} 不同")
                    self.logger.info(f"   轉換後值: '{conv_val}' (長度: {len(conv_val)})")
                    self.logger.info(f"   Gerrit值:  '{target_val}' (長度: {len(target_val)})")
                    # 🔥 添加字元級別的比較
                    if len(conv_val) != len(target_val):
                        self.logger.info(f"   長度不同!")
                    else:
                        for i, (c1, c2) in enumerate(zip(conv_val, target_val)):
                            if c1 != c2:
                                self.logger.info(f"   第 {i} 個字元不同: '{c1}' vs '{c2}' (ASCII: {ord(c1)} vs {ord(c2)})")
                                break
                    return False
            
            # self.logger.info(f"✅ 專案 {project_name} 所有屬性都相同")
            return True
            
        except Exception as e:
            self.logger.error(f"比較專案屬性失敗: {str(e)}")
            return False

    def _generate_source_link(self, project_name: str, revision: str, remote: str = '') -> str:
        """
        根據專案名稱、revision 和 remote 生成 gerrit source link
        """
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
        """執行 Git clone, commit, push 操作 - 使用 config.py 的 commit message 模板"""
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
            source_filename = self.source_files[overwrite_type]
            
            # 步驟 1: Clone repository
            self.logger.info(f"📥 Clone repository: {repo_url}")
            clone_cmd = ["git", "clone", "-b", branch, repo_url, temp_git_dir]
            
            subprocess.run(clone_cmd, check=True, capture_output=True, text=True, timeout=60)
            
            # 步驟 2: 切換到 Git 目錄並設定環境
            original_cwd = os.getcwd()
            os.chdir(temp_git_dir)
            
            # 步驟 2.5: 安裝 commit-msg hook
            self.logger.info(f"🔧 安裝 commit-msg hook...")
            try:
                hook_install_cmd = "gitdir=$(git rev-parse --git-dir); scp -p -P 29418 vince_lin@mm2sd.rtkbf.com:hooks/commit-msg ${gitdir}/hooks/"
                
                result_hook = subprocess.run(
                    hook_install_cmd,
                    shell=True,
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
            
            # 步驟 6: 生成 Commit Message（從 config.py）
            commit_message = self._generate_commit_message(
                overwrite_type=overwrite_type,
                source_file=source_filename,
                target_file=target_filename
            )
            
            self.logger.info("📝 使用 config.py 的 commit message 模板")
            self.logger.debug(f"Commit message:\n{commit_message[:200]}...")  # 只顯示前200字符
            
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
                self.logger.error(f"Change-Id 錯誤: {error_msg}")
            elif "Permission denied" in error_msg or "publickey" in error_msg:
                result['message'] = f"SSH 認證失敗: {error_msg}"
                self.logger.error(f"SSH 認證問題: {error_msg}")
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

    def _generate_commit_message(self, overwrite_type: str, source_file: str = None, 
                                target_file: str = None, rddb_number: str = None) -> str:
        """
        從 config.py 生成 commit message
        
        Args:
            overwrite_type: 轉換類型
            source_file: 源檔案名稱
            target_file: 目標檔案名稱
            rddb_number: RDDB 號碼（可選）
            
        Returns:
            格式化的 commit message
        """
        try:
            import config
            
            # 取得 RDDB 號碼
            if not rddb_number:
                rddb_number = getattr(config, 'DEFAULT_RDDB_NUMBER', 'RDDB-923')
            
            # 檢查是否使用詳細模板
            use_detailed = getattr(config, 'USE_DETAILED_COMMIT_MESSAGE', True)
            
            if use_detailed:
                # 使用詳細模板
                template = getattr(config, 'COMMIT_MESSAGE_TEMPLATE', '')
                
                if not template:
                    # 如果 config 中沒有模板，使用預設
                    self.logger.warning("config.py 中沒有 COMMIT_MESSAGE_TEMPLATE，使用預設模板")
                    template = self._get_default_detailed_template()
                
                # 格式化模板
                commit_message = template.format(
                    rddb_number=rddb_number,
                    overwrite_type=overwrite_type
                )
                
                self.logger.info(f"使用詳細 commit message 模板 (RDDB: {rddb_number})")
                
            else:
                # 使用簡單模板
                template = getattr(config, 'COMMIT_MESSAGE_SIMPLE', '')
                
                if not template:
                    # 如果沒有簡單模板，使用預設
                    template = """Auto-generated manifest update: {overwrite_type}

    Generated by manifest conversion tool
    Source: {source_file}
    Target: {target_file}"""
                
                # 格式化模板
                commit_message = template.format(
                    overwrite_type=overwrite_type,
                    source_file=source_file or self.source_files.get(overwrite_type, 'unknown'),
                    target_file=target_file or self.output_files.get(overwrite_type, 'unknown')
                )
                
                self.logger.info("使用簡單 commit message 模板")
            
            return commit_message
            
        except Exception as e:
            self.logger.error(f"生成 commit message 失敗: {str(e)}")
            
            # 返回預設的簡單訊息
            default_message = f"""Auto-generated manifest update: {overwrite_type}

    Generated by manifest conversion tool
    Source: {source_file or self.source_files.get(overwrite_type, 'unknown')}
    Target: {target_file or self.output_files.get(overwrite_type, 'unknown')}"""
            
            self.logger.warning("使用預設 commit message")
            return default_message

    def _get_default_detailed_template(self) -> str:
        """取得預設的詳細 commit message 模板"""
        return """[{rddb_number}][Manifest][Feat]: manifest update: {overwrite_type}
    
    * Problem: for google request
    * Root Cause: change branches every three months
    * Solution: manifest update: {overwrite_type}
    * Dependency: N
    * Testing Performed:
    - ac/dc on/off: ok
    * RD-CodeSync: Y
    * PL-CodeSync: N
    - Mac7p: N
    - Mac8q: N
    - Mac9q: N
    - Merlin5: N
    - Merlin7: N
    - Merlin8: N
    - Merlin8p: N
    - Merlin9: N
    - Dante: N
    - Dora: N
    - MatriX: N
    - Midas: N
    - AN11: N
    - AN12: N
    - AN14: N
    - AN16: N
    - R2U: N
    - Kernel_Only: N
    * Supplementary:
    
    * Issue:
    - {rddb_number}"""
        
    def _generate_excel_report(self, overwrite_type: str, source_file_path: Optional[str],
                        output_file_path: Optional[str], target_file_path: Optional[str], 
                        diff_analysis: Dict, output_folder: str, 
                        excel_filename: Optional[str], source_download_success: bool,
                        target_download_success: bool, push_result: Optional[Dict[str, Any]] = None,
                        expanded_file_path: Optional[str] = None, use_expanded: bool = False) -> str:
        """產生 Excel 報告 - 修正版本，新的頁籤順序和底色"""
        try:
            if excel_filename:
                excel_file = os.path.join(output_folder, excel_filename)
            else:
                default_name = f"{overwrite_type}_conversion_report.xlsx"
                excel_file = os.path.join(output_folder, default_name)
            
            with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
                # 🆕 頁籤 1: 轉換摘要（淺藍色底色）
                summary_data = [{
                    'SN': 1,
                    '轉換類型': overwrite_type,
                    'Gerrit 源檔案': os.path.basename(source_file_path) if source_file_path else '無',
                    '源檔案下載狀態': '成功' if source_download_success else '失敗',
                    '源檔案': self.source_files.get(overwrite_type, ''),  # 這個會被轉為連結
                    '包含 include 標籤': '是' if use_expanded else '否',
                    'Gerrit 展開檔案': os.path.basename(expanded_file_path) if expanded_file_path else '無',
                    '使用展開檔案轉換': '是' if use_expanded else '否',
                    '輸出檔案': os.path.basename(output_file_path) if output_file_path else '',
                    'Gerrit 目標檔案': os.path.basename(target_file_path) if target_file_path else '無',
                    '目標檔案下載狀態': '成功' if target_download_success else '失敗 (檔案不存在)',
                    '目標檔案': self.target_files.get(overwrite_type, ''),  # 這個會被轉為連結
                    '📊 總專案數': diff_analysis['summary'].get('converted_count', 0),
                    '🔄 實際轉換專案數': diff_analysis['summary'].get('actual_conversion_count', 0),
                    '⭕ 未轉換專案數': diff_analysis['summary'].get('unchanged_count', 0),
                    '🎯 目標檔案專案數': diff_analysis['summary'].get('target_count', 0),
                    '❌ 轉換後有差異數': diff_analysis['summary'].get('differences_count', 0),
                    '✅ 轉換後相同數': diff_analysis['summary'].get('identical_converted_count', 0),
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

                # 🆕 為轉換摘要頁籤添加超連結
                worksheet_summary = writer.sheets['轉換摘要']
                self._add_summary_hyperlinks(worksheet_summary, overwrite_type)
                
                # 頁籤 2: 轉換後專案（淺藍色底色）
                if diff_analysis['converted_projects']:
                    converted_data = []
                    for i, proj in enumerate(diff_analysis['converted_projects'], 1):
                        has_conversion = proj.get('changed', False)
                        if has_conversion:
                            conversion_status = '🔄 已轉換'
                            status_description = f"{proj['original_revision']} → {proj['converted_revision']}"
                        else:
                            conversion_status = '⭕ 未轉換'
                            status_description = f"保持原值: {proj['original_revision']}"
                        
                        converted_data.append({
                            'SN': i,
                            '專案名稱': proj['name'],
                            '專案路徑': proj['path'],
                            '轉換狀態': conversion_status,
                            '原始 Revision': proj['original_revision'],
                            '轉換後 Revision': proj['converted_revision'],
                            'Revision 是否相等': '',  # 🔥 添加新欄位，空值將由 Excel 公式填充
                            '轉換說明': status_description,
                            'Upstream': proj['upstream'],
                            'Dest-Branch': proj['dest-branch'],
                            'Groups': proj['groups'],
                            'Clone-Depth': proj['clone-depth'],
                            'Remote': proj['remote']
                        })
                    
                    df_converted = pd.DataFrame(converted_data)
                    df_converted.to_excel(writer, sheet_name='轉換後專案', index=False)
                    
                    # 🔥 添加 Excel 公式到 "轉換後專案" 頁籤的 "Revision 是否相等" 欄位
                    worksheet_converted = writer.sheets['轉換後專案']
                    self._add_revision_comparison_formula_converted_projects(worksheet_converted)
                
                # 頁籤 3: 轉換後與 Gerrit manifest 的差異（淺紅色底色）
                if diff_analysis['has_target'] and diff_analysis['differences']:
                    diff_sheet_name = "轉換後與 Gerrit manifest 的差異"
                    df_diff = pd.DataFrame(diff_analysis['differences'])
                    
                    # 🔥 修正欄位順序，移除不需要的 "revision" 和 "Revision 是否相等" 欄位
                    diff_columns = [
                        'SN', 'comparison_status', 'comparison_result',
                        'source_file', 'content', 'name', 'path', 
                        'original_revision',  # 🔥 只保留 original_revision，移除 revision 和 Revision 是否相等
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
                        # 🔥 修改原因說明 - 區分 hash 和非 hash revision
                        reason = "符合跳過轉換條件或無需轉換"
                        needs_red_font = False
                        
                        if proj['original_revision']:  # 如果有保持的 Revision
                            # 🔥 檢查是否為 hash
                            if self._is_revision_hash(proj['original_revision']):
                                reason = "符合跳過轉換條件或無需轉換 (Hash Revision)"
                                needs_red_font = False  # hash 不需要紅字
                            else:
                                reason = "需檢查是否來源端是否有問題"
                                needs_red_font = True   # 非 hash 但有值，需要紅字
                            
                        unchanged_data.append({
                            'SN': i,
                            '專案名稱': proj['name'],
                            '專案路徑': proj['path'],
                            '保持的 Revision': proj['original_revision'],
                            '原因': reason,
                            '需要紅字': needs_red_font,  # 🔥 標記是否需要紅字
                            'Upstream': proj['upstream'],
                            'Groups': proj['groups'],
                            'Remote': proj['remote']
                        })
                    
                    df_unchanged = pd.DataFrame(unchanged_data)
                    df_unchanged.to_excel(writer, sheet_name='未轉換專案', index=False)
                    
                    # 🔥 設定原因欄位的紅字格式
                    worksheet_unchanged = writer.sheets['未轉換專案']
                    self._format_unchanged_projects_reason_column(worksheet_unchanged)
                
                # 🆕 頁籤 5: 來源的 manifest（淺綠色底色）
                if diff_analysis['converted_projects']:
                    source_data = []
                    for i, proj in enumerate(diff_analysis['converted_projects'], 1):
                        source_link = self._generate_source_link(proj['name'], proj['original_revision'], proj['remote'])
                        # 🔥 修正：使用 gerrit_ 開頭的來源檔案名稱
                        gerrit_source_filename = f"gerrit_{self.source_files.get(overwrite_type, 'unknown.xml')}"
                        
                        source_data.append({
                            'SN': i,
                            'source_file': gerrit_source_filename,  # 🔥 例如：gerrit_atv-google-refplus-wave.xml
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
                
                # 🆕 頁籤 6: 轉換後的 manifest（淺綠色底色）
                if diff_analysis['converted_projects']:
                    converted_manifest_data = []
                    for i, proj in enumerate(diff_analysis['converted_projects'], 1):
                        source_link = self._generate_source_link(proj['name'], proj['converted_revision'], proj['remote'])
                        # 🔥 修正：使用轉換後的檔案名稱（即將用來比對的那份）
                        output_filename = self.output_files.get(overwrite_type, 'unknown.xml')
                        
                        converted_manifest_data.append({
                            'SN': i,
                            'source_file': output_filename,  # 🔥 例如：atv-google-refplus-wave-backup.xml
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
                
                # 🆕 頁籤 7: gerrit 上的 manifest（淺綠色底色）
                if diff_analysis['has_target'] and diff_analysis['target_projects']:
                    gerrit_data = []
                    for i, proj in enumerate(diff_analysis['target_projects'], 1):
                        source_link = self._generate_source_link(proj['name'], proj['revision'], proj['remote'])
                        # 🔥 修正：使用 gerrit_ 開頭的目標檔案名稱
                        gerrit_target_filename = f"gerrit_{self.target_files.get(overwrite_type, 'unknown.xml')}"
                        
                        gerrit_data.append({
                            'SN': i,
                            'source_file': gerrit_target_filename,  # 🔥 例如：gerrit_atv-google-refplus-wave-backup.xml
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
                
                # 🆕 格式化所有工作表 - 新的底色方案
                for sheet_name in writer.sheets:
                    worksheet = writer.sheets[sheet_name]
                    self._format_worksheet_with_background_colors(worksheet, sheet_name)
                    
                    # 🆕 為相關頁籤添加超連結
                    if sheet_name in ['來源的 manifest', '轉換後的 manifest', 'gerrit 上的 manifest', '轉換後與 Gerrit manifest 的差異']:
                        self._add_manifest_hyperlinks(worksheet, sheet_name)
                        
                        # 🆕 額外日誌說明各頁籤的連結策略
                        if sheet_name == '來源的 manifest':
                            self.logger.info(f"📋 {sheet_name}: source_file 欄位已添加 Gerrit 連結")
                        elif sheet_name == '轉換後的 manifest':
                            self.logger.info(f"📋 {sheet_name}: source_file 欄位不添加連結（本地檔案）")
                        elif sheet_name == 'gerrit 上的 manifest':
                            self.logger.info(f"📋 {sheet_name}: source_file 欄位已添加 Gerrit 連結")
                        elif sheet_name == '轉換後與 Gerrit manifest 的差異':
                            self.logger.info(f"📋 {sheet_name}: 僅 gerrit_source_file 欄位添加連結，source_file 不添加")
            
            self.logger.info(f"成功產生 Excel 報告: {excel_file}")
            return excel_file
            
        except Exception as e:
            self.logger.error(f"產生 Excel 報告失敗: {str(e)}")
            raise

    def _add_manifest_hyperlinks(self, worksheet, sheet_name: str):
        """
        為 manifest 相關頁籤添加 source_file 欄位的超連結
        
        Args:
            worksheet: Excel 工作表
            sheet_name: 頁籤名稱
        """
        try:
            # 找到 source_file 欄位的位置
            source_file_col = None
            gerrit_source_file_col = None
            
            for col_num, cell in enumerate(worksheet[1], 1):  # 表頭行
                header_value = str(cell.value) if cell.value else ''
                
                if header_value == 'source_file':
                    source_file_col = col_num
                elif header_value == 'gerrit_source_file':
                    gerrit_source_file_col = col_num
            
            # 🆕 只有特定頁籤的 source_file 欄位需要添加連結
            source_file_need_link = sheet_name in ['來源的 manifest', 'gerrit 上的 manifest']
            
            # 為 source_file 欄位添加連結（僅限指定頁籤）
            if source_file_col and source_file_need_link:
                for row_num in range(2, worksheet.max_row + 1):
                    cell = worksheet.cell(row=row_num, column=source_file_col)
                    filename = str(cell.value) if cell.value else ''
                    
                    if filename and filename not in ['', 'N/A']:
                        gerrit_url = self._generate_gerrit_manifest_link(filename)
                        self._add_hyperlink_to_cell(worksheet, row_num, source_file_col, gerrit_url, filename)
            
            # 為 gerrit_source_file 欄位添加連結（所有有此欄位的頁籤都需要）
            if gerrit_source_file_col:
                for row_num in range(2, worksheet.max_row + 1):
                    cell = worksheet.cell(row=row_num, column=gerrit_source_file_col)
                    filename = str(cell.value) if cell.value else ''
                    
                    if filename and filename not in ['', 'N/A']:
                        gerrit_url = self._generate_gerrit_manifest_link(filename)
                        self._add_hyperlink_to_cell(worksheet, row_num, gerrit_source_file_col, gerrit_url, filename)
            
            # 🆕 記錄處理結果
            if source_file_col and source_file_need_link:
                self.logger.info(f"✅ 已為 {sheet_name} 添加 source_file 欄位連結")
            elif source_file_col and not source_file_need_link:
                self.logger.info(f"⏭️ 跳過 {sheet_name} 的 source_file 欄位連結（按需求不添加）")
            
            if gerrit_source_file_col:
                self.logger.info(f"✅ 已為 {sheet_name} 添加 gerrit_source_file 欄位連結")
            
        except Exception as e:
            self.logger.error(f"添加 {sheet_name} 超連結失敗: {str(e)}")
            
    def _add_summary_hyperlinks(self, worksheet, overwrite_type: str):
        """
        為轉換摘要頁籤添加 Gerrit 超連結
        
        Args:
            worksheet: Excel 工作表
            overwrite_type: 轉換類型
        """
        try:
            # 找到需要添加連結的欄位
            target_columns = {
                '源檔案': self.source_files.get(overwrite_type, ''),
                '目標檔案': self.target_files.get(overwrite_type, '')  # 🔥 確保包含目標檔案
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
        """為轉換後專案頁籤添加真正的動態條件格式"""
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
            
            # 🔥 只添加 Excel 公式，不手動設定顏色
            for row_num in range(2, worksheet.max_row + 1):
                formula = f'=IF({original_col_letter}{row_num}={converted_col_letter}{row_num},"Y","N")'
                cell = worksheet[f"{comparison_col_letter}{row_num}"]
                cell.value = formula
                # 🔥 不設定任何手動顏色，讓條件格式處理
            
            # 🔥 設定真正的動態條件格式
            green_font = Font(color="00B050", bold=True)
            red_font = Font(color="FF0000", bold=True)
            
            # 條件格式範圍
            range_string = f"{comparison_col_letter}2:{comparison_col_letter}{worksheet.max_row}"
            
            # 🔥 為 "Y" 值設定綠色字體（使用文字比較）
            green_rule = Rule(
                type="containsText",
                operator="containsText",
                text="Y",
                dxf=DifferentialStyle(font=green_font)
            )
            green_rule.formula = [f'NOT(ISERROR(SEARCH("Y",{comparison_col_letter}2)))']
            
            # 🔥 為 "N" 值設定紅色字體（使用文字比較）
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
            # 使用備用方案
            self._add_revision_comparison_formula_converted_projects_backup(worksheet)

    def _add_revision_comparison_formula_converted_projects_backup(self, worksheet):
        """備用方案：使用更簡單的條件格式語法"""
        try:
            from openpyxl.styles import Font
            from openpyxl.utils import get_column_letter
            from openpyxl.formatting.rule import CellIsRule
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
                return
            
            # 取得欄位字母
            original_col_letter = get_column_letter(original_revision_col)
            converted_col_letter = get_column_letter(converted_revision_col)
            comparison_col_letter = get_column_letter(comparison_col)
            
            # 🔥 只添加公式，不設定手動顏色
            for row_num in range(2, worksheet.max_row + 1):
                formula = f'=IF({original_col_letter}{row_num}={converted_col_letter}{row_num},"Y","N")'
                cell = worksheet[f"{comparison_col_letter}{row_num}"]
                cell.value = formula
            
            # 🔥 使用 CellIsRule 設定條件格式
            green_font_style = DifferentialStyle(font=Font(color="00B050", bold=True))
            red_font_style = DifferentialStyle(font=Font(color="FF0000", bold=True))
            
            # 為 "Y" 設定綠色
            green_rule = CellIsRule(
                operator='equal',
                formula=['"Y"'],
                dxf=green_font_style,
                stopIfTrue=False
            )
            
            # 為 "N" 設定紅色
            red_rule = CellIsRule(
                operator='equal',
                formula=['"N"'],
                dxf=red_font_style,
                stopIfTrue=False
            )
            
            # 應用條件格式
            range_string = f"{comparison_col_letter}2:{comparison_col_letter}{worksheet.max_row}"
            worksheet.conditional_formatting.add(range_string, green_rule)
            worksheet.conditional_formatting.add(range_string, red_rule)
            
            self.logger.info("✅ 已使用備用方案添加動態條件格式")
            
        except Exception as e:
            self.logger.error(f"備用方案也失敗: {str(e)}")
            # 最後使用最簡單的方案
            self._add_revision_comparison_formula_only(worksheet)

    def _add_revision_comparison_formula_only(self, worksheet):
        """最簡單方案：只添加公式，讓使用者在Excel中手動設定條件格式"""
        try:
            from openpyxl.utils import get_column_letter
            
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
                return
            
            # 取得欄位字母
            original_col_letter = get_column_letter(original_revision_col)
            converted_col_letter = get_column_letter(converted_revision_col)
            comparison_col_letter = get_column_letter(comparison_col)
            
            # 🔥 只添加 Excel 動態公式
            for row_num in range(2, worksheet.max_row + 1):
                formula = f'=IF({original_col_letter}{row_num}={converted_col_letter}{row_num},"Y","N")'
                cell = worksheet[f"{comparison_col_letter}{row_num}"]
                cell.value = formula
            
            self.logger.info("✅ 已添加 Excel 動態公式（無條件格式）")
            self.logger.info("💡 提示：可在Excel中手動為 'Revision 是否相等' 欄位設定條件格式")
            self.logger.info("   - 選取範圍 → 常用 → 設定格式化的條件 → 等於 'Y' 設綠色，'N' 設紅色")
            
        except Exception as e:
            self.logger.error(f"添加公式失敗: {str(e)}")
                                    
    def _format_unchanged_projects_reason_column(self, worksheet):
        """格式化未轉換專案的原因欄位 - 設定紅字，區分 hash 和非 hash revision"""
        try:
            from openpyxl.styles import Font
            
            red_font = Font(color="FF0000", bold=True)  # 紅字
            
            # 找到原因欄位的位置
            reason_col = None
            needs_red_col = None
            revision_col = None
            
            for col_num, cell in enumerate(worksheet[1], 1):
                header_value = str(cell.value) if cell.value else ''
                if header_value == '原因':
                    reason_col = col_num
                elif header_value == '需要紅字':
                    needs_red_col = col_num
                elif header_value == '保持的 Revision':
                    revision_col = col_num
            
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
            
            # 🔥 隱藏 "需要紅字" 輔助欄位
            if needs_red_col:
                from openpyxl.utils import get_column_letter
                col_letter = get_column_letter(needs_red_col)
                worksheet.column_dimensions[col_letter].hidden = True
            
            self.logger.info("✅ 已設定未轉換專案原因欄位的紅字格式")
            
        except Exception as e:
            self.logger.error(f"設定原因欄位紅字格式失敗: {str(e)}")
            
    def _add_revision_comparison_formula(self, worksheet):
        """添加 Revision 是否相等 欄位的 Excel 公式"""
        try:
            from openpyxl.styles import Font
            from openpyxl.utils import get_column_letter
            
            # 找到相關欄位的位置
            original_revision_col = None
            converted_revision_col = None
            comparison_col = None
            
            for col_num, cell in enumerate(worksheet[1], 1):
                header_value = str(cell.value) if cell.value else ''
                if header_value == 'original_revision':
                    original_revision_col = col_num
                elif header_value == 'revision':  # 這是 "轉換後 Revision"
                    converted_revision_col = col_num
                elif header_value == 'Revision 是否相等':
                    comparison_col = col_num
            
            if not all([original_revision_col, converted_revision_col, comparison_col]):
                self.logger.warning(f"無法找到所需的欄位位置: original_revision_col={original_revision_col}, converted_revision_col={converted_revision_col}, comparison_col={comparison_col}")
                return
            
            # 定義字體顏色
            green_font = Font(color="00B050", bold=True)  # 綠字
            red_font = Font(color="FF0000", bold=True)    # 紅字
            
            # 為每個資料行添加公式
            for row_num in range(2, worksheet.max_row + 1):
                # 取得欄位字母
                original_col_letter = get_column_letter(original_revision_col)
                converted_col_letter = get_column_letter(converted_revision_col)
                comparison_col_letter = get_column_letter(comparison_col)
                
                # 添加 Excel 公式
                formula = f'=IF({original_col_letter}{row_num}={converted_col_letter}{row_num},"Y","N")'
                cell = worksheet[f"{comparison_col_letter}{row_num}"]
                cell.value = formula
                
                # 🔥 根據實際值設定字體顏色
                original_value = worksheet[f"{original_col_letter}{row_num}"].value or ''
                converted_value = worksheet[f"{converted_col_letter}{row_num}"].value or ''
                
                # 標準化比較值（去除空白）
                original_clean = str(original_value).strip()
                converted_clean = str(converted_value).strip()
                
                if original_clean == converted_clean:
                    cell.font = green_font  # Y - 綠字
                    cell.value = 'Y'  # 直接設定值而不是公式，這樣更可靠
                else:
                    cell.font = red_font    # N - 紅字
                    cell.value = 'N'
            
            self.logger.info("✅ 已添加 Revision 是否相等 欄位的公式和格式")
            
        except Exception as e:
            self.logger.error(f"添加 Revision 比較公式失敗: {str(e)}")

    def _generate_gerrit_manifest_link(self, filename: str) -> str:
        """
        生成 Gerrit manifest 檔案的連結
        
        Args:
            filename: manifest 檔案名稱
            
        Returns:
            Gerrit 連結 URL
        """
        try:
            if not filename or filename == '無':
                return '無'
            
            # 移除 gerrit_ 前綴（如果有的話）
            clean_filename = filename.replace('gerrit_', '') if filename.startswith('gerrit_') else filename
            
            # 構建 Gerrit 連結
            base_url = "https://mm2sd.rtkbf.com/gerrit/plugins/gitiles/realtek/android/manifest/+/refs/heads/realtek/android-14/master"
            gerrit_link = f"{base_url}/{clean_filename}"
            
            self.logger.debug(f"生成 Gerrit 連結: {clean_filename} → {gerrit_link}")
            return gerrit_link
            
        except Exception as e:
            self.logger.error(f"生成 Gerrit 連結失敗: {str(e)}")
            return filename  # 返回原始檔名作為備用

    def _add_hyperlink_to_cell(self, worksheet, row: int, col: int, url: str, display_text: str):
        """
        為 Excel 單元格添加超連結 - 改進版本，減少安全警告
        
        Args:
            worksheet: Excel 工作表
            row: 行號
            col: 列號  
            url: 連結 URL
            display_text: 顯示文字
        """
        try:
            from openpyxl.worksheet.hyperlink import Hyperlink
            from openpyxl.styles import Font
            
            cell = worksheet.cell(row=row, column=col)
            
            # 🆕 方案1: 使用完整的 HYPERLINK 函數格式
            try:
                # 使用 Excel 的 HYPERLINK 函數，這樣 Excel 會更友善地處理
                cell.value = f'=HYPERLINK("{url}","{display_text}")'
                cell.font = Font(color="0000FF", underline="single")
                self.logger.debug(f"添加 HYPERLINK 函數: {display_text} → {url}")
                return
            except Exception as e:
                self.logger.warning(f"HYPERLINK 函數失敗，嘗試標準超連結: {str(e)}")
            
            # 🆕 方案2: 標準超連結（備用）
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
                                
    def _format_worksheet_with_background_colors(self, worksheet, sheet_name: str):
        """格式化工作表 - 修正版本，設定Excel頁籤標籤顏色和新的表頭顏色"""
        try:
            from openpyxl.styles import PatternFill, Font, Alignment
            from openpyxl.utils import get_column_letter
            
            # 🆕 設定Excel頁籤標籤顏色
            if sheet_name in ['轉換摘要', '轉換後專案']:
                # 淺藍色頁籤
                worksheet.sheet_properties.tabColor = "ADD8E6"  # Light Blue
            elif sheet_name in ['來源的 manifest', '轉換後的 manifest', 'gerrit 上的 manifest']:
                # 淺綠色頁籤
                worksheet.sheet_properties.tabColor = "90EE90"  # Light Green
            elif sheet_name in ['轉換後與 Gerrit manifest 的差異', '未轉換專案']:
                # 淺紅色頁籤
                worksheet.sheet_properties.tabColor = "FFB6C1"  # Light Pink
            
            # 🆕 新增顏色定義
            blue_header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")  # 藍底
            green_fill = PatternFill(start_color="00B050", end_color="00B050", fill_type="solid")        # 綠底
            red_fill = PatternFill(start_color="C5504B", end_color="C5504B", fill_type="solid")         # 紅底
            orange_fill = PatternFill(start_color="FF8C00", end_color="FF8C00", fill_type="solid")      # 🆕 橘底
            purple_fill = PatternFill(start_color="8A2BE2", end_color="8A2BE2", fill_type="solid")      # 🆕 紫底
            
            white_font = Font(color="FFFFFF", bold=True)    # 白字
            blue_font = Font(color="0070C0", bold=True)     # 藍字
            gray_font = Font(color="808080", bold=True)     # 灰字
            
            # 🆕 定義特殊顏色的欄位
            orange_header_fields = ["推送狀態", "推送結果", "Commit ID", "Review URL"]
            green_header_fields = ["Gerrit 源檔案", "Gerrit 展開檔案", "Gerrit 目標檔案"]
            purple_header_fields = ["源檔案", "輸出檔案", "目標檔案"]
            
            # 設定表頭和欄寬
            for col_num, cell in enumerate(worksheet[1], 1):
                col_letter = get_column_letter(col_num)
                header_value = str(cell.value) if cell.value else ''
                
                # 🆕 根據欄位名稱設定特殊顏色
                if header_value in orange_header_fields:
                    cell.fill = orange_fill
                    cell.font = white_font
                    self.logger.debug(f"設定橘底白字表頭: {header_value}")
                elif header_value in green_header_fields:
                    cell.fill = green_fill
                    cell.font = white_font
                    self.logger.debug(f"設定綠底白字表頭: {header_value}")
                elif header_value in purple_header_fields:
                    cell.fill = purple_fill
                    cell.font = white_font
                    self.logger.debug(f"設定紫底白字表頭: {header_value}")
                else:
                    # 預設所有其他表頭都是藍底白字
                    cell.fill = blue_header_fill
                    cell.font = white_font
                
                cell.alignment = Alignment(horizontal='center', vertical='center')
                
                # 特殊處理差異頁籤
                if sheet_name == "轉換後專案":
                    if header_value == '原始 Revision':
                        cell.fill = red_fill
                        cell.font = white_font
                        worksheet.column_dimensions[col_letter].width = 35
                    elif header_value == '轉換後 Revision':
                        cell.fill = red_fill
                        cell.font = white_font
                        worksheet.column_dimensions[col_letter].width = 35
                    elif header_value == 'Revision 是否相等':
                        cell.fill = red_fill
                        cell.font = white_font
                        worksheet.column_dimensions[col_letter].width = 15
                    elif 'revision' in header_value.lower():
                        worksheet.column_dimensions[col_letter].width = 35

                # 特殊處理差異頁籤
                elif sheet_name == "轉換後與 Gerrit manifest 的差異":
                    # gerrit_ 開頭的欄位用綠底白字（但前面已經被特殊顏色覆蓋了）
                    if header_value.startswith('gerrit_') and header_value not in green_header_fields:
                        cell.fill = green_fill
                        cell.font = white_font
                    
                    # gerrit_revision 用紅底白字
                    elif header_value in ['gerrit_revision']:
                        cell.fill = red_fill
                        cell.font = white_font
                    
                    # comparison_status 和 comparison_result 用紅底白字
                    elif header_value in ['comparison_status', 'comparison_result']:
                        cell.fill = red_fill
                        cell.font = white_font
                    
                    # 設定欄寬
                    if 'content' in header_value or 'gerrit_content' in header_value:
                        worksheet.column_dimensions[col_letter].width = 80
                    elif 'revision' in header_value.lower():
                        worksheet.column_dimensions[col_letter].width = 35
                    elif 'comparison' in header_value:
                        worksheet.column_dimensions[col_letter].width = 20
                    elif header_value in ['name', 'gerrit_name']:
                        worksheet.column_dimensions[col_letter].width = 25
                    
                    # 根據比較狀態設定行的背景色
                    self._set_comparison_row_colors(worksheet, col_num, header_value)
                
                # manifest 相關頁籤的處理
                elif sheet_name in ['來源的 manifest', '轉換後的 manifest', 'gerrit 上的 manifest']:
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
            
            # 設定轉換後專案頁籤的轉換狀態顏色
            if sheet_name == "轉換後專案":
                self._set_conversion_status_colors_v2(worksheet)
            
            self.logger.debug(f"已格式化工作表: {sheet_name}")
            
        except Exception as e:
            self.logger.error(f"格式化工作表失敗 {sheet_name}: {str(e)}")
            
    def _format_worksheet_unified(self, worksheet, sheet_name: str):
        """統一格式化工作表 - 修正版本"""
        try:
            from openpyxl.styles import PatternFill, Font, Alignment
            from openpyxl.utils import get_column_letter
            
            # 統一顏色定義
            blue_header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")  # 藍底
            green_fill = PatternFill(start_color="00B050", end_color="00B050", fill_type="solid")        # 綠底
            red_fill = PatternFill(start_color="C5504B", end_color="C5504B", fill_type="solid")         # 紅底
            
            white_font = Font(color="FFFFFF", bold=True)    # 白字
            blue_font = Font(color="0070C0", bold=True)     # 藍字
            gray_font = Font(color="808080", bold=True)     # 灰字
            
            # 統一設定所有表頭為藍底白字
            for col_num, cell in enumerate(worksheet[1], 1):
                col_letter = get_column_letter(col_num)
                header_value = str(cell.value) if cell.value else ''
                
                # 預設所有表頭都是藍底白字
                cell.fill = blue_header_fill
                cell.font = white_font
                cell.alignment = Alignment(horizontal='center', vertical='center')
                
                # 特殊處理差異頁籤
                if sheet_name == "轉換後與 Gerrit manifest 的差異":
                    # gerrit_ 開頭的欄位用綠底白字
                    if header_value.startswith('gerrit_'):
                        cell.fill = green_fill
                        cell.font = white_font
                    
                    # original_revision 和 gerrit_revision 用紅底白字
                    elif header_value in ['original_revision', 'gerrit_revision']:
                        cell.fill = red_fill
                        cell.font = white_font
                    
                    # 🆕 comparison_status 和 comparison_result 用紅底白字
                    elif header_value in ['comparison_status', 'comparison_result']:
                        cell.fill = red_fill
                        cell.font = white_font
                    
                    # 設定欄寬
                    if 'content' in header_value or 'gerrit_content' in header_value:
                        worksheet.column_dimensions[col_letter].width = 80
                    elif 'revision' in header_value:
                        worksheet.column_dimensions[col_letter].width = 35
                    elif 'comparison' in header_value:
                        worksheet.column_dimensions[col_letter].width = 20
                    elif header_value in ['name', 'gerrit_name']:
                        worksheet.column_dimensions[col_letter].width = 25
                    
                    # 根據比較狀態設定行的背景色
                    self._set_comparison_row_colors(worksheet, col_num, header_value)
                
                # 轉換後專案頁籤的特殊處理
                elif sheet_name == "轉換後專案":
                    if header_value == '原始 Revision':
                        cell.fill = red_fill
                        cell.font = white_font
                        worksheet.column_dimensions[col_letter].width = 35
                    elif header_value == '轉換後 Revision':
                        cell.fill = red_fill
                        cell.font = white_font
                        worksheet.column_dimensions[col_letter].width = 35
                    elif 'revision' in header_value.lower():
                        worksheet.column_dimensions[col_letter].width = 35
                
                # manifest 相關頁籤的處理
                elif sheet_name in ['來源的 manifest', '轉換後的 manifest', 'gerrit 上的 manifest']:
                    if 'revision' in header_value.lower():
                        worksheet.column_dimensions[col_letter].width = 35
                    elif header_value in ['name']:
                        worksheet.column_dimensions[col_letter].width = 25
                    elif header_value in ['path']:
                        worksheet.column_dimensions[col_letter].width = 30
                    elif header_value in ['groups']:
                        worksheet.column_dimensions[col_letter].width = 40
                
                # 其他頁籤的一般欄寬調整
                else:
                    if 'revision' in header_value.lower():
                        worksheet.column_dimensions[col_letter].width = 35
                    elif '名稱' in header_value or 'name' in header_value:
                        worksheet.column_dimensions[col_letter].width = 25
                    elif '路徑' in header_value or 'path' in header_value:
                        worksheet.column_dimensions[col_letter].width = 30
            
            # 設定轉換後專案頁籤的轉換狀態顏色（移除是否轉換欄位的處理）
            if sheet_name == "轉換後專案":
                self._set_conversion_status_colors_v2(worksheet)
            
            self.logger.debug(f"已格式化工作表: {sheet_name}")
            
        except Exception as e:
            self.logger.error(f"格式化工作表失敗 {sheet_name}: {str(e)}")

    def _set_conversion_status_colors_v2(self, worksheet):
        """設定轉換狀態的文字顏色 - 修正版本，移除是否轉換欄位"""
        try:
            from openpyxl.styles import Font
            
            blue_font = Font(color="0070C0", bold=True)   # 藍字
            gray_font = Font(color="808080", bold=True)   # 灰字
            
            # 只找轉換狀態欄位
            status_column = None
            
            for col_num, cell in enumerate(worksheet[1], 1):
                header_value = str(cell.value) if cell.value else ''
                if '轉換狀態' in header_value:
                    status_column = col_num
                    break
            
            # 設定轉換狀態顏色
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
            
    def _set_conversion_status_colors(self, worksheet):
        """設定轉換狀態的文字顏色"""
        try:
            from openpyxl.styles import Font
            from openpyxl.utils import get_column_letter
            
            blue_font = Font(color="0070C0", bold=True)   # 藍字
            gray_font = Font(color="808080", bold=True)   # 灰字
            
            # 找到轉換狀態和是否轉換欄位
            status_column = None
            conversion_column = None
            
            for col_num, cell in enumerate(worksheet[1], 1):
                header_value = str(cell.value) if cell.value else ''
                if '轉換狀態' in header_value:
                    status_column = col_num
                elif '是否轉換' in header_value:
                    conversion_column = col_num
            
            # 設定轉換狀態顏色
            if status_column:
                for row_num in range(2, worksheet.max_row + 1):
                    status_cell = worksheet.cell(row=row_num, column=status_column)
                    status_value = str(status_cell.value) if status_cell.value else ''
                    
                    if '🔄 已轉換' in status_value:
                        status_cell.font = blue_font
                    elif '⭕ 未轉換' in status_value:
                        status_cell.font = gray_font
            
            # 設定是否轉換欄位顏色
            if conversion_column:
                col_letter = get_column_letter(conversion_column)
                for row_num in range(2, worksheet.max_row + 1):
                    cell = worksheet[f"{col_letter}{row_num}"]
                    cell_value = str(cell.value) if cell.value else ''
                    
                    if cell_value == '是':
                        cell.font = blue_font
                    elif cell_value == '否':
                        cell.font = gray_font
            
        except Exception as e:
            self.logger.error(f"設定轉換狀態顏色失敗: {str(e)}")
            
    def _set_comparison_row_colors(self, worksheet, status_col_num: int, header_value: str):
        """設定比較狀態的行顏色 - 修正版本"""
        try:
            from openpyxl.styles import PatternFill
            
            # 找到比較狀態欄位
            if header_value != 'comparison_status':
                return
            
            # 定義狀態顏色（覆蓋頁籤底色）
            status_colors = {
                '✅ 相同': PatternFill(start_color="D4FFCD", end_color="D4FFCD", fill_type="solid"),     # 深一點的綠
                '❌ 不同': PatternFill(start_color="FFCCCC", end_color="FFCCCC", fill_type="solid"),     # 深一點的紅
                '🆕 新增': PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid"),     # 深一點的黃
                '🗑️ 刪除': PatternFill(start_color="FFDAB9", end_color="FFDAB9", fill_type="solid")      # 深一點的橘
            }
            
            # 設定每一行的背景色
            for row_num in range(2, worksheet.max_row + 1):
                status_cell = worksheet.cell(row=row_num, column=status_col_num)
                status_value = str(status_cell.value) if status_cell.value else ''
                
                # 根據狀態設定整行背景色
                for status, fill_color in status_colors.items():
                    if status in status_value:
                        for col in range(1, worksheet.max_column + 1):
                            worksheet.cell(row=row_num, column=col).fill = fill_color
                        break
            
        except Exception as e:
            self.logger.error(f"設定比較狀態行顏色失敗: {str(e)}")
                        
    def _format_unchanged_projects_sheet(self, worksheet):
        """格式化未轉換專案頁籤 - 新方法"""
        try:
            from openpyxl.styles import PatternFill, Font
            from openpyxl.utils import get_column_letter
            
            # 定義顏色（灰色系，表示未變化）
            gray_fill = PatternFill(start_color="D3D3D3", end_color="D3D3D3", fill_type="solid")    # 灰底
            white_font = Font(color="FFFFFF", bold=True)  # 白字
            
            # 設定表頭格式
            for col_num, cell in enumerate(worksheet[1], 1):
                cell.fill = gray_fill
                cell.font = white_font
                
                # 設定欄寬
                col_letter = get_column_letter(col_num)
                header_value = str(cell.value) if cell.value else ''
                
                if 'Revision' in header_value:
                    worksheet.column_dimensions[col_letter].width = 35
                elif '專案名稱' in header_value:
                    worksheet.column_dimensions[col_letter].width = 25
                elif '原因' in header_value:
                    worksheet.column_dimensions[col_letter].width = 30
            
            self.logger.info("已設定未轉換專案頁籤格式")
            
        except Exception as e:
            self.logger.error(f"格式化未轉換專案頁籤失敗: {str(e)}")
            
    def _format_converted_projects_sheet_v2(self, worksheet):
        """格式化轉換後專案頁籤 - 新版本（支援轉換狀態分類）"""
        try:
            from openpyxl.styles import PatternFill, Font
            from openpyxl.utils import get_column_letter
            
            # 定義顏色
            red_fill = PatternFill(start_color="C5504B", end_color="C5504B", fill_type="solid")    # 紅底
            green_fill = PatternFill(start_color="00B050", end_color="00B050", fill_type="solid")   # 綠底
            blue_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")    # 藍底
            white_font = Font(color="FFFFFF", bold=True)  # 白字
            blue_font = Font(color="0070C0", bold=True)   # 藍字
            gray_font = Font(color="808080", bold=True)   # 灰字
            
            # 🆕 特殊格式化欄位
            special_columns = {
                '轉換狀態': blue_fill,
                '原始 Revision': red_fill,
                '轉換後 Revision': red_fill,
                '轉換說明': green_fill
            }
            
            # 找到各欄位並設定表頭格式
            status_column = None
            conversion_column = None
            
            for col_num, cell in enumerate(worksheet[1], 1):  # 標題列
                col_letter = get_column_letter(col_num)
                header_value = str(cell.value) if cell.value else ''
                
                # 設定特殊欄位的表頭格式
                if header_value in special_columns:
                    cell.fill = special_columns[header_value]
                    cell.font = white_font
                    
                    # 設定欄寬
                    if 'Revision' in header_value or '轉換說明' in header_value:
                        worksheet.column_dimensions[col_letter].width = 35
                    elif '轉換狀態' in header_value:
                        worksheet.column_dimensions[col_letter].width = 15
                        status_column = col_num
                elif header_value == '是否轉換':
                    conversion_column = col_num
            
            # 🆕 根據轉換狀態設定行的顏色
            if status_column:
                for row_num in range(2, worksheet.max_row + 1):
                    status_cell = worksheet.cell(row=row_num, column=status_column)
                    status_value = str(status_cell.value) if status_cell.value else ''
                    
                    if '🔄 已轉換' in status_value:
                        status_cell.font = blue_font  # 藍色文字
                    elif '⭕ 未轉換' in status_value:
                        status_cell.font = gray_font  # 灰色文字
            
            # 設定是否轉換欄位的內容顏色
            if conversion_column:
                col_letter = get_column_letter(conversion_column)
                for row_num in range(2, worksheet.max_row + 1):
                    cell = worksheet[f"{col_letter}{row_num}"]
                    cell_value = str(cell.value) if cell.value else ''
                    
                    if cell_value == '是':
                        cell.font = blue_font  # 是：藍色
                    elif cell_value == '否':
                        cell.font = gray_font   # 否：灰色
            
            self.logger.info("已設定轉換後專案頁籤格式（新版本）：支援轉換狀態分類")
            
        except Exception as e:
            self.logger.error(f"格式化轉換後專案頁籤失敗: {str(e)}")
            
    def _format_expand_status_columns(self, worksheet, use_expanded: bool):
        """格式化展開狀態欄位 - 新增方法"""
        try:
            from openpyxl.styles import Font
            from openpyxl.utils import get_column_letter
            
            # 定義顏色
            blue_font = Font(color="0070C0", bold=True)   # 藍字（是）
            black_font = Font(color="000000")             # 黑字（否）
            
            # 找到展開相關欄位的位置
            expand_columns = {}
            for col_num, cell in enumerate(worksheet[1], 1):  # 標題列
                header_value = str(cell.value) if cell.value else ''
                
                if 'include 標籤' in header_value or '展開檔案轉換' in header_value:
                    expand_columns[header_value] = col_num
            
            # 格式化展開狀態欄位
            for header_name, col_num in expand_columns.items():
                col_letter = get_column_letter(col_num)
                
                # 資料列（第2列開始）
                for row_num in range(2, worksheet.max_row + 1):
                    cell = worksheet[f"{col_letter}{row_num}"]
                    cell_value = str(cell.value) if cell.value else ''
                    
                    if '是' in cell_value:
                        cell.font = blue_font  # 是：藍色
                    elif '否' in cell_value:
                        cell.font = black_font   # 否：黑色
            
            self.logger.info("已設定展開狀態欄位格式：是=藍字，否=黑字")
            
        except Exception as e:
            self.logger.error(f"格式化展開狀態欄位失敗: {str(e)}")

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
                                  target_download_success: bool, push_result: Optional[Dict[str, Any]] = None,
                                  expanded_file_path: Optional[str] = None, use_expanded: bool = False) -> str:
        """安全的 Excel 報告生成 - 包含展開檔案資訊"""
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
                          excel_file: str, source_download_success: bool, target_download_success: bool,
                          expanded_file_path: Optional[str] = None):
        """最終檔案檢查和報告 - 增強版本，包含展開檔案"""
        try:
            self.logger.info("📁 最終檔案檢查報告:")
            self.logger.info(f"📂 輸出資料夾: {output_folder}")
            
            # 檢查所有應該存在的檔案
            files_to_check = []
            
            if source_file_path:
                status = "✅" if source_download_success else "❌"
                files_to_check.append((f"Gerrit 源檔案 {status}", source_file_path))
            
            if expanded_file_path:
                files_to_check.append(("Gerrit 展開檔案 ✅", expanded_file_path))
            
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
            
            if expanded_file_path:
                self.logger.info(f"  🟢 Manifest 展開: {'✅ 成功' if os.path.exists(expanded_file_path) else '❌ 失敗'}")
            
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
                        is_expanded = "_expand.xml" in filename
                        file_type = "(展開檔案)" if is_expanded else "(原始檔案)"
                        self.logger.info(f"    - {filename} ({size} bytes) {file_type}")
                    
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
                if expanded_file_path:
                    expanded_filename = os.path.basename(expanded_file_path)
                    self.logger.info(f"🎯 重點提醒: 已保存展開檔案為 {expanded_filename}")
                    self.logger.info(f"🎯 轉換使用的是展開後的檔案")
                if not target_download_success:
                    self.logger.info(f"📋 Excel 報告中已記錄目標檔案下載失敗狀態（紅字標示）")
            else:
                self.logger.warning(f"\n⚠️ 部分檔案可能保存失敗，請檢查上述報告")
                
        except Exception as e:
            self.logger.error(f"檔案檢查報告失敗: {str(e)}")

    def _is_revision_hash(self, revision: str) -> bool:
        """
        判斷 revision 是否為 commit hash
        
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


    def _get_effective_revision_for_conversion(self, project_element) -> str:
        """
        取得用於轉換的有效 revision（XML 元素版本）
        
        邏輯：
        - 如果 revision 是 hash → 使用 upstream
        - 如果 revision 是 branch name → 使用 revision
        - 如果都沒有 → 使用 default revision（如果 remote=rtk）
        
        Args:
            project_element: XML project 元素
            
        Returns:
            用於轉換的 revision 字串
        """
        revision = project_element.get('revision', '')
        upstream = project_element.get('upstream', '')
        remote = project_element.get('remote', '') or self.default_remote
        
        # 如果 revision 是 hash，使用 upstream
        if self._is_revision_hash(revision):
            if upstream:
                self.logger.debug(f"專案 {project_element.get('name', '')} revision 是 hash，使用 upstream: {upstream}")
                return upstream
            else:
                self.logger.warning(f"專案 {project_element.get('name', '')} revision 是 hash 但沒有 upstream")
                return ''
        
        # 如果 revision 是 branch name，直接使用
        if revision:
            self.logger.debug(f"專案 {project_element.get('name', '')} revision 是 branch name: {revision}")
            return revision
        
        # 如果沒有 revision，返回空字串（會由其他邏輯處理 default revision）
        self.logger.debug(f"專案 {project_element.get('name', '')} 沒有 revision")
        return ''
                
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

修正重點：
1. 重命名 _expand_manifest_with_repo 為 _expand_manifest_with_repo_fixed
2. 在 _expand_manifest_with_repo_fixed 中立即保存展開檔案到最終目標位置
3. 增加多層驗證確保檔案正確保存
4. 增強日誌輸出和錯誤診斷
5. 確保 repo 命令錯誤處理更完善
6. 修改特殊項目處理邏輯，移除特定項目限制，改用通用檢查邏輯
"""